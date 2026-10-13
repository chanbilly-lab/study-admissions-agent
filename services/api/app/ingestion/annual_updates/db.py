"""Explicit local maintenance database policy, without environment or fallback."""

from sqlalchemy import text
from sqlalchemy.engine import Connection, make_url

ANNUAL_HEAD = "0001_annual_updates"
ANNUAL_TABLES = ("public.annual_source_cycles", "public.annual_source_update_requests")


def annual_database_url(raw):
    try:
        if type(raw) is not str or not 1 <= len(raw) <= 4096:
            raise ValueError()
        url = make_url(raw)
        if (url.drivername != "postgresql+psycopg" or url.host not in {"127.0.0.1", "localhost", "::1"}
                or url.database != "annual_source_updates" or not url.username or not url.password or url.query
                or url.username.upper().startswith("DEMO_") or url.password == "demo_local_only"):
            raise ValueError()
        return url
    except Exception:
        raise ValueError("EXPLICIT_ANNUAL_MAINTENANCE_DATABASE_REQUIRED") from None


def require_maintenance(connection):
    try:
        if (not isinstance(connection, Connection) or connection.closed
                or connection.dialect.name != "postgresql" or not connection.in_transaction()):
            raise ValueError()
        flags = connection.execute(text("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
                                        "FROM pg_roles WHERE rolname=current_user")).one()
        location = connection.execute(text("SELECT current_database(),current_schema()")).one()
        if any(flags) or tuple(location) != ("annual_source_updates", "public"):
            raise ValueError()
        for table in ANNUAL_TABLES:
            selected, inserted = connection.execute(text(
                "SELECT has_table_privilege(current_user,:table,'SELECT'), "
                "has_table_privilege(current_user,:table,'INSERT')"), {"table": table}).one()
            if selected is not True or inserted is not True:
                raise ValueError()
        if connection.execute(text("SELECT version_num FROM public.annual_updates_alembic_version")).scalars().all() != [ANNUAL_HEAD]:
            raise ValueError()
    except Exception:
        raise ValueError("ANNUAL_MAINTENANCE_UNAVAILABLE") from None
