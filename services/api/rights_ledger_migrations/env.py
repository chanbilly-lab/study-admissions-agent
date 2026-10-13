"""Explicit incremental PostgreSQL chain; no dotenv, seed, or startup DDL."""

import os

from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from services.api.app.privacy.rights.models import LedgerBase

config = context.config
HEADS = {}


def configure(*, connection=None, url=None):
    options = {"target_metadata": LedgerBase.metadata, "version_table": "rights_ledger_alembic_version"}
    if connection is not None:
        if connection.dialect.name != "postgresql":
            raise ValueError("Rights migrations require PostgreSQL")
        for table, head in HEADS.items():
            if connection.execute(text("SELECT version_num FROM " + table)).scalars().all() != [head]:
                raise ValueError("Rights migration prerequisites are unavailable")
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
        raise ValueError("Rights migration could not complete") from None
else:
    try:
        raw = os.environ.get("RIGHTS_LEDGER_DATABASE_URL")
        if not raw:
            raise ValueError()
        url = make_url(raw)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        if url.drivername != "postgresql+psycopg" or not url.database:
            raise ValueError()
    except Exception:
        raise ValueError("Rights migrations require an explicit PostgreSQL RIGHTS_LEDGER_DATABASE_URL") from None
    if context.is_offline_mode():
        configure(url=url)
    else:
        engine = None
        try:
            engine = create_engine(url, hide_parameters=True)
            with engine.begin() as connection:
                configure(connection=connection)
        except Exception:
            raise ValueError("Rights migration could not complete") from None
        finally:
            if engine is not None:
                engine.dispose()
