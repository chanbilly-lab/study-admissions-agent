from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from .settings import Settings


def make_engine(settings: Settings):
    options = {"pool_pre_ping": True}
    if settings.database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if ":memory:" in settings.database_url:
            options["poolclass"] = StaticPool
    engine = create_engine(settings.database_url, **options)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def foreign_keys_on(dbapi_connection, _):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")
    return engine
