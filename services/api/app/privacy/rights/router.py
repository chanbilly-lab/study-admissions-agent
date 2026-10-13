"""Six finite operations; origin/CSRF are inherited from the identity factory."""
import json
from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from ...api.v2.errors import ApiError
from ...api.v2.router import ERROR_RESPONSES, foundation_meta
from ...auth.dependencies import current_principal
from ...profiles.router import _body_schema, _call, _id, _query, _unique
from ...profiles.schemas import ProfileEnvelope, ProfileMeta
from .schemas import ExportContent, OwnerConfirmation, RightsContext, RightsRequestData

REQUEST_MODELS = (OwnerConfirmation,)
router = APIRouter(responses=ERROR_RESPONSES)


def service(request):
    request.state.private_access = True
    value = getattr(request.app.state, "rights_service", None)
    if value is None:
        raise ApiError(503, "SERVICE_UNAVAILABLE")
    return value


def response(request, value):
    return ProfileEnvelope(data=value, meta=ProfileMeta.model_validate(foundation_meta(request).model_dump()))


async def confirmation(request, principal):
    await _call(service(request).preflight, principal)
    _query(request)
    if (len(request.headers.getlist("content-type")) != 1 or request.headers["content-type"].lower() != "application/json"
        or request.headers.getlist("idempotency-key")):
        raise ApiError(422, "VALIDATION_ERROR")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 16384:
            raise ApiError(422, "VALIDATION_ERROR")
        body.extend(chunk)
    try:
        return OwnerConfirmation.model_validate(json.loads(bytes(body).decode("utf-8"), object_pairs_hook=_unique,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError())))
    except ValidationError as error:
        raise RequestValidationError([{**item, "loc": ("body", *item["loc"])} for item in error.errors(include_input=False, include_context=False)]) from None
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ApiError(422, "VALIDATION_ERROR") from None


@router.get("/privacy/rights/context", response_model=ProfileEnvelope[RightsContext], operation_id="getV2RightsContext")
async def context(request: Request):
    _query(request)
    request.state.private_access = True
    value = getattr(request.app.state, "rights_service", None)
    if value is None:
        return response(request, RightsContext(enabled=False, reason="RIGHTS_DISABLED"))
    principal = current_principal(request)
    return response(request, await _call(value.context, principal))


@router.post("/privacy/exports", response_model=ProfileEnvelope[RightsRequestData], operation_id="createV2Export", openapi_extra=_body_schema(OwnerConfirmation))
async def create_export(request: Request, principal=Depends(current_principal)):
    body = await confirmation(request, principal)
    return response(request, await _call(service(request).create, principal, "export", body))


@router.get("/privacy/exports/{request_id}", response_model=ProfileEnvelope[RightsRequestData], operation_id="getV2Export")
async def get_export(request: Request, request_id: str, principal=Depends(current_principal)):
    _query(request)
    return response(request, await _call(service(request).get, principal, _id(request_id), "export"))


@router.get("/privacy/exports/{request_id}/content", response_model=ProfileEnvelope[ExportContent], operation_id="getV2ExportContent")
async def content(request: Request, request_id: str, principal=Depends(current_principal)):
    _query(request)
    return response(request, await _call(service(request).content, principal, _id(request_id)))


@router.post("/privacy/deletions", response_model=ProfileEnvelope[RightsRequestData], operation_id="createV2Deletion", openapi_extra=_body_schema(OwnerConfirmation))
async def create_deletion(request: Request, principal=Depends(current_principal)):
    body = await confirmation(request, principal)
    return response(request, await _call(service(request).create, principal, "deletion", body))


@router.get("/privacy/deletions/{request_id}", response_model=ProfileEnvelope[RightsRequestData], operation_id="getV2Deletion")
async def get_deletion(request: Request, request_id: str, principal=Depends(current_principal)):
    _query(request)
    return response(request, await _call(service(request).get, principal, _id(request_id), "deletion"))
