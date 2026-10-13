"""Explicit isolated draft migrations: no application startup, seed or logging."""

import os

from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from services.api.app.plans.models import PlansBase


config = context.config
_HEADS = {
    "auth_alembic_version": "0006_audit_t10",
    "idempotency_alembic_version": "0001_idempotency_t49",
    "catalog_alembic_version": "0003_catalog_sources_t13",
    "storage_alembic_version": "0001_storage_t14",
    "imports_alembic_version": "0001_imports_t15",
    "evidence_alembic_version": "0001_evidence_t16",
    "facts_alembic_version": "0001_facts_t17",
    "reviews_alembic_version": "0001_reviews_t18",
    "releases_alembic_version": "0001_releases_t19",
    "profiles_alembic_version": "0001_profiles_t23",
    "assessments_alembic_version": "0001_assessments_t28",
}


def configure(*, connection=None, url=None):
    options = {"target_metadata": PlansBase.metadata, "version_table": "plans_alembic_version"}
    if connection is not None:
        if connection.dialect.name != "postgresql":
            raise ValueError("Plan migrations require PostgreSQL")
        for table, head in _HEADS.items():
            if connection.execute(text("SELECT version_num FROM " + table)).scalars().all() != [head]:
                raise ValueError("Plan migration prerequisites are unavailable")
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
        raise ValueError("Plan migration could not complete") from None
else:
    try:
        raw = os.environ.get("PLANS_DATABASE_URL")
        if not raw:
            raise ValueError()
        url = make_url(raw)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        if url.drivername != "postgresql+psycopg" or not url.database:
            raise ValueError()
    except Exception:
        raise ValueError("Plan migrations require an explicit PostgreSQL PLANS_DATABASE_URL") from None
    if context.is_offline_mode():
        configure(url=url)
    else:
        engine = None
        try:
            engine = create_engine(url, hide_parameters=True)
            with engine.begin() as connection:
                configure(connection=connection)
        except Exception:
            raise ValueError("Plan migration could not complete") from None
        finally:
            if engine is not None:
                engine.dispose()
