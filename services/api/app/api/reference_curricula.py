from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field, field_validator
from .reference_contract import ReferenceQuery, EmptyReferenceData, empty_reference, unique_parameters
from .v2.schemas import Envelope


class CurriculumQuery(ReferenceQuery):
    year: int = Field(alias="entry_cohort", ge=1, le=9999)
    teaching_year: int | None = Field(default=None, ge=1, le=9999)

    @field_validator("teaching_year", mode="before")
    @classmethod
    def exact_teaching_year(cls, value):
        return ReferenceQuery.decimal_integer(value) if value is not None else None


router = APIRouter(prefix="/reference", dependencies=[Depends(unique_parameters)])


@router.get("/programs/{program_id}/curricula", response_model=Envelope[EmptyReferenceData])
def curricula(program_id: UUID, request: Request, query: Annotated[CurriculumQuery, Query()]):
    return empty_reference(request, "curricula", query, extra_filters={"program_id": str(program_id)})
