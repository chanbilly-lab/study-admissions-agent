"""T19 real PostgreSQL, explicit DEMO-only publication and atomic revocation."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event, get_ident
from time import monotonic
from uuid import uuid4

from alembic import command
from pydantic import SecretStr
import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from services.api.app.admin.sources.models import CatalogSourceVersion
from services.api.app.admissions_catalog.models import AdmissionOffering, CatalogDataset
from services.api.app.audit.models import AuditEvent
from services.api.app.auth.models import AuthSession, AuthUserRole
from services.api.app.idempotency.models import IdempotencyRecord
from services.api.app.releases.models import (
    ReleasesBase, CatalogRelease, CatalogReleaseMember, CatalogReleaseState, ChangeEvent, OutboxEvent,
)
from services.api.app.releases.schemas import PublishMember, ReleasePolicy, WithdrawalRequest
from services.api.app.releases.service import ReleaseService
from services.api.app.releases.store import migrate_releases, migration_config
from services.api.app.reviews.schemas import CHECK_FIELDS, ReviewRequest, ReviewCheck, ConflictResolution
from services.api.app.storage.models import StorageObject


pytestmark = pytest.mark.postgres
SENTINEL = "DEMO_T19_PRIVATE_FAILURE_SENTINEL"
MODELS = (CatalogRelease, CatalogReleaseMember, CatalogReleaseState, ChangeEvent, OutboxEvent)


def denied(call, *codes):
    with pytest.raises(ValueError) as caught:
        call()
    assert caught.value.status_code in codes
    assert SENTINEL not in str(caught.value) + repr(caught.value)
    return caught.value


def rows(engine, model):
    with engine.connect() as connection:
        return connection.execute(model.__table__.select().order_by(*model.__table__.primary_key.columns)).mappings().all()


def snapshot(engine):
    return tuple(rows(engine, model) for model in MODELS)


def receipts(engine):
    return [row for row in rows(engine, IdempotencyRecord) if row["operation"] == "catalog.publish"]


def publish(case, request=None, *, key=None, actor=None, session=None):
    return case.releases.publish(actor or case.reviewer.principal, request or case.publish_request(),
        SecretStr(key or "DEMO_T19_" + uuid4().hex), session=session)


def withdrawal(release, **changes):
    values = dict(release_id=release.release_id, expected_state_revision=release.state_revision,
        reason_code="ADMIN_REQUEST")
    values.update(changes)
    return WithdrawalRequest(**values)


def approval(case, fact, *, revision=0):
    return case.reviews.decide(case.reviewer.principal, ReviewRequest(fact_id=fact.id, expected_fact_version=1,
        expected_case_revision=revision, action="approve", checks=tuple(ReviewCheck(field=field,
            status="not_applicable" if field in ("statistics_context", "date_context") else "accepted")
            for field in CHECK_FIELDS), conflict_resolutions=tuple(ConflictResolution(fact_id=identifier,
            reason_code="INCORRECT_VALUE") for identifier in fact.conflicting_ids), return_reason=None))


def wait_for_block(engine, started, pids, blocker, *, pending=None):
    # Multi-member T18 proofs are deliberately repeated around T49. Wait for the
    # real SQL event, while surfacing a worker's early safe domain failure rather
    # than incorrectly labelling every missing event as a slow query.
    arrival_deadline = monotonic() + 20
    while not started.wait(timeout=0.05):
        if pending is not None and pending.done():
            pending.result()
            pytest.fail("The worker completed without reaching the required SQL boundary")
        if monotonic() >= arrival_deadline:
            pytest.fail("The contender did not reach its SQL boundary within 20 seconds")
    deadline = monotonic() + 5
    while monotonic() < deadline:
        with engine.connect() as connection:
            locked = connection.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_stat_activity "
                "WHERE pid=:pid AND wait_event_type='Lock' AND :blocker=ANY(pg_blocking_pids(pid)))"),
                {"pid": pids[0], "blocker": blocker})
        if locked:
            return
    pytest.fail("The actual PostgreSQL lock wait was not observed")


def install_audit_barrier(engine):
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE demo_t19_audit_barrier(id integer PRIMARY KEY)"))
        connection.execute(text("INSERT INTO demo_t19_audit_barrier VALUES(1)"))
        connection.execute(text("CREATE FUNCTION demo_t19_wait_audit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN IF current_setting('t19.probe',true)='1' THEN "
            "PERFORM id FROM demo_t19_audit_barrier WHERE id=1 FOR UPDATE; END IF; RETURN NEW; END $$"))
        connection.execute(text("CREATE TRIGGER demo_t19_audit_wait BEFORE INSERT ON auth_audit_events "
            "FOR EACH ROW EXECUTE FUNCTION demo_t19_wait_audit()"))


def test_publish_exact_approved_snapshot_receipt_events_and_outbox_one_transaction(release_case_factory, pg_engine):
    case = release_case_factory()
    request = case.publish_request()
    read_count = case.storage.backend.read_count
    connection_ids = []
    def observe(connection, cursor, statement, parameters, context, many):
        connection_ids.append(id(connection.connection))
    event.listen(pg_engine, "before_cursor_execute", observe)
    try:
        result = publish(case, request)
    finally:
        event.remove(pg_engine, "before_cursor_execute", observe)
    assert len(set(connection_ids)) == 1
    assert result.kind == "test_fixture" and result.is_synthetic is True and result.state == "published"
    assert result.version == result.state_revision == 1 and result.replayed is False
    assert result.ruleset_version is None
    assert result.members[0].fact_id == case.candidates[0].id
    assert result.members[0].decision_id == case.decisions[0].decision_id
    assert result.members[0].public_evidence is False
    assert case.releases.get_release(case.reviewer.principal, result.release_id).release_id == result.release_id
    assert case.storage.backend.read_count == read_count
    assert [len(items) for items in snapshot(pg_engine)] == [1, 1, 1, 1, 1]
    assert len(receipts(pg_engine)) == 1 and receipts(pg_engine)[0]["state"] == "completed"
    assert any(row["action"] == "catalog.publish" and row["outcome"] == "succeeded"
        for row in rows(pg_engine, AuditEvent))


def test_key_replay_new_key_and_expired_receipt_keep_single_natural_content(release_case_factory, pg_engine, clock):
    case = release_case_factory(ttl_seconds=1)
    request = case.publish_request()
    first = publish(case, request, key="DEMO_STABLE_KEY")
    same = publish(case, request, key="DEMO_STABLE_KEY")
    other = publish(case, request, key="DEMO_OTHER_KEY")
    clock.advance(1)
    expired = publish(case, request, key="DEMO_STABLE_KEY")
    assert {item.release_id for item in (first, same, other, expired)} == {first.release_id}
    assert same.replayed and other.replayed and expired.replayed
    assert [len(items) for items in snapshot(pg_engine)] == [1, 1, 1, 1, 1]
    assert len(receipts(pg_engine)) == 2
    assert SENTINEL not in repr(receipts(pg_engine))


def test_same_key_changed_request_is_conflict_without_second_business(release_case_factory, pg_engine):
    case = release_case_factory()
    request = case.publish_request()
    publish(case, request, key="DEMO_EXACT_KEY")
    before = snapshot(pg_engine)
    altered = request.model_copy(update={"valid_until": request.valid_until + timedelta(seconds=1)})
    denied(lambda: publish(case, altered, key="DEMO_EXACT_KEY"), 409)
    assert snapshot(pg_engine) == before and len(receipts(pg_engine)) == 1


def test_default_policy_and_formal_channel_never_accept_demo(release_case_factory, pg_engine):
    case = release_case_factory()
    formal = case.publish_request(kind="formal")
    denied(lambda: publish(case, formal), 422, 503)
    for policy in (ReleasePolicy(), ReleasePolicy(enabled=True),
                   ReleasePolicy(enabled=True, real_releases_ready=True)):
        service = ReleaseService(case.reviews, case.release_idempotency, case.releases.store, policy)
        denied(lambda: service.publish(case.reviewer.principal, case.publish_request(), SecretStr("DEMO_CLOSED")), 503)
    assert all(not items for items in snapshot(pg_engine)) and receipts(pg_engine) == []


def test_unreviewed_and_wrong_current_decision_cannot_publish(release_case_factory, pg_engine):
    case = release_case_factory(approve=False)
    member = PublishMember(fact_id=case.candidates[0].id, expected_case_revision=1,
        expected_decision_id=uuid4(), public_evidence=False)
    denied(lambda: publish(case, case.publish_request(members=(member,))), 404, 409)
    decision = approval(case, case.candidates[0])
    member = member.model_copy(update={"expected_decision_id": decision.decision_id, "expected_case_revision": 2})
    denied(lambda: publish(case, case.publish_request(members=(member,))), 409)
    assert all(not items for items in snapshot(pg_engine))


def test_manual_permission_is_not_publication_permission(release_case_factory, pg_engine):
    case = release_case_factory(publication_permission="denied")
    assert case.source.manual_import_permission == "granted" and case.source.publication_permission == "denied"
    denied(lambda: publish(case), 403, 409)
    assert all(not items for items in snapshot(pg_engine)) and receipts(pg_engine) == []


def test_exact_dataset_year_and_dataset_revision_cannot_be_client_overridden(release_case_factory, pg_engine):
    case = release_case_factory()
    request = case.publish_request()
    for changes in ({"dataset_id": uuid4()}, {"entry_year": 2027},
                    {"expected_dataset_revision": request.expected_dataset_revision + 1}):
        denied(lambda changes=changes: publish(case, request.model_copy(update=changes)), 404, 409)
    with Session(pg_engine) as session, session.begin():
        session.get(AdmissionOffering, case.candidates[0].offering_id).entry_year = 2027
    denied(lambda: publish(case, request), 409, 503)
    assert all(not items for items in snapshot(pg_engine))


def test_resolved_historical_conflict_can_publish_but_new_conflict_invalidates_approval(
        release_case_factory, candidate_factory, pg_engine):
    raw = [candidate_factory(value_text=value) for value in ("600", "601")]
    case = release_case_factory(rows=raw, approve=False)
    fact = case.facts.get_fact(case.reviewer.principal, case.candidates[0].id)
    assert len(fact.conflicting_ids) == 1
    decision = approval(case, fact)
    member = PublishMember(fact_id=fact.id, expected_case_revision=decision.case_revision,
        expected_decision_id=decision.decision_id, public_evidence=True)
    first = publish(case, case.publish_request(members=(member,)))
    assert first.members[0].fact_id == fact.id
    # A new classification changes its logical context rather than supplying a
    # new public fact. A third actual source row is built in the companion case.
    extra = release_case_factory(rows=[candidate_factory(value_text="602")], approve=False)
    denied(lambda: publish(case, case.publish_request(members=(member,),
        valid_until=first.valid_until + timedelta(seconds=1))), 409)
    assert len(rows(pg_engine, CatalogRelease)) == 1 and extra.candidates[0].id != fact.id


def test_current_role_session_and_mfa_rechecked_before_receipt_replay(release_case_factory, pg_engine, clock):
    case = release_case_factory()
    request = case.publish_request()
    publish(case, request, key="DEMO_AUTH_REPLAY")
    before = snapshot(pg_engine)
    with Session(pg_engine) as session, session.begin():
        session.get(StorageObject, case.file.id).status = "deleted"
    denied(lambda: publish(case, request, key="DEMO_AUTH_REPLAY"), 404, 409)
    with Session(pg_engine) as session, session.begin():
        session.get(StorageObject, case.file.id).status = "quarantined"
    with Session(pg_engine) as session, session.begin():
        session.get(AuthUserRole, (case.reviewer.actor.user_id, "data_admin")).revoked_at = clock()
    denied(lambda: publish(case, request, key="DEMO_AUTH_REPLAY"), 403)
    with Session(pg_engine) as session, session.begin():
        session.get(AuthUserRole, (case.reviewer.actor.user_id, "data_admin")).revoked_at = None
        session.get(AuthSession, case.reviewer.actor.session_id).revoked_at = clock()
    denied(lambda: publish(case, request, key="DEMO_AUTH_REPLAY"), 401)
    with Session(pg_engine) as session, session.begin():
        session.get(AuthSession, case.reviewer.actor.session_id).revoked_at = None
    clock.advance(61)
    denied(lambda: publish(case, request, key="DEMO_AUTH_REPLAY"), 403)
    assert snapshot(pg_engine) == before


def test_withdraw_invalid_old_source_and_no_replay_resurrection(release_case_factory, pg_engine):
    case = release_case_factory()
    request = case.publish_request()
    published = publish(case, request, key="DEMO_WITHDRAW_KEY")
    with Session(pg_engine) as session, session.begin():
        session.get(CatalogSourceVersion, case.source.id).publication_permission = "denied"
    withdrawn = case.releases.withdraw(case.reviewer.principal, withdrawal(published, reason_code="RIGHTS_REVOKED"))
    assert withdrawn.state == "withdrawn" and withdrawn.state_revision == 2
    assert len(rows(pg_engine, CatalogRelease)) == 1 and len(rows(pg_engine, ChangeEvent)) == 2
    assert len(rows(pg_engine, OutboxEvent)) == 2
    denied(lambda: case.releases.withdraw(case.reviewer.principal, withdrawal(published)), 409)
    denied(lambda: publish(case, request, key="DEMO_WITHDRAW_KEY"), 403, 409)
    denied(lambda: publish(case, request, key="DEMO_NEW_AFTER_WITHDRAW"), 403, 409)
    # Current proof can become valid again, but the old release must stay revoked.
    with Session(pg_engine) as session, session.begin():
        session.get(CatalogSourceVersion, case.source.id).publication_permission = "granted"
    denied(lambda: publish(case, request, key="DEMO_WITHDRAW_KEY"), 409)
    denied(lambda: publish(case, request, key="DEMO_NEW_AFTER_WITHDRAW"), 409)
    assert case.releases.get_release(case.reviewer.principal, published.release_id).state == "withdrawn"


def test_replacement_is_explicit_cas_and_keeps_old_immutable_history(release_case_factory, pg_engine):
    case = release_case_factory()
    request = case.publish_request()
    first = publish(case, request)
    immutable = rows(pg_engine, CatalogRelease), rows(pg_engine, CatalogReleaseMember)
    different = case.publish_request(valid_from=request.valid_from,
        valid_until=request.valid_until + timedelta(seconds=1))
    denied(lambda: publish(case, different), 409)
    stale = different.model_copy(update={"replaces_release_id": first.release_id, "expected_replaced_state_revision": 2})
    denied(lambda: publish(case, stale), 409)
    valid = stale.model_copy(update={"expected_replaced_state_revision": 1})
    before = snapshot(pg_engine), receipts(pg_engine)
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION demo_t19_replace_fail() RETURNS trigger LANGUAGE plpgsql AS $$ "
            f"BEGIN RAISE EXCEPTION '{SENTINEL}' USING ERRCODE='23514'; END $$"))
        connection.execute(text("CREATE TRIGGER demo_t19_replace_fail BEFORE INSERT ON catalog_outbox "
            "FOR EACH ROW EXECUTE FUNCTION demo_t19_replace_fail()"))
    denied(lambda: publish(case, valid, key="DEMO_REPLACE_RETRY"), 503)
    assert (snapshot(pg_engine), receipts(pg_engine)) == before
    assert case.releases.get_release(case.reviewer.principal, first.release_id).state == "published"
    with pg_engine.begin() as connection:
        connection.execute(text("DROP TRIGGER demo_t19_replace_fail ON catalog_outbox"))
    replacement = publish(case, valid, key="DEMO_REPLACE_RETRY")
    assert replacement.state == "published" and replacement.replaces_release_id == first.release_id
    old = case.releases.get_release(case.reviewer.principal, first.release_id)
    assert old.state == "replaced" and old.replaced_by_release_id == replacement.release_id and old.state_revision == 2
    assert immutable[0][0] in rows(pg_engine, CatalogRelease) and immutable[1][0] in rows(pg_engine, CatalogReleaseMember)
    assert [len(items) for items in snapshot(pg_engine)] == [2, 2, 2, 3, 3]
    denied(lambda: publish(case, request), 409)


@pytest.mark.parametrize("failure", ["audit", "outbox", "commit"])
def test_required_audit_outbox_and_deferred_commit_failure_leave_no_partial_release(
        release_case_factory, pg_engine, failure):
    case = release_case_factory()
    request = case.publish_request()
    fired, business_connections = [], set()
    def fail_audit(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().startswith("INSERT INTO catalog_releases"):
            business_connections.add(id(connection))
        if statement.lstrip().startswith("INSERT INTO auth_audit_events") and id(connection) in business_connections:
            fired.append(True)
            raise RuntimeError(SENTINEL)
    if failure == "audit":
        event.listen(pg_engine, "before_cursor_execute", fail_audit)
    else:
        table = "catalog_outbox" if failure == "outbox" else "catalog_releases"
        with pg_engine.begin() as connection:
            connection.execute(text("CREATE FUNCTION demo_t19_required_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
                f"BEGIN RAISE EXCEPTION '{SENTINEL}' USING ERRCODE='23514'; END $$"))
            ddl = (f"CREATE TRIGGER demo_t19_fail BEFORE INSERT ON {table} FOR EACH ROW "
                   "EXECUTE FUNCTION demo_t19_required_failure()" if failure == "outbox" else
                   f"CREATE CONSTRAINT TRIGGER demo_t19_fail AFTER INSERT ON {table} "
                   "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION demo_t19_required_failure()")
            connection.execute(text(ddl))
    try:
        denied(lambda: publish(case, request, key="DEMO_ATOMIC_RETRY"), 503)
    finally:
        if failure == "audit":
            event.remove(pg_engine, "before_cursor_execute", fail_audit)
        else:
            with pg_engine.begin() as connection:
                connection.execute(text(f"DROP TRIGGER demo_t19_fail ON {table}"))
    if failure == "audit":
        assert fired, "The required audit failure was never reached"
    assert all(not items for items in snapshot(pg_engine)) and receipts(pg_engine) == []
    assert publish(case, request, key="DEMO_ATOMIC_RETRY").state == "published"


def test_caller_transaction_abort_and_all_new_mapper_binds_reject_without_foreign_io(
        release_case_factory, pg_engine):
    case = release_case_factory()
    request = case.publish_request()
    with Session(pg_engine) as session:
        session.begin()
        session.get(CatalogDataset, case.source.dataset_id).revision += 1
        denied(lambda: publish(case, request, session=session), 409)
        assert not session.in_transaction()
        session.commit()
    assert all(not items for items in snapshot(pg_engine))
    with Session(pg_engine) as session:
        assert session.get(CatalogDataset, case.source.dataset_id).revision == request.expected_dataset_revision
    foreign = create_engine(pg_engine.url, hide_parameters=True)
    def no_connect(*args):
        pytest.fail("A rejected mapper bind performed foreign I/O")
    event.listen(foreign, "connect", no_connect)
    try:
        for model in MODELS:
            with Session(pg_engine, binds={model: foreign}) as session:
                session.begin()
                denied(lambda: publish(case, request, session=session), 503)
                assert not session.in_transaction()
        with Session(foreign) as session:
            session.begin()
            denied(lambda: publish(case, request, session=session), 503)
            assert session.in_transaction()
    finally:
        foreign.dispose()
    assert receipts(pg_engine) == []


@pytest.mark.parametrize("expiry", ["first_file", "first_source", "mfa"])
def test_real_audit_wait_crosses_first_member_or_authority_deadline_and_rolls_back(
        release_case_factory, candidate_factory, pg_engine, clock, monkeypatch, expiry):
    case = release_case_factory(rows=[candidate_factory(field_key="first_minimum_score")], ttl_seconds=120)
    other = release_case_factory(rows=[candidate_factory(field_key="second_minimum_score")])
    # Distinct sources and files matter: checking only the final member must not
    # accidentally catch the same expired file used by both members.
    first, last = sorted((case, other), key=lambda item: str(item.candidates[0].id))
    members = tuple(PublishMember(fact_id=item.decisions[0].fact_id,
        expected_case_revision=item.decisions[0].case_revision,
        expected_decision_id=item.decisions[0].decision_id, public_evidence=False) for item in (first, last))
    request = case.publish_request(members=members)
    if expiry == "first_file":
        with Session(pg_engine) as session, session.begin():
            session.get(StorageObject, first.file.id).expires_at = clock() + timedelta(seconds=1)
    elif expiry == "first_source":
        # Explicit synthetic setup extends still-current fixture metadata before
        # any clock advancement; it never revives an expired original document.
        with Session(pg_engine) as session, session.begin():
            for item in (first, last):
                session.get(StorageObject, item.file.id).expires_at = clock() + timedelta(days=3)
            later_source = session.get(CatalogSourceVersion, last.source.id)
            later_source.recheck_days = 2
            later_source.recheck_due_at = later_source.created_at + timedelta(days=2)
        clock.advance(int((first.source.recheck_due_at - clock()).total_seconds()) - 1)
        with Session(pg_engine) as session, session.begin():
            stored_session = session.get(AuthSession, case.reviewer.actor.session_id)
            stored_session.created_at = clock()
            stored_session.expires_at = clock() + timedelta(hours=1)
            stored_session.assurance_auth_time = clock()
        case.reviewer.principal = case.reviewer.service.get_principal(case.reviewer.actor.cookie)
        request = case.publish_request(members=members)
    install_audit_barrier(pg_engine)
    started, pids = Event(), []
    # The post-idempotency verifier is the third complete verification. Arm the
    # real required audit INSERT in its LAST member, after the first member's
    # exact proof has already been collected. Earlier audit waits would merely
    # cause that first proof to fail on its next read, masking aggregation bugs.
    verify_calls = []
    original_verify = case.releases._verify_release
    original_member = case.releases._member_proof
    def verify(*args, **kwargs):
        verify_calls.append(True)
        args[0].connection().info["t19_final_verify"] = len(verify_calls) == 3
        return original_verify(*args, **kwargs)
    def member(*args, **kwargs):
        if args[0].connection().info.get("t19_final_verify") and args[2].fact_id == last.candidates[0].id:
            args[0].execute(text("SET LOCAL t19.probe='1'"))
        return original_member(*args, **kwargs)
    monkeypatch.setattr(case.releases, "_verify_release", verify)
    monkeypatch.setattr(case.releases, "_member_proof", member)
    def mark(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().startswith("INSERT INTO auth_audit_events") and not started.is_set():
            if connection.scalar(text("SELECT current_setting('t19.probe',true)")) == "1":
                pids.append(connection.scalar(text("SELECT pg_backend_pid()")))
                started.set()
    event.listen(pg_engine, "before_cursor_execute", mark)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pg_engine.begin() as blocker:
                blocker_id = blocker.scalar(text("SELECT pg_backend_pid()"))
                blocker.execute(text("SELECT id FROM demo_t19_audit_barrier WHERE id=1 FOR UPDATE"))
                pending = pool.submit(publish, case, request)
                wait_for_block(pg_engine, started, pids, blocker_id, pending=pending)
                clock.advance(61 if expiry == "mfa" else 1)
            denied(lambda: pending.result(timeout=30), 401, 403, 404, 409)
    finally:
        event.remove(pg_engine, "before_cursor_execute", mark)
    assert len(verify_calls) == 3
    assert all(not items for items in snapshot(pg_engine)) and receipts(pg_engine) == []


@pytest.mark.parametrize("same_content", [True, False])
def test_two_distinct_accounts_really_wait_and_natural_dedup_or_cas_is_atomic(
        release_case_factory, administrator_factory, pg_engine, same_content):
    case = release_case_factory()
    second = administrator_factory()
    assert second.actor.user_id != case.reviewer.actor.user_id
    request = case.publish_request()
    second_request = request if same_content else request.model_copy(
        update={"valid_until": request.valid_until + timedelta(seconds=1)})
    install_audit_barrier(pg_engine)
    first_started, second_started = Event(), Event()
    first_pid, second_pid, worker_ids = [], [], []
    def observe(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().startswith("INSERT INTO catalog_releases") and not first_started.is_set():
            connection.execute(text("SET LOCAL t19.probe='1'"))
        elif statement.lstrip().startswith("INSERT INTO auth_audit_events") and not first_started.is_set():
            if connection.scalar(text("SELECT current_setting('t19.probe',true)")) == "1":
                first_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
                first_started.set()
        if (worker_ids and get_ident() == worker_ids[0] and statement.lstrip().startswith("SELECT")
            and "FOR UPDATE" in statement.upper() and any(name in statement for name in
                ("catalog_datasets", "catalog_offerings", "catalog_release_states")) and not second_started.is_set()):
            second_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
            second_started.set()
    def contender():
        worker_ids.append(get_ident())
        return publish(case, second_request, actor=second.principal)
    event.listen(pg_engine, "before_cursor_execute", observe)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            with pg_engine.begin() as blocker:
                blocker_id = blocker.scalar(text("SELECT pg_backend_pid()"))
                blocker.execute(text("SELECT id FROM demo_t19_audit_barrier WHERE id=1 FOR UPDATE"))
                first = pool.submit(publish, case, request)
                wait_for_block(pg_engine, first_started, first_pid, blocker_id)
                pending = pool.submit(contender)
                wait_for_block(pg_engine, second_started, second_pid, first_pid[0])
            first_result = first.result(timeout=10)
            if same_content:
                second_result = pending.result(timeout=10)
                assert first_result.release_id == second_result.release_id and second_result.replayed
            else:
                denied(lambda: pending.result(timeout=10), 409)
    finally:
        event.remove(pg_engine, "before_cursor_execute", observe)
    assert [len(items) for items in snapshot(pg_engine)] == [1, 1, 1, 1, 1]
    assert len(receipts(pg_engine)) == (2 if same_content else 1)


def test_database_history_immutable_and_partial_published_unique_guard(release_case_factory, pg_engine, releases_store):
    case = release_case_factory()
    publish(case)
    before = snapshot(pg_engine)
    for table in ("catalog_releases", "catalog_release_members", "catalog_change_events"):
        for statement in (f"UPDATE {table} SET id=id", f"DELETE FROM {table}"):
            with pytest.raises(DBAPIError) as blocked:
                with pg_engine.begin() as connection:
                    connection.execute(text(statement))
            assert blocked.value.orig.sqlstate == "23514"
    assert snapshot(pg_engine) == before
    duplicate_root, duplicate_state = dict(before[0][0]), dict(before[2][0])
    duplicate_root.update(id=uuid4(), content_sha256="b" * 64)
    duplicate_state.update(release_id=duplicate_root["id"])
    with pytest.raises(DBAPIError) as blocked:
        with pg_engine.begin() as connection:
            connection.execute(CatalogRelease.__table__.insert().values(**duplicate_root))
            connection.execute(CatalogReleaseState.__table__.insert().values(**duplicate_state))
    assert blocked.value.orig.sqlstate == "23505"
    assert snapshot(pg_engine) == before
    with pg_engine.begin() as connection:
        triggers = set(connection.execute(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal AND tgenabled='O' "
            "AND tgrelid IN(to_regclass('catalog_releases'),to_regclass('catalog_release_members'),"
            "to_regclass('catalog_change_events'))")).scalars())
        assert triggers == {"releases_root_immutable", "releases_members_immutable", "releases_events_immutable"}
        indexes = connection.execute(text("SELECT indexdef FROM pg_indexes WHERE tablename='catalog_release_states' "
            "AND schemaname=current_schema()")).scalars().all()
        assert any("UNIQUE" in definition and "WHERE" in definition and "published" in definition for definition in indexes)
        connection.execute(text("ALTER TABLE catalog_releases DISABLE TRIGGER releases_root_immutable"))
    denied(releases_store.assert_schema_ready, 503)
    with pg_engine.begin() as connection:
        connection.execute(text("ALTER TABLE catalog_releases ENABLE TRIGGER releases_root_immutable"))


def test_independent_migration_repeat_and_downgrade_preserve_prior_domains(
        release_case_factory, pg_engine, releases_store, monkeypatch, tmp_path):
    from services.api.app.migrations import migrate as migrate_m0
    from services.api.app.seed import seed
    case = release_case_factory()
    publish(case)
    monkeypatch.chdir(tmp_path)
    migrate_m0(pg_engine)
    seed(pg_engine)
    own_tables = {model.__tablename__ for model in MODELS} | {"releases_alembic_version"}
    def preserved():
        with pg_engine.connect() as connection:
            return {name: connection.execute(text('SELECT * FROM "' + name + '" ORDER BY 1')).all()
                for name in inspect(connection).get_table_names() if name not in own_tables}
    before = preserved()
    assert len(ReleasesBase.metadata.tables) == 5
    migrate_releases(pg_engine)
    migrate_releases(pg_engine)
    assert preserved() == before
    with pg_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert not own_tables - {"releases_alembic_version"} & set(inspect(pg_engine).get_table_names())
    denied(releases_store.assert_schema_ready, 503)
    assert preserved() == before
    migrate_releases(pg_engine)
    releases_store.assert_schema_ready()
    assert preserved() == before and all(not items for items in snapshot(pg_engine))
