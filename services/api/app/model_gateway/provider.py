"""An async read-only port and a deterministic synthetic offline provider."""

from typing import Protocol, runtime_checkable

from .schemas import Claim,ProviderResponse,StructuredAnswer,GatewayError,input_units,validate_request


@runtime_checkable
class ModelProvider(Protocol):
    async def complete(self, request) -> ProviderResponse: ...


class OfflineMock:
    async def complete(self,request):
        request=validate_request(request)
        if any(atom.is_synthetic is not True for atom in request.evidence):
            raise GatewayError("INVALID_MODEL_INPUT")
        if request.evidence and all("<" not in atom.value and ">" not in atom.value for atom in request.evidence):
            answer=StructuredAnswer(status="answered",claims=tuple(Claim(citation_id=atom.citation_id,value=atom.value)
                for atom in request.evidence),advice_codes=("REVIEW_SOURCE",))
        else:
            answer=StructuredAnswer(status="unknown",claims=(),advice_codes=("MISSING_EVIDENCE",))
        return ProviderResponse(answer=answer,input_usage=input_units(request),output_usage=0,is_synthetic=True)
