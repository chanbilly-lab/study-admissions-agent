"""Future explicitly enabled synthetic CI. This file was not executed in T43."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
PROFILES = ("foundation", "identity", "public_catalog", "admin", "admin_review", "profiles",
            "assessments", "plans", "revisions", "notifications", "qa", "rights")
PG_TESTS = ("tests/integration/eligibility", "tests/integration/plan_execution", "tests/integration/qa",
            "tests/integration/privacy_rights/test_t40_http.py", "tests/integration/privacy_rights/test_t40_safety.py")


def run(arguments, *, environment=None, capture=False):
    return subprocess.run(arguments, cwd=ROOT, env=environment, check=True,
                          text=True, capture_output=capture, timeout=1800)


def pytest_gate(name, paths, marker, environment=None):
    report = ROOT / ".cache" / "ci" / (name + ".xml")
    report.parent.mkdir(parents=True, exist_ok=True)
    run([sys.executable, "-B", "-m", "pytest", "-p", "scripts.ci.offline_plugin", *paths,
         "-m", marker, "-q", "--junitxml=" + str(report)], environment=environment)
    if report.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("CI_REPORT_TOO_LARGE")
    suites = list(ET.fromstring(report.read_bytes()).iter("testsuite"))
    counts = {key: sum(int(suite.get(key, "0")) for suite in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    if counts["tests"] <= 0 or any(counts[key] for key in ("failures", "errors", "skipped")):
        raise ValueError("CI_GATE_FAILED_OR_SKIPPED")
    print(name + ": " + str(counts["tests"]) + " executed; no failures/errors/skips")


def migration_gate(url):
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, text
    from deploy.migrate import PROFILES as migration_profiles

    schema = "ci_migrations_" + secrets.token_hex(12)
    ledger_schema = "ci_ledger_" + secrets.token_hex(12)
    admin = create_engine(url, hide_parameters=True)
    created = []
    try:
        for name in (schema, ledger_schema):
            with admin.begin() as connection:
                connection.execute(text('CREATE SCHEMA "' + name + '"'))
            created.append(name)
        for profile in migration_profiles:
            selected = ledger_schema if profile == "rights_ledger" else schema
            config = Config(str(ROOT / "services" / "api" / (profile + "_alembic.ini")))
            heads = ScriptDirectory.from_config(config).get_heads()
            if len(heads) != 1:
                raise ValueError("CI_MIGRATION_HEAD_AMBIGUOUS")
            with admin.begin() as connection:
                connection.execute(text('SET LOCAL search_path TO "' + selected + '"'))
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
                actual = connection.execute(text("SELECT version_num FROM " + profile + "_alembic_version")).scalars().all()
                if actual != heads:
                    raise ValueError("CI_MIGRATION_HEAD_MISMATCH")
    finally:
        for name in reversed(created):
            with admin.begin() as connection:
                connection.execute(text('DROP SCHEMA "' + name + '" CASCADE'))
        admin.dispose()


def postgres_gate():
    image = os.environ.get("STUDY_CI_POSTGRES_IMAGE", "")
    if re.fullmatch(r"postgres:16\.\d+-bookworm@sha256:[0-9a-f]{64}", image) is None:
        raise ValueError("CI_FIXED_PG_IMAGE_REQUIRED")
    name = "study-ci-pg-" + secrets.token_hex(12)
    password = secrets.token_hex(32)
    print("::add-mask::" + password, flush=True)
    environment = dict(os.environ, POSTGRES_PASSWORD=password)
    owned = False
    try:
        run(["docker", "run", "--detach", "--name", name, "--publish", "127.0.0.1:55438:5432",
             "--env", "POSTGRES_PASSWORD", "--env", "POSTGRES_USER=study_ci",
             "--env", "POSTGRES_DB=study_t23_20261003", image], environment=environment, capture=True)
        owned = True
        deadline = time.monotonic() + 90
        while True:
            try:
                run(["docker", "exec", name, "pg_isready", "-U", "study_ci", "-d", "study_t23_20261003"], capture=True)
                break
            except subprocess.CalledProcessError:
                if time.monotonic() >= deadline:
                    raise ValueError("CI_PG_NOT_READY") from None
                time.sleep(1)
        url = "postgresql+psycopg://study_ci:" + password + "@127.0.0.1:55438/study_t23_20261003"
        migration_gate(url)
        environment = dict(os.environ, T23_TEST_POSTGRES_URL=url)
        pytest_gate("postgres", list(PG_TESTS), "postgres", environment)
    finally:
        if owned:
            # Only this invocation's successfully-created, randomly-named container.
            run(["docker", "rm", "--force", name], capture=True)


def execute(stage):
    if stage == "contracts":
        for profile in PROFILES:
            run([sys.executable, "-B", "scripts/generate_contracts.py", "--profile", profile, "--check"])
        for path in ("scripts/verify_contract.py", "scripts/verify_originals.py", "scripts/verify_qa_golden.py"):
            run([sys.executable, "-B", path])
        run(["git", "diff", "--exit-code", "--", "packages/contracts"])
    elif stage == "pure":
        pytest_gate("pure", ["tests/unit", "tests/backend", "tests/security", "tests/contracts", "tests/research", "tests/evals"], "not postgres")
    elif stage == "postgres":
        postgres_gate()
    else:
        run(["pnpm", "--dir", "apps/web", "test"])
        run(["pnpm", "--dir", "apps/web", "typecheck"])
        for mode in ("demo", "auth"):
            run(["pnpm", "--dir", "apps/web", "build", "--outDir", "../../.cache/ci/" + mode],
                environment=dict(os.environ, VITE_APP_MODE=mode))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("contracts", "pure", "postgres", "web"))
    args = parser.parse_args()
    if os.environ.get("STUDY_CI_CHECKS") != "1" or os.environ.get("GITHUB_ACTIONS") != "true":
        print("CI_NOT_EXECUTED: explicit synthetic workflow enablement required.", file=sys.stderr)
        return 78
    try:
        execute(args.stage)
    except Exception:
        print("CI_STAGE_FAILED: " + args.stage, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
