"""Published directory choices; disabled factories perform zero catalog reads."""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import field_validator

from .v2.errors import ApiError
from .v2.router import foundation_meta
from .v2.schemas import Envelope
from ..public_catalog.schemas import PublicCatalogError
from ..reference_directory.reader import PublishedDirectoryReader
from ..reference_directory.schemas import (DirectoryData, DirectoryQuery, ProgramDirectoryQuery, disabled_data)


class InstitutionParameters(DirectoryQuery):
    @field_validator("limit", mode="before")
    @classmethod
    def decimal_limit(cls, value):
        if type(value) is str:
            if re.fullmatch(r"[1-9][0-9]{0,2}", value) is None:
                raise ValueError("A decimal integer limit is required")
            return int(value)
        return value


class ProgramParameters(ProgramDirectoryQuery):
    _limit = field_validator("limit", mode="before")(InstitutionParameters.decimal_limit.__func__)


def exact_query(fields):
    def check(request: Request):
        names = [name for name, _ in request.query_params.multi_items()]
        duplicates = {name for name in names if names.count(name) > 1}
        extras = set(names) - fields
        if duplicates or extras:
            raise RequestValidationError([{"type": "duplicate_parameter" if name in duplicates else "extra_forbidden",
                "loc": ("query", name if name in fields else "parameters")} for name in sorted(duplicates | extras)])
    return check


router = APIRouter(prefix="/reference")


def install_directory(app, directory_reader):
    if directory_reader is not None:
        if type(directory_reader) is not PublishedDirectoryReader:
            raise ApiError(503, "SERVICE_UNAVAILABLE")
        try:
            directory_reader.validate_runtime(app.state.runtime_settings)
        except Exception:
            raise ApiError(503, "SERVICE_UNAVAILABLE") from None
    app.state.directory_reader = directory_reader

    def guard():
        if app.state.directory_reader is not directory_reader or app.state.get_directory_reader is not guard:
            raise ApiError(503, "SERVICE_UNAVAILABLE")
        if directory_reader is not None:
            try:
                directory_reader.validate_runtime(app.state.runtime_settings)
            except Exception:
                raise ApiError(503, "SERVICE_UNAVAILABLE") from None
        return directory_reader

    app.state.get_directory_reader = guard
    app.include_router(router)
    return guard


def result(request, resource, query):
    try:
        getter = request.app.state.get_directory_reader
        reader = getter()
        if reader is None:
            if query.cursor is not None:
                raise ApiError(422, "VALIDATION_ERROR")
            data = disabled_data(resource, query)
        else:
            data = reader.search(resource, query)
        if getter() is not reader:
            raise ApiError(503, "SERVICE_UNAVAILABLE")
        return Envelope(data=DirectoryData.model_validate(data), meta=foundation_meta(request))
    except PublicCatalogError as error:
        raise ApiError(error.status_code, error.code) from None


@router.get("/institutions", response_model=Envelope[DirectoryData],
            dependencies=[Depends(exact_query(frozenset(InstitutionParameters.model_fields)))])
def institutions(request: Request, query: Annotated[InstitutionParameters, Query()]):
    return result(request, "institutions", DirectoryQuery.model_validate(query.model_dump()))


@router.get("/programs", response_model=Envelope[DirectoryData],
            dependencies=[Depends(exact_query(frozenset(ProgramParameters.model_fields)))])
def programs(request: Request, query: Annotated[ProgramParameters, Query()]):
    return result(request, "programs", ProgramDirectoryQuery.model_validate(query.model_dump()))
