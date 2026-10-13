"""Bounded, explicitly confirmed administration endpoints; no URL fetching."""

import json
import re
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from pydantic import SecretStr, ValidationError
from starlette.concurrency import run_in_threadpool

from ...api.v2.errors import ApiError, STATUS_CODES
from ...api.v2.router import ERROR_RESPONSES, foundation_meta
from ...api.v2.schemas import Envelope, OfferingQuery
from ...auth.dependencies import current_principal
from ...ingestion.schemas import ImportResult, MAX_IMPORT_BYTES
from ...storage.schemas import FileData
from .schemas import (AdminContextData, AdminImportInput, AdminSourceData, AdminSourceFileInput,
                      AdminSourceRegisterInput, AdminSourceRevisionInput)

MAX_BODY_BYTES = 32768
MAX_UPLOAD_BODY_BYTES = 6 * MAX_IMPORT_BYTES + 16384
REQUEST_MODELS = (AdminSourceRegisterInput, AdminSourceRevisionInput, AdminSourceFileInput, AdminImportInput)
router = APIRouter(prefix="/admin", responses=ERROR_RESPONSES)


def safe_failure(error):
    # Only fixed domain errors carry this server-validated integer status.
    status = getattr(error, "status_code", None)
    if type(status) is not int or status not in STATUS_CODES:
        status = 503
    return ApiError(status, STATUS_CODES[status])


def _facade(request):
    request.state.private_access = True
    facade = getattr(request.app.state, "admin_facade", None)
    if facade is None:
        raise ApiError(503, "SERVICE_UNAVAILABLE")
    return facade


async def _call(function, *args):
    try:
        return await run_in_threadpool(function, *args)
    except Exception as error:
        raise safe_failure(error) from None


def _identifier(value):
    try:
        parsed = UUID(value)
        if str(parsed) != value:
            raise ValueError
        return parsed
    except (ValueError, TypeError, AttributeError):
        raise RequestValidationError([{"type": "value_error", "loc": ("path", "identifier")}]) from None


def _query(request, *, version=False):
    pairs = list(request.query_params.multi_items())
    if not pairs:
        return None
    if not version or len(pairs) != 1 or pairs[0][0] != "version":
        raise RequestValidationError([{"type": "extra_forbidden", "loc": ("query",)}])
    try:
        value = OfferingQuery.integer_parameter(pairs[0][1])
        result = int(value)
        if not 1 <= result <= 2147483647:
            raise ValueError
        return result
    except (ValueError, TypeError):
        raise RequestValidationError([{"type": "value_error", "loc": ("query", "version")}]) from None


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


async def _body(request, model, principal, capability):
    facade = _facade(request)
    await _call(facade.preflight, principal, capability)
    _query(request)
    if len(request.headers.getlist("content-type")) != 1 or request.headers["content-type"].lower() != "application/json":
        raise ApiError(422, "VALIDATION_ERROR")
    limit = MAX_UPLOAD_BODY_BYTES if model is AdminSourceFileInput else MAX_BODY_BYTES
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > limit:
            raise ApiError(422, "VALIDATION_ERROR")
        data.extend(chunk)
    try:
        value = json.loads(bytes(data).decode("utf-8"), object_pairs_hook=_unique,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError("invalid JSON constant")))
        return model.model_validate(value)
    except ValidationError as error:
        raise RequestValidationError([{**item, "loc": ("body", *item["loc"])}
                                      for item in error.errors(include_input=False, include_context=False)]) from None
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ApiError(422, "VALIDATION_ERROR") from None


def _body_schema(model):
    return {"requestBody": {"required": True, "content": {"application/json": {
        "schema": {"$ref": "#/components/schemas/" + model.__name__}}}}}


def _envelope(request, value):
    return Envelope(data=value, meta=foundation_meta(request))


@router.get("/context", response_model=Envelope[AdminContextData], operation_id="getV2AdminContext")
async def context(request: Request, principal=Depends(current_principal)):
    _query(request)
    return _envelope(request, await _call(_facade(request).context, principal))


@router.post("/sources", response_model=Envelope[AdminSourceData], operation_id="registerV2AdminSource",
             openapi_extra=_body_schema(AdminSourceRegisterInput))
async def register_source(request: Request, principal=Depends(current_principal)):
    data = await _body(request, AdminSourceRegisterInput, principal, "catalog.source.register")
    return _envelope(request, await _call(_facade(request).register, principal, data))


@router.get("/sources/{source_id}", response_model=Envelope[AdminSourceData], operation_id="getV2AdminSource",
            openapi_extra={"parameters": [{"name": "version", "in": "query", "required": False,
                "schema": {"type": "integer", "minimum": 1, "maximum": 2147483647}}]})
async def source(request: Request, source_id: str, principal=Depends(current_principal)):
    version = _query(request, version=True)
    return _envelope(request, await _call(_facade(request).get_source, principal, _identifier(source_id), version))


@router.put("/sources/{source_id}", response_model=Envelope[AdminSourceData], operation_id="reviseV2AdminSource",
            openapi_extra=_body_schema(AdminSourceRevisionInput))
async def revise_source(request: Request, source_id: str, principal=Depends(current_principal)):
    data = await _body(request, AdminSourceRevisionInput, principal, "catalog.source.register")
    return _envelope(request, await _call(_facade(request).revise, principal, _identifier(source_id), data))


@router.post("/source-files", response_model=Envelope[FileData], operation_id="uploadV2AdminSourceFile",
             openapi_extra=_body_schema(AdminSourceFileInput))
async def upload(request: Request, principal=Depends(current_principal)):
    data = await _body(request, AdminSourceFileInput, principal, "catalog.storage.write")
    return _envelope(request, await _call(_facade(request).upload, principal, data))


@router.post("/imports", response_model=Envelope[ImportResult], operation_id="createV2AdminImport",
             openapi_extra={**_body_schema(AdminImportInput), "parameters": [{"name": "Idempotency-Key",
                "in": "header", "required": True, "schema": {"type": "string", "minLength": 1,
                    "maxLength": 128, "pattern": "^[A-Za-z0-9._:-]{1,128}$"}}]})
async def import_file(request: Request, principal=Depends(current_principal)):
    values = request.headers.getlist("idempotency-key")
    if len(values) != 1 or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", values[0]):
        raise ApiError(422, "VALIDATION_ERROR")
    data = await _body(request, AdminImportInput, principal, "catalog.import")
    return _envelope(request, await _call(_facade(request).import_file, principal, data, SecretStr(values[0])))


@router.get("/imports/{import_id}", response_model=Envelope[ImportResult], operation_id="getV2AdminImport")
async def get_import(request: Request, import_id: str, principal=Depends(current_principal)):
    _query(request)
    return _envelope(request, await _call(_facade(request).get_import, principal, _identifier(import_id)))
