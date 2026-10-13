"""Independent T10 attacks against correlation, redaction and responsibility.

All participants are synthetic. PostgreSQL cases require the T10 dedicated
database fixture; no external provider or real student content is used.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
import logging
import os
from pathlib import Path
from threading import Barrier
from threading import Event
from time import monotonic
from uuid import uuid4

from pydantic import ValidationError
import pytest
import httpx
from sqlalchemy import event as sql_event, select, text
from sqlalchemy.orm import Session

from services.api.app.audit.context import audited, current_request_id, request_context
from services.api.app.audit.retention import LOG_MAX_DAYS, expires_after_months
from services.api.app.audit.schemas import AuditActor, AuditEventData, AuditEventInput, POLICY_VERSION
from services.api.app.auth.authorization import AuthorizationError
from services.api.app.auth.authorization import Authorizer
from services.api.app.auth.assurance import AdminAssurancePolicy
from services.api.app.auth.config import AuthFlowError
from services.api.app.auth.models import AuthIdentity, AuthOwnedResource, AuthSession, AuthUser, AuthUserRole, LoginTransaction
from services.api.app.auth.oidc import KeycloakOidcAdapter
from services.api.app.auth.service import AuthService
from services.api.app.audit.models import AuditEvent
from services.api.app.audit.service import AuditService
from services.api.app.privacy.schemas import AgeDeclarationInput, CoreConsentInput
from services.api.app.audit.logging import CONFIGURED_LOGGERS, SafeLogEvent, SafeLogFormatter, configure_logging, emit, purge_log_files


SENTINEL = "T10_SYNTHETIC_STUDENT_TOKEN_PROMPT_SECRET"
NOW = datetime(2024, 2, 29, 12, 34, 56, tzinfo=timezone.utc)


def successful_event(**changes):
    values = dict(action="authorization.owned.check", outcome="succeeded", reason_code="OK",
        object_type="profile", object_id=uuid4(), object_version=1)
    values.update(changes)
    return values


def complete_event(**changes):
    values = dict(**successful_event(), id=uuid4(), occurred_at=NOW, actor_kind="anonymous",
        actor_user_id=None, actor_session_id=None, request_id="a" * 32, is_synthetic=True,
        policy_version=POLICY_VERSION, expires_at=expires_after_months(NOW))
    values.update(changes)
    return values


@pytest.mark.parametrize("action", [SENTINEL, "GET /profiles/private?token=" + SENTINEL,
    "authorization.*", "student.chat", "catalog.delete_all", "", "auth.login.start\n" + SENTINEL])
def test_action_never_becomes_free_text_or_implicit_business_event(action):
    with pytest.raises(ValidationError) as rejected:
        AuditEventInput(**successful_event(action=action))
    assert SENTINEL not in str(rejected.value) and SENTINEL not in repr(rejected.value)


@pytest.mark.parametrize("field", ["actor", "actor_user_id", "session_id", "owner_user_id", "roles", "issuer", "subject",
    "email", "ip", "user_agent", "headers", "query", "body", "payload", "exception", "prompt", "score", "filename"])
def test_event_input_rejects_request_actor_and_sensitive_storage_fields(field):
    with pytest.raises(ValidationError) as rejected:
        AuditEventInput(**{**successful_event(), field: SENTINEL})
    assert SENTINEL not in str(rejected.value) and SENTINEL not in repr(rejected.value)


@pytest.mark.parametrize("outcome", ["denied", "failed"])
@pytest.mark.parametrize("changes", [dict(object_id=uuid4(), object_type="profile"),
    dict(object_id=uuid4(), object_type="attachment", object_version=1),
    dict(object_version=1)])
def test_failure_events_cannot_retain_requested_or_foreign_object_identity(outcome, changes):
    with pytest.raises(ValidationError):
        AuditEventInput(action="authorization.owned.check", outcome=outcome, reason_code="NOT_FOUND", **changes)


@pytest.mark.parametrize("outcome,reason", [("succeeded", "NOT_FOUND"), ("succeeded", "INTERNAL_ERROR"),
    ("denied", "OK"), ("failed", "OK"), ("success", "OK"), ("denied", SENTINEL)])
def test_outcome_and_fixed_reason_cannot_forge_success_or_store_exception(outcome, reason):
    with pytest.raises(ValidationError):
        AuditEventInput(action="authorization.owned.check", outcome=outcome, reason_code=reason)


@pytest.mark.parametrize("value", [True, False, "1", 1.0, 0, -1])
def test_object_version_is_positive_strict_integer(value):
    with pytest.raises(ValidationError):
        AuditEventInput(**successful_event(object_version=value))


@pytest.mark.parametrize("changes", [dict(object_type=SENTINEL), dict(object_type=None),
    dict(object_id=None, object_version=1)])
def test_object_reference_requires_closed_type_and_complete_version_reference(changes):
    with pytest.raises(ValidationError):
        AuditEventInput(**successful_event(**changes))


@pytest.mark.parametrize("forgery", ["copy", "construct"])
@pytest.mark.parametrize("changes", [dict(action=SENTINEL), dict(outcome="denied", reason_code="NOT_FOUND"),
    dict(object_version=True), dict(reason_code=SENTINEL)])
def test_event_instances_are_revalidated_at_service_boundary(forgery, changes):
    event = AuditEventInput(**successful_event())
    forged = event.model_copy(update=changes) if forgery == "copy" else AuditEventInput.model_construct(
        **{**event.model_dump(), **changes})
    with pytest.raises(ValidationError):
        AuditEventInput.model_validate(forged)


@pytest.mark.parametrize("changes", [dict(actor_kind="anonymous", actor_user_id=uuid4()),
    dict(actor_kind="system", actor_user_id=uuid4()), dict(actor_kind="system", actor_session_id=uuid4()),
    dict(actor_kind="user", actor_user_id=None), dict(actor_kind="guardian"), dict(is_synthetic=1),
    dict(is_synthetic="true"), dict(request_id="CLIENT-" + SENTINEL), dict(policy_version="unreviewed"),
    dict(expires_at=NOW), dict(expires_at=NOW - timedelta(seconds=1))])
def test_stored_event_rejects_inconsistent_actor_correlation_and_infinite_retention(changes):
    with pytest.raises(ValidationError):
        AuditEventData(**complete_event(**changes))


@pytest.mark.parametrize("value", [1, "true", None])
def test_actor_synthetic_marker_is_not_a_coercible_request_verified_claim(value):
    with pytest.raises(ValidationError):
        AuditActor(user_id=uuid4(), session_id=None, is_synthetic=value)


@pytest.mark.parametrize("identifier", [SENTINEL, "a" * 31, "a" * 33, "A" * 32, "z" * 32,
    "a" * 32 + "\n", True, 123])
def test_context_refuses_arbitrary_correlation_content(identifier):
    with pytest.raises(ValueError) as rejected:
        with request_context(identifier):
            pytest.fail("untrusted context was entered")
    assert SENTINEL not in str(rejected.value)


def test_context_is_nested_exception_safe_and_thread_local():
    barrier = Barrier(2)
    def separate(identifier):
        with request_context(identifier):
            barrier.wait(timeout=5)
            with request_context("c" * 32):
                assert current_request_id() == "c" * 32
            return current_request_id()
    with request_context("d" * 32):
        with pytest.raises(RuntimeError):
            with request_context("e" * 32):
                raise RuntimeError(SENTINEL)
        assert current_request_id() == "d" * 32
        with ThreadPoolExecutor(max_workers=2) as pool:
            one, two = [pool.submit(separate, value * 32) for value in ("a", "b")]
            assert [one.result(timeout=8), two.result(timeout=8)] == ["a" * 32, "b" * 32]
        assert current_request_id() == "d" * 32
    assert current_request_id() not in {"d" * 32, "e" * 32}


@pytest.mark.parametrize("start,months,expected", [
    (datetime(2024, 2, 29, 12, 34, 56, tzinfo=timezone.utc), 24, datetime(2026, 2, 28, 12, 34, 56, tzinfo=timezone.utc)),
    (datetime(2024, 1, 31, 23, 59, 59, tzinfo=timezone.utc), 1, datetime(2024, 2, 29, 23, 59, 59, tzinfo=timezone.utc)),
    (datetime(2023, 1, 31, tzinfo=timezone.utc), 1, datetime(2023, 2, 28, tzinfo=timezone.utc)),
    (datetime(2024, 3, 31, tzinfo=timezone.utc), 1, datetime(2024, 4, 30, tzinfo=timezone.utc)),
    (datetime(2024, 2, 29, 0, 30, tzinfo=timezone(timedelta(hours=8))), 24,
        datetime(2026, 2, 28, 16, 30, tzinfo=timezone.utc)),
])
def test_retention_uses_real_utc_calendar_months_and_clamps_month_end(start, months, expected):
    assert expires_after_months(start, months) == expected
    assert LOG_MAX_DAYS == 30


@pytest.mark.parametrize("months", [True, False, 0, -1, 25, 720, 24.0, "24", None])
def test_retention_cannot_exceed_product_upper_bound_or_coerce_units(months):
    with pytest.raises(ValueError):
        expires_after_months(NOW, months)


@pytest.mark.parametrize("value", [datetime(2024, 2, 29), "2024-02-29", 1709208000, None])
def test_retention_requires_an_explicit_aware_instant(value):
    with pytest.raises(ValueError):
        expires_after_months(value)


@pytest.mark.parametrize("passing", ["positional", "keyword"])
def test_failure_audit_never_runs_inside_caller_owned_active_transaction(passing):
    calls = []
    class Writer:
        def failure(self, *args, **kwargs):
            calls.append(True)
    class Service:
        audit = Writer()
        @audited("authorization.owned.execute")
        def guarded(self, session):
            assert session.in_transaction()
            raise AuthorizationError(403)
    # No engine is required to prove root transaction lifetime; no DB/network.
    with Session() as transaction, transaction.begin():
        with pytest.raises(AuthorizationError) as denied:
            if passing == "positional":
                Service().guarded(transaction)
            else:
                Service().guarded(session=transaction)
        assert denied.value.status_code == 403
        assert calls == [], "failure writer ran before caller released its root transaction"


@pytest.fixture
def configured_output():
    old = {name: (logging.getLogger(name).handlers[:], logging.getLogger(name).propagate,
        logging.getLogger(name).level, logging.getLogger(name).disabled) for name in CONFIGURED_LOGGERS}
    stream = StringIO()
    handler = configure_logging(stream)
    for name in CONFIGURED_LOGGERS:
        logging.getLogger(name).setLevel(logging.DEBUG)
    try:
        yield stream
    finally:
        for name, (handlers, propagate, level, disabled) in old.items():
            logger = logging.getLogger(name)
            logger.handlers, logger.propagate = handlers, propagate
            logger.setLevel(level)
            logger.disabled = disabled
        handler.close()


@pytest.mark.parametrize("name", ["admissions", "uvicorn.access", "uvicorn.error", "httpx", "httpcore",
    "sqlalchemy.engine", "sqlalchemy.pool", "fastapi", "starlette"])
def test_configured_handler_drops_sensitive_message_exception_and_custom_extras(configured_output, name):
    try:
        raise RuntimeError("private traceback: " + SENTINEL)
    except RuntimeError:
        with request_context("f" * 32):
            logging.getLogger(name).error("Authorization: Bearer %s /auth/callback?code=%s score=750 %s",
                SENTINEL, SENTINEL, SENTINEL, exc_info=True, stack_info=True,
                extra={"headers": SENTINEL, "body": {"prompt": SENTINEL}, "query": SENTINEL,
                    "filename_private": SENTINEL, "student_score": SENTINEL})
    output = configured_output.getvalue()
    assert SENTINEL not in output and "Traceback" not in output and "Authorization" not in output
    event = json.loads(output)
    assert event == dict(operation_id="runtime.message", request_id="f" * 32,
        status=None, reason_code=None, duration_ms=None)


def test_formatter_never_calls_unsafe_message_stringification(configured_output):
    class ExplodingMessage:
        def __str__(self):
            raise AssertionError("formatter evaluated private message " + SENTINEL)
    with request_context("b" * 32):
        logging.getLogger("uvicorn.error").error(ExplodingMessage())
        record = logging.LogRecord("sqlalchemy.engine", logging.ERROR, SENTINEL, 9,
            ExplodingMessage(), (SENTINEL,), None)
        raw = SafeLogFormatter().format(record)
    assert SENTINEL not in raw + configured_output.getvalue()
    assert json.loads(raw)["request_id"] == "b" * 32


@pytest.mark.parametrize("changes", [dict(operation_id=SENTINEL), dict(request_id=SENTINEL),
    dict(status=True), dict(status=600), dict(reason_code=SENTINEL), dict(duration_ms=-1),
    dict(duration_ms=float("nan")), dict(payload=SENTINEL)])
def test_malformed_safe_extra_never_extends_closed_output(configured_output, changes):
    candidate = dict(operation_id="request.failed", request_id="c" * 32, status=403,
        reason_code="FORBIDDEN", duration_ms=2)
    with request_context("d" * 32):
        logging.getLogger("httpx").warning(SENTINEL, extra={"safe_event": {**candidate, **changes}})
    output = configured_output.getvalue()
    assert SENTINEL not in output
    assert json.loads(output)["operation_id"] == "runtime.message"
    assert json.loads(output)["request_id"] == "d" * 32


def test_safe_operation_still_preserves_fixed_failure_and_server_correlation(configured_output):
    with request_context("e" * 32):
        emit("request.failed", status=403, reason_code="FORBIDDEN", duration_ms=7)
    assert json.loads(configured_output.getvalue()) == dict(operation_id="request.failed", request_id="e" * 32,
        status=403, reason_code="FORBIDDEN", duration_ms=7)


def test_log_cleanup_is_explicit_bounded_and_preserves_unknown_and_nested_files(tmp_path):
    now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    cutoff = now - timedelta(days=30)
    for name, stamp in [("admissions-2026-09-01.jsonl", cutoff - timedelta(seconds=1)),
                        ("admissions-2026-09-02.jsonl", cutoff),
                        ("admissions-2026-09-04.jsonl", now),
                        ("student-attachment.jsonl", cutoff - timedelta(days=1))]:
        path = tmp_path / name
        path.write_text(SENTINEL, encoding="utf-8")
        os.utime(path, (stamp.timestamp(), stamp.timestamp()))
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "admissions-2026-09-01.jsonl").write_text(SENTINEL, encoding="utf-8")
    assert purge_log_files(tmp_path, now=now, limit=1) == 1
    assert not (tmp_path / "admissions-2026-09-01.jsonl").exists()
    assert (tmp_path / "admissions-2026-09-02.jsonl").exists()
    assert purge_log_files(tmp_path, now=now, limit=1) == 1
    assert (tmp_path / "admissions-2026-09-04.jsonl").exists()
    assert (tmp_path / "student-attachment.jsonl").read_text(encoding="utf-8") == SENTINEL
    assert (nested / "admissions-2026-09-01.jsonl").exists()


@pytest.mark.parametrize("limit", [True, 0, -1, 1001, "1", 1.0])
def test_log_cleanup_rejects_unbounded_or_coercible_batches(tmp_path, limit):
    with pytest.raises(ValueError):
        purge_log_files(tmp_path, now=NOW, limit=limit)


def test_failure_writer_exception_does_not_mask_original_fixed_error():
    class Writer:
        def failure(self, *args, **kwargs):
            raise RuntimeError(SENTINEL)
    class Service:
        audit = Writer()
        @audited("authorization.owned.check")
        def denied(self):
            raise AuthorizationError(404)
    with pytest.raises(AuthorizationError) as error:
        Service().denied()
    assert error.value.status_code == 404
    assert SENTINEL not in str(error.value) and SENTINEL not in repr(error.value)


def test_valid_foreign_extra_request_id_cannot_replace_server_correlation(configured_output):
    supplied = dict(operation_id="request.failed", request_id="b" * 32,
        status=403, reason_code="FORBIDDEN", duration_ms=1)
    with request_context("a" * 32):
        for event in (supplied, SafeLogEvent(**supplied)):
            logging.getLogger("httpx").error(SENTINEL, extra={"safe_event": event})
    outputs = [json.loads(line) for line in configured_output.getvalue().splitlines()]
    assert len(outputs) == 2
    assert all(item["request_id"] == "a" * 32 for item in outputs)
    assert all(item["operation_id"] == "request.failed" for item in outputs)
    assert SENTINEL not in configured_output.getvalue()


def test_touching_old_log_mtime_cannot_extend_canonical_daily_retention(tmp_path):
    now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    expired = tmp_path / "admissions-2026-08-01.jsonl"
    expired.write_text(SENTINEL, encoding="utf-8")
    os.utime(expired, (now.timestamp(), now.timestamp()))
    assert purge_log_files(tmp_path, now=now, limit=1) == 1
    assert not expired.exists()


def test_log_cleanup_scan_budget_includes_nonmatching_entries(tmp_path, monkeypatch):
    now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    untouched = tmp_path / "unknown-user-file.txt"
    untouched.write_text(SENTINEL, encoding="utf-8")
    expired = tmp_path / "admissions-2026-08-01.jsonl"
    expired.write_text(SENTINEL, encoding="utf-8")
    scanned = []
    original = Path.iterdir
    def observed_entries():
        for i in range(3):
            scanned.append(i)
            yield untouched
        raise AssertionError("cleanup exhausted its scan budget before finding a log")
    def bounded_iterator(directory):
        return observed_entries() if directory == tmp_path else original(directory)
    monkeypatch.setattr(Path, "iterdir", bounded_iterator)
    assert purge_log_files(tmp_path, now=now, limit=1, scan_limit=3) == 0
    assert scanned == [0, 1, 2]
    assert expired.exists() and untouched.read_text(encoding="utf-8") == SENTINEL


def test_outside_request_cannot_trust_private_extra_as_server_request_id(configured_output, capfd):
    foreign = "b" * 32
    for identifier in (SENTINEL, foreign):
        logging.getLogger("httpx").error("private payload %s", SENTINEL,
            extra={"_audit_server_request_id": identifier})
    captured = capfd.readouterr()
    rendered = configured_output.getvalue()
    assert SENTINEL not in rendered + captured.out + captured.err
    events = [json.loads(line) for line in rendered.splitlines()]
    assert len(events) == 2
    assert all(event["request_id"] != foreign and len(event["request_id"]) == 32 for event in events)


def stored_events(engine, action=None):
    with Session(engine) as session:
        query = select(AuditEvent)
        if action is not None:
            query = query.where(AuditEvent.action == action)
        return [{column.name: getattr(row, column.name) for column in AuditEvent.__table__.columns}
            for row in session.scalars(query).all()]


def assert_denied(call, code):
    with pytest.raises(AuthFlowError) as error:
        call()
    assert error.value.status_code == code
    assert SENTINEL not in str(error.value) and SENTINEL not in repr(error.value)


@pytest.fixture
def operator(auth_store, session_settings_factory, runtime, clock, actor_factory, pg_engine):
    """Trusted synthetic DB provenance fixture, not a new JWT-verification claim."""
    base = session_settings_factory()
    provider = base.provider.model_copy(update={"client_id": "T10_OPERATOR_CLIENT"})
    policy = AdminAssurancePolicy(enabled=True, trusted_issuer=provider.issuer,
        admin_client_id=provider.client_id, student_client_id="T10_STUDENT_CLIENT",
        allowed_acr=("T10_TEST_MFA",), required_amr=("pwd", "otp"), max_auth_age_seconds=60)
    settings = base.model_copy(update={"provider": provider, "admin_assurance_policy": policy})
    def forbidden_io(request):
        raise AssertionError("audit operator must not call a provider")
    adapter = KeycloakOidcAdapter(settings, runtime, transport=httpx.MockTransport(forbidden_io))
    service = AuthService(settings, runtime, auth_store, adapter, clock=clock)
    actor = actor_factory(role="operations")
    with Session(pg_engine) as session, session.begin():
        row = session.get(AuthSession, actor.session_id)
        row.verified_issuer, row.verified_client_id = provider.issuer, provider.client_id
        row.assurance_acr, row.assurance_amr, row.assurance_auth_time = "T10_TEST_MFA", ["pwd", "otp"], clock()
    return service, AuditService(service), actor


@pytest.mark.postgres
@pytest.mark.parametrize("target", ["missing", "foreign"])
def test_actual_denial_records_verified_actor_but_no_requested_object(pg_engine, auth_service, actor_factory,
        resource_factory, target):
    owner, requester = actor_factory(), actor_factory()
    resource = resource_factory(owner)
    reference = resource.id if target == "foreign" else uuid4()
    principal = auth_service.get_principal(requester.cookie)
    with request_context("f" * 32):
        assert_denied(lambda: Authorizer(auth_service).require_owned(principal, "profile", reference), 404)
    failures = [row for row in stored_events(pg_engine, "authorization.owned.check") if row["outcome"] == "denied"]
    assert len(failures) == 1
    failure = failures[0]
    assert failure["actor_kind"] == "user" and failure["actor_user_id"] == requester.user_id
    assert failure["actor_session_id"] == requester.session_id and failure["request_id"] == "f" * 32
    assert failure["object_id"] is None and failure["object_version"] is None
    assert failure["reason_code"] == "NOT_FOUND"
    assert SENTINEL not in repr(stored_events(pg_engine))


@pytest.mark.postgres
def test_principal_roles_in_request_reference_do_not_grant_audit_reader_access(audit_service, auth_service,
        actor_factory, pg_engine):
    actor = actor_factory()
    principal = auth_service.get_principal(actor.cookie)
    forged = principal.model_copy(update={"roles": ("operations",), "authorization_context": "a" * 64})
    assert_denied(lambda: audit_service.list_events(forged), 403)
    failures = [r for r in stored_events(pg_engine, "audit.read") if r["outcome"] == "denied"]
    assert failures and failures[-1]["actor_user_id"] == actor.user_id


@pytest.mark.postgres
@pytest.mark.parametrize("action", ["role", "object", "consent", "grant", "logout"])
def test_required_audit_insert_failure_rolls_back_real_business_write(pg_engine, auth_service, audit_writer,
        actor_factory, admitted_actor_factory, resource_factory, privacy_service, sharing_service,
        create_request_factory, clock, action):
    owner = admitted_actor_factory() if action == "grant" else actor_factory()
    principal = auth_service.get_principal(owner.cookie)
    desired = {"role": "auth.role.assign", "object": "authorization.owned.execute",
        "consent": "privacy.core.confirm", "grant": "sharing.grant.create", "logout": "auth.logout"}[action]
    if action == "object":
        resource = resource_factory(owner)
    elif action == "consent":
        current = privacy_service.get_admission(principal)
        privacy_service.declare_age(principal, AgeDeclarationInput(age_band="18_plus", confirmed=True,
            notice_id=current.notice_id, expected_revision=current.revision))
        before = privacy_service.get_admission(principal)
    elif action == "grant":
        recipient = admitted_actor_factory(role=None)
        resource = resource_factory(owner)
        request = create_request_factory(owner, recipient, resource)
    elif action == "logout":
        token = auth_service.get_csrf_token(owner.cookie).token
    existing_success_ids = {row["id"] for row in stored_events(pg_engine, desired) if row["outcome"] == "succeeded"}
    def database_fault(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().startswith("INSERT INTO auth_audit_events") and parameters.get("action") == desired:
            raise RuntimeError(SENTINEL)
    sql_event.listen(pg_engine, "before_cursor_execute", database_fault)
    try:
        if action == "role":
            operation = lambda: auth_service.store.assign_role(owner.user_id, "operations", now=clock())
        elif action == "object":
            operation = lambda: Authorizer(auth_service).touch_owned(principal, "profile", resource.id, 1)
        elif action == "consent":
            operation = lambda: privacy_service.confirm_core(principal, CoreConsentInput(purpose="core_consultation",
                confirmed=True, notice_id=before.notice_id, expected_revision=before.revision))
        elif action == "grant":
            operation = lambda: sharing_service.create_grant(principal, request)
        else:
            operation = lambda: auth_service.logout(owner.cookie, token)
        assert_denied(operation, 503)
    finally:
        sql_event.remove(pg_engine, "before_cursor_execute", database_fault)
    with Session(pg_engine) as session:
        if action == "role":
            assert session.get(AuthUserRole, (owner.user_id, "operations")) is None
        elif action == "object":
            assert session.get(AuthOwnedResource, resource.id).version == 1
        elif action == "logout":
            assert session.get(AuthSession, owner.session_id).revoked_at is None
    if action == "consent":
        after = privacy_service.get_admission(principal)
        assert after.revision == before.revision and after.consent_id is None
    elif action == "grant":
        assert sharing_service.list_grants(principal).revision == 0
        assert sharing_service.list_grants(principal).items == [] or sharing_service.list_grants(principal).items == ()
    assert {row["id"] for row in stored_events(pg_engine, desired) if row["outcome"] == "succeeded"} == existing_success_ids


@pytest.mark.postgres
def test_callback_failure_rolls_back_then_records_failure_after_account_lock_release(auth_service, actor_factory,
        resource_factory, audit_writer, pg_engine, monkeypatch):
    actor = actor_factory()
    resource = resource_factory(actor)
    principal = auth_service.get_principal(actor.cookie)
    original = audit_writer.failure
    observed = []
    def after_transaction(action, error, **kwargs):
        with pg_engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout = '1000ms'"))
            connection.execute(select(AuthUser).where(AuthUser.id == actor.user_id).with_for_update())
            observed.append(action)
        return original(action, error, **kwargs)
    monkeypatch.setattr(audit_writer, "failure", after_transaction)
    def rollback(session, current, value):
        session.get(AuthOwnedResource, resource.id).status = "deleted"
        session.flush()
        raise AuthorizationError(403)
    assert_denied(lambda: Authorizer(auth_service).execute_owned(principal, "profile", resource.id, "write", rollback), 403)
    assert observed == ["authorization.owned.execute"]
    with Session(pg_engine) as session:
        assert session.get(AuthOwnedResource, resource.id).status == "active"
    failures = [r for r in stored_events(pg_engine, "authorization.owned.execute") if r["outcome"] == "denied"]
    assert len(failures) == 1 and failures[0]["object_id"] is None


@pytest.mark.postgres
def test_success_event_commits_with_object_and_is_not_permission_credential(auth_service, actor_factory,
        resource_factory, pg_engine):
    actor = actor_factory()
    resource = resource_factory(actor)
    with request_context("d" * 32):
        current = auth_service.get_principal(actor.cookie)
        updated = Authorizer(auth_service).touch_owned(current, "profile", resource.id, 1)
    successes = [row for row in stored_events(pg_engine, "authorization.owned.execute") if row["outcome"] == "succeeded"]
    assert len(successes) == 1
    record = successes[0]
    assert record["actor_user_id"] == actor.user_id and record["object_id"] == resource.id
    assert record["object_version"] == updated.version == 2 and record["request_id"] == "d" * 32
    assert_denied(lambda: Authorizer(auth_service).require_owned(record, "profile", resource.id), 401)


@pytest.mark.postgres
@pytest.mark.parametrize("change", ["role_revoked", "session_revoked", "assurance_missing", "wrong_client", "disabled_policy"])
def test_audit_operator_reads_revalidate_current_role_session_provenance_and_policy(operator, pg_engine, clock, change):
    service, audit, actor = operator
    current = service.get_principal(actor.cookie)
    assert audit.list_events(current).items
    if change == "disabled_policy":
        service.settings = service.settings.model_copy(update={"admin_assurance_policy": AdminAssurancePolicy()})
    elif change == "role_revoked":
        service.store.revoke_role(actor.user_id, "operations", now=clock())
    else:
        with Session(pg_engine) as session, session.begin():
            row = session.get(AuthSession, actor.session_id)
            if change == "session_revoked":
                row.revoked_at = clock()
            elif change == "wrong_client":
                row.verified_client_id = "T10_STUDENT_CLIENT"
            else:
                row.assurance_acr = None
    assert_denied(lambda: audit.list_events(current), 401 if change == "session_revoked" else 403)
    assert_denied(lambda: audit.purge_expired(current), 401 if change == "session_revoked" else 403)


@pytest.mark.postgres
def test_explicit_audit_cleanup_is_bounded_at_inclusive_expiry(operator, pg_engine, clock, audit_writer):
    service, audit, actor = operator
    current = service.get_principal(actor.cookie)
    ids = [uuid4() for _ in range(3)]
    with Session(pg_engine) as session, session.begin():
        for i, identifier in enumerate(ids):
            values = complete_event(id=identifier, occurred_at=clock() - timedelta(days=1),
                expires_at=clock() + timedelta(seconds=i - 1))
            session.add(AuditEvent(**values))
    assert audit.purge_expired(current, limit=1) == 1
    with Session(pg_engine) as session:
        assert sum(session.get(AuditEvent, identifier) is not None for identifier in ids[:2]) == 1
        assert session.get(AuditEvent, ids[2]) is not None
    assert audit.purge_expired(current, limit=1) == 1
    page = audit.list_events(current, limit=100)
    assert ids[0] not in {item.id for item in page.items} and ids[1] not in {item.id for item in page.items}
    assert ids[2] in {item.id for item in page.items}


def wait_for_audit_table_lock(engine, started, blocker_pid):
    assert started.wait(5)
    deadline = monotonic() + 8
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        while monotonic() < deadline:
            # Statistics must be fresh on each poll, not one transaction's snapshot.
            connection.execute(text("SELECT pg_stat_clear_snapshot()"))
            waiting = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                "AND wait_event_type='Lock' AND :blocker=ANY(pg_blocking_pids(pid)) "
                "AND query ILIKE '%auth_audit_events%'"), {"blocker": blocker_pid})
            if waiting:
                return
            started.wait(0.01)
    pytest.fail("No actual PostgreSQL audit INSERT/DELETE lock wait observed")


@pytest.mark.postgres
@pytest.mark.parametrize("operation", ["read", "purge"])
@pytest.mark.parametrize("expiry", ["session", "role", "assurance"])
def test_pg_audit_io_lock_wait_rechecks_operator_expiry_and_rolls_back(operator, pg_engine, clock, operation, expiry):
    service, audit, actor = operator
    current = service.get_principal(actor.cookie)
    old_id = uuid4()
    with Session(pg_engine) as session, session.begin():
        session.add(AuditEvent(**complete_event(id=old_id, occurred_at=clock() - timedelta(days=1),
            expires_at=clock() - timedelta(seconds=1))))
        if expiry == "session":
            session.get(AuthSession, actor.session_id).expires_at = clock() + timedelta(seconds=5)
        elif expiry == "role":
            session.get(AuthUserRole, (actor.user_id, "operations")).expires_at = clock() + timedelta(seconds=5)
    started = Event()
    def waiting_operation():
        started.set()
        return audit.list_events(current) if operation == "read" else audit.purge_expired(current)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pg_engine.begin() as blocker:
            blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
            blocker.execute(text("LOCK TABLE auth_audit_events IN SHARE MODE"))
            future = pool.submit(waiting_operation)
            wait_for_audit_table_lock(pg_engine, started, blocker_pid)
            clock.advance(61 if expiry == "assurance" else 5)
        assert_denied(lambda: future.result(timeout=8), 401 if expiry == "session" else 403)
    with Session(pg_engine) as session:
        assert session.get(AuditEvent, old_id) is not None, "expired deletion committed after operator authority expired"
    records = stored_events(pg_engine, "audit.read" if operation == "read" else "audit.purge")
    assert not [row for row in records if row["outcome"] == "succeeded"]
    assert [row for row in records if row["outcome"] == "denied"]


@pytest.mark.postgres
@pytest.mark.parametrize("stage,advance", [("consume", 300), ("complete", 300), ("complete", 3600)])
def test_real_signed_login_audit_wait_never_mints_session_after_deadline(auth_service, pg_engine,
        idp, clock, audit_writer, monkeypatch, stage, advance):
    """Real RS256/PKCE exchange stays offline; only the audit I/O time advances."""
    user_id = uuid4()
    subject = "T10_SYNTHETIC_LOGIN_AUDIT_WAIT"
    with Session(pg_engine) as session, session.begin():
        session.add(AuthUser(id=user_id, status="active", is_synthetic=True, created_at=clock()))
        session.flush()
        session.add(AuthIdentity(id=uuid4(), user_id=user_id,
            issuer=auth_service.settings.provider.issuer, subject=subject, created_at=clock()))
    login = auth_service.start_login()
    code, state = idp.issue_from_authorization(login.authorization_url.get_secret_value(), subject)
    original = audit_writer.success
    observed = []
    target = "auth.login.consume" if stage == "consume" else "auth.login.complete"
    def slow_required_audit(session, action, **kwargs):
        result = original(session, action, **kwargs)
        if action == target:
            # The pending real PG row must roll back if this final flush consumes
            # the login deadline or the absolute session lifetime.
            assert session.in_transaction()
            observed.append(action)
            clock.advance(advance)
        return result
    monkeypatch.setattr(audit_writer, "success", slow_required_audit)
    assert_denied(lambda: auth_service.complete_login(code, state, login.browser_binding), 401)
    assert observed == [target]
    with Session(pg_engine) as session:
        assert session.scalars(select(AuthSession).where(AuthSession.user_id == user_id)).all() == []
        transaction = session.scalars(select(LoginTransaction)).one()
        assert transaction.consumed_at is not None and transaction.encrypted_context is None
    assert not [row for row in stored_events(pg_engine, "auth.login.complete") if row["outcome"] == "succeeded"]
    if stage == "consume":
        assert idp.requests == [], "already expired context was sent to the token endpoint"
    else:
        assert len(idp.requests) == 2 and idp.last_token is not None
