"""Bounded explicit review work; original domain DTOs remain unchanged."""

import re

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from pydantic import SecretStr

from ...api.v2.errors import ApiError
from ...api.v2.router import ERROR_RESPONSES
from ...api.v2.schemas import Envelope, OfferingQuery
from ...auth.dependencies import current_principal
from ...evidence.schemas import DocumentData, SnippetData, VersionData
from ...facts.schemas import TypedCandidate
from ...releases.schemas import ReleaseData
from ...reviews.schemas import ReviewDecisionData
from ..http.router import _body, _body_schema, _call, _envelope, _identifier, _query
from .schemas import (AdminDocumentInput, AdminFactInput, AdminPublishInput, AdminReviewInput,
    AdminSnippetInput, AdminVersionInput, AdminWithdrawalInput, CurrentReleaseData, ImportRowsData,
    PublishPrecheckData, ReviewCandidatesData, ReviewContextData, ReviewDetailData)


REQUEST_MODELS = (AdminDocumentInput, AdminVersionInput, AdminSnippetInput, AdminFactInput,
                  AdminReviewInput, AdminPublishInput, AdminWithdrawalInput)
router = APIRouter(prefix="/admin", responses=ERROR_RESPONSES)


def _facade(request):
    request.state.private_access = True
    facade = getattr(request.app.state, "admin_review_facade", None)
    if facade is None:
        raise ApiError(503, "SERVICE_UNAVAILABLE")
    return facade


def _parameters(*, scope=False, page=False, maximum=100):
    fields = []
    if scope:
        fields.extend([{"name": "dataset_id", "in": "query", "required": True,
            "schema": {"type": "string", "format": "uuid"}},
            {"name": "entry_year", "in": "query", "required": True,
                "schema": {"type": "integer", "minimum": 1, "maximum": 9999}}])
    if page:
        fields.extend([{"name": "limit", "in": "query", "required": False,
            "schema": {"type": "integer", "minimum": 1, "maximum": maximum, "default": 20}},
            {"name": "cursor", "in": "query", "required": False,
                "schema": {"type": "string", "minLength": 1, "maxLength": 1024}}])
    return {"parameters": fields}


def _queries(request, *, scope=False, page=False, maximum=100):
    values = {}
    allowed = ({"dataset_id", "entry_year"} if scope else set()) | ({"limit", "cursor"} if page else set())
    try:
        for key, value in request.query_params.multi_items():
            if key not in allowed or key in values:
                raise ValueError
            values[key] = value
        result = []
        if scope:
            result.extend((_identifier(values["dataset_id"]), _integer(values["entry_year"], 9999)))
        if page:
            cursor = values.get("cursor")
            if cursor is not None and (not 1 <= len(cursor) <= 1024 or not cursor.isascii()):
                raise ValueError
            result.extend((_integer(values.get("limit", "20"), maximum), cursor))
        return tuple(result)
    except (ValueError, TypeError, KeyError):
        raise RequestValidationError([{"type": "value_error", "loc": ("query",)}]) from None


def _integer(value, maximum):
    parsed = int(OfferingQuery.integer_parameter(value))
    if not 1 <= parsed <= maximum:
        raise ValueError
    return parsed


@router.get("/review-context", response_model=Envelope[ReviewContextData], operation_id="getV2ReviewContext")
async def context(request: Request, principal=Depends(current_principal)):
    _query(request)
    return _envelope(request, await _call(_facade(request).context, principal))


@router.get("/imports/{import_id}/rows", response_model=Envelope[ImportRowsData], operation_id="getV2AdminImportRows",
    openapi_extra=_parameters(page=True, maximum=20))
async def rows(request: Request, import_id: str, principal=Depends(current_principal)):
    limit, cursor = _queries(request, page=True, maximum=20)
    return _envelope(request, await _call(_facade(request).import_rows, principal, _identifier(import_id), limit, cursor))


@router.post("/evidence/documents", response_model=Envelope[DocumentData], operation_id="createV2EvidenceDocument",
    openapi_extra=_body_schema(AdminDocumentInput))
async def document(request: Request, principal=Depends(current_principal)):
    data = await _body(request, AdminDocumentInput, principal, "catalog.import")
    return _envelope(request, await _call(_facade(request).create_document, principal, data))


@router.post("/evidence/versions", response_model=Envelope[VersionData], operation_id="createV2EvidenceVersion",
    openapi_extra=_body_schema(AdminVersionInput))
async def version(request: Request, principal=Depends(current_principal)):
    data = await _body(request, AdminVersionInput, principal, "catalog.import")
    return _envelope(request, await _call(_facade(request).create_version, principal, data))


@router.post("/evidence/snippets", response_model=Envelope[SnippetData], operation_id="createV2EvidenceSnippet",
    openapi_extra=_body_schema(AdminSnippetInput))
async def snippet(request: Request, principal=Depends(current_principal)):
    data = await _body(request, AdminSnippetInput, principal, "catalog.import")
    return _envelope(request, await _call(_facade(request).create_snippet, principal, data))


@router.post("/facts", response_model=Envelope[TypedCandidate], operation_id="createV2TypedFact",
    openapi_extra=_body_schema(AdminFactInput))
async def fact(request: Request, principal=Depends(current_principal)):
    data = await _body(request, AdminFactInput, principal, "catalog.import")
    return _envelope(request, await _call(_facade(request).create_fact, principal, data))


@router.get("/review-candidates", response_model=Envelope[ReviewCandidatesData], operation_id="listV2ReviewCandidates",
    openapi_extra=_parameters(scope=True, page=True))
async def candidates(request: Request, principal=Depends(current_principal)):
    args = _queries(request, scope=True, page=True)
    return _envelope(request, await _call(_facade(request).candidates, principal, *args))


@router.get("/review-candidates/{fact_id}", response_model=Envelope[ReviewDetailData], operation_id="getV2ReviewDetail")
async def detail(request: Request, fact_id: str, principal=Depends(current_principal)):
    _query(request)
    return _envelope(request, await _call(_facade(request).detail, principal, _identifier(fact_id)))


@router.post("/review-decisions", response_model=Envelope[ReviewDecisionData], operation_id="createV2ReviewDecision",
    openapi_extra=_body_schema(AdminReviewInput))
async def decision(request: Request, principal=Depends(current_principal)):
    data = await _body(request, AdminReviewInput, principal, "catalog.review")
    return _envelope(request, await _call(_facade(request).decide, principal, data))


@router.post("/releases/precheck", response_model=Envelope[PublishPrecheckData], operation_id="precheckV2Release",
    openapi_extra=_body_schema(AdminPublishInput))
async def precheck(request: Request, principal=Depends(current_principal)):
    data = await _body(request, AdminPublishInput, principal, "catalog.publish")
    return _envelope(request, await _call(_facade(request).precheck, principal, data))


@router.post("/releases", response_model=Envelope[ReleaseData], operation_id="publishV2AdminRelease",
    openapi_extra={**_body_schema(AdminPublishInput), "parameters": [{"name": "Idempotency-Key", "in": "header",
        "required": True, "schema": {"type": "string", "minLength": 1, "maxLength": 128,
            "pattern": "^[A-Za-z0-9._:-]{1,128}$"}}]})
async def publish(request: Request, principal=Depends(current_principal)):
    values = request.headers.getlist("idempotency-key")
    if len(values) != 1 or re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", values[0]) is None:
        raise ApiError(422, "VALIDATION_ERROR")
    data = await _body(request, AdminPublishInput, principal, "catalog.publish")
    return _envelope(request, await _call(_facade(request).publish, principal, data, SecretStr(values[0])))


@router.get("/releases/current", response_model=Envelope[CurrentReleaseData], operation_id="getV2CurrentRelease",
    openapi_extra=_parameters(scope=True))
async def current(request: Request, principal=Depends(current_principal)):
    return _envelope(request, await _call(_facade(request).current_release, principal, *_queries(request, scope=True)))


@router.get("/releases/{release_id}", response_model=Envelope[ReleaseData], operation_id="getV2AdminRelease")
async def release(request: Request, release_id: str, principal=Depends(current_principal)):
    _query(request)
    return _envelope(request, await _call(_facade(request).get_release, principal, _identifier(release_id)))


@router.post("/releases/{release_id}/withdraw", response_model=Envelope[ReleaseData], operation_id="withdrawV2AdminRelease",
    openapi_extra=_body_schema(AdminWithdrawalInput))
async def withdraw(request: Request, release_id: str, principal=Depends(current_principal)):
    data = await _body(request, AdminWithdrawalInput, principal, "catalog.withdraw")
    return _envelope(request, await _call(_facade(request).withdraw, principal, _identifier(release_id), data))
