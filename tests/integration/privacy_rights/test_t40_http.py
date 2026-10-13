"""Actual HTTP cookie/Origin/CSRF and current-owner checks against real PostgreSQL."""
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import uuid4

from services.api.app.api.rights import create_rights_v2_app
from services.api.app.privacy.rights.models import RightsRequest
from tests.integration.plan_revisions.test_t35_http import identify, safe

pytestmark = pytest.mark.postgres


def test_real_http_closed_input_cookie_security_pending_complete_and_foreign(rights_case_factory, actor_factory, pg_engine):
    case = rights_case_factory()
    app = create_rights_v2_app(case.auth.runtime_settings, identity_service=case.auth, profile_service=case.profiles,
        assessment_service=case.eligibility, execution_service=case.execution, notification_service=case.notifications,
        rights_service=case.rights)
    with TestClient(app, base_url="https://app.test.invalid", follow_redirects=False) as client:
        safe(client.get("/privacy/rights/context"), 401)
        headers = identify(client, case.owner)
        context = safe(client.get("/privacy/rights/context"), 200)
        assert context["enabled"] and not context["real_rights_ready"]
        for proof in ({}, {"Origin": headers["Origin"]}, {"X-CSRF-Token": headers["X-CSRF-Token"]},
            {**headers, "Origin": "https://foreign.test.invalid"}):
            safe(client.post("/privacy/deletions", json={"owner_confirmed": True}, headers=proof), 403)
        for body in ({"owner_confirmed": 1}, {"owner_confirmed": False}, {"owner_confirmed": True, "owner": "DEMO_FOREIGN"},
            {"owner_confirmed": True, "path": "C:/DEMO"}, {"owner_confirmed": True, "resource_ids": []}):
            safe(client.post("/privacy/deletions", json=body, headers=headers), 422)
        for body in ('{"owner_confirmed":true,"owner_confirmed":false}', '{"owner_confirmed":NaN}', '{"extra":"' + "x" * 16385 + '"}'):
            safe(client.post("/privacy/deletions", content=body, headers={**headers, "Content-Type": "application/json"}), 422)
        safe(client.post("/privacy/deletions", json={"owner_confirmed": True}, headers={**headers, "Idempotency-Key": "DEMO"}), 422)
        safe(client.get("/privacy/rights/context?owner=foreign"), 422)
        safe(client.get("/privacy/deletions/not-a-uuid"), 422)
        with Session(pg_engine) as session:
            assert session.scalar(select(RightsRequest).limit(1)) is None
        export = safe(client.post("/privacy/exports", json={"owner_confirmed": True}, headers=headers), 200)
        assert export["status"] == "queued"
        safe(client.get(f'/privacy/exports/{export["request_id"]}/content'), 409)
        case.rights.run(case.rights.claim(uuid4()))
        assert safe(client.get(f'/privacy/exports/{export["request_id"]}/content'), 200)["content_type"] == "application/json"
        other = actor_factory()
        identify(client, other)
        safe(client.get(f'/privacy/exports/{export["request_id"]}'), 404)
        safe(client.get(f'/privacy/exports/{export["request_id"]}/content'), 404)
        headers = identify(client, case.owner)
        deletion = safe(client.post("/privacy/deletions", json={"owner_confirmed": True}, headers=headers), 200)
        assert deletion["status"] == "queued" and not deletion["online_cleanup_complete"]
        assert safe(client.post("/privacy/deletions", json={"owner_confirmed": True}, headers=headers), 200)["request_id"] == deletion["request_id"]
        safe(client.post("/privacy/exports", json={"owner_confirmed": True}, headers=headers), 403)
        safe(client.get(f'/profiles/{case.profile.profile_id}'), 403)
        admission = safe(client.get("/me/admission"), 200)
        assert not admission["core_consultation_allowed"]
        case.rights.run(case.rights.claim(uuid4()))
        completed = safe(client.get(f'/privacy/deletions/{deletion["request_id"]}'), 200)
        assert completed["status"] == "completed" and completed["online_cleanup_complete"]
