"""Real PostgreSQL adult/consent transitions and transactional composition."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from services.api.app.auth.authorization import Authorizer
from services.api.app.auth.config import AuthFlowError
from services.api.app.auth.models import AuthUser
from services.api.app.privacy.config import PrivacySettings
from services.api.app.privacy.models import PrivacyAdmissionRecord, PrivacyNoticeVersion
from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput
from services.api.app.privacy.service import PrivacyService


pytestmark = pytest.mark.postgres


def rejected(status, operation):
    with pytest.raises(AuthFlowError) as caught:
        operation()
    assert caught.value.status_code == status


def declare(service, principal, age_band="18_plus", revision=None, notice_id=None):
    current = service.get_admission(principal)
    return service.declare_age(principal, AgeDeclarationInput(age_band=age_band, confirmed=True,
        notice_id=notice_id or current.notice_id, expected_revision=current.revision if revision is None else revision))


def admit(service, principal):
    current = declare(service, principal)
    return service.confirm_core(principal, CoreConsentInput(purpose="core_consultation", confirmed=True,
        notice_id=current.notice_id, expected_revision=current.revision))


def guard(service, principal, purpose="core_consultation"):
    with Session(service.auth_service.store.engine) as session, session.begin():
        return service.require_purpose(session, principal, purpose)


def test_adult_confirmation_and_idempotent_owner_withdrawal(privacy_service, principal_factory, pg_engine):
    principal = principal_factory()
    empty = privacy_service.get_admission(principal)
    assert empty.revision == 0 and empty.reason == "age_missing" and empty.notice_id is not None
    declared = declare(privacy_service, principal)
    assert declared.age_assurance == "declared" and declared.reason == "consent_missing"
    consent = privacy_service.confirm_core(principal, CoreConsentInput(purpose="core_consultation", confirmed=True,
        notice_id=declared.notice_id, expected_revision=declared.revision))
    assert consent.core_consultation_allowed and not consent.private_business_available
    assert guard(privacy_service, principal).consent_id == consent.consent_id
    withdrawn = privacy_service.withdraw_core(principal, consent.consent_id)
    assert not withdrawn.core_consultation_allowed and withdrawn.reason == "consent_withdrawn"
    assert privacy_service.withdraw_core(principal, consent.consent_id) == withdrawn
    with Session(pg_engine) as session:
        rows = session.scalars(select(PrivacyAdmissionRecord).order_by(PrivacyAdmissionRecord.revision)).all()
        assert [row.event_type for row in rows] == ["adult_declared", "consent_confirmed", "consent_withdrawn"]
        assert [row.revision for row in rows] == [1, 2, 3]
    rejected(403, lambda: guard(privacy_service, principal))


@pytest.mark.parametrize("band", ["unknown", "under_14", "14_17"])
def test_initial_nonadult_rejection_saves_no_associated_age(privacy_service, principal_factory, pg_engine, band):
    principal = principal_factory()
    rejected(403, lambda: declare(privacy_service, principal, band))
    with Session(pg_engine) as session:
        assert session.scalar(select(func.count()).select_from(PrivacyAdmissionRecord)) == 0
    assert privacy_service.get_admission(principal).age_band is None


@pytest.mark.parametrize("band", ["unknown", "under_14", "14_17"])
def test_adult_changed_to_nonadult_invalidates_previous_positive(privacy_service, principal_factory, pg_engine, band):
    principal = principal_factory()
    admit(privacy_service, principal)
    rejected(403, lambda: declare(privacy_service, principal, band))
    latest = privacy_service.get_admission(principal)
    assert latest.age_band is None and latest.age_assurance == "unknown" and not latest.core_consultation_allowed
    assert latest.revision == 3
    with Session(pg_engine) as session:
        rows = session.scalars(select(PrivacyAdmissionRecord).where(PrivacyAdmissionRecord.user_id == principal.user_id)).all()
        assert {row.age_band for row in rows} == {None, "18_plus"}
        assert rows[-1].event_type == "admission_invalidated"
    rejected(403, lambda: guard(privacy_service, principal))


def test_redeclaration_requires_new_consent_and_old_withdrawal_does_not_touch_new(privacy_service, principal_factory):
    principal = principal_factory()
    original = admit(privacy_service, principal)
    next_age = declare(privacy_service, principal)
    assert next_age.consent_status == "invalidated" and not next_age.core_consultation_allowed
    new = privacy_service.confirm_core(principal, CoreConsentInput(purpose="core_consultation", confirmed=True,
        notice_id=next_age.notice_id, expected_revision=next_age.revision))
    assert new.consent_id != original.consent_id
    assert privacy_service.withdraw_core(principal, original.consent_id) == new
    assert guard(privacy_service, principal).core_consultation_allowed


@pytest.mark.parametrize("state", ["stale_revision", "wrong_notice", "damaged_notice", "closed"])
def test_nonadult_revocation_cannot_be_blocked_by_positive_write_proofs(privacy_service, principal_factory, pg_engine, state):
    principal = principal_factory()
    current = admit(privacy_service, principal)
    notice_id = uuid4() if state == "wrong_notice" else current.notice_id
    if state == "damaged_notice":
        with Session(pg_engine) as session, session.begin():
            session.execute(update(PrivacyNoticeVersion).values(text_sha256="0" * 64))
    elif state == "closed":
        privacy_service.settings = PrivacySettings()
    rejected(403, lambda: privacy_service.declare_age(principal, AgeDeclarationInput(age_band="14_17", confirmed=True,
        notice_id=notice_id, expected_revision=0)))
    with Session(pg_engine) as session:
        latest = session.scalar(select(PrivacyAdmissionRecord).order_by(PrivacyAdmissionRecord.revision.desc()).limit(1))
        assert latest.age_band is None and latest.age_assurance == "unknown" and latest.consent_status == "invalidated"
        assert latest.revision == current.revision + 1
    rejected(503 if state in {"damaged_notice", "closed"} else 403, lambda: guard(privacy_service, principal))


def test_revision_notice_and_actor_binding(privacy_service, principal_factory):
    alice, bob = principal_factory(), principal_factory()
    consent = admit(privacy_service, alice)
    rejected(409, lambda: declare(privacy_service, alice, revision=0))
    rejected(409, lambda: declare(privacy_service, alice, notice_id=uuid4()))
    rejected(404, lambda: privacy_service.withdraw_core(bob, consent.consent_id))
    assert privacy_service.get_admission(bob).revision == 0
    assert privacy_service.get_admission(alice).core_consultation_allowed


def test_declaration_absolute_expiry_does_not_slide(privacy_service, principal_factory, clock):
    principal = principal_factory(lifetime=20000)
    state = admit(privacy_service, principal)
    clock.advance(100)
    assert privacy_service.get_admission(principal).declaration_expires_at == state.declaration_expires_at
    clock.advance(7100)
    assert privacy_service.get_admission(principal).reason == "age_expired"
    rejected(403, lambda: guard(privacy_service, principal))


@pytest.mark.parametrize("mode", ["role", "user", "session"])
def test_current_auth_state_is_rechecked_before_processing(privacy_service, actor_factory, auth_service, pg_engine, clock, mode):
    actor = actor_factory()
    principal = auth_service.get_principal(actor.cookie)
    admit(privacy_service, principal)
    if mode == "role":
        auth_service.store.revoke_role(actor.user_id, "student", now=clock())
        assert privacy_service.get_admission(principal).reason == "role_missing"
        rejected(403, lambda: guard(privacy_service, principal))
    elif mode == "user":
        with Session(pg_engine) as session, session.begin():
            session.execute(update(AuthUser).where(AuthUser.id == actor.user_id).values(status="disabled"))
        rejected(401, lambda: guard(privacy_service, principal))
    else:
        token = auth_service.get_csrf_token(actor.cookie).token
        auth_service.logout(actor.cookie, token)
        rejected(401, lambda: guard(privacy_service, principal))


def test_role_does_not_replace_consent_and_settings_remain_accessible_without_student(privacy_service, principal_factory):
    student, administrator = principal_factory(), principal_factory(role="data_admin")
    rejected(403, lambda: guard(privacy_service, student))
    state = admit(privacy_service, administrator)
    assert state.reason == "role_missing" and state.consent_status == "active"
    withdrawn = privacy_service.withdraw_core(administrator, state.consent_id)
    assert withdrawn.consent_status == "withdrawn"


@pytest.mark.parametrize("roll", ["notice", "policy"])
def test_notice_policy_roll_requires_declaration_and_confirmation_again(privacy_service, principal_factory, pg_engine, clock, roll):
    principal = principal_factory()
    state = admit(privacy_service, principal)
    new_id = uuid4()
    settings = privacy_service.settings.model_copy(update={"notice_id": new_id,
        "policy_version": "T08_changed_policy" if roll == "policy" else privacy_service.settings.policy_version})
    with Session(pg_engine) as session, session.begin():
        old = session.get(PrivacyNoticeVersion, state.notice_id)
        session.add(PrivacyNoticeVersion(id=new_id, version="T08_changed_notice", policy_version=settings.policy_version,
            text=old.text, text_sha256=old.text_sha256, controller_reference=settings.controller_reference,
            review_status="test_reviewed", reviewed_at=clock(), is_synthetic=True))
    privacy_service.settings = settings
    assert privacy_service.get_admission(principal).reason == ("policy_changed" if roll == "policy" else "notice_changed")
    rejected(403, lambda: guard(privacy_service, principal))
    rejected(403, lambda: privacy_service.confirm_core(principal, CoreConsentInput(purpose="core_consultation",
        confirmed=True, notice_id=new_id, expected_revision=state.revision)))
    assert admit(privacy_service, principal).core_consultation_allowed


def test_default_closed_rejects_real_writes_but_retains_owner_withdrawal(privacy_service, principal_factory, auth_service):
    principal = principal_factory()
    state = admit(privacy_service, principal)
    closed = PrivacyService(auth_service)
    assert not closed.current_notice().readiness
    assert closed.get_admission(principal).reason == "processing_disabled"
    rejected(503, lambda: closed.declare_age(principal, AgeDeclarationInput(age_band="18_plus", confirmed=True,
        notice_id=state.notice_id, expected_revision=state.revision)))
    withdrawn = closed.withdraw_core(principal, state.consent_id)
    assert withdrawn.consent_status == "withdrawn" and not withdrawn.readiness


def test_guard_requires_current_transaction_engine_and_fixed_purpose(privacy_service, principal_factory, pg_engine):
    principal = principal_factory()
    admit(privacy_service, principal)
    rejected(403, lambda: guard(privacy_service, principal, "marketing"))
    with Session(pg_engine) as idle:
        rejected(503, lambda: privacy_service.require_purpose(idle, principal, "core_consultation"))


def test_actor_binding_is_per_root_transaction_and_rollback_does_not_poison_reuse(privacy_service, principal_factory, pg_engine):
    alice, bob = principal_factory(), principal_factory()
    admit(privacy_service, alice)
    admit(privacy_service, bob)
    with Session(pg_engine) as session:
        with session.begin():
            privacy_service.require_purpose(session, alice, "core_consultation")
            rejected(403, lambda: privacy_service.require_purpose(session, bob, "core_consultation"))
        with session.begin():
            assert privacy_service.require_purpose(session, bob, "core_consultation").user_id == bob.user_id
        session.begin()
        privacy_service.require_purpose(session, alice, "core_consultation")
        session.rollback()
        with session.begin():
            assert privacy_service.require_purpose(session, bob, "core_consultation").core_consultation_allowed


def test_object_and_purpose_guard_share_one_transaction_and_fail_after_withdrawal(privacy_service, principal_factory, auth_service, pg_engine):
    principal = principal_factory()
    state = admit(privacy_service, principal)
    authorizer = Authorizer(auth_service)
    resource = authorizer.register_owned(principal, "profile")
    seen = []
    def operation(session, actor, owned):
        result = privacy_service.require_purpose(session, actor, "core_consultation")
        assert result.user_id == owned.owner_user_id
        seen.append(result.user_id)
        return "synthetic_effect"
    assert authorizer.execute_owned(principal, "profile", resource.id, "write", operation) == "synthetic_effect"
    privacy_service.withdraw_core(principal, state.consent_id)
    rejected(403, lambda: authorizer.execute_owned(principal, "profile", resource.id, "write", operation))
    assert seen == [principal.user_id]


@pytest.mark.parametrize("model", ["copy", "construct"])
def test_forged_confirmation_revalidated_at_service(privacy_service, principal_factory, model):
    principal = principal_factory()
    valid = AgeDeclarationInput(age_band="18_plus", confirmed=True, notice_id=privacy_service.settings.notice_id,
        expected_revision=0)
    forged = valid.model_copy(update={"confirmed": 1}) if model == "copy" else AgeDeclarationInput.model_construct(
        **{**valid.model_dump(), "confirmed": 1})
    rejected(403, lambda: privacy_service.declare_age(principal, forged))
    assert privacy_service.get_admission(principal).revision == 0
