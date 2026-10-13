"""Real HTTP administrator writes over isolated PostgreSQL and local blobs."""

from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from services.api.app.admin.imports.models import ImportBatch, ImportCandidateRow
from services.api.app.auth.models import AuthSession
from services.api.app.idempotency.models import IdempotencyRecord
from services.api.app.storage.models import StorageObject
from services.api.app.admissions_catalog.models import CatalogDataset
from tests.integration.imports.conftest import serialize_rows

pytestmark = pytest.mark.postgres


def authorized_client(case):
    client = TestClient(case.app, base_url="https://app.test.invalid", raise_server_exceptions=False)
    client.cookies.set("__Host-admissions-session", case.admin.actor.cookie.get_secret_value())
    csrf = client.get("/v2/auth/csrf")
    assert csrf.status_code == 200
    return client, {"Origin": "https://app.test.invalid", "X-CSRF-Token": csrf.json()["data"]["csrf_token"]}


@pytest.mark.parametrize("format", ["json", "csv"])
def test_actual_source_upload_import_and_cas(admin_case_factory, source_request_factory, candidate_factory,
                                            pg_engine, format):
    case = admin_case_factory()
    client, headers = authorized_client(case)
    assert client.get("/v2/admin/context").json()["data"]["can_import"] is True
    request = source_request_factory(definition_updates={"manual_import_permission": "granted",
        "manual_import_enabled": True, "license_basis": "DEMO_T21_PERMISSION",
        "permission_record_reference": "DEMO_T21_RECORD"})
    with Session(pg_engine) as session:
        revision = session.get(CatalogDataset, request.dataset_id).revision
    response = client.post("/v2/admin/sources", headers=headers, json={"source": request.model_dump(mode="json"),
        "expected_dataset_revision": revision, "confirmed": True})
    assert response.status_code == 200, response.text
    source = response.json()["data"]
    assert source["dataset_revision"] == revision + 1
    assert "responsible_user_id" not in source
    assert client.get("/v2/admin/sources/" + str(request.id)).status_code == 200
    assert client.put("/v2/admin/sources/" + str(request.id), headers=headers, json={
        "definition": request.definition.model_dump(mode="json"), "expected_dataset_revision": revision,
        "expected_source_version": 1, "confirmed": True}).status_code == 409
    original = serialize_rows([candidate_factory(), candidate_factory(field_key="second")], format)
    uploaded = client.post("/v2/admin/source-files", headers=headers, json={"source_id": str(request.id),
        "source_version": 1, "filename": "DEMO_T21." + format,
        "content_type": "application/json" if format == "json" else "text/csv",
        "content_utf8": original.decode("utf-8"), "confirmed": True})
    assert uploaded.status_code == 200, uploaded.text
    file = uploaded.json()["data"]
    assert file["size_bytes"] == len(original)
    assert not {"path", "storage_key", "owner_user_id"} & set(file)
    payload = dict(dataset_id=str(request.dataset_id), source_id=str(request.id), source_version=1,
        file_id=file["id"], file_sha256=file["sha256"], format=format, confirmed=True)
    imported = client.post("/v2/admin/imports", headers={**headers, "Idempotency-Key": "DEMO_T21_KEY"}, json=payload)
    assert imported.status_code == 200, imported.text
    result = imported.json()["data"]
    assert result["status"] == "staged" and result["staged_rows"] == 2
    assert client.get("/v2/admin/imports/" + result["id"]).status_code == 200
    replay = client.post("/v2/admin/imports", headers={**headers, "Idempotency-Key": "DEMO_T21_KEY"}, json=payload)
    assert replay.status_code == 200 and replay.json()["data"]["replayed"] is True


def test_student_operations_stale_mfa_and_csrf_direct_http(admin_case_factory, administrator_factory,
                                                        pg_engine, clock):
    case = admin_case_factory()
    client, headers = authorized_client(case)
    for role in ("student", "operations"):
        actor = administrator_factory(role=role)
        client.cookies.set("__Host-admissions-session", actor.actor.cookie.get_secret_value())
        assert client.get("/v2/admin/context").status_code == 403
    client.cookies.set("__Host-admissions-session", case.admin.actor.cookie.get_secret_value())
    for bad in ({}, {**headers, "Origin": "https://foreign.test.invalid"},
                {**headers, "X-CSRF-Token": "A" * 43}):
        response = client.post("/v2/admin/source-files", headers=bad, json={})
        assert response.status_code == 403 and response.headers["cache-control"] == "no-store"
    clock.advance(61)
    assert client.get("/v2/admin/context").status_code == 403
    assert client.post("/v2/admin/source-files", headers=headers, json={}).status_code == 403


def test_safe_bad_rows_and_input_no_success(admin_case_factory, pg_engine):
    case = admin_case_factory(rows=[{"DEMO_PRIVATE_BAD_VALUE": "DEMO_SECRET_NEVER_REFLECT"}])
    client, headers = authorized_client(case)
    for confirmation in (1, 1.0, False):
        payload = {**case.request().model_dump(mode="json"), "confirmed": confirmation}
        assert client.post("/v2/admin/imports", json=payload,
            headers={**headers, "Idempotency-Key": "DEMO_T21_KEY"}).status_code == 422
    payload = {**case.request().model_dump(mode="json"), "confirmed": True}
    response = client.post("/v2/admin/imports", json=payload,
        headers={**headers, "Idempotency-Key": "DEMO_T21_KEY"})
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "rejected" and result["staged_rows"] == 0 and result["errors"]
    assert "DEMO_SECRET_NEVER_REFLECT" not in response.text
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(ImportCandidateRow)) == 0
    extra = client.post("/v2/admin/imports", json={**payload, "owner_user_id": "DEMO_SECRET_NEVER_REFLECT"},
        headers={**headers, "Idempotency-Key": "DEMO_ANOTHER_KEY"})
    assert extra.status_code == 422 and "DEMO_SECRET_NEVER_REFLECT" not in extra.text
    duplicate = client.post("/v2/admin/imports", content='{"confirmed":true,"confirmed":true}',
        headers={**headers, "Content-Type": "application/json", "Idempotency-Key": "DEMO_OTHER"})
    assert duplicate.status_code == 422
    assert client.get("/v2/admin/sources/" + str(case.source.source_id) + "?version=1.0").status_code == 422


@pytest.mark.parametrize("deadline", ["file", "source", "copy_file"])
def test_import_last_auth_sql_wait_expiry_rolls_back_http_write(admin_case_factory, pg_engine,
                                                              clock, monkeypatch, deadline):
    """A real PG advisory blocker at the final role SELECT, after T49 returns.

    The test-only blocker adds I/O at the existing SQL boundary. It neither
    fakes a failed commit nor advances time before current proof is collected.
    """
    case = admin_case_factory(lifetime=172800, assurance_age_limit=86400)
    client, headers = authorized_client(case)
    selected_file = case.file
    baseline = 0
    if deadline == "copy_file":
        from pydantic import SecretStr
        case.service.import_file(case.admin.principal, case.request(), SecretStr("DEMO_T21_ORIGINAL"))
        selected_file = case.upload()
        baseline = 1
    if deadline in {"file", "copy_file"}:
        with Session(pg_engine) as session, session.begin():
            session.get(StorageObject, selected_file.id).expires_at = clock() + timedelta(seconds=1)
    completed, armed, reached = Event(), Event(), Event()
    actual_execute = case.service.idempotency_service.execute
    actual_source = case.storage.source_service.get_source_version
    def execute(*args, **kwargs):
        result = actual_execute(*args, **kwargs)
        completed.set()
        return result
    def source(*args, **kwargs):
        import inspect
        result = actual_source(*args, **kwargs)
        caller = inspect.currentframe().f_back
        if (completed.is_set() and caller.f_code.co_name == "_current_file"
            and caller.f_locals["request"].file_id == case.file.id):
            armed.set()
        return result
    monkeypatch.setattr(case.service.idempotency_service, "execute", execute)
    monkeypatch.setattr(case.storage.source_service, "get_source_version", source)
    lock_key = uuid4().int % (2**63 - 1)
    worker_pid = []
    def barrier(connection, cursor, statement, parameters, context, executemany):
        if (armed.is_set() and not reached.is_set() and "FROM auth_user_roles" in statement
            and "ORDER BY auth_user_roles.role" in statement):
            worker_pid.append(connection.connection.driver_connection.info.backend_pid)
            reached.set()
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))
    payload = {**case.request(selected_file).model_dump(mode="json"), "confirmed": True}
    with pg_engine.connect() as blocker, pg_engine.connect() as observer, ThreadPoolExecutor(max_workers=1) as pool:
        blocker.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_key})
        blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
        event.listen(pg_engine, "before_cursor_execute", barrier)
        future = pool.submit(client.post, "/v2/admin/imports", json=payload,
            headers={**headers, "Idempotency-Key": "DEMO_T21_LATE_EXPIRY"})
        try:
            assert reached.wait(20), "the final SQL boundary was not reached"
            until, waiting = monotonic() + 10, False
            while monotonic() < until:
                observer.commit()
                waiting = observer.scalar(text("SELECT :blocker = ANY(pg_blocking_pids(:worker))"),
                    {"blocker": blocker_pid, "worker": worker_pid[0]})
                if waiting:
                    break
            assert waiting, "no actual PostgreSQL lock wait observed"
            clock.advance(86400 if deadline == "source" else 1)
        finally:
            blocker.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
        try:
            response = future.result(timeout=30)
        finally:
            event.remove(pg_engine, "before_cursor_execute", barrier)
    assert response.status_code == 409, response.text
    with Session(pg_engine) as session:
        for model in (ImportBatch, ImportCandidateRow, IdempotencyRecord):
            assert session.scalar(select(func.count()).select_from(model)) == baseline
