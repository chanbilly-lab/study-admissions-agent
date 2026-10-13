"""Reuse real T35 services with per-schema fixtures and a loopback OIDC origin."""

import secrets
from types import SimpleNamespace

import pytest

from tests.integration.plan_revisions.conftest import (
    pg_engine, clock, runtime, idp, oidc_adapter, auth_store, auth_service,
    actor_factory, privacy_settings, privacy_service, catalog_store, catalog_tree,
    source_store, administrator_factory, source_request_factory, blob_root,
    io_probe, storage_store, storage_factory, idempotency_store, imports_store,
    imports_factory, candidate_factory, evidence_store, evidence_factory,
    facts_store, facts_factory, classification_factory, reviews_store,
    releases_store, import_case_factory, isolate_releases_environment_and_network,
    profiles_store, assessments_store, assessment_case_factory, plans_store,
    plan_case_factory, execution_store, execution_case_factory, changes_store,
    change_case_factory, revisions_store, revision_case_factory,
)
from tests.integration.catalog_ui.conftest import (
    browser_origin, session_settings_factory, session_settings,
)


@pytest.fixture
def workspace_factory(revision_case_factory, actor_factory):
    from services.api.app.api.revisions import create_revisions_app
    from services.api.app.plans.schemas import PlanCreateInput
    from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput

    def make():
        case = revision_case_factory()
        other = actor_factory()
        other_principal = case.auth.get_principal(other.cookie)
        privacy = case.profiles.privacy_service
        notice = privacy.settings.notice_id
        adult = privacy.declare_age(other_principal, AgeDeclarationInput(age_band="18_plus",
            confirmed=True, notice_id=notice, expected_revision=0))
        privacy.confirm_core(other_principal, CoreConsentInput(purpose="core_consultation",
            confirmed=True, notice_id=notice, expected_revision=adult.revision))
        reject_new = case.execution.create_plan(case.principal,
            PlanCreateInput(assessment_ids=(case.new_assessment.assessment_id,), confirmed=True))
        app = create_revisions_app(case.auth.runtime_settings, identity_service=case.auth,
            profile_service=case.profiles, assessment_service=case.eligibility,
            execution_service=case.execution, revision_service=case.service)
        fixture = {
            "owner_cookie": case.owner.cookie.get_secret_value(),
            "other_cookie": other.cookie.get_secret_value(),
            "user_id": str(case.principal.user_id),
            "other_user_id": str(other_principal.user_id),
            "profile_id": str(case.new_profile.profile_id),
            "profile_version_id": str(case.new_profile.version_id),
            "old_plan_id": str(case.old.plan_id), "new_plan_id": str(case.new.plan_id),
            "reject_new_plan_id": str(reject_new.plan_id),
            "old_completed_count": len(case.old.completed_tasks),
            "control_secret": secrets.token_urlsafe(32),
        }
        return SimpleNamespace(app=app, browser_fixture=fixture, case=case)
    return make
