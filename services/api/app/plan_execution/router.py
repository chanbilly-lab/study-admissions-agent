"""Bounded owner-only T32 HTTP operations on an explicit execution service."""

import json
import re

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from pydantic import SecretStr, ValidationError

from ..api.v2.errors import ApiError
from ..api.v2.router import ERROR_RESPONSES, foundation_meta
from ..auth.dependencies import current_principal
from ..plans.schemas import PlanCreateInput
from ..profiles.router import _body_schema, _call, _id, _unique
from .http_schemas import HttpWorkspaceInput, PlanEnvelope, PlanMeta
from .schemas import (CompleteInput, CompleteResult, ConfirmInput, ConfirmResult,
                      ExecutionContextData, ExecutionData, ExecutionPage, MAX_BODY_BYTES)

REQUEST_MODELS = (PlanCreateInput, HttpWorkspaceInput, ConfirmInput, CompleteInput)
router = APIRouter(prefix="/plans", responses=ERROR_RESPONSES)
IDEMPOTENCY_SCHEMA = {"name": "Idempotency-Key", "in": "header", "required": True,
    "schema": {"type": "string", "minLength": 1, "maxLength": 128, "pattern": "^[A-Za-z0-9._:-]{1,128}$"}}
PAGINATION_SCHEMA = {"parameters": [
    {"name": "limit", "in": "query", "required": False,
     "schema": {"type": "integer", "minimum": 1, "maximum": 20, "default": 20}},
    {"name": "cursor", "in": "query", "required": False,
     "schema": {"type": "string", "minLength": 1, "maxLength": 1024}}]}


def _service(request):
    request.state.private_access = True
    service = getattr(request.app.state, "execution_service", None)
    if service is None:
        raise ApiError(503, "SERVICE_UNAVAILABLE")
    return service


def _query(request, *, pagination=False):
    pairs = request.query_params.multi_items()
    if not pagination:
        if pairs:
            raise ApiError(422, "VALIDATION_ERROR")
        return {}
    try:
        values = {}
        for key, value in pairs:
            if key in values or key not in {"limit", "cursor"}:
                raise ValueError()
            values[key] = value
        limit = values.get("limit", "20")
        if len(limit) > 2 or re.fullmatch(r"[1-9][0-9]*", limit) is None or not 1 <= int(limit) <= 20:
            raise ValueError()
        cursor = values.get("cursor")
        if cursor is not None and (not cursor or len(cursor) > 1024):
            raise ValueError()
        return {"limit": int(limit), "cursor": cursor}
    except (ValueError, TypeError):
        raise ApiError(422, "VALIDATION_ERROR") from None


def _state_version(value):
    if type(value) is not str or re.fullmatch(r"[1-9][0-9]*", value) is None:
        raise ApiError(422, "VALIDATION_ERROR")
    # The length check precedes int conversion, avoiding unbounded digit work.
    if len(value) > 10 or int(value) > 2147483647:
        raise ApiError(422, "VALIDATION_ERROR")
    return int(value)


def _task_key(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ApiError(422, "VALIDATION_ERROR")
    return value


async def _body(request, model, principal, *, idempotent=False):
    await _call(_service(request).preflight, principal)
    _query(request)
    if (len(request.headers.getlist("content-type")) != 1
        or request.headers["content-type"].lower() != "application/json"
        or not idempotent and request.headers.getlist("idempotency-key")):
        raise ApiError(422, "VALIDATION_ERROR")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BODY_BYTES:
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
    fields = foundation_meta(request).model_dump()
    execution = value.execution if isinstance(value, (ConfirmResult, CompleteResult)) else value
    if isinstance(execution, ExecutionData):
        fields.update(profile_version_id=execution.proposal.effective_draft.profile_version_id,
                      profile_mode="synthetic" if execution.is_synthetic else "real")
    return PlanEnvelope(data=value, meta=PlanMeta.model_validate(fields))


@router.get("/context", response_model=PlanEnvelope[ExecutionContextData], operation_id="getV2PlansContext")
async def context(request: Request, principal=Depends(current_principal)):
    _query(request)
    service = getattr(request.app.state, "execution_service", None)
    if service is None:
        # The dependency has checked the current cookie. Optional execution
        # does not promise any capability merely because identity is enabled.
        value = ExecutionContextData(schema_version="v2.t32", can_create=False, can_read=False,
            can_edit=False, can_confirm=False, can_complete=False, reason="processing_disabled",
            is_synthetic=principal.is_synthetic)
    else:
        value = await _call(service.context, principal)
    return _response(request, value)


@router.get("", response_model=PlanEnvelope[ExecutionPage], operation_id="listV2Plans", openapi_extra=PAGINATION_SCHEMA)
async def list_plans(request: Request, principal=Depends(current_principal)):
    return _response(request, await _call(_service(request).list_plans, principal, **_query(request, pagination=True)))


@router.post("", response_model=PlanEnvelope[ExecutionData], operation_id="createV2Plan", openapi_extra=_body_schema(PlanCreateInput))
async def create_plan(request: Request, principal=Depends(current_principal)):
    body = await _body(request, PlanCreateInput, principal)
    return _response(request, await _call(_service(request).create_plan, principal, body))


@router.get("/{plan_id}", response_model=PlanEnvelope[ExecutionData], operation_id="getV2Plan")
async def get_plan(request: Request, plan_id: str, principal=Depends(current_principal)):
    _query(request)
    return _response(request, await _call(_service(request).get_plan, principal, _id(plan_id)))


@router.get("/{plan_id}/versions/{state_version}", response_model=PlanEnvelope[ExecutionData], operation_id="getV2PlanVersion")
async def get_version(request: Request, plan_id: str, state_version: str, principal=Depends(current_principal)):
    _query(request)
    return _response(request, await _call(_service(request).get_version, principal, _id(plan_id), _state_version(state_version)))


@router.post("/{plan_id}/workspace", response_model=PlanEnvelope[ExecutionData], operation_id="updateV2PlanWorkspace", openapi_extra=_body_schema(HttpWorkspaceInput))
async def workspace(request: Request, plan_id: str, principal=Depends(current_principal)):
    body = await _body(request, HttpWorkspaceInput, principal)
    return _response(request, await _call(_service(request).update_workspace, principal, _id(plan_id), body.to_domain()))


@router.post("/{plan_id}/confirm", response_model=PlanEnvelope[ConfirmResult], operation_id="confirmV2Plan",
    openapi_extra={**_body_schema(ConfirmInput), "parameters": [IDEMPOTENCY_SCHEMA]})
async def confirm(request: Request, plan_id: str, principal=Depends(current_principal)):
    body = await _body(request, ConfirmInput, principal, idempotent=True)
    keys = request.headers.getlist("idempotency-key")
    if len(keys) != 1 or re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", keys[0]) is None:
        raise ApiError(422, "VALIDATION_ERROR")
    return _response(request, await _call(_service(request).confirm_plan, principal, _id(plan_id), body, SecretStr(keys[0])))


@router.post("/{plan_id}/tasks/{task_key}/complete", response_model=PlanEnvelope[CompleteResult], operation_id="completeV2PlanTask", openapi_extra=_body_schema(CompleteInput))
async def complete(request: Request, plan_id: str, task_key: str, principal=Depends(current_principal)):
    body = await _body(request, CompleteInput, principal)
    return _response(request, await _call(_service(request).complete_task, principal, _id(plan_id), _task_key(task_key), body))
