from logging.config import fileConfig

from alembic import context

from services.api.app.database import make_engine
from services.api.app.models import Base
from services.api.app.settings import Settings

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline():
    settings = Settings()
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    external = config.attributes.get("connection")
    if external is not None:
        context.configure(connection=external, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = make_engine(Settings())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
