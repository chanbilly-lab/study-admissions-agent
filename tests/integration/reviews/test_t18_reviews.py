"""Independent T18 synthetic human-account, current-proof and real PG boundaries."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event, get_ident
from time import monotonic
from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from services.api.app.admin.sources.models import CatalogSourceVersion
from services.api.app.admissions_catalog.models import AdmissionOffering, CatalogDataset
from services.api.app.audit.models import AuditEvent
from services.api.app.auth.models import AuthSession, AuthUserRole
from services.api.app.evidence.models import EvidenceSnippet
from services.api.app.facts.models import FactCandidate, FactConflict
from services.api.app.reviews.models import ReviewsBase, ReviewCase, ReviewDecision, ReviewConflictResolution
from services.api.app.reviews.schemas import CHECK_FIELDS, ReviewRequest, ReviewCheck, ConflictResolution, ReviewPolicy
from services.api.app.reviews.service import ReviewService
from services.api.app.reviews.store import migrate_reviews, migration_config
from services.api.app.storage.models import StorageObject


pytestmark = pytest.mark.postgres
SENTINEL = "DEMO_T18_PRIVATE_FAILURE_SENTINEL"


def denied(call, *codes):
    with pytest.raises(ValueError) as caught:
        call()
    assert caught.value.status_code in codes
    assert SENTINEL not in str(caught.value) + repr(caught.value)
    return caught.value


def rows(engine, model):
    with engine.connect() as connection:
        return connection.execute(model.__table__.select().order_by(*model.__table__.primary_key.columns)).mappings().all()


def request(candidate, *, revision=0, action="approve", conflicts=None, **changes):
    fields = dict(fact_id=candidate.id, expected_fact_version=1, expected_case_revision=revision,
        action=action, checks=tuple(ReviewCheck(field=field,
            status="not_applicable" if field in ("statistics_context", "date_context") else "accepted")
            for field in CHECK_FIELDS), conflict_resolutions=tuple(ConflictResolution(fact_id=identifier,
            reason_code="INCORRECT_VALUE") for identifier in (candidate.conflicting_ids if conflicts is None else conflicts)),
        return_reason="INVALID_VALUE" if action == "return" else None)
    if action == "return":
        fields["conflict_resolutions"] = ()
    fields.update(changes)
    return ReviewRequest(**fields)


def decide(case, candidate=None, **changes):
    return case.reviews.decide(case.reviewer.principal, request(candidate or case.candidates[0], **changes))


def verify(case, session, decision, **changes):
    fields = dict(expected_case_revision=decision.case_revision, expected_decision_id=decision.decision_id)
    fields.update(changes)
    return case.reviews.approval_in_transaction(session, case.reviewer.principal, decision.fact_id, **fields)


def wait_for_block(engine, started, pids, blocker):
    assert started.wait(timeout=5), "The contender did not reach its SQL boundary"
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
        connection.execute(text("CREATE TABLE demo_t18_audit_barrier(id integer PRIMARY KEY)"))
        connection.execute(text("INSERT INTO demo_t18_audit_barrier VALUES(1)"))
        connection.execute(text("CREATE FUNCTION demo_t18_wait_audit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN IF current_setting('t18.probe',true)='1' THEN "
            "PERFORM id FROM demo_t18_audit_barrier WHERE id=1 FOR UPDATE; END IF; RETURN NEW; END $$"))
        connection.execute(text("CREATE TRIGGER demo_t18_audit_wait BEFORE INSERT ON auth_audit_events "
            "FOR EACH ROW EXECUTE FUNCTION demo_t18_wait_audit()"))


def test_approve_exact_original_row_returns_only_current_internal_decision(review_case_factory, pg_engine):
    case = review_case_factory()
    candidate = case.candidates[0]
    before = rows(pg_engine, FactCandidate), rows(pg_engine, FactConflict)
    read_count = case.storage.backend.read_count
    empty = case.reviews.get_case(case.reviewer.principal, candidate.id)
    assert empty.case_revision == 0 and empty.current_approved is False
    decision = decide(case)
    assert decision.action == "approve" and decision.current_approved and decision.case_revision == 1
    assert decision.reviewer_user_id == case.reviewer.actor.user_id != case.admin.actor.user_id
    assert decision.fact_id == candidate.id and decision.is_synthetic is True
    current = case.reviews.get_case(case.reviewer.principal, candidate.id)
    assert current.chosen_fact_id == candidate.id and current.current_decision_id == decision.decision_id
    assert current.current_approved is True and current.case_revision == 1
    connections = []
    def observe(connection, cursor, statement, parameters, context, many):
        connections.append(id(connection.connection))
    event.listen(pg_engine, "before_cursor_execute", observe)
    try:
        with Session(pg_engine) as session, session.begin():
            assert verify(case, session, decision) == decision
    finally:
        event.remove(pg_engine, "before_cursor_execute", observe)
    assert len(set(connections)) == 1
    assert case.storage.backend.read_count == read_count
    assert before == (rows(pg_engine, FactCandidate), rows(pg_engine, FactConflict))
    assert candidate.hard_rule is False and candidate.publication_eligible is False
    assert any(item["action"] == "catalog.review" and item["outcome"] == "succeeded"
        and item["actor_user_id"] == case.reviewer.actor.user_id for item in rows(pg_engine, AuditEvent))


def test_return_clears_current_approval_and_preserves_decision_history(review_case_factory, pg_engine):
    case = review_case_factory()
    approved = decide(case)
    returned = decide(case, revision=1, action="return")
    assert returned.case_revision == 2 and returned.current_approved is False and returned.return_reason == "INVALID_VALUE"
    current = case.reviews.get_case(case.reviewer.principal, approved.fact_id)
    assert current.current_approved is False and current.chosen_fact_id is None
    history = rows(pg_engine, ReviewDecision)
    assert len(history) == 2 and {item["action"] for item in history} == {"approve", "return"}
    with Session(pg_engine) as session, session.begin():
        denied(lambda: verify(case, session, approved), 409)
    denied(lambda: decide(case, revision=1), 409)


def test_current_logical_case_requires_every_conflict_and_has_only_one_winner(review_case_factory,
        candidate_factory, pg_engine):
    case = review_case_factory(rows=[candidate_factory(value_text=value) for value in ("600", "601", "602")])
    first = case.facts.get_fact(case.reviewer.principal, case.candidates[0].id)
    assert len(first.conflicting_ids) == 2
    denied(lambda: decide(case, first, conflicts=()), 409)
    denied(lambda: decide(case, first, conflicts=first.conflicting_ids[:1]), 409)
    denied(lambda: decide(case, first, conflicts=(*first.conflicting_ids, uuid4())), 409)
    chosen = decide(case, first)
    assert len(rows(pg_engine, ReviewConflictResolution)) == 2
    second = case.facts.get_fact(case.reviewer.principal, case.candidates[1].id)
    replaced = decide(case, second, revision=chosen.case_revision)
    assert replaced.case_id == chosen.case_id and replaced.case_revision == 2
    for candidate in case.candidates:
        current = case.reviews.get_case(case.reviewer.principal, candidate.id)
        assert current.chosen_fact_id == second.id and current.current_approved is True
    with Session(pg_engine) as session, session.begin():
        denied(lambda: verify(case, session, chosen), 409)
    assert len(rows(pg_engine, ReviewCase)) == 1 and len(rows(pg_engine, FactConflict)) == 3


def test_new_conflict_permanently_invalidates_old_approval_until_explicit_new_review(review_case_factory,
        classification_factory, pg_engine):
    case = review_case_factory()
    approved = decide(case)
    another = case.facts.create_fact(case.admin.principal, case.fact_request(
        classification_factory(claim_kind="typical_offer"), evidence_id=case.review_snippets[0].id))
    assert another.conflicting_ids == ()
    with Session(pg_engine) as session, session.begin():
        assert verify(case, session, approved).current_approved is True
    competing = review_case_factory(rows=[dict(case.raw_rows[0], value_text="601.00")])
    assert competing.admin.actor.user_id != case.admin.actor.user_id
    assert competing.source.source_id != case.source.source_id
    assert competing.imported.id != case.imported.id
    current = case.reviews.get_case(case.reviewer.principal, approved.fact_id)
    assert current.current_approved is False and current.case_revision == 1
    with Session(pg_engine) as session, session.begin():
        denied(lambda: verify(case, session, approved), 409)
    updated = case.facts.get_fact(case.reviewer.principal, approved.fact_id)
    assert updated.conflicting_ids == (competing.candidates[0].id,)
    denied(lambda: decide(case, case.candidates[0], revision=1), 409)
    fresh = decide(case, updated, revision=1)
    assert fresh.current_approved is True and fresh.case_revision == 2
    assert len(rows(pg_engine, ReviewDecision)) == 2 and len(rows(pg_engine, FactConflict)) == 1


@pytest.mark.parametrize("kind", ["missing", "value_only"])
def test_unlocated_or_incomplete_literal_evidence_cannot_be_approved(review_case_factory, pg_engine, kind):
    case = review_case_factory(with_evidence=kind != "missing", value_only=kind == "value_only")
    denied(lambda: decide(case), 422)
    assert rows(pg_engine, ReviewDecision) == []
    returned = decide(case, action="return")
    assert returned.current_approved is False


def test_unknown_scope_and_draft_are_not_promoted_by_human_check_flags(review_case_factory,
        candidate_factory, classification_factory, pg_engine, catalog_tree):
    with Session(pg_engine) as session, session.begin():
        session.get(AdmissionOffering, catalog_tree.offering.id).province_key = "unknown"
    case = review_case_factory()
    denied(lambda: decide(case), 422)
    draft = review_case_factory(rows=[candidate_factory(value_text=None, missing_reason="not_provided")],
        with_evidence=False, classification=classification_factory(unit_code="unknown"))
    denied(lambda: decide(draft), 422)
    assert rows(pg_engine, ReviewDecision) == []


def test_forged_checks_copy_and_server_fields_are_revalidated(review_case_factory, pg_engine):
    case = review_case_factory()
    valid = request(case.candidates[0])
    for invalid in (valid.model_copy(update={"expected_fact_version": True}),
                    valid.model_copy(update={"checks": ()}),
                    {**valid.model_dump(), "reviewer_user_id": case.reviewer.actor.user_id}):
        denied(lambda invalid=invalid: case.reviews.decide(case.reviewer.principal, invalid), 422)
    assert rows(pg_engine, ReviewDecision) == []
    closed = ReviewService(case.facts, case.reviews.store, ReviewPolicy())
    denied(lambda: closed.decide(case.reviewer.principal, valid), 503)


def test_creator_cannot_review_own_import_even_with_current_strong_role(review_case_factory, pg_engine):
    case = review_case_factory()
    denied(lambda: case.reviews.decide(case.admin.principal, request(case.candidates[0])), 403)
    assert rows(pg_engine, ReviewDecision) == []


@pytest.mark.parametrize("removed", ["role", "mfa", "session"])
def test_live_authority_is_rechecked_before_replaying_a_decision(review_case_factory, pg_engine, clock, removed):
    case = review_case_factory()
    approved = decide(case)
    with Session(pg_engine) as session, session.begin():
        if removed == "role":
            session.get(AuthUserRole, (case.reviewer.actor.user_id, "data_admin")).revoked_at = clock()
        elif removed == "mfa":
            session.get(AuthSession, case.reviewer.actor.session_id).assurance_auth_time = clock() - timedelta(seconds=61)
        else:
            session.get(AuthSession, case.reviewer.actor.session_id).revoked_at = clock()
    denied(lambda: case.reviews.get_case(case.reviewer.principal, approved.fact_id), 401, 403)
    with Session(pg_engine) as session, session.begin():
        denied(lambda: verify(case, session, approved), 401, 403)
    assert len(rows(pg_engine, ReviewDecision)) == 1


def test_stale_revision_or_current_source_permission_cannot_authorize(review_case_factory, pg_engine, clock):
    case = review_case_factory()
    approved = decide(case)
    denied(lambda: decide(case), 409)
    clock.advance(1)
    with Session(pg_engine) as session, session.begin():
        file = session.get(StorageObject, case.file.id)
        original_expiry = file.expires_at
        file.expires_at = clock()
    expired = denied(lambda: case.reviews.get_case(case.reviewer.principal, approved.fact_id), 404)
    assert "current_approved" not in str(expired) and case.raw_rows[0]["footnote_text"] not in str(expired)
    with Session(pg_engine) as session, session.begin():
        denied(lambda: verify(case, session, approved), 404)
    with Session(pg_engine) as session, session.begin():
        session.get(StorageObject, case.file.id).expires_at = original_expiry
        source = session.get(CatalogSourceVersion, case.source.id)
        source.manual_import_permission = "denied"
        source.manual_import_enabled = False
    unavailable = case.reviews.get_case(case.reviewer.principal, approved.fact_id)
    assert unavailable.current_approved is False and unavailable.current_decision_id == approved.decision_id
    with Session(pg_engine) as session, session.begin():
        denied(lambda: verify(case, session, approved), 403, 409)
    assert len(rows(pg_engine, ReviewDecision)) == 1


def test_wrong_mapper_engine_is_rejected_before_io_and_caller_failure_rolls_back(review_case_factory,
        pg_engine, monkeypatch):
    case = review_case_factory()
    approved = decide(case)
    foreign = create_engine(pg_engine.url, hide_parameters=True)
    event.listen(foreign, "connect", lambda *args: pytest.fail("A mismatched mapper must not connect"))
    try:
        for model in (ReviewCase, ReviewDecision, ReviewConflictResolution, FactCandidate, StorageObject, EvidenceSnippet):
            with Session(pg_engine, binds={model: foreign}) as session, session.begin():
                denied(lambda: verify(case, session, approved), 503)
        wrong = Session(foreign)
        wrong.begin()
        denied(lambda: verify(case, wrong, approved), 503)
        assert wrong.in_transaction()
        wrong.rollback()
        wrong.close()
    finally:
        foreign.dispose()
    with Session(pg_engine) as session:
        session.begin()
        dataset = session.get(CatalogDataset, case.source.dataset_id)
        before = dataset.revision
        dataset.revision += 1
        session.flush()
        denied(lambda: verify(case, session, approved, expected_case_revision=999), 409)
        assert not session.in_transaction()
        session.commit()
    with Session(pg_engine) as session:
        assert session.get(CatalogDataset, case.source.dataset_id).revision == before


def test_required_success_audit_failure_rolls_back_case_and_decision(review_case_factory, pg_engine):
    case = review_case_factory()
    inserted = False
    def fail(connection, cursor, statement, parameters, context, many):
        nonlocal inserted
        if statement.lstrip().startswith("INSERT INTO review_decisions"):
            inserted = True
        elif inserted and statement.lstrip().startswith("INSERT INTO auth_audit_events"):
            raise RuntimeError(SENTINEL)
    event.listen(pg_engine, "before_cursor_execute", fail)
    try:
        denied(lambda: decide(case), 503)
    finally:
        event.remove(pg_engine, "before_cursor_execute", fail)
    assert inserted and rows(pg_engine, ReviewCase) == [] and rows(pg_engine, ReviewDecision) == []
    assert decide(case).case_revision == 1


def test_true_deferred_commit_failure_rolls_back_all_review_rows_then_retry(review_case_factory, pg_engine):
    case = review_case_factory()
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION demo_t18_commit_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'DEMO_T18_PRIVATE_FAILURE_SENTINEL' USING ERRCODE='23514'; END $$"))
        connection.execute(text("CREATE CONSTRAINT TRIGGER demo_t18_commit_failure AFTER INSERT ON review_decisions "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION demo_t18_commit_failure()"))
    denied(lambda: decide(case), 503)
    assert rows(pg_engine, ReviewCase) == [] and rows(pg_engine, ReviewDecision) == []
    assert rows(pg_engine, ReviewConflictResolution) == []
    with pg_engine.begin() as connection:
        connection.execute(text("DROP TRIGGER demo_t18_commit_failure ON review_decisions"))
    assert decide(case).case_revision == 1


@pytest.mark.parametrize("expiry", ["file", "source", "mfa"])
def test_actual_audit_wait_crossing_expiry_refuses_and_rolls_back(review_case_factory, pg_engine, clock, expiry):
    case = review_case_factory()
    if expiry == "file":
        with Session(pg_engine) as session, session.begin():
            session.get(StorageObject, case.file.id).expires_at = clock() + timedelta(seconds=1)
    elif expiry == "source":
        # Keep the separately checked file/session/MFA current, then cross only the
        # exact source snapshot's real one-day fixture recheck deadline during SQL I/O.
        clock.advance(int((case.source.recheck_due_at - clock()).total_seconds()) - 1)
        with Session(pg_engine) as session, session.begin():
            session.get(StorageObject, case.file.id).expires_at = case.source.recheck_due_at + timedelta(days=1)
            current_session = session.get(AuthSession, case.reviewer.actor.session_id)
            current_session.created_at = clock()
            current_session.expires_at = clock() + timedelta(seconds=3600)
            current_session.assurance_auth_time = clock()
        case.reviewer.principal = case.reviewer.service.get_principal(case.reviewer.actor.cookie)
    install_audit_barrier(pg_engine)
    started, pids = Event(), []
    def mark(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().startswith("INSERT INTO review_decisions"):
            connection.execute(text("SET LOCAL t18.probe='1'"))
        elif statement.lstrip().startswith("INSERT INTO auth_audit_events") and not started.is_set():
            if connection.scalar(text("SELECT current_setting('t18.probe',true)")) == "1":
                pids.append(connection.scalar(text("SELECT pg_backend_pid()")))
                started.set()
    event.listen(pg_engine, "before_cursor_execute", mark)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pg_engine.begin() as blocker:
                blocker_id = blocker.scalar(text("SELECT pg_backend_pid()"))
                blocker.execute(text("SELECT id FROM demo_t18_audit_barrier WHERE id=1 FOR UPDATE"))
                pending = pool.submit(decide, case)
                wait_for_block(pg_engine, started, pids, blocker_id)
                clock.advance(61 if expiry == "mfa" else 1)
            denied(lambda: pending.result(timeout=8), 401, 403, 404, 409)
    finally:
        event.remove(pg_engine, "before_cursor_execute", mark)
    assert rows(pg_engine, ReviewCase) == [] and rows(pg_engine, ReviewDecision) == []


def test_two_different_reviewer_accounts_serialize_real_decisions_on_one_logical_case(review_case_factory,
        administrator_factory, pg_engine):
    case = review_case_factory()
    second_reviewer = administrator_factory()
    assert second_reviewer.actor.user_id not in (case.admin.actor.user_id, case.reviewer.actor.user_id)
    install_audit_barrier(pg_engine)
    first_started, second_started = Event(), Event()
    first_pid, second_pid, worker_ids = [], [], []
    def observe(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().startswith("INSERT INTO review_decisions") and not first_started.is_set():
            connection.execute(text("SET LOCAL t18.probe='1'"))
        elif statement.lstrip().startswith("INSERT INTO auth_audit_events") and not first_started.is_set():
            if connection.scalar(text("SELECT current_setting('t18.probe',true)")) == "1":
                first_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
                first_started.set()
        if (worker_ids and get_ident() == worker_ids[0] and statement.lstrip().startswith("SELECT")
            and "FOR UPDATE" in statement.upper() and any(name in statement for name in
                ("catalog_datasets", "catalog_offerings", "review_cases")) and not second_started.is_set()):
            second_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
            second_started.set()
    def contender():
        worker_ids.append(get_ident())
        return case.reviews.decide(second_reviewer.principal, request(case.candidates[0]))
    event.listen(pg_engine, "before_cursor_execute", observe)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            with pg_engine.begin() as blocker:
                blocker_id = blocker.scalar(text("SELECT pg_backend_pid()"))
                blocker.execute(text("SELECT id FROM demo_t18_audit_barrier WHERE id=1 FOR UPDATE"))
                first = pool.submit(decide, case)
                wait_for_block(pg_engine, first_started, first_pid, blocker_id)
                pending = pool.submit(contender)
                wait_for_block(pg_engine, second_started, second_pid, first_pid[0])
            assert first.result(timeout=8).case_revision == 1
            denied(lambda: pending.result(timeout=8), 409)
    finally:
        event.remove(pg_engine, "before_cursor_execute", observe)
    assert len(rows(pg_engine, ReviewDecision)) == 1 and len(rows(pg_engine, ReviewCase)) == 1


def test_two_store_sessions_really_contend_on_unique_case_without_auth_serialization(review_case_factory,
        administrator_factory, reviews_store, pg_engine, clock):
    case = review_case_factory()
    second_reviewer = administrator_factory()
    fact = case.candidates[0]
    first_started, release, second_started = Event(), Event(), Event()
    first_pid, second_pid, worker_ids = [], [], []
    def observe(connection, cursor, statement, parameters, context, many):
        if (worker_ids and get_ident() == worker_ids[0] and statement.lstrip().startswith("INSERT INTO review_cases")
            and not second_started.is_set()):
            second_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
            second_started.set()
    def work(reviewer, *, first=False):
        if not first:
            worker_ids.append(get_ident())
        with Session(pg_engine) as session, session.begin():
            hint = session.get(FactCandidate, fact.id)
            claimed = reviews_store.claim_case(session, hint, now=clock())
            result = reviews_store.record(session, claimed, request(fact), fact, reviewer=reviewer.principal,
                audit_event_id=uuid4(), now=clock())
            if first:
                first_pid.append(session.scalar(text("SELECT pg_backend_pid()")))
                first_started.set()
                assert release.wait(timeout=8), "The first case transaction was not released"
            return result.id
    event.listen(pg_engine, "before_cursor_execute", observe)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(work, case.reviewer, first=True)
            assert first_started.wait(timeout=5)
            second = pool.submit(work, second_reviewer)
            try:
                wait_for_block(pg_engine, second_started, second_pid, first_pid[0])
            finally:
                release.set()
            assert first.result(timeout=8)
            denied(lambda: second.result(timeout=8), 409)
    finally:
        release.set()
        event.remove(pg_engine, "before_cursor_execute", observe)
    assert len(rows(pg_engine, ReviewDecision)) == 1 and len(rows(pg_engine, ReviewCase)) == 1


def test_history_update_delete_are_database_rejected_and_original_facts_unchanged(review_case_factory,
        candidate_factory, pg_engine, reviews_store):
    case = review_case_factory(rows=[candidate_factory(value_text=value) for value in ("600", "601")])
    fact = case.facts.get_fact(case.reviewer.principal, case.candidates[0].id)
    prior = rows(pg_engine, FactCandidate), rows(pg_engine, FactConflict)
    decide(case, fact)
    for table in ("review_decisions", "review_conflict_resolutions"):
        for command_text in (f"UPDATE {table} SET id=id", f"DELETE FROM {table}"):
            with pytest.raises(DBAPIError), pg_engine.begin() as connection:
                connection.execute(text(command_text))
    assert prior == (rows(pg_engine, FactCandidate), rows(pg_engine, FactConflict))
    with pg_engine.begin() as connection:
        triggers = set(connection.execute(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal AND tgenabled='O' "
            "AND tgrelid IN(to_regclass('review_decisions'),to_regclass('review_conflict_resolutions'))")).scalars())
        assert triggers == {"reviews_decisions_immutable", "reviews_resolutions_immutable"}
        connection.execute(text("ALTER TABLE review_decisions DISABLE TRIGGER reviews_decisions_immutable"))
    denied(reviews_store.assert_schema_ready, 503)
    with pg_engine.begin() as connection:
        connection.execute(text("ALTER TABLE review_decisions ENABLE TRIGGER reviews_decisions_immutable"))


def test_independent_migration_repeat_and_downgrade_preserve_all_prior_domains(review_case_factory,
        pg_engine, reviews_store, monkeypatch, tmp_path):
    from services.api.app.migrations import migrate as migrate_m0
    from services.api.app.seed import seed
    case = review_case_factory()
    decide(case)
    monkeypatch.chdir(tmp_path)
    migrate_m0(pg_engine)
    seed(pg_engine)
    def preserved():
        with pg_engine.connect() as connection:
            return {name: connection.execute(text('SELECT * FROM "' + name + '" ORDER BY 1')).all()
                for name in inspect(connection).get_table_names() if name not in
                    {"review_cases", "review_decisions", "review_conflict_resolutions", "reviews_alembic_version"}}
    before = preserved()
    assert len(ReviewsBase.metadata.tables) == 3
    migrate_reviews(pg_engine)
    migrate_reviews(pg_engine)
    assert preserved() == before
    with pg_engine.begin() as connection:
        config = migration_config()
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    assert not {"review_cases", "review_decisions", "review_conflict_resolutions"} & set(inspect(pg_engine).get_table_names())
    denied(reviews_store.assert_schema_ready, 503)
    assert preserved() == before
    migrate_reviews(pg_engine)
    reviews_store.assert_schema_ready()
    assert preserved() == before and rows(pg_engine, ReviewDecision) == []
