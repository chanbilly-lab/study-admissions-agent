"""Explicit private declarations, bounded before parsing and never cached."""

import json
import re
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from pydantic import SecretStr, ValidationError
from starlette.concurrency import run_in_threadpool

from ..api.v2.errors import ApiError, STATUS_CODES
from ..api.v2.router import ERROR_RESPONSES, foundation_meta
from ..api.v2.schemas import OfferingQuery
from ..auth.dependencies import current_principal
from .schemas import (AppendInput, CreateInput, MAX_PROFILE_BYTES, ProfileContextData,
                      ProfileEnvelope, ProfileMeta, ProfilePage, ProfileVersionData, ProfileWriteData)

REQUEST_MODELS = (CreateInput, AppendInput)
router = APIRouter(prefix="/profiles", responses=ERROR_RESPONSES)


def _service(request):
    request.state.private_access = True
    service = getattr(request.app.state, "profile_service", None)
    if service is None:
        raise ApiError(503, "SERVICE_UNAVAILABLE")
    return service


async def _call(function, *args, **kwargs):
    try:
        return await run_in_threadpool(function, *args, **kwargs)
    except Exception as error:
        status = getattr(error, "status_code", None)
        status = status if type(status) is int and status in STATUS_CODES else 503
        raise ApiError(status, STATUS_CODES[status]) from None


def _id(value):
    try:
        result = UUID(value)
        if str(result) != value:
            raise ValueError()
        return result
    except (ValueError, TypeError, AttributeError):
        raise RequestValidationError([{"type": "value_error", "loc": ("path", "identifier")}]) from None


def _query(request, *, pagination=False):
    pairs = list(request.query_params.multi_items())
    if not pagination:
        if pairs:
            raise RequestValidationError([{"type": "extra_forbidden", "loc": ("query",)}])
        return {}
    values = {}
    try:
        for key, value in pairs:
            if key in values or key not in {"limit", "cursor"}:
                raise ValueError()
            values[key] = value
        limit = int(OfferingQuery.integer_parameter(values.get("limit", "20")))
        if not 1 <= limit <= 20:
            raise ValueError()
        cursor = values.get("cursor")
        if cursor is not None and (not cursor or len(cursor) > 2048):
            raise ValueError()
        return {"limit": limit, "cursor": cursor}
    except (ValueError, TypeError):
        raise RequestValidationError([{"type": "value_error", "loc": ("query",)}]) from None


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


async def _body(request, model, principal):
    service = _service(request)
    await _call(service.preflight, principal)
    _query(request)
    if len(request.headers.getlist("content-type")) != 1 or request.headers["content-type"].lower() != "application/json":
        raise ApiError(422, "VALIDATION_ERROR")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_PROFILE_BYTES:
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


def _body_schema(model):
    return {"requestBody": {"required": True, "content": {"application/json": {
        "schema": {"$ref": "#/components/schemas/" + model.__name__}}}}}


def _response(request, value):
    fields = foundation_meta(request).model_dump()
    version = value.version if isinstance(value, ProfileWriteData) else value
    if isinstance(version, ProfileVersionData):
        fields.update(profile_version_id=version.version_id,
                      profile_mode="synthetic" if version.is_synthetic else "real")
    return ProfileEnvelope(data=value, meta=ProfileMeta.model_validate(fields))


@router.get("/context", response_model=ProfileEnvelope[ProfileContextData], operation_id="getV2ProfilesContext")
async def context(request: Request, principal=Depends(current_principal)):
    _query(request)
    return _response(request, await _call(_service(request).context, principal))


@router.get("", response_model=ProfileEnvelope[ProfilePage], operation_id="listV2Profiles",
    openapi_extra={"parameters": [{"name": "limit", "in": "query", "required": False,
        "schema": {"type": "integer", "minimum": 1, "maximum": 20, "default": 20}},
        {"name": "cursor", "in": "query", "required": False,
         "schema": {"type": "string", "minLength": 1, "maxLength": 2048}}]})
async def list_profiles(request: Request, principal=Depends(current_principal)):
    return _response(request, await _call(_service(request).list_profiles, principal, **_query(request, pagination=True)))


@router.post("", response_model=ProfileEnvelope[ProfileWriteData], operation_id="createV2Profile",
    openapi_extra={**_body_schema(CreateInput), "parameters": [{"name": "Idempotency-Key", "in": "header",
        "required": True, "schema": {"type": "string", "minLength": 1, "maxLength": 128,
        "pattern": r"^[A-Za-z0-9._:-]{1,128}$"}}]})
async def create(request: Request, principal=Depends(current_principal)):
    data = await _body(request, CreateInput, principal)
    keys = request.headers.getlist("idempotency-key")
    if len(keys) != 1 or re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", keys[0]) is None:
        raise ApiError(422, "VALIDATION_ERROR")
    return _response(request, await _call(_service(request).create_profile, principal, data, SecretStr(keys[0])))


@router.get("/{profile_id}", response_model=ProfileEnvelope[ProfileVersionData], operation_id="getV2Profile")
async def get_profile(request: Request, profile_id: str, principal=Depends(current_principal)):
    _query(request)
    return _response(request, await _call(_service(request).get_profile, principal, _id(profile_id)))


@router.get("/{profile_id}/versions/{version_id}", response_model=ProfileEnvelope[ProfileVersionData], operation_id="getV2ProfileVersion")
async def get_version(request: Request, profile_id: str, version_id: str, principal=Depends(current_principal)):
    _query(request)
    return _response(request, await _call(_service(request).get_version, principal, _id(profile_id), _id(version_id)))


@router.post("/{profile_id}/versions", response_model=ProfileEnvelope[ProfileWriteData], operation_id="appendV2ProfileVersion",
             openapi_extra=_body_schema(AppendInput))
async def append(request: Request, profile_id: str, principal=Depends(current_principal)):
    data = await _body(request, AppendInput, principal)
    if request.headers.getlist("idempotency-key"):
        raise ApiError(422, "VALIDATION_ERROR")
    return _response(request, await _call(_service(request).append_version, principal, _id(profile_id), data))
