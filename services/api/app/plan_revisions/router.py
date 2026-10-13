"""Five explicit session/CSRF-protected revision operations."""

import json

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from ..api.v2.errors import ApiError
from ..api.v2.router import ERROR_RESPONSES, foundation_meta
from ..auth.dependencies import current_principal
from ..profiles.router import _body_schema, _call, _id, _unique
from ..profiles.schemas import ProfileMeta
from .schemas import (MAX_BODY_BYTES, ProposeInput, DecisionInput, RevisionContextData, RevisionHistoryData,
    RevisionData, RevisionResult, RevisionEnvelope)

REQUEST_MODELS=(ProposeInput,DecisionInput)
router=APIRouter(prefix="/plan-revisions",responses=ERROR_RESPONSES)


def _service(request):
    request.state.private_access=True
    service=getattr(request.app.state,"revision_service",None)
    if service is None:
        raise ApiError(503,"SERVICE_UNAVAILABLE")
    return service


def _query(request):
    if request.query_params:
        raise ApiError(422,"VALIDATION_ERROR")


async def _body(request,model,principal):
    await _call(_service(request).preflight,principal)
    _query(request)
    if (len(request.headers.getlist("content-type"))!=1 or request.headers["content-type"].lower()!="application/json"
        or request.headers.getlist("idempotency-key")):
        raise ApiError(422,"VALIDATION_ERROR")
    content=bytearray()
    async for chunk in request.stream():
        if len(content)+len(chunk)>MAX_BODY_BYTES:
            raise ApiError(422,"VALIDATION_ERROR")
        content.extend(chunk)
    try:
        raw=json.loads(bytes(content).decode("utf-8"),object_pairs_hook=_unique,
            parse_constant=lambda value:(_ for _ in ()).throw(ValueError()))
        return model.model_validate(raw)
    except ValidationError as error:
        raise RequestValidationError([{**item,"loc":("body",*item["loc"])} for item in error.errors(include_input=False,include_context=False)]) from None
    except (ValueError,TypeError,UnicodeError,RecursionError):
        raise ApiError(422,"VALIDATION_ERROR") from None


def _response(request,value):
    actual=value.revision if isinstance(value,RevisionResult) else value
    pin=actual.new.pin if isinstance(actual,RevisionData) else actual.pin if isinstance(actual,RevisionHistoryData) else None
    fields=foundation_meta(request).model_dump()
    if pin is not None:
        fields.update(profile_version_id=pin.profile_version_id,profile_mode="synthetic" if pin.is_synthetic else "real")
    return RevisionEnvelope(data=value,meta=ProfileMeta.model_validate(fields))


@router.get("/context",response_model=RevisionEnvelope[RevisionContextData],operation_id="getV2RevisionContext")
async def context(request:Request,principal=Depends(current_principal)):
    _query(request)
    service=getattr(request.app.state,"revision_service",None)
    value=(RevisionContextData(schema_version="v2.t35",can_read_history=False,can_propose=False,can_decide=False,
        reason="processing_disabled",is_synthetic=principal.is_synthetic) if service is None else await _call(service.context,principal))
    return _response(request,value)


@router.get("/history/{plan_id}",response_model=RevisionEnvelope[RevisionHistoryData],operation_id="getV2PlanRevisionHistory")
async def history(request:Request,plan_id:str,principal=Depends(current_principal)):
    _query(request)
    return _response(request,await _call(_service(request).get_history,principal,_id(plan_id)))


@router.post("",response_model=RevisionEnvelope[RevisionResult],operation_id="proposeV2PlanRevision",openapi_extra=_body_schema(ProposeInput))
async def propose(request:Request,principal=Depends(current_principal)):
    body=await _body(request,ProposeInput,principal)
    return _response(request,await _call(_service(request).propose,principal,body))


@router.get("/{revision_id}",response_model=RevisionEnvelope[RevisionData],operation_id="getV2PlanRevision")
async def get_revision(request:Request,revision_id:str,principal=Depends(current_principal)):
    _query(request)
    return _response(request,await _call(_service(request).get_revision,principal,_id(revision_id)))


@router.post("/{revision_id}/decision",response_model=RevisionEnvelope[RevisionResult],operation_id="decideV2PlanRevision",openapi_extra=_body_schema(DecisionInput))
async def decide(request:Request,revision_id:str,principal=Depends(current_principal)):
    body=await _body(request,DecisionInput,principal)
    return _response(request,await _call(_service(request).decide,principal,_id(revision_id),body))
