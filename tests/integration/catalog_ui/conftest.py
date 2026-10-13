"""T29's synthetic public/private pipeline in a fresh, dedicated PG schema."""

from datetime import timedelta
import json
import os
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import SecretStr
import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from tests.integration.eligibility.conftest import (
    clock, runtime, idp, oidc_adapter, auth_store, auth_service, actor_factory,
    privacy_settings, privacy_service, catalog_store, catalog_tree, source_store,
    administrator_factory, source_request_factory, blob_root, io_probe, storage_store,
    storage_factory, idempotency_store, imports_store, imports_factory, candidate_factory,
    evidence_store, evidence_factory, facts_store, facts_factory, classification_factory,
    reviews_store, releases_store, import_case_factory, profiles_store, assessments_store,
    assessment_case_factory, isolate_releases_environment_and_network,
)
from tests.integration.auth.conftest import session_settings_factory as _base_settings_factory


@pytest.fixture
def pg_engine():
    url = os.getenv("T23_TEST_POSTGRES_URL")
    if not url:
        pytest.fail("Required T29 PG acceptance needs T23_TEST_POSTGRES_URL", pytrace=False)
    parsed = urlsplit(url)
    if (parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1"
            or parsed.path != "/study_t23_20261003"):
        pytest.fail("T29 requires the dedicated loopback study_t23_20261003 database", pytrace=False)
    schema = "catalog_ui_t29_" + uuid4().hex
    maintenance = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    engine, created = None, False
    try:
        with maintenance.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        created = True
        engine = create_engine(url, hide_parameters=True,
            connect_args={"options": "-csearch_path=" + schema, "connect_timeout": 5})
        assert inspect(engine).get_table_names() == []
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with maintenance.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        maintenance.dispose()


@pytest.fixture
def browser_origin():
    # The loopback server sets this before building the real service pipeline.
    return {"value": "https://app.test.invalid"}


@pytest.fixture
def session_settings_factory(browser_origin):
    from services.api.app.auth.config import SessionAuthSettings
    from services.api.app.auth.schemas import AuthProviderSettings
    defaults = _base_settings_factory.__wrapped__()
    def make(**changes):
        base = defaults(**changes)
        callback = browser_origin["value"] + "/api/v2/auth/callback"
        provider = AuthProviderSettings.model_validate({**base.provider.model_dump(),
            "callback_allowlist": (callback,)})
        return SessionAuthSettings.model_validate({**base.model_dump(), "provider": provider,
            "redirect_uri": callback})
    return make


@pytest.fixture
def session_settings(session_settings_factory):
    return session_settings_factory()


@pytest.fixture
def workspace_factory(assessment_case_factory, catalog_tree, catalog_store, candidate_factory,
        import_case_factory, evidence_factory, facts_factory, classification_factory,
        actor_factory, assessments_store, pg_engine, clock):
    """Actual T19 replacement makes the exact published snippets publicly readable.

    T28's historical fixture remains unchanged. The driver receives only cookies;
    all target/profile/evaluation IDs must be discovered by real HTTP requests.
    """
    from fastapi import FastAPI
    from services.api.app.admissions_catalog.models import CatalogDataset
    from services.api.app.admissions_catalog.schemas import OfferingInput, ScopeKey
    from services.api.app.admin.imports.models import ImportCandidateRow
    from services.api.app.api.assessments import create_assessments_v2_app
    from services.api.app.api.public_catalog import create_public_catalog_v2_app
    from services.api.app.evidence.schemas import DocumentCreate, VersionCreate, SnippetCreate
    from services.api.app.facts.schemas import FactCreate
    from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput
    from services.api.app.profiles.schemas import CreateInput
    from services.api.app.public_catalog.reader import CatalogReader
    from services.api.app.public_catalog.schemas import PublicCatalogPolicy
    from services.api.app.releases.schemas import PublishRequest, PublishMember
    from services.api.app.reviews.schemas import ReviewRequest, ReviewCheck, CHECK_FIELDS
    from services.api.app.rules.schemas import AssessmentPolicy
    from services.api.app.rules.service import EligibilityService
    from services.api.app.settings import V2RuntimeSettings

    def make():
        expression = {"op": "all", "children": [
            {"op": "gte", "field": {"name": "assessment", "key": key, "basis": "achieved"},
             "value": {"kind": "decimal", "value": value, "unit": "points", "scale": scale}}
            for key, value, scale in (("gaokao_total", "600", "750"), ("math", "90", "150"))]}
        case = assessment_case_factory(expression=expression, deferral=True)

        # A second actual offering in the same release has facts, but no trusted
        # rule binding. This exercises both SQL pagination and genuine unknown.
        extra = OfferingInput.model_validate({**catalog_tree.offering.model_dump(),
            "id": uuid4(), "reference_key": "DEMO_T29_SECOND_OFFERING",
            "channel": ScopeKey(status="known", value="DEMO_SECOND_CHANNEL")})
        with Session(pg_engine) as session, session.begin():
            catalog_store.create_offering(session, extra,
                expected_dataset_revision=catalog_store.get_dataset(session, extra.dataset_id).revision,
                version_id=uuid4())
        sentinel = "DEMO_<img src=https://source-sentinel.invalid/x onerror=window.__t29Xss=1>"
        row = candidate_factory(offering_id=str(extra.id), fact_type="requirement", field_key="DEMO_T29_INFORMATION",
            value_kind="text", value_text="DEMO_NO_APPROVED_RULESET", unit="text",
            footnote_state="present", footnote_text=sentinel)
        other = import_case_factory(rows=[row], ttl_seconds=86400)
        imported = other.service.import_file(other.admin.principal, other.request(), SecretStr("DEMO_T29_IMPORT"))
        evidence = evidence_factory(other.storage)
        document = evidence.create_document(other.admin.principal, DocumentCreate(dataset_id=extra.dataset_id,
            source_id=other.source.source_id, source_version=other.source.version,
            document_reference="DEMO_T29_SECOND_DOCUMENT", language="und"))
        evidence.create_version(other.admin.principal, VersionCreate(document_id=document.id,
            expected_current_version=0, file_id=other.file.id, file_sha256=other.file.sha256))
        snippet = evidence.create_snippet(other.admin.principal, SnippetCreate(document_id=document.id,
            document_version=1, offering_id=extra.id, offering_version=1, entry_year=2026,
            byte_start=0, byte_end=len(other.data)))
        with Session(pg_engine) as session:
            imported_row = session.scalar(select(ImportCandidateRow).where(ImportCandidateRow.import_id == imported.id))
            row_id = imported_row.id
        facts = facts_factory(other.storage, imports=other.service, evidence=evidence)
        fact = facts.create_fact(other.admin.principal, FactCreate(import_id=imported.id, import_row_id=row_id,
            classification=classification_factory(unit_code="text", claim_kind="information"), evidence_id=snippet.id))
        decision = case.releases.review_service.decide(case.reviewer.principal, ReviewRequest(fact_id=fact.id,
            expected_fact_version=1, expected_case_revision=0, action="approve",
            checks=tuple(ReviewCheck(field=name, status="not_applicable" if name in
                {"date_context", "statistics_context"} else "accepted") for name in CHECK_FIELDS),
            conflict_resolutions=(), return_reason=None))
        old = case.releases.get_release(case.reviewer.principal, case.release.release_id)
        members = tuple(PublishMember(fact_id=item.fact_id, expected_case_revision=item.case_revision,
            expected_decision_id=item.decision_id, public_evidence=True) for item in old.members)
        members += (PublishMember(fact_id=fact.id, expected_case_revision=decision.case_revision,
            expected_decision_id=decision.decision_id, public_evidence=True),)
        with Session(pg_engine) as session:
            revision = session.get(CatalogDataset, extra.dataset_id).revision
        release = case.releases.publish(case.reviewer.principal, PublishRequest(dataset_id=extra.dataset_id,
            expected_dataset_revision=revision, entry_year=2026, kind="test_fixture", valid_from=clock(),
            valid_until=clock()+timedelta(hours=1), members=members, replaces_release_id=old.release_id,
            expected_replaced_state_revision=old.state_revision), SecretStr("DEMO_T29_PUBLIC_RELEASE"))
        bundle = case.bundle.model_copy(update={"release_id": release.release_id,
            "requirements_version": release.requirements_version})
        policy = case.deferral.model_copy(update={"release_id": release.release_id,
            "requirements_version": release.requirements_version})
        service = EligibilityService(case.profiles, case.releases, assessments_store,
            AssessmentPolicy(enabled=True, allow_test_bindings=True),
            rule_binding_reader=lambda session, query: (bundle,) if query.target.offering_id == bundle.offering_id else (),
            deferral_reader=lambda session, query: (policy,) if query.target.offering_id == bundle.offering_id else ())
        identity = case.profiles.auth_service
        receiver = actor_factory()
        receiver_principal = identity.get_principal(receiver.cookie)
        privacy = case.profiles.privacy_service
        adult = privacy.declare_age(receiver_principal, AgeDeclarationInput(age_band="18_plus", confirmed=True,
            notice_id=privacy.settings.notice_id, expected_revision=0))
        privacy.confirm_core(receiver_principal, CoreConsentInput(purpose="core_consultation", confirmed=True,
            notice_id=adult.notice_id, expected_revision=adult.revision))
        receiver_profile = case.profiles.create_profile(receiver_principal,
            CreateInput(profile=case.profile.profile, confirmed=True), SecretStr("DEMO_T29_SECOND_STUDENT")).version
        public_runtime = V2RuntimeSettings(app_environment="test", data_mode="demo", model_mode="disabled",
            database_url=None, legacy_demo_mode=None, _env_file=None)
        reader = CatalogReader(case.releases, public_runtime,
            PublicCatalogPolicy(enabled=True, allow_test_fixture_read=True))
        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        app.mount("/v2", create_assessments_v2_app(identity.runtime_settings,
            identity_service=identity, profile_service=case.profiles, assessment_service=service))
        app.mount("/public/v2", create_public_catalog_v2_app(public_runtime, reader=reader))
        return SimpleNamespace(app=app, case=case, auth=identity, receiver=receiver, service=service,
            receiver_profile=receiver_profile, reader=reader, release=release, extra=extra,
            public_snippet=snippet, xss_sentinel=sentinel)
    return make
