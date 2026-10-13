"""Independent private-profile permissions, longitudinal state and PG atomicity."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json
from threading import Event, get_ident
from time import monotonic
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, event, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.audit.models import AuditEvent
from services.api.app.audit.retention import expires_after_months
from services.api.app.auth.models import AuthOwnedResource, AuthSession, AuthUser, AuthUserRole
from services.api.app.idempotency.models import IdempotencyRecord
from services.api.app.privacy.models import PrivacyAdmissionRecord, PrivacyNoticeVersion
from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput
from services.api.app.profiles.models import ProfileRoot, ProfileVersion
from services.api.app.profiles.schemas import AppendInput, CreateInput, ProfilePolicy, ProfileSnapshot

from .conftest import snapshot_payload


pytestmark = pytest.mark.postgres
KEY = SecretStr("DEMO_T23_CREATE_KEY")
SENTINEL = "DEMO_T23_PRIVATE_INPUT_SENTINEL"


def denied(operation, statuses):
    with pytest.raises(ValueError) as failure:
        operation()
    expected = (statuses,) if isinstance(statuses, int) else statuses
    assert getattr(failure.value, "status_code", None) in expected
    assert SENTINEL not in str(failure.value) and SENTINEL not in repr(failure.value)
    assert KEY.get_secret_value() not in str(failure.value)
    return failure.value


def rows(engine, model):
    with engine.connect() as connection:
        return connection.execute(select(model.__table__).order_by(*model.__table__.primary_key.columns)).mappings().all()


def durable_state(engine):
    return tuple(rows(engine, model) for model in (ProfileRoot, ProfileVersion, IdempotencyRecord, AuthOwnedResource)), {
        row["id"] for row in rows(engine, AuditEvent) if row["outcome"] == "succeeded"}


def append_input(version=1, **changes):
    profile = snapshot_payload()
    profile.update(changes)
    return AppendInput(profile=profile, confirmed=True, expected_current_version=version)


def readmit(privacy_service, principal):
    current = privacy_service.get_admission(principal)
    age = privacy_service.declare_age(principal, AgeDeclarationInput(age_band="18_plus", confirmed=True,
        expected_revision=current.revision, notice_id=current.notice_id))
    return privacy_service.confirm_core(principal, CoreConsentInput(confirmed=True, expected_revision=age.revision,
        notice_id=age.notice_id, purpose="core_consultation"))


def require_blocked(engine, worker_pid, blocker_pid, pending):
    deadline, pause = monotonic() + 15, Event()
    with engine.connect() as connection:
        while monotonic() < deadline:
            if pending.done():
                pending.result()
                pytest.fail("Worker completed before reaching a real PostgreSQL lock wait")
            if worker_pid and connection.scalar(text("SELECT wait_event_type='Lock' AND :blocker=ANY(pg_blocking_pids(pid)) "
                    "FROM pg_stat_activity WHERE pid=:pid"), {"blocker": blocker_pid, "pid": worker_pid[0]}):
                return
            pause.wait(0.01)
    pytest.fail("No actual PostgreSQL lock contention observed")


def test_declared_snapshot_preserves_actual_prediction_missing_and_exact_zero(created, profile_service,
        principal, pg_engine, clock):
    saved = created.version
    actual = profile_service.get_profile(principal, saved.profile_id)
    assert actual == saved and actual.source == "student_declared" and actual.is_synthetic is True
    assert actual.expires_at == expires_after_months(actual.confirmed_at, 24)
    assert actual.confirmed_at == clock()
    grades = actual.profile.assessments
    assert grades["gaokao_total"].achieved.value == "625.25"
    assert grades["gaokao_total"].predicted.value == "700.000001"
    assert grades["math"].achieved.value is None and grades["math"].predicted.value == "0"
    assert grades["ielts_overall"].achieved.status == "pending"
    assert actual.profile.weekly_hours is None and actual.profile.preferences is None
    assert actual.profile.residence_region.value == "hk"
    assert actual.profile.exam_province.value == "zhejiang"
    assert actual.profile.applicant_category.value == "cn_mainland"
    assert actual.adaptation.status == "unknown" and actual.adaptation.reason == "ADAPTER_NOT_IMPLEMENTED"
    wire = actual.model_dump(mode="json")
    assert not {"owner_user_id", "consent_id", "admission_id", "declaration_id", "session_id"} & wire.keys()
    payload = actual.profile.model_dump(mode="json")
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    assert actual.profile_sha256 == sha256(canonical).hexdigest()
    assert len(rows(pg_engine, ProfileRoot)) == len(rows(pg_engine, ProfileVersion)) == 1


def test_append_keeps_old_snapshot_and_create_receipt_replays_original_version(created, profile_service,
        principal, create_input, pg_engine):
    before = rows(pg_engine, ProfileVersion)
    appended = profile_service.append_version(principal, created.version.profile_id,
        append_input(weekly_hours="0", preferences={"preferred_fields": [SENTINEL], "preferred_countries": ["GB"], "budget": None}))
    assert appended.replayed is False and appended.version.version == 2
    assert appended.version.profile.weekly_hours == "0"
    assert profile_service.get_version(principal, created.version.profile_id, created.version.version_id) == created.version
    assert profile_service.get_profile(principal, created.version.profile_id) == appended.version
    replay = profile_service.create_profile(principal, create_input, KEY)
    assert replay.replayed is True and replay.version == created.version
    assert rows(pg_engine, ProfileVersion)[0] in before or rows(pg_engine, ProfileVersion)[1] in before
    assert len(rows(pg_engine, ProfileVersion)) == 2
    assert len(rows(pg_engine, IdempotencyRecord)) == 1
    assert rows(pg_engine, AuthOwnedResource)[0]["version"] == 2
    denied(lambda: profile_service.append_version(principal, created.version.profile_id, append_input()), 409)


@pytest.mark.parametrize("field,value,reason", [
    ("course_system", "hkdse", "COURSE_NOT_SUPPORTED"),
    ("pathway", "joint_admission", "PATHWAY_NOT_SUPPORTED"),
    ("applicant_category", "other", "APPLICANT_NOT_SUPPORTED"),
])
def test_unsupported_intent_is_saved_without_inferred_gaokao_qualification(field, value, reason,
        profile_service, principal):
    payload = snapshot_payload()
    payload[field] = {"status": "known", "value": value}
    result = profile_service.create_profile(principal, CreateInput(profile=payload, confirmed=True), KEY)
    assert result.version.profile.model_dump(mode="json")[field] == payload[field]
    assert result.version.adaptation.status == "unsupported" and result.version.adaptation.reason == reason
    assert "eligible" not in result.version.model_dump_json()


def test_two_owners_and_same_client_key_never_share_current_or_historical_payload(created, profile_service,
        principal, admitted_actor_factory, auth_service, create_input, pg_engine):
    bob = auth_service.get_principal(admitted_actor_factory().cookie)
    b = profile_service.create_profile(bob, create_input, KEY).version
    assert b.profile_id != created.version.profile_id
    assert {r.profile_id for r in profile_service.list_profiles(principal).items} == {created.version.profile_id}
    assert {r.profile_id for r in profile_service.list_profiles(bob).items} == {b.profile_id}
    for who, identifier in ((bob, created.version.profile_id), (principal, b.profile_id)):
        denied(lambda: profile_service.get_profile(who, identifier), 404)
        denied(lambda: profile_service.append_version(who, identifier, append_input()), 404)
    denied(lambda: profile_service.get_version(bob, created.version.profile_id, created.version.version_id), 404)
    denied(lambda: profile_service.get_version(principal, created.version.profile_id, b.version_id), 404)
    assert len(rows(pg_engine, IdempotencyRecord)) == 2


def test_metadata_grant_and_administrator_do_not_authorize_profile_content(created, profile_service, principal,
        owner, admitted_actor_factory, actor_factory, auth_service, privacy_service, clock):
    from services.api.app.auth.grants.schemas import AcceptGrantInput, CreateGrantInput, SharingSettings
    from services.api.app.auth.grants.service import SharingService
    sharing = SharingService(auth_service, privacy_service, SharingSettings(fixture_mode=True))
    receiver_actor = admitted_actor_factory()
    receiver = auth_service.get_principal(receiver_actor.cookie)
    policy, management = sharing.get_policy(), sharing.list_grants(principal)
    grant = sharing.create_grant(principal, CreateGrantInput(resource_type="profile", resource_id=created.version.profile_id,
        expected_resource_version=1, grantee_user_id=receiver.user_id, fields=["status", "version"], actions=["read", "list"],
        expires_at=clock() + timedelta(seconds=600), confirmed=True, expected_revision=management.revision,
        owner_consent_id=management.owner_consent_id, sharing_policy_version=policy.policy_version,
        sharing_policy_hash=policy.text_sha256))
    sharing.accept_grant(receiver, grant.grant.id, AcceptGrantInput(confirmed=True, expected_version=grant.grant.version,
        sharing_policy_version=policy.policy_version, sharing_policy_hash=policy.text_sha256))
    projection = sharing.require_shared(receiver, "profile", created.version.profile_id, ("status", "version"))
    assert "assessments" not in projection.model_dump_json()
    denied(lambda: profile_service.get_profile(receiver, created.version.profile_id), 404)
    denied(lambda: profile_service.append_version(receiver, created.version.profile_id, append_input()), 404)
    admin = auth_service.get_principal(actor_factory(role="data_admin").cookie)
    denied(lambda: profile_service.get_profile(admin, created.version.profile_id), (403, 404))
    forged = receiver.model_copy(update={"user_id": owner.user_id, "roles": ("student", "data_admin")})
    denied(lambda: profile_service.get_profile(forged, created.version.profile_id), 401)


@pytest.mark.parametrize("stage", ["no_age", "no_consent", "bad_notice"])
def test_private_processing_requires_current_adult_and_core_notice(stage, actor_factory, auth_service,
        privacy_service, profile_service, pg_engine, create_input):
    who = auth_service.get_principal(actor_factory().cookie)
    if stage != "no_age":
        admission = privacy_service.get_admission(who)
        privacy_service.declare_age(who, AgeDeclarationInput(age_band="18_plus", confirmed=True,
            expected_revision=admission.revision, notice_id=admission.notice_id))
    if stage == "bad_notice":
        readmit(privacy_service, who)
        with Session(pg_engine) as session, session.begin():
            session.execute(update(PrivacyNoticeVersion).values(text_sha256="0" * 64))
    before = durable_state(pg_engine)
    denied(lambda: profile_service.create_profile(who, create_input, KEY), 503 if stage == "bad_notice" else 403)
    assert durable_state(pg_engine) == before


def test_withdraw_and_new_consent_do_not_revive_history_or_receipt_but_full_append_can_rebind(created,
        profile_service, principal, privacy_service, create_input):
    current = privacy_service.get_admission(principal)
    privacy_service.withdraw_core(principal, current.consent_id)
    denied(lambda: profile_service.get_profile(principal, created.version.profile_id), 403)
    denied(lambda: profile_service.create_profile(principal, create_input, KEY), 403)
    readmit(privacy_service, principal)
    denied(lambda: profile_service.get_version(principal, created.version.profile_id, created.version.version_id), (403, 409))
    denied(lambda: profile_service.create_profile(principal, create_input, KEY), (403, 409))
    assert profile_service.list_profiles(principal).items == ()
    appended = profile_service.append_version(principal, created.version.profile_id, append_input())
    assert appended.version.version == 2
    assert profile_service.get_profile(principal, created.version.profile_id) == appended.version
    assert tuple(r.profile_id for r in profile_service.list_profiles(principal).items) == (created.version.profile_id,)
    denied(lambda: profile_service.get_version(principal, created.version.profile_id, created.version.version_id), (403, 409))


@pytest.mark.parametrize("change,status", [("session", 401), ("account", 401), ("student", 403), ("registry", 404)])
def test_cached_principal_and_create_receipt_are_reauthorized(change, status, created, profile_service,
        principal, create_input, pg_engine, clock):
    with Session(pg_engine) as session, session.begin():
        if change == "session":
            session.get(AuthSession, principal.session_id).revoked_at = clock()
        elif change == "account":
            session.get(AuthUser, principal.user_id).status = "disabled"
        elif change == "student":
            session.get(AuthUserRole, (principal.user_id, "student")).revoked_at = clock()
        else:
            session.get(AuthOwnedResource, created.version.profile_id).status = "deleted"
    before = durable_state(pg_engine)
    denied(lambda: profile_service.get_profile(principal, created.version.profile_id), status)
    denied(lambda: profile_service.create_profile(principal, create_input, KEY), (status, 403))
    assert durable_state(pg_engine) == before


def test_model_copy_and_construct_cannot_bypass_confirmation_or_nested_score_validation(profile_service,
        principal, create_input, pg_engine):
    before = durable_state(pg_engine)
    forged = create_input.model_copy(update={"confirmed": 1})
    denied(lambda: profile_service.create_profile(principal, forged, KEY), 422)
    forged = CreateInput.model_construct(profile=create_input.profile, confirmed="true")
    denied(lambda: profile_service.create_profile(principal, forged, KEY), 422)
    bad = deepcopy(snapshot_payload())
    bad["assessments"]["math"]["predicted"].update(value=SENTINEL, scale="0")
    unsafe = ProfileSnapshot.model_construct(**bad)
    denied(lambda: profile_service.create_profile(principal,
        CreateInput.model_construct(profile=unsafe, confirmed=True), KEY), 422)
    assert durable_state(pg_engine) == before


def test_default_real_gate_and_changed_configuration_cannot_collect_profile(profile_factory, profile_service,
        principal, create_input, pg_engine):
    closed = profile_factory(policy=ProfilePolicy())
    assert closed.context(principal).can_create is False
    before = durable_state(pg_engine)
    denied(lambda: closed.create_profile(principal, create_input, KEY), 503)
    profile_service.policy = ProfilePolicy(enabled=True, real_profiles_ready=True)
    denied(lambda: profile_service.create_profile(principal, create_input, KEY), 503)
    assert durable_state(pg_engine) == before


def test_two_sessions_compete_for_same_expected_version_without_overwriting_history(created, profile_service,
        principal, pg_engine):
    entered, release, second_started = Event(), Event(), Event()
    first_thread, first_pid, second_pid = [], [], []
    def capture(connection, cursor, statement, parameters, context, executemany):
        if not first_thread:
            return
        if get_ident() == first_thread[0] and statement.lstrip().upper().startswith("INSERT INTO STUDENT_PROFILE_VERSIONS"):
            first_pid.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            entered.set()
            assert release.wait(20), "First append was not released"
        elif get_ident() != first_thread[0] and "FOR UPDATE" in statement.upper() and not second_pid:
            second_pid.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            second_started.set()
    def first():
        first_thread.append(get_ident())
        return profile_service.append_version(principal, created.version.profile_id, append_input(weekly_hours="1"))
    event.listen(pg_engine, "before_cursor_execute", capture)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(first), None
        try:
            assert entered.wait(15)
            b = pool.submit(profile_service.append_version, principal, created.version.profile_id, append_input(weekly_hours="2"))
            assert second_started.wait(10)
            require_blocked(pg_engine, second_pid, first_pid[0], b)
            release.set()
            assert a.result(timeout=30).version.version == 2
            denied(lambda: b.result(timeout=30), 409)
        finally:
            release.set()
            event.remove(pg_engine, "before_cursor_execute", capture)
    saved = rows(pg_engine, ProfileVersion)
    assert len(saved) == 2 and {r["version"] for r in saved} == {1, 2}
    assert profile_service.get_profile(principal, created.version.profile_id).profile.weekly_hours == "1"


def test_required_audit_failure_and_actual_deferred_commit_failure_leave_no_partial_profile(profile_service,
        principal, create_input, pg_engine):
    before = durable_state(pg_engine)
    for stage in ("audit", "commit"):
        with pg_engine.begin() as connection:
            connection.execute(text("CREATE FUNCTION t23_reject_commit() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'Synthetic forced failure' USING ERRCODE='23514'; END $$"))
            if stage == "audit":
                connection.execute(text("CREATE FUNCTION t23_reject_audit() RETURNS trigger LANGUAGE plpgsql AS $$ "
                    "BEGIN IF EXISTS(SELECT 1 FROM student_profile_versions) THEN RAISE EXCEPTION 'Synthetic audit failure' "
                    "USING ERRCODE='23514'; END IF; RETURN NEW; END $$"))
                connection.execute(text("CREATE TRIGGER t23_audit_failure BEFORE INSERT ON auth_audit_events "
                    "FOR EACH ROW EXECUTE FUNCTION t23_reject_audit()"))
            else:
                connection.execute(text("CREATE CONSTRAINT TRIGGER t23_commit_failure AFTER INSERT ON student_profile_versions "
                    "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION t23_reject_commit()"))
        try:
            denied(lambda: profile_service.create_profile(principal, create_input, KEY), 503)
            assert durable_state(pg_engine) == before
        finally:
            with pg_engine.begin() as connection:
                if stage == "audit":
                    connection.execute(text("DROP TRIGGER t23_audit_failure ON auth_audit_events"))
                    connection.execute(text("DROP FUNCTION t23_reject_audit()"))
                else:
                    connection.execute(text("DROP TRIGGER t23_commit_failure ON student_profile_versions"))
                connection.execute(text("DROP FUNCTION t23_reject_commit()"))
    retry = profile_service.create_profile(principal, create_input, KEY)
    assert retry.replayed is False and retry.version.version == 1


@pytest.mark.parametrize("winner_commits", [True, False])
def test_concurrent_same_key_creates_one_root_and_rollback_frees_receipt_claim(winner_commits,
        profile_service, principal, create_input, pg_engine):
    worker_pid, reached = [], Event()
    main_thread = get_ident()
    def observe(connection, cursor, statement, parameters, context, executemany):
        if get_ident() != main_thread and "FOR UPDATE" in statement.upper() and not worker_pid:
            worker_pid.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            reached.set()
    event.listen(pg_engine, "before_cursor_execute", observe)
    with Session(pg_engine) as winner:
        winner.begin()
        first = profile_service.create_profile(principal, create_input, KEY, session=winner)
        blocker_pid = winner.scalar(text("SELECT pg_backend_pid()"))
        with ThreadPoolExecutor(max_workers=1) as pool:
            contender = pool.submit(profile_service.create_profile, principal, create_input, KEY)
            try:
                assert reached.wait(15)
                require_blocked(pg_engine, worker_pid, blocker_pid, contender)
                winner.commit() if winner_commits else winner.rollback()
                second = contender.result(timeout=30)
                assert second.replayed is winner_commits
                if winner_commits:
                    assert second.version == first.version
                else:
                    assert second.version.profile_id != first.version.profile_id
            finally:
                winner.rollback()
                event.remove(pg_engine, "before_cursor_execute", observe)
    assert len(rows(pg_engine, ProfileRoot)) == len(rows(pg_engine, ProfileVersion)) == 1
    assert len(rows(pg_engine, IdempotencyRecord)) == len(rows(pg_engine, AuthOwnedResource)) == 1


def test_caller_transaction_is_same_session_and_domain_failure_aborts_all_work(created, profile_service,
        principal, pg_engine):
    before = durable_state(pg_engine)
    with Session(pg_engine) as session:
        session.begin()
        session.execute(update(AuthOwnedResource).where(AuthOwnedResource.id == created.version.profile_id).values(status="deleted"))
        denied(lambda: profile_service.append_version(principal, created.version.profile_id,
            append_input(), session=session), 404)
        session.commit()  # Catching a safe domain error must not retain preceding caller writes.
    assert durable_state(pg_engine) == before
    with Session(pg_engine) as session, session.begin():
        result = profile_service.append_version(principal, created.version.profile_id,
            append_input(weekly_hours="3"), session=session)
        assert result.version.version == 2 and session.in_transaction()
        session.rollback()
    assert durable_state(pg_engine) == before


def test_wrong_engine_and_mapper_binds_are_rejected_before_other_database_io(profile_service,
        principal, create_input, pg_engine):
    routed = create_engine(pg_engine.url, hide_parameters=True)
    attempts = []
    def no_connection(*args):
        attempts.append(True)
        raise AssertionError("A wrongly routed profile mapper must not connect")
    event.listen(routed, "do_connect", no_connection)
    before = durable_state(pg_engine)
    try:
        for mapper in (ProfileRoot, ProfileVersion, AuthUser, AuthSession, AuthUserRole, AuthOwnedResource,
                       PrivacyNoticeVersion, PrivacyAdmissionRecord, AuditEvent, IdempotencyRecord):
            with Session(pg_engine, binds={mapper: routed}) as session, session.begin():
                denied(lambda: profile_service.create_profile(principal, create_input, KEY, session=session), 503)
        with Session(routed) as session, session.begin():
            denied(lambda: profile_service.create_profile(principal, create_input, KEY, session=session), 503)
        with Session(pg_engine) as session:
            denied(lambda: profile_service.create_profile(principal, create_input, KEY, session=session), 503)
    finally:
        routed.dispose()
    assert attempts == [] and durable_state(pg_engine) == before
