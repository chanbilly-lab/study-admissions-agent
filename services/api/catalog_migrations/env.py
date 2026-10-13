"""Explicit catalog migrations; no demo/auth settings or logging configuration."""

import os

from alembic import context
from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import make_url

from services.api.app.admissions_catalog.models import CatalogBase
from services.api.app.admissions_catalog.date_models import DatesBase
from services.api.app.admin.sources.models import SourceBase


config = context.config
target_metadata = MetaData()
for metadata in (CatalogBase.metadata, DatesBase.metadata, SourceBase.metadata):
    for table in metadata.tables.values():
        table.to_metadata(target_metadata)


def configure(*, connection=None, url=None):
    options = {"target_metadata": target_metadata, "version_table": "catalog_alembic_version"}
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
        raise ValueError("Catalog migrations require PostgreSQL")
    configure(connection=external)
else:
    raw_url = os.environ.get("CATALOG_DATABASE_URL")
    try:
        if not raw_url:
            raise ValueError()
        url = make_url(raw_url)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        if url.drivername != "postgresql+psycopg" or not url.database:
            raise ValueError()
    except Exception:
        raise ValueError("Catalog migrations require an explicit PostgreSQL CATALOG_DATABASE_URL") from None
    if context.is_offline_mode():
        configure(url=url)
    else:
        engine = None
        try:
            engine = create_engine(url, hide_parameters=True)
            with engine.connect() as connection:
                configure(connection=connection)
        except Exception:
            raise ValueError("Catalog migration could not complete") from None
        finally:
            if engine is not None:
                engine.dispose()
