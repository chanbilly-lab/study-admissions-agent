"""Bounded local reviewed cutoffs; every query rechecks the current database state."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from .reference_contract import EmptyReferenceData, ReferenceQuery, empty_reference, unique_parameters
from .v2.errors import ApiError
from .v2.router import foundation_meta
from .v2.schemas import Envelope
from ..statistics.reference_cutoffs.schemas import LocalCutoffData, LocalStatisticalQuery
from ..statistics.reference_cutoffs.service import query_cutoffs, require_reader

router = APIRouter(prefix="/reference", dependencies=[Depends(unique_parameters)])


@router.get("/coverage", response_model=Envelope[EmptyReferenceData])
def coverage(request: Request, query: Annotated[ReferenceQuery, Query()]):
    # Three local facts do not establish a national denominator or a public release.
    return empty_reference(request, "coverage", query)


@router.get("/province-cutoffs", response_model=Envelope[LocalCutoffData])
def cutoffs(request: Request, query: Annotated[LocalStatisticalQuery, Query()]):
    try:
        engine = request.app.state.reference_engine
        with engine.connect() as connection, connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            require_reader(connection)
            with Session(bind=connection) as session:
                data = query_cutoffs(session, query)
        return Envelope(data=data, meta=foundation_meta(request))
    except Exception:
        # Never return candidates, stale caches, DEMO, passwords, paths, or DB errors.
        raise ApiError(503, "SERVICE_UNAVAILABLE") from None
