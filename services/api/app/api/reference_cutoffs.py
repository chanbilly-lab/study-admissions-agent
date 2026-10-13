from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request
from .reference_contract import ReferenceQuery, StatisticalQuery, EmptyReferenceData, empty_reference, unique_parameters
from .v2.schemas import Envelope

router = APIRouter(prefix="/reference", dependencies=[Depends(unique_parameters)])


@router.get("/coverage", response_model=Envelope[EmptyReferenceData])
def coverage(request: Request, query: Annotated[ReferenceQuery, Query()]):
    return empty_reference(request, "coverage", query)


@router.get("/province-cutoffs", response_model=Envelope[EmptyReferenceData])
def cutoffs(request: Request, query: Annotated[StatisticalQuery, Query()]):
    return empty_reference(request, "province_cutoffs", query)
