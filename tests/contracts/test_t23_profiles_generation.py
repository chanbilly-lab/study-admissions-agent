"""T23's independent, bounded profiles wire and frozen previous exporters."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from scripts import generate_contracts as generator
from scripts.verify_contract import Contract, assert_schema_matches

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "packages/contracts/v2/profiles"
KEYS = {"gaokao_total", "chinese", "math", "gaokao_english", "physics", "chemistry",
        "biology", "politics", "history", "geography", "ielts_overall", "ielts_listening",
        "ielts_reading", "ielts_writing", "ielts_speaking"}


def artifacts(document=None, **overrides):
    flags = dict(allow_identity_redirects=True, allow_profiles=True)
    flags.update(overrides)
    return generator.generate_artifacts(document or generator.load_openapi("profiles"), **flags)


def profile_contract(document=None):
    """Reuse the old verifier for actual new declarations and their references.

    The complete identity parent contains numeric privacy-policy literals that
    M0's verifier never supported. Its files stay frozen; the complete generated
    artifact, including those literals, is checked by TypeScript separately.
    """
    document = document or generator.load_openapi("profiles")
    source = artifacts(document)["generated.ts"]
    matches = list(re.finditer(r"export (?:interface|type) ([A-Za-z_$][\w$]*)", source))
    declarations = {match[1]: source[match.start():matches[index + 1].start() if index + 1 < len(matches) else len(source)]
                    for index, match in enumerate(matches)}
    pending = {"GradeSlot", "GradeAssessments", "AssessmentPair", "Budget", "Preferences",
               "ProfileSnapshot", "CreateInput", "AppendInput", "AdaptationData", "ProfileVersionData",
               "ProfileWriteData", "ProfileRef", "ProfilePage", "ProfileContextData"}
    for path, method in generator.PROFILES_OPERATIONS:
        operation = document["paths"][path][method]["operationId"]
        prefix = operation[0].upper() + operation[1:]
        pending |= {name for name in declarations if name.startswith(prefix)}
    selected = set()
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        selected.add(name)
        pending |= set(re.findall(r"\b[A-Za-z_$][\w$]*\b", declarations[name])) & declarations.keys() - selected
    return Contract("\n".join(declarations[name] for name in sorted(selected))), selected


def snapshot():
    known = lambda value: {"status": "known", "value": value}
    empty = {"status": "missing", "value": None, "scale": None, "unit": None}
    return {"study_level": "bachelor", "entry_year": 2027,
            "residence_region": known("HK"), "course_system": known("gaokao"),
            "applicant_category": known("cn_mainland"), "exam_province": known("DEMO_PROVINCE"),
            "pathway": known("gaokao"), "subjects": ["physics"],
            "assessments": {"math": {"achieved": {"status": "provided", "value": "0", "scale": "100", "unit": "points"},
                                      "predicted": empty}}, "weekly_hours": "0", "preferences": None}


def test_profile_is_deterministic_explicit_and_all_five_previous_artifacts_match():
    document = generator.load_openapi("profiles")
    generated = artifacts(document)
    assert generated == artifacts()
    assert not generator.write_or_check(generated, OUTPUT, check=True)
    actual = {(path, method) for path, item in document["paths"].items() for method in item}
    assert actual == generator.PROFILES_OPERATIONS | generator.PROFILES_PARENT_OPERATIONS
    assert len(document["paths"]) == 21
    assert document["servers"] == [{"url": "/v2"}]
    assert document["info"]["version"] == "v2.t23"
    assert "create_profiles_v2_app()" in generated["generated.ts"]
    assert all("\r" not in content for content in generated.values())
    assert not re.search(r":\s*(?:any|unknown)(?:[;\[\s]|$)", generated["generated.ts"])
    for profile in ("foundation", "identity", "public_catalog", "admin", "admin_review"):
        previous = generator.generate_artifacts(generator.load_openapi(profile),
            allow_identity_redirects=profile in {"identity", "admin", "admin_review"},
            allow_public_catalog=profile == "public_catalog", allow_admin=profile in {"admin", "admin_review"},
            allow_admin_review=profile == "admin_review")
        directory = generator.OUTPUT_DIR if profile == "foundation" else generator.OUTPUT_DIR / profile
        assert not generator.write_or_check(previous, directory, check=True)


def test_all_published_components_match_generated_shape_and_nullable_decimals_are_required():
    document = generator.load_openapi("profiles")
    contract, selected = profile_contract(document)
    for name in selected & document["components"]["schemas"].keys():
        assert_schema_matches(contract, name, document["components"]["schemas"][name], document)
    schemas = document["components"]["schemas"]
    for name in ("GradeSlot", "AssessmentPair", "ProfileSnapshot", "ProfileVersionData", "ProfileMeta"):
        assert set(schemas[name]["required"]) == set(schemas[name]["properties"])
        assert schemas[name]["additionalProperties"] is False
    grades = schemas["ProfileSnapshot"]["properties"]["assessments"]
    if "$ref" in grades:
        grades = schemas[grades["$ref"].rsplit("/", 1)[1]]
    assert set(grades["properties"]) == KEYS
    assert not grades.get("required")
    assert grades["additionalProperties"] is False
    assert {part["type"] for part in schemas["GradeSlot"]["properties"]["value"]["anyOf"]} == {"string", "null"}
    assert schemas["CreateInput"]["properties"]["confirmed"]["const"] is True
    assert schemas["AppendInput"]["properties"]["expected_current_version"]["type"] == "integer"
    assert set(schemas["AdaptationData"]["properties"]["status"]["enum"]) == {"unknown", "unsupported"}
    assert schemas["Meta"]["properties"]["profile_version_id"]["type"] == "null"
    assert schemas["Meta"]["properties"]["profile_mode"]["type"] == "null"
    assert {part["type"] for part in schemas["ProfileMeta"]["properties"]["profile_version_id"]["anyOf"]} == {"string", "null"}


def test_local_response_meta_binds_the_actual_version_and_keeps_list_meta_empty():
    from starlette.requests import Request
    from services.api.app.api.profiles import create_profiles_v2_app
    from services.api.app.api.v2.idempotency_canonical import canonical_request_hash
    from services.api.app.profiles.router import _response
    from services.api.app.profiles.schemas import ProfileEnvelope, ProfilePage, ProfileSnapshot, ProfileVersionData, adaptation
    from services.api.app.settings import V2RuntimeSettings
    settings = V2RuntimeSettings(app_environment="test", data_mode="verified", model_mode="disabled",
                                 database_url=None, legacy_demo_mode=None, _env_file=None)
    request = Request({"type": "http", "app": create_profiles_v2_app(settings), "state": {}})
    declared = ProfileSnapshot.model_validate(snapshot())
    now = datetime(2026, 10, 3, tzinfo=timezone.utc)
    version = ProfileVersionData(profile_id=uuid4(), version_id=uuid4(), version=1, profile=declared,
        profile_sha256=canonical_request_hash(declared.model_dump(mode="json")), confirmed_at=now,
        source="student_declared", expires_at=now + timedelta(days=1), is_synthetic=True,
        adaptation=adaptation(declared))
    response = _response(request, version)
    contract, _ = profile_contract()
    contract.assert_payload("GetV2ProfileResponse200", response.model_dump(mode="json"))
    assert response.meta.profile_version_id == version.version_id
    assert response.meta.profile_mode == "synthetic"
    for update in ({"profile_version_id": uuid4()}, {"profile_mode": "real"}):
        forged = response.model_copy(update={"meta": response.meta.model_copy(update=update)})
        with pytest.raises(ValidationError):
            ProfileEnvelope[ProfileVersionData].model_validate(forged)
    listing = _response(request, ProfilePage(items=(), next_cursor=None))
    contract.assert_payload("ListV2ProfilesResponse200", listing.model_dump(mode="json"))
    assert listing.meta.profile_version_id is None and listing.meta.profile_mode is None


def test_actual_runtime_slots_retain_zero_prediction_and_reject_unknown_keys_or_omitted_nulls():
    from services.api.app.profiles.schemas import CreateInput, ProfileSnapshot
    payload = snapshot()
    payload["assessments"]["math"]["predicted"] = {"status": "provided", "value": "87.123456", "scale": "100", "unit": "points"}
    validated = CreateInput.model_validate({"profile": payload, "confirmed": True})
    wire = validated.model_dump(mode="json")
    contract, _ = profile_contract()
    contract.assert_payload("CreateInput", wire)
    assert wire["profile"]["assessments"]["math"]["achieved"]["value"] == "0"
    assert wire["profile"]["weekly_hours"] == "0"
    assert wire["profile"]["residence_region"] != wire["profile"]["exam_province"]
    bad = deepcopy(payload); bad["assessments"]["unknown_subject"] = bad["assessments"]["math"]
    with pytest.raises(ValidationError):
        ProfileSnapshot.model_validate(bad)
    bad = deepcopy(payload); del bad["assessments"]["math"]["predicted"]["unit"]
    with pytest.raises(ValidationError):
        ProfileSnapshot.model_validate(bad)


@pytest.mark.parametrize("mutation", ["no_optin", "no_identity", "admin_mix", "public_mix",
    "extra_get", "new_method", "missing_operation", "missing_body", "optional_body", "extra_media",
    "missing_uuid", "missing_history_uuid", "wrong_uuid", "duplicate_uuid", "missing_header",
    "duplicate_header", "wrong_header", "unbounded_header", "append_header", "extra_query", "extra_get_body"])
def test_refuses_unselected_operations_bodies_paths_or_creation_headers(mutation):
    document = deepcopy(generator.load_openapi("profiles"))
    append = document["paths"]["/profiles/{profile_id}/versions"]["post"]
    create = document["paths"]["/profiles"]["post"]
    history = document["paths"]["/profiles/{profile_id}/versions/{version_id}"]["get"]
    overrides = {}
    if mutation in {"no_optin", "no_identity", "admin_mix", "public_mix"}:
        overrides[{"no_optin": "allow_profiles", "no_identity": "allow_identity_redirects",
                   "admin_mix": "allow_admin", "public_mix": "allow_public_catalog"}[mutation]] = mutation.endswith("mix")
    elif mutation == "extra_get":
        document["paths"]["/profiles/unselected"] = {"get": deepcopy(history)}
    elif mutation == "new_method":
        document["paths"]["/profiles/{profile_id}/versions"] = {"patch": append}
    elif mutation == "missing_operation":
        del document["paths"]["/profiles"]["get"]
    elif mutation == "missing_body":
        append.pop("requestBody")
    elif mutation == "optional_body":
        append["requestBody"]["required"] = False
    elif mutation == "extra_media":
        append["requestBody"]["content"]["text/plain"] = deepcopy(append["requestBody"]["content"]["application/json"])
    elif mutation == "missing_uuid":
        append["parameters"] = []
    elif mutation == "missing_history_uuid":
        history["parameters"] = [item for item in history["parameters"] if item["name"] != "version_id"]
    elif mutation == "wrong_uuid":
        next(item for item in history["parameters"] if item["name"] == "version_id")["schema"]["format"] = "uri"
    elif mutation == "duplicate_uuid":
        history["parameters"].append(deepcopy(history["parameters"][0]))
    elif mutation == "append_header":
        append["parameters"].append(deepcopy(next(item for item in create["parameters"] if item["in"] == "header")))
    elif mutation == "extra_query":
        document["paths"]["/profiles"]["get"]["parameters"].append({"name": "owner_id", "in": "query", "schema": {"type": "string"}})
    elif mutation == "extra_get_body":
        history["requestBody"] = deepcopy(create["requestBody"])
    else:
        parameters = create["parameters"]
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


def test_check_drift_is_read_only_and_does_not_create_missing_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(generator, "OUTPUT_DIR", tmp_path)
    assert generator.main(["--profile", "profiles", "--check"]) == 1
    assert not list(tmp_path.iterdir())
    assert generator.main(["--profile", "profiles"]) == 0
    output = tmp_path / "profiles/generated.ts"
    output.write_bytes(output.read_bytes() + b"// drift\n")
    before = {path.name: path.read_bytes() for path in output.parent.iterdir()}
    assert generator.main(["--profile", "profiles", "--check"]) == 1
    assert before == {path.name: path.read_bytes() for path in output.parent.iterdir()}


def test_fresh_export_and_default_closed_factories_import_no_persistence_jose_or_network(tmp_path):
    code = "import sys\nsys.path.insert(0," + repr(str(ROOT)) + ")\n" + """
import os,socket
os.environ.update(V2_APP_ENVIRONMENT='invalid',V2_DATA_MODE='invalid',V2_MODEL_MODE='live',DEMO_MODE='invalid')
def deny(*args,**kwargs): raise AssertionError('unexpected database/network access')
socket.create_connection=deny
from scripts.generate_contracts import load_openapi,generate_artifacts
from services.api.app.api.profiles import create_profiles_app,create_profiles_v2_app
from services.api.app.settings import V2RuntimeSettings
settings=V2RuntimeSettings(app_environment='production',data_mode='verified',model_mode='disabled',database_url=None,legacy_demo_mode=None,_env_file=None)
parent=create_profiles_app(settings)
child=create_profiles_v2_app(settings)
assert '/v2' in {route.path for route in parent.routes}
assert len(child.openapi()['paths'])==21
generate_artifacts(load_openapi('profiles'),allow_identity_redirects=True,allow_profiles=True)
for prefix in ('sqlalchemy','psycopg','alembic','joserfc','services.api.app.auth.service','services.api.app.storage.local','services.api.app.main'):
 assert not any(name==prefix or name.startswith(prefix+'.') for name in sys.modules),prefix
print('closed profiles factory and exporter have no persistence/JOSE/network imports')
"""
    (tmp_path / ".env").write_text("V2_MODEL_MODE=live\nDATABASE_URL=must-not-open\n", encoding="utf8")
    result = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", code], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_default_closed_http_errors_match_actual_generated_safe_envelope():
    from services.api.app.api.profiles import create_profiles_app, create_profiles_v2_app
    from services.api.app.settings import V2RuntimeSettings
    settings = V2RuntimeSettings(app_environment="test", data_mode="verified", model_mode="disabled",
                                 database_url=None, legacy_demo_mode=None, _env_file=None)
    contract, _ = profile_contract()
    with TestClient(create_profiles_v2_app(settings)) as client:
        response = client.get("/profiles/context")
        assert response.status_code == 503
        contract.assert_payload("GetV2ProfilesContextResponse503", response.json())
        assert response.headers["cache-control"] == "no-store"
        assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])
        assert client.get("/openapi.json").status_code == 200
    with TestClient(create_profiles_app(settings)) as client:
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/docs").status_code == 404
        assert client.get("/v2/openapi.json").status_code == 200
        assert client.get("/v2/profiles/context").status_code == 503
