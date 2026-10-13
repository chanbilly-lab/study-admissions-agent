"""Replaceable narrative boundary. Live is intentionally unavailable in M0."""
from typing import Protocol

from .schemas import Eligibility, Profile


class LiveProviderUnavailable(RuntimeError):
    pass


class NarrativeProvider(Protocol):
    def draft_narrative(self, profile: Profile, results: list[Eligibility]) -> str: ...


class MockProvider:
    def draft_narrative(self, profile, results):
        counts = {status: sum(item.status == status for item in results)
                  for status in ("eligible", "ineligible", "conditional", "unknown")}
        return (f"DEMO 演示模式：已确认合成画像的 {len(results)} 个项目已进行确定性检查。"
                f"满足 {counts['eligible']}，不满足 {counts['ineligible']}，带条件 {counts['conditional']}，"
                f"未知 {counts['unknown']}。这是待用户审核的计划草案，资格满足不代表录取。")


class LiveProvider:
    def draft_narrative(self, profile, results):
        raise LiveProviderUnavailable("M0 live 模型接口仅预留，当前不可用；没有生成草案，也不会回退至 mock")


def provider_for(mode: str) -> NarrativeProvider:
    if mode == "mock":
        return MockProvider()
    if mode == "live":
        return LiveProvider()
    raise ValueError("Unknown provider mode")
