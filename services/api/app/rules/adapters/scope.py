"""Declared applicant scope and finite province comparisons, without guessing."""

from typing import Literal

from pydantic import Field, field_validator, model_validator

from ...admissions_catalog.schemas import CatalogModel, Identifier, ScopeKey
from .schemas import AdapterInputError, ScopeRequest, TargetReference

ProvinceCode = Literal["Beijing", "Tianjin", "Hebei", "Shanxi", "InnerMongolia", "Liaoning",
    "Jilin", "Heilongjiang", "Shanghai", "Jiangsu", "Zhejiang", "Anhui", "Fujian", "Jiangxi",
    "Shandong", "Henan", "Hubei", "Hunan", "Guangdong", "Guangxi", "Hainan", "Chongqing",
    "Sichuan", "Guizhou", "Yunnan", "Tibet", "Shaanxi", "Gansu", "Qinghai", "Ningxia", "Xinjiang"]
PROVINCES = ProvinceCode.__args__
_ALIASES = ("beijing", "tianjin", "hebei", "shanxi", "innermongolia", "liaoning", "jilin",
    "heilongjiang", "shanghai", "jiangsu", "zhejiang", "anhui", "fujian", "jiangxi", "shandong",
    "henan", "hubei", "hunan", "guangdong", "guangxi", "hainan", "chongqing", "sichuan",
    "guizhou", "yunnan", "tibet", "shaanxi", "gansu", "qinghai", "ningxia", "xinjiang")
_REGISTRY = tuple((canonical, (alias, "inner_mongolia") if canonical == "InnerMongolia" else (alias,))
                  for canonical, alias in zip(PROVINCES, _ALIASES, strict=True))
EXTRA_SCOPE_FIELDS = ("intake", "application_cycle", "channel", "exam_system", "subject_scope", "batch_group")
CONFIG_NOTE = "Input recognition only; no province or year is declared to have reviewed real rules."


class ProvinceDefinition(CatalogModel):
    canonical: ProvinceCode
    aliases: tuple[Identifier, ...] = Field(min_length=1, max_length=2)

    @field_validator("aliases", mode="before")
    @classmethod
    def exact_list(cls, value):
        if type(value) not in (list, tuple) or any(type(item) is not str for item in value):
            raise ValueError("explicit fixed aliases are required")
        return value


class ScopeConfiguration(CatalogModel):
    schema_version: Literal["T26_v1"]
    provinces: tuple[ProvinceDefinition, ...] = Field(min_length=31, max_length=31)
    uk_entry_years: tuple[Literal[2027], ...] = Field(min_length=1, max_length=1)
    real_rules_ready: Literal[False]
    note: Literal[CONFIG_NOTE]

    @field_validator("uk_entry_years", mode="before")
    @classmethod
    def exact_year(cls, value):
        if type(value) not in (list, tuple) or any(type(item) is not int for item in value):
            raise ValueError("explicit integer years are required")
        return value

    @field_validator("real_rules_ready", mode="before")
    @classmethod
    def real_closed(cls, value):
        if value is not False:
            raise ValueError("real rules are unavailable")
        return value

    @model_validator(mode="after")
    def registered_aliases_only(self):
        supplied = tuple((item.canonical, item.aliases) for item in self.provinces)
        if supplied != _REGISTRY:
            raise ValueError("the complete case-exact province registry is required")
        return self


DEFAULT_CONFIGURATION = ScopeConfiguration(schema_version="T26_v1",
    provinces=tuple(ProvinceDefinition(canonical=canonical, aliases=aliases) for canonical, aliases in _REGISTRY),
    uk_entry_years=(2027,), real_rules_ready=False, note=CONFIG_NOTE)


def parse_scope_configuration(value) -> ScopeConfiguration:
    """Validate caller-loaded native config; never read a file or environment."""
    try:
        return ScopeConfiguration.model_validate(value)
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise AdapterInputError() from None


def canonical_province(value, *, configuration=DEFAULT_CONFIGURATION) -> str | None:
    current = parse_scope_configuration(configuration)
    if type(value) is not str:
        return None
    for entry in current.provinces:
        if value == entry.canonical or value in entry.aliases:
            return entry.canonical
    return None


def scope_request_from_profile(profile, *, target: TargetReference, stage, assessment_at,
        intake: ScopeKey | None, application_cycle: ScopeKey | None, channel: ScopeKey | None,
        exam_system: ScopeKey | None, subject_scope: ScopeKey | None, batch_group: ScopeKey | None) -> ScopeRequest:
    """Revalidate the whole T23 snapshot and project only declared scope."""
    try:
        from ...profiles.schemas import ProfileSnapshot

        current = ProfileSnapshot.model_validate(profile)
        return ScopeRequest(entry_year=current.entry_year, study_level=current.study_level,
            residence_region=current.residence_region, course_system=current.course_system,
            applicant_category=current.applicant_category, exam_province=current.exam_province,
            pathway=current.pathway, target=target, stage=stage, assessment_at=assessment_at,
            intake=intake, application_cycle=application_cycle, channel=channel,
            exam_system=exam_system, subject_scope=subject_scope, batch_group=batch_group)
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise AdapterInputError() from None
