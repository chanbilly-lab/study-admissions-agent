"""Opt-in private assessments; no domain or database imports on schema startup."""

import json

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from ..api.v2.errors import ApiError
from ..api.v2.router import ERROR_RESPONSES, foundation_meta
from ..auth.dependencies import current_principal
from ..profiles.router import _call, _id, _query, _unique, _body_schema
from .schemas import (AssessmentContextData, AssessmentData, AssessmentEnvelope, AssessmentMeta,
                      AssessmentRequest, MAX_ASSESSMENT_REQUEST_BYTES, ReplayRequest)

REQUEST_MODELS = (AssessmentRequest, ReplayRequest)
router = APIRouter(prefix="/eligibility", responses=ERROR_RESPONSES)


def _service(request):
    request.state.private_access = True
    service = getattr(request.app.state, "assessment_service", None)
    if service is None:
        raise ApiError(503, "SERVICE_UNAVAILABLE")
    return service


async def _body(request, model, principal):
    await _call(_service(request).preflight, principal)
    _query(request)
    if (request.headers.getlist("idempotency-key") or len(request.headers.getlist("content-type")) != 1
        or request.headers["content-type"].lower() != "application/json"):
        raise ApiError(422, "VALIDATION_ERROR")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_ASSESSMENT_REQUEST_BYTES:
            raise ApiError(422, "VALIDATION_ERROR")
        data.extend(chunk)
    try:
        raw = json.loads(bytes(data).decode("utf-8"), object_pairs_hook=_unique,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))
        return model.model_validate(raw)
    except ValidationError as error:
        raise RequestValidationError([{**item, "loc": ("body", *item["loc"])}
            for item in error.errors(include_input=False, include_context=False)]) from None
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise ApiError(422, "VALIDATION_ERROR") from None


def _response(request, value):
    meta = foundation_meta(request).model_dump()
    if isinstance(value, AssessmentData):
        meta.update(profile_version_id=value.profile_version_id,
                    profile_mode="synthetic" if value.profile_is_synthetic else "real")
    return AssessmentEnvelope(data=value, meta=AssessmentMeta.model_validate(meta))


@router.get("/context", response_model=AssessmentEnvelope[AssessmentContextData], operation_id="getV2EligibilityContext")
async def context(request: Request, principal=Depends(current_principal)):
    _query(request)
    return _response(request, await _call(_service(request).context, principal))


@router.post("/evaluations", response_model=AssessmentEnvelope[AssessmentData], operation_id="evaluateV2Eligibility",
             openapi_extra=_body_schema(AssessmentRequest))
async def evaluate(request: Request, principal=Depends(current_principal)):
    body = await _body(request, AssessmentRequest, principal)
    return _response(request, await _call(_service(request).evaluate, principal, body))


@router.get("/evaluations/{assessment_id}", response_model=AssessmentEnvelope[AssessmentData], operation_id="getV2EligibilityEvaluation")
async def get_assessment(request: Request, assessment_id: str, principal=Depends(current_principal)):
    _query(request)
    return _response(request, await _call(_service(request).get_assessment, principal, _id(assessment_id)))


@router.post("/evaluations/{assessment_id}/replay", response_model=AssessmentEnvelope[AssessmentData], operation_id="replayV2EligibilityEvaluation",
             openapi_extra=_body_schema(ReplayRequest))
async def replay(request: Request, assessment_id: str, principal=Depends(current_principal)):
    body = await _body(request, ReplayRequest, principal)
    return _response(request, await _call(_service(request).replay, principal, _id(assessment_id), body))
