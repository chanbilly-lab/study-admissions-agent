"""T28 uses a new random schema in the explicit T23 loopback test database."""

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

from tests.integration.releases.conftest import (
    clock, session_settings_factory, session_settings, runtime, idp, oidc_adapter,
    auth_store, auth_service, actor_factory, privacy_settings, privacy_service,
    catalog_store, source_store, administrator_factory, source_request_factory,
    blob_root, io_probe, storage_store, storage_factory, idempotency_store, imports_store,
    imports_factory, candidate_factory, evidence_store, evidence_factory, facts_store,
    facts_factory, classification_factory, reviews_store, releases_store, import_case_factory,
    isolate_releases_environment_and_network,
)


@pytest.fixture
def pg_engine():
    raw = os.getenv("T23_TEST_POSTGRES_URL")
    if not raw:
        pytest.fail("T28 required PostgreSQL check needs T23_TEST_POSTGRES_URL", pytrace=False)
    parsed = urlsplit(raw)
    if parsed.scheme != "postgresql+psycopg" or parsed.hostname != "127.0.0.1" or parsed.path != "/study_t23_20261003":
        pytest.fail("T28 requires the dedicated loopback study_t23_20261003 database", pytrace=False)
    schema = "eligibility_t28_" + uuid4().hex
    admin = create_engine(raw, hide_parameters=True, connect_args={"connect_timeout": 5})
    engine, created = None, False
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        created = True
        engine = create_engine(raw, hide_parameters=True,
            connect_args={"options": "-csearch_path=" + schema, "connect_timeout": 5})
        assert inspect(engine).get_table_names() == []
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def catalog_tree(catalog_store, pg_engine):
    from services.api.app.admissions_catalog.schemas import DatasetInput, InstitutionInput, ProgramInput, OfferingInput, ScopeKey
    known = lambda value: ScopeKey(status="known", value=value)
    dataset = DatasetInput(id=uuid4(), reference_key="DEMO_T28_DATASET", data_mode="demo", is_synthetic=True)
    institution = InstitutionInput(id=uuid4(), dataset_id=dataset.id, reference_key="DEMO_T28_INSTITUTION",
        name="DEMO_T28_SYNTHETIC_INSTITUTION", country="CN", is_synthetic=True)
    program = ProgramInput(id=uuid4(), dataset_id=dataset.id, institution_id=institution.id,
        reference_key="DEMO_T28_PROGRAM", name="DEMO_T28_SYNTHETIC_PROGRAM", study_level="undergraduate",
        is_synthetic=True, **{name: known("DEMO_" + name.upper()) for name in (
            "degree", "course", "campus", "teaching_language", "progression_pathway")})
    codes = {"course_system": "gaokao", "pathway": "gaokao", "applicant_category": "cn_mainland", "province": "Zhejiang"}
    offering = OfferingInput(id=uuid4(), dataset_id=dataset.id, program_id=program.id,
        reference_key="DEMO_T28_OFFERING", is_synthetic=True, entry_year=2026,
        **{name: known(codes.get(name, "DEMO_" + name.upper())) for name in (
            "intake", "application_cycle", "channel", "course_system", "pathway", "applicant_category",
            "province", "exam_system", "subject_scope", "batch_group")})
    with Session(pg_engine) as session, session.begin():
        catalog_store.create_dataset(session, dataset)
        for method, value in ((catalog_store.create_institution, institution), (catalog_store.create_program, program)):
            method(session, value, expected_dataset_revision=catalog_store.get_dataset(session, dataset.id).revision)
        current = catalog_store.create_offering(session, offering,
            expected_dataset_revision=catalog_store.get_dataset(session, dataset.id).revision, version_id=uuid4())
    return SimpleNamespace(dataset=dataset, institution=institution, program=program, offering=offering, current=current)


@pytest.fixture
def profiles_store(releases_store, idempotency_store, pg_engine):
    from services.api.app.profiles.store import ProfilesStore, migrate_profiles
    migrate_profiles(pg_engine)
    return ProfilesStore(pg_engine)


@pytest.fixture
def assessments_store(profiles_store, pg_engine):
    from services.api.app.assessments.store import AssessmentsStore, migrate_assessments
    migrate_assessments(pg_engine)
    return AssessmentsStore(pg_engine)


@pytest.fixture
def assessment_case_factory(assessments_store, profiles_store, import_case_factory, candidate_factory,
        evidence_store, evidence_factory, facts_factory, classification_factory, reviews_store, releases_store,
        administrator_factory, actor_factory, pg_engine, catalog_tree, clock):
    from services.api.app.admin.imports.models import ImportCandidateRow
    from services.api.app.admissions_catalog.date_schemas import DateEventInput
    from services.api.app.admissions_catalog.date_store import DateEventStore
    from services.api.app.admissions_catalog.models import CatalogDataset
    from services.api.app.evidence.schemas import DocumentCreate, VersionCreate, SnippetCreate
    from services.api.app.facts.schemas import FactCreate
    from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput
    from services.api.app.profiles.schemas import CreateInput, ProfilePolicy
    from services.api.app.profiles.service import ProfileService
    from services.api.app.releases.schemas import ReleasePolicy, PublishMember, PublishRequest
    from services.api.app.releases.service import ReleaseService
    from services.api.app.reviews.schemas import CHECK_FIELDS, ReviewPolicy, ReviewRequest, ReviewCheck
    from services.api.app.reviews.service import ReviewService
    from services.api.app.rules.adapters.schemas import RuleBundle, TargetReference, scope_fingerprint, expression_fingerprint
    from services.api.app.rules.deferral import DeferralBundle, DeadlineBinding
    from services.api.app.rules.expression import parse_expression
    from services.api.app.rules.schemas import AssessmentPolicy, AssessmentRequest
    from services.api.app.rules.service import EligibilityService, rule_descriptor, deferral_descriptor
    from tests.integration.profiles.conftest import snapshot_payload

    def make(*, expression=None, deferral=False, policy_text=True, binding=True, profile_updates=None,
             file_lifetime_seconds=None):
        expression = parse_expression(expression or {"op": "gte", "field": {"name": "assessment", "key": "gaokao_total", "basis": "achieved"},
            "value": {"kind": "decimal", "value": "600", "unit": "points", "scale": "750"}})
        with Session(pg_engine) as session, session.begin():
            scope = evidence_store.scope(session, dataset_id=catalog_tree.dataset.id,
                offering_id=catalog_tree.offering.id, offering_version=1, entry_year=2026, is_synthetic=True)
        prototype = RuleBundle(bundle_id=uuid4(), reference_key="DEMO_T28_EXPLICIT_RULE", release_id=uuid4(), release_version=1,
            requirements_version="0" * 64, ruleset_version=expression_fingerprint(expression), is_synthetic=True,
            scope=scope, scope_sha256=scope_fingerprint(scope), offering_id=catalog_tree.offering.id, offering_version=1,
            stage="application", valid_from=clock(), valid_until=clock() + timedelta(hours=1), expression=expression,
            expression_sha256=expression_fingerprint(expression), fact_ids=(uuid4(),), evidence_ids=(uuid4(),))
        raw = [candidate_factory(fact_type="requirement", value_kind="text", field_key="DEMO_T28_RULE",
            value_text=rule_descriptor(prototype), unit="text")]
        policy, dates = None, []
        if deferral:
            store = DateEventStore(pg_engine)
            for kind, seconds in (("application_deadline", 40), ("score_supplement", 80)):
                instant = clock() + timedelta(seconds=seconds)
                value = DateEventInput(id=uuid4(), dataset_id=scope.dataset_id, offering_id=prototype.offering_id,
                    offering_version=1, entry_year=2026, reference_key="DEMO_T28_DATE_" + uuid4().hex, is_synthetic=True,
                    event_type=kind, original_text=instant.strftime("%Y-%m-%d %H:%M:%S UTC"), precision="second",
                    local_date=instant.date(), local_time=instant.time().replace(tzinfo=None), timezone="UTC",
                    source_alignment="pending", evidence_reference=None)
                with Session(pg_engine) as session, session.begin():
                    date = store.create_date_event(session, value,
                        expected_dataset_revision=session.get(CatalogDataset, scope.dataset_id).revision)
                dates.append(date)
            policy = DeferralBundle(bundle_id=uuid4(), reference_key="DEMO_T28_EXPLICIT_DEFERRAL", policy_id=uuid4(),
                policy_version="d"*64, release_id=prototype.release_id, release_version=1, requirements_version="0"*64,
                ruleset_version=prototype.ruleset_version, is_synthetic=True, scope=scope, scope_sha256=prototype.scope_sha256,
                offering_id=prototype.offering_id, offering_version=1, stage="application", assessment_keys=("math",),
                allowed_missing_states=("missing", "pending"), valid_from=clock(), valid_until=clock()+timedelta(hours=1),
                policy_evidence_ids=(uuid4(),), application_deadline_required=True,
                application_deadline=DeadlineBinding(date_event=dates[0], evidence_ids=(uuid4(),), reference_calendar="UTC"),
                supplement_deadline=DeadlineBinding(date_event=dates[1], evidence_ids=(uuid4(),), reference_calendar="UTC"))
            raw.append(candidate_factory(fact_type="requirement", value_kind="text", field_key="DEMO_T28_POLICY",
                source_record_reference="DEMO_T28_POLICY_RECORD", value_text=deferral_descriptor(policy) if policy_text else "DEMO_NO_DEFERRAL_DECLARATION", unit="text"))
            raw += [candidate_factory(fact_type="date", value_kind="text", field_key="DEMO_T28_DATE_"+str(index),
                source_record_reference="DEMO_T28_DATE_RECORD_"+str(index), value_text=date.original_text, unit="ISO_DATE")
                for index, date in enumerate(dates)]
        case = import_case_factory(rows=raw, ttl_seconds=86400)
        imported = case.service.import_file(case.admin.principal, case.request(), SecretStr("DEMO_T28_IMPORT"))
        evidence = evidence_factory(case.storage)
        document = evidence.create_document(case.admin.principal, DocumentCreate(dataset_id=scope.dataset_id,
            source_id=case.source.source_id, source_version=case.source.version, document_reference="DEMO_T28_DOC", language="und"))
        version = evidence.create_version(case.admin.principal, VersionCreate(document_id=document.id, expected_current_version=0,
            file_id=case.file.id, file_sha256=case.file.sha256))
        facts = facts_factory(case.storage, imports=case.service, evidence=evidence)
        snippets, candidates = [], []
        with Session(pg_engine) as session:
            rows = session.scalars(select(ImportCandidateRow).where(ImportCandidateRow.import_id == imported.id).order_by(ImportCandidateRow.row_number)).all()
            row_ids = tuple(row.id for row in rows)
        for index, row in enumerate(raw):
            encoded_row = json.dumps(row, ensure_ascii=False, allow_nan=False).encode("utf-8")
            start = case.data.index(encoded_row)
            snippet = evidence.create_snippet(case.admin.principal, SnippetCreate(document_id=document.id, document_version=1,
                offering_id=prototype.offering_id, offering_version=1, entry_year=2026,
                byte_start=start, byte_end=start+len(encoded_row)))
            snippets.append(snippet)
            classification = classification_factory(unit_code="text" if index < 2 else "ISO_DATE",
                claim_kind="minimum_requirement" if index == 0 else "information",
                date_event_id=dates[index-2].id if index >= 2 else None)
            candidates.append(facts.create_fact(case.admin.principal, FactCreate(import_id=imported.id,
                import_row_id=row_ids[index], classification=classification, evidence_id=snippet.id)))
        reviewer = administrator_factory()
        reviews = ReviewService(facts, reviews_store, ReviewPolicy(enabled=True))
        decisions = []
        for index, fact in enumerate(candidates):
            decisions.append(reviews.decide(reviewer.principal, ReviewRequest(fact_id=fact.id, expected_fact_version=1,
                expected_case_revision=0, action="approve", checks=tuple(ReviewCheck(field=field,
                    status="accepted" if field != "statistics_context" and (field != "date_context" or index >= 2) else "not_applicable")
                    for field in CHECK_FIELDS), conflict_resolutions=(), return_reason=None)))
        releases = ReleaseService(reviews, case.service.idempotency_service, releases_store,
            ReleasePolicy(enabled=True, allow_test_releases=True))
        if file_lifetime_seconds is not None:
            from services.api.app.storage.models import StorageObject
            assert type(file_lifetime_seconds) is int and file_lifetime_seconds > 0
            with Session(pg_engine) as session, session.begin():
                session.get(StorageObject, case.file.id).expires_at = clock()+timedelta(seconds=file_lifetime_seconds)
        with Session(pg_engine) as session:
            revision = session.get(CatalogDataset, scope.dataset_id).revision
        release = releases.publish(reviewer.principal, PublishRequest(dataset_id=scope.dataset_id,
            expected_dataset_revision=revision, entry_year=2026, kind="test_fixture", valid_from=clock(),
            valid_until=clock()+timedelta(hours=1), members=tuple(PublishMember(fact_id=item.fact_id,
                expected_case_revision=item.case_revision, expected_decision_id=item.decision_id, public_evidence=False)
                for item in decisions), replaces_release_id=None, expected_replaced_state_revision=None), SecretStr("DEMO_T28_PUBLISH"))
        bundle = prototype.model_copy(update={"release_id": release.release_id, "requirements_version": release.requirements_version,
            "fact_ids": (candidates[0].id,), "evidence_ids": (snippets[0].id,)})
        if policy is not None:
            policy = policy.model_copy(update={"release_id": release.release_id, "requirements_version": release.requirements_version,
                "policy_evidence_ids": (snippets[1].id,),
                "application_deadline": policy.application_deadline.model_copy(update={"evidence_ids": (snippets[2].id,)}),
                "supplement_deadline": policy.supplement_deadline.model_copy(update={"evidence_ids": (snippets[3].id,)})})
        identity = releases.auth_service
        privacy = releases.idempotency_service.privacy_service
        profiles = ProfileService(identity, privacy, releases.idempotency_service, profiles_store, ProfilePolicy(enabled=True))
        owner = actor_factory()
        principal = identity.get_principal(owner.cookie)
        adult = privacy.declare_age(principal, AgeDeclarationInput(age_band="18_plus", confirmed=True,
            notice_id=privacy.settings.notice_id, expected_revision=0))
        privacy.confirm_core(principal, CoreConsentInput(purpose="core_consultation", confirmed=True,
            notice_id=adult.notice_id, expected_revision=adult.revision))
        payload = snapshot_payload()
        payload.update(entry_year=2026, exam_province={"status":"known","value":"Zhejiang"})
        payload.update(profile_updates or {})
        profile = profiles.create_profile(principal, CreateInput(profile=payload, confirmed=True), SecretStr("DEMO_T28_PROFILE")).version
        service = EligibilityService(profiles, releases, assessments_store, AssessmentPolicy(enabled=True, allow_test_bindings=True),
            rule_binding_reader=(lambda session, query: (bundle,)) if binding else None,
            deferral_reader=(lambda session, query: (policy,)) if policy is not None else None)
        request = AssessmentRequest(profile_id=profile.profile_id, profile_version_id=profile.version_id,
            target=TargetReference(dataset_id=scope.dataset_id, institution_id=scope.institution_id, program_id=scope.program_id,
                offering_id=prototype.offering_id, offering_version=1, country="CN", scope_sha256=prototype.scope_sha256),
            release_id=release.release_id, stage="application", confirmed=True,
            **{name: getattr(scope, name) for name in ("intake", "application_cycle", "channel", "exam_system", "subject_scope", "batch_group")})
        values = dict(vars(case))
        values.update(imports=case.service, profiles=profiles, profile=profile, owner=owner, principal=principal,
            releases=releases, release=release, reviewer=reviewer, service=service, request=request,
            bundle=bundle, deferral=policy, candidates=tuple(candidates), snippets=tuple(snippets), dates=tuple(dates),
            assessment_service=service, profile_service=profiles)
        return SimpleNamespace(**values)
    return make
