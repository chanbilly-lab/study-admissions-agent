"""Actual cookie/CSRF/Origin and owner-only notification HTTP boundaries."""
from fastapi.testclient import TestClient
import pytest
from services.api.app.api.notifications import create_notifications_v2_app
from services.api.app.notifications.schemas import MarkReadInput
from services.api.app.privacy.schemas import AgeDeclarationInput,CoreConsentInput
from tests.integration.plan_revisions.test_t35_http import safe,identify
from tests.integration.jobs.test_t36_store import drain

pytestmark=pytest.mark.postgres


def test_real_http_preferences_inbox_read_and_denials(job_case_factory,actor_factory):
    case=job_case_factory(withdraw=True)
    drain(case)
    app=create_notifications_v2_app(case.auth.runtime_settings,identity_service=case.auth,profile_service=case.profiles,
        assessment_service=case.eligibility,execution_service=case.execution,notification_service=case.notifications)
    with TestClient(app,base_url="https://app.test.invalid") as client:
        safe(client.get("/notifications"),401)
        headers=identify(client,case.owner)
        context=safe(client.get("/notifications/context"),200)
        assert context["can_read"] and not context["external_delivery_enabled"]
        preference=safe(client.get("/notifications/preferences"),200)
        assert preference["version"]==1 and preference["enabled"]
        response=client.get("/notifications?limit=1")
        page=safe(response,200)
        assert response.json()["meta"]["profile_version_id"] is None
        item=page["items"][0]
        read_path=f'/notifications/{item["id"]}/read'
        body={"expected_version":1,"student_confirmed":True}
        for proof in ({},{"Origin":headers["Origin"]},{"X-CSRF-Token":headers["X-CSRF-Token"]},
                      {**headers,"Origin":"https://wrong.test.invalid"}):
            safe(client.post(read_path,json=body,headers=proof),403)
        read=safe(client.post(read_path,json=body,headers=headers),200)
        assert read["version"]==2
        assert safe(client.post(read_path,json=body,headers=headers),200)==read
        disabled=safe(client.post("/notifications/preferences",json={"expected_version":1,"enabled":False,"profile_id":None,"student_confirmed":True},headers=headers),200)
        assert disabled["version"]==2 and not disabled["enabled"]
        for payload in ({"expected_version":2,"enabled":0,"profile_id":None,"student_confirmed":True},
                        {"expected_version":True,"enabled":False,"profile_id":None,"student_confirmed":True},
                        {"expected_version":2,"enabled":False,"profile_id":None,"student_confirmed":1},
                        {"expected_version":2,"enabled":False,"profile_id":None,"student_confirmed":True,"owner_user_id":str(case.owner.user_id)}):
            safe(client.post("/notifications/preferences",json=payload,headers=headers),422)
        safe(client.post("/notifications/preferences",content='{"student_confirmed":true,"student_confirmed":false}',headers={**headers,"Content-Type":"application/json"}),422)
        safe(client.post("/notifications/preferences",content='{"extra":"'+"x"*65536+'"}',headers={**headers,"Content-Type":"application/json"}),422)
        safe(client.post(read_path,json=body,headers={**headers,"Idempotency-Key":"DEMO_UNSUPPORTED"}),422)
        safe(client.post(read_path,content="{}",headers={**headers,"Content-Type":"text/plain"}),422)
        for query in ("limit=0","limit=21","limit=true","limit=1&limit=2","owner=foreign","cursor="+"a"*1025):
            safe(client.get("/notifications?"+query),422)
        safe(client.post("/notifications/not-a-uuid/read",json=body,headers=headers),422)
        other=actor_factory()
        principal=case.auth.get_principal(other.cookie)
        privacy=case.profiles.privacy_service
        adult=privacy.declare_age(principal,AgeDeclarationInput(age_band="18_plus",confirmed=True,notice_id=privacy.settings.notice_id,expected_revision=0))
        privacy.confirm_core(principal,CoreConsentInput(purpose="core_consultation",confirmed=True,notice_id=adult.notice_id,expected_revision=adult.revision))
        other_headers=identify(client,other)
        assert safe(client.get("/notifications"),200)["items"]==[]
        safe(client.post(read_path,json=body,headers=other_headers),404)
        admin_headers=identify(client,case.reviewer.actor)
        safe(client.get("/notifications"),403)
        safe(client.post(read_path,json=body,headers=admin_headers),403)
    closed=create_notifications_v2_app(case.auth.runtime_settings,identity_service=case.auth,profile_service=case.profiles,
        assessment_service=case.eligibility,execution_service=case.execution)
    with TestClient(closed,base_url="https://app.test.invalid") as client:
        identify(client,case.owner)
        assert not safe(client.get("/notifications/context"),200)["can_read"]
        safe(client.get("/notifications/preferences"),503)
