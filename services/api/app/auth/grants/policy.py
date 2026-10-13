"""Actual synthetic scope text, independent of core-purpose confirmation."""

from hashlib import sha256

from .schemas import SharingPolicyData, SharingScopeData

POLICY_VERSION = "T09_sharing_v1"
MAX_DURATION_SECONDS = 2592000
POLICY_TEXT = (
    "合成测试共享告知，真实共享关闭。核心咨询确认不包含第三方共享。"
    "每次须本人独立确认指定对象、指定预登记受权人、status/version元数据字段、read/list动作及明确期限，"
    "受权人须以自己的有效成年声明和会话独立接受。本合成策略期限最多30天。"
    "没有通配、全会话、继承、转授权或监护关系默认权限；不授领域内容、整文件下载、写入、导出、执行或代确认。"
    "对象版本、用途、年龄声明或策略改变会使旧许可失效，重新确认不复活旧授权。可撤回，撤回后服务端读取、"
    "缓存与延迟只读操作重新校验；不能收回已送达副本。此非正式生产隐私告知，不解除运营主体和法律复核门槛。"
)
POLICY_HASH = sha256(POLICY_TEXT.encode("utf-8")).hexdigest()


def sharing_policy(available=False):
    return SharingPolicyData(policy_version=POLICY_VERSION, text=POLICY_TEXT, text_sha256=POLICY_HASH,
        is_synthetic=True, sharing_available=available,
        readiness_reason="synthetic_test_ready" if available else "disabled", max_duration_seconds=MAX_DURATION_SECONDS,
        scope_matrix=[SharingScopeData(resource_type=kind, fields=["status", "version"], actions=["read", "list"])
            for kind in ("profile", "plan", "attachment", "export", "job")],
        guardian_verification_available=False, private_business_available=False)
