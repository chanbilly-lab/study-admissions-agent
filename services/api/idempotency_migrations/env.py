"""Explicit PostgreSQL profile; no dotenv, runtime mounting or logging mutation."""

import os

from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from services.api.app.idempotency.models import IdempotencyBase


config = context.config


def configure(*, connection=None, url=None):
    options = {"target_metadata": IdempotencyBase.metadata, "version_table": "idempotency_alembic_version"}
    if connection is not None:
        if connection.dialect.name != "postgresql":
            raise ValueError()
        if connection.execute(text("SELECT version_num FROM auth_alembic_version")).scalars().all() != ["0006_audit_t10"]:
            raise ValueError()
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
        raise ValueError("Idempotency migration could not complete") from None
else:
    try:
        raw = os.environ.get("IDEMPOTENCY_DATABASE_URL")
        if not raw:
            raise ValueError()
        url = make_url(raw)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        if url.drivername != "postgresql+psycopg" or not url.database:
            raise ValueError()
    except Exception:
        raise ValueError("Idempotency migrations require an explicit PostgreSQL IDEMPOTENCY_DATABASE_URL") from None
    if context.is_offline_mode():
        configure(url=url)
    else:
        engine = None
        try:
            engine = create_engine(url, hide_parameters=True)
            with engine.begin() as connection:
                configure(connection=connection)
        except Exception:
            raise ValueError("Idempotency migration could not complete") from None
        finally:
            if engine is not None:
                engine.dispose()
