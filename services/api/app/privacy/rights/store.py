"""Explicit migrations/readiness for the business rights and external ledger chains."""
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from ...jobs.store import HEADS as JOBS_HEADS
from .models import RightsBase
from .schemas import RightsError

HEADS = {**JOBS_HEADS, "jobs_alembic_version": "0001_jobs_t36"}


def migrate(engine, *, ledger=False, target="head"):
    if engine.dialect.name != "postgresql" or target not in {"head", "base", "0001_rights_t40", "0001_ledger_t40"}:
        raise RightsError()
    name = "rights_ledger_alembic.ini" if ledger else "rights_alembic.ini"
    config = Config(str(Path(__file__).resolve().parents[3] / name))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, target)
    except Exception:
        raise RightsError() from None


class RightsStore:
    def __init__(self, engine):
        if engine.dialect.name != "postgresql":
            raise RightsError()
        self.engine = engine
        self._engine = engine

    def assert_schema_ready(self):
        if self.engine is not self._engine:
            raise RightsError()
        try:
            with self.engine.connect() as connection:
                for table, head in {**HEADS, "rights_alembic_version": "0001_rights_t40"}.items():
                    if connection.execute(text("SELECT version_num FROM " + table)).scalars().all() != [head]:
                        raise ValueError()
                for table, trigger in (("privacy_rights_requests", "privacy_rights_requests_scope_guard"),
                    ("privacy_rights_attempts", "privacy_rights_attempts_no_update")):
                    state = connection.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgrelid=CAST(:table AS regclass) AND tgname=:trigger AND NOT tgisinternal"),
                        {"table": table, "trigger": trigger}).scalar_one_or_none()
                    if state not in {"O", "A"}:
                        raise ValueError()
            for table in RightsBase.metadata.tables.values():
                if set(table.columns.keys()) != {column["name"] for column in inspect(self.engine).get_columns(table.name)}:
                    raise ValueError()
        except Exception:
            raise RightsError() from None
