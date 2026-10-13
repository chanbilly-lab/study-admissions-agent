"""Independent T09 sharing attacks; synthetic input and no external services."""

from datetime import date, datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from threading import Event
from time import monotonic
from uuid import UUID, uuid4

from pydantic import ValidationError
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from services.api.app.auth.grants.policy import POLICY_HASH, POLICY_VERSION, sharing_policy
from services.api.app.auth.grants.schemas import AcceptGrantInput, CreateGrantInput, SharingSettings
from services.api.app.auth.grants.service import SharingError, SharingService
from services.api.app.auth.grants.models import AccessGrant
from services.api.app.auth.models import AuthOwnedResource, AuthUser, AuthUserRole
from services.api.app.auth.authorization import Authorizer
from services.api.app.auth.config import AuthFlowError
from services.api.app.auth.router import SESSION_COOKIE
from services.api.app.privacy.models import PrivacyNoticeVersion
from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput
from services.api.app.privacy.service import PrivacyService
from services.api.app.privacy.policy import hash_text


PRIVATE_MARKER = "T09_PRIVATE_CONVERSATION_SENTINEL"
RESOURCE_ID = UUID("cb3ffb53-1ea6-4269-8eec-234c49fcf318")
RECIPIENT_ID = UUID("28ed3d2f-aea0-4c58-8253-dedab9eac622")
CONSENT_ID = UUID("6f058ccd-37d1-4c2b-b72c-130f829d718b")


def create_payload():
    return dict(resource_type="profile", resource_id=str(RESOURCE_ID), expected_resource_version=1,
        grantee_user_id=str(RECIPIENT_ID), fields=["status"], actions=["read"],
        expires_at="2026-10-04T12:00:00+08:00", confirmed=True, expected_revision=0,
        owner_consent_id=str(CONSENT_ID), sharing_policy_version=POLICY_VERSION,
        sharing_policy_hash=POLICY_HASH)


def accept_payload():
    return dict(confirmed=True, expected_version=1,
        sharing_policy_version=POLICY_VERSION, sharing_policy_hash=POLICY_HASH)


@pytest.mark.parametrize("model,payload", [(CreateGrantInput, create_payload), (AcceptGrantInput, accept_payload)])
@pytest.mark.parametrize("value", [1, 1.0, 0, False, None, "true", "True", [], {}])
def test_each_independent_confirmation_is_boolean_true(model, payload, value):
    with pytest.raises(ValidationError):
        model.model_validate({**payload(), "confirmed": value})


@pytest.mark.parametrize("model,payload", [(CreateGrantInput, create_payload), (AcceptGrantInput, accept_payload)])
@pytest.mark.parametrize("field", ["owner_user_id", "actor_user_id", "role", "verified",
    "is_synthetic", "guardian_verified", "grantee_declaration_id", "production_reviewed"])
def test_request_cannot_supply_server_identity_or_cross_subject_proof(model, payload, field):
    with pytest.raises(ValidationError) as denied:
        model.model_validate({**payload(), field: PRIVATE_MARKER})
    assert PRIVATE_MARKER not in str(denied.value)
    assert PRIVATE_MARKER not in repr(denied.value)


@pytest.mark.parametrize("fields", [[], ["status", "status"], ["version", "version"],
    ["status", "version", "status"], ["*"], ["conversation"], ["conversation.text"],
    ["owner_user_id"], ["parent_id"], ["payload"], ["private_chat"], ["__proto__"]])
def test_scope_cannot_expand_from_metadata_to_student_content(fields):
    with pytest.raises(ValidationError):
        CreateGrantInput.model_validate({**create_payload(), "fields": fields})


@pytest.mark.parametrize("actions", [[], ["read", "read"], ["list", "list"],
    ["read", "list", "read"], ["*"], ["download"], ["export"], ["write"],
    ["execute"], ["confirm"], ["accept"], ["share"]])
def test_grant_never_creates_file_mutation_or_execution_permission(actions):
    with pytest.raises(ValidationError):
        CreateGrantInput.model_validate({**create_payload(), "actions": actions})


@pytest.mark.parametrize("kind", ["conversation", "assessment", "user", "*", "PROFILE"])
def test_resource_types_are_closed(kind):
    with pytest.raises(ValidationError):
        CreateGrantInput.model_validate({**create_payload(), "resource_type": kind})


@pytest.mark.parametrize("model,payload,field", [
    (CreateGrantInput, create_payload, "expected_revision"),
    (CreateGrantInput, create_payload, "expected_resource_version"),
    (AcceptGrantInput, accept_payload, "expected_version"),
])
@pytest.mark.parametrize("value", [True, False, "1", 1.0, -1])
def test_versions_are_integer_positive_write_proofs(model, payload, field, value):
    with pytest.raises(ValidationError):
        model.model_validate({**payload(), field: value})


@pytest.mark.parametrize("model,payload", [(CreateGrantInput, create_payload), (AcceptGrantInput, accept_payload)])
@pytest.mark.parametrize("digest", ["a" * 63, "a" * 65, "A" * 64, "z" * 64, "a" * 64 + "\n"])
def test_policy_hash_has_exact_lowercase_sha256_shape(model, payload, digest):
    with pytest.raises(ValidationError):
        model.model_validate({**payload(), "sharing_policy_hash": digest})


@pytest.mark.parametrize("value", [1791000000, 1791000000.0, "1791000000", True,
    "2026-10-03", "2026-10-03T10:00:00", date(2026, 10, 3), datetime(2026, 10, 3), [], {}])
def test_expiry_requires_explicit_date_time_offset_not_coercible_timestamp(value):
    with pytest.raises(ValidationError):
        CreateGrantInput.model_validate({**create_payload(), "expires_at": value})


def test_explicit_offset_is_preserved_as_the_same_instant_and_policy_hash_uses_actual_text():
    request = CreateGrantInput.model_validate(create_payload())
    assert request.expires_at == datetime(2026, 10, 4, 4, tzinfo=timezone.utc)
    request_z = CreateGrantInput.model_validate({**create_payload(), "expires_at": "2026-10-04T04:00:00Z"})
    assert request_z.expires_at == request.expires_at
    policy = sharing_policy()
    assert sha256(policy.text.encode("utf-8")).hexdigest() == policy.text_sha256 == POLICY_HASH
    assert policy.sharing_available is False
    assert policy.private_business_available is False
    assert policy.guardian_verification_available is False


@pytest.mark.parametrize("model,payload,changes", [
    (CreateGrantInput, create_payload, {"confirmed": 1}),
    (CreateGrantInput, create_payload, {"fields": ["conversation"]}),
    (CreateGrantInput, create_payload, {"actions": ["execute"]}),
    (CreateGrantInput, create_payload, {"expected_resource_version": True}),
    (AcceptGrantInput, accept_payload, {"confirmed": 1}),
    (AcceptGrantInput, accept_payload, {"expected_version": True}),
])
@pytest.mark.parametrize("forgery", ["copy", "construct"])
def test_forged_model_instances_do_not_bypass_wire_validation(model, payload, changes, forgery):
    valid = model.model_validate(payload())
    forged = valid.model_copy(update=changes) if forgery == "copy" else model.model_construct(
        **{**valid.model_dump(), **changes})
    with pytest.raises(ValidationError):
        model.model_validate(forged)


@pytest.mark.parametrize("value", [1, 1.0, "true", None])
def test_fixture_configuration_is_explicit_boolean(value):
    with pytest.raises(ValidationError):
        SharingSettings(fixture_mode=value)


def test_configuration_is_frozen_and_environment_cannot_enable_real_or_fixture_sharing(monkeypatch):
    for name in ("SHARING_FIXTURE_MODE", "V2_SHARING_FIXTURE_MODE", "SHARING_PRODUCTION_REVIEWED"):
        monkeypatch.setenv(name, "true")
    configuration = SharingSettings()
    assert configuration.fixture_mode is False
    with pytest.raises(ValidationError):
        configuration.fixture_mode = True
    with pytest.raises(ValidationError):
        SharingSettings(production_reviewed=True)


def principal(service, actor):
    return service.auth_service.get_principal(actor.cookie)


def accept(service, actor, grant):
    return service.accept_grant(principal(service, actor), grant.id,
        AcceptGrantInput(confirmed=True, expected_version=grant.version,
            sharing_policy_version=POLICY_VERSION, sharing_policy_hash=POLICY_HASH))


def read(service, recipient, resource, fields=("status",), action="read"):
    return service.require_shared(principal(service, recipient), resource.resource_type, resource.id, fields, action)


def denied(call, statuses=(403, 404)):
    with pytest.raises(AuthFlowError) as error:
        call()
    assert error.value.status_code in statuses
    assert PRIVATE_MARKER not in str(error.value)
    assert PRIVATE_MARKER not in repr(error.value)


def redeclare(privacy, service, actor):
    current = privacy.get_admission(principal(service, actor))
    return privacy.declare_age(principal(service, actor), AgeDeclarationInput(age_band="18_plus", confirmed=True,
        notice_id=current.notice_id, expected_revision=current.revision))


def reconfirm(privacy, service, actor):
    current = privacy.get_admission(principal(service, actor))
    return privacy.confirm_core(principal(service, actor), CoreConsentInput(purpose="core_consultation", confirmed=True,
        notice_id=current.notice_id, expected_revision=current.revision))


@pytest.mark.postgres
@pytest.mark.parametrize("kind", ["profile", "plan", "attachment", "export", "job"])
def test_each_kind_only_reveals_explicit_metadata_to_roleless_adult(sharing_service, admitted_actor_factory,
        resource_factory, accepted_grant_factory, privacy_service, pg_engine, kind):
    owner = admitted_actor_factory()
    recipient = admitted_actor_factory(role=None)
    resource = resource_factory(owner, kind)
    _, _, _, grant = accepted_grant_factory(owner, recipient, resource, fields=["status"])
    projected = read(sharing_service, recipient, resource)
    assert projected.model_dump() == dict(resource_id=resource.id, resource_type=kind, is_synthetic=True,
        requested_fields=("status",), status="active", version=None)
    assert grant.access_active is True
    assert privacy_service.get_admission(principal(sharing_service, recipient)).consent_id is None
    with Session(pg_engine) as session:
        assert session.scalars(select(AuthUserRole).where(AuthUserRole.user_id == recipient.user_id)).all() == []
    denied(lambda: read(sharing_service, recipient, resource, ("version",)))
    child = resource_factory(owner, "attachment")
    denied(lambda: read(sharing_service, recipient, child))


@pytest.mark.postgres
@pytest.mark.parametrize("action", ["download", "write", "export", "execute", "confirm"])
def test_no_grant_authorizes_forbidden_action_or_invokes_delayed_operation(sharing_service, accepted_grant_factory, action):
    _, recipient, resource, _ = accepted_grant_factory()
    invoked = []
    denied(lambda: sharing_service.execute_shared(principal(sharing_service, recipient), resource.resource_type,
        resource.id, ("status",), lambda *args: invoked.append(True), action), (403,))
    assert invoked == []


@pytest.mark.postgres
def test_owner_core_reconfirmation_never_revives_old_grant(sharing_service, accepted_grant_factory, privacy_service):
    owner, recipient, resource, grant = accepted_grant_factory()
    before = privacy_service.get_admission(principal(sharing_service, owner))
    privacy_service.withdraw_core(principal(sharing_service, owner), before.consent_id)
    denied(lambda: read(sharing_service, recipient, resource))
    current = reconfirm(privacy_service, sharing_service, owner)
    assert current.consent_id != before.consent_id
    denied(lambda: read(sharing_service, recipient, resource))
    received = sharing_service.list_grants(principal(sharing_service, recipient), "received")
    assert received.items[0].id == grant.id and received.items[0].access_active is False
    assert sharing_service.list_shared(principal(sharing_service, recipient), "profile", ("status",)).total == 0


@pytest.mark.postgres
@pytest.mark.parametrize("accepted", [False, True])
def test_receiver_age_reset_never_rebinds_old_pending_or_accepted_grant(sharing_service, admitted_actor_factory,
        resource_factory, create_request_factory, privacy_service, accepted):
    owner, recipient = admitted_actor_factory(), admitted_actor_factory(role=None)
    resource = resource_factory(owner)
    grant = sharing_service.create_grant(principal(sharing_service, owner),
        create_request_factory(owner, recipient, resource)).grant
    if accepted:
        grant = accept(sharing_service, recipient, grant).grant
    current = privacy_service.get_admission(principal(sharing_service, recipient))
    denied(lambda: privacy_service.declare_age(principal(sharing_service, recipient),
        AgeDeclarationInput(age_band="unknown", confirmed=True, notice_id=current.notice_id,
            expected_revision=current.revision)), (403,))
    redeclare(privacy_service, sharing_service, recipient)
    denied(lambda: accept(sharing_service, recipient, grant))
    denied(lambda: read(sharing_service, recipient, resource))
    assert sharing_service.list_shared(principal(sharing_service, recipient), "profile", ("status",)).total == 0


@pytest.mark.postgres
def test_new_notice_and_fresh_confirmations_do_not_rebind_previous_grant(sharing_service, accepted_grant_factory,
        privacy_service, privacy_settings, clock, pg_engine):
    owner, recipient, resource, _ = accepted_grant_factory()
    old = privacy_service.current_notice()
    next_id = uuid4()
    next_text = old.text + "\nT09 synthetic revised notice"
    with Session(pg_engine) as session, session.begin():
        session.add(PrivacyNoticeVersion(id=next_id, version="T09_SYNTHETIC_NOTICE_v2",
            policy_version=privacy_settings.policy_version, text=next_text, text_sha256=hash_text(next_text),
            controller_reference=privacy_settings.controller_reference, review_status="test_reviewed",
            reviewed_at=clock(), is_synthetic=True))
    fresh_privacy = PrivacyService(sharing_service.auth_service, privacy_settings.model_copy(update={"notice_id": next_id}))
    fresh = SharingService(sharing_service.auth_service, fresh_privacy, sharing_service.settings)
    denied(lambda: read(fresh, recipient, resource))
    redeclare(fresh_privacy, fresh, owner)
    reconfirm(fresh_privacy, fresh, owner)
    redeclare(fresh_privacy, fresh, recipient)
    denied(lambda: read(fresh, recipient, resource))
    assert fresh.list_shared(principal(fresh, recipient), "profile", ("status",)).total == 0


@pytest.mark.postgres
@pytest.mark.parametrize("change", ["resource_version", "parent_deleted", "owner_role", "owner_status"])
def test_current_object_parent_owner_and_role_revalidated(sharing_service, accepted_grant_factory,
        admitted_actor_factory, resource_factory, pg_engine, clock, change):
    owner = admitted_actor_factory()
    resource = resource_factory(owner, "attachment" if change == "parent_deleted" else "profile")
    _, recipient, _, _ = accepted_grant_factory(owner=owner, resource=resource)
    if change == "owner_role":
        sharing_service.auth_service.store.revoke_role(owner.user_id, "student", now=clock())
    else:
        with Session(pg_engine) as session, session.begin():
            if change == "owner_status":
                session.get(AuthUser, owner.user_id).status = "disabled"
            elif change == "parent_deleted":
                session.get(AuthOwnedResource, resource.parent_id).status = "deleted"
            else:
                session.get(AuthOwnedResource, resource.id).version += 1
    denied(lambda: read(sharing_service, recipient, resource))
    assert sharing_service.list_shared(principal(sharing_service, recipient), resource.resource_type, ("status",)).total == 0


@pytest.mark.postgres
def test_sql_scope_filters_before_total_and_page_and_deduplicates_resources(sharing_service, admitted_actor_factory,
        accepted_grant_factory, resource_factory, create_request_factory, pg_engine, clock):
    owner, recipient = admitted_actor_factory(), admitted_actor_factory(role=None)
    authorizer = Authorizer(sharing_service.auth_service)
    resources = [authorizer.register_owned(principal(sharing_service, owner), "profile", resource_id=UUID(int=i))
        for i in range(1, 7)]
    grants = []
    for resource in resources:
        grants.append(accepted_grant_factory(owner, recipient, resource)[3])
    # Earliest UUIDs are excluded by expiry, revocation and field/action scope.
    with Session(pg_engine) as session, session.begin():
        session.get(AccessGrant, grants[0].id).expires_at = clock() + timedelta(seconds=1)
    clock.advance(1)
    sharing_service.revoke_grant(principal(sharing_service, owner), grants[1].id)
    sharing_service.revoke_grant(principal(sharing_service, owner), grants[2].id)
    accepted_grant_factory(owner, recipient, resources[2], fields=["version"], actions=["read"])
    # Multiple independently accepted grants do not inflate total/page objects.
    accepted_grant_factory(owner, recipient, resources[3])
    current = principal(sharing_service, recipient)
    first = sharing_service.list_shared(current, "profile", ("status",), limit=1)
    second = sharing_service.list_shared(current, "profile", ("status",), limit=1, after_id=first.next_cursor)
    third = sharing_service.list_shared(current, "profile", ("status",), limit=1, after_id=second.next_cursor)
    assert [item.resource_id for page in [first, second, third] for item in page.items] == [r.id for r in resources[3:]]
    assert [page.total for page in [first, second, third]] == [3, 3, 3]
    assert first.next_cursor == resources[3].id and second.next_cursor == resources[4].id and third.next_cursor is None


@pytest.mark.postgres
def test_separate_grants_cannot_union_fields_to_expand_one_scope(sharing_service, accepted_grant_factory,
        admitted_actor_factory, resource_factory):
    owner, recipient = admitted_actor_factory(), admitted_actor_factory(role=None)
    resource = resource_factory(owner)
    accepted_grant_factory(owner, recipient, resource, fields=["status"])
    accepted_grant_factory(owner, recipient, resource, fields=["version"])
    assert read(sharing_service, recipient, resource, ("status",)).status == "active"
    assert read(sharing_service, recipient, resource, ("version",)).version == 1
    denied(lambda: read(sharing_service, recipient, resource, ("status", "version")))
    assert sharing_service.list_shared(principal(sharing_service, recipient), "profile", ("status", "version")).total == 0


@pytest.mark.postgres
def test_cached_mapping_cannot_inject_private_payload_and_revoke_precedes_cache_lookup(sharing_service,
        accepted_grant_factory):
    owner, recipient, resource, grant = accepted_grant_factory()
    current = principal(sharing_service, recipient)
    key = sharing_service.cache_key(current, "profile", resource.id, ("status",))
    projection = read(sharing_service, recipient, resource)
    assert sharing_service.cached_value(current, "profile", resource.id, ("status",), {key: projection}) == projection
    for bad in [{**projection.model_dump(), "conversation": PRIVATE_MARKER},
                {**projection.model_dump(), "resource_id": uuid4()},
                {**projection.model_dump(), "status": "deleted"}]:
        assert sharing_service.cached_value(current, "profile", resource.id, ("status",), {key: bad}) is None
    sharing_service.revoke_grant(principal(sharing_service, owner), grant.id)
    calls = []
    class BombCache(dict):
        def get(self, *args):
            calls.append(True)
            raise AssertionError("must not read cache after revocation")
    denied(lambda: sharing_service.cached_value(current, "profile", resource.id, ("status",), BombCache()))
    assert calls == []


@pytest.mark.postgres
def test_cache_wait_and_delayed_read_recheck_absolute_expiry(sharing_service, accepted_grant_factory, clock):
    _, recipient, resource, _ = accepted_grant_factory(expires_at=clock() + timedelta(seconds=5))
    current = principal(sharing_service, recipient)
    projection = read(sharing_service, recipient, resource)
    key = sharing_service.cache_key(current, "profile", resource.id, ("status",))
    class SlowCache(dict):
        def get(self, *args):
            clock.advance(5)
            return projection
    denied(lambda: sharing_service.cached_value(current, "profile", resource.id, ("status",), SlowCache({key: projection})))
    called = []
    denied(lambda: sharing_service.execute_shared(current, "profile", resource.id, ("status",),
        lambda *args: called.append(True)))
    assert called == []


@pytest.mark.postgres
def test_receiver_exit_remains_possible_after_bad_notice_and_unknown_age(sharing_service, accepted_grant_factory,
        privacy_service, privacy_settings, pg_engine):
    owner, recipient, resource, grant = accepted_grant_factory()
    current = privacy_service.get_admission(principal(sharing_service, recipient))
    denied(lambda: privacy_service.declare_age(principal(sharing_service, recipient),
        AgeDeclarationInput(age_band="unknown", confirmed=True, notice_id=current.notice_id,
            expected_revision=current.revision)), (403,))
    with Session(pg_engine) as session, session.begin():
        session.get(PrivacyNoticeVersion, privacy_settings.notice_id).text += PRIVATE_MARKER
    result = sharing_service.revoke_grant(principal(sharing_service, recipient), grant.id)
    assert result.user_id == recipient.user_id and result.revision == 0
    assert result.grant.state == "revoked" and result.grant.access_active is False
    assert sharing_service.list_grants(principal(sharing_service, owner)).revision == 2
    denied(lambda: accept(sharing_service, recipient, result.grant), (503,))


@pytest.mark.postgres
def test_third_party_cannot_revoke_or_accept_and_stale_owner_create_cannot_replay(sharing_service,
        admitted_actor_factory, resource_factory, create_request_factory):
    owner, recipient, outsider = admitted_actor_factory(), admitted_actor_factory(role=None), admitted_actor_factory(role=None)
    resource = resource_factory(owner)
    request = create_request_factory(owner, recipient, resource)
    grant = sharing_service.create_grant(principal(sharing_service, owner), request).grant
    denied(lambda: accept(sharing_service, outsider, grant), (404,))
    denied(lambda: sharing_service.revoke_grant(principal(sharing_service, outsider), grant.id), (404,))
    sharing_service.revoke_grant(principal(sharing_service, recipient), grant.id)
    denied(lambda: sharing_service.create_grant(principal(sharing_service, owner), request), (409,))
    denied(lambda: accept(sharing_service, recipient, grant), (409,))


@pytest.mark.postgres
def test_read_seam_retains_actual_actor_and_rolls_back_dirty_callback(sharing_service, accepted_grant_factory,
        privacy_service, pg_engine):
    owner, recipient, resource, _ = accepted_grant_factory()
    called = []
    def wrong_subject(session, current, projection):
        called.append(current.user_id)
        privacy_service.require_purpose(session, principal(sharing_service, owner), "core_consultation")
    denied(lambda: sharing_service.execute_shared(principal(sharing_service, recipient), "profile", resource.id,
        ("status",), wrong_subject), (403,))
    assert called == [recipient.user_id]
    def mutation(session, current, projection):
        session.get(AuthOwnedResource, resource.id).status = "deleted"
    denied(lambda: sharing_service.execute_shared(principal(sharing_service, recipient), "profile", resource.id,
        ("status",), mutation), (403,))
    with Session(pg_engine) as session:
        assert session.get(AuthOwnedResource, resource.id).status == "active"


@pytest.mark.postgres
def test_adult_proof_reuse_rebinds_new_transaction_but_not_actor_within_transaction(sharing_service,
        admitted_actor_factory, privacy_service, pg_engine):
    first, second = admitted_actor_factory(role=None), admitted_actor_factory(role=None)
    with Session(pg_engine) as session:
        with session.begin():
            assert privacy_service.require_declared_adult(session, principal(sharing_service, first)).user_id == first.user_id
            denied(lambda: privacy_service.require_declared_adult(session, principal(sharing_service, second)), (403,))
        with session.begin():
            assert privacy_service.require_declared_adult(session, principal(sharing_service, second)).user_id == second.user_id


def headers_for(service, actor):
    csrf = service.auth_service.get_csrf_token(actor.cookie).token.get_secret_value()
    return {"Cookie": f"{SESSION_COOKIE}={actor.cookie.get_secret_value()}",
        "Origin": "https://app.test.invalid", "X-CSRF-Token": csrf}


def assert_safe_http(response, status):
    assert response.status_code == status, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    body = response.json()
    assert body["meta" if status == 200 else "error"]["request_id"] == response.headers["x-request-id"]
    assert PRIVATE_MARKER not in response.text


@pytest.mark.postgres
@pytest.mark.parametrize("route", ["create", "accept", "revoke"])
@pytest.mark.parametrize("attack", ["missing_csrf", "wrong_origin", "duplicate_csrf", "duplicate_origin"])
def test_every_sharing_write_enforces_central_csrf_origin_before_transition(client, sharing_service,
        admitted_actor_factory, resource_factory, create_request_factory, route, attack):
    owner, recipient = admitted_actor_factory(), admitted_actor_factory(role=None)
    resource = resource_factory(owner)
    create = create_request_factory(owner, recipient, resource)
    grant = sharing_service.create_grant(principal(sharing_service, owner), create).grant
    actor = recipient if route == "accept" else owner
    path = "/access-grants" if route == "create" else f"/access-grants/{grant.id}" + ("/accept" if route == "accept" else "")
    payload = create.model_dump(mode="json") if route == "create" else accept_payload()
    entries = list(headers_for(sharing_service, actor).items())
    if attack == "missing_csrf":
        entries = [(k, v) for k, v in entries if k != "X-CSRF-Token"]
    elif attack == "wrong_origin":
        entries = [(k, "https://evil.test.invalid" if k == "Origin" else v) for k, v in entries]
    elif attack == "duplicate_csrf":
        entries += [next(pair for pair in entries if pair[0] == "X-CSRF-Token")]
    else:
        entries += [("Origin", "https://app.test.invalid")]
    kwargs = {} if route == "revoke" else {"json": payload}
    response = client.request("DELETE" if route == "revoke" else "POST", path, headers=entries, **kwargs)
    assert_safe_http(response, 403)
    assert sharing_service.list_grants(principal(sharing_service, owner)).revision == 1
    assert sharing_service.list_grants(principal(sharing_service, owner)).items[0].state == "pending"


@pytest.mark.postgres
def test_http_independent_accept_then_recipient_exit_and_account_switch(client, sharing_service,
        admitted_actor_factory, resource_factory, create_request_factory):
    owner, recipient, outsider = admitted_actor_factory(), admitted_actor_factory(role=None), admitted_actor_factory(role=None)
    resource = resource_factory(owner)
    request = create_request_factory(owner, recipient, resource)
    created = client.post("/access-grants", headers=headers_for(sharing_service, owner), json=request.model_dump(mode="json"))
    assert_safe_http(created, 200)
    grant_id = created.json()["data"]["grant"]["id"]
    denied_response = client.post(f"/access-grants/{grant_id}/accept", headers=headers_for(sharing_service, outsider), json=accept_payload())
    assert_safe_http(denied_response, 404)
    accepted = client.post(f"/access-grants/{grant_id}/accept", headers=headers_for(sharing_service, recipient), json=accept_payload())
    assert_safe_http(accepted, 200)
    assert accepted.json()["data"]["user_id"] == str(recipient.user_id)
    grant = accepted.json()["data"]["grant"]
    assert "owner_consent_id" not in grant and "grantee_declaration_id" not in grant
    exited = client.delete(f"/access-grants/{grant_id}", headers=headers_for(sharing_service, recipient))
    assert_safe_http(exited, 200)
    assert exited.json()["data"]["revision"] == 0
    replay = client.post(f"/access-grants/{grant_id}/accept", headers=headers_for(sharing_service, recipient),
        json={**accept_payload(), "expected_version": exited.json()["data"]["grant"]["version"]})
    assert_safe_http(replay, 404)


def wait_for_account_lock(engine, began, blocker_pid):
    assert began.wait(5), "worker never began"
    deadline = monotonic() + 8
    with engine.connect() as connection:
        while monotonic() < deadline:
            waiting = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                "AND pid<>pg_backend_pid() AND wait_event_type='Lock' AND query ILIKE '%auth_users%FOR UPDATE%' "
                "AND :blocker_pid=ANY(pg_blocking_pids(pid))"), {"blocker_pid": blocker_pid})
            if waiting:
                return
    pytest.fail("No actual PostgreSQL account-lock wait observed")


@pytest.mark.postgres
def test_pg_lock_wait_rechecks_grant_expiry_before_exposing_metadata(sharing_service, accepted_grant_factory,
        pg_engine, clock):
    owner, recipient, resource, _ = accepted_grant_factory(expires_at=clock() + timedelta(seconds=5))
    current = principal(sharing_service, recipient)
    began = Event()
    def blocked_read():
        began.set()
        return sharing_service.require_shared(current, "profile", resource.id, ("status",))
    with ThreadPoolExecutor(max_workers=1) as pool:
        with Session(pg_engine) as blocker, blocker.begin():
            blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
            blocker.execute(select(AuthUser).where(AuthUser.id.in_([owner.user_id, recipient.user_id]))
                .order_by(AuthUser.id).with_for_update()).all()
            future = pool.submit(blocked_read)
            wait_for_account_lock(pg_engine, began, blocker_pid)
            clock.advance(5)
        denied(lambda: future.result(timeout=8), (404,))


@pytest.mark.postgres
def test_pg_reciprocal_grants_use_sorted_account_lock_order_without_deadlock(sharing_service,
        admitted_actor_factory, resource_factory, create_request_factory, pg_engine):
    first, second = admitted_actor_factory(), admitted_actor_factory()
    first_resource, second_resource = resource_factory(first), resource_factory(second)
    first_request = create_request_factory(first, second, first_resource)
    second_request = create_request_factory(second, first, second_resource)
    actors = [principal(sharing_service, first), principal(sharing_service, second)]
    started = [Event(), Event()]
    def create(index):
        started[index].set()
        return sharing_service.create_grant(actors[index], [first_request, second_request][index])
    with ThreadPoolExecutor(max_workers=2) as pool:
        with Session(pg_engine) as blocker, blocker.begin():
            blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
            blocker.execute(select(AuthUser).where(AuthUser.id.in_([first.user_id, second.user_id]))
                .order_by(AuthUser.id).with_for_update()).all()
            futures = [pool.submit(create, i) for i in range(2)]
            for event in started:
                assert event.wait(5)
            wait_for_account_lock(pg_engine, started[0], blocker_pid)
        results = [f.result(timeout=12) for f in futures]
    assert [result.revision for result in results] == [1, 1]
    assert all(result.grant.state == "pending" for result in results)


@pytest.mark.postgres
def test_slow_cache_rechecks_current_owner_role_expiry(sharing_service, accepted_grant_factory, clock, pg_engine):
    owner, recipient, resource, _ = accepted_grant_factory()
    with Session(pg_engine) as session, session.begin():
        session.get(AuthUserRole, (owner.user_id, "student")).expires_at = clock() + timedelta(seconds=5)
    current = principal(sharing_service, recipient)
    value = read(sharing_service, recipient, resource)
    key = sharing_service.cache_key(current, "profile", resource.id, ("status",))
    class SlowCache(dict):
        def get(self, *args):
            clock.advance(5)
            return value
    denied(lambda: sharing_service.cached_value(current, "profile", resource.id, ("status",), SlowCache({key: value})))


@pytest.mark.postgres
def test_pg_owner_consent_invalidation_commit_while_reader_waits_does_not_expose_metadata(sharing_service,
        accepted_grant_factory, pg_engine, privacy_service):
    owner, recipient, resource, _ = accepted_grant_factory()
    current = principal(sharing_service, recipient)
    owner_current = principal(sharing_service, owner)
    consent = privacy_service.get_admission(owner_current).consent_id
    began = Event()
    def blocked_read():
        began.set()
        return sharing_service.require_shared(current, "profile", resource.id, ("status",))
    with ThreadPoolExecutor(max_workers=1) as pool:
        with Session(pg_engine) as blocker, blocker.begin():
            blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
            blocker.execute(select(AuthUser).where(AuthUser.id.in_([owner.user_id, recipient.user_id]))
                .order_by(AuthUser.id).with_for_update()).all()
            future = pool.submit(blocked_read)
            wait_for_account_lock(pg_engine, began, blocker_pid)
            # Persist the exact withdrawal snapshot in a privileged fixture
            # transaction; the waiting reader must see this committed proof.
            from services.api.app.privacy.models import PrivacyAdmissionRecord
            latest = blocker.scalar(select(PrivacyAdmissionRecord).where(PrivacyAdmissionRecord.user_id == owner.user_id)
                .order_by(PrivacyAdmissionRecord.revision.desc()).limit(1).with_for_update())
            blocker.add(PrivacyAdmissionRecord(id=uuid4(), user_id=owner.user_id, revision=latest.revision + 1,
                event_type="consent_withdrawn", recorded_at=sharing_service.auth_service._now(), policy_version=latest.policy_version,
                age_band=latest.age_band, age_assurance=latest.age_assurance, declared_at=latest.declared_at,
                declaration_expires_at=latest.declaration_expires_at, declaration_notice_id=latest.declaration_notice_id,
                consent_id=consent, consent_status="withdrawn", consent_notice_id=latest.consent_notice_id,
                consent_confirmed_at=latest.consent_confirmed_at, consent_withdrawn_at=sharing_service.auth_service._now()))
        denied(lambda: future.result(timeout=8))


@pytest.mark.postgres
def test_pg_recipient_revoke_serializes_with_inflight_read_and_blocks_all_later_reads(sharing_service,
        accepted_grant_factory, pg_engine):
    _, recipient, resource, grant = accepted_grant_factory()
    current = principal(sharing_service, recipient)
    key = sharing_service.cache_key(current, "profile", resource.id, ("status",))
    projection = read(sharing_service, recipient, resource)
    entered, release, revoke_started = Event(), Event(), Event()
    read_pids = []
    def inflight(session, actor, value):
        assert actor.user_id == recipient.user_id and value == projection
        read_pids.append(session.scalar(text("SELECT pg_backend_pid()")))
        entered.set()
        assert release.wait(8), "read operation was not released"
        return value
    def revoke():
        revoke_started.set()
        return sharing_service.revoke_grant(current, grant.id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        reading = pool.submit(sharing_service.execute_shared, current, "profile", resource.id, ("status",), inflight)
        try:
            assert entered.wait(5)
            revoking = pool.submit(revoke)
            wait_for_account_lock(pg_engine, revoke_started, read_pids[0])
        finally:
            release.set()
        assert reading.result(timeout=8) == projection
        assert revoking.result(timeout=8).grant.state == "revoked"
    denied(lambda: read(sharing_service, recipient, resource))
    denied(lambda: sharing_service.cached_value(current, "profile", resource.id, ("status",), {key: projection}))
    assert sharing_service.list_shared(current, "profile", ("status",)).total == 0
