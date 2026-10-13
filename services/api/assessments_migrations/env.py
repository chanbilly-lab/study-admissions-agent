"""Explicit independent assessment migrations; no fixture or logging mutation."""

import os

from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from services.api.app.assessments.models import AssessmentsBase


config = context.config
_HEADS = {
    "auth_alembic_version": "0006_audit_t10",
    "profiles_alembic_version": "0001_profiles_t23",
    "idempotency_alembic_version": "0001_idempotency_t49",
    "catalog_alembic_version": "0003_catalog_sources_t13",
    "storage_alembic_version": "0001_storage_t14",
    "imports_alembic_version": "0001_imports_t15",
    "evidence_alembic_version": "0001_evidence_t16",
    "facts_alembic_version": "0001_facts_t17",
    "reviews_alembic_version": "0001_reviews_t18",
    "releases_alembic_version": "0001_releases_t19",
}


def configure(*, connection=None, url=None):
    options = {"target_metadata": AssessmentsBase.metadata,
        "version_table": "assessments_alembic_version"}
    if connection is not None:
        if connection.dialect.name != "postgresql":
            raise ValueError("Assessment migrations require PostgreSQL")
        for table, head in _HEADS.items():
            if connection.execute(text(f"SELECT version_num FROM {table}")).scalars().all() != [head]:
                raise ValueError("Assessment migration prerequisites are unavailable")
        options["connection"] = connection
    else:
        options.update(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    context.configure(**options)
    with context.begin_transaction():
        context.run_migrations()


external = config.attributes.get("connection")
if external is not None:
    try:
        configure(connection=external)
    except Exception:
        raise ValueError("Assessment migration could not complete") from None
else:
    try:
        raw = os.environ.get("ASSESSMENTS_DATABASE_URL")
        if not raw:
            raise ValueError()
        url = make_url(raw)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        if url.drivername != "postgresql+psycopg" or not url.database:
            raise ValueError()
    except Exception:
        raise ValueError("Assessment migrations require an explicit PostgreSQL ASSESSMENTS_DATABASE_URL") from None
    if context.is_offline_mode():
        configure(url=url)
    else:
        engine = None
        try:
            engine = create_engine(url, hide_parameters=True)
            with engine.begin() as connection:
                configure(connection=connection)
        except Exception:
            raise ValueError("Assessment migration could not complete") from None
        finally:
            if engine is not None:
                engine.dispose()
