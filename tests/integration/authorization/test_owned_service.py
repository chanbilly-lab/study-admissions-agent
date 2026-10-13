"""Real SQL owner scoping and immutable server ownership, without business payloads."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, select, update
from sqlalchemy.orm import Session

from services.api.app.auth.models import AuthSession, AuthUser

from .conftest import rejected


KINDS = ("profile", "plan", "attachment", "export", "job")
ACTIONS = ("read", "list", "write", "download", "export", "execute")
ALLOWED = {
    "profile": {"read", "list", "write", "export"},
    "plan": {"read", "list", "write", "export"},
    "attachment": {"read", "list", "download"},
    "export": {"read", "list", "download"},
    "job": {"read", "list", "execute"},
}


@pytest.fixture
def students(harness):
    first, second = harness.account(), harness.account()
    harness.role(first)
    harness.role(second)
    return first, second


@pytest.mark.parametrize("kind", KINDS)
def test_owner_filtered_list_count_and_uuid_pagination(harness, students, kind):
    first, second = students
    ours = [harness.owned(first, kind) for _ in range(3)]
    theirs = [harness.owned(second, kind) for _ in range(4)]
    principal = harness.principal(first)
    page = harness.authorizer.list_owned(principal, kind, limit=2)
    assert page.total == 3
    assert len(page.items) == 2 and page.next_cursor is not None
    next_page = harness.authorizer.list_owned(principal, kind, limit=2, after_id=page.next_cursor)
    assert next_page.total == 3
    assert len(next_page.items) == 1 and next_page.next_cursor is None
    ids = {row.id for row in (*page.items, *next_page.items)}
    assert ids == {row.id for row in ours}
    assert not ids.intersection(row.id for row in theirs)
    assert all(row.owner_user_id == first.user_id for row in (*page.items, *next_page.items))
    assert harness.authorizer.list_owned(harness.principal(second), kind).total == 4


@pytest.mark.parametrize("kind", KINDS)
def test_foreign_and_missing_resource_have_identical_failure(harness, students, kind):
    first, second = students
    own, foreign = harness.owned(first, kind), harness.owned(second, kind)
    principal = harness.principal(first)
    assert harness.authorizer.require_owned(principal, kind, own.id).id == own.id
    denied = rejected(lambda: harness.authorizer.require_owned(principal, kind, foreign.id), 404, "NOT_FOUND")
    missing = rejected(lambda: harness.authorizer.require_owned(principal, kind, uuid4()), 404, "NOT_FOUND")
    assert str(denied) == str(missing)
    assert str(foreign.id) not in str(denied)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("action", ACTIONS)
def test_fixed_action_matrix_does_not_grant_other_resource_actions(harness, students, kind, action):
    first, _ = students
    resource = harness.owned(first, kind)
    principal = harness.principal(first)
    if action in ALLOWED[kind]:
        assert harness.authorizer.require_owned(principal, kind, resource.id, action).id == resource.id
    else:
        rejected(lambda: harness.authorizer.require_owned(principal, kind, resource.id, action), 403)


@pytest.mark.parametrize("kind,action", (("profile", "write"), ("profile", "export"),
    ("plan", "write"), ("plan", "export"), ("attachment", "download"),
    ("export", "download"), ("job", "execute")))
def test_cross_owner_sensitive_actions_never_run_callback(harness, students, kind, action):
    first, second = students
    foreign = harness.owned(second, kind)
    principal = harness.principal(first)
    effects = []
    rejected(lambda: harness.authorizer.require_owned(principal, kind, foreign.id, action), 404)
    rejected(lambda: harness.authorizer.execute_owned(principal, kind, foreign.id, action,
        lambda db, current, resource: effects.append(resource.id)), 404)
    assert effects == []


def test_owned_id_cannot_be_reinterpreted_as_another_resource_kind(harness, students):
    first, _ = students
    profile = harness.owned(first)
    principal = harness.principal(first)
    rejected(lambda: harness.authorizer.require_owned(principal, "plan", profile.id), 404)
    rejected(lambda: harness.authorizer.cache_key(principal, "plan", profile.id), 404)


@pytest.mark.parametrize("kind,action", [("student", "read"), ("profile", "share"),
    ("PROFILE", "read"), ("profile", "READ"), ("*", "*"), ("profile", "delete")])
def test_unknown_kind_or_action_is_closed(harness, students, kind, action):
    first, _ = students
    resource = harness.owned(first)
    rejected(lambda: harness.authorizer.require_owned(harness.principal(first), kind, resource.id, action), 403)


def test_count_and_page_queries_have_owner_predicate_before_execution(harness, students):
    first, second = students
    harness.owned(first)
    harness.owned(second)
    statements = []

    def capture(_, __, statement, parameters, ___, ____):
        if "auth_owned_resources" in statement.lower() and statement.lstrip().upper().startswith("SELECT"):
            statements.append((statement.lower(), parameters))

    event.listen(harness.engine, "before_cursor_execute", capture)
    try:
        result = harness.authorizer.list_owned(harness.principal(first), "profile", limit=1)
    finally:
        event.remove(harness.engine, "before_cursor_execute", capture)
    assert result.total == 1
    assert len(statements) >= 2
    for statement, parameters in statements:
        assert "where" in statement
        assert "owner_user_id" in statement.partition("where")[2]
        assert first.user_id.hex in str(parameters)
        assert second.user_id.hex not in str(parameters)


@pytest.mark.parametrize("kind", KINDS)
def test_server_registration_derives_owner_and_synthetic_status(harness, students, kind):
    first, second = students
    resource = harness.owned(first, kind)
    assert resource.owner_user_id == first.user_id and resource.is_synthetic is True
    with pytest.raises(TypeError):
        harness.authorizer.register_owned(harness.principal(first), kind, owner_user_id=second.user_id)
    with pytest.raises(TypeError):
        harness.authorizer.register_owned(harness.principal(first), kind, is_synthetic=False)


@pytest.mark.parametrize("kind", ("profile", "plan"))
def test_metadata_touch_versions_are_optimistic_and_owner_checked(harness, students, kind):
    first, second = students
    resource = harness.owned(first, kind)
    principal = harness.principal(first)
    touched = harness.authorizer.touch_owned(principal, kind, resource.id, resource.version)
    assert touched.version == resource.version + 1
    assert touched.owner_user_id == resource.owner_user_id and touched.parent_id == resource.parent_id
    rejected(lambda: harness.authorizer.touch_owned(principal, kind, resource.id, resource.version), 409, "CONFLICT")
    rejected(lambda: harness.authorizer.touch_owned(harness.principal(second), kind, resource.id, touched.version), 404)
    assert harness.authorizer.require_owned(principal, kind, resource.id).version == touched.version


@pytest.mark.parametrize("kind", ("attachment", "export", "job"))
def test_children_require_current_owned_root(harness, students, kind):
    from services.api.app.auth.models import AuthOwnedResource

    first, second = students
    root = harness.owned(first, "plan")
    child = harness.owned(first, kind, parent_id=root.id)
    foreign_root = harness.owned(second)
    principal = harness.principal(first)
    rejected(lambda: harness.authorizer.register_owned(principal, kind, parent_id=foreign_root.id), 404)
    rejected(lambda: harness.authorizer.register_owned(principal, kind, parent_id=child.id), 404)
    with Session(harness.engine) as db, db.begin():
        db.execute(update(AuthOwnedResource).where(AuthOwnedResource.id == root.id).values(status="deleted"))
    rejected(lambda: harness.authorizer.require_owned(principal, kind, child.id), 404)
    assert harness.authorizer.list_owned(principal, kind).total == 0


@pytest.mark.parametrize("change", ("expired", "revoked", "disabled"))
def test_all_owner_access_rechecks_current_session(harness, students, change):
    first, _ = students
    resource = harness.owned(first)
    principal = harness.principal(first)
    with Session(harness.engine) as db, db.begin():
        if change == "disabled":
            db.execute(update(AuthUser).where(AuthUser.id == first.user_id).values(status="disabled"))
        elif change == "revoked":
            db.execute(update(AuthSession).where(AuthSession.id == first.session_id).values(revoked_at=harness.clock[0]))
        else:
            harness.clock[0] = principal.expires_at
    for call in (
        lambda: harness.authorizer.refresh(principal),
        lambda: harness.authorizer.list_owned(principal, "profile"),
        lambda: harness.authorizer.require_owned(principal, "profile", resource.id),
        lambda: harness.authorizer.cache_key(principal, "profile", resource.id),
    ):
        rejected(call, 401)
