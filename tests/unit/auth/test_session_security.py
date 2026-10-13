"""T06 service checks against an explicit migrated, synthetic SQLite substitute."""

from datetime import timedelta
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from services.api.app.auth.assurance import AdminAssurancePolicy, SessionAssurance, check_admin_assurance
from services.api.app.auth.config import AuthFlowError, SessionAuthSettings
from services.api.app.auth.models import AuthSession, AuthUser
from services.api.app.auth.schemas import AuthProviderSettings
from services.api.app.auth.service import AuthService, ExecutionReference, digest_secret
from services.api.app.auth.store import AuthStore, migrate_auth
from services.api.app.settings import V2RuntimeSettings


class UnusedProvider:
    def prepare_authorization(self, context):
        raise AssertionError("This test does not perform login")

    def exchange_code(self, code, context, *, now):
        raise AssertionError("This test does not exchange tokens")


@pytest.fixture
def security_service(now):
    engine = create_engine("sqlite+pysqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False}, hide_parameters=True)
    migrate_auth(engine)
    provider = AuthProviderSettings(provider_mode="oidc_boundary", provider_id="T06_SYNTHETIC_PROVIDER",
        issuer="https://idp.test.invalid/realms/students", client_id="T06_SYNTHETIC_STUDENT_CLIENT",
        callback_allowlist=("https://app.test.invalid/v2/auth/callback",), client_secret="T06_SYNTHETIC_SECRET")
    config = SessionAuthSettings(enabled=True, provider=provider, redirect_uri=provider.callback_allowlist[0],
                                 context_encryption_key=Fernet.generate_key().decode("ascii"))
    runtime = V2RuntimeSettings(app_environment="test", data_mode="verified", model_mode="disabled",
                                database_url=None, legacy_demo_mode=None, _env_file=None)
    clock = [now]
    service = AuthService(config, runtime, AuthStore(engine), UnusedProvider(), clock=lambda: clock[0])
    user_id, session_id = uuid4(), uuid4()
    cookie = SecretStr("T06_SYNTHETIC_COOKIE_" + "a" * 43)
    with Session(engine) as session, session.begin():
        session.add(AuthUser(id=user_id, status="active", is_synthetic=True, created_at=now))
        session.add(AuthSession(id=session_id, user_id=user_id, session_digest=digest_secret(cookie, "session"),
            created_at=now, expires_at=now + timedelta(hours=1), revoked_at=None))
    try:
        yield service, engine, clock, cookie, ExecutionReference(session_id=session_id, user_id=user_id)
    finally:
        engine.dispose()


def rejects(call, status):
    with pytest.raises(AuthFlowError) as error:
        call()
    assert error.value.status_code == status


def test_stable_lazy_csrf_is_digest_and_encrypted_only(security_service):
    service, engine, clock, cookie, _ = security_service
    first = service.get_csrf_token(cookie)
    clock[0] += timedelta(minutes=10)
    second = service.get_csrf_token(cookie)
    assert first == second
    assert len(first.token.get_secret_value()) == 43
    with Session(engine) as session:
        row = session.scalar(select(AuthSession))
        assert row.csrf_digest == digest_secret(first.token, "csrf")
        assert first.token.get_secret_value() not in (row.csrf_digest, row.csrf_encrypted_token)
        assert row.verified_issuer is None
    assert service.verify_csrf(cookie, first.token).expires_at == first.expires_at


@pytest.mark.parametrize("token", ["", "a" * 42, "a" * 44, "x" * 43, "😀" * 43])
def test_invalid_csrf_does_not_revoke_session(security_service, token):
    service, _, _, cookie, _ = security_service
    service.get_csrf_token(cookie)
    rejects(lambda: service.logout(cookie, token), 403)
    assert service.get_session(cookie).user_id


def test_logout_is_atomic_and_repeat_is_unauthorized(security_service):
    service, engine, _, cookie, _ = security_service
    csrf = service.get_csrf_token(cookie)
    service.logout(cookie, csrf.token)
    rejects(lambda: service.get_session(cookie), 401)
    rejects(lambda: service.logout(cookie, csrf.token), 401)
    with Session(engine) as session:
        row = session.scalar(select(AuthSession))
        assert row.revoked_at is not None
        assert row.csrf_digest is row.csrf_encrypted_token is None


def test_absolute_expiry_not_extended_by_csrf_reads(security_service):
    service, _, clock, cookie, _ = security_service
    csrf = service.get_csrf_token(cookie)
    clock[0] = csrf.expires_at
    rejects(lambda: service.get_csrf_token(cookie), 401)
    rejects(lambda: service.logout(cookie, csrf.token), 401)


@pytest.mark.parametrize("verifier", [None, lambda _: False, lambda _: 1, lambda _: object()])
def test_execution_requires_explicit_boolean_permission(security_service, verifier):
    service, _, _, _, reference = security_service
    called = []
    rejects(lambda: service.execute_authenticated(reference, lambda _: called.append(True),
                                                  permission_verifier=verifier), 403)
    assert not called


def test_execution_reference_owner_checked(security_service):
    service, _, _, _, reference = security_service
    forged = reference.model_copy(update={"user_id": uuid4()})
    rejects(lambda: service.revalidate_execution(forged, permission_verifier=lambda _: True), 401)


def test_permission_callback_cannot_keep_expired_actor(security_service):
    service, _, clock, _, reference = security_service
    called = []

    def verifier(actor):
        clock[0] = actor.expires_at
        return True

    rejects(lambda: service.execute_authenticated(reference, lambda _: called.append(True),
                                                  permission_verifier=verifier), 401)
    assert not called


def test_permission_callback_revocation_prevents_operation(security_service):
    service, engine, clock, _, reference = security_service
    called = []

    def verifier(_):
        with Session(engine) as session, session.begin():
            session.get(AuthSession, reference.session_id).revoked_at = clock[0]
        return True

    rejects(lambda: service.execute_authenticated(reference, lambda _: called.append(True),
                                                  permission_verifier=verifier), 401)
    assert not called


def test_positive_execution_has_current_actor(security_service):
    service, _, _, cookie, reference = security_service
    assert reference == service.create_execution_reference(cookie)
    assert service.execute_authenticated(reference, lambda actor: actor.user_id,
                                         permission_verifier=lambda _: True) == reference.user_id


def policy():
    return AdminAssurancePolicy(enabled=True, trusted_issuer="https://idp.test.invalid/realms/students",
        admin_client_id="T06_SYNTHETIC_ADMIN_CLIENT", student_client_id="T06_SYNTHETIC_STUDENT_CLIENT",
        allowed_acr=("T06_SYNTHETIC_STRONG_AUTH",), required_amr=("T06_SYNTHETIC_PASSWORD", "T06_SYNTHETIC_OTP"),
        max_auth_age_seconds=300)


def proof(now):
    return SessionAssurance(acr="T06_SYNTHETIC_STRONG_AUTH",
        amr=("T06_SYNTHETIC_PASSWORD", "T06_SYNTHETIC_OTP"), auth_time=now)


def test_admin_strength_positive_does_not_create_roles(now):
    evidence, config = proof(now), policy()
    assert check_admin_assurance(evidence, issuer=config.trusted_issuer,
        client_id=config.admin_client_id, policy=config, now=now) is None
    assert "roles" not in evidence.model_dump()


@pytest.mark.parametrize("change", ["disabled", "missing", "issuer", "student", "acr", "amr", "old", "future", "forged_policy"])
def test_admin_strength_fail_closed(now, change):
    config, evidence, issuer, client = policy(), proof(now), policy().trusted_issuer, policy().admin_client_id
    if change == "disabled":
        config = AdminAssurancePolicy()
    elif change == "missing":
        evidence = None
    elif change == "issuer":
        issuer += "/"
    elif change == "student":
        client = config.student_client_id
    elif change == "acr":
        evidence = evidence.model_copy(update={"acr": "999999"})
    elif change == "amr":
        evidence = evidence.model_copy(update={"amr": ("T06_SYNTHETIC_PASSWORD",)})
    elif change == "old":
        evidence = evidence.model_copy(update={"auth_time": now - timedelta(seconds=301)})
    elif change == "future":
        evidence = evidence.model_copy(update={"auth_time": now + timedelta(seconds=1)})
    else:
        config = config.model_copy(update={"max_auth_age_seconds": True})
    rejects(lambda: check_admin_assurance(evidence, issuer=issuer, client_id=client, policy=config, now=now), 403)


def test_policy_requires_explicit_distinct_client_and_no_weakening():
    with pytest.raises(ValidationError):
        AdminAssurancePolicy(enabled=True)
    values = policy().model_dump()
    values["admin_client_id"] = values["student_client_id"]
    with pytest.raises(ValidationError):
        AdminAssurancePolicy(**values)


def test_old_session_admin_rejected_and_normal_session_valid(security_service):
    service, _, _, cookie, _ = security_service
    rejects(lambda: service.check_admin_assurance(cookie, permission_verifier=lambda _: True), 403)
    assert service.get_session(cookie).user_id


def configure_admin_fixture(service, engine, reference, now):
    config, evidence = policy(), proof(now)
    provider = service.settings.provider.model_copy(update={"client_id": config.admin_client_id})
    service.settings = SessionAuthSettings.model_validate(service.settings.model_copy(update={
        "provider": provider, "admin_assurance_policy": config}))
    with Session(engine) as session, session.begin():
        row = session.get(AuthSession, reference.session_id)
        row.verified_issuer, row.verified_client_id = config.trusted_issuer, config.admin_client_id
        row.assurance_acr, row.assurance_amr, row.assurance_auth_time = evidence.acr, list(evidence.amr), evidence.auth_time
    return config


def test_service_strength_checks_frozen_policy_and_explicit_permission(security_service):
    service, engine, clock, cookie, reference = security_service
    config = configure_admin_fixture(service, engine, reference, clock[0])
    assert service.check_admin_assurance(cookie, config, permission_verifier=lambda _: True).user_id == reference.user_id
    rejects(lambda: service.check_admin_assurance(cookie, config), 403)
    weaker = config.model_copy(update={"max_auth_age_seconds": 3600})
    rejects(lambda: service.check_admin_assurance(cookie, weaker, permission_verifier=lambda _: True), 403)


@pytest.mark.parametrize("change", ["proof", "provenance", "policy"])
def test_admin_rechecks_current_proof_and_policy_after_permission_callback(security_service, change):
    service, engine, clock, cookie, reference = security_service
    configure_admin_fixture(service, engine, reference, clock[0])

    def permission(_):
        if change == "policy":
            service.settings = service.settings.model_copy(update={"admin_assurance_policy": AdminAssurancePolicy()})
        else:
            with Session(engine) as session, session.begin():
                row = session.get(AuthSession, reference.session_id)
                if change == "proof":
                    row.assurance_acr = "T06_SYNTHETIC_WEAK_AUTH"
                else:
                    row.verified_client_id = "T06_SYNTHETIC_STUDENT_CLIENT"
        return True

    rejects(lambda: service.check_admin_assurance(cookie, permission_verifier=permission), 403)


def test_execution_rechecks_permission_at_operation_boundary(security_service):
    service, _, _, _, reference = security_service
    calls, operation_calls = [], []

    def permission(_):
        calls.append(True)
        return len(calls) == 1

    rejects(lambda: service.execute_authenticated(reference, lambda _: operation_calls.append(True),
                                                  permission_verifier=permission), 403)
    assert len(calls) == 2
    assert not operation_calls


def test_corrupted_csrf_ciphertext_is_safe_unavailable(security_service):
    service, engine, _, cookie, reference = security_service
    service.get_csrf_token(cookie)
    with Session(engine) as session, session.begin():
        session.get(AuthSession, reference.session_id).csrf_encrypted_token = "T06_SYNTHETIC_CORRUPTED_CIPHER"
    rejects(lambda: service.get_csrf_token(cookie), 503)
