"""Anonymous HTTP and real-PG current-proof checks for DEMO test releases only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from threading import Event, get_ident
from time import monotonic
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr
import pytest
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.orm import Session

from services.api.app.admin.sources.models import CatalogSource, CatalogSourceVersion
from services.api.app.admissions_catalog.models import AdmissionOffering, CatalogDataset
from services.api.app.api.public_catalog import create_public_catalog_app
from services.api.app.auth.models import AuthSession, AuthUserRole
from services.api.app.public_catalog.query import encode_cursor
from services.api.app.public_catalog.reader import CatalogReader
from services.api.app.public_catalog.schemas import PublicCatalogError, PublicCatalogPolicy, PublicOfferingQuery
from services.api.app.public_catalog.schemas import CoverageData, PublicOfferingsData
from services.api.app.api.v2.schemas import PageInfo
from services.api.app.releases.models import CatalogReleaseMember, CatalogReleaseState, ChangeEvent
from services.api.app.releases.schemas import PublishMember, WithdrawalRequest
from services.api.app.reviews.schemas import CHECK_FIELDS, ReviewCheck, ReviewRequest
from services.api.app.settings import V2RuntimeSettings
from services.api.app.storage.models import StorageObject


pytestmark = pytest.mark.postgres
PRIVATE_SENTINEL = "DEMO_T20_PRIVATE_URL_SENTINEL"
PRIVATE_KEYS = {"file_id", "file_metadata_sha256", "owner_user_id", "publisher_user_id", "reviewer_user_id",
    "session_id", "entry_url", "storage_key", "object_key", "import_id", "import_row_id", "source_record_reference"}


def denied(call, *codes):
    with pytest.raises(ValueError) as caught:
        call()
    assert caught.value.status_code in codes
    assert PRIVATE_SENTINEL not in str(caught.value) + repr(caught.value)
    return caught.value


def query(**changes):
    return PublicOfferingQuery(**dict({"entry_year": 2026}, **changes))


def publish(case, **changes):
    members = tuple(PublishMember(fact_id=item.fact_id, expected_case_revision=item.case_revision,
        expected_decision_id=item.decision_id, public_evidence=True) for item in case.decisions)
    return case.releases.publish(case.reviewer.principal, case.publish_request(members=members, **changes),
        SecretStr("DEMO_T20_" + uuid4().hex))


def withdraw(case, release=None):
    release = release or case.release
    return case.releases.withdraw(case.reviewer.principal, WithdrawalRequest(release_id=release.release_id,
        expected_state_revision=release.state_revision, reason_code="ADMIN_REQUEST"))


def assert_public_projection(value):
    if isinstance(value, dict):
        assert not PRIVATE_KEYS.intersection(value)
        for nested in value.values():
            assert_public_projection(nested)
    elif isinstance(value, (tuple, list)):
        for nested in value:
            assert_public_projection(nested)


def assert_protocol(response, status):
    assert response.status_code == status
    assert response.headers["Cache-Control"] == "no-store"
    body = response.json()
    assert len(response.headers["X-Request-ID"]) == 32
    assert body.get("meta", body.get("error"))["request_id"] == response.headers["X-Request-ID"]
    assert PRIVATE_SENTINEL not in response.text
    return body


def client(case):
    return TestClient(create_public_catalog_app(case.public_settings, reader=case.reader), base_url="https://public.test.invalid")


def test_anonymous_http_returns_pinned_fact_and_public_excerpt_without_private_provenance(public_case_factory, pg_engine, catalog_store):
    case = public_case_factory()
    reads_before = case.storage.backend.read_count
    with client(case) as browser:
        body = assert_protocol(browser.get("/v2/offerings", params={"entry_year": "2026"},
            headers={"X-Request-ID": "CLIENT_ID_MUST_NOT_BE_TRUSTED"}), 200)
        item = body["data"]["items"][0]
        assert item["release_id"] == str(case.release.release_id)
        assert item["id"] == str(case.candidates[0].offering_id) and item["version"] == 1
        assert item["is_synthetic"] is True and item["institution_name"].startswith("DEMO_")
        fact = item["facts"][0]
        assert (fact["value_text"], fact["normalized_value"], fact["unit"], fact["footnote_state"]) == ("600.00", "600", "points", "present")
        evidence = assert_protocol(browser.get("/v2/evidence/" + fact["evidence_id"],
            params={"release_id": str(case.release.release_id)}), 200)["data"]
        assert evidence["quote"] == case.review_snippets[0].text
        assert evidence["document_sha256"] == case.file.sha256
        assert evidence["locator"]["page"] is None and evidence["locator"]["section"] is None
        assert evidence["publisher"].startswith("DEMO_") and evidence["authority_claim"] == "claimed_official"
        for data in (body["data"], evidence):
            assert_public_projection(data)
            raw = json.dumps(data, ensure_ascii=False)
            assert str(case.file.id) not in raw and str(case.admin.actor.user_id) not in raw
            assert case.source.entry_url not in raw
        coverage = body["data"]["coverage"]
        assert coverage == {"status": "partial", "returned_count": 1, "expected_total": None, "coverage_ratio": None}
    assert case.storage.backend.read_count == reads_before
    # A later registry version does not silently rewrite the released reference.
    with Session(pg_engine) as session, session.begin():
        revision = session.get(CatalogDataset, case.source.dataset_id).revision
        catalog_store.append_offering_version(session, case.candidates[0].offering_id, version_id=uuid4(),
            expected_dataset_revision=revision, expected_version=1)
    pinned = case.reader.list_offerings(query()).items[0]
    assert pinned.version == 1
    # Page identity uses all three pinned references, matching SQL/cursor order.
    shaped = PublicOfferingsData(items=(pinned, pinned.model_copy(update={"version": 2})),
        page=PageInfo(limit=2, next_cursor=None, has_more=False),
        coverage=CoverageData(status="partial", returned_count=2, expected_total=None, coverage_ratio=None))
    assert len(shaped.items) == 2
    with pytest.raises(ValueError):
        PublicOfferingsData.model_validate(shaped.model_copy(update={"items": (pinned, pinned)}))


def test_public_authority_is_independent_of_creator_reviewer_publisher_sessions_and_roles(public_case_factory, pg_engine, monkeypatch):
    case = public_case_factory()
    with Session(pg_engine) as session, session.begin():
        for actor in (case.admin.actor, case.reviewer.actor):
            session.get(AuthSession, actor.session_id).revoked_at = case.releases.auth_service._now()
            session.get(AuthUserRole, (actor.user_id, "data_admin")).revoked_at = case.releases.auth_service._now()
    def forbidden(*args, **kwargs):
        raise AssertionError("Public reads must not impersonate a private administrator")
    for service in (case.admin.service, case.reviewer.service):
        monkeypatch.setattr(service, "get_principal", forbidden)
        monkeypatch.setattr(service, "check_admin_assurance", forbidden)
    with client(case) as browser:
        assert len(assert_protocol(browser.get("/v2/offerings?entry_year=2026"), 200)["data"]["items"]) == 1
        assert_protocol(browser.get(f"/v2/evidence/{case.review_snippets[0].id}?release_id={case.release.release_id}"), 200)


def test_draft_and_unpublished_registry_never_become_public_records(public_case_factory):
    case = public_case_factory(published=False, approve=False)
    result = case.reader.list_offerings(query())
    assert result.items == () and result.coverage.status == "no_published_records"
    assert result.coverage.expected_total is None
    denied(lambda: case.reader.get_evidence(case.review_snippets[0].id, uuid4()), 404)


def test_private_evidence_has_no_public_identifier_and_wrong_release_never_authorizes(public_case_factory):
    case = public_case_factory(public_evidence=False)
    page = case.reader.list_offerings(query())
    assert page.items[0].facts[0].evidence_id is None
    denied(lambda: case.reader.get_evidence(case.review_snippets[0].id, case.release.release_id), 404)
    denied(lambda: case.reader.get_evidence(case.review_snippets[0].id, uuid4()), 404)


def test_distinct_offering_pagination_filters_and_empty_terminal_page(public_case_factory, candidate_factory, extra_offering_factory, pg_engine):
    second, third = extra_offering_factory(), extra_offering_factory()
    case = public_case_factory(rows=[candidate_factory(field_key="DEMO_FIELD_A"), candidate_factory(field_key="DEMO_FIELD_B"),
        candidate_factory(offering_id=str(second.id)), candidate_factory(offering_id=str(third.id))])
    pages, cursor = [], None
    for _ in range(3):
        page = case.reader.list_offerings(query(limit=1, cursor=cursor))
        assert len(page.items) == 1 and page.coverage.status == "partial"
        pages.extend(page.items)
        cursor = page.page.next_cursor
        if not page.page.has_more:
            break
    assert len(pages) == 3 and len({(item.release_id, item.id) for item in pages}) == 3
    assert [item.id for item in pages] == sorted(item.id for item in pages)
    assert sum(len(item.facts) for item in pages) == 4
    assert cursor is None
    with Session(pg_engine) as session:
        watermark = session.scalar(select(func.count()).select_from(ChangeEvent))
    token = encode_cursor(query(limit=1), watermark, UUID(int=(1 << 128) - 1), UUID(int=(1 << 128) - 1), 1)
    terminal = case.reader.list_offerings(query(limit=1, cursor=token))
    assert terminal.items == () and terminal.coverage.status == "partial" and terminal.coverage.returned_count == 0
    assert not terminal.page.has_more and terminal.coverage.expected_total is None


def test_year_country_and_applicant_filters_are_exact_without_inferred_identity(public_case_factory):
    case = public_case_factory()
    positive = query(country="CN", study_level="undergraduate", province="known:DEMO_PROVINCE",
        pathway="known:DEMO_PATHWAY", course_system="known:DEMO_COURSE_SYSTEM", applicant_category="known:DEMO_APPLICANT_CATEGORY")
    assert len(case.reader.list_offerings(positive).items) == 1
    for changes in ({"entry_year": 2027}, {"country": "GB"}, {"province": "known:demo_province"},
                    {"applicant_category": "not_applicable"}, {"release_id": uuid4()}):
        empty = case.reader.list_offerings(query(**changes))
        assert empty.items == () and empty.coverage.status == "no_published_records"


@pytest.mark.parametrize("change", ["withdraw", "replace"])
def test_cursor_watermark_rejects_publication_changes_and_old_release_never_falls_back(public_case_factory, change):
    case = public_case_factory()
    first = case.reader.list_offerings(query(limit=1))
    token = encode_cursor(query(limit=1), 1, case.release.release_id, first.items[0].id, 1)
    if change == "withdraw":
        withdraw(case)
    else:
        successor = publish(case, valid_until=case.release.valid_until + timedelta(seconds=1),
            replaces_release_id=case.release.release_id, expected_replaced_state_revision=1)
        assert case.reader.list_offerings(query()).items[0].release_id == successor.release_id
    denied(lambda: case.reader.list_offerings(query(limit=1, cursor=token)), 409)
    assert case.reader.list_offerings(query(release_id=case.release.release_id)).items == ()
    denied(lambda: case.reader.get_evidence(case.review_snippets[0].id, case.release.release_id), 404)


@pytest.mark.parametrize("mutation", ["public_permission", "source_latest", "file_hash", "file_deleted", "scope"])
def test_captured_proof_requires_current_public_rights_latest_source_exact_file_and_scope(public_case_factory, pg_engine, mutation):
    case = public_case_factory()
    with Session(pg_engine) as session, session.begin():
        if mutation == "public_permission":
            session.get(CatalogSourceVersion, case.source.id).publication_permission = "denied"
        elif mutation == "source_latest":
            root = session.get(CatalogSource, case.source.source_id)
            original = session.get(CatalogSourceVersion, case.source.id)
            values = {column.name: getattr(original, column.name) for column in original.__table__.columns}
            values.update(id=uuid4(), version=2, publication_permission="denied")
            session.add(CatalogSourceVersion(**values))
            root.current_version = 2
        elif mutation == "file_hash":
            session.get(StorageObject, case.file.id).sha256 = "0" * 64
        elif mutation == "file_deleted":
            session.get(StorageObject, case.file.id).status = "delete_pending"
        else:
            session.get(AdmissionOffering, case.candidates[0].offering_id).province_key = "known:DEMO_CHANGED_PROVINCE"
    denied(lambda: case.reader.list_offerings(query()), 404, 409, 503)
    denied(lambda: case.reader.get_evidence(case.review_snippets[0].id, case.release.release_id), 404, 409, 503)


def test_file_and_release_expiry_do_not_return_previously_public_snapshot(public_case_factory, pg_engine, clock):
    case = public_case_factory(published=False)
    with Session(pg_engine) as session, session.begin():
        session.get(StorageObject, case.file.id).expires_at = clock() + timedelta(seconds=1)
    case.release = publish(case)
    assert len(case.reader.list_offerings(query()).items) == 1
    clock.advance(1)
    denied(lambda: case.reader.list_offerings(query()), 404, 409)
    denied(lambda: case.reader.get_evidence(case.review_snippets[0].id, case.release.release_id), 404, 409)


def test_current_return_decision_removes_public_approval_without_reusing_old_review(public_case_factory):
    case = public_case_factory()
    decision = case.decisions[0]
    case.reviews.decide(case.reviewer.principal, ReviewRequest(fact_id=decision.fact_id,
        expected_fact_version=1, expected_case_revision=decision.case_revision, action="return",
        checks=tuple(ReviewCheck(field=field, status="not_applicable" if field in ("statistics_context", "date_context")
            else "accepted") for field in CHECK_FIELDS), conflict_resolutions=(), return_reason="INVALID_VALUE"))
    denied(lambda: case.reader.list_offerings(query()), 409)


def test_new_conflicting_fact_invalidates_published_review_selection(public_case_factory, candidate_factory):
    case = public_case_factory()
    other = public_case_factory(published=False, approve=False, rows=[candidate_factory(value_text="601.00",
        footnote_state="present", footnote_text=case.raw_rows[0]["footnote_text"])])
    assert case.candidates[0].id in other.candidates[0].conflicting_ids
    denied(lambda: case.reader.list_offerings(query()), 409)


def test_immutable_original_row_binding_rejects_post_publication_raw_candidate_changes(public_case_factory, pg_engine):
    from services.api.app.admin.imports.models import ImportCandidateRow
    case = public_case_factory()
    with Session(pg_engine) as session, session.begin():
        row = session.get(ImportCandidateRow, case.row_ids[0])
        # Preserve the frozen decimal DB constraint; the meaningful attack is a
        # different admissible raw value whose captured fingerprint is stale.
        row.value_text = "601.00"
    denied(lambda: case.reader.list_offerings(query()), 409, 503)


def test_production_and_missing_explicit_test_permission_cannot_read_demo(public_case_factory):
    case = public_case_factory()
    for settings, policy in (
        (case.public_settings, PublicCatalogPolicy()),
        (case.public_settings, PublicCatalogPolicy(enabled=True)),
        (V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled", _env_file=None),
            PublicCatalogPolicy()),
    ):
        reader = CatalogReader(case.releases, settings, policy)
        denied(lambda: reader.list_offerings(query()), 503)
    forged = case.reader.policy.model_copy(update={"enabled": 1})
    with pytest.raises(ValueError):
        CatalogReader(case.releases, case.public_settings, forged)
    # Explicitly opening a server configuration does not promote DEMO records
    # into formal data. There is no invented real/final-fact positive fixture.
    production = CatalogReader(case.releases, V2RuntimeSettings(app_environment="production",
        data_mode="verified", model_mode="disabled", _env_file=None),
        PublicCatalogPolicy(enabled=True, real_catalog_ready=True))
    assert production.list_offerings(query()).items == ()
    denied(lambda: production.get_evidence(case.review_snippets[0].id, case.release.release_id), 503)
    identity = case.releases.auth_service
    prior = identity.runtime_settings
    try:
        identity.runtime_settings = V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled", _env_file=None)
        denied(lambda: CatalogReader(case.releases, case.public_settings,
            PublicCatalogPolicy(enabled=True, allow_test_fixture_read=True)), 503)
    finally:
        identity.runtime_settings = prior


def test_http_query_errors_and_unknown_private_routes_are_safe_no_store(public_case_factory, monkeypatch):
    case = public_case_factory()
    with client(case) as browser:
        for suffix in ("", "?entry_year=2026&entry_year=2026", "?entry_year=2026&owner_user_id=DEMO_T20_PRIVATE_URL_SENTINEL",
            "?entry_year=2026.0", "?entry_year=true", "?entry_year=2026&limit=0", "?entry_year=2026&limit=101",
            "?entry_year=2026&province=unknown", "?entry_year=2026&cursor=DEMO_T20_PRIVATE_URL_SENTINEL"):
            assert_protocol(browser.get("/v2/offerings" + suffix), 422)
        assert_protocol(browser.get(f"/v2/evidence/{case.review_snippets[0].id}"), 422)
        assert_protocol(browser.get(f"/v2/evidence/{case.review_snippets[0].id}?release_id={case.release.release_id}&release_id={case.release.release_id}"), 422)
        assert_protocol(browser.get("/v2/profiles/" + str(case.admin.actor.user_id)), 404)
        assert_protocol(browser.post("/v2/offerings"), 405)
        assert_protocol(browser.get("/v2/config?data_mode=verified"), 422)
        assert_protocol(browser.get("/v2/offerings?entry_year=2026&limit=1"), 200)
        for path in ("/v1", "/v2/openapi.json"):
            closed = browser.get(path)
            assert closed.status_code == 404 and closed.headers["Cache-Control"] == "no-store"
        invalid = assert_protocol(browser.get("/v2/offerings?entry_year=2026&cursor=DEMO_BAD_CURSOR"), 422)
        assert invalid["error"]["message"] == "分页游标无效或与查询不匹配"
        def unexpected(_):
            raise RuntimeError(PRIVATE_SENTINEL)
        monkeypatch.setattr(case.reader, "list_offerings", unexpected)
        failure = assert_protocol(browser.get("/v2/offerings?entry_year=2026"), 500)
        assert failure["error"]["code"] == "INTERNAL_ERROR"


def test_public_reads_do_not_create_tables_audit_events_receipts_or_mutate_state(public_case_factory, pg_engine):
    case = public_case_factory()
    tables_before = inspect(pg_engine).get_table_names()
    def counts():
        with pg_engine.connect() as connection:
            return tuple(connection.scalar(text("SELECT count(*) FROM " + name)) for name in (
                "auth_audit_events", "idempotency_records", "catalog_change_events", "catalog_outbox"))
    before = counts()
    for _ in range(2):
        case.reader.list_offerings(query())
        case.reader.get_evidence(case.review_snippets[0].id, case.release.release_id)
    assert counts() == before and inspect(pg_engine).get_table_names() == tables_before
    # A mapper-specific bind must be rejected before touching another engine.
    from sqlalchemy import create_engine
    foreign = create_engine(pg_engine.url, hide_parameters=True)
    def forbidden_connect(*args, **kwargs):
        raise AssertionError("A public read connected to a foreign engine")
    event.listen(foreign, "connect", forbidden_connect)
    try:
        with Session(pg_engine, binds={StorageObject: foreign}) as session, session.begin():
            denied(lambda: case.reader._guard_session(session), 503)
    finally:
        foreign.dispose()
    assert counts() == before


def wait_for_block(engine, started, pids, blocker, pending):
    arrival = monotonic() + 20
    while not started.wait(timeout=0.05):
        if pending.done():
            pending.result()
            pytest.fail("The reader completed before the required SQL lock boundary")
        if monotonic() >= arrival:
            pytest.fail("The reader did not reach its SQL boundary within 20 seconds")
    until = monotonic() + 5
    while monotonic() < until:
        with engine.connect() as connection:
            waiting = connection.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_stat_activity "
                "WHERE pid=:pid AND wait_event_type='Lock' AND :blocker=ANY(pg_blocking_pids(pid)))"),
                {"pid": pids[0], "blocker": blocker})
        if waiting:
            return
    pytest.fail("An actual PostgreSQL lock wait was not observed")


def test_reader_waiting_on_dataset_observes_committed_withdrawal_not_initial_hint(public_case_factory, pg_engine):
    case = public_case_factory()
    started, pids, main_thread = Event(), [], get_ident()
    def observe(connection, cursor, statement, parameters, context, many):
        if get_ident() != main_thread and "FROM catalog_datasets" in statement and "FOR UPDATE" in statement:
            if not started.is_set():
                pids.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
                started.set()
    event.listen(pg_engine, "before_cursor_execute", observe)
    try:
        with Session(pg_engine) as locked:
            locked.begin()
            blocker = locked.scalar(text("SELECT pg_backend_pid()"))
            locked.execute(select(CatalogDataset).where(CatalogDataset.id == case.source.dataset_id).with_for_update())
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(lambda: denied(lambda: case.reader.list_offerings(query()), 404, 409))
                try:
                    wait_for_block(pg_engine, started, pids, blocker, pending)
                    case.releases.withdraw(case.reviewer.principal, WithdrawalRequest(release_id=case.release.release_id,
                        expected_state_revision=1, reason_code="ADMIN_REQUEST"), session=locked)
                    locked.commit()
                finally:
                    if locked.in_transaction():
                        locked.rollback()
                pending.result(timeout=30)
        assert case.reader.list_offerings(query()).items == ()
    finally:
        event.remove(pg_engine, "before_cursor_execute", observe)


@pytest.mark.parametrize("deadline", ["source", "file"])
def test_real_later_member_sql_wait_rechecks_first_member_deadline_for_anonymous_reader(
        public_case_factory, candidate_factory, pg_engine, clock, deadline):
    one = public_case_factory(published=False, rows=[candidate_factory(field_key="DEMO_FIRST_FIELD")])
    two = public_case_factory(published=False, rows=[candidate_factory(field_key="DEMO_SECOND_FIELD")])
    first, later = sorted((one, two), key=lambda case: case.candidates[0].id)
    # All changes happen before capturing the release. No expired source or
    # original file is extended or revived, and no published hash is rewritten.
    with Session(pg_engine) as session, session.begin():
        last_source = session.get(CatalogSourceVersion, later.source.id)
        last_source.recheck_days = 2
        last_source.recheck_due_at = last_source.created_at + timedelta(days=2)
        for case in (first, later):
            asset = session.get(StorageObject, case.file.id)
            asset.expires_at = asset.created_at + timedelta(days=2 if deadline == "source" or case is later else 1)
        if deadline == "file":
            initial_source = session.get(CatalogSourceVersion, first.source.id)
            initial_source.recheck_days = 2
            initial_source.recheck_due_at = initial_source.created_at + timedelta(days=2)
    members = tuple(PublishMember(fact_id=case.decisions[0].fact_id, expected_case_revision=1,
        expected_decision_id=case.decisions[0].decision_id, public_evidence=True) for case in (first, later))
    released = first.releases.publish(first.reviewer.principal,
        first.publish_request(members=members, valid_until=clock() + timedelta(days=2)), SecretStr("DEMO_T20_DEADLINE"))
    clock.advance(86400 - 1)
    assert len(first.reader.list_offerings(query()).items[0].facts) == 2
    started, pids, main_thread = Event(), [], get_ident()
    def observe(connection, cursor, statement, parameters, context, many):
        values = parameters.values() if isinstance(parameters, dict) else parameters
        if (get_ident() != main_thread and "FROM catalog_sources" in statement and "FOR UPDATE" in statement
            and any(str(value) == str(later.source.source_id) for value in values)):
            if not started.is_set():
                pids.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
                started.set()
    event.listen(pg_engine, "before_cursor_execute", observe)
    try:
        with Session(pg_engine) as locked:
            locked.begin()
            blocker = locked.scalar(text("SELECT pg_backend_pid()"))
            locked.execute(select(CatalogSource).where(CatalogSource.id == later.source.source_id).with_for_update())
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(lambda: denied(lambda: first.reader.list_offerings(query()), 409))
                try:
                    wait_for_block(pg_engine, started, pids, blocker, pending)
                    clock.advance(1)
                finally:
                    locked.rollback()
                pending.result(timeout=30)
        denied(lambda: first.reader.get_evidence(first.review_snippets[0].id, released.release_id), 409)
    finally:
        event.remove(pg_engine, "before_cursor_execute", observe)
