"""Independent T08 trust-boundary checks; fixtures are synthetic and offline."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident
import time
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.auth.authorization import Authorizer
from services.api.app.auth.config import AuthFlowError
from services.api.app.auth.models import AuthOwnedResource, AuthUser
from services.api.app.auth.router import SESSION_COOKIE
from services.api.app.privacy.config import PrivacySettings
from services.api.app.privacy.errors import PrivacyError
from services.api.app.privacy.models import PrivacyAdmissionRecord, PrivacyNoticeVersion
from services.api.app.privacy.policy import hash_text
from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput


NOTICE_ID = UUID("d648c6b6-959d-44d8-86db-6c85c47160b9")
PRIVATE_MARKER = "T08_ADVERSARIAL_PRIVATE_SENTINEL"


def fixture_configuration():
    return PrivacySettings(
        fixture_mode=True,
        notice_id=NOTICE_ID,
        controller_reference="DEMO_T08_SYNTHETIC_CONTROLLER",
        age_assurance_method="adult_self_declaration",
        declaration_validity_seconds=300,
    )


def declaration_payload():
    return {
        "age_band": "18_plus", "confirmed": True,
        "notice_id": str(NOTICE_ID), "expected_revision": 0,
    }


def consent_payload():
    return {
        "purpose": "core_consultation", "confirmed": True,
        "notice_id": str(NOTICE_ID), "expected_revision": 0,
    }


@pytest.mark.parametrize("model,payload", [
    (AgeDeclarationInput, declaration_payload), (CoreConsentInput, consent_payload),
])
@pytest.mark.parametrize("value", [1, 1.0, 0, False, None, "true", "True", [], {}])
def test_confirmation_requires_actual_json_boolean_true(model, payload, value):
    """JSON numeric equality to True is not an explicit Boolean confirmation."""
    with pytest.raises(ValidationError):
        model.model_validate({**payload(), "confirmed": value})


@pytest.mark.parametrize("model,payload", [
    (AgeDeclarationInput, declaration_payload), (CoreConsentInput, consent_payload),
])
@pytest.mark.parametrize("field", [
    "owner_user_id", "user_id", "role", "is_synthetic", "verified",
    "guardian_verified", "controller_reference", "production_reviewed",
])
def test_external_payload_cannot_create_trusted_authority(model, payload, field):
    with pytest.raises(ValidationError) as denied:
        model.model_validate({**payload(), field: PRIVATE_MARKER})
    # Direct structured Pydantic errors may contain input and must not be logged;
    # the standard displayed error follows the project's hidden-input policy.
    assert PRIVATE_MARKER not in str(denied.value)
    assert PRIVATE_MARKER not in repr(denied.value)


@pytest.mark.parametrize("model,payload", [
    (AgeDeclarationInput, declaration_payload), (CoreConsentInput, consent_payload),
])
@pytest.mark.parametrize("revision", [True, False, "0", 0.0, -1])
def test_revision_is_an_integer_concurrency_proof(model, payload, revision):
    with pytest.raises(ValidationError):
        model.model_validate({**payload(), "expected_revision": revision})


@pytest.mark.parametrize("changes", [
    {"fixture_mode": False}, {"notice_id": None},
    {"age_assurance_method": "verified_age"},
    {"declaration_validity_seconds": True},
    {"declaration_validity_seconds": 0},
    {"declaration_validity_seconds": 31536001},
])
@pytest.mark.parametrize("forgery", ["copy", "construct"])
def test_forged_internal_configuration_is_revalidated(changes, forgery):
    valid = fixture_configuration()
    if forgery == "copy":
        forged = valid.model_copy(update=changes)
    else:
        forged = PrivacySettings.model_construct(**{**valid.model_dump(), **changes})
    with pytest.raises(ValidationError):
        PrivacySettings.model_validate(forged)


@pytest.mark.parametrize("field,value", [
    ("controller_reference", "DEMO_T08_SYNTHETIC_CONTROLLER"),
    ("notice_id", NOTICE_ID),
    ("age_assurance_method", "adult_self_declaration"),
    ("declaration_validity_seconds", 300),
    ("real_processing_enabled", True),
    ("production_reviewed", True),
])
def test_real_readiness_cannot_be_claimed_by_a_placeholder(field, value):
    with pytest.raises(ValidationError):
        PrivacySettings.model_validate({field: value})


def test_process_environment_cannot_enable_fixture_or_real_processing(monkeypatch):
    for field, value in {
        "PRIVACY_FIXTURE_MODE": "true",
        "PRIVACY_CONTROLLER_REFERENCE": "DEMO_T08_SYNTHETIC_CONTROLLER",
        "PRIVACY_REAL_PROCESSING_ENABLED": "true",
        "PRIVACY_PRODUCTION_REVIEWED": "true",
        "V2_PRIVACY_FIXTURE_MODE": "true",
    }.items():
        monkeypatch.setenv(field, value)
    configuration = PrivacySettings()
    assert configuration.fixture_mode is False
    assert configuration.controller_reference is None
    assert configuration.age_assurance_method == "unconfigured"
    assert configuration.notice_id is None
    with pytest.raises(ValidationError):
        configuration.fixture_mode = True


def admit(privacy_service, principal):
    notice = privacy_service.current_notice()
    current = privacy_service.get_admission(principal)
    declared = privacy_service.declare_age(principal, AgeDeclarationInput(
        age_band="18_plus", confirmed=True, notice_id=notice.notice_id,
        expected_revision=current.revision))
    return privacy_service.confirm_core(principal, CoreConsentInput(
        purpose="core_consultation", confirmed=True, notice_id=notice.notice_id,
        expected_revision=declared.revision))


def write_headers(auth_service, actor):
    token = auth_service.get_csrf_token(actor.cookie).token.get_secret_value()
    return {"Cookie": f"{SESSION_COOKIE}={actor.cookie.get_secret_value()}",
            "Origin": "https://app.test.invalid", "X-CSRF-Token": token}


def assert_private_response(response, status):
    assert response.status_code == status, response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    body = response.json()
    identifier = body["error"]["request_id"] if status >= 400 else body["meta"]["request_id"]
    assert response.headers["X-Request-ID"] == identifier
    assert PRIVATE_MARKER not in response.text


@pytest.mark.postgres
@pytest.mark.parametrize("route,payload", [
    ("/me/age-declarations", declaration_payload), ("/me/consents", consent_payload),
])
@pytest.mark.parametrize("value", [1, 1.0])
def test_http_numeric_confirmation_never_appends_admission(
    client, auth_service, actor_factory, privacy_settings, pg_engine, route, payload, value,
):
    actor = actor_factory()
    body = {**payload(), "notice_id": str(privacy_settings.notice_id), "confirmed": value}
    response = client.post(route, json=body, headers=write_headers(auth_service, actor))
    assert_private_response(response, 422)
    with Session(pg_engine) as database:
        assert database.scalar(select(func.count()).select_from(PrivacyAdmissionRecord)) == 0


@pytest.mark.postgres
@pytest.mark.parametrize("age_band", ["unknown", "under_14", "14_17"])
@pytest.mark.parametrize("had_admission", [False, True])
def test_rejected_nonadult_does_not_preserve_an_old_private_permission(
    client, auth_service, actor_factory, privacy_service, privacy_settings, pg_engine,
    age_band, had_admission,
):
    actor = actor_factory()
    principal = auth_service.get_principal(actor.cookie)
    old = admit(privacy_service, principal) if had_admission else privacy_service.get_admission(principal)
    response = client.post("/me/age-declarations", json={
        "age_band": age_band, "confirmed": True, "notice_id": str(privacy_settings.notice_id),
        "expected_revision": old.revision}, headers=write_headers(auth_service, actor))
    assert_private_response(response, 403)
    current = privacy_service.get_admission(principal)
    assert current.core_consultation_allowed is False
    assert current.age_band is None and current.age_assurance == "unknown"
    assert current.revision == old.revision + int(had_admission)
    with Session(pg_engine) as database:
        rows = database.scalars(select(PrivacyAdmissionRecord).where(
            PrivacyAdmissionRecord.user_id == actor.user_id)).all()
        assert all(row.age_band in (None, "18_plus") for row in rows)
        assert len(rows) == (3 if had_admission else 0)
    with Session(pg_engine) as database, database.begin(), pytest.raises(PrivacyError) as refused:
        privacy_service.require_purpose(database, principal, "core_consultation")
    assert refused.value.status_code == 403


@pytest.mark.postgres
def test_old_withdrawal_is_idempotent_and_cannot_withdraw_a_new_confirmation(
    client, auth_service, actor_factory, privacy_service,
):
    actor = actor_factory()
    principal = auth_service.get_principal(actor.cookie)
    first = admit(privacy_service, principal)
    headers = write_headers(auth_service, actor)
    withdrawn = client.delete(f"/me/consents/{first.consent_id}", headers=headers)
    assert_private_response(withdrawn, 200)
    revision = withdrawn.json()["data"]["revision"]
    second = privacy_service.confirm_core(principal, CoreConsentInput(
        purpose="core_consultation", confirmed=True, notice_id=first.notice_id,
        expected_revision=revision))
    replay = client.delete(f"/me/consents/{first.consent_id}", headers=headers)
    assert_private_response(replay, 200)
    data = replay.json()["data"]
    assert data["revision"] == second.revision
    assert data["consent_id"] == str(second.consent_id)
    assert data["consent_status"] == "active"
    assert data["core_consultation_allowed"] is True
    assert data["private_business_available"] is False


@pytest.mark.postgres
@pytest.mark.parametrize("damage", ["hash", "text", "policy", "review", "synthetic"])
def test_damaged_notice_closes_guard_but_owner_withdrawal_still_commits(
    client, auth_service, actor_factory, privacy_service, privacy_settings, pg_engine, damage,
):
    actor = actor_factory()
    principal = auth_service.get_principal(actor.cookie)
    active = admit(privacy_service, principal)
    with Session(pg_engine) as database, database.begin():
        notice = database.get(PrivacyNoticeVersion, privacy_settings.notice_id)
        if damage == "hash":
            notice.text_sha256 = "0" * 64
        elif damage == "text":
            notice.text = PRIVATE_MARKER
        elif damage == "policy":
            notice.policy_version = "T08_unreviewed_changed_policy"
        elif damage == "review":
            notice.review_status = "reviewed"
        else:
            notice.is_synthetic = False
    with Session(pg_engine) as database, database.begin(), pytest.raises(PrivacyError) as refused:
        privacy_service.require_purpose(database, principal, "core_consultation")
    assert refused.value.status_code == 503
    response = client.delete(f"/me/consents/{active.consent_id}",
                             headers=write_headers(auth_service, actor))
    assert_private_response(response, 200)
    assert response.json()["data"]["consent_status"] == "withdrawn"
    assert response.json()["data"]["readiness"] is False
    assert response.json()["data"]["core_consultation_allowed"] is False
    with Session(pg_engine) as database:
        latest = database.scalar(select(PrivacyAdmissionRecord).where(
            PrivacyAdmissionRecord.user_id == actor.user_id).order_by(PrivacyAdmissionRecord.revision.desc()))
        assert latest.consent_status == "withdrawn"
        assert latest.revision == active.revision + 1


@pytest.mark.postgres
def test_foreign_consent_reference_never_changes_either_owner(
    client, auth_service, actor_factory, privacy_service,
):
    actors = [actor_factory(), actor_factory()]
    principals = [auth_service.get_principal(actor.cookie) for actor in actors]
    states = [admit(privacy_service, principal) for principal in principals]
    response = client.delete(f"/me/consents/{states[0].consent_id}",
                             headers=write_headers(auth_service, actors[1]))
    assert_private_response(response, 404)
    for principal, old in zip(principals, states):
        current = privacy_service.get_admission(principal)
        assert current.revision == old.revision and current.core_consultation_allowed is True


@pytest.mark.postgres
@pytest.mark.parametrize("failure", ["no_transaction", "wrong_engine"])
def test_purpose_guard_requires_the_callers_active_transaction(
    privacy_service, principal_factory, pg_engine, failure,
):
    principal = principal_factory()
    admit(privacy_service, principal)
    other = create_engine("sqlite+pysqlite:///:memory:") if failure == "wrong_engine" else None
    try:
        with Session(other or pg_engine) as database:
            if failure == "wrong_engine":
                database.begin()
            with pytest.raises(PrivacyError) as refused:
                privacy_service.require_purpose(database, principal, "core_consultation")
            assert refused.value.status_code == 503
    finally:
        if other is not None:
            other.dispose()


@pytest.mark.postgres
def test_same_transaction_cannot_borrow_another_actors_consent_and_new_transaction_can_rebind(
    privacy_service, principal_factory, pg_engine,
):
    first, second = principal_factory(), principal_factory()
    admit(privacy_service, first)
    admit(privacy_service, second)
    with Session(pg_engine) as database:
        with database.begin():
            assert privacy_service.require_purpose(database, first, "core_consultation").user_id == first.user_id
            with pytest.raises(AuthFlowError) as refused:
                privacy_service.require_purpose(database, second, "core_consultation")
            assert refused.value.status_code == 403
        with database.begin():
            assert privacy_service.require_purpose(database, second, "core_consultation").user_id == second.user_id


@pytest.mark.postgres
@pytest.mark.parametrize("changes", [
    {"age_band": None}, {"declaration_expires_at": None},
    {"declared_at": None}, {"declaration_notice_id": None},
    {"age_band": None, "age_assurance": "unknown", "declared_at": None,
     "declaration_expires_at": None, "declaration_notice_id": None},
])
def test_real_postgresql_rejects_null_unknown_check_bypasses(
    privacy_service, principal_factory, pg_engine, changes,
):
    principal = principal_factory()
    active = admit(privacy_service, principal)
    with Session(pg_engine) as database:
        original = database.get(PrivacyAdmissionRecord, active.consent_id)
        values = {column.name: getattr(original, column.name)
                  for column in PrivacyAdmissionRecord.__table__.columns}
    values.update(id=uuid4(), revision=active.revision + 1, **changes)
    with Session(pg_engine) as database, pytest.raises(IntegrityError):
        database.add(PrivacyAdmissionRecord(**values))
        database.commit()


@pytest.mark.postgres
def test_same_transaction_object_operation_stops_after_withdrawal(
    auth_service, privacy_service, principal_factory, pg_engine,
):
    principal = principal_factory()
    active = admit(privacy_service, principal)
    authorizer = Authorizer(auth_service)
    resource = authorizer.register_owned(principal, "profile")
    effects = []

    def consume(database, current, owned):
        allowed = privacy_service.require_purpose(database, current, "core_consultation")
        assert allowed.user_id == owned.owner_user_id
        effects.append(owned.id)

    authorizer.execute_owned(principal, "profile", resource.id, "read", consume)
    assert effects == [resource.id]
    privacy_service.withdraw_core(principal, active.consent_id)
    with pytest.raises(AuthFlowError) as refused:
        authorizer.execute_owned(principal, "profile", resource.id, "read", consume)
    assert refused.value.status_code == 403
    assert effects == [resource.id]
    with Session(pg_engine) as database:
        assert database.get(AuthOwnedResource, resource.id).version == resource.version


@pytest.mark.postgres
@pytest.mark.parametrize("change", ["notice", "policy"])
def test_changed_notice_requires_new_age_confirmation_and_can_then_be_confirmed(
    privacy_service, principal_factory, pg_engine, clock, change,
):
    principal = principal_factory()
    active = admit(privacy_service, principal)
    new_id = uuid4()
    policy = "T08_product_v2" if change == "policy" else privacy_service.settings.policy_version
    with Session(pg_engine) as database, database.begin():
        old = database.get(PrivacyNoticeVersion, active.notice_id)
        revised_text = old.text + " 合成新版告知。"
        database.add(PrivacyNoticeVersion(id=new_id, version="T08_SYNTHETIC_NOTICE_v2",
            policy_version=policy, text=revised_text, text_sha256=hash_text(revised_text),
            controller_reference=old.controller_reference, review_status="test_reviewed",
            reviewed_at=clock(), is_synthetic=True))
    privacy_service.settings = PrivacySettings.model_validate(privacy_service.settings.model_copy(
        update={"notice_id": new_id, "policy_version": policy}))
    state = privacy_service.get_admission(principal)
    assert state.core_consultation_allowed is False
    with pytest.raises(PrivacyError) as refused:
        privacy_service.confirm_core(principal, CoreConsentInput(purpose="core_consultation",
            confirmed=True, notice_id=new_id, expected_revision=state.revision))
    assert refused.value.status_code == 403
    assert privacy_service.get_admission(principal).revision == active.revision
    with pytest.raises(PrivacyError) as stale:
        privacy_service.declare_age(principal, AgeDeclarationInput(age_band="18_plus", confirmed=True,
            notice_id=active.notice_id, expected_revision=state.revision))
    assert stale.value.status_code == 409
    declared = privacy_service.declare_age(principal, AgeDeclarationInput(age_band="18_plus",
        confirmed=True, notice_id=new_id, expected_revision=state.revision))
    assert declared.core_consultation_allowed is False
    renewed = privacy_service.confirm_core(principal, CoreConsentInput(purpose="core_consultation",
        confirmed=True, notice_id=new_id, expected_revision=declared.revision))
    assert renewed.core_consultation_allowed is True
    assert renewed.consent_id != active.consent_id
    assert renewed.notice_id == new_id and renewed.policy_version == policy


def _observe_lock(engine, reached, pids, worker_identity):
    def observe(connection, cursor, statement, parameters, context, executemany):
        if worker_identity and get_ident() == worker_identity[0] and "FOR UPDATE" in statement.upper():
            pids.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar_one())
            reached.set()
    event.listen(engine, "before_cursor_execute", observe)
    return observe


def _require_lock_wait(engine, reached, pids):
    assert reached.wait(5), "Privacy worker never issued its account lock"
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with engine.connect() as database:
            waiting = database.scalar(text(
                "SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid=:pid"), {"pid": pids[0]})
        if waiting:
            return
        time.sleep(0.01)
    pytest.fail("PostgreSQL did not report a real privacy worker lock wait")


@pytest.mark.postgres
def test_lock_wait_cannot_use_a_declaration_that_expires_before_execution(
    auth_service, actor_factory, privacy_service, pg_engine, clock, privacy_settings,
):
    actor = actor_factory(lifetime=12000)
    principal = auth_service.get_principal(actor.cookie)
    admit(privacy_service, principal)
    reached, pids, identity, effects = Event(), [], [], []

    def attempt():
        identity.append(get_ident())
        try:
            with Session(pg_engine) as database, database.begin():
                privacy_service.require_purpose(database, principal, "core_consultation")
                effects.append("private_operation")
            return 200
        except AuthFlowError as error:
            return error.status_code

    with Session(pg_engine) as locker:
        locker.scalar(select(AuthUser).where(AuthUser.id == principal.user_id).with_for_update())
        listener = _observe_lock(pg_engine, reached, pids, identity)
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            pending = executor.submit(attempt)
            _require_lock_wait(pg_engine, reached, pids)
            clock.advance(privacy_settings.declaration_validity_seconds)
            locker.commit()
            assert pending.result(timeout=10) == 403
            assert effects == []
        finally:
            locker.rollback()
            executor.shutdown(wait=True)
            event.remove(pg_engine, "before_cursor_execute", listener)


@pytest.mark.postgres
def test_withdrawal_serializes_after_local_private_transaction_and_blocks_the_next(
    privacy_service, principal_factory, pg_engine,
):
    principal = principal_factory()
    active = admit(privacy_service, principal)
    reached, pids, identity = Event(), [], []

    def withdraw():
        identity.append(get_ident())
        return privacy_service.withdraw_core(principal, active.consent_id)

    with Session(pg_engine) as operation:
        operation.begin()
        assert privacy_service.require_purpose(operation, principal, "core_consultation").core_consultation_allowed
        listener = _observe_lock(pg_engine, reached, pids, identity)
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            pending = executor.submit(withdraw)
            _require_lock_wait(pg_engine, reached, pids)
            assert not pending.done()
            operation.commit()
            assert pending.result(timeout=10).consent_status == "withdrawn"
        finally:
            operation.rollback()
            executor.shutdown(wait=True)
            event.remove(pg_engine, "before_cursor_execute", listener)
    with Session(pg_engine) as operation, operation.begin(), pytest.raises(PrivacyError) as refused:
        privacy_service.require_purpose(operation, principal, "core_consultation")
    assert refused.value.status_code == 403


@pytest.mark.postgres
@pytest.mark.parametrize("operation", ["declare", "confirm", "withdraw"])
@pytest.mark.parametrize("bad_proof", ["missing_csrf", "wrong_origin", "duplicate_csrf"])
def test_all_new_privacy_writes_enforce_the_central_cookie_write_boundary(
    client, auth_service, actor_factory, privacy_service, operation, bad_proof,
):
    actor = actor_factory()
    principal = auth_service.get_principal(actor.cookie)
    active = admit(privacy_service, principal)
    headers = write_headers(auth_service, actor)
    if bad_proof == "missing_csrf":
        headers.pop("X-CSRF-Token")
    elif bad_proof == "wrong_origin":
        headers["Origin"] = f"https://{PRIVATE_MARKER}.invalid"
    else:
        headers = [*headers.items(), ("X-CSRF-Token", headers["X-CSRF-Token"])]
    if operation == "withdraw":
        response = client.delete(f"/me/consents/{active.consent_id}", headers=headers)
    else:
        route = "/me/age-declarations" if operation == "declare" else "/me/consents"
        body = declaration_payload() if operation == "declare" else consent_payload()
        body.update(notice_id=str(active.notice_id), expected_revision=active.revision)
        response = client.post(route, json=body, headers=headers)
    assert_private_response(response, 403)
    after = privacy_service.get_admission(principal)
    assert after.revision == active.revision
    assert after.consent_id == active.consent_id
    assert after.consent_status == "active" and after.core_consultation_allowed is True
