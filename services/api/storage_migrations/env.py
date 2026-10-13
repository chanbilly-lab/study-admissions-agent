"""Explicit PostgreSQL storage migrations; no settings or logging side effects."""

import os

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from services.api.app.storage.models import StorageBase


config = context.config


def configure(*, connection=None, url=None):
    options = {"target_metadata": StorageBase.metadata, "version_table": "storage_alembic_version"}
    if connection is not None:
        options["connection"] = connection
    else:
        options.update(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    context.configure(**options)
    with context.begin_transaction():
        context.run_migrations()


external = config.attributes.get("connection")
if external is not None:
    if external.dialect.name != "postgresql":
        raise ValueError("Storage migrations require PostgreSQL")
    configure(connection=external)
else:
    try:
        raw = os.environ.get("STORAGE_DATABASE_URL")
        if not raw:
            raise ValueError()
        url = make_url(raw)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        if url.drivername != "postgresql+psycopg" or not url.database:
            raise ValueError()
    except Exception:
        raise ValueError("Storage migrations require an explicit PostgreSQL STORAGE_DATABASE_URL") from None
    if context.is_offline_mode():
        configure(url=url)
    else:
        engine = None
        try:
            engine = create_engine(url, hide_parameters=True)
            with engine.connect() as connection:
                configure(connection=connection)
        except Exception:
            raise ValueError("Storage migration could not complete") from None
        finally:
            if engine is not None:
                engine.dispose()
