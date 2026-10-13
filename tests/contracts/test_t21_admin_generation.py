"""T21 explicit admin export, preserving the three frozen contract profiles."""

from copy import deepcopy
from pathlib import Path
import re
import subprocess
import sys

import pytest

from scripts import generate_contracts as generator


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "packages/contracts/v2/admin"
ADMIN_PATHS = {"/admin/context", "/admin/sources", "/admin/sources/{source_id}",
               "/admin/source-files", "/admin/imports", "/admin/imports/{import_id}"}


def test_admin_artifacts_deterministic_lf_and_old_profiles_unchanged():
    document = generator.load_openapi("admin")
    artifacts = generator.generate_artifacts(document, allow_identity_redirects=True, allow_admin=True)
    assert artifacts == generator.generate_artifacts(generator.load_openapi("admin"),
                                                       allow_identity_redirects=True, allow_admin=True)
    assert not generator.write_or_check(artifacts, OUTPUT, check=True)
    assert document["servers"] == [{"url": "/v2"}]
    assert document["info"]["version"] == "v2.t21"
    assert set(document["paths"]) == set(generator.load_openapi("identity")["paths"]) | ADMIN_PATHS
    assert sum(len(item) for path, item in document["paths"].items() if path in ADMIN_PATHS) == 7
    assert all("\r" not in content for content in artifacts.values())
    assert not re.search(r":\s*(?:any|unknown)(?:[;\[\s]|$)", artifacts["generated.ts"])
    for profile in ("foundation", "identity", "public_catalog"):
        expected = generator.generate_artifacts(generator.load_openapi(profile),
            allow_identity_redirects=profile == "identity", allow_public_catalog=profile == "public_catalog")
        directory = generator.OUTPUT_DIR if profile == "foundation" else generator.OUTPUT_DIR / profile
        assert not generator.write_or_check(expected, directory, check=True)


@pytest.mark.parametrize("mutation", ["no_optin", "no_identity", "missing_uuid", "wrong_uuid", "new_body",
                                     "missing_header", "duplicate_header", "wrong_header"])
def test_admin_export_refuses_unselected_structure(mutation):
    document = deepcopy(generator.load_openapi("admin"))
    operation = document["paths"]["/admin/sources/{source_id}"]["put"]
    if mutation == "missing_uuid":
        operation["parameters"] = []
    elif mutation == "wrong_uuid":
        next(p for p in operation["parameters"] if p["in"] == "path")["name"] = "owner_id"
    elif mutation == "new_body":
        document["paths"]["/admin/execute"] = {"post": deepcopy(operation)}
        document["paths"]["/admin/execute"]["post"]["operationId"] = "executeUnselectedAdmin"
    elif mutation in {"missing_header", "duplicate_header", "wrong_header"}:
        parameters = document["paths"]["/admin/imports"]["post"]["parameters"]
        header = next(p for p in parameters if p["in"] == "header")
        if mutation == "missing_header":
            parameters.remove(header)
        elif mutation == "duplicate_header":
            parameters.append(deepcopy(header))
        else:
            header["name"] = "Authorization"
    with pytest.raises(generator.UnsupportedSchema):
        generator.generate_artifacts(document, allow_identity_redirects=mutation != "no_identity",
                                      allow_admin=mutation != "no_optin")


def test_admin_check_is_readonly_and_detects_drift(tmp_path, monkeypatch):
    monkeypatch.setattr(generator, "OUTPUT_DIR", tmp_path)
    assert generator.main(["--profile", "admin", "--check"]) == 1
    assert not list(tmp_path.iterdir())
    assert generator.main(["--profile", "admin"]) == 0
    file = tmp_path / "admin/generated.ts"
    file.write_bytes(file.read_bytes() + b"// drift\n")
    before = {p.name: p.read_bytes() for p in file.parent.iterdir()}
    assert generator.main(["--profile", "admin", "--check"]) == 1
    assert before == {p.name: p.read_bytes() for p in file.parent.iterdir()}


def test_admin_closed_factory_export_is_offline_without_persistence(tmp_path):
    code = "import sys\nsys.path.insert(0," + repr(str(ROOT)) + ")\n" + """
import os,socket
os.environ.update(V2_APP_ENVIRONMENT='invalid',V2_DATA_MODE='invalid',V2_MODEL_MODE='live',DEMO_MODE='invalid')
def deny(*args,**kwargs): raise AssertionError('external or database connection forbidden')
socket.create_connection=deny
from scripts.generate_contracts import load_openapi,generate_artifacts
from services.api.app.api.admin import create_admin_app
from services.api.app.settings import V2RuntimeSettings
settings=V2RuntimeSettings(app_environment='production',data_mode='verified',model_mode='disabled',database_url=None,legacy_demo_mode=None,_env_file=None)
create_admin_app(settings)
generate_artifacts(load_openapi('admin'),allow_identity_redirects=True,allow_admin=True)
for prefix in ('sqlalchemy','psycopg','alembic','services.api.app.auth.service','services.api.app.storage.local'):
 assert not any(m==prefix or m.startswith(prefix+'.') for m in sys.modules),prefix
print('closed admin and schema export import no persistence')
"""
    (tmp_path / ".env").write_text("V2_MODEL_MODE=live\n", encoding="utf8")
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", code], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
