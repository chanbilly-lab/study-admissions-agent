"""Offline query/cursor trust-boundary tests, independent of any database."""

import base64
import json
import socket
import subprocess
import sys
from uuid import UUID, uuid4

from pydantic import ValidationError
import pytest

from services.api.app.public_catalog.query import decode_cursor, encode_cursor, query_fingerprint
from services.api.app.public_catalog.schemas import CoverageData, PublicCatalogError, PublicOfferingQuery


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("T20 unit tests must remain offline")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


def encoded(body):
    raw = body if isinstance(body, str) else json.dumps(body, sort_keys=True, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("ascii")).decode("ascii").rstrip("=")


def cursor_body(query):
    return dict(v=1, q=query_fingerprint(query), w=2, r=str(uuid4()), o=str(uuid4()), n=1)


def test_cursor_round_trip_preserves_exact_scope_and_is_not_a_query_default():
    query = PublicOfferingQuery(entry_year=2026, country="CN", province="known:DEMO_PROVINCE",
        pathway="not_applicable", course_system="known:DEMO_SYSTEM", applicant_category="known:DEMO_CATEGORY",
        release_id=uuid4(), limit=1)
    release, offering = uuid4(), uuid4()
    token = encode_cursor(query, 3, release, offering, 2147483647)
    result = decode_cursor(query.model_copy(update={"cursor": token}), token)
    assert (result.watermark, result.release_id, result.offering_id, result.offering_version) == (3, release, offering, 2147483647)
    assert query_fingerprint(query) == query_fingerprint(query.model_copy(update={"cursor": token}))
    assert len(token) <= 512 and "=" not in token


@pytest.mark.parametrize("changes", [
    {"entry_year": 2027}, {"country": "GB"}, {"study_level": "undergraduate"},
    {"province": "known:DEMO_P"}, {"pathway": "known:DEMO_ROUTE"},
    {"course_system": "not_applicable"}, {"applicant_category": "known:DEMO_CATEGORY"},
    {"release_id": uuid4()}, {"limit": 2},
])
def test_cursor_cannot_be_reused_under_a_different_filter_or_page_size(changes):
    query = PublicOfferingQuery(entry_year=2026, limit=1)
    token = encode_cursor(query, 1, uuid4(), uuid4(), 1)
    with pytest.raises(PublicCatalogError) as caught:
        decode_cursor(query.model_copy(update=changes), token)
    assert caught.value.status_code == 422 and caught.value.code == "INVALID_CURSOR"


@pytest.mark.parametrize("changes", [
    {"entry_year": True}, {"entry_year": 2026.0}, {"entry_year": "2026"}, {"entry_year": 0}, {"entry_year": 10000},
    {"limit": False}, {"limit": "1"}, {"limit": 0}, {"limit": 101},
    {"country": "cn"}, {"country": "CN\n"}, {"province": "unknown"},
    {"pathway": "known:"}, {"course_system": "known:DEMO 系统"},
    {"applicant_category": "known:DEMO_A\n"}, {"owner_user_id": str(uuid4())},
    {"cursor": " "}, {"cursor": "X" * 513},
])
def test_query_refuses_coercion_unknown_scope_and_private_authority_inputs(changes):
    values = {"entry_year": 2026}
    values.update(changes)
    with pytest.raises(ValidationError):
        PublicOfferingQuery.model_validate(values)


def test_year_is_required_and_copy_construct_cannot_bypass_hash_validation():
    with pytest.raises(ValidationError):
        PublicOfferingQuery()
    query = PublicOfferingQuery(entry_year=2026)
    for forged in (query.model_copy(update={"limit": True}), PublicOfferingQuery.model_construct(entry_year=2026, province="unknown")):
        with pytest.raises(PublicCatalogError) as caught:
            query_fingerprint(forged)
        assert caught.value.status_code == 422


@pytest.mark.parametrize("mutation", [
    {"v": True}, {"v": 2}, {"w": True}, {"w": -1}, {"w": 9007199254740992},
    {"n": True}, {"n": 0}, {"n": 2147483648}, {"q": "0" * 64},
    {"r": "00000000000000000000000000000001"}, {"o": "DEMO_PRIVATE_CURSOR_SENTINEL"},
    {"extra": "DEMO_PRIVATE_CURSOR_SENTINEL"},
])
def test_cursor_payload_fields_are_closed_canonical_and_strict(mutation):
    query = PublicOfferingQuery(entry_year=2026)
    body = cursor_body(query)
    body.update(mutation)
    with pytest.raises(PublicCatalogError) as caught:
        decode_cursor(query, encoded(body))
    assert caught.value.code == "INVALID_CURSOR"
    assert "DEMO_PRIVATE_CURSOR_SENTINEL" not in str(caught.value) + repr(caught.value)


def test_cursor_rejects_duplicate_json_keys_alternate_base64_and_wrong_json_shape():
    query = PublicOfferingQuery(entry_year=2026)
    body = cursor_body(query)
    valid = encoded(body)
    duplicate = json.dumps(body)[:-1] + ',"w":2}'
    for token in (encoded(duplicate), encoded([]), valid + "=", valid + "\n", "_", "\ud800"):
        with pytest.raises(PublicCatalogError) as caught:
            decode_cursor(query, token)
        assert caught.value.status_code == 422 and caught.value.code == "INVALID_CURSOR"


def test_semantically_equal_construction_has_identical_hash_but_case_is_preserved():
    first = PublicOfferingQuery(entry_year=2026, country="CN", province="known:DEMO_A", release_id=UUID(int=1))
    same = PublicOfferingQuery.model_validate({"country": "CN", "province": "known:DEMO_A",
        "release_id": "00000000-0000-0000-0000-000000000001", "entry_year": 2026})
    assert query_fingerprint(first) == query_fingerprint(same)
    assert query_fingerprint(first) != query_fingerprint(first.model_copy(update={"province": "known:demo_a"}))


def test_empty_cursor_page_does_not_assert_that_the_query_scope_has_no_records():
    assert CoverageData(status="partial", returned_count=0, expected_total=None, coverage_ratio=None).returned_count == 0
    assert CoverageData(status="no_published_records", returned_count=0, expected_total=None, coverage_ratio=None).expected_total is None
    with pytest.raises(ValidationError):
        CoverageData(status="no_published_records", returned_count=1, expected_total=None, coverage_ratio=None)


def test_closed_factory_can_serve_no_key_config_without_database_identity_model_or_external_network():
    code = r'''
import importlib.abc
import socket
import sys
from fastapi.testclient import TestClient
class Blocked(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(("sqlalchemy", "services.api.app.auth", "services.api.app.database", "services.api.app.providers")) or fullname == "services.api.app.main" or (fullname.startswith("services.api.app.") and fullname.endswith(".models")):
            raise AssertionError("closed public factory imported a business dependency")
sys.meta_path.insert(0, Blocked())
for method in ("connect", "connect_ex"):
    original = getattr(socket.socket, method)
    def guarded(sock, address, original=original):
        # Windows asyncio creates its self-pipe through a loopback socketpair.
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original(sock, address)
        raise AssertionError("closed public factory attempted external network")
    setattr(socket.socket, method, guarded)
def no_dns(*args, **kwargs):
    raise AssertionError("closed public factory attempted DNS")
socket.getaddrinfo = no_dns
from services.api.app.settings import V2RuntimeSettings
from services.api.app.api.public_catalog import create_public_catalog_app
settings = V2RuntimeSettings(app_environment="production", data_mode="verified", model_mode="disabled", database_url=None, legacy_demo_mode=None, _env_file=None)
app = create_public_catalog_app(settings)
with TestClient(app) as client:
    config = client.get("/v2/config")
    assert config.status_code == 200 and config.json()["data"]["business_available"] is False
    assert config.json()["data"]["entry_year"] is None and config.json()["data"]["allow_test_fixture_read"] is False
    for path in ("/v2/offerings?entry_year=2026", "/v2/evidence/00000000-0000-0000-0000-000000000001?release_id=00000000-0000-0000-0000-000000000002"):
        response = client.get(path)
        assert response.status_code == 503 and response.headers["Cache-Control"] == "no-store"
        assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    for path in ("/v1", "/v2/openapi.json"):
        response = client.get(path)
        assert response.status_code == 404 and response.headers["Cache-Control"] == "no-store"
print("closed no-database factory verified")
'''
    result = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "closed no-database factory verified" in result.stdout
