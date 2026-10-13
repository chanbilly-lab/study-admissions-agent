"""Internal source declarations; syntax does not establish authority or rights."""

from calendar import monthrange
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
import re
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from ...admissions_catalog.schemas import (
    CatalogModel, Identifier, PositiveVersion, _identifier, _namespace,
)


Permission = Literal["pending", "denied", "granted"]


def validate_source_url(value: str) -> str:
    """Keep a syntactically valid metadata URL; never resolve or fetch its host."""
    try:
        if (type(value) is not str or not 1 <= len(value) <= 2048
            or any(character.isspace() or ord(character) < 32 or 127 <= ord(character) <= 159
                   for character in value)
            or "\\" in value or "#" in value):
            raise ValueError
        value.encode("utf-8")
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname
            or parsed.username is not None or parsed.password is not None or "%" in parsed.netloc):
            raise ValueError
        port = parsed.port
        if parsed.netloc.endswith(":") or (port is not None and not 1 <= port <= 65535):
            raise ValueError
        try:
            ip_address(parsed.hostname)
        except ValueError:
            host = parsed.hostname.encode("idna").decode("ascii")
            if len(host) > 253 or any(re.fullmatch(
                r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) is None
                for label in host.split(".")):
                raise ValueError
        if re.search(r"%(?![0-9A-Fa-f]{2})", parsed.path + parsed.query):
            raise ValueError
    except (ValueError, UnicodeError):
        raise ValueError("a valid HTTP(S) metadata URL without credentials or fragment is required") from None
    return value


def _text(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValueError("valid nonblank text is required") from None
    if not value.strip() or "\x00" in value:
        raise ValueError("valid nonblank text is required")
    return value


def _utc_time(value):
    if (type(value) is not datetime or value.tzinfo is None
        or value.utcoffset() is None or value.fold != 0):
        raise ValueError("a native aware UTC timestamp is required")
    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        raise ValueError("timestamp is outside the supported UTC calendar") from None


class SourceDefinition(CatalogModel):
    publisher: str = Field(strict=True, min_length=1, max_length=200)
    entry_url: str = Field(strict=True, min_length=1, max_length=2048)
    purpose: Literal["admissions_reference"]
    data_type: Literal[
        "entry_requirements", "application_dates", "regional_cutoffs", "admission_observations",
        "curriculum", "outcomes", "institution_directory",
    ]
    scope_note: str = Field(strict=True, min_length=1, max_length=1000)
    authority_claim: Literal["unclassified", "claimed_official", "not_official"]
    manual_import_permission: Permission
    publication_permission: Permission
    automated_fetch_permission: Permission
    license_basis: str | None = Field(strict=True, min_length=1, max_length=2000)
    permission_record_reference: Identifier | None
    recheck_days: int = Field(strict=True, ge=1, le=730)
    manual_import_enabled: bool = Field(strict=True)

    @field_validator("publisher", "scope_note", "license_basis")
    @classmethod
    def valid_text(cls, value):
        return _text(value) if value is not None else None

    @field_validator("publisher")
    @classmethod
    def publisher_label(cls, value):
        if any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value):
            raise ValueError("publisher must be a display label without controls")
        return value

    @field_validator("entry_url")
    @classmethod
    def metadata_url(cls, value):
        return validate_source_url(value)

    @field_validator("permission_record_reference")
    @classmethod
    def exact_permission_reference(cls, value):
        return _identifier(value) if value is not None else None

    @model_validator(mode="after")
    def permissions_have_a_record(self):
        recorded = any(value != "pending" for value in (
            self.manual_import_permission, self.publication_permission, self.automated_fetch_permission))
        if recorded != (self.license_basis is not None and self.permission_record_reference is not None):
            raise ValueError("recorded permissions require both a basis and record reference")
        if not recorded and (self.license_basis is not None or self.permission_record_reference is not None):
            raise ValueError("pending permissions require null basis and reference")
        if self.manual_import_enabled and self.manual_import_permission != "granted":
            raise ValueError("manual import can only be requested with a granted manual permission")
        return self

    def validate_namespace(self, is_synthetic: bool) -> None:
        current = SourceDefinition.model_validate(self)
        if type(is_synthetic) is not bool:
            raise ValueError("a strict synthetic marker is required")
        _namespace(current.publisher, is_synthetic)
        if current.permission_record_reference is not None:
            _namespace(current.permission_record_reference, is_synthetic)


class SourceCreateInput(CatalogModel):
    id: UUID
    dataset_id: UUID
    reference_key: Identifier
    is_synthetic: bool = Field(strict=True)
    definition: SourceDefinition

    @field_validator("reference_key")
    @classmethod
    def exact_reference(cls, value):
        return _identifier(value)

    @model_validator(mode="after")
    def source_namespace(self):
        _namespace(self.reference_key, self.is_synthetic)
        self.definition.validate_namespace(self.is_synthetic)
        return self


class SourceRevisionInput(CatalogModel):
    source_id: UUID
    definition: SourceDefinition


class SourceVersionData(SourceDefinition):
    id: UUID
    dataset_id: UUID
    source_id: UUID
    version: PositiveVersion
    is_synthetic: bool = Field(strict=True)
    responsible_user_id: UUID
    created_at: datetime = Field(strict=True)
    permission_reviewed_at: datetime | None = Field(strict=True)
    recheck_due_at: datetime = Field(strict=True)
    auto_fetch_enabled: Literal[False]

    @field_validator("auto_fetch_enabled", mode="before")
    @classmethod
    def fetch_is_disabled(cls, value):
        if value is not False:
            raise ValueError("automatic fetching is disabled")
        return value

    @field_validator("created_at", "permission_reviewed_at", "recheck_due_at", mode="before")
    @classmethod
    def native_utc_timestamp(cls, value):
        return _utc_time(value) if value is not None else None

    @model_validator(mode="after")
    def server_declaration_fields(self):
        _namespace(self.publisher, self.is_synthetic)
        if self.permission_record_reference is not None:
            _namespace(self.permission_record_reference, self.is_synthetic)
        recorded = any(value != "pending" for value in (
            self.manual_import_permission, self.publication_permission, self.automated_fetch_permission))
        if recorded != (self.permission_reviewed_at is not None):
            raise ValueError("only recorded permissions contain a server declaration timestamp")
        if self.permission_reviewed_at is not None and self.permission_reviewed_at != self.created_at:
            raise ValueError("permission declaration must be the server version creation timestamp")
        try:
            year = self.created_at.year + 2
            calendar_limit = self.created_at.replace(year=year,
                day=min(self.created_at.day, monthrange(year, self.created_at.month)[1]))
            expected_due = min(self.created_at + timedelta(days=self.recheck_days), calendar_limit)
        except (OverflowError, ValueError):
            raise ValueError("recheck date is outside the supported calendar") from None
        if self.recheck_due_at != expected_due:
            raise ValueError("recheck date must follow the explicit interval from version creation")
        return self


class SourcePolicy(CatalogModel):
    enabled: bool = Field(default=False, strict=True)
    real_sources_ready: bool = Field(default=False, strict=True)
    responsible_user_ids: tuple[UUID, ...] = ()

    @field_validator("responsible_user_ids", mode="before")
    @classmethod
    def explicit_responsible_ids(cls, value):
        if type(value) is not tuple:
            raise ValueError("responsible users must be an explicit tuple of UUIDs")
        return value

    @model_validator(mode="after")
    def responsibility_configuration(self):
        if len(set(self.responsible_user_ids)) != len(self.responsible_user_ids):
            raise ValueError("responsible user identifiers must be unique")
        if self.real_sources_ready and not self.responsible_user_ids:
            raise ValueError("real source readiness requires an explicit responsible user")
        return self
