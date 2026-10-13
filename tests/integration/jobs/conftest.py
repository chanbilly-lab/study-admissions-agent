"""Real T36 jobs use a fresh schema in the dedicated loopback test database."""

import os
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from sqlalchemy import create_engine,inspect,select,text
from sqlalchemy.orm import Session

from tests.integration.plan_revisions.conftest import (
    clock,session_settings_factory,session_settings,runtime,idp,oidc_adapter,
    auth_store,auth_service,actor_factory,privacy_settings,privacy_service,
    catalog_store,catalog_tree,source_store,administrator_factory,source_request_factory,
    blob_root,io_probe,storage_store,storage_factory,idempotency_store,imports_store,
    imports_factory,candidate_factory,evidence_store,evidence_factory,facts_store,
    facts_factory,classification_factory,reviews_store,releases_store,import_case_factory,
    isolate_releases_environment_and_network,profiles_store,assessments_store,
    assessment_case_factory,plans_store,plan_case_factory,execution_store,execution_case_factory,
    changes_store,change_case_factory,revisions_store,
)


@pytest.fixture
def pg_engine():
    raw=os.getenv("T23_TEST_POSTGRES_URL")
    if not raw:
        pytest.fail("T36 requires the dedicated T23_TEST_POSTGRES_URL",pytrace=False)
    parsed=urlsplit(raw)
    if parsed.scheme!="postgresql+psycopg" or parsed.hostname!="127.0.0.1" or parsed.port!=55438 or parsed.path!="/study_t23_20261003":
        pytest.fail("T36 requires the dedicated loopback study_t23_20261003 database",pytrace=False)
    schema="jobs_t36_"+uuid4().hex
    admin=create_engine(raw,hide_parameters=True,connect_args={"connect_timeout":5})
    engine,created=None,False
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        created=True
        engine=create_engine(raw,hide_parameters=True,connect_args={"options":"-csearch_path="+schema,"connect_timeout":5})
        assert inspect(engine).get_table_names()==[]
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def jobs_store(revisions_store,pg_engine):
    from services.api.app.jobs.store import JobsStore,migrate_jobs
    migrate_jobs(pg_engine)
    return JobsStore(pg_engine)


@pytest.fixture
def notifications_store(jobs_store,pg_engine):
    from services.api.app.notifications.store import NotificationsStore
    return NotificationsStore(pg_engine)


@pytest.fixture
def job_case_factory(jobs_store,notifications_store,change_case_factory,pg_engine):
    from services.api.app.jobs.service import JobsService
    from services.api.app.jobs.schemas import JobsPolicy
    from services.api.app.notifications.service import NotificationService
    from services.api.app.notifications.schemas import NotificationPolicy,PreferenceInput
    from services.api.app.releases.models import ChangeEvent
    from services.api.app.releases.schemas import WithdrawalRequest

    def make(*,opt_in=True,withdraw=False,lease_seconds=30,max_attempts=3,retry_seconds=1,
             job_ttl_seconds=86400,jobs_policy=None,notification_policy=None,**options):
        original=change_case_factory(**options)
        changes=original.service
        notifications=NotificationService(original.profiles,notifications_store,
            notification_policy or NotificationPolicy(enabled=True,allow_test_notifications=True))
        jobs=JobsService(changes,notifications,jobs_store,jobs_policy or JobsPolicy(enabled=True,
            allow_test_jobs=True,allow_cleanup_probe=True,lease_seconds=lease_seconds,
            max_attempts=max_attempts,retry_seconds=retry_seconds,job_ttl_seconds=job_ttl_seconds))
        values={**vars(original),"changes":changes,"notifications":notifications,"jobs":jobs,
            "service":jobs,"auth":jobs.auth_service,"profile_service":original.profiles,
            "notifications_store":notifications_store,"jobs_store":jobs_store,
            "clock":jobs.auth_service.clock}
        if opt_in:
            values["preference"]=notifications.update_preferences(original.principal,PreferenceInput(
                expected_version=0,enabled=True,profile_id=original.profile.profile_id,student_confirmed=True))
        else:
            values["preference"]=notifications.get_preferences(original.principal)
        values["preferences"]=values["preference"]
        if withdraw:
            original.releases.withdraw(original.reviewer.principal,WithdrawalRequest(
                release_id=original.release.release_id,expected_state_revision=original.release.state_revision,
                reason_code="SOURCE_UNAVAILABLE"))
        with Session(pg_engine) as session:
            values["event_id"]=session.scalar(select(ChangeEvent.id).where(
                ChangeEvent.release_id==original.release.release_id,
                ChangeEvent.event_type==("withdrawn" if withdraw else "published")))
        assert values["event_id"] is not None
        return SimpleNamespace(**values)
    return make
