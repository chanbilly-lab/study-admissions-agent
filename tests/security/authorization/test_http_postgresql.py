"""Test-only routes exercise the real BFF dependencies against isolated PG."""

from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field
import pytest


pytestmark = pytest.mark.postgres
KINDS = ("profile", "plan", "attachment", "export", "job")
ORIGIN = "https://app.test.invalid"


def private_response(response):
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    payload = response.json()
    request_id = payload.get("meta", payload.get("error", {}))["request_id"]
    assert request_id == response.headers["x-request-id"]
    return payload


class TouchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(strict=True, ge=1)


def add_test_routes(child):
    from services.api.app.auth.dependencies import authorization_service, current_principal, owned_resource
    from services.api.app.auth.authorization import AuthorizationError
    from services.api.app.api.v2.errors import ApiError
    from services.api.app.api.v2.router import foundation_meta, no_config_query

    def read_endpoint(kind):
        def read(request: Request, resource=Depends(owned_resource(kind))):
            return {"data": {"id": str(resource.id), "owner_user_id": str(resource.owner_user_id)},
                    "meta": foundation_meta(request).model_dump(mode="json")}
        return read

    def list_endpoint(kind):
        def listing(request: Request, principal=Depends(current_principal), auth=Depends(authorization_service)):
            try:
                page = auth.list_owned(principal, kind, limit=2)
            except AuthorizationError as error:
                raise ApiError(error.status_code, error.code) from None
            return {"data": {"ids": [str(row.id) for row in page.items], "total": page.total},
                    "meta": foundation_meta(request).model_dump(mode="json")}
        return listing

    for kind in KINDS:
        child.add_api_route("/probe/" + kind + "/{resource_id}", read_endpoint(kind), methods=["GET"],
                            dependencies=[Depends(current_principal), Depends(no_config_query)])
        child.add_api_route("/probe/" + kind, list_endpoint(kind), methods=["GET"],
                            dependencies=[Depends(current_principal), Depends(no_config_query)])

    @child.post("/probe/profile/{resource_id}/touch", dependencies=[Depends(no_config_query)])
    def touch(resource_id: UUID, body: TouchBody, request: Request,
              principal=Depends(current_principal), auth=Depends(authorization_service)):
        try:
            updated = auth.touch_owned(principal, "profile", resource_id, expected_version=body.expected_version)
        except AuthorizationError as error:
            raise ApiError(error.status_code, error.code) from None
        return {"data": {"version": updated.version}, "meta": foundation_meta(request).model_dump(mode="json")}


@pytest.fixture(params=(False, True), ids=("standalone", "mounted"))
def http(request, auth_service, runtime):
    from services.api.app.api.identity import create_identity_v2_app
    from services.api.app.auth.authorization import Authorizer

    child = create_identity_v2_app(runtime, identity_service=auth_service)
    assert isinstance(child.state.authorization_service, Authorizer)
    add_test_routes(child)
    parent = FastAPI() if request.param else child
    if request.param:
        parent.mount("/v2", child)
    with TestClient(parent, base_url=ORIGIN, follow_redirects=False) as client:
        yield client, "/v2" if request.param else ""


def cookie_header(cookie):
    from services.api.app.auth.router import SESSION_COOKIE

    return {"Cookie": SESSION_COOKIE + "=" + cookie.get_secret_value()}


@pytest.mark.parametrize("kind", KINDS)
def test_two_students_real_http_lists_and_single_objects(
    http, principal_factory, authorizer, kind,
):
    client, prefix = http
    student, cookie = principal_factory()
    foreign_student, foreign_cookie = principal_factory()
    own_parent = authorizer.register_owned(student, "profile")
    foreign_parent = authorizer.register_owned(foreign_student, "profile")
    own = own_parent if kind == "profile" else authorizer.register_owned(student, kind,
        parent_id=None if kind == "plan" else own_parent.id)
    foreign = foreign_parent if kind == "profile" else authorizer.register_owned(foreign_student, kind,
        parent_id=None if kind == "plan" else foreign_parent.id)
    headers = cookie_header(cookie)
    result = client.get(prefix + "/probe/" + kind, headers=headers)
    assert result.status_code == 200
    assert private_response(result)["data"] == {"ids": [str(own.id)], "total": 1}
    assert str(foreign.id) not in result.text and str(foreign_student.user_id) not in result.text
    visible = client.get(prefix + "/probe/" + kind + "/" + str(own.id), headers=headers)
    assert visible.status_code == 200
    assert private_response(visible)["data"]["owner_user_id"] == str(student.user_id)
    foreign_response = client.get(prefix + "/probe/" + kind + "/" + str(foreign.id), headers=headers)
    missing = client.get(prefix + "/probe/" + kind + "/" + str(uuid4()), headers=headers)
    assert foreign_response.status_code == missing.status_code == 404
    foreign_body, missing_body = private_response(foreign_response), private_response(missing)
    assert foreign_body["error"]["code"] == missing_body["error"]["code"] == "NOT_FOUND"
    assert str(foreign.id) not in foreign_response.text and str(foreign_student.user_id) not in foreign_response.text
    reverse = client.get(prefix + "/probe/" + kind + "/" + str(own.id), headers=cookie_header(foreign_cookie))
    assert reverse.status_code == 404
    private_response(reverse)


@pytest.mark.parametrize("roles", ((), ("data_admin",), ("operations",)))
def test_private_http_cannot_use_management_or_client_roles(http, principal_factory, authorizer, roles):
    client, prefix = http
    owner, _ = principal_factory()
    resource = authorizer.register_owned(owner, "profile")
    actor, cookie = principal_factory(roles=roles)
    result = client.get(prefix + "/probe/profile/" + str(resource.id), headers={
        **cookie_header(cookie), "X-Role": "student", "X-Owner-User-ID": str(owner.user_id)})
    assert result.status_code == 403
    private_response(result)
    assert str(owner.user_id) not in result.text and str(actor.user_id) not in result.text
    anonymous = client.get(prefix + "/probe/profile/" + str(resource.id), headers={"X-Role": "student"})
    assert anonymous.status_code == 401
    private_response(anonymous)


def test_pg_http_write_requires_csrf_origin_and_forbids_owner_role(
    http, principal_factory, authorizer, auth_service, pg_engine,
):
    from sqlalchemy.orm import Session
    from services.api.app.auth.models import AuthOwnedResource

    client, prefix = http
    actor, cookie = principal_factory()
    resource = authorizer.register_owned(actor, "profile")
    path = prefix + "/probe/profile/" + str(resource.id) + "/touch"
    token = auth_service.get_csrf_token(cookie).token.get_secret_value()
    good = {**cookie_header(cookie), "X-CSRF-Token": token, "Origin": ORIGIN}
    for headers in (cookie_header(cookie), {**good, "Origin": "https://foreign.test.invalid"}):
        denied = client.post(path, json={"expected_version": 1}, headers=headers)
        assert denied.status_code == 403
        private_response(denied)
    for field in ("owner_user_id", "role", "is_synthetic", "parent_id", "resource_type"):
        extra = client.post(path, json={"expected_version": 1, field: str(uuid4())}, headers=good)
        assert extra.status_code == 422
        private_response(extra)
    query = client.get(prefix + "/probe/profile", params={"owner_user_id": str(uuid4())}, headers=cookie_header(cookie))
    assert query.status_code == 422
    private_response(query)
    with Session(pg_engine) as database:
        assert database.get(AuthOwnedResource, resource.id).version == 1
    accepted = client.post(path, json={"expected_version": 1}, headers=good)
    assert accepted.status_code == 200
    assert private_response(accepted)["data"]["version"] == 2
    stale = client.post(path, json={"expected_version": 1}, headers=good)
    assert stale.status_code == 409
    private_response(stale)


def test_real_factory_schema_keeps_business_and_test_probes_closed(auth_service, runtime):
    from services.api.app.api.identity import create_identity_v2_app

    child = create_identity_v2_app(runtime, identity_service=auth_service)
    paths = set(child.openapi()["paths"])
    assert paths == {"/config", "/offerings", "/auth/login", "/auth/callback",
                     "/auth/session", "/auth/csrf", "/auth/logout", "/privacy/notices/current", "/me/admission",
                     "/me/age-declarations", "/me/consents", "/me/consents/{consent_id}",
        "/sharing/policy", "/access-grants", "/access-grants/{grant_id}", "/access-grants/{grant_id}/accept"}
    with TestClient(child, base_url=ORIGIN) as client:
        assert client.get("/config").json()["data"]["business_available"] is False
        for path in ("/profiles", "/plans", "/attachments", "/exports", "/jobs", "/probe/profile"):
            assert client.get(path).status_code == 404
