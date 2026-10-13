"""Pure/default-closed administration contract checks without domain wiring."""

import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from services.api.app.api.admin import create_admin_app, create_admin_v2_app
from services.api.app.admin.http.schemas import AdminImportInput, AdminSourceFileInput
from services.api.app.settings import V2RuntimeSettings


def runtime():
    return V2RuntimeSettings(app_environment="test", data_mode="verified", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None)


@pytest.mark.parametrize("confirmation", [False, 1, 1.0, "true", None])
def test_confirmation_is_not_coerced(confirmation):
    with pytest.raises(ValidationError):
        AdminSourceFileInput(source_id=uuid4(), source_version=1, filename="DEMO.json",
            content_type="application/json", content_utf8='{"DEMO":true}', confirmed=confirmation)


def test_upload_keeps_exact_text_and_rejects_oversized_utf8():
    body = dict(source_id=uuid4(), source_version=1, filename="DEMO.json", content_type="application/json",
                content_utf8='\ufeff{\r\n "DEMO": true\r\n}\r\n', confirmed=True)
    assert AdminSourceFileInput(**body).content_utf8 == body["content_utf8"]
    for value in ("界" * 400000, "\ud800", ""):
        with pytest.raises(ValidationError):
            AdminSourceFileInput(**{**body, "content_utf8": value})


def test_closed_profile_isolated_and_safe():
    app = create_admin_app(runtime())
    with TestClient(app, base_url="https://app.test.invalid", raise_server_exceptions=False) as client:
        assert client.get("/v2/config").status_code == 200
        for method, path in (("GET", "/v2/admin/context"), ("GET", f"/v2/admin/sources/{uuid4()}"),
                             ("POST", "/v2/admin/source-files")):
            response = client.request(method, path, json={"DEMO_SECRET": "never reflect this"})
            assert response.status_code == 503
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["x-request-id"] == response.json()["error"]["request_id"]
            assert "DEMO_SECRET" not in response.text
        assert client.get("/v1/config").status_code == 404
        assert client.get("/v2/admin/reviews").status_code == 404


def test_schema_registers_real_request_contracts_and_security():
    schema = create_admin_v2_app(runtime()).openapi()
    assert len(schema["paths"]) == 22
    assert "responsible_user_id" not in schema["components"]["schemas"]["AdminSourceData"]["properties"]
    assert "dataset_revision" in schema["components"]["schemas"]["AdminSourceData"]["required"]
    assert schema["paths"]["/admin/sources"]["post"]["requestBody"]["required"] is True
    assert schema["paths"]["/admin/source-files"]["post"]["security"] == [
        {"SessionCookie": [], "CsrfHeader": [], "RequestOrigin": []}]
    for name in ("source_id", "import_id"):
        path = "/admin/sources/{source_id}" if name == "source_id" else "/admin/imports/{import_id}"
        assert schema["paths"][path]["get"]["parameters"][0]["schema"]["format"] == "uuid"


def test_default_factory_fresh_process_has_no_database_crypto_or_network():
    script = '''
import sys,socket,logging
from services.api.app.api.admin import create_admin_v2_app
from services.api.app.settings import V2RuntimeSettings
before={n:(l.disabled,tuple(l.handlers)) for n,l in logging.Logger.manager.loggerDict.items() if isinstance(l,logging.Logger)}
socket.socket.connect=lambda *a:(_ for _ in ()).throw(AssertionError('network forbidden'))
app=create_admin_v2_app(V2RuntimeSettings(app_environment='test',data_mode='verified',model_mode='disabled',database_url=None,legacy_demo_mode=None,_env_file=None))
app.openapi()
for prefix in ('sqlalchemy','psycopg','joserfc','cryptography','services.api.app.main','services.api.app.admin.sources.models','services.api.app.admin.imports.models'):
 assert not any(n==prefix or n.startswith(prefix+'.') for n in sys.modules),prefix
assert all((logging.getLogger(n).disabled,tuple(logging.getLogger(n).handlers))==v for n,v in before.items())
print('closed profile safe')
'''
    result = subprocess.run([sys.executable, "-B", "-c", script], cwd=Path(__file__).resolve().parents[3],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "closed profile safe"
