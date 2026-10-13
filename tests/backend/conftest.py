from datetime import date
import socket

import pytest
from fastapi.testclient import TestClient

from services.api.app.main import create_app
from services.api.app.migrations import migrate
from services.api.app.seed import seed
from services.api.app.settings import Settings


@pytest.fixture(autouse=True)
def deny_network(monkeypatch, request):
    """Offline backend tests fail if Python attempts an outbound socket connection."""
    if "postgres" in request.keywords:
        return
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex
    def offline_connect(sock, address):
        # Windows asyncio implements socketpair with a loopback TCP pair.
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original_connect(sock, address)
        raise AssertionError("Offline test attempted an external network connection")
    def offline_connect_ex(sock, address):
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original_connect_ex(sock, address)
        raise AssertionError("Offline test attempted an external network connection")
    monkeypatch.setattr(socket.socket, "connect", offline_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", offline_connect_ex)


@pytest.fixture
def settings():
    return Settings(_env_file=None, database_url="sqlite+pysqlite:///:memory:", sqlite_test_mode=True,
                    supported_province="浙江", entry_year=2027, model_mode="mock", assessment_date=date(2026, 9, 30))


@pytest.fixture
def app(settings):
    application = create_app(settings)
    migrate(application.state.engine)
    seed(application.state.engine)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def profile_input():
    return {"display_name": "合成学生甲", "is_synthetic": True, "confirmed": True,
            "study_level": "bachelor", "course_system": "gaokao", "entry_year": 2027,
            "province": "浙江", "applicant_category": "cn_mainland", "subjects": ["physics", "chemistry"],
            "assessments": {"gaokao_total": {"value": 620, "scale": 750, "unit": "points", "kind": "achieved"},
                            "math": {"value": 115, "scale": 150, "unit": "points", "kind": "achieved"},
                            "english_language": {"value": 7, "scale": 9, "unit": "band", "kind": "achieved"}},
            "weekly_hours": 6}


ALICE = {"Authorization": "Bearer demo-alice-token"}
BOB = {"Authorization": "Bearer demo-bob-token"}


@pytest.fixture
def saved_profile(client, profile_input):
    response = client.post("/v1/profiles", headers=ALICE, json=profile_input)
    assert response.status_code == 201, response.text
    return response.json()["data"]
