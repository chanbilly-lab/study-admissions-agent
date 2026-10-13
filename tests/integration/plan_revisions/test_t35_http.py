"""Actual cookie/CSRF boundaries reject unsafe revision requests without writes."""

import re

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select,func
from sqlalchemy.orm import Session

from services.api.app.api.revisions import create_revisions_v2_app
from services.api.app.auth.router import SESSION_COOKIE
from services.api.app.plan_revisions.models import RevisionProposal,RevisionDecision,PlanReplacement
from services.api.app.privacy.schemas import AgeDeclarationInput,CoreConsentInput

pytestmark=pytest.mark.postgres
SENTINEL="DEMO_T35_PRIVATE_INPUT_DO_NOT_ECHO"


def safe(response,status):
    assert response.status_code==status,response.text
    assert response.headers["cache-control"]=="no-store"
    assert response.headers["pragma"]=="no-cache"
    assert response.headers["referrer-policy"]=="no-referrer"
    assert re.fullmatch("[0-9a-f]{32}",response.headers["x-request-id"])
    body=response.json()
    identifier=body["meta"]["request_id"] if status==200 else body["error"]["request_id"]
    assert identifier==response.headers["x-request-id"]
    assert SENTINEL not in response.text
    return body.get("data")


def identify(client,actor):
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE,actor.cookie.get_secret_value())
    result=client.get("/auth/csrf")
    assert result.status_code==200
    return {"Origin":"https://app.test.invalid","X-CSRF-Token":result.json()["data"]["csrf_token"]}


def test_http_owner_csrf_and_bounded_closed_json_contract(revision_case_factory,actor_factory,pg_engine):
    case=revision_case_factory()
    app=create_revisions_v2_app(case.auth.runtime_settings,identity_service=case.auth,
        profile_service=case.profiles,assessment_service=case.eligibility,
        execution_service=case.execution,revision_service=case.service)
    with TestClient(app,base_url="https://app.test.invalid",follow_redirects=False) as client:
        safe(client.get(f"/plan-revisions/history/{case.old.plan_id}"),401)
        headers=identify(client,case.owner)
        history=safe(client.get(f"/plan-revisions/history/{case.old.plan_id}"),200)
        assert history["current_actions"] is False and history["completion_refs"]
        payload=case.request.model_dump(mode="json")
        for proof in ({}, {"Origin":headers["Origin"]}, {"X-CSRF-Token":headers["X-CSRF-Token"]},
                      {**headers,"Origin":"https://wrong.test.invalid"}):
            safe(client.post("/plan-revisions",json=payload,headers=proof),403)
        safe(client.post("/plan-revisions",content="{}",headers={**headers,"Content-Type":"text/plain"}),422)
        safe(client.post("/plan-revisions",content='{"student_confirmed":true,"student_confirmed":false}',
            headers={**headers,"Content-Type":"application/json"}),422)
        safe(client.post("/plan-revisions",json={**payload,"student_confirmed":1},headers=headers),422)
        safe(client.post("/plan-revisions",json={**payload,"owner_user_id":SENTINEL},headers=headers),422)
        safe(client.post("/plan-revisions",json=payload,headers={**headers,"Idempotency-Key":SENTINEL}),422)
        safe(client.post("/plan-revisions",content='{"extra":"'+"x"*65536+'"}',
            headers={**headers,"Content-Type":"application/json"}),422)
        safe(client.get(f"/plan-revisions/history/{case.old.plan_id}?owner={SENTINEL}"),422)
        safe(client.get("/plan-revisions/history/not-a-uuid"),422)
        other=actor_factory()
        current=case.auth.get_principal(other.cookie)
        privacy=case.profiles.privacy_service
        adult=privacy.declare_age(current,AgeDeclarationInput(age_band="18_plus",confirmed=True,
            notice_id=privacy.settings.notice_id,expected_revision=0))
        privacy.confirm_core(current,CoreConsentInput(purpose="core_consultation",confirmed=True,
            notice_id=adult.notice_id,expected_revision=adult.revision))
        other_headers=identify(client,other)
        assert client.get("/auth/session").status_code==200
        assert client.get(f"/plan-revisions/history/{case.old.plan_id}").status_code in {403,404}
        assert client.post("/plan-revisions",json=payload,headers=other_headers).status_code in {403,404}
    with Session(pg_engine) as session:
        assert all(session.scalar(select(func.count()).select_from(model))==0
            for model in (RevisionProposal,RevisionDecision,PlanReplacement))
