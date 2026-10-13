"""Public development policy; importing this module loads no database or JOSE."""

from hashlib import sha256

from .config import DRAFT_NOTICE_TEXT, PrivacySettings
from .errors import PrivacyError
from .schemas import PrivacyAgePolicy, PrivacyNoticeData, PrivacyRetentionPolicy


def hash_text(text):
    try:
        return sha256(text.encode("utf-8")).hexdigest()
    except (AttributeError, UnicodeError):
        raise PrivacyError(503) from None


def notice_data(settings: PrivacySettings, *, notice=None) -> PrivacyNoticeData:
    settings = PrivacySettings.model_validate(settings)
    ready = notice is not None
    text = notice.text if ready else DRAFT_NOTICE_TEXT
    return PrivacyNoticeData(policy_version=settings.policy_version,
        notice_id=notice.id if ready else None, notice_version=notice.version if ready else None,
        notice_hash=hash_text(text), text=text, is_synthetic=True, readiness=ready,
        readiness_reason="test_fixture_ready" if ready else "processing_disabled", purposes=["core_consultation"],
        age_policy=PrivacyAgePolicy(under_14="public_only", age_14_17="private_disabled",
            age_18_plus="self_declaration_and_confirmation", unknown="public_only",
            guardian_verification_available=False, declaration_is_verification=False),
        retention_policy=PrivacyRetentionPolicy(file_types=["pdf", "utf8_csv", "json"], max_file_bytes=10485760,
            private_data_max_months=24, online_deletion_max_days=30, sanitized_logs_max_days=30,
            audit_authorization_max_months=24, backup_max_days=35, cleanup_implemented=False))
