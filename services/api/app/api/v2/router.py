"""Isolated runtime configuration and a fail-closed empty foundation catalog."""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.exceptions import RequestValidationError

from ..catalog_access import CatalogAccessError
from .errors import ApiError, MESSAGES, STATUS_CODES, request_id
from .schemas import (
    Envelope, ErrorDetail, ErrorEnvelope, FoundationConfig, Meta,
    OfferingQuery, OfferingReference, Page, PageInfo,
)


REQUEST_ID_HEADER = {
    "X-Request-ID": {"description": "Server-generated request identifier",
                     "schema": {"type": "string", "pattern": r"^[0-9a-f]{32}$"}},
}
ERROR_RESPONSES = {
    status: {"model": ErrorEnvelope, "description": MESSAGES[code], "headers": REQUEST_ID_HEADER}
    for status, code in STATUS_CODES.items()
}


def reject_demo_credentials(request: Request) -> None:
    if request.app.state.runtime_settings.data_mode != "verified":
        return
    # Inspect every raw header, including coalesced duplicate values. No token
    # here becomes a real identity; recognized DEMO credentials are prohibited.
    pattern = r"(?:^|[\s,])(?i:bearer)\s+(?:demo-alice-token|demo-bob-token)(?=$|[\s,])"
    if any(re.search(pattern, header, re.IGNORECASE) for header in request.headers.getlist("authorization")):
        raise ApiError(401, "UNAUTHORIZED", headers={"WWW-Authenticate": "Bearer"})


router = APIRouter(responses=ERROR_RESPONSES)


def foundation_meta(request: Request) -> Meta:
    settings = request.app.state.runtime_settings
    return Meta(api_version="v2", request_id=request_id(request), data_as_of=None,
                profile_version_id=None, release_id=None, ruleset_version=None,
                profile_mode=None, data_mode=settings.data_mode, model_mode=settings.model_mode)


def no_config_query(request: Request) -> None:
    if request.query_params:
        raise RequestValidationError([{"type": "extra_forbidden", "loc": ("query",)}])


def unique_query_parameters(request: Request) -> None:
    duplicates = sorted({name for name, _ in request.query_params.multi_items()
                         if len(request.query_params.getlist(name)) > 1})
    if duplicates:
        raise RequestValidationError([
            {"type": "duplicate_parameter", "loc": ("query", name if name in {"limit", "cursor"} else "parameters")}
            for name in duplicates
        ])


@router.get("/config", response_model=Envelope[FoundationConfig], operation_id="getV2Config",
            dependencies=[Depends(no_config_query)], responses={200: {"headers": REQUEST_ID_HEADER}})
def get_config(request: Request) -> Envelope[FoundationConfig]:
    settings = request.app.state.runtime_settings
    return Envelope(data=FoundationConfig(api_version="v2", schema_version="v2.t03",
                                         contract_stage="foundation", app_environment=settings.app_environment,
                                         query_role=settings.query_role, data_mode=settings.data_mode,
                                         model_mode=settings.model_mode, live_available=False,
                                         business_available=False, supported_scope=[],
                                         supported_province=None, entry_year=None),
                    meta=foundation_meta(request))


@router.get("/offerings", response_model=Envelope[Page[OfferingReference]],
            operation_id="listV2Offerings", dependencies=[Depends(unique_query_parameters)],
            responses={200: {"headers": REQUEST_ID_HEADER}})
def list_offerings(request: Request, query: Annotated[OfferingQuery, Query()]) -> Envelope[Page[OfferingReference]]:
    if query.cursor is not None:
        raise ApiError(422, "INVALID_CURSOR", details=[
            ErrorDetail(field_path="query.cursor", code="INVALID_CURSOR", message="本阶段未发行有效分页游标"),
        ])
    try:
        items = request.app.state.catalog_policy.read_foundation(request.app.state.catalog_candidates)
    except CatalogAccessError:
        raise ApiError(503, "SERVICE_UNAVAILABLE") from None
    return Envelope(data=Page[OfferingReference](items=items, page=PageInfo(limit=query.limit, next_cursor=None, has_more=False)),
                    meta=foundation_meta(request))
