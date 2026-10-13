"""Explicit, independent local reference migrations; no startup or seed."""

import os

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from services.api.app.statistics.reference_cutoffs.models import ReferenceCutoffsBase

config = context.config


def configure(*, connection=None, url=None):
    options = {"target_metadata": ReferenceCutoffsBase.metadata,
               "version_table": "reference_cutoffs_alembic_version"}
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
        raise ValueError("Reference cutoffs require PostgreSQL")
    configure(connection=external)
else:
    raw = os.environ.get("REFERENCE_CUTOFFS_DATABASE_URL")
    try:
        if not raw:
            raise ValueError()
        url = make_url(raw)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        if (url.drivername != "postgresql+psycopg" or url.host not in {"127.0.0.1", "localhost", "::1"}
                or url.database != "reference_zj_2026" or not url.username or not url.password):
            raise ValueError()
    except Exception:
        raise ValueError("An explicit local reference maintenance database is required") from None
    if context.is_offline_mode():
        configure(url=url)
    else:
        engine = None
        try:
            engine = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
            with engine.connect() as connection:
                configure(connection=connection)
        except Exception:
            raise ValueError("Local reference migration could not complete") from None
        finally:
            if engine is not None:
                engine.dispose()
