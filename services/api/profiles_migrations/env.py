"""Explicit isolated profile migrations; no dotenv, seed or logging changes."""

import os

from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from services.api.app.profiles.models import ProfilesBase


config = context.config
_HEADS = {"auth_alembic_version": "0006_audit_t10",
          "idempotency_alembic_version": "0001_idempotency_t49"}


def configure(*, connection=None, url=None):
    options = {"target_metadata": ProfilesBase.metadata,
               "version_table": "profiles_alembic_version"}
    if connection is not None:
        if connection.dialect.name != "postgresql":
            raise ValueError("Profiles migrations require PostgreSQL")
        for table, head in _HEADS.items():
            if connection.execute(text(f"SELECT version_num FROM {table}")).scalars().all() != [head]:
                raise ValueError("Profiles migration prerequisites are unavailable")
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
        raise ValueError("Profiles migration could not complete") from None
else:
    try:
        raw = os.environ.get("PROFILES_DATABASE_URL")
        if not raw:
            raise ValueError()
        url = make_url(raw)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        if url.drivername != "postgresql+psycopg" or not url.database:
            raise ValueError()
    except Exception:
        raise ValueError("Profiles migrations require an explicit PostgreSQL PROFILES_DATABASE_URL") from None
    if context.is_offline_mode():
        configure(url=url)
    else:
        engine = None
        try:
            engine = create_engine(url, hide_parameters=True)
            with engine.begin() as connection:
                configure(connection=connection)
        except Exception:
            raise ValueError("Profiles migration could not complete") from None
        finally:
            if engine is not None:
                engine.dispose()
