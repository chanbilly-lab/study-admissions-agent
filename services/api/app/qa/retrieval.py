"""Anonymous exact-scope retrieval through the current published catalog proof."""

from ..evidence.schemas import EvidenceScope
from ..model_gateway.schemas import ModelScope
from ..public_catalog.reader import CatalogReader
from ..public_catalog.schemas import PublicCatalogError, PublicEvidenceData
from .schemas import (ProjectionLimit, QAError, QAPolicy, RetrievalRequest, SCOPE_FIELDS, atom_value,
                      bundle_from_public, citation_from_public, fingerprint)


class ScopedRetriever:
    def __init__(self, reader=None, policy=QAPolicy()):
        try:
            self.policy = QAPolicy.model_validate(policy)
            if reader is not None and type(reader) is not CatalogReader:
                raise ValueError()
            self.reader = reader
            self._initial_reader = reader
            self._initial_policy = QAPolicy.model_validate(self.policy)
            self._initial_configuration = self._configuration() if reader is not None else None
        except Exception:
            raise QAError() from None

    def _configuration(self):
        reader = self.reader
        reader._validate()
        services = (reader.release_service, reader.proof.reviews, reader.proof.facts,
                    reader.proof.evidence, reader.proof.imports, reader.proof.sources, reader.proof.storage)
        # Independent serialized copies catch legal-field in-place drift in an
        # older frozen model as well as ordinary object replacement.
        runtime_settings = (reader.settings, reader.release_service.auth_service.runtime_settings)
        values = [type(item).model_validate(item).model_dump(mode="json") for item in
                  (*runtime_settings, reader.policy,
                   *(service.policy for service in services if hasattr(service, "policy")))]
        # SecretStr JSON masks are intentionally equal for different secrets.
        # A private digest detects configuration drift without exposing a URL.
        values.append([fingerprint(item.database_url.get_secret_value()) if item.database_url is not None else None
                       for item in runtime_settings])
        identities = tuple(id(item) for item in (reader.store, reader.proof, reader.store.engine,
            reader.release_service.auth_service, reader.release_service.auth_service.clock, *services))
        return fingerprint(values), identities

    def _ready(self):
        try:
            current = QAPolicy.model_validate(self.policy)
            if current != self._initial_policy or self.reader is not self._initial_reader:
                raise ValueError()
            if not current.enabled or self.reader is None:
                raise ValueError()
            if (self._configuration() != self._initial_configuration or not self.reader._available()
                or self.reader.settings.app_environment != "test" or self.reader.settings.data_mode != "demo"
                or not current.allow_test_fixture_read or not self.reader.policy.allow_test_fixture_read):
                raise ValueError()
        except Exception:
            raise QAError() from None

    @staticmethod
    def _matches_intent(fact, intent):
        if intent == "background":
            return fact.fact_type == "statistic" or fact.claim_kind in {"historical_statistic", "typical_offer"}
        if intent == "requirements":
            return fact.fact_type in {"requirement", "score"} and fact.claim_kind not in {"historical_statistic", "typical_offer"}
        return fact.fact_type == {"materials": "material", "dates": "date", "fees": "fee"}[intent]

    def _empty(self, request, reason):
        return bundle_from_public(request, unknown_reasons=(reason,), retrieved_at=self.reader._now())

    @staticmethod
    def _bounded_bundle(request, **values):
        try:
            return bundle_from_public(request, **values)
        except ProjectionLimit:
            return bundle_from_public(request, **{**values, "citations": (), "unknown_reasons": ("LIMIT_EXCEEDED",)})

    def retrieve(self, request):
        self._ready()
        try:
            request = RetrievalRequest.model_validate(request)
        except Exception:
            raise QAError(422) from None
        if any(getattr(request.scope, name).status == "unknown" for name in SCOPE_FIELDS):
            return self._empty(request, "SCOPE_UNKNOWN")
        reader = self.reader
        try:
            with reader._transaction() as session:
                hint = reader.store.get(session, request.release_id, lock=False)
                reader.store.dataset(session, hint.dataset_id)
                root, state, released, proofs = reader._release(session, request.release_id)
                scope = EvidenceScope(dataset_id=root.dataset_id, **request.scope.model_dump())
                model_scope = ModelScope(dataset_id=root.dataset_id, offering_id=request.offering_id,
                    offering_version=request.offering_version, entry_year=request.entry_year)
                selected = tuple(proof for proof in proofs if
                    (proof.member.offering_id, proof.member.offering_version, root.entry_year, proof.evidence.scope) ==
                    (request.offering_id, request.offering_version, request.entry_year, scope))
                citations, reasons = [], []
                if not selected:
                    reasons.append("TARGET_MISMATCH")
                matching = 0
                for proof in selected:
                    fact = reader._fact(proof)
                    if not self._matches_intent(fact, request.intent):
                        continue
                    # Scope and current publication are already proven before
                    # literal text filtering. Keywords never enter a SQL query.
                    searchable = fact.model_dump_json() + "\n" + (proof.evidence.text if proof.member.public_evidence else "")
                    if any(keyword not in searchable for keyword in request.keywords):
                        continue
                    matching += 1
                    if not proof.member.public_evidence:
                        reasons.append("NO_PUBLIC_EVIDENCE")
                        continue
                    evidence = proof.evidence
                    public = PublicEvidenceData(evidence_id=evidence.id, release_id=root.id,
                        release_version=root.version, requirements_version=released.requirements_version,
                        is_synthetic=root.is_synthetic, offering_id=evidence.offering_id,
                        offering_version=evidence.offering_version, entry_year=root.entry_year,
                        language=evidence.language, quote=evidence.text, document_sha256=evidence.document_sha256,
                        snippet_sha256=evidence.snippet_sha256, locator=evidence.locator, scope=evidence.scope,
                        publisher=proof.source.publisher, authority_claim=proof.source.authority_claim)
                    try:
                        atom_value(fact)
                    except ProjectionLimit:
                        reasons.append("LIMIT_EXCEEDED")
                        break
                    citations.append(citation_from_public(fact, public))
                    if fact.value_text is None:
                        reasons.append("VALUE_UNAVAILABLE")
                    if fact.fact_type == "date" and (fact.date_resolution is None
                        or fact.date_resolution.utc_instant is None):
                        reasons.append("DATE_UNRESOLVED")
                if selected and not matching:
                    reasons.append("NO_MATCHING_FACTS")
                if len(citations) > 20 or "LIMIT_EXCEEDED" in reasons:
                    citations = []
                    reasons = ["LIMIT_EXCEEDED"]
                self._ready()
                now = reader._now()
                reader.proof.final_deadlines(proofs, ((root, state),), now)
                result = self._bounded_bundle(request, model_scope=model_scope, release_version=root.version,
                    requirements_version=released.requirements_version, content_sha256=released.content_sha256,
                    citations=citations, unknown_reasons=tuple(dict.fromkeys(reasons)),
                    retrieved_at=now, is_synthetic=root.is_synthetic)
            return result
        except PublicCatalogError as error:
            if error.status_code in {404, 409}:
                return self._empty(request, "RELEASE_UNAVAILABLE")
            raise QAError() from None
        except Exception as error:
            if isinstance(error, QAError):
                raise
            if getattr(error, "status_code", None) in {404, 409}:
                return self._empty(request, "RELEASE_UNAVAILABLE")
            raise QAError() from None
