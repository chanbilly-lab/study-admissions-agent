"""Actual SQLAlchemy routing guards reject foreign engines before connections."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from services.api.app.audit.models import AuditEvent
from services.api.app.auth.models import AuthOwnedResource, AuthSession, AuthUser, AuthUserRole
from services.api.app.idempotency.models import IdempotencyRecord
from services.api.app.privacy.models import PrivacyAdmissionRecord, PrivacyNoticeVersion
from services.api.app.profiles.models import ProfileRoot, ProfileVersion
from services.api.app.profiles.schemas import ProfileError
from services.api.app.profiles.service import ProfileService
from services.api.app.profiles.store import ProfilesStore


@pytest.mark.parametrize("mapper", [AuthUser, AuthSession, AuthUserRole, AuthOwnedResource,
    PrivacyAdmissionRecord, PrivacyNoticeVersion, AuditEvent, IdempotencyRecord, ProfileRoot, ProfileVersion])
def test_all_used_mappers_must_use_same_engine_before_io(mapper):
    first = create_engine("postgresql+psycopg://test:test@127.0.0.1:1/unreachable")
    second = create_engine("postgresql+psycopg://test:test@127.0.0.1:1/unreachable")
    connections = []
    for engine in (first, second):
        event.listen(engine, "do_connect", lambda *args: connections.append(True))
    service = object.__new__(ProfileService)
    service.store = ProfilesStore(first)
    with Session(first, binds={mapper: second}) as session, session.begin():
        with pytest.raises(ProfileError) as error:
            service._guard_session(session)
        assert error.value.status_code == 503
    assert connections == []
    first.dispose()
    second.dispose()


def test_store_requires_postgresql_and_active_caller_transaction():
    engine = create_engine("sqlite://")
    with pytest.raises(ProfileError):
        ProfilesStore(engine)
    engine.dispose()
    engine = create_engine("postgresql+psycopg://test:test@127.0.0.1:1/unreachable")
    with Session(engine) as session:
        with pytest.raises(ProfileError):
            with ProfilesStore(engine)._work(session):
                pytest.fail("inactive transaction was accepted")
    engine.dispose()
