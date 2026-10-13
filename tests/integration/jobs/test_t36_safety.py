"""Independent T36 checks use actual loopback PostgreSQL and synthetic actors."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import os
import subprocess
import sys
from threading import Event, get_ident
from time import monotonic
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session

from services.api.app.audit.models import AuditEvent
from services.api.app.auth.models import AuthOwnedResource, AuthSession, AuthUser
from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput
from services.api.app.jobs.models import CleanupPermit, DurableJob, JobAttempt, InboxNotification, NotificationPreference
from services.api.app.jobs.schemas import JobClaim, JobsPolicy
from services.api.app.jobs.service import JobsService
from services.api.app.notifications.schemas import MarkReadInput, PreferenceInput


pytestmark = pytest.mark.postgres
SENTINEL = "DEMO_T36_PRIVATE_FAILURE_SENTINEL"


def denied(operation, *statuses):
    with pytest.raises(Exception) as failure:
        operation()
    assert getattr(failure.value, "status_code", None) in statuses
    assert SENTINEL not in str(failure.value) + repr(failure.value)
    return failure.value


def observe_lock(engine, pids, blocker_pid, pending):
    deadline, pause = monotonic() + 40, Event()
    with engine.connect() as connection:
        while monotonic() < deadline:
            if pending.done():
                pending.result()
                pytest.fail("The worker finished before the required PostgreSQL lock wait")
            connection.execute(text("SELECT pg_stat_clear_snapshot()"))
            if pids and connection.scalar(text("SELECT wait_event_type='Lock' AND "
                ":blocker=ANY(pg_blocking_pids(pid)) FROM pg_stat_activity WHERE pid=:pid"),
                {"blocker": blocker_pid, "pid": pids[0]}):
                return
            pause.wait(0.01)
    pytest.fail("No actual PostgreSQL job lock wait was observed")


def original_rows(engine):
    """Capture frozen effects only; worker SELECT observation is separate."""
    from services.api.app.assessments.models import AssessmentsBase
    from services.api.app.plan_execution.models import ExecutionBase
    from services.api.app.releases.models import OutboxEvent

    with engine.connect() as connection:
        result = {name: connection.execute(select(table).order_by(*table.primary_key.columns)).mappings().all()
            for base in (AssessmentsBase, ExecutionBase) for name, table in base.metadata.tables.items()}
        result["catalog_outbox"] = connection.execute(select(OutboxEvent.__table__)
            .order_by(OutboxEvent.id)).mappings().all()
    return result


def success_audits(engine):
    with engine.connect() as connection:
        return set(connection.scalars(select(AuditEvent.id).where(AuditEvent.outcome == "succeeded")))


def readmit(case):
    """A new consent never reauthorizes the original opt-in/profile proof."""
    privacy = case.profiles.privacy_service
    principal = case.profiles.auth_service.get_principal(case.owner.cookie)
    before = privacy.get_admission(principal)
    adult = privacy.declare_age(principal, AgeDeclarationInput(age_band="18_plus", confirmed=True,
        notice_id=before.notice_id, expected_revision=before.revision))
    privacy.confirm_core(principal, CoreConsentInput(purpose="core_consultation", confirmed=True,
        notice_id=adult.notice_id, expected_revision=adult.revision))
    return principal


def job_row(engine, job_id):
    with Session(engine) as session:
        return dict(session.execute(select(DurableJob.__table__).where(DurableJob.id == job_id)).mappings().one())


def notification_claim(case, engine):
    """Run genuine system effects, retaining the private job's committed claim."""
    case.jobs.enqueue_outbox()
    found = []
    for _ in range(10):
        claimed = case.jobs.claim(uuid4())
        if claimed is None:
            break
        row = job_row(engine, claimed.job_id)
        if row["kind"] == "notification":
            if row["event_id"] == case.event_id:
                found.append(claimed)
        else:
            assert case.jobs.run_claim(claimed).status in {"completed", "queued"}
    assert len(found) == 1, "The real withdrawal must generate one bound private reminder"
    return found[0]


def new_login(case, engine, clock):
    """The same fixed synthetic account receives a new real database session."""
    from services.api.app.auth.service import digest_secret
    cookie, session_id = SecretStr("DEMO_T36_SESSION_" + uuid4().hex), uuid4()
    with Session(engine) as session, session.begin():
        session.add(AuthSession(id=session_id, user_id=case.owner.user_id,
            session_digest=digest_secret(cookie, "session"), created_at=clock(),
            expires_at=clock() + timedelta(hours=1), revoked_at=None))
    return case.auth.get_principal(cookie)


def test_two_actual_consumers_skip_locked_jobs_without_mutating_old_outbox(job_case_factory, pg_engine, clock):
    case = job_case_factory(opt_in=False, withdraw=True)
    original = original_rows(pg_engine)
    assert len(case.jobs.enqueue_outbox()) == 2
    statements, second_pids = [], []

    def observed(connection, cursor, sql, parameters, context, executemany):
        if "skip locked" in sql.lower():
            statements.append(sql)

    event.listen(pg_engine, "before_cursor_execute", observed)
    try:
        with Session(pg_engine) as first:
            first.begin()
            first_pid = first.scalar(text("SELECT pg_backend_pid()"))
            a = case.jobs.store.claim(first, uuid4(), now=clock(), policy=case.jobs.policy)
            assert a is not None
            with ThreadPoolExecutor(max_workers=1) as pool:
                def other():
                    with Session(pg_engine) as second, second.begin():
                        second_pids.append(second.scalar(text("SELECT pg_backend_pid()")))
                        return case.jobs.store.claim(second, uuid4(), now=clock(), policy=case.jobs.policy)
                b = pool.submit(other).result(timeout=15)
            assert b is not None and b.job_id != a.job_id
            assert second_pids[0] != first_pid
            assert job_row(pg_engine, b.job_id)["lease_token"] == b.lease_token
            first.commit()
    finally:
        event.remove(pg_engine, "before_cursor_execute", observed)
    assert len(statements) >= 2
    assert case.jobs.run_claim(a).status == case.jobs.run_claim(b).status == "completed"
    assert case.jobs.claim(uuid4()) is None
    assert original_rows(pg_engine) == original
    with Session(pg_engine) as session:
        assert session.scalars(select(InboxNotification)).all() == []


def test_new_process_recovers_expired_lease_and_old_token_cannot_write(job_case_factory, pg_engine, clock):
    case = job_case_factory(opt_in=False, withdraw=True, lease_seconds=2)
    case.jobs.enqueue_outbox()
    old = case.jobs.claim(uuid4())
    assert old is not None
    original = original_rows(pg_engine)
    clock.advance(3)
    with pg_engine.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    # A separate Python process sees only the dedicated test URL and schema;
    # no old process state, migrations, session cookies or private payloads.
    code = """
import json, os, re, sys
from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from services.api.app.jobs.schemas import JobsPolicy
from services.api.app.jobs.store import JobsStore
data=json.load(sys.stdin)
url=os.environ['T23_TEST_POSTGRES_URL']
target=urlsplit(url)
assert target.hostname=='127.0.0.1' and target.port==55438 and target.path=='/study_t23_20261003'
assert re.fullmatch(r'jobs_t36_[0-9a-f]{32}',data['schema'])
engine=create_engine(url,hide_parameters=True,connect_args={'options':'-csearch_path='+data['schema'],'connect_timeout':5})
store=JobsStore(engine)
store.assert_schema_ready()
with Session(engine) as session,session.begin():
    result=store.claim(session,UUID(data['worker']),now=datetime.fromisoformat(data['now']),policy=JobsPolicy.model_validate(data['policy']))
print(result.model_dump_json())
engine.dispose()
"""
    completed = subprocess.run([sys.executable, "-X", "utf8", "-B", "-c", code],
        input=json.dumps({"schema": schema, "worker": str(uuid4()), "now": clock().isoformat(),
            "policy": case.jobs.policy.model_dump(mode="json")}), text=True,
        capture_output=True, timeout=30, env=os.environ.copy(), check=False)
    assert completed.returncode == 0, "The isolated new worker process must recover its persisted claim"
    fresh = JobClaim.model_validate_json(completed.stdout)
    assert fresh.job_id == old.job_id and fresh.generation == old.generation + 1
    assert fresh.worker_id != old.worker_id and fresh.lease_token != old.lease_token
    before = job_row(pg_engine, old.job_id)
    denied(lambda: case.jobs.run_claim(old), 409)
    denied(lambda: case.jobs.retry_claim(old), 409)
    assert job_row(pg_engine, old.job_id) == before
    # Publication propagation does not borrow its old administrator's login.
    case.releases.auth_service.logout(case.reviewer.actor.cookie,
        case.releases.auth_service.get_csrf_token(case.reviewer.actor.cookie).token)
    restarted = JobsService(case.changes, case.notifications, case.jobs.store, case.jobs.policy)
    assert restarted.run_claim(fresh).status == "completed"
    assert original_rows(pg_engine) == original


def test_current_owner_reads_and_new_consent_do_not_revive_original_opt_in(
        job_case_factory, pg_engine, clock, actor_factory):
    first = job_case_factory(withdraw=True)
    claimed = notification_claim(first, pg_engine)
    outsider = actor_factory()
    foreign = first.auth.get_principal(outsider.cookie)
    privacy = first.profiles.privacy_service
    before = privacy.get_admission(foreign)
    adult = privacy.declare_age(foreign, AgeDeclarationInput(age_band="18_plus", confirmed=True,
        notice_id=before.notice_id, expected_revision=before.revision))
    privacy.confirm_core(foreign, CoreConsentInput(purpose="core_consultation", confirmed=True,
        notice_id=adult.notice_id, expected_revision=adult.revision))
    assert first.notifications.list_notifications(foreign).items == ()
    denied(lambda: first.notifications.list_notifications(first.reviewer.principal), 403)
    # The original opt-in remains tied to the original consent after a genuine
    # withdrawal and new confirmation; a new consent is not automatic delivery.
    old = privacy.get_admission(first.principal)
    privacy.withdraw_core(first.principal, old.consent_id)
    current = privacy.get_admission(first.principal)
    privacy.confirm_core(first.principal, CoreConsentInput(purpose="core_consultation", confirmed=True,
        notice_id=current.notice_id, expected_revision=current.revision))
    cancelled = first.jobs.run_claim(claimed)
    assert cancelled.status == "cancelled" and cancelled.reason == "AUTHORITY_REVOKED"
    assert first.notifications.get_preferences(first.principal).enabled is False
    from services.api.app.profiles.schemas import AppendInput
    latest = first.profiles.append_version(first.principal, first.profile.profile_id, AppendInput(
        expected_current_version=first.profile.version, profile=first.profile.profile, confirmed=True)).version
    chosen = first.notifications.update_preferences(first.principal, PreferenceInput(
        expected_version=first.preference.version, enabled=True, profile_id=latest.profile_id, student_confirmed=True))
    assert chosen.enabled and chosen.profile_version_id == latest.version_id
    assert first.notifications.list_notifications(first.principal).items == ()
    assert job_row(pg_engine, claimed.job_id)["status"] == "cancelled"
    # A new login can recover a finite, effective-off CAS without rebinding it.
    first.auth.logout(first.owner.cookie, first.auth.get_csrf_token(first.owner.cookie).token)
    fresh_principal = new_login(first, pg_engine, clock)
    with Session(pg_engine) as session:
        saved = dict(session.execute(select(NotificationPreference.__table__).where(
            NotificationPreference.owner_user_id == first.owner.user_id)).mappings().one())
    effective = first.notifications.get_preferences(fresh_principal)
    assert not effective.enabled and effective.version == chosen.version
    assert effective.profile_id is effective.profile_version_id is effective.profile_sha256 is None
    with Session(pg_engine) as session:
        assert dict(session.execute(select(NotificationPreference.__table__).where(
            NotificationPreference.owner_user_id == first.owner.user_id)).mappings().one()) == saved
    enabled = first.notifications.update_preferences(fresh_principal, PreferenceInput(
        expected_version=effective.version, enabled=True, profile_id=latest.profile_id, student_confirmed=True))
    assert enabled.enabled and enabled.version == effective.version + 1
    assert job_row(pg_engine, claimed.job_id)["status"] == "cancelled"


@pytest.mark.parametrize("deadline", ["session", "lease", "job"])
def test_actual_last_role_sql_wait_rechecks_private_authority_or_lease(
        job_case_factory, pg_engine, clock, monkeypatch, deadline):
    case = job_case_factory(withdraw=True, lease_seconds=40 if deadline == "lease" else 120)
    claimed = notification_claim(case, pg_engine)
    if deadline == "session":
        with Session(pg_engine) as session, session.begin():
            session.get(AuthSession, case.owner.session_id).expires_at = clock() + timedelta(seconds=40)
    elif deadline == "job":
        # Shorten this new mutable job only. Its original committed claim keeps
        # a 120-second lease, so expiry cannot be hidden by the lease guard.
        with Session(pg_engine) as session, session.begin():
            session.get(DurableJob, claimed.job_id).expires_at = clock() + timedelta(seconds=40)
        assert claimed.lease_until == clock() + timedelta(seconds=120)
    original = original_rows(pg_engine)
    with Session(pg_engine) as session:
        user_audits = set(session.scalars(select(AuditEvent.id).where(
            AuditEvent.actor_user_id == case.owner.user_id, AuditEvent.outcome == "succeeded")))
    state = {"worker": None, "written": False, "inside_final": False, "roles": 0, "blocked": False}
    reached, pids, lock = Event(), [], uuid4().int % (2 ** 62)
    original_final = case.profiles._final

    def final(*args, **kwargs):
        state["inside_final"] = state["written"] and get_ident() == state["worker"]
        try:
            return original_final(*args, **kwargs)
        finally:
            state["inside_final"] = False
    monkeypatch.setattr(case.profiles, "_final", final)

    def gate(connection, cursor, sql, parameters, context, executemany):
        if get_ident() != state["worker"]:
            return
        normalized = " ".join(sql.lower().split())
        if normalized.startswith("insert into inbox_notifications"):
            state["written"] = True
        if state["inside_final"] and normalized.startswith("select ") and "from auth_user_roles" in normalized:
            state["roles"] += 1
            # Profile._final refreshes roles once, then its second role SELECT
            # is the actual last SQL before the shared fresh-clock boundary.
            if state["roles"] == 2 and not state["blocked"]:
                state["blocked"] = True
                pids.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
                reached.set()
                connection.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (lock,))
    event.listen(pg_engine, "after_cursor_execute", gate)
    try:
        with pg_engine.connect() as blocker:
            blocker.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock})
            blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
            with ThreadPoolExecutor(max_workers=1) as pool:
                def run():
                    state["worker"] = get_ident()
                    return case.jobs.run_claim(claimed)
                pending = pool.submit(run)
                try:
                    assert reached.wait(40), "The actual last role query was not reached after notification INSERT"
                    observe_lock(pg_engine, pids, blocker_pid, pending)
                    clock.advance(40)
                finally:
                    blocker.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock})
                if deadline == "session":
                    result = pending.result(timeout=60)
                    assert result.status == "cancelled" and result.reason == "AUTHORITY_REVOKED"
                else:
                    denied(lambda: pending.result(timeout=60), 409)
    finally:
        event.remove(pg_engine, "after_cursor_execute", gate)
    assert state["written"] and state["blocked"] and state["roles"] == 2
    with Session(pg_engine) as session:
        assert session.scalars(select(InboxNotification).where(InboxNotification.job_id == claimed.job_id)).all() == []
        assert set(session.scalars(select(AuditEvent.id).where(AuditEvent.actor_user_id == case.owner.user_id,
            AuditEvent.outcome == "succeeded"))) == user_audits
        attempts = session.scalars(select(JobAttempt).where(JobAttempt.job_id == claimed.job_id)).all()
        assert len(attempts) == (1 if deadline == "session" else 0)
    assert original_rows(pg_engine) == original
    if deadline == "lease":
        fresh = case.jobs.claim(uuid4())
        assert fresh.job_id == claimed.job_id and fresh.generation == claimed.generation + 1
        assert case.jobs.run_claim(fresh).status == "completed"
    elif deadline == "job":
        case.jobs.claim(uuid4())
        expired = job_row(pg_engine, claimed.job_id)
        assert expired["status"] == "cancelled" and expired["reason"] == "EXPIRED"


def test_cleanup_requires_persisted_mint_and_survives_logout_without_changing_private_data(
        job_case_factory, pg_engine):
    case = job_case_factory(opt_in=False)
    job_id = case.jobs.accept_cleanup_probe(case.principal, (case.profile.profile_id,), watermark=1)
    original = original_rows(pg_engine)
    claimed = case.jobs.claim(uuid4())
    assert claimed.job_id == job_id
    # A different scope may advance the same owner's watermark. The processor
    # must serialize that acceptance even though the registry IDs do not overlap.
    reached, second_started = Event(), Event()
    state = {"first": None, "second": None, "gated": False}
    first_pids, second_pids, lock = [], [], uuid4().int % (2 ** 62)
    def identify(connection, cursor, sql, parameters, context, executemany):
        if get_ident() == state["second"] and not second_pids:
            second_pids.append(0)
            second_pids[0] = connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one()
            second_started.set()
    def gate(connection, cursor, sql, parameters, context, executemany):
        if (get_ident() == state["first"] and not state["gated"]
            and "max(cleanup_permits.watermark)" in sql.lower()):
            state["gated"] = True
            first_pids.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            reached.set()
            connection.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (lock,))
    event.listen(pg_engine, "before_cursor_execute", identify)
    event.listen(pg_engine, "after_cursor_execute", gate)
    try:
        with pg_engine.connect() as blocker:
            blocker.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock})
            with ThreadPoolExecutor(max_workers=2) as pool:
                def first():
                    state["first"] = get_ident()
                    return case.jobs.run_claim(claimed)
                def second():
                    state["second"] = get_ident()
                    return case.jobs.accept_cleanup_probe(case.principal, (case.plan.plan_id,), watermark=2)
                a = pool.submit(first)
                try:
                    assert reached.wait(40), "The real cleanup watermark query was not reached"
                    b = pool.submit(second)
                    assert second_started.wait(20)
                    observe_lock(pg_engine, second_pids, first_pids[0], b)
                finally:
                    blocker.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock})
                assert a.result(timeout=60).status == "completed"
                second_job_id = b.result(timeout=60)
    finally:
        event.remove(pg_engine, "before_cursor_execute", identify)
        event.remove(pg_engine, "after_cursor_execute", gate)
    assert state["gated"] and first_pids[0] != second_pids[0]
    second_claim = case.jobs.claim(uuid4())
    assert second_claim.job_id == second_job_id
    case.auth.logout(case.owner.cookie, case.auth.get_csrf_token(case.owner.cookie).token)
    assert case.jobs.run_claim(second_claim).status == "completed"
    assert original_rows(pg_engine) == original
    with Session(pg_engine) as session:
        baseline = dict(session.execute(select(CleanupPermit.__table__).where(
            CleanupPermit.watermark == 2)).mappings().one())
    fake_id, fake_audit = uuid4(), uuid4()
    from services.api.app.jobs.schemas import CleanupScope, scope_hash
    forged_scope = CleanupScope.model_validate(baseline["scope"]).model_copy(update={"watermark": 3})
    with Session(pg_engine) as session, session.begin():
        session.add(CleanupPermit(**(baseline | {"id": fake_id, "watermark": 3,
            "scope": forged_scope.model_dump(mode="json"), "scope_sha256": scope_hash(forged_scope),
            "audit_event_id": fake_audit})))
        session.flush()
        fake_job = case.jobs.store.put_job(session, kind="cleanup_probe", natural={"DEMO_forged_permit": str(fake_id)},
            payload={"scope_sha256": scope_hash(forged_scope), "watermark": 3},
            now=case.auth._now(), expires_at=case.auth._now() + timedelta(minutes=5), is_synthetic=True,
            owner=case.owner.user_id, permit_id=fake_id)
        fake_job_id = fake_job.id
    forged_claim = case.jobs.claim(uuid4())
    assert forged_claim.job_id == fake_job_id
    before = job_row(pg_engine, fake_job_id)
    audits = success_audits(pg_engine)
    denied(lambda: case.jobs.run_claim(forged_claim), 409)
    assert job_row(pg_engine, fake_job_id) == before
    assert success_audits(pg_engine) == audits
    assert original_rows(pg_engine) == original
    with Session(pg_engine) as session:
        assert session.scalars(select(InboxNotification)).all() == []
    closed = JobsService(case.changes, case.notifications, case.jobs.store,
        JobsPolicy(enabled=True, allow_test_jobs=True, allow_cleanup_probe=False))
    denied(lambda: closed.run_claim(forged_claim), 503)


def test_disabled_and_mapper_routed_work_fails_before_connection_or_audit(job_case_factory, pg_engine):
    from services.api.app.profiles.models import ProfileVersion
    case = job_case_factory(opt_in=False)
    closed = JobsService(case.changes, case.notifications, case.jobs.store, JobsPolicy())
    statements = []
    def record(*arguments):
        statements.append(arguments[2])
    event.listen(pg_engine, "before_cursor_execute", record)
    try:
        denied(lambda: closed.enqueue_outbox(), 503)
        denied(lambda: closed.claim(uuid4()), 503)
        denied(lambda: closed.accept_cleanup_probe(case.principal, (case.profile.profile_id,), watermark=1), 503)
    finally:
        event.remove(pg_engine, "before_cursor_execute", record)
    assert statements == []
    foreign_engine = create_engine(pg_engine.url, hide_parameters=True)
    connected = []
    event.listen(foreign_engine, "do_connect", lambda *arguments: connected.append(True))
    try:
        for mapper in (DurableJob, JobAttempt, CleanupPermit, InboxNotification, NotificationPreference, ProfileVersion, AuditEvent):
            with Session(bind=pg_engine, binds={mapper: foreign_engine}) as supplied:
                supplied.begin()
                denied(lambda: case.jobs.claim(uuid4(), session=supplied), 503)
                supplied.commit()
        assert connected == []
    finally:
        foreign_engine.dispose()
