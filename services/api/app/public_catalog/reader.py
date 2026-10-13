"""Bounded anonymous published-catalog reads with current metadata proofs."""

from contextlib import contextmanager
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from ..admin.imports.models import ImportBatch, ImportCandidateRow, ImportRowError
from ..admin.sources.models import CatalogSource, CatalogSourceVersion
from ..admissions_catalog.date_models import CatalogDateEvent
from ..admissions_catalog.models import (AdmissionOffering, AdmissionOfferingVersion, CatalogDataset,
                                         CatalogInstitution, CatalogProgram)
from ..api.v2.schemas import PageInfo
from ..evidence.models import Document, DocumentVersion, EvidenceSnippet
from ..evidence.store import utc_time
from ..facts.models import FactCandidate, FactConflict
from ..releases.models import CatalogRelease, CatalogReleaseMember, CatalogReleaseState, ChangeEvent, OutboxEvent
from ..releases.service import ReleaseService
from ..releases.schemas import ReleasesError
from ..reviews.models import ReviewCase, ReviewConflictResolution, ReviewDecision
from ..settings import V2RuntimeSettings
from ..storage.models import StorageObject
from .proof import AnonymousProofVerifier
from .query import decode_cursor, encode_cursor
from .schemas import (CoverageData, DEMO_BANNER, PublicCatalogError, PublicCatalogPolicy, PublicConfigData,
                      PublicDateData, PublicEvidenceData, PublicFactData, PublicOfferingData,
                      PublicOfferingQuery, PublicOfferingsData)


_MAPPERS = (None, CatalogDataset, CatalogInstitution, CatalogProgram, AdmissionOffering, AdmissionOfferingVersion,
    CatalogDateEvent, CatalogSource, CatalogSourceVersion, StorageObject, ImportBatch, ImportCandidateRow,
    ImportRowError, Document, DocumentVersion, EvidenceSnippet, FactCandidate, FactConflict,
    ReviewCase, ReviewDecision, ReviewConflictResolution, CatalogRelease, CatalogReleaseState,
    CatalogReleaseMember, ChangeEvent, OutboxEvent)


class CatalogReader:
    def __init__(self, release_service, settings: V2RuntimeSettings, policy: PublicCatalogPolicy = PublicCatalogPolicy()):
        try:
            if not isinstance(release_service, ReleaseService):
                raise ValueError()
            self.settings = V2RuntimeSettings.model_validate(settings)
            self.policy = PublicCatalogPolicy.model_validate(policy)
            self.release_service = release_service
            self.store = release_service.store
            self.proof = AnonymousProofVerifier(release_service)
            self._initial_settings, self._initial_policy = self.settings, self.policy
            self._initial_release_service = release_service
            self._initial_auth_service = release_service.auth_service
            self._initial_engine = self.store.engine
            self._initial_clock = self._initial_auth_service.clock
            self._initial_pipeline_runtime = V2RuntimeSettings.model_validate(self._initial_auth_service.runtime_settings)
            self._validate()
        except Exception:
            raise PublicCatalogError() from None

    def _validate(self):
        try:
            runtime = V2RuntimeSettings.model_validate(self.settings)
            policy = PublicCatalogPolicy.model_validate(self.policy)
            if (runtime != self._initial_settings or policy != self._initial_policy
                or self.release_service is not self._initial_release_service
                or self.store is not self.release_service.store or self.proof.releases is not self.store
                or self.store.engine is not self._initial_engine or self.store.engine.dialect.name != "postgresql"
                or self.release_service.auth_service is not self._initial_auth_service
                or self._initial_auth_service.store.engine is not self._initial_engine
                or self._initial_auth_service.clock is not self._initial_clock):
                raise ValueError()
            if policy.allow_test_fixture_read and (runtime.app_environment != "test" or runtime.data_mode != "demo"):
                raise ValueError()
            pipeline_runtime = V2RuntimeSettings.model_validate(self.release_service.auth_service.runtime_settings)
            if pipeline_runtime != self._initial_pipeline_runtime:
                raise ValueError()
            if policy.allow_test_fixture_read and pipeline_runtime.app_environment != "test":
                raise ValueError()
            self.proof.validate_configuration()
            return runtime, policy
        except Exception:
            raise PublicCatalogError() from None

    def _available(self):
        runtime, policy = self._validate()
        return policy.enabled and ((runtime.app_environment == "test" and runtime.data_mode == "demo"
            and policy.allow_test_fixture_read) or (runtime.data_mode == "verified" and policy.real_catalog_ready))

    def config(self):
        runtime, policy = self._validate()
        return PublicConfigData(api_version="v2", schema_version="v2.t20", contract_stage="public_catalog",
            app_environment=runtime.app_environment, query_role=runtime.query_role, data_mode=runtime.data_mode,
            model_mode=runtime.model_mode, live_available=False, business_available=self._available(),
            allow_test_fixture_read=policy.allow_test_fixture_read,
            demo_banner=DEMO_BANNER if policy.allow_test_fixture_read else None,
            supported_scope=[], supported_province=None, entry_year=None)

    def _now(self):
        try:
            return utc_time(self.release_service.auth_service.clock())
        except Exception:
            raise PublicCatalogError() from None

    def _guard_session(self, session):
        if (not isinstance(session, Session) or not session.is_active or not session.in_transaction()
            or not session.get_transaction().is_active):
            raise PublicCatalogError()
        for mapper in _MAPPERS:
            bind = session.get_bind(mapper=mapper)
            if getattr(bind, "engine", bind) is not self.store.engine:
                raise PublicCatalogError()

    @contextmanager
    def _transaction(self):
        try:
            if not self._available():
                raise PublicCatalogError()
            # Explicit readiness is a read-only preflight before holding any
            # catalog locks. Default/schema factories never call this method.
            self.store.assert_schema_ready()
            with Session(self.store.engine) as session, session.begin():
                self._guard_session(session)
                yield session
        except PublicCatalogError:
            raise
        except (ValidationError, TypeError, AttributeError, OverflowError):
            raise PublicCatalogError() from None
        except Exception as error:
            # Current proof failure is fixed and contains no SQL/input values.
            # No private service handler or historical Principal is invoked.
            if getattr(error, "status_code", None) in {404, 409, 422}:
                raise PublicCatalogError(409) from None
            raise PublicCatalogError() from None

    def _mode(self, root, dataset):
        runtime, policy = self._validate()
        if root.dataset_id != dataset.id or root.is_synthetic != dataset.is_synthetic:
            raise PublicCatalogError()
        if runtime.data_mode == "demo":
            if (runtime.app_environment != "test" or not policy.allow_test_fixture_read
                or root.kind != "test_fixture" or not root.is_synthetic or dataset.data_mode != "demo"
                or not dataset.reference_key.startswith("DEMO_")):
                raise PublicCatalogError()
        elif (not policy.real_catalog_ready or root.kind != "formal" or root.is_synthetic
              or dataset.data_mode != "verified" or dataset.reference_key.upper().startswith("DEMO_")):
            raise PublicCatalogError()

    def _release(self, session, release_id):
        root = self.store.get(session, release_id)
        dataset = self.store.dataset(session, root.dataset_id)
        self._mode(root, dataset)
        state = self.store.state(session, root.id)
        if state.status != "published":
            raise PublicCatalogError(404)
        result = self.store.result(session, root)
        members = self.store.members(session, root.id)
        proofs = tuple(self.proof.member(session, root, member) for member in members)
        return root, state, result, proofs

    def _base_query(self, query, now):
        statement = select(CatalogRelease.id.label("release_id"), CatalogRelease.dataset_id,
            CatalogReleaseMember.offering_id, CatalogReleaseMember.offering_version).join(
                CatalogReleaseState, CatalogReleaseState.release_id == CatalogRelease.id).join(
                CatalogReleaseMember, CatalogReleaseMember.release_id == CatalogRelease.id).join(
                AdmissionOffering, AdmissionOffering.id == CatalogReleaseMember.offering_id).join(
                CatalogProgram, CatalogProgram.id == AdmissionOffering.program_id).join(
                CatalogInstitution, CatalogInstitution.id == CatalogProgram.institution_id).join(
                CatalogDataset, CatalogDataset.id == CatalogRelease.dataset_id).where(
                CatalogReleaseState.status == "published", CatalogRelease.entry_year == query.entry_year,
                CatalogRelease.valid_from <= now, CatalogRelease.valid_until > now)
        runtime, _ = self._validate()
        statement = statement.where(CatalogRelease.kind == ("test_fixture" if runtime.data_mode == "demo" else "formal"),
            CatalogRelease.is_synthetic == (runtime.data_mode == "demo"), CatalogDataset.data_mode == runtime.data_mode,
            CatalogDataset.is_synthetic == (runtime.data_mode == "demo"))
        if query.release_id is not None:
            statement = statement.where(CatalogRelease.id == query.release_id)
        if query.country is not None:
            statement = statement.where(CatalogInstitution.country == query.country)
        if query.study_level is not None:
            statement = statement.where(CatalogProgram.study_level == query.study_level)
        for name in ("province", "pathway", "course_system", "applicant_category"):
            value = getattr(query, name)
            if value is not None:
                statement = statement.where(getattr(AdmissionOffering, name + "_key") == value)
        return statement.distinct().order_by(CatalogRelease.id, CatalogReleaseMember.offering_id,
                                            CatalogReleaseMember.offering_version)

    @staticmethod
    def _watermark(session):
        value = session.scalar(select(func.count()).select_from(ChangeEvent))
        if type(value) is not int or not 0 <= value <= 9007199254740991:
            raise PublicCatalogError()
        return value

    @staticmethod
    def _fact(proof):
        fact = proof.fact
        classification = fact.classification
        fields = {name: getattr(fact, name) for name in PublicFactData.model_fields
                  if name not in {"evidence_id", "date_resolution"} and hasattr(fact, name)}
        fields.update({name: getattr(classification, name) for name in type(classification).model_fields if name != "date_event_id"})
        fields["evidence_id"] = proof.evidence.id if proof.member.public_evidence else None
        fields["date_resolution"] = (PublicDateData.model_validate({name: getattr(fact.date_resolution, name)
            for name in PublicDateData.model_fields}) if fact.date_resolution is not None else None)
        return PublicFactData.model_validate(fields)

    def list_offerings(self, query):
        try:
            query = PublicOfferingQuery.model_validate(query)
        except (ValidationError, ValueError, TypeError):
            raise PublicCatalogError(422) from None
        cursor = decode_cursor(query, query.cursor) if query.cursor is not None else None
        with self._transaction() as session:
            watermark = self._watermark(session)
            if cursor is not None and cursor.watermark != watermark:
                raise PublicCatalogError(409)
            base = self._base_query(query, self._now())
            window = base
            if cursor is not None:
                window = window.where(tuple_(CatalogRelease.id, CatalogReleaseMember.offering_id,
                    CatalogReleaseMember.offering_version) > tuple_(cursor.release_id, cursor.offering_id, cursor.offering_version))
            hints = session.execute(window.limit(query.limit + 1)).all()
            # Every relevant dataset is locked in a deterministic order before
            # release/state/member locks, matching the writer's first domain lock.
            for dataset_id in sorted({hint.dataset_id for hint in hints}, key=str):
                self.store.dataset(session, dataset_id)
            items, all_proofs, releases, cached = [], [], [], {}
            for hint in hints[:query.limit]:
                if hint.release_id not in cached:
                    cached[hint.release_id] = self._release(session, hint.release_id)
                    root, state, _, proofs = cached[hint.release_id]
                    releases.append((root, state))
                    all_proofs.extend(proofs)
                root, _, result, proofs = cached[hint.release_id]
                selected = tuple(proof for proof in proofs if (proof.member.offering_id, proof.member.offering_version) ==
                                 (hint.offering_id, hint.offering_version))
                if not selected:
                    raise PublicCatalogError(409)
                first = selected[0]
                scope = first.evidence.scope
                if (scope.entry_year != query.entry_year or query.country is not None and scope.country != query.country
                    or query.study_level is not None and scope.study_level != query.study_level
                    or any(getattr(query, name) is not None and getattr(scope, name).canonical_key() != getattr(query, name)
                           for name in ("province", "pathway", "course_system", "applicant_category"))):
                    raise PublicCatalogError(409)
                items.append(PublicOfferingData(release_id=root.id, release_version=root.version,
                    requirements_version=result.requirements_version, content_sha256=result.content_sha256,
                    ruleset_version=None, id=hint.offering_id, version=hint.offering_version,
                    entry_year=root.entry_year, is_synthetic=root.is_synthetic,
                    institution_id=first.institution.id, institution_name=first.institution.name,
                    program_id=first.program.id, program_name=first.program.name, scope=scope,
                    facts=tuple(self._fact(proof) for proof in selected)))
            # An empty cursor page can still be part of a nonempty query scope.
            any_records = bool(hints) or session.execute(base.limit(1)).first() is not None
            has_more = len(hints) > query.limit
            last = hints[query.limit - 1] if has_more else None
            next_cursor = encode_cursor(query, watermark, last.release_id, last.offering_id,
                                        last.offering_version) if last is not None else None
            result = PublicOfferingsData(items=tuple(items), page=PageInfo(limit=query.limit,
                next_cursor=next_cursor, has_more=has_more), coverage=CoverageData(
                status="partial" if any_records else "no_published_records", returned_count=len(items),
                expected_total=None, coverage_ratio=None))
            if self._watermark(session) != watermark:
                raise PublicCatalogError(409)
            self._validate()
            self.proof.final_deadlines(all_proofs, releases, self._now())
        return result

    def get_evidence(self, evidence_id, release_id):
        if type(evidence_id) is not UUID or type(release_id) is not UUID:
            raise PublicCatalogError(404)
        with self._transaction() as session:
            try:
                hint = self.store.get(session, release_id, lock=False)
            except ReleasesError as error:
                if error.status_code == 404:
                    raise PublicCatalogError(404) from None
                raise
            self.store.dataset(session, hint.dataset_id)
            root, state, released, proofs = self._release(session, release_id)
            selected = tuple(proof for proof in proofs if proof.evidence.id == evidence_id and proof.member.public_evidence)
            if not selected:
                raise PublicCatalogError(404)
            proof = selected[0]
            evidence = proof.evidence
            result = PublicEvidenceData(evidence_id=evidence.id, release_id=root.id, release_version=root.version,
                requirements_version=released.requirements_version, is_synthetic=root.is_synthetic,
                offering_id=evidence.offering_id, offering_version=evidence.offering_version,
                entry_year=root.entry_year, language=evidence.language, quote=evidence.text,
                document_sha256=evidence.document_sha256, snippet_sha256=evidence.snippet_sha256,
                locator=evidence.locator, scope=evidence.scope, publisher=proof.source.publisher,
                authority_claim=proof.source.authority_claim)
            self._validate()
            self.proof.final_deadlines(proofs, ((root, state),), self._now())
        return result
