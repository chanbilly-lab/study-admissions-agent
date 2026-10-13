from copy import deepcopy
from datetime import date
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import JSON, create_engine, event, func, inspect, select, text
from sqlalchemy.orm import Session

from services.api.app.main import create_app
from services.api.app.migrations import migrate
from services.api.app.models import (
    EligibilityResultRecord, EvidenceRecord, InstitutionRecord, OfferingRecord,
    PlanDraftRecord, ProfileVersionRecord, RuleRecord,
)
from services.api.app.seed import FIXTURE_PATH, seed
from services.api.app.settings import Settings
from .conftest import ALICE, BOB


def test_frozen_migration_and_idempotent_seed_preserve_profile(app, saved_profile):
    engine = app.state.engine
    assert set(inspect(engine).get_table_names()) == {"alembic_version", "institutions", "offerings", "evidence", "rules", "profile_versions", "eligibility_results", "plan_drafts"}
    migrate(engine)
    assert seed(engine) == {"institutions": 0, "evidence": 0, "offerings": 0, "rules": 0}
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(ProfileVersionRecord)) == 1
        assert session.get(ProfileVersionRecord, saved_profile["id"]).payload == saved_profile
        for item in session.scalars(select(EvidenceRecord)):
            assert sha256(item.raw_document.encode("utf-8")).hexdigest() == item.document_sha256


def test_bad_fixture_hash_and_existing_conflict_do_not_overwrite(app, tmp_path):
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    invalid = deepcopy(fixture)
    invalid["documents"][0]["raw_document"] += "篡改"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        seed(app.state.engine, path)
    changed = deepcopy(fixture)
    changed["institutions"][0]["name"] = "DEMO_冲突机构名"
    path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="preserved"):
        seed(app.state.engine, path)
    assert seed(app.state.engine) == {"institutions": 0, "evidence": 0, "offerings": 0, "rules": 0}


def test_sqlite_requires_explicit_test_mode():
    with pytest.raises(ValidationError, match="SQLite requires"):
        Settings(_env_file=None, database_url="sqlite+pysqlite:///:memory:", sqlite_test_mode=False)


def test_environment_plain_variables_precede_legacy_aliases(monkeypatch):
    monkeypatch.setenv("SUPPORTED_PROVINCE", "浙江")
    monkeypatch.setenv("M0_SUPPORTED_PROVINCE", "广东")
    monkeypatch.setenv("MODEL_MODE", "live")
    monkeypatch.setenv("M0_MODEL_MODE", "mock")
    config = Settings(_env_file=None)
    assert config.supported_province == "浙江" and config.model_mode == "live"


CATALOG_COUNTS = {"institutions": 2, "evidence": 7, "offerings": 4, "rules": 9}
ZERO_INSERTS = {name: 0 for name in CATALOG_COUNTS}
FROZEN_MODELS = (
    InstitutionRecord, OfferingRecord, EvidenceRecord, RuleRecord,
    ProfileVersionRecord, EligibilityResultRecord, PlanDraftRecord,
)
FROZEN_TABLES = {model.__tablename__ for model in FROZEN_MODELS} | {"alembic_version"}
ALEMBIC_CONFIG = Path(__file__).resolve().parents[2] / "services/api/alembic.ini"


@pytest.fixture
def postgres_engine():
    """Only the internally generated schema is created or removed by a test."""
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("未执行 PostgreSQL integration：TEST_POSTGRES_URL 未配置")
    if not url.startswith("postgresql+psycopg://"):
        pytest.fail("TEST_POSTGRES_URL must explicitly use postgresql+psycopg")
    schema = f"m0_test_{uuid4().hex}"
    admin_engine = create_engine(url, connect_args={"connect_timeout": 5})
    test_engine = None
    schema_created = False
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        schema_created = True
        test_engine = create_engine(
            url, connect_args={"options": f"-csearch_path={schema}", "connect_timeout": 5},
        )
        with test_engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == schema
            assert connection.scalar(text("SHOW search_path")) == schema
        assert inspect(test_engine).get_table_names() == []
        yield test_engine
    finally:
        if test_engine is not None:
            test_engine.dispose()
        try:
            if schema_created:
                with admin_engine.begin() as connection:
                    connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        finally:
            admin_engine.dispose()


@pytest.fixture
def postgres_client(postgres_engine):
    settings = Settings(
        _env_file=None, database_url=postgres_engine.url.render_as_string(hide_password=False),
        sqlite_test_mode=False, supported_province="浙江", entry_year=2027,
        model_mode="mock", assessment_date=date(2026, 9, 30),
    )
    application = create_app(settings)
    # The factory engine has not connected; every API request uses the isolated PG engine.
    application.state.engine.dispose()
    application.state.engine = postgres_engine
    migrate(postgres_engine)
    assert seed(postgres_engine) == CATALOG_COUNTS
    with TestClient(application) as client:
        yield client


def assert_frozen_postgresql_schema(engine):
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == FROZEN_TABLES
    expected_foreign_keys = {
        "institutions": set(), "evidence": set(), "profile_versions": set(),
        "offerings": {(("institution_id",), "institutions", ("id",))},
        "rules": {(("offering_id",), "offerings", ("id",)),
                  (("evidence_id",), "evidence", ("id",))},
        "eligibility_results": {(("profile_version_id",), "profile_versions", ("id",)),
                                (("offering_id",), "offerings", ("id",))},
        "plan_drafts": {(("profile_version_id",), "profile_versions", ("id",))},
    }
    expected_indexes = {
        "institutions": set(), "evidence": set(),
        "offerings": {("ix_offerings_country", ("country",)),
                      ("ix_offerings_entry_year", ("entry_year",))},
        "rules": {("ix_rules_offering_id", ("offering_id",))},
        "profile_versions": {("ix_profile_versions_owner_id", ("owner_id",))},
        "eligibility_results": {("ix_eligibility_results_owner_id", ("owner_id",)),
                                ("ix_eligibility_results_profile_version_id", ("profile_version_id",))},
        "plan_drafts": {("ix_plan_drafts_owner_id", ("owner_id",)),
                        ("ix_plan_drafts_profile_version_id", ("profile_version_id",))},
    }
    for table in expected_foreign_keys:
        assert inspector.get_pk_constraint(table)["constrained_columns"] == ["id"]
        foreign_keys = inspector.get_foreign_keys(table)
        assert {(tuple(item["constrained_columns"]), item["referred_table"],
                 tuple(item["referred_columns"])) for item in foreign_keys} == expected_foreign_keys[table]
        assert all(item["referred_schema"] in (None, inspector.default_schema_name) for item in foreign_keys)
        # PostgreSQL also reflects unique-constraint backing indexes; these are checked separately.
        indexes = inspector.get_indexes(table)
        assert {(item["name"], tuple(item["column_names"])) for item in indexes
                if not item.get("duplicates_constraint")} == expected_indexes[table]
        if table != "institutions":
            columns = {item["name"]: item for item in inspector.get_columns(table)}
            assert isinstance(columns["payload"]["type"], JSON)
            assert columns["payload"]["nullable"] is False
    assert {(item["name"], tuple(item["column_names"]))
            for item in inspector.get_unique_constraints("profile_versions")} == {
                ("uq_profile_version", ("profile_id", "version")),
            }
    with engine.connect() as connection:
        assert connection.scalars(text("SELECT version_num FROM alembic_version")).all() == ["0001_m0"]


def database_snapshot(engine):
    """Read every stored column, including private payloads, through a fresh transaction."""
    with Session(engine) as session:
        return {
            model.__tablename__: [
                {column.name: deepcopy(getattr(row, column.name)) for column in model.__table__.columns}
                for row in session.scalars(select(model).order_by(model.id))
            ]
            for model in FROZEN_MODELS
        }


def assert_catalog_roundtrip(engine):
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    with Session(engine) as session:
        for model in (InstitutionRecord, EvidenceRecord, OfferingRecord, RuleRecord):
            assert session.scalar(select(func.count()).select_from(model)) == CATALOG_COUNTS[model.__tablename__]
        for expected in fixture["institutions"]:
            row = session.get(InstitutionRecord, expected["id"])
            assert {column.name: getattr(row, column.name) for column in row.__table__.columns} == expected
            assert row.is_synthetic is True
        for document in fixture["documents"]:
            expected = document["evidence"]
            row = session.get(EvidenceRecord, expected["id"])
            assert row.raw_document == document["raw_document"]
            assert sha256(row.raw_document.encode("utf-8")).hexdigest() == row.document_sha256 == expected["document_sha256"]
            assert row.document_version_id == expected["document_version_id"]
            assert row.payload == expected
            assert row.payload["is_synthetic"] is True
            assert expected["excerpt"] in row.raw_document
        assert any(ord(character) > 127 for item in fixture["documents"] for character in item["raw_document"])
        for offering in fixture["offerings"]:
            row = session.get(OfferingRecord, offering["id"])
            expected = deepcopy(offering)
            expected["rules"] = []
            assert row.payload == expected
            assert row.is_synthetic is True
            assert row.institution_id == offering["institution_id"]
            assert row.country == offering["country"] and row.entry_year == offering["entry_year"]
            assert row.province == offering["province"]
            for rule in offering["rules"]:
                record = session.get(RuleRecord, rule["id"])
                assert record.payload == rule
                assert record.offering_id == offering["id"]
                assert record.evidence_id == rule["evidence_id"] and record.version == rule["version"]


def create_private_records(client, profile_input, headers):
    response = client.post("/v1/profiles", headers=headers, json=profile_input)
    assert response.status_code == 201, response.text
    profile = response.json()["data"]
    payload = {"profile_version_id": profile["id"], "offering_ids": ["DEMO_CN_MATH", "DEMO_GB_DEFERRED"]}
    response = client.post("/v1/eligibility/check", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    checked = response.json()["data"]
    response = client.post("/v1/plans/drafts", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return profile, checked, response.json()["data"]


@pytest.mark.postgres
def test_postgresql_migration_and_seed_in_isolated_schema(postgres_engine):
    migrate(postgres_engine)
    assert_frozen_postgresql_schema(postgres_engine)
    assert seed(postgres_engine) == CATALOG_COUNTS
    assert_catalog_roundtrip(postgres_engine)
    before = database_snapshot(postgres_engine)
    assert all(before[table] == [] for table in ("profile_versions", "eligibility_results", "plan_drafts"))
    assert seed(postgres_engine) == ZERO_INSERTS
    assert database_snapshot(postgres_engine) == before


@pytest.mark.postgres
def test_postgresql_api_private_data_survives_repeat_upgrade_and_seed(postgres_engine, postgres_client, profile_input):
    alice = create_private_records(postgres_client, profile_input, ALICE)
    bob_input = deepcopy(profile_input)
    bob_input["display_name"] = "合成学生乙：PostgreSQL"
    bob = create_private_records(postgres_client, bob_input, BOB)
    with Session(postgres_engine) as session:
        for owner, (profile, checked, plan) in (("demo_alice", alice), ("demo_bob", bob)):
            row = session.get(ProfileVersionRecord, profile["id"])
            assert row.payload == profile and row.owner_id == owner
            assert row.profile_id == profile["id"] and row.version == 1 and row.is_synthetic is True
            row = session.get(PlanDraftRecord, plan["id"])
            assert row.payload == plan and row.owner_id == owner and row.profile_version_id == profile["id"]
            for result in checked + plan["eligibility_results"]:
                row = session.get(EligibilityResultRecord, result["id"])
                assert row.payload == result and row.owner_id == owner
                assert row.profile_version_id == profile["id"] and row.offering_id == result["offering_id"]
                assert row.ruleset_version == "DEMO_M0_v1"
    before = database_snapshot(postgres_engine)
    migrate(postgres_engine)
    assert seed(postgres_engine) == ZERO_INSERTS
    assert_frozen_postgresql_schema(postgres_engine)
    assert_catalog_roundtrip(postgres_engine)
    assert database_snapshot(postgres_engine) == before
    for headers, own, other in ((ALICE, alice, bob), (BOB, bob, alice)):
        assert postgres_client.get("/v1/profiles", headers=headers).json()["data"] == [own[0]]
        assert postgres_client.get(f"/v1/profiles/{own[0]['id']}", headers=headers).json()["data"] == own[0]
        assert postgres_client.get(f"/v1/plans/{own[2]['id']}", headers=headers).json()["data"] == own[2]
        assert postgres_client.get(f"/v1/profiles/{other[0]['id']}", headers=headers).status_code == 404
        assert postgres_client.get(f"/v1/plans/{other[2]['id']}", headers=headers).status_code == 404
        for endpoint in ("/v1/eligibility/check", "/v1/plans/drafts"):
            response = postgres_client.post(endpoint, headers=headers, json={
                "profile_version_id": other[0]["id"], "offering_ids": ["DEMO_CN_MATH"],
            })
            assert response.status_code == 404
    assert database_snapshot(postgres_engine) == before


@pytest.mark.postgres
def test_postgresql_late_fixture_conflict_rolls_back_flushed_rows(postgres_engine, postgres_client, profile_input, tmp_path):
    create_private_records(postgres_client, profile_input, ALICE)
    before = database_snapshot(postgres_engine)
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    changed = deepcopy(fixture)
    new_institution = deepcopy(changed["institutions"][0])
    new_institution["id"] = f"DEMO_ROLLBACK_{uuid4().hex}"
    new_institution["name"] = "DEMO_事务回滚测试机构"
    changed["institutions"].insert(0, new_institution)
    # This conflict is reached after the institutions stage has explicitly flushed.
    changed["offerings"][-1]["title"] += "：不可覆盖的冲突"
    path = tmp_path / "late-conflict.json"
    path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
    flushed_inserts = []

    def record_successful_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO INSTITUTIONS"):
            flushed_inserts.append(deepcopy(parameters))

    event.listen(postgres_engine, "after_cursor_execute", record_successful_insert)
    try:
        with pytest.raises(ValueError, match="existing data preserved"):
            seed(postgres_engine, path)
    finally:
        event.remove(postgres_engine, "after_cursor_execute", record_successful_insert)
    assert flushed_inserts, "The test must reach a successful INSERT before the later conflict"
    with Session(postgres_engine) as session:
        assert session.get(InstitutionRecord, new_institution["id"]) is None
    assert database_snapshot(postgres_engine) == before
    invalid = deepcopy(fixture)
    invalid["documents"][0]["raw_document"] += "篡改"
    path.write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        seed(postgres_engine, path)
    assert database_snapshot(postgres_engine) == before
    assert seed(postgres_engine) == ZERO_INSERTS


@pytest.mark.postgres
def test_postgresql_disposable_schema_downgrade_upgrade_and_reseed(postgres_engine):
    migrate(postgres_engine)
    assert seed(postgres_engine) == CATALOG_COUNTS
    before = database_snapshot(postgres_engine)
    assert all(before[table] == [] for table in ("profile_versions", "eligibility_results", "plan_drafts"))
    config = Config(str(ALEMBIC_CONFIG))
    with postgres_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    # The initial migration deliberately drops all business data; this is not a preservation test.
    assert set(inspect(postgres_engine).get_table_names()) == {"alembic_version"}
    with postgres_engine.connect() as connection:
        assert connection.scalars(text("SELECT version_num FROM alembic_version")).all() == []
    migrate(postgres_engine)
    assert_frozen_postgresql_schema(postgres_engine)
    assert seed(postgres_engine) == CATALOG_COUNTS
    assert_catalog_roundtrip(postgres_engine)
    assert database_snapshot(postgres_engine) == before
    assert seed(postgres_engine) == ZERO_INSERTS
