"""Server roles, stale references and scoped caches never act as permission proofs."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Column, MetaData, String, Table, Uuid, create_engine, select, update
from sqlalchemy.orm import Session

from services.api.app.auth.models import AuthSession, AuthUser
from services.api.app.auth.service import digest_secret

from .conftest import rejected


def student(harness):
    actor = harness.account()
    harness.role(actor)
    return actor


def test_newly_registered_account_has_no_automatic_business_role(harness):
    actor = harness.account()
    principal = harness.principal(actor)
    assert principal.roles == ()
    assert harness.service.get_session(actor.cookie).user_id == actor.user_id
    rejected(lambda: harness.authorizer.list_owned(principal, "profile"), 403)
    rejected(lambda: harness.authorizer.register_owned(principal, "profile"), 403)


@pytest.mark.parametrize("role", ("data_admin", "operations"))
def test_non_student_roles_cannot_access_even_their_own_private_resource(harness, role):
    actor = student(harness)
    resource = harness.owned(actor)
    harness.service.store.revoke_role(actor.user_id, "student", now=harness.clock[0])
    harness.role(actor, role)
    principal = harness.principal(actor)
    assert principal.roles == (role,)
    rejected(lambda: harness.authorizer.require_owned(principal, "profile", resource.id), 403)
    rejected(lambda: harness.authorizer.list_owned(principal, "profile"), 403)


@pytest.mark.parametrize("extra_role", ("data_admin", "operations"))
def test_mixed_roles_keep_student_access_limited_to_self(harness, extra_role):
    actor, other = student(harness), student(harness)
    own, foreign = harness.owned(actor), harness.owned(other)
    harness.role(actor, extra_role)
    principal = harness.principal(actor)
    assert set(principal.roles) == {"student", extra_role}
    assert harness.authorizer.require_owned(principal, "profile", own.id).owner_user_id == actor.user_id
    rejected(lambda: harness.authorizer.require_owned(principal, "profile", foreign.id), 404)


@pytest.mark.parametrize("change", ("not_yet_effective", "expired", "revoked"))
def test_role_lifecycle_is_read_from_database_not_principal_snapshot(harness, change):
    from services.api.app.auth.models import AuthUserRole

    actor = student(harness)
    resource = harness.owned(actor)
    principal = harness.principal(actor)
    assert principal.roles == ("student",)
    with Session(harness.engine) as db, db.begin():
        values = {"not_yet_effective": {"granted_at": harness.clock[0] + timedelta(seconds=1)},
            "expired": {"expires_at": harness.clock[0] + timedelta(seconds=1)},
            "revoked": {"revoked_at": harness.clock[0]}}[change]
        db.execute(update(AuthUserRole).where(AuthUserRole.user_id == actor.user_id,
            AuthUserRole.role == "student").values(**values))
    if change == "expired":
        harness.clock[0] += timedelta(seconds=1)
    assert harness.authorizer.refresh(principal).roles == ()
    rejected(lambda: harness.authorizer.require_owned(principal, "profile", resource.id), 403)


def test_forged_role_and_expiry_snapshot_are_ignored(harness):
    actor = harness.account()
    original = harness.principal(actor)
    forged = original.model_copy(update={"roles": ("student", "data_admin", "operations"),
        "is_synthetic": False, "expires_at": original.expires_at + timedelta(days=365),
        "authorization_context": "0" * 64})
    refreshed = harness.authorizer.refresh(forged)
    assert refreshed.roles == () and refreshed.is_synthetic is True
    assert refreshed.expires_at == original.expires_at
    assert refreshed.authorization_context == original.authorization_context
    rejected(lambda: harness.authorizer.register_owned(forged, "profile"), 403)
    rejected(lambda: harness.authorizer.require_capability(forged, "operations.status"), 403)


@pytest.mark.parametrize("field", ("user_id", "session_id"))
def test_forged_uuid_binding_does_not_resolve_another_actor(harness, field):
    actor, victim = student(harness), student(harness)
    resource = harness.owned(victim)
    principal = harness.principal(actor)
    forged = principal.model_copy(update={field: getattr(victim, field)})
    rejected(lambda: harness.authorizer.refresh(forged), 401)
    rejected(lambda: harness.authorizer.require_owned(forged, "profile", resource.id), 401)


@pytest.mark.parametrize("capability", ("operations.status", "catalog.import", "catalog.review",
    "catalog.publish", "catalog.withdraw", "profiles.read", "*"))
def test_student_role_is_not_admin_or_operations_capability(harness, capability):
    actor = student(harness)
    rejected(lambda: harness.authorizer.require_capability(harness.principal(actor), capability), 403)


def test_operations_has_only_non_personal_status_capability(harness):
    actor = harness.account()
    harness.role(actor, "operations")
    principal = harness.principal(actor)
    harness.authorizer.require_capability(principal, "operations.status")
    for capability in ("catalog.import", "catalog.review", "catalog.publish", "catalog.withdraw", "profile.read"):
        rejected(lambda capability=capability: harness.authorizer.require_capability(principal, capability), 403)


def test_data_admin_role_alone_cannot_bypass_disabled_strength_policy(harness):
    actor = harness.account()
    harness.role(actor, "data_admin")
    for capability in ("catalog.import", "catalog.review", "catalog.publish", "catalog.withdraw"):
        rejected(lambda capability=capability: harness.authorizer.require_capability(
            harness.principal(actor), capability), 403)


def configure_admin(harness):
    from services.api.app.auth.assurance import AdminAssurancePolicy
    from services.api.app.auth.config import SessionAuthSettings

    original = harness.service.settings
    policy = AdminAssurancePolicy(enabled=True, trusted_issuer=original.provider.issuer,
        student_client_id=original.provider.client_id, admin_client_id="T07_SYNTHETIC_ADMIN_CLIENT",
        allowed_acr=("T07_HIGH",), required_amr=("pwd", "otp"), max_auth_age_seconds=60)
    values = original.model_copy(update={"provider": original.provider.model_copy(
        update={"client_id": policy.admin_client_id}), "admin_assurance_policy": policy})
    harness.service.settings = SessionAuthSettings.model_validate(values)
    return {"verified_issuer": policy.trusted_issuer, "verified_client_id": policy.admin_client_id,
        "assurance_acr": "T07_HIGH", "assurance_amr": ["pwd", "otp"],
        "assurance_auth_time": harness.clock[0]}


@pytest.mark.parametrize("capability", ("catalog.import", "catalog.review", "catalog.publish", "catalog.withdraw"))
def test_admin_capability_requires_both_current_role_and_trusted_strength(harness, capability):
    # This seeds the verified-proof storage boundary; JWT crypto belongs to the T05 tests.
    proof = configure_admin(harness)
    actor = harness.account(proof=proof)
    rejected(lambda: harness.authorizer.require_capability(harness.principal(actor), capability), 403)
    harness.role(actor, "data_admin")
    harness.authorizer.require_capability(harness.principal(actor), capability)
    harness.service.store.revoke_role(actor.user_id, "data_admin", now=harness.clock[0])
    rejected(lambda: harness.authorizer.require_capability(harness.principal(actor), capability), 403)


@pytest.mark.parametrize("defect", ("missing", "issuer", "client", "acr", "amr", "stale"))
def test_admin_role_does_not_replace_invalid_or_old_proof(harness, defect):
    proof = configure_admin(harness)
    if defect == "missing":
        proof = None
    elif defect == "issuer":
        proof["verified_issuer"] = "https://other.test.invalid/realms/students"
    elif defect == "client":
        proof["verified_client_id"] = "T07_SYNTHETIC_STUDENT_CLIENT"
    elif defect == "acr":
        proof["assurance_acr"] = "T07_WEAK"
    elif defect == "amr":
        proof["assurance_amr"] = ["pwd"]
    actor = harness.account(proof=proof)
    harness.role(actor, "data_admin")
    if defect == "stale":
        harness.clock[0] += timedelta(seconds=61)
    rejected(lambda: harness.authorizer.require_capability(harness.principal(actor), "catalog.publish"), 403)


def test_cache_changes_with_session_action_filters_roles_and_resource_version(harness):
    actor = student(harness)
    resource = harness.owned(actor)
    principal = harness.principal(actor)
    base = harness.authorizer.cache_key(principal, "profile", resource.id)
    other_cookie = "T07_OTHER_SYNTHETIC_COOKIE_" + "b" * 43
    other_session = uuid4()
    with Session(harness.engine) as db, db.begin():
        db.add(AuthSession(id=other_session, user_id=actor.user_id,
            session_digest=digest_secret(other_cookie, "session"), created_at=harness.clock[0],
            expires_at=principal.expires_at, revoked_at=None))
    other_principal = harness.service.get_principal(other_cookie)
    keys = {base, harness.authorizer.cache_key(other_principal, "profile", resource.id),
        harness.authorizer.cache_key(principal, "profile", resource.id, "export"),
        harness.authorizer.cache_key(principal, "profile", resource.id, filters=("route:gaokao",)),
        harness.authorizer.cache_key(principal, "profile", resource.id, filters=("route:uk",))}
    harness.role(actor, "operations")
    keys.add(harness.authorizer.cache_key(principal, "profile", resource.id))
    harness.authorizer.touch_owned(principal, "profile", resource.id, resource.version)
    keys.add(harness.authorizer.cache_key(principal, "profile", resource.id))
    assert len(keys) == 7
    assert str(actor.user_id) not in base and other_cookie not in base


def test_cache_hit_rechecks_role_and_does_not_return_cross_owner_value(harness):
    actor, other = student(harness), student(harness)
    resource, foreign = harness.owned(actor), harness.owned(other)
    principal = harness.principal(actor)
    key = harness.authorizer.cache_key(principal, "profile", resource.id)
    cache = {key: "T07_SYNTHETIC_PRIVATE_CACHE_VALUE"}
    assert harness.authorizer.cached_value(principal, "profile", resource.id, cache) == cache[key]
    rejected(lambda: harness.authorizer.cached_value(harness.principal(other), "profile", resource.id, cache), 404)
    rejected(lambda: harness.authorizer.cached_value(principal, "profile", foreign.id, cache), 404)
    harness.service.store.revoke_role(actor.user_id, "student", now=harness.clock[0])
    rejected(lambda: harness.authorizer.cached_value(principal, "profile", resource.id, cache), 403)


@pytest.mark.parametrize("secondary_role", ("operations", "data_admin"))
def test_slow_cache_read_drops_value_if_secondary_role_context_expires(harness, secondary_role):
    actor = student(harness)
    harness.role(actor, secondary_role, expires_at=harness.clock[0] + timedelta(seconds=1))
    resource = harness.owned(actor)
    principal = harness.principal(actor)
    key = harness.authorizer.cache_key(principal, "profile", resource.id)

    class SlowCache(dict):
        def get(self, requested, default=None):
            harness.clock[0] += timedelta(seconds=1)
            return super().get(requested, default)

    cache = SlowCache({key: "T07_VALUE_FROM_EXPIRED_SECONDARY_ROLE_CONTEXT"})
    assert harness.authorizer.cached_value(principal, "profile", resource.id, cache) is None
    refreshed = harness.authorizer.refresh(principal)
    assert refreshed.roles == ("student",)
    assert refreshed.authorization_context != principal.authorization_context
    assert harness.authorizer.require_owned(refreshed, "profile", resource.id).id == resource.id


@pytest.mark.parametrize("change", ("role_revoked", "resource_deleted", "parent_deleted", "account_disabled",
    "session_revoked", "session_expired"))
def test_delayed_job_reference_rechecks_access_before_callback(harness, change):
    from services.api.app.auth.models import AuthOwnedResource

    actor = student(harness)
    parent = harness.owned(actor)
    job = harness.owned(actor, "job", parent_id=parent.id)
    principal = harness.principal(actor)
    effects = []
    if change == "role_revoked":
        harness.service.store.revoke_role(actor.user_id, "student", now=harness.clock[0])
    elif change == "session_expired":
        harness.clock[0] = principal.expires_at
    else:
        with Session(harness.engine) as db, db.begin():
            if change in {"resource_deleted", "parent_deleted"}:
                target = job.id if change == "resource_deleted" else parent.id
                db.execute(update(AuthOwnedResource).where(AuthOwnedResource.id == target).values(status="deleted"))
            elif change == "account_disabled":
                db.execute(update(AuthUser).where(AuthUser.id == actor.user_id).values(status="disabled"))
            else:
                db.execute(update(AuthSession).where(AuthSession.id == actor.session_id).values(revoked_at=harness.clock[0]))
    expected = 403 if change == "role_revoked" else 404 if change in {"resource_deleted", "parent_deleted"} else 401
    rejected(lambda: harness.authorizer.execute_owned(principal, "job", job.id, "execute",
        lambda db, current, resource: effects.append(resource.id)), expected)
    assert effects == []


def test_local_callback_uses_one_transaction_and_rolls_back_on_failure(harness):
    from services.api.app.auth.authorization import AuthorizationError

    actor = student(harness)
    job = harness.owned(actor, "job")
    principal = harness.principal(actor)
    written_id = uuid4()

    def operation(db, current, resource):
        assert db.in_transaction()
        assert current.user_id == actor.user_id and resource.id == job.id
        db.add(AuthUser(id=written_id, status="active", is_synthetic=True, created_at=harness.clock[0]))
        db.flush()
        raise AuthorizationError(403, "FORBIDDEN")

    rejected(lambda: harness.authorizer.execute_owned(principal, "job", job.id, "execute", operation), 403)
    with Session(harness.engine) as db:
        assert db.scalar(select(AuthUser).where(AuthUser.id == written_id)) is None


def test_successful_callback_commit_is_local_and_principal_is_fresh(harness):
    actor = student(harness)
    job = harness.owned(actor, "job")
    principal = harness.principal(actor)
    harness.role(actor, "operations")
    written_id = uuid4()

    def operation(db, current, resource):
        assert db.in_transaction()
        assert current.roles != principal.roles and current.user_id == actor.user_id
        assert resource.owner_user_id == actor.user_id
        db.add(AuthUser(id=written_id, status="active", is_synthetic=True, created_at=harness.clock[0]))
        return "local-result"

    assert harness.authorizer.execute_owned(principal, "job", job.id, "execute", operation) == "local-result"
    with Session(harness.engine) as db:
        assert db.scalar(select(AuthUser.id).where(AuthUser.id == written_id)) == written_id


def domain_stub(harness):
    # Test-only local effect table; no application model, migration or student payload.
    metadata = MetaData()
    table = Table("t07_synthetic_domain_stub", metadata,
        Column("id", Uuid, primary_key=True), Column("effect", String(32), nullable=False))
    metadata.create_all(harness.engine)
    return table


@pytest.mark.parametrize("outcome", ("commit", "caller_rollback", "caller_error"))
def test_registration_and_domain_stub_share_explicit_caller_transaction(harness, outcome):
    from services.api.app.auth.models import AuthOwnedResource

    actor = student(harness)
    principal = harness.principal(actor)
    resource_id = uuid4()
    stub = domain_stub(harness)

    def register(db):
        db.execute(stub.insert().values(id=resource_id, effect="T07_SYNTHETIC_EFFECT"))
        resource = harness.authorizer.register_owned(principal, "profile", resource_id=resource_id, session=db)
        assert resource.id == resource_id and resource.owner_user_id == actor.user_id
        assert db.scalar(select(AuthOwnedResource.id).where(AuthOwnedResource.id == resource_id)) == resource_id

    if outcome == "caller_error":
        with pytest.raises(RuntimeError, match="synthetic command failed"):
            with Session(harness.engine) as db, db.begin():
                register(db)
                raise RuntimeError("synthetic command failed")
    elif outcome == "caller_rollback":
        with Session(harness.engine) as db:
            db.begin()
            register(db)
            db.rollback()
    else:
        with Session(harness.engine) as db, db.begin():
            register(db)
    with Session(harness.engine) as db:
        actual_resource = db.scalar(select(AuthOwnedResource.id).where(AuthOwnedResource.id == resource_id))
        actual_effect = db.scalar(select(stub.c.id).where(stub.c.id == resource_id))
    expected = resource_id if outcome == "commit" else None
    assert actual_resource == actual_effect == expected


@pytest.mark.parametrize("binding", ("no_active_transaction", "wrong_engine"))
def test_registration_refuses_untrusted_session_binding_without_metadata(harness, binding):
    from services.api.app.auth.models import AuthOwnedResource

    actor = student(harness)
    principal = harness.principal(actor)
    resource_id = uuid4()
    other_engine = create_engine("sqlite+pysqlite://", hide_parameters=True)
    try:
        if binding == "wrong_engine":
            with Session(other_engine) as db, db.begin():
                rejected(lambda: harness.authorizer.register_owned(principal, "profile",
                    resource_id=resource_id, session=db), 503)
        else:
            with Session(harness.engine) as db:
                assert not db.in_transaction()
                rejected(lambda: harness.authorizer.register_owned(principal, "profile",
                    resource_id=resource_id, session=db), 503)
        with Session(harness.engine) as db:
            assert db.scalar(select(AuthOwnedResource.id).where(AuthOwnedResource.id == resource_id)) is None
    finally:
        other_engine.dispose()


def test_callback_immutable_synthetic_flag_change_rolls_back_all_local_effects(harness):
    from services.api.app.auth.models import AuthOwnedResource

    actor = student(harness)
    resource = harness.owned(actor)
    stub = domain_stub(harness)
    effect_id = uuid4()

    def operation(db, current, snapshot):
        db.execute(stub.insert().values(id=effect_id, effect="T07_SYNTHETIC_EFFECT"))
        db.execute(update(AuthOwnedResource).where(AuthOwnedResource.id == snapshot.id).values(is_synthetic=False))
        return "must-not-commit"

    rejected(lambda: harness.authorizer.execute_owned(harness.principal(actor), "profile",
        resource.id, "write", operation), 403)
    with Session(harness.engine) as db:
        assert db.scalar(select(stub.c.id).where(stub.c.id == effect_id)) is None
        assert db.scalar(select(AuthOwnedResource.is_synthetic).where(AuthOwnedResource.id == resource.id)) is True
