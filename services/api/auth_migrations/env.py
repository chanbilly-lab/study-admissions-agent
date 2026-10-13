"""Authentication migrations never import the demo app, models, settings or seed."""

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from services.api.app.auth.models import AuthBase
from services.api.app.privacy import models as privacy_models
from services.api.app.auth.grants import models as grant_models
from services.api.app.audit import models as audit_models
from services.api.app.settings import V2RuntimeSettings

config = context.config


def configure(connection=None, url=None):
    options = {"target_metadata": AuthBase.metadata, "version_table": "auth_alembic_version"}
    if connection is not None:
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
    settings = V2RuntimeSettings(_env_file=None)
    if settings.database_url is None:
        raise ValueError("authentication migration requires explicit V2_DATABASE_URL")
    url = make_url(settings.database_url.get_secret_value())
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    if context.is_offline_mode():
        configure(url=url)
    else:
        engine = create_engine(url, hide_parameters=True)
        try:
            with engine.connect() as connection:
                configure(connection=connection)
        finally:
            engine.dispose()
