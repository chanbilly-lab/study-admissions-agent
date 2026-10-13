"""Separate immutable v2 runtime policy from the retained M0 demo settings."""

from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Literal
from urllib.parse import parse_qsl, unquote, urlsplit

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class V2RuntimeSettings(BaseSettings):
    """No implicit dotenv, database connection, provider, or identity setup."""

    model_config = SettingsConfigDict(
        env_file=None, env_prefix="V2_", extra="forbid", populate_by_name=True,
        frozen=True, hide_input_in_errors=True, revalidate_instances="always",
    )

    app_environment: Literal["development", "test", "production"] = "development"
    data_mode: Literal["demo", "verified"] = "demo"
    model_mode: Literal["disabled", "mock", "live"] = "disabled"
    database_url: SecretStr | None = None
    legacy_demo_mode: bool | None = Field(default=None, validation_alias="DEMO_MODE")

    def __init__(self, **values):
        # BaseSettings merges aliases as source keys. Normalize the explicit
        # field so an explicit None also overrides a conflicting process alias.
        if "legacy_demo_mode" in values and "DEMO_MODE" not in values:
            values["DEMO_MODE"] = values.pop("legacy_demo_mode")
        super().__init__(**values)

    @property
    def query_role(self) -> Literal["demo_only", "published_readonly"]:
        return "demo_only" if self.data_mode == "demo" else "published_readonly"

    @model_validator(mode="after")
    def validate_runtime(self):
        if self.app_environment == "production" and self.data_mode != "verified":
            raise ValueError("production requires verified data mode")
        if self.data_mode == "verified" and self.model_mode == "mock":
            raise ValueError("mock is available only for demo data")
        if self.model_mode == "live":
            raise ValueError("v2 live provider is not implemented; no fallback is permitted")
        if self.legacy_demo_mode is not None and self.legacy_demo_mode != (self.data_mode == "demo"):
            raise ValueError("DEMO_MODE conflicts with the explicit v2 data mode")
        if self.database_url is not None:
            secret = self.database_url.get_secret_value()
            try:
                if any(character.isspace() or ord(character) < 32 for character in secret):
                    raise ValueError
                parsed = urlsplit(secret)
                if parsed.scheme not in {"postgresql", "postgresql+psycopg"} or parsed.fragment or not parsed.path.strip("/"):
                    raise ValueError
                identity_overrides = {"user", "username", "password", "dbname", "database", "service", "passfile"}
                if any(name.casefold() in identity_overrides for name, _ in parse_qsl(parsed.query, keep_blank_values=True)):
                    raise ValueError
                # Accessing port validates malformed authorities without connecting.
                _ = parsed.port
                username = unquote(parsed.username or "")
                password = unquote(parsed.password or "")
                database = unquote(parsed.path.lstrip("/"))
            except (ValueError, UnicodeError):
                raise ValueError("V2_DATABASE_URL must be a valid PostgreSQL URL") from None
            if self.data_mode == "verified" and (
                username.casefold() == "demo" or username.upper().startswith("DEMO_")
                or database.casefold() == "admissions_demo" or database.upper().startswith("DEMO_")
                or password == "demo_local_only"
            ):
                raise ValueError("verified mode rejects known DEMO database credentials")
        return self


def assert_m0_allowed(*, legacy_demo_mode: bool | None = None) -> None:
    """Read process policy on each boundary, even with explicit M0 settings."""
    runtime = V2RuntimeSettings()
    if runtime.app_environment == "production" or runtime.data_mode == "verified" or legacy_demo_mode is False:
        raise ValueError("M0 demo entry and fixture import are disabled in this runtime")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True,
                                      hide_input_in_errors=True)

    database_url: str = Field(
        default="postgresql+psycopg://demo:demo_local_only@127.0.0.1:5432/admissions_demo",
        validation_alias="DATABASE_URL",
    )
    sqlite_test_mode: bool = Field(default=False, validation_alias="M0_SQLITE_TEST_MODE")
    supported_province: str = Field(default="浙江", validation_alias=AliasChoices("SUPPORTED_PROVINCE", "M0_SUPPORTED_PROVINCE"))
    entry_year: int = Field(default=2027, ge=2026, le=2100, validation_alias=AliasChoices("ENTRY_YEAR", "M0_ENTRY_YEAR"))
    model_mode: Literal["mock", "live"] = Field(default="mock", validation_alias=AliasChoices("MODEL_MODE", "M0_MODEL_MODE"))
    assessment_date: date = Field(default_factory=lambda: datetime.now(ZoneInfo("Asia/Hong_Kong")).date(), validation_alias="M0_ASSESSMENT_DATE")
    cors_origin: str = Field(default="http://127.0.0.1:5173", validation_alias="M0_CORS_ORIGIN")
    legacy_demo_mode: bool | None = Field(default=None, validation_alias="DEMO_MODE")

    @model_validator(mode="after")
    def validate_database(self):
        assert_m0_allowed(legacy_demo_mode=self.legacy_demo_mode)
        if self.database_url.startswith("sqlite") and not self.sqlite_test_mode:
            raise ValueError("SQLite requires explicit M0_SQLITE_TEST_MODE=true; deployment uses PostgreSQL")
        if not self.database_url.startswith(("postgresql", "sqlite")):
            raise ValueError("M0 supports PostgreSQL and the explicit offline SQLite test stand-in")
        return self
