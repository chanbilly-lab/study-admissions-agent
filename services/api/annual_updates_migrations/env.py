"""Explicit isolated annual request migration; application startup never calls it."""

import os

from alembic import context
from sqlalchemy import create_engine, text

from services.api.app.ingestion.annual_updates.db import annual_database_url
from services.api.app.ingestion.annual_updates.models import AnnualUpdatesBase

config = context.config


def configure(*, connection=None, url=None):
    options = {"target_metadata": AnnualUpdatesBase.metadata, "version_table": "annual_updates_alembic_version",
               "version_table_schema": "public"}
    if connection is not None:
        if not connection.in_transaction():
            raise ValueError("An explicit migration transaction is required")
        location = connection.execute(text("SELECT current_database(),current_schema()")).one()
        if tuple(location) != ("annual_source_updates", "public"):
            raise ValueError("Annual update migrations require the explicit maintenance namespace")
        options["connection"] = connection
    else:
        options.update(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    context.configure(**options)
    with context.begin_transaction():
        context.run_migrations()


external = config.attributes.get("connection")
if external is not None:
    if external.dialect.name != "postgresql":
        raise ValueError("Annual update metadata requires PostgreSQL")
    configure(connection=external)
else:
    engine = None
    try:
        url = annual_database_url(os.environ.get("ANNUAL_UPDATES_DATABASE_URL"))
        if context.is_offline_mode():
            configure(url=url)
        else:
            engine = create_engine(url, hide_parameters=True, echo=False, connect_args={"connect_timeout": 5})
            with engine.begin() as connection:
                configure(connection=connection)
    except Exception:
        raise ValueError("Annual update migration could not complete") from None
    finally:
        if engine is not None:
            engine.dispose()
