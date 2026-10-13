from typing import Literal
from pydantic import model_validator
from ..statistics.candidates import Candidate, Year, Text
from ..statistics.regions import RegionScope
from ..admissions_catalog.schemas import Identifier, _namespace


class AcademicUnit(Candidate):
    unit_kind: Literal["internal_college", "independent_institution"]
    institution_ref: Identifier
    campus_ref: Identifier | None = None
    parent_unit_ref: Identifier | None = None
    valid_from_year: Year
    valid_to_year: Year | None = None

    @model_validator(mode="after")
    def identity(self):
        for reference in (self.institution_ref, self.campus_ref, self.parent_unit_ref):
            if reference is not None:
                _namespace(reference, self.is_synthetic)
        if self.valid_to_year is not None and self.valid_to_year < self.valid_from_year:
            raise ValueError("Invalid year range")
        if self.unit_kind == "independent_institution" and self.parent_unit_ref is not None:
            raise ValueError("Independent institution is not an internal college")
        if self.parent_unit_ref == self.record_id:
            raise ValueError("Self parent forbidden")
        return self


class CodeCrosswalk(Candidate):
    scope: RegionScope
    admission_year: Year
    code_kind: Literal["national_major", "local_institution", "local_program", "local_group"]
    original_code: Text
    catalog_version: Text
    institution_ref: Identifier
    program_ref: Identifier | None = None
    campus_ref: Identifier | None = None
    group_members: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def namespace_and_members(self):
        for reference in (self.institution_ref, self.program_ref, self.campus_ref, *self.group_members):
            if reference is not None:
                _namespace(reference, self.is_synthetic)
        if len(self.group_members) > 100 or len(set(self.group_members)) != len(self.group_members):
            raise ValueError("Bounded distinct group members required")
        if self.code_kind != "local_group" and self.group_members:
            raise ValueError("Only groups carry members")
        return self

    def resolved_program(self) -> None:
        # Candidate target references are proposals, never a reviewed crosswalk.
        return None
