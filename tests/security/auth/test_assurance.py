"""Strength is explicit, signed provenance is fixed, and strength grants no role."""

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session


@pytest.fixture
def policy_factory(session_settings):
    from services.api.app.auth.assurance import AdminAssurancePolicy

    def make(**changes):
        values = {"enabled": True, "trusted_issuer": session_settings.provider.issuer,
            "admin_client_id": session_settings.provider.client_id,
            "student_client_id": "T06_SEPARATE_STUDENT_CLIENT", "allowed_acr": ("T06_MFA",),
            "required_amr": ("pwd", "otp"), "max_auth_age_seconds": 300}
        values.update(changes)
        return AdminAssurancePolicy(**values)

    return make


def test_complete_explicit_strength_is_only_a_check(policy_factory, clock):
    from services.api.app.auth.assurance import SessionAssurance, check_admin_assurance

    policy = policy_factory()
    proof = SessionAssurance(acr="T06_MFA", amr=("pwd", "otp"), auth_time=clock())
    assert check_admin_assurance(proof, issuer=policy.trusted_issuer, client_id=policy.admin_client_id,
                                 policy=policy, now=clock()) is None
    assert not hasattr(proof, "roles") and not hasattr(policy, "roles")


@pytest.mark.parametrize("change", ["disabled", "missing", "issuer", "student", "acr", "method", "future", "old", "no-time", "naive-now"])
def test_missing_wrong_or_stale_strength_is_closed(policy_factory, clock, change):
    from services.api.app.auth.assurance import AdminAssurancePolicy, SessionAssurance, check_admin_assurance
    from services.api.app.auth.config import AuthFlowError

    policy = policy_factory()
    values = {"acr": "T06_MFA", "amr": ("pwd", "otp"), "auth_time": clock()}
    issuer, client, now = policy.trusted_issuer, policy.admin_client_id, clock()
    if change == "disabled":
        policy = AdminAssurancePolicy()
    elif change == "issuer":
        issuer += "/other"
    elif change == "student":
        client = policy.student_client_id
    elif change == "acr":
        values["acr"] = "T06_MFA_HIGHER_BY_NAME"
    elif change == "method":
        values["amr"] = ("pwd", "OTP")
    elif change == "future":
        values["auth_time"] += timedelta(seconds=1)
    elif change == "old":
        values["auth_time"] -= timedelta(seconds=301)
    elif change == "no-time":
        values["auth_time"] = None
    elif change == "naive-now":
        now = now.replace(tzinfo=None)
    proof = None if change == "missing" else SessionAssurance(**values)
    with pytest.raises(AuthFlowError) as caught:
        check_admin_assurance(proof, issuer=issuer, client_id=client, policy=policy, now=now)
    assert caught.value.status_code == 403


@pytest.mark.parametrize("field,value", [
    ("trusted_issuer", None), ("admin_client_id", None), ("student_client_id", None),
    ("admin_client_id", "T06_SEPARATE_STUDENT_CLIENT"), ("allowed_acr", ()),
    ("required_amr", ()), ("max_auth_age_seconds", None), ("max_auth_age_seconds", 0),
    ("max_auth_age_seconds", True), ("allowed_acr", ("same", "same")),
    ("required_amr", ("otp", "otp")), ("unknown_policy", "T06_SENSITIVE_POLICY"),
], ids=["issuer", "admin", "student", "shared-client", "acr", "amr", "age", "zero", "bool", "dup-acr", "dup-amr", "extra"])
def test_enabled_policy_requires_full_explicit_trust(policy_factory, field, value):
    with pytest.raises(ValueError) as caught:
        policy_factory(**{field: value})
    assert "T06_SENSITIVE_POLICY" not in str(caught.value) + repr(caught.value)


@pytest.mark.parametrize("bypass", ["copy", "construct"])
def test_admin_checker_revalidates_policy_and_proof(policy_factory, clock, bypass):
    from services.api.app.auth.assurance import AdminAssurancePolicy, SessionAssurance, check_admin_assurance
    from services.api.app.auth.config import AuthFlowError

    policy = policy_factory()
    invalid = (policy.model_copy(update={"max_auth_age_seconds": True}) if bypass == "copy" else
        AdminAssurancePolicy.model_construct(**{**policy.model_dump(), "max_auth_age_seconds": True}))
    proof = SessionAssurance(acr="T06_MFA", amr=("pwd", "otp"), auth_time=clock())
    with pytest.raises(AuthFlowError):
        check_admin_assurance(proof, issuer=policy.trusted_issuer, client_id=policy.admin_client_id,
                              policy=invalid, now=clock())
    forged = proof.model_copy(update={"auth_time": clock().replace(tzinfo=None)})
    with pytest.raises(AuthFlowError):
        check_admin_assurance(forged, issuer=policy.trusted_issuer, client_id=policy.admin_client_id,
                              policy=policy, now=clock())


@pytest.fixture
def admin_service(policy_factory, session_settings_factory, runtime, auth_store, idp, clock):
    from services.api.app.auth.oidc import KeycloakOidcAdapter
    from services.api.app.auth.service import AuthService

    settings = session_settings_factory(admin_assurance_policy=policy_factory())
    return AuthService(settings, runtime, auth_store,
        KeycloakOidcAdapter(settings, runtime, transport=idp.transport), clock=clock)


def signed_login(service, fake_idp, clock, **claims):
    fake_idp.claim_changes = {"acr": "T06_MFA", "amr": ["pwd", "otp"],
        "auth_time": int(clock().timestamp()), **claims}
    started = service.start_login()
    code, state = fake_idp.issue_from_authorization(started.authorization_url.get_secret_value())
    return service.complete_login(code, state, started.browser_binding).session_cookie


@pytest.mark.postgres
def test_signed_strength_and_fixed_provenance_are_persisted_without_roles(
    admin_service, idp, active_account, clock, pg_engine,
):
    from services.api.app.auth.models import AuthSession

    cookie = signed_login(admin_service, idp, clock)
    current = admin_service.check_admin_assurance(cookie, permission_verifier=lambda current: True)
    assert current.user_id == active_account
    assert set(current.model_dump()) == {"user_id", "expires_at", "is_synthetic"}
    with Session(pg_engine) as database:
        row = database.scalar(select(AuthSession))
        assert row.verified_issuer == admin_service.settings.provider.issuer
        assert row.verified_client_id == admin_service.settings.provider.client_id
        assert row.assurance_acr == "T06_MFA" and row.assurance_amr == ["pwd", "otp"]
        assert row.assurance_auth_time == clock()


@pytest.mark.postgres
@pytest.mark.parametrize("variant", ["missing-acr", "missing-amr", "missing-time", "weak", "old", "roles", "disabled-policy", "no-permission"])
def test_real_signature_does_not_make_incomplete_or_unconfigured_admin_proof_valid(
    admin_service, auth_service, idp, active_account, clock, variant,
):
    from services.api.app.auth.config import AuthFlowError

    changes = {}
    if variant == "weak":
        changes["acr"] = "weak"
    elif variant == "old":
        changes["auth_time"] = int(clock().timestamp()) - 301
    elif variant == "roles":
        changes = {"acr": "weak", "realm_access": {"roles": ["admin"]}}
    idp.claim_removals = {"missing-acr": {"acr"}, "missing-amr": {"amr"}, "missing-time": {"auth_time"}}.get(variant, set())
    cookie = signed_login(admin_service, idp, clock, **changes)
    service = auth_service if variant == "disabled-policy" else admin_service
    permission = None if variant == "no-permission" else lambda current: True
    with pytest.raises(AuthFlowError) as caught:
        service.check_admin_assurance(cookie, permission_verifier=permission)
    assert caught.value.status_code == 403


@pytest.mark.postgres
@pytest.mark.parametrize("claims", [
    {"acr": 2}, {"amr": "otp"}, {"amr": ["otp", "otp"]}, {"amr": [True]},
    {"auth_time": True}, {"auth_time": "now"}, {"auth_time": float("inf")},
    {"acr": None}, {"amr": None}, {"auth_time": None}, {"amr": True},
    {"auth_time": float("nan")}, {"auth_time": "future"},
], ids=["acr-number", "amr-string", "duplicate-method", "method-bool", "time-bool", "time-string", "time-infinite",
        "acr-null", "amr-null", "time-null", "amr-bool", "time-nan", "time-future"])
def test_malformed_signed_assurance_claims_cannot_establish_session(admin_service, idp, active_account, clock, claims):
    from services.api.app.auth.config import AuthFlowError

    if claims.get("auth_time") == "future":
        claims = {"auth_time": int(clock().timestamp()) + 1}
    with pytest.raises(AuthFlowError) as caught:
        signed_login(admin_service, idp, clock, **claims)
    assert caught.value.status_code == 401


@pytest.mark.postgres
def test_signed_student_client_provenance_does_not_satisfy_admin_policy(
    policy_factory, session_settings_factory, runtime, auth_store, idp, active_account, clock,
):
    from services.api.app.auth.config import AuthFlowError
    from services.api.app.auth.oidc import KeycloakOidcAdapter
    from services.api.app.auth.service import AuthService

    policy = policy_factory(admin_client_id="T06_SEPARATE_ADMIN_CLIENT", student_client_id=idp.settings.provider.client_id)
    settings = session_settings_factory(admin_assurance_policy=policy)
    service = AuthService(settings, runtime, auth_store,
        KeycloakOidcAdapter(settings, runtime, transport=idp.transport), clock=clock)
    cookie = signed_login(service, idp, clock)
    assert service.get_session(cookie).user_id == active_account
    with pytest.raises(AuthFlowError) as caught:
        service.check_admin_assurance(cookie, permission_verifier=lambda current: True)
    assert caught.value.status_code == 403


@pytest.mark.postgres
@pytest.mark.parametrize("change", ["proof", "provenance", "policy", "age"])
def test_admin_check_rechecks_strength_and_policy_after_permission_callback(
    admin_service, idp, active_account, clock, pg_engine, change,
):
    from services.api.app.auth.assurance import AdminAssurancePolicy
    from services.api.app.auth.config import AuthFlowError
    from services.api.app.auth.models import AuthSession

    cookie = signed_login(admin_service, idp, clock)

    def permission(current):
        if change == "policy":
            admin_service.settings = admin_service.settings.model_copy(update={"admin_assurance_policy": AdminAssurancePolicy()})
        elif change == "age":
            clock.advance(301)
        else:
            with Session(pg_engine) as database, database.begin():
                row = database.scalar(select(AuthSession))
                if change == "proof":
                    row.assurance_acr = "weak"
                else:
                    row.verified_client_id = "T06_UNTRUSTED_CLIENT"
        return True

    with pytest.raises(AuthFlowError) as caught:
        admin_service.check_admin_assurance(cookie, permission_verifier=permission)
    assert caught.value.status_code == 403
