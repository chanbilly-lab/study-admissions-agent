from typing import Annotated
from fastapi import APIRouter, Depends, Query, Request
from ..admissions_catalog.schemas import Identifier
from ..statistics.candidates import Text
from .reference_contract import StatisticalQuery, EmptyReferenceData, empty_reference, unique_parameters
from .v2.schemas import Envelope


class AdmissionQuery(StatisticalQuery):
    institution_code: Text | None = None
    group_code: Text | None = None
    program_code: Text | None = None


class ComparisonQuery(AdmissionQuery):
    left_record_id: Identifier
    right_record_id: Identifier


router = APIRouter(prefix="/reference", dependencies=[Depends(unique_parameters)])


@router.get("/score-distributions", response_model=Envelope[EmptyReferenceData])
def distributions(request: Request, query: Annotated[StatisticalQuery, Query()]):
    return empty_reference(request, "score_distributions", query)


@router.get("/admissions", response_model=Envelope[EmptyReferenceData])
def admissions(request: Request, query: Annotated[AdmissionQuery, Query()]):
    return empty_reference(request, "admissions", query)


@router.get("/comparisons", response_model=Envelope[EmptyReferenceData])
def comparisons(request: Request, query: Annotated[ComparisonQuery, Query()]):
    # No records can be resolved from the empty dataset; do not compare caller payloads.
    return empty_reference(request, "comparisons", query)
