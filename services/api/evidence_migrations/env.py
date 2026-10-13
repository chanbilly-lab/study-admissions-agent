"""Explicit isolated evidence migrations; no dotenv, seed or logging changes."""

import os

from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from services.api.app.evidence.models import EvidenceBase


config = context.config
_HEADS = {"auth_alembic_version": "0006_audit_t10", "catalog_alembic_version": "0003_catalog_sources_t13",
          "storage_alembic_version": "0001_storage_t14"}


def configure(*, connection=None, url=None):
    options = {"target_metadata": EvidenceBase.metadata, "version_table": "evidence_alembic_version"}
    if connection is not None:
        if connection.dialect.name != "postgresql":
            raise ValueError("Evidence migrations require PostgreSQL")
        for table, head in _HEADS.items():
            if connection.execute(text(f"SELECT version_num FROM {table}")).scalars().all() != [head]:
                raise ValueError("Evidence migration prerequisites are unavailable")
        options["connection"] = connection
    else:
        options.update(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    context.configure(**options)
    with context.begin_transaction():
        context.run_migrations()


external = config.attributes.get("connection")
if external is not None:
    configure(connection=external)
else:
    try:
        raw = os.environ.get("EVIDENCE_DATABASE_URL")
        if not raw:
            raise ValueError()
        url = make_url(raw)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        if url.drivername != "postgresql+psycopg" or not url.database:
            raise ValueError()
    except Exception:
        raise ValueError("Evidence migrations require an explicit PostgreSQL EVIDENCE_DATABASE_URL") from None
    if context.is_offline_mode():
        configure(url=url)
    else:
        engine = None
        try:
            engine = create_engine(url, hide_parameters=True)
            with engine.connect() as connection:
                configure(connection=connection)
        except Exception:
            raise ValueError("Evidence migration could not complete") from None
        finally:
            if engine is not None:
                engine.dispose()
