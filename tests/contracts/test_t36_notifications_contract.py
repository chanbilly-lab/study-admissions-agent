"""The finite inbox profile cannot add caller authority or unbounded queries."""

from copy import deepcopy
from pathlib import Path
import re
import pytest
from scripts import generate_contracts as generator

FLAGS = dict(allow_identity_redirects=True, allow_profiles=True,
    allow_assessments=True, allow_plans=True, allow_revisions=True, allow_notifications=True)
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def document():
    return generator.load_openapi("notifications")


def test_precise_five_operations_lf_and_frozen_parent_profiles(document):
    parent = generator.load_openapi("revisions")
    operations = {(path, method) for path, item in document["paths"].items() for method in item}
    previous = {(path, method) for path, item in parent["paths"].items() for method in item}
    assert operations - previous == generator.NOTIFICATIONS_OPERATIONS
    assert len(operations - previous) == 5
    assert all(document["paths"][path] == item for path,item in parent["paths"].items())
    artifacts = generator.generate_artifacts(document, **FLAGS)
    assert artifacts == generator.generate_artifacts(generator.load_openapi("notifications"), **FLAGS)
    assert not generator.write_or_check(artifacts, ROOT/"packages/contracts/v2/notifications", check=True)
    assert all("\r" not in value for value in artifacts.values())
    assert not re.search(r":\s*(?:any|unknown)(?:[;\[\s]|$)", artifacts["generated.ts"])


def test_cookie_origin_csrf_and_explicit_student_only_fields(document):
    for name, fields in {
        "PreferenceInput": {"expected_version","enabled","profile_id","student_confirmed"},
        "MarkReadInput": {"expected_version","student_confirmed"},
    }.items():
        schema=document["components"]["schemas"][name]
        assert set(schema["properties"])==set(schema["required"])==fields
        assert schema["additionalProperties"] is False
        assert schema["properties"]["student_confirmed"]["const"] is True
    for path,method in generator.NOTIFICATIONS_OPERATIONS:
        assert document["paths"][path][method]["security"]==[{"SessionCookie":[],**(
            {"CsrfHeader":[],"RequestOrigin":[]} if method=="post" else {})}]


@pytest.mark.parametrize("mutation", ["extra_operation","missing_operation","put","missing_body",
    "caller_owner","unbounded_limit","unbounded_cursor","missing_uuid","idempotency_header","missing_parent"])
def test_finite_profile_rejects_authority_and_query_expansion(document,mutation):
    value=deepcopy(document)
    read=value["paths"]["/notifications/{notification_id}/read"]["post"]
    listing=value["paths"]["/notifications"]["get"]
    if mutation=="extra_operation":
        value["paths"]["/notifications/export"]={"post":deepcopy(read)}
    elif mutation=="missing_operation":
        del value["paths"]["/notifications/context"]
    elif mutation=="put":
        item=value["paths"]["/notifications/preferences"]
        item["put"]=item.pop("post")
    elif mutation=="missing_body":
        del read["requestBody"]
    elif mutation=="caller_owner":
        listing["parameters"].append({"in":"query","name":"owner","schema":{"type":"string"}})
    elif mutation in {"unbounded_limit","unbounded_cursor"}:
        name="limit" if mutation=="unbounded_limit" else "cursor"
        next(item for item in listing["parameters"] if item["name"]==name)["schema"]={"type":"integer" if name=="limit" else "string"}
    elif mutation=="missing_uuid":
        read["parameters"]=[]
    elif mutation=="idempotency_header":
        read["parameters"].append({"in":"header","name":"Idempotency-Key","required":True,"schema":{"type":"string"}})
    flags=FLAGS|({"allow_revisions":False} if mutation=="missing_parent" else {})
    with pytest.raises(generator.UnsupportedSchema):
        generator.generate_artifacts(value,**flags)
