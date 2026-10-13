"""T22 HTTP-only conversion and closed opt-in surface."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from services.api.app.admin.review_http.schemas import AdminDocumentInput, AdminPublishInput
from services.api.app.api.admin_review import create_admin_review_app, create_admin_review_v2_app
from services.api.app.settings import V2RuntimeSettings


def publish_input(**updates):
    values = dict(dataset_id=str(uuid4()), expected_dataset_revision=1, entry_year=2026,
        kind="test_fixture", valid_from="2026-10-03T01:00:00Z", valid_until="2026-10-03T02:00:00+00:00",
        members=[dict(fact_id=str(uuid4()), expected_case_revision=1,
            expected_decision_id=str(uuid4()), public_evidence=True)], replaces_release_id=None,
        expected_replaced_state_revision=None, confirmed=True)
    values.update(updates)
    return values


@pytest.mark.parametrize("instant", ["2026-10-03T00:00:00+00:99", "2026-10-03T00:00:00+24:00",
    "2026-10-03T00:00:00-00:00", "2026-10-03T00:00:00", 1790989200, "1790989200", True])
def test_http_instant_requires_explicit_valid_offset(instant):
    with pytest.raises(ValidationError):
        AdminPublishInput.model_validate(publish_input(valid_from=instant))


def test_http_offset_converts_to_native_utc_without_weakening_internal_contract():
    actual = AdminPublishInput.model_validate(publish_input(valid_from="2026-10-03T09:00:00+08:00"))
    assert actual.valid_from == datetime(2026, 10, 3, 1, tzinfo=timezone.utc)
    from services.api.app.releases.schemas import PublishRequest
    with pytest.raises(ValidationError):
        PublishRequest.model_validate({name: value for name, value in publish_input().items() if name != "confirmed"})


@pytest.mark.parametrize("confirmation", [1, 1.0, "true", False])
def test_preparation_requires_literal_human_confirmation(confirmation):
    with pytest.raises(ValidationError):
        AdminDocumentInput.model_validate(dict(dataset_id=str(uuid4()), source_id=str(uuid4()),
            source_version=1, document_reference="DEMO_EXPLICIT", language="und", confirmed=confirmation))


def test_closed_profile_keeps_original_routes_and_public_config_closed():
    settings = V2RuntimeSettings(app_environment="test", data_mode="verified", model_mode="disabled",
        database_url=None, legacy_demo_mode=None, _env_file=None)
    child = create_admin_review_v2_app(settings)
    assert child.version == "v2.t22" and len(child.openapi()["paths"]) == 36
    assert child.state.admin_review_facade is None
    with TestClient(create_admin_review_app(settings), raise_server_exceptions=False) as client:
        response = client.get("/v2/admin/review-context")
        assert response.status_code == 503 and response.headers["cache-control"] == "no-store"
        public = client.get("/public/v2/config")
        assert public.status_code == 200 and public.json()["data"]["business_available"] is False
        assert client.get("/public/v2/offerings?entry_year=2026").status_code == 503
        assert client.get("/v1/projects").status_code == 404
