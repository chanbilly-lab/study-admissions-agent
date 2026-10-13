"""Read-only current retrieval around an actual bounded asynchronous gateway."""

from uuid import uuid4

from starlette.concurrency import run_in_threadpool

from ..model_gateway.gateway import ModelGateway
from ..model_gateway.schemas import BudgetKey, GatewayError, ModelRequest, StructuredAnswer
from ..public_catalog.schemas import DEMO_BANNER
from ..settings import V2RuntimeSettings
from .http_schemas import QAAnswerData, QAContextData
from .retrieval import ScopedRetriever
from .schemas import QAError, RetrievalRequest, fingerprint
from .validation import validate_answer

QUESTIONS = {
    "requirements": "Return only exact provided current requirement values with their citation identities.",
    "materials": "Return only exact provided current material values with their citation identities.",
    "dates": "Return only exact provided original date values; candidate UTC is not an official deadline.",
    "fees": "Return only exact provided current fee values, preserving units and citation identities.",
    "background": "Return only exact provided background values; statistics and typical offers are not hard requirements.",
}


class QAService:
    def __init__(self, settings, *, retriever, gateway, budget_key=None):
        try:
            self.settings = V2RuntimeSettings.model_validate(settings)
            if type(retriever) is not ScopedRetriever or type(gateway) is not ModelGateway:
                raise ValueError()
            self.retriever, self.gateway = retriever, gateway
            self.budget_key = BudgetKey.model_validate(budget_key) if budget_key is not None else BudgetKey(key_id=uuid4())
            self._references = (retriever, gateway, gateway.budget, gateway.provider, gateway.budget.clock)
            self._questions = tuple(QUESTIONS.items())
            self._initial = self._configuration()
            self.preflight()
        except Exception:
            raise QAError() from None

    def _configuration(self):
        settings = V2RuntimeSettings.model_validate(self.settings)
        self.gateway._validate()
        self.retriever._ready()
        if self.retriever.reader.settings != settings:
            raise QAError()
        values = [settings.model_dump(mode="json"), self.gateway.policy.model_dump(mode="json"),
            self.gateway.budget.policy.model_dump(mode="json"), self.budget_key.model_dump(mode="json"),
            self.retriever._configuration()]
        values.append(fingerprint(settings.database_url.get_secret_value()) if settings.database_url is not None else None)
        return fingerprint(values)

    def preflight(self):
        try:
            runtime = V2RuntimeSettings.model_validate(self.settings)
            if runtime.model_mode != "mock":
                raise GatewayError("MODEL_DISABLED")
            if (runtime.app_environment != "test" or runtime.data_mode != "demo"
                or (self.retriever, self.gateway, self.gateway.budget, self.gateway.provider, self.gateway.budget.clock) != self._references
                or self.gateway.policy.app_environment != "test" or self.gateway.policy.data_mode != "demo"
                or self.gateway.policy.model_mode != "mock" or self.gateway.budget.policy.max_output_tokens != 4096
                or tuple(QUESTIONS.items()) != self._questions
                or self._configuration() != self._initial):
                raise QAError()
        except (QAError, GatewayError):
            raise
        except Exception:
            raise QAError() from None

    def context(self):
        self.preflight()
        return QAContextData(schema_version="v2.t39", can_ask=True, model_mode="mock", live_available=False,
            real_processing_enabled=False, allow_test_fixture_read=True, demo_banner=DEMO_BANNER,
            disabled_reason=None, budget_unit="conservative_utf8_bytes")

    async def answer(self, request):
        try:
            return await self._answer(request)
        except (QAError, GatewayError):
            raise
        except Exception:
            raise QAError() from None

    async def _answer(self, request):
        self.preflight()
        try:
            request = RetrievalRequest.model_validate(request)
        except Exception:
            raise QAError(422) from None
        bundle = await run_in_threadpool(self.retriever.retrieve, request)
        self.preflight()
        if bundle.atoms:
            response = await self.gateway.complete(self.budget_key, ModelRequest(scope=bundle.model_scope,
                question=QUESTIONS[request.intent], evidence=bundle.atoms))
            answer = response.answer
        else:
            answer = StructuredAnswer(status="unknown", claims=(), advice_codes=("MISSING_EVIDENCE",))
        self.preflight()
        verified = await run_in_threadpool(validate_answer, self.retriever, bundle, answer)
        self.preflight()
        by_id = {item.id: item for item in bundle.citations}
        return QAAnswerData(schema_version="v2.t39", status=verified.status, request=request,
            model_scope=bundle.model_scope, release_version=bundle.release_version,
            requirements_version=bundle.requirements_version, content_sha256=bundle.content_sha256,
            citations=tuple(by_id[item.citation_id] for item in verified.claims), advice_codes=verified.advice_codes,
            unknown_reasons=bundle.unknown_reasons, is_synthetic=bundle.is_synthetic,
            model_mode="mock", live_available=False, generated_at=self.retriever.reader._now())
