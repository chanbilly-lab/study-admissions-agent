"""T41 uses the existing dedicated random schemas, with a real loopback origin."""
import pytest
from http.server import ThreadingHTTPServer
from tests.integration.privacy_rights.conftest import (
    schema_pair, pg_engine, clock, runtime, idp, oidc_adapter,
    auth_store, auth_service, actor_factory, privacy_settings, privacy_service,
    catalog_store, catalog_tree, source_store, administrator_factory, source_request_factory,
    blob_root, io_probe, storage_store, storage_factory, idempotency_store, imports_store,
    imports_factory, candidate_factory, evidence_store, evidence_factory, facts_store,
    facts_factory, classification_factory, reviews_store, releases_store, import_case_factory,
    isolate_releases_environment_and_network, profiles_store, assessments_store,
    assessment_case_factory, plans_store, plan_case_factory, execution_store, execution_case_factory,
    changes_store, change_case_factory, revisions_store, jobs_store, notifications_store, job_case_factory,
    rights_store, external_ledger, rights_case_factory,
)
from tests.integration.auth.conftest import session_settings_factory as base_session_settings_factory

@pytest.fixture
def loopback_server():
    from tests.integration.privacy_ui.test_t41_browser import Bridge
    server=ThreadingHTTPServer(('127.0.0.1',0),Bridge)
    server.daemon_threads=True
    server.origin='http://127.0.0.1:'+str(server.server_port)
    try:yield server
    finally:server.server_close()

@pytest.fixture
def session_settings_factory(loopback_server,base_session_settings_factory):
    from services.api.app.auth.schemas import AuthProviderSettings
    from services.api.app.auth.config import SessionAuthSettings
    def make(**changes):
        settings=base_session_settings_factory(**changes)
        callback=loopback_server.origin+'/api/v2/auth/callback'
        provider=AuthProviderSettings.model_validate({**settings.provider.model_dump(),'callback_allowlist':(callback,)})
        return SessionAuthSettings.model_validate({**settings.model_dump(),'provider':provider,'redirect_uri':callback})
    return make

@pytest.fixture
def session_settings(session_settings_factory):
    return session_settings_factory()
