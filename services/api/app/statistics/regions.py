"""Stable internal region keys reused from T50A, never official code mappings."""

from types import MappingProxyType
from typing import Literal

from pydantic import ConfigDict, field_validator, model_validator

from ..admissions_catalog.schemas import CatalogModel, Identifier, _identifier

MAINLAND_NAMES = (
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
    "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
    "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
    "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆",
)
REGION_NAMES = MappingProxyType({**{f"cn_region_{index:02d}": name for index, name in enumerate(MAINLAND_NAMES, 1)},
                                "hk": "香港", "mo": "澳门", "tw": "台湾"})
LOCAL_PATHWAYS = MappingProxyType({"hk": "hk_local_admissions", "mo": "mo_local_admissions", "tw": "tw_local_admissions"})
Pathway = Literal["ordinary_gaokao", "institution_reference", "hk_local_admissions", "mo_local_admissions", "tw_local_admissions"]


class StrictCatalogModel(CatalogModel):
    model_config = ConfigDict(strict=True)


class RegionScope(StrictCatalogModel):
    region_key: Identifier
    pathway: Pathway
    authority_key: Identifier | None = None
    subscope: Literal["xinjiang_bingtuan"] | None = None

    @field_validator("authority_key")
    @classmethod
    def authority_identifier(cls, value):
        return _identifier(value) if value is not None else None

    @model_validator(mode="after")
    def applicable_scope(self):
        if self.region_key not in REGION_NAMES:
            raise ValueError("Unknown internal region key")
        allowed = {"institution_reference", LOCAL_PATHWAYS.get(self.region_key, "ordinary_gaokao")}
        if self.pathway not in allowed:
            raise ValueError("Admissions pathway is not applicable to this region scope")
        if self.subscope is not None and self.region_key != "cn_region_31":
            raise ValueError("Bingtuan is a Xinjiang subscope, never another province")
        return self

    def province_key(self) -> str:
        # Authority/subscope metadata never expands the province-level denominator.
        return RegionScope.model_validate(self.model_dump()).region_key


def region_definition(region_key: str) -> dict:
    if type(region_key) is not str or region_key not in REGION_NAMES:
        raise ValueError("Unknown internal region key")
    mainland = region_key not in LOCAL_PATHWAYS
    return {"region_key": region_key, "region_name": REGION_NAMES[region_key], "is_official_code": False,
            "region_kind": {"hk": "hong_kong", "mo": "macau", "tw": "taiwan"}.get(region_key, "mainland_province"),
            "ordinary_gaokao_applicability": "applicable" if mainland else "not_applicable",
            "pathways": ("institution_reference", LOCAL_PATHWAYS.get(region_key, "ordinary_gaokao"))}
