"""Only anonymous, bounded reads of the explicit public-catalog profile."""

import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BeforeValidator, field_validator

from ...evidence.schemas import _uuid
from ...public_catalog.schemas import (
    PublicCatalogError, PublicConfigData, PublicEvidenceData,
    PublicOfferingQuery, PublicOfferingsData,
)
from .errors import ApiError
from .router import ERROR_RESPONSES, REQUEST_ID_HEADER, foundation_meta, no_config_query
from .schemas import Envelope


QUERY_FIELDS = frozenset(PublicOfferingQuery.model_fields)
router = APIRouter(responses=ERROR_RESPONSES)


class PublicOfferingParameters(PublicOfferingQuery):
    """HTTP lexical parsing only; the reader receives the strict native DTO."""

    @field_validator("entry_year", "limit", mode="before")
    @classmethod
    def integer_parameter(cls, value):
        if type(value) is str:
            if len(value) > 12 or re.fullmatch(r"[+-]?[0-9]+", value) is None:
                raise ValueError("an integer query parameter is required")
            return int(value)
        return value


def query_parameters(request: Request) -> None:
    names = [name for name, _ in request.query_params.multi_items()]
    duplicates = {name for name in names if names.count(name) > 1}
    extras = set(names) - QUERY_FIELDS
    if duplicates or extras:
        raise RequestValidationError([
            {"type": "duplicate_parameter" if name in duplicates else "extra_forbidden",
             "loc": ("query", name if name in QUERY_FIELDS else "parameters")}
            for name in sorted(duplicates | extras)
        ])


def evidence_query_parameters(request: Request) -> None:
    names = [name for name, _ in request.query_params.multi_items()]
    if set(names) - {"release_id"} or len(names) != len(set(names)):
        raise RequestValidationError([{"type": "extra_forbidden", "loc": ("query", "parameters")}])


def reader(request: Request):
    current = request.app.state.public_catalog_reader
    if current is None:
        raise ApiError(503, "SERVICE_UNAVAILABLE")
    return current


def translate(error: PublicCatalogError) -> ApiError:
    return ApiError(error.status_code, error.code)


@router.get("/config", response_model=Envelope[PublicConfigData], operation_id="getV2PublicConfig",
            dependencies=[Depends(no_config_query)], responses={200: {"headers": REQUEST_ID_HEADER}})
def get_config(request: Request) -> Envelope[PublicConfigData]:
    current = request.app.state.public_catalog_reader
    if current is None:
        settings = request.app.state.runtime_settings
        data = PublicConfigData(api_version="v2", schema_version="v2.t20", contract_stage="public_catalog",
            app_environment=settings.app_environment, query_role=settings.query_role,
            data_mode=settings.data_mode, model_mode=settings.model_mode, live_available=False,
            business_available=False, allow_test_fixture_read=False, demo_banner=None,
            supported_scope=[], supported_province=None, entry_year=None)
    else:
        try:
            data = PublicConfigData.model_validate(current.config())
        except PublicCatalogError as error:
            raise translate(error) from None
    return Envelope(data=data, meta=foundation_meta(request))


@router.get("/offerings", response_model=Envelope[PublicOfferingsData], operation_id="listV2PublicOfferings",
            dependencies=[Depends(query_parameters)], responses={200: {"headers": REQUEST_ID_HEADER}})
def list_offerings(request: Request, query: Annotated[PublicOfferingParameters, Query()]) -> Envelope[PublicOfferingsData]:
    try:
        native = PublicOfferingQuery.model_validate(query.model_dump())
        data = PublicOfferingsData.model_validate(reader(request).list_offerings(native))
    except PublicCatalogError as error:
        raise translate(error) from None
    return Envelope(data=data, meta=foundation_meta(request))


@router.get("/evidence/{evidence_id}", response_model=Envelope[PublicEvidenceData], operation_id="getV2PublicEvidence",
            dependencies=[Depends(evidence_query_parameters)], responses={200: {"headers": REQUEST_ID_HEADER}})
def get_evidence(request: Request,
        evidence_id: Annotated[UUID, BeforeValidator(_uuid), Path()],
        release_id: Annotated[UUID, BeforeValidator(_uuid), Query()]) -> Envelope[PublicEvidenceData]:
    try:
        data = PublicEvidenceData.model_validate(reader(request).get_evidence(evidence_id, release_id))
    except PublicCatalogError as error:
        raise translate(error) from None
    return Envelope(data=data, meta=foundation_meta(request))
