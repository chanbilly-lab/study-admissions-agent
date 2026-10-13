from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field
from ..admissions_catalog.schemas import Identifier
from .reference_contract import ReferenceQuery, EmptyReferenceData, empty_reference, unique_parameters
from .v2.schemas import Envelope


class OutcomeQuery(ReferenceQuery):
    year: int = Field(alias="graduation_cohort", ge=1, le=9999)
    requested_level: Literal["institution", "college", "program", "discipline"]
    subject_ref: Identifier
    metric_kind: Literal["working", "further_study", "destination_confirmed", "salary"] | None = None


router = APIRouter(prefix="/reference", dependencies=[Depends(unique_parameters)])


@router.get("/outcomes", response_model=Envelope[EmptyReferenceData])
def outcomes(request: Request, query: Annotated[OutcomeQuery, Query()]):
    # No silent fallback from a requested program to school/discipline aggregates.
    return empty_reference(request, "outcomes", query)
