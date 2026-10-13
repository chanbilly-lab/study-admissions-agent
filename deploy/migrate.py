"""Explicit maintenance only. Importing or invoking help never creates tables."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROFILES = (
    "auth", "catalog", "storage", "idempotency", "imports", "evidence",
    "facts", "reviews", "releases", "profiles", "assessments", "plans",
    "execution", "changes", "revisions", "jobs", "rights", "rights_ledger",
)


def apply_profile(profile: str) -> None:
    # Import locked maintenance dependencies only after explicit --apply.
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url

    ledger = profile == "rights_ledger"
    secret_name = "ledger_migration_url" if ledger else "business_migration_url"
    with Path("/run/secrets", secret_name).open("rb") as handle:
        raw = handle.read(16 * 1024 + 1)
    if not raw or len(raw) > 16 * 1024:
        raise ValueError("invalid secret length")
    value = raw.decode("utf-8").strip()
    if not value or any(character.isspace() for character in value):
        raise ValueError("invalid secret encoding")
    url = make_url(value)
    expected = ("ledger_db", "study_ledger_owner", "study_ledger") if ledger else (
        "db", "study_owner", "study_business"
    )
    if (url.drivername not in {"postgresql", "postgresql+psycopg"}
            or (url.host, url.username, url.database) != expected
            or url.port not in {None, 5432}
            or not url.password or len(url.password) < 32 or url.query):
        raise ValueError("connection outside fixed maintenance target")
    url = url.set(drivername="postgresql+psycopg")
    config_path = Path(__file__).resolve().parents[1] / "services" / "api" / f"{profile}_alembic.ini"
    config = Config(str(config_path))
    # Suppress configuration-driven logging of SQL parameters/connection errors.
    config.attributes["configure_logger"] = False
    engine = create_engine(url, hide_parameters=True, echo=False,
                           connect_args={"connect_timeout": 5, "options": "-c statement_timeout=120000 -c lock_timeout=10000"})
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Single fixed Alembic profile; no seed, downgrade or automatic migration.")
    parser.add_argument("--profile", choices=PROFILES, required=True)
    parser.add_argument("--apply", action="store_true", help="Explicitly permit the selected migration on the isolated database.")
    args = parser.parse_args(argv)
    if not args.apply:
        print("MIGRATION_NOT_APPLIED: --apply is required.", file=sys.stderr)
        return 2
    try:
        apply_profile(args.profile)
    except Exception:
        # Do not echo URLs, driver diagnostics, source rows or credentials.
        print("MIGRATION_FAILED: inspect permissions, fixed target and migration compatibility privately.", file=sys.stderr)
        return 1
    print(f"MIGRATION_APPLIED: {args.profile}; business and public release remain disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
