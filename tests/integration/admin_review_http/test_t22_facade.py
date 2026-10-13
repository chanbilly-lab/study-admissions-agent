"""Real T22 HTTP preparation and independent review in a fresh PostgreSQL schema."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, timedelta
import json
from threading import Barrier, Event
import time
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from services.api.app.admissions_catalog.models import CatalogDataset
from services.api.app.auth.router import SESSION_COOKIE
from services.api.app.releases.models import CatalogRelease, ChangeEvent, OutboxEvent
from services.api.app.reviews.models import ReviewDecision
from services.api.app.reviews.schemas import CHECK_FIELDS


pytestmark = pytest.mark.postgres
ORIGIN = "https://app.test.invalid"


@contextmanager
def browser(workspace, administrator):
    with TestClient(workspace.app, base_url=ORIGIN, raise_server_exceptions=False) as client:
        client.cookies.set(SESSION_COOKIE, administrator.actor.cookie.get_secret_value())
        token = client.get("/v2/auth/csrf")
        assert token.status_code == 200, token.json()
        client.headers.update({"Origin": ORIGIN, "X-CSRF-Token": token.json()["data"]["csrf_token"]})
        yield client


def succeeds(response):
    assert response.status_code == 200, response.json()
    assert response.headers["cache-control"] == "no-store"
    return response.json()["data"]


def review_request(detail, *, action="approve", revision=None):
    return dict(fact_id=detail["fact"]["id"], expected_fact_version=1,
        expected_case_revision=detail["case"]["case_revision"] if revision is None else revision,
        action=action, checks=[dict(field=field, status="not_applicable" if field in {
            "statistics_context", "date_context"} else "accepted") for field in CHECK_FIELDS],
        conflict_resolutions=[dict(fact_id=row["fact_id"], reason_code="INCORRECT_VALUE")
            for row in detail["conflicts"]] if action == "approve" else [],
        return_reason="MISSING_EVIDENCE" if action == "return" else None, confirmed=True)


@pytest.fixture
def workflow_factory(workspace_factory, administrator_factory, source_request_factory,
        candidate_factory, classification_factory, pg_engine, clock):
    def make(*, rows=None, publication_permission="granted", classification=None, setup=None):
        creator = administrator_factory(assurance_age_limit=600)
        reviewer = administrator_factory(assurance_age_limit=600)
        third = administrator_factory(assurance_age_limit=600)
        workspace = workspace_factory(administrator=creator)
        raw = rows if rows is not None else [candidate_factory()]
        if setup is not None:
            setup(workspace)
        data = json.dumps(raw, ensure_ascii=False).encode("utf-8")
        assert len(data) <= 4096
        request = source_request_factory(definition_updates=dict(manual_import_permission="granted",
            manual_import_enabled=True, publication_permission=publication_permission,
            license_basis="DEMO_T22_EXPLICIT_LICENSE", permission_record_reference="DEMO_T22_PERMISSION"))
        with Session(pg_engine) as session:
            revision = session.get(CatalogDataset, request.dataset_id).revision
        with browser(workspace, creator) as client:
            source = succeeds(client.post("/v2/admin/sources", json=dict(source=request.model_dump(mode="json"),
                expected_dataset_revision=revision, confirmed=True)))
            file = succeeds(client.post("/v2/admin/source-files", json=dict(source_id=source["source_id"],
                source_version=source["version"], filename="DEMO_T22.json", content_type="application/json",
                content_utf8=data.decode("utf-8"), confirmed=True)))
            imported = succeeds(client.post("/v2/admin/imports", headers={"Idempotency-Key": uuid4().hex}, json=dict(
                dataset_id=source["dataset_id"], source_id=source["source_id"], source_version=source["version"],
                file_id=file["id"], file_sha256=file["sha256"], format="json", confirmed=True)))
            found = succeeds(client.get(f'/v2/admin/imports/{imported["id"]}/rows'))
            document = succeeds(client.post("/v2/admin/evidence/documents", json=dict(dataset_id=source["dataset_id"],
                source_id=source["source_id"], source_version=source["version"], document_reference="DEMO_T22_" + uuid4().hex,
                language="und", confirmed=True)))
            version = succeeds(client.post("/v2/admin/evidence/versions", json=dict(document_id=document["id"],
                expected_current_version=0, file_id=file["id"], file_sha256=file["sha256"], confirmed=True)))
            prepared = []
            for row in found["rows"]:
                fields = row["row"]
                snippet = succeeds(client.post("/v2/admin/evidence/snippets", json=dict(document_id=document["id"],
                    document_version=version["version"], offering_id=fields["offering_id"],
                    offering_version=fields["offering_version"], entry_year=fields["entry_year"],
                    byte_start=0, byte_end=len(data), confirmed=True)))
                fact = succeeds(client.post("/v2/admin/facts", json=dict(import_id=imported["id"],
                    import_row_id=row["row_id"], classification=(classification or classification_factory()).model_dump(mode="json"),
                    evidence_id=snippet["id"], confirmed=True)))
                prepared.append(fact)
        def detail(client, index=0):
            return succeeds(client.get("/v2/admin/review-candidates/" + prepared[index]["id"]))
        def publish_request(decisions, **updates):
            with Session(pg_engine) as session:
                revision = session.get(CatalogDataset, request.dataset_id).revision
            fields = dict(dataset_id=str(request.dataset_id), expected_dataset_revision=revision, entry_year=2026,
                kind="test_fixture", valid_from=clock().isoformat(), valid_until=(clock() + timedelta(hours=1)).isoformat(),
                members=[dict(fact_id=decision["fact_id"], expected_case_revision=decision["case_revision"],
                    expected_decision_id=decision["decision_id"], public_evidence=True) for decision in decisions],
                replaces_release_id=None, expected_replaced_state_revision=None, confirmed=True)
            fields.update(updates)
            return fields
        return SimpleNamespace(workspace=workspace, creator=creator, reviewer=reviewer, third=third, source=source,
            file=file, imported=imported, found=found, facts=prepared, data=data, detail=detail,
            publish_request=publish_request)
    return make


def approve(case, client, index=0):
    return succeeds(client.post("/v2/admin/review-decisions", json=review_request(case.detail(client, index))))


def test_discover_prepare_independent_review_precheck_publish_replace_withdraw(workflow_factory, pg_engine):
    case = workflow_factory()
    with browser(case.workspace, case.creator) as creator:
        context = succeeds(creator.get("/v2/admin/review-context"))
        assert all(context[name] for name in ("can_prepare", "can_review", "can_publish", "can_withdraw"))
        detail = case.detail(creator)
        assert "SELF_REVIEW_FORBIDDEN" in detail["gaps"] and "UNRESOLVED_LOCATOR" not in detail["gaps"]
        assert creator.post("/v2/admin/review-decisions", json=review_request(detail)).status_code == 403
    with browser(case.workspace, case.reviewer) as reviewer:
        queue = succeeds(reviewer.get("/v2/admin/review-candidates", params={"dataset_id": case.source["dataset_id"], "entry_year": 2026}))
        assert [row["fact_id"] for row in queue["items"]] == [case.facts[0]["id"]]
        assert reviewer.get(f'/v2/admin/imports/{case.imported["id"]}/rows').status_code == 403
        decision = approve(case, reviewer)
        request = case.publish_request([decision])
        precheck = succeeds(reviewer.post("/v2/admin/releases/precheck", json=request))
        assert precheck["status"] == "precheck_passed"
        with Session(pg_engine) as session:
            assert session.scalar(select(func.count()).select_from(CatalogRelease)) == 0
        key = uuid4().hex
        published = succeeds(reviewer.post("/v2/admin/releases", json=request, headers={"Idempotency-Key": key}))
        replay = succeeds(reviewer.post("/v2/admin/releases", json=request, headers={"Idempotency-Key": key}))
        assert replay["release_id"] == published["release_id"] and replay["replayed"]
        assert succeeds(reviewer.get("/v2/admin/releases/" + published["release_id"]))["members"] == published["members"]
        current = succeeds(reviewer.get("/v2/admin/releases/current", params={"dataset_id": request["dataset_id"], "entry_year": 2026}))
        assert current["release"]["release_id"] == published["release_id"]
        replacement = case.publish_request([decision], replaces_release_id=published["release_id"],
            expected_replaced_state_revision=1)
        newer = succeeds(reviewer.post("/v2/admin/releases", json=replacement, headers={"Idempotency-Key": uuid4().hex}))
        with TestClient(case.workspace.app, base_url=ORIGIN) as anonymous:
            public = succeeds(anonymous.get("/public/v2/offerings?entry_year=2026"))
            assert public["items"][0]["release_id"] == newer["release_id"]
        withdrawn = succeeds(reviewer.post(f'/v2/admin/releases/{newer["release_id"]}/withdraw', json=dict(
            expected_state_revision=1, reason_code="ADMIN_REQUEST", confirmed=True)))
        assert withdrawn["state"] == "withdrawn"
        assert reviewer.get("/v2/admin/releases/" + newer["release_id"]).status_code == 409
        assert succeeds(reviewer.get("/v2/admin/releases/current", params={"dataset_id": request["dataset_id"], "entry_year": 2026}))["release"] is None
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(ChangeEvent)) == 4
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 4


def test_three_actors_current_conflicts_and_real_review_cas(workflow_factory, candidate_factory, pg_engine):
    case = workflow_factory(rows=[candidate_factory(value_text="600.00"), candidate_factory(value_text="601.00")])
    with browser(case.workspace, case.creator) as creator:
        first = succeeds(creator.get(f'/v2/admin/imports/{case.imported["id"]}/rows?limit=1'))
        second = succeeds(creator.get(f'/v2/admin/imports/{case.imported["id"]}/rows',
            params={"limit": 1, "cursor": first["next_cursor"]}))
        assert [first["rows"][0]["row"]["row_number"], second["rows"][0]["row"]["row_number"]] == [1, 2]
        assert second["next_cursor"] is None
        assert creator.get(f'/v2/admin/imports/{case.imported["id"]}/rows',
            params={"limit": 2, "cursor": first["next_cursor"]}).status_code == 409
        assert creator.get(f'/v2/admin/imports/{case.imported["id"]}/rows?limit=1.0').status_code == 422
    with browser(case.workspace, case.reviewer) as reviewer:
        page = succeeds(reviewer.get("/v2/admin/review-candidates", params=dict(
            dataset_id=case.source["dataset_id"], entry_year=2026, limit=1)))
        tail = succeeds(reviewer.get("/v2/admin/review-candidates", params=dict(
            dataset_id=case.source["dataset_id"], entry_year=2026, limit=1, cursor=page["next_cursor"])))
        assert {page["items"][0]["fact_id"], tail["items"][0]["fact_id"]} == {fact["id"] for fact in case.facts}
        detail = case.detail(reviewer)
        assert "CURRENT_CONFLICTS" in detail["gaps"] and len(detail["conflicts"]) == 1
        invalid = review_request(detail)
        invalid["conflict_resolutions"] = []
        assert reviewer.post("/v2/admin/review-decisions", json=invalid).status_code == 409
        payload = review_request(detail)
    barrier = Barrier(2)
    def run(actor):
        with browser(case.workspace, actor) as client:
            barrier.wait(timeout=10)
            return client.post("/v2/admin/review-decisions", json=payload).status_code
    with ThreadPoolExecutor(2) as executor:
        result = list(executor.map(run, (case.reviewer, case.third)))
    assert sorted(result) == [200, 409]
    with Session(pg_engine) as session:
        decisions = session.scalars(select(ReviewDecision)).all()
        assert len(decisions) == 1 and decisions[0].reviewer_user_id in {case.reviewer.actor.user_id, case.third.actor.user_id}
    with browser(case.workspace, case.reviewer) as client:
        refreshed = case.detail(client)
        assert refreshed["case"]["case_revision"] == 1 and refreshed["case"]["current_approved"]
        assert client.post("/v2/admin/review-decisions", json=payload).status_code == 409


def test_precheck_rejects_manual_only_license_and_withdraw_survives_source_loss(workflow_factory, pg_engine):
    case = workflow_factory()
    with browser(case.workspace, case.reviewer) as client:
        decision = approve(case, client)
        request = case.publish_request([decision])
        published = succeeds(client.post("/v2/admin/releases", json=request, headers={"Idempotency-Key": uuid4().hex}))
        with pg_engine.begin() as connection:
            connection.execute(text("UPDATE catalog_source_versions SET publication_permission='denied' WHERE source_id=:id"),
                {"id": UUID(case.source["source_id"])})
        assert client.post("/v2/admin/releases/precheck", json=case.publish_request([decision],
            replaces_release_id=published["release_id"], expected_replaced_state_revision=1)).status_code == 409
        assert client.get("/v2/admin/releases/" + published["release_id"]).status_code == 409
        current = succeeds(client.get("/v2/admin/releases/current", params={"dataset_id": request["dataset_id"], "entry_year": 2026}))
        assert current["release"]["release_id"] == published["release_id"]
        assert succeeds(client.post(f'/v2/admin/releases/{published["release_id"]}/withdraw', json=dict(
            expected_state_revision=1, reason_code="RIGHTS_REVOKED", confirmed=True)))["state"] == "withdrawn"


def test_review_commit_failure_has_no_decision_or_partial_case(workflow_factory, pg_engine):
    case = workflow_factory()
    with pg_engine.begin() as connection:
        connection.execute(text("CREATE FUNCTION t22_fail_commit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'T22 synthetic commit failure' USING ERRCODE='23514'; END $$"))
        connection.execute(text("CREATE CONSTRAINT TRIGGER t22_commit_failure AFTER INSERT ON review_decisions "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION t22_fail_commit()"))
    with browser(case.workspace, case.reviewer) as client:
        payload = review_request(case.detail(client))
        response = client.post("/v2/admin/review-decisions", json=payload)
        assert response.status_code == 503
        assert "commit failure" not in response.text
        assert case.detail(client)["case"]["case_revision"] == 0
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(ReviewDecision)) == 0


def test_all_writes_require_origin_csrf_and_strong_role(workspace_factory, administrator_factory):
    workspace = workspace_factory()
    with browser(workspace, workspace.admin) as client:
        endpoints = ("/evidence/documents", "/evidence/versions", "/evidence/snippets", "/facts",
                     "/review-decisions", "/releases/precheck", "/releases", f"/releases/{uuid4()}/withdraw")
        for path in endpoints:
            headers = {"Origin": "https://other.test.invalid", "Idempotency-Key": "explicit"}
            assert client.post("/v2/admin" + path, json={}, headers=headers).status_code == 403
            assert client.post("/v2/admin" + path, json={}, headers={"X-CSRF-Token": "x" * 43}).status_code == 403
    for role in ("student", "operations", None):
        actor = administrator_factory(role=role)
        with browser(workspace, actor) as client:
            response = client.get("/v2/admin/review-context")
            assert response.status_code == 403 and response.headers["cache-control"] == "no-store"
    weak = administrator_factory(assurance_age_limit=1)
    with Session(workspace.auth.store.engine) as session, session.begin():
        from services.api.app.auth.models import AuthSession
        session.get(AuthSession, weak.actor.session_id).assurance_acr = "UNTRUSTED_WEAK"
    with browser(workspace, weak) as client:
        assert client.get("/v2/admin/review-context").status_code == 403


def test_existing_t12_date_candidate_is_readable_without_new_date_http(workflow_factory, catalog_tree,
        candidate_factory, classification_factory, pg_engine):
    from services.api.app.admissions_catalog.date_schemas import DateEventInput
    from services.api.app.admissions_catalog.date_store import DateEventStore
    original = "2026-12-01"
    identifier = uuid4()
    def setup(_workspace):
        with Session(pg_engine) as session, session.begin():
            dataset = session.get(CatalogDataset, catalog_tree.dataset.id)
            DateEventStore(pg_engine).create_date_event(session, DateEventInput(id=identifier,
                dataset_id=dataset.id, offering_id=catalog_tree.offering.id, offering_version=1,
                reference_key="DEMO_T22_DATE", is_synthetic=True, entry_year=2026,
                event_type="application_deadline", original_text=original, precision="date",
                local_date=date(2026, 12, 1), local_time=None, timezone=None,
                source_alignment="pending", evidence_reference=None), expected_dataset_revision=dataset.revision)
    raw = candidate_factory(fact_type="date", value_kind="text", value_text=original, unit="ISO_DATE")
    selected = classification_factory(unit_code="ISO_DATE", date_event_id=identifier)
    case = workflow_factory(rows=[raw], classification=selected, setup=setup)
    with browser(case.workspace, case.reviewer) as client:
        detail = case.detail(client)
        assert detail["fact"]["date_resolution"]["conversion_status"] == "date_only"
        assert "UNRESOLVED_DATE" not in detail["gaps"]
        assert succeeds(client.get("/v2/admin/review-candidates", params=dict(dataset_id=case.source["dataset_id"],
            entry_year=2026)))["items"][0]["fact_id"] == detail["fact"]["id"]
    with browser(case.workspace, case.creator) as client:
        unknown_date = succeeds(client.post("/v2/admin/facts", json=dict(import_id=case.imported["id"],
            import_row_id=case.found["rows"][0]["row_id"], evidence_id=case.facts[0]["evidence_id"],
            classification=classification_factory(unit_code="ISO_DATE").model_dump(mode="json"), confirmed=True)))
    with browser(case.workspace, case.reviewer) as client:
        missing = succeeds(client.get("/v2/admin/review-candidates/" + unknown_date["id"]))
        assert "UNRESOLVED_DATE" in missing["gaps"] and missing["fact"]["state"] == "draft"
        assert client.post("/v2/admin/review-decisions", json=review_request(missing)).status_code == 422


def test_final_sql_disabled_policy_cannot_return_derivative(workflow_factory):
    case = workflow_factory()
    facade = case.workspace.app.routes[0].app.state.admin_review_facade
    entered = {"final": False, "disabled": False}
    original = facade._final
    def final(*args, **kwargs):
        entered["final"] = True
        try:
            return original(*args, **kwargs)
        finally:
            entered["final"] = False
    facade._final = final
    def change(_connection, _cursor, statement, _parameters, _context, _executemany):
        if entered["final"] and not entered["disabled"] and "auth_user_roles" in statement.lower():
            entered["disabled"] = True
            case.workspace.reviews.policy = case.workspace.reviews.policy.model_copy(update={"enabled": False})
    event.listen(case.workspace.auth.store.engine, "after_cursor_execute", change)
    try:
        with browser(case.workspace, case.reviewer) as client:
            response = client.get("/v2/admin/review-candidates/" + case.facts[0]["id"])
            assert response.status_code == 503 and entered["disabled"]
            assert case.data.decode("utf-8") not in response.text
    finally:
        event.remove(case.workspace.auth.store.engine, "after_cursor_execute", change)


def test_detail_rechecks_every_conflict_file_after_real_final_sql_wait(workflow_factory,
        candidate_factory, pg_engine, clock):
    selected = workflow_factory(rows=[candidate_factory(value_text="600.00")])
    foreign = workflow_factory(rows=[candidate_factory(value_text="601.00")])
    from services.api.app.storage.models import StorageObject
    with Session(pg_engine) as session, session.begin():
        session.get(StorageObject, UUID(foreign.file["id"])).expires_at = clock() + timedelta(seconds=1)
    facade = selected.workspace.app.routes[0].app.state.admin_review_facade
    original = facade._final
    marker = {"final": False, "pid": None, "blocked": False}
    started = Event()
    key = int(uuid4().hex[:12], 16)
    def final(*args, **kwargs):
        marker["final"] = True
        try:
            return original(*args, **kwargs)
        finally:
            marker["final"] = False
    facade._final = final
    def wait(connection, _cursor, statement, _parameters, _context, _executemany):
        if marker["final"] and not marker["blocked"] and "auth_user_roles" in statement.lower():
            marker["blocked"] = True
            marker["pid"] = connection.scalar(text("SELECT pg_backend_pid()"))
            started.set()
            connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
    with pg_engine.connect() as blocker:
        transaction = blocker.begin()
        blocker.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
        event.listen(pg_engine, "before_cursor_execute", wait)
        try:
            def run():
                with browser(selected.workspace, selected.reviewer) as client:
                    return client.get("/v2/admin/review-candidates/" + selected.facts[0]["id"])
            with ThreadPoolExecutor(1) as executor:
                future = executor.submit(run)
                assert started.wait(20), "Final SQL barrier was not reached"
                deadline = time.monotonic() + 10
                observed = False
                while time.monotonic() < deadline:
                    blockers = blocker.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": marker["pid"]})
                    if blocker_pid in blockers:
                        observed = True
                        break
                    time.sleep(0.02)
                assert observed, "Actual PostgreSQL final query wait was not observed"
                clock.advance(seconds=1)
                transaction.rollback()
                response = future.result(timeout=30)
                assert response.status_code == 409
                assert '"fact"' not in response.text and '"conflicts"' not in response.text
        finally:
            if transaction.is_active:
                transaction.rollback()
            event.remove(pg_engine, "before_cursor_execute", wait)
