"""T22 protocol opt-in and byte-stable existing application profiles."""

from copy import deepcopy
from pathlib import Path
import re
import subprocess
import sys

import pytest

from scripts import generate_contracts as generator

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "packages/contracts/v2/admin_review"
PATHS = {
    "/admin/review-context", "/admin/imports/{import_id}/rows",
    "/admin/evidence/documents", "/admin/evidence/versions", "/admin/evidence/snippets",
    "/admin/facts", "/admin/review-candidates", "/admin/review-candidates/{fact_id}",
    "/admin/review-decisions", "/admin/releases/precheck", "/admin/releases",
    "/admin/releases/current", "/admin/releases/{release_id}",
    "/admin/releases/{release_id}/withdraw",
}


def artifacts(document=None, **overrides):
    flags = dict(allow_identity_redirects=True, allow_admin=True, allow_admin_review=True)
    flags.update(overrides)
    return generator.generate_artifacts(document or generator.load_openapi("admin_review"), **flags)


def test_profile_deterministic_closed_lf_and_existing_artifacts_unchanged():
    document = generator.load_openapi("admin_review")
    generated = artifacts(document)
    assert generated == artifacts()
    assert not generator.write_or_check(generated, OUTPUT, check=True)
    assert set(document["paths"]) == set(generator.load_openapi("admin")["paths"]) | PATHS
    assert document["servers"] == [{"url": "/v2"}]
    assert document["info"]["version"] == "v2.t22"
    assert "create_admin_review_v2_app()" in generated["generated.ts"]
    assert all("\r" not in content for content in generated.values())
    assert not re.search(r":\s*(?:any|unknown)(?:[;\[\s]|$)", generated["generated.ts"])
    for profile in ("foundation", "identity", "public_catalog", "admin"):
        previous = generator.generate_artifacts(generator.load_openapi(profile),
            allow_identity_redirects=profile in {"identity", "admin"},
            allow_public_catalog=profile == "public_catalog", allow_admin=profile == "admin")
        directory = generator.OUTPUT_DIR if profile == "foundation" else generator.OUTPUT_DIR / profile
        assert not generator.write_or_check(previous, directory, check=True)


@pytest.mark.parametrize("mutation", ["no_optin", "no_admin", "no_identity", "extra_get",
    "new_method", "missing_body", "missing_uuid", "wrong_uuid", "missing_header",
    "duplicate_header", "wrong_header", "unbounded_header"])
def test_refuses_unselected_or_incomplete_operations(mutation):
    document = deepcopy(generator.load_openapi("admin_review"))
    operation = document["paths"]["/admin/releases/{release_id}/withdraw"]["post"]
    overrides = {}
    if mutation.startswith("no_"):
        overrides[{"no_optin": "allow_admin_review", "no_admin": "allow_admin",
                   "no_identity": "allow_identity_redirects"}[mutation]] = False
    elif mutation == "extra_get":
        document["paths"]["/admin/unselected"] = {"get": deepcopy(document["paths"]["/admin/review-context"]["get"])}
        document["paths"]["/admin/unselected"]["get"]["operationId"] = "unselectedAdminReviewRead"
    elif mutation == "new_method":
        document["paths"]["/admin/releases/{release_id}/withdraw"] = {"delete": operation}
    elif mutation == "missing_body":
        operation.pop("requestBody")
    elif mutation == "missing_uuid":
        operation["parameters"] = []
    elif mutation == "wrong_uuid":
        next(item for item in operation["parameters"] if item["in"] == "path")["name"] = "owner_id"
    else:
        parameters = document["paths"]["/admin/releases"]["post"]["parameters"]
        header = next(item for item in parameters if item["in"] == "header")
        if mutation == "missing_header":
            parameters.remove(header)
        elif mutation == "duplicate_header":
            parameters.append(deepcopy(header))
        elif mutation == "wrong_header":
            header["name"] = "Authorization"
        else:
            header["schema"].pop("maxLength")
    with pytest.raises(generator.UnsupportedSchema):
        artifacts(document, **overrides)


def test_check_reports_drift_without_partial_rewrite(tmp_path, monkeypatch):
    monkeypatch.setattr(generator, "OUTPUT_DIR", tmp_path)
    assert generator.main(["--profile", "admin_review", "--check"]) == 1
    assert not list(tmp_path.iterdir())
    assert generator.main(["--profile", "admin_review"]) == 0
    file = tmp_path / "admin_review/generated.ts"
    file.write_bytes(file.read_bytes() + b"// drift\n")
    before = {path.name: path.read_bytes() for path in file.parent.iterdir()}
    assert generator.main(["--profile", "admin_review", "--check"]) == 1
    assert before == {path.name: path.read_bytes() for path in file.parent.iterdir()}


def test_schema_export_and_closed_parent_import_no_persistence_or_network(tmp_path):
    code = "import sys\nsys.path.insert(0," + repr(str(ROOT)) + ")\n" + """
import os,socket
os.environ.update(V2_APP_ENVIRONMENT='invalid',V2_DATA_MODE='invalid',V2_MODEL_MODE='live',DEMO_MODE='invalid')
def deny(*args,**kwargs): raise AssertionError('network/database access forbidden')
socket.create_connection=deny
from scripts.generate_contracts import load_openapi,generate_artifacts
from services.api.app.api.admin_review import create_admin_review_app
from services.api.app.settings import V2RuntimeSettings
settings=V2RuntimeSettings(app_environment='production',data_mode='verified',model_mode='disabled',database_url=None,legacy_demo_mode=None,_env_file=None)
parent=create_admin_review_app(settings)
assert {'/v2','/public/v2'}.issubset({route.path for route in parent.routes})
generate_artifacts(load_openapi('admin_review'),allow_identity_redirects=True,allow_admin=True,allow_admin_review=True)
for prefix in ('sqlalchemy','psycopg','alembic','services.api.app.auth.service','services.api.app.storage.local'):
 assert not any(m==prefix or m.startswith(prefix+'.') for m in sys.modules),prefix
print('closed T22 application and protocol export import no persistence')
"""
    (tmp_path / ".env").write_text("V2_MODEL_MODE=live\n", encoding="utf8")
    result = subprocess.run([sys.executable, "-X", "utf8", "-c", code], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
