"""Frozen product policy; no environment files, network, persistence or secrets."""

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from ..auth.schemas import AuthModel


POLICY_VERSION = "T08_product_v1"
DRAFT_NOTICE_TEXT = (
    "开发告知草案，尚非正式上线隐私政策。核心用途仅为本人确认的本科咨询、确定性资格和准备计划。"
    "本版未成年人及未知年龄仅可公开浏览，不提供监护核验或私有咨询；18岁及以上需本人明确声明及用途确认，"
    "声明不等于年龄已核验。不收完整出生日期或身份证、护照影像。"
    "外部模型、营销及第三方共享关闭。撤回立即停止后续相应用途处理，隐私设置和退出仍可使用。"
    "PDF、UTF-8 CSV、JSON单文件上限10MiB；私有资料最长24个月，删除受理后30天内清理在线副本，"
    "脱敏日志30天，审计及授权记录最长24个月，备份35天；更短必要期限优先。"
    "法定保留例外、影响评估材料及各地区适用性须单独审查，不能将所有记录归为同一期限。"
    "清理、删除传播及备份恢复重施删除尚未实现。正式运营主体、权利渠道及适用性复核未完成，真实处理关闭。"
)


class PrivacySettings(AuthModel):
    """Only an explicit synthetic test configuration enables T08's full flow.

    Real controller/notice/age-assurance approval remains a release gate. There
    is no boolean that turns placeholder declarations into production readiness.
    """

    fixture_mode: bool = Field(default=False, strict=True)
    notice_id: UUID | None = None
    controller_reference: str | None = Field(default=None, min_length=1, max_length=255, strict=True)
    age_assurance_method: Literal["unconfigured", "adult_self_declaration"] = "unconfigured"
    declaration_validity_seconds: int | None = Field(default=None, ge=1, le=31536000, strict=True)
    policy_version: str = Field(default=POLICY_VERSION, min_length=1, max_length=100, strict=True)

    @model_validator(mode="after")
    def explicit_fixture(self):
        values = (self.notice_id, self.controller_reference, self.declaration_validity_seconds)
        if self.fixture_mode:
            if not all(values) or self.age_assurance_method != "adult_self_declaration":
                raise ValueError("test privacy configuration requires explicit notice and controller")
        elif any(values) or self.age_assurance_method != "unconfigured":
            raise ValueError("real privacy processing is not activated by this configuration")
        return self
