"""Offline catalog CLI and frozen migration checks; no database connection."""

import importlib.util
import io
import logging
import logging.config
import os
from pathlib import Path
import subprocess
import sys

from alembic import command
import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, MetaData, Table, UniqueConstraint
from sqlalchemy.dialects import postgresql

from app.admissions_catalog.models import CatalogBase
from app.admissions_catalog.store import migration_config


ROOT = Path(__file__).resolve().parents[3]
SECRET_SENTINEL = "T11_SYNTHETIC_CONFIGURATION_SECRET"


@pytest.mark.parametrize("url", [None, f"sqlite:///{SECRET_SENTINEL}.db", f"invalid://user:{SECRET_SENTINEL}@localhost/db"])
def test_catalog_cli_requires_explicit_supported_configuration_without_echoing_input(url, tmp_path):
    environment = os.environ.copy()
    environment.pop("CATALOG_DATABASE_URL", None)
    if url is not None:
        environment["CATALOG_DATABASE_URL"] = url
    # A user .env and unrelated legacy/V2 variables cannot supply the catalog URL.
    (tmp_path / ".env").write_text(f"DATABASE_URL=postgresql://user:{SECRET_SENTINEL}@localhost/db\n", encoding="utf-8")
    environment.update(V2_DATABASE_URL=f"postgresql://user:{SECRET_SENTINEL}@localhost/db",
                       V2_DATA_MODE="invalid", DEMO_MODE="invalid")
    result = subprocess.run([sys.executable, "-m", "alembic", "-c",
                             str(ROOT / "services/api/catalog_alembic.ini"), "upgrade", "0001_catalog_t11", "--sql"],
                            cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "Catalog migrations require an explicit PostgreSQL CATALOG_DATABASE_URL" in output
    assert SECRET_SENTINEL not in output
    assert "CREATE TABLE" not in output


def test_catalog_offline_upgrade_does_not_connect_or_reconfigure_loggers(monkeypatch):
    monkeypatch.setenv("CATALOG_DATABASE_URL", f"postgresql+psycopg://user:{SECRET_SENTINEL}@127.0.0.1:1/catalog_fixture")
    monkeypatch.setenv("V2_DATA_MODE", "invalid")
    monkeypatch.setenv("DEMO_MODE", "invalid")
    monkeypatch.setattr(logging.config, "fileConfig", lambda *args, **kwargs: pytest.fail("fileConfig must not be invoked"))
    loggers = [logging.getLogger(name) for name in ("", "alembic", "sqlalchemy", "httpx", "httpcore", "uvicorn")]
    before = [(list(logger.handlers), logger.disabled, logger.level, logger.propagate) for logger in loggers]
    config = migration_config()
    buffer = io.StringIO()
    config.output_buffer = buffer
    command.upgrade(config, "0001_catalog_t11", sql=True)
    output = buffer.getvalue()
    assert "CREATE TABLE catalog_alembic_version" in output
    assert output.count("CREATE TABLE catalog_") == 6
    assert "CREATE TABLE auth_" not in output and "CREATE TABLE institutions" not in output
    assert SECRET_SENTINEL not in output
    assert [(list(logger.handlers), logger.disabled, logger.level, logger.propagate) for logger in loggers] == before


def _table_signature(table):
    dialect = postgresql.dialect()
    columns = {column.name: (column.type.compile(dialect=dialect), column.nullable, column.primary_key)
               for column in table.columns}
    constraints = set()
    for constraint in table.constraints:
        if isinstance(constraint, CheckConstraint):
            constraints.add(("check", constraint.name, str(constraint.sqltext)))
        elif isinstance(constraint, UniqueConstraint):
            constraints.add(("unique", constraint.name, tuple(column.name for column in constraint.columns)))
        elif isinstance(constraint, ForeignKeyConstraint):
            constraints.add(("foreign", constraint.name,
                             tuple((element.parent.name, element.target_fullname) for element in constraint.elements),
                             constraint.ondelete))
    return columns, constraints


def test_current_metadata_matches_frozen_literal_migration(monkeypatch):
    path = ROOT / "services/api/catalog_migrations/versions/0001_catalog_t11.py"
    spec = importlib.util.spec_from_file_location("t11_frozen_catalog_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    frozen = MetaData()
    monkeypatch.setattr(module.op, "create_table", lambda name, *columns, **kwargs: Table(name, frozen, *columns, **kwargs))
    module.upgrade()
    assert module.revision == "0001_catalog_t11" and module.down_revision is None
    assert set(frozen.tables) == set(CatalogBase.metadata.tables)
    assert {name: _table_signature(table) for name, table in frozen.tables.items()} == {
        name: _table_signature(table) for name, table in CatalogBase.metadata.tables.items()}
    # Historic migration definitions must not follow mutable application imports.
    assert "app.admissions_catalog" not in path.read_text(encoding="utf-8")
