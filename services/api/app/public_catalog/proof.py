"""Anonymous current proofs read metadata directly, never a historical identity."""

from dataclasses import dataclass

from sqlalchemy import func, or_, select

from ..admin.imports.models import ImportCandidateRow, ImportRowError
from ..admin.sources.schemas import SourcePolicy
from ..admissions_catalog.date_models import CatalogDateEvent
from ..admissions_catalog.models import CatalogInstitution, CatalogProgram, PROGRAM_SCOPE_FIELDS
from ..admissions_catalog.schemas import InstitutionData, ProgramData
from ..evidence.store import scope_hash, utc_time
from ..facts.models import FactConflict
from ..facts.schemas import DateResolutionSnapshot
from ..facts.store import fingerprint
from ..facts.typing import type_candidate
from ..ingestion.schemas import PARSER_SCHEMA_VERSION, ParsedRow, ROW_FIELDS
from ..reviews.store import conflict_fingerprint, fact_fingerprint
from ..reviews.validation import validate_review
from ..storage.schemas import StorageNamespace, StoragePolicy
from .schemas import PublicCatalogError


@dataclass(frozen=True)
class MemberProof:
    member: object
    fact: object
    evidence: object
    source: object
    file: object
    institution: object
    program: object
    created_times: tuple


class AnonymousProofVerifier:
    def __init__(self, release_service):
        self.releases = release_service.store
        self.reviews = release_service.review_service
        self.facts = self.reviews.fact_service
        self.imports = self.facts.import_service
        self.evidence = self.facts.evidence_service
        self.sources = self.imports.source_service
        self.storage = self.imports.storage_service
        self.engine = self.releases.engine

    def validate_configuration(self):
        # Revalidate frozen server configuration, without authenticating anyone
        # or looking up the historical publisher/reviewer's current sessions.
        policy = SourcePolicy.model_validate(self.sources.policy)
        storage_policy = StoragePolicy.model_validate(self.storage.policy)
        if policy != self.sources._initial_policy or storage_policy != self.storage._initial_policy:
            raise PublicCatalogError()
        for store in (self.reviews.store, self.facts.store, self.facts.date_store,
                      self.imports.store, self.evidence.store, self.sources.store, self.storage.store):
            if store.engine is not self.engine:
                raise PublicCatalogError()
        return policy, storage_policy

    def member(self, session, root, member) -> MemberProof:
        source_policy, storage_policy = self.validate_configuration()
        if (not source_policy.enabled or not storage_policy.enabled
            or storage_policy.source_retention_days is None):
            raise PublicCatalogError()
        row = self.facts.store.get(session, member.fact_id)
        batch = self.imports.store.get(session, row.import_id)
        if ((row.dataset_id, row.is_synthetic, row.offering_id, row.offering_version, row.entry_year,
             row.logical_key_hash, row.evidence_id) != (root.dataset_id, root.is_synthetic, member.offering_id,
             member.offering_version, root.entry_year, member.logical_key_hash, member.evidence_id)
            or (batch.dataset_id, batch.is_synthetic) != (root.dataset_id, root.is_synthetic)
            or batch.status != "staged" or batch.version != 1 or batch.parser_schema_version != PARSER_SCHEMA_VERSION
            or type(batch.total_rows) is not int or not 1 <= batch.total_rows <= 200
            or batch.staged_rows != batch.total_rows or batch.error_count != 0):
            raise PublicCatalogError(409)
        count = session.scalar(select(func.count()).select_from(ImportCandidateRow)
            .where(ImportCandidateRow.import_id == batch.id))
        errors = session.scalar(select(func.count()).select_from(ImportRowError)
            .where(ImportRowError.import_id == batch.id))
        if count != batch.total_rows or errors != 0:
            raise PublicCatalogError(409)
        raw = session.scalar(select(ImportCandidateRow).where(ImportCandidateRow.id == row.import_row_id,
            ImportCandidateRow.import_id == batch.id).with_for_update().execution_options(populate_existing=True))
        if (raw is None or (raw.dataset_id, raw.is_synthetic, raw.review_state, raw.evidence_state) !=
            (root.dataset_id, root.is_synthetic, "draft", "unresolved")):
            raise PublicCatalogError(409)
        original = ParsedRow(**{name: getattr(raw, name) for name in (*ROW_FIELDS, "row_number")})
        original.validate_namespace(root.is_synthetic)
        start = 1 if batch.format == "json" else 2 if batch.format == "csv" else None
        if start is None or not start <= original.row_number < start + batch.total_rows:
            raise PublicCatalogError(409)
        scope = self.evidence.store.scope(session, dataset_id=root.dataset_id,
            offering_id=member.offering_id, offering_version=member.offering_version,
            entry_year=root.entry_year, is_synthetic=root.is_synthetic)
        if (original.offering_id, original.offering_version, original.entry_year) != (
            member.offering_id, member.offering_version, root.entry_year):
            raise PublicCatalogError(409)
        classification = self.facts.store.classification(row)
        date_snapshot, date_hash = None, None
        if classification.date_event_id is not None:
            date_row = session.scalar(select(CatalogDateEvent).where(CatalogDateEvent.id == classification.date_event_id)
                .with_for_update().execution_options(populate_existing=True))
            if date_row is None:
                raise PublicCatalogError(409)
            date = self.facts.date_store.get_date_event(session, date_row.id)
            if ((date.dataset_id, date.offering_id, date.offering_version, date.entry_year,
                 date.is_synthetic, date.original_text) != (root.dataset_id, member.offering_id,
                 member.offering_version, root.entry_year, root.is_synthetic, original.value_text)):
                raise PublicCatalogError(409)
            date_snapshot = DateResolutionSnapshot.from_date_event(date)
            date_hash = fingerprint(date.model_dump(mode="json"))
        snippet_row = self.evidence.store.get_snippet(session, member.evidence_id)
        evidence = self.evidence.store.snippet_data(session, snippet_row)
        document = self.evidence.store.get_document(session, evidence.document_id)
        version = self.evidence.store.get_version(session, document.id, evidence.document_version)
        source = self.sources.store.get_source_version(session, batch.source_id)
        file_row = self.storage.store.get(session, batch.file_id)
        file = self.storage.store.data(file_row)
        if ((evidence.scope, evidence.offering_id, evidence.offering_version, evidence.entry_year,
             evidence.is_synthetic) != (scope, member.offering_id, member.offering_version, root.entry_year, root.is_synthetic)
            or (batch.source_id, batch.source_version) != (member.source_id, member.source_version)
            or (source.dataset_id, source.source_id, source.version, source.is_synthetic) !=
               (root.dataset_id, member.source_id, member.source_version, root.is_synthetic)
            or (document.dataset_id, document.source_id, document.source_version, document.is_synthetic) !=
               (root.dataset_id, member.source_id, member.source_version, root.is_synthetic)
            or (version.file_id, version.document_sha256, version.size_bytes, version.is_synthetic) !=
               (batch.file_id, batch.file_sha256, batch.file_size, root.is_synthetic)
            or (file_row.dataset_id, file_row.source_id, file_row.source_version, file.is_synthetic) !=
               (root.dataset_id, member.source_id, member.source_version, root.is_synthetic)
            or file.namespace != StorageNamespace.source_quarantine or file.status != "quarantined"
            or (file.id, file.sha256, file.size_bytes, file.media_type) !=
               (member.file_id, batch.file_sha256, batch.file_size, version.media_type)
            or evidence.document_sha256 != file.sha256 or file.sha256 != member.file_sha256
            or not source.manual_import_enabled or source.manual_import_permission != "granted"
            or source.publication_permission != "granted" or source.license_basis is None
            or source.permission_record_reference is None or source.permission_reviewed_at is None
            or fingerprint(source.model_dump(mode="json")) != member.source_sha256
            or fingerprint(file.model_dump(mode="json")) != member.file_metadata_sha256):
            raise PublicCatalogError(409)
        if not root.is_synthetic and (not source_policy.real_sources_ready or not storage_policy.real_storage_ready
            or source.responsible_user_id not in source_policy.responsible_user_ids):
            raise PublicCatalogError()
        payload = type_candidate(original, classification, evidence_id=evidence.id, date_resolution=date_snapshot)
        fact = self.facts.store.data(session, row, payload,
            row_sha256=fingerprint(original.model_dump(mode="json")), scope_sha256=scope_hash(scope),
            date_sha256=date_hash, evidence_sha256=fingerprint(evidence.model_dump(mode="json")))
        case = self.reviews.store.get_case(session, row.logical_key_hash)
        decision = self.reviews.store.get_decision(session, member.decision_id)
        if (case is None or case.logical_key_hash != row.logical_key_hash
            or (case.revision, case.chosen_fact_id, case.current_decision_id, case.is_synthetic) !=
            (member.case_revision, fact.id, decision.id, root.is_synthetic)
            or (decision.case_id, decision.case_revision, decision.logical_key_hash, decision.fact_id,
                decision.action, decision.is_synthetic) !=
               (case.id, case.revision, row.logical_key_hash, fact.id, "approve", root.is_synthetic)
            or decision.reviewer_user_id == batch.actor_user_id
            or decision.fact_sha256 != fact_fingerprint(fact)
            or decision.conflicts_sha256 != conflict_fingerprint(fact.conflicting_ids)):
            raise PublicCatalogError(409)
        validate_review(self.reviews.store.request(session, decision), fact, evidence)
        if (fingerprint(fact.model_dump(mode="json")) != member.fact_sha256
            or fingerprint(evidence.model_dump(mode="json")) != member.evidence_sha256
            or scope_hash(scope) != member.scope_sha256
            or member.snapshot != {"fact": fact.model_dump(mode="json"), "evidence": evidence.model_dump(mode="json")}):
            raise PublicCatalogError(409)
        # Names and namespaces are current bounded catalog labels, not inferred
        # qualification, user-location or stored raw import values.
        institution_row = session.scalar(select(CatalogInstitution).where(CatalogInstitution.id == scope.institution_id)
            .with_for_update().execution_options(populate_existing=True))
        program_row = session.scalar(select(CatalogProgram).where(CatalogProgram.id == scope.program_id)
            .with_for_update().execution_options(populate_existing=True))
        if institution_row is None or program_row is None:
            raise PublicCatalogError(409)
        institution = InstitutionData.model_validate({name: getattr(institution_row, name)
                                                     for name in InstitutionData.model_fields})
        fields = {name: getattr(program_row, name) for name in ProgramData.model_fields if name not in PROGRAM_SCOPE_FIELDS}
        fields.update({name: getattr(scope, name) for name in PROGRAM_SCOPE_FIELDS})
        program = ProgramData.model_validate(fields)
        if ((institution.dataset_id, institution.is_synthetic, program.dataset_id, program.is_synthetic,
             program.institution_id) != (root.dataset_id, root.is_synthetic, root.dataset_id,
             root.is_synthetic, institution.id)):
            raise PublicCatalogError(409)
        edges = session.scalars(select(FactConflict).where(or_(FactConflict.left_id == fact.id,
            FactConflict.right_id == fact.id)).order_by(FactConflict.left_id, FactConflict.right_id)
            .limit(201).with_for_update().execution_options(populate_existing=True)).all()
        edge_ids = tuple(sorted((edge.right_id if edge.left_id == fact.id else edge.left_id for edge in edges), key=str))
        if len(edges) > 200 or edge_ids != fact.conflicting_ids:
            raise PublicCatalogError(409)
        return MemberProof(member, fact, evidence, source, file, institution, program,
            (batch.created_at, fact.created_at, document.created_at, version.created_at, evidence.created_at,
             case.created_at, case.updated_at, decision.created_at, *(edge.created_at for edge in edges)))

    @staticmethod
    def final_deadlines(proofs, releases, now):
        """One fresh instant after the final SQL applies to all returned proofs."""
        now = utc_time(now)
        for root, state in releases:
            if (state.status != "published" or not utc_time(root.valid_from) <= now < utc_time(root.valid_until)
                or utc_time(root.published_at) > now or utc_time(state.updated_at) > now):
                raise PublicCatalogError(409)
        for proof in proofs:
            if (not proof.source.created_at <= now < proof.source.recheck_due_at
                or proof.source.permission_reviewed_at is None or proof.source.permission_reviewed_at > now
                or not proof.file.created_at <= now < proof.file.expires_at
                or any(utc_time(created) > now for created in proof.created_times)):
                raise PublicCatalogError(409)
