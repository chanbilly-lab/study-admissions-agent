"""Server request correlation and small operation wrappers; never raw inputs."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from inspect import signature
import re
from uuid import uuid4

from .schemas import AuditActor

_request = ContextVar("audit_request_id", default=None)
_attempt = ContextVar("audit_attempt", default=None)
_scope = ContextVar("audit_request_scope", default=None)


@dataclass
class RequestScope:
    actor: AuditActor | None = None
    failure_recorded: bool = False
    failure_deferred: bool = False


@contextmanager
def request_context(identifier=None):
    identifier = identifier if identifier is not None else uuid4().hex
    if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{32}", identifier):
        raise ValueError("server request identifier is invalid")
    token = _request.set(identifier)
    scope_token = _scope.set(RequestScope()) if _scope.get() is None else None
    try:
        yield identifier
    finally:
        _request.reset(token)
        if scope_token is not None:
            _scope.reset(scope_token)


def current_request_id():
    return _request.get() or uuid4().hex


def active_request_id():
    return _request.get()


def current_actor():
    scope = _scope.get()
    return scope.actor if scope is not None else None


def failure_handled():
    scope = _scope.get()
    return scope is not None and (scope.failure_recorded or scope.failure_deferred)


def mark_failure_recorded():
    scope = _scope.get()
    if scope is not None:
        scope.failure_recorded = True


@dataclass
class Attempt:
    actor: AuditActor | None = None


def observe_actor(actor):
    value = AuditActor(user_id=actor.user_id, session_id=getattr(actor, "session_id", None),
                       is_synthetic=actor.is_synthetic)
    scope = _scope.get()
    if scope is not None:
        scope.actor = value
    attempt = _attempt.get()
    if attempt is not None:
        attempt.actor = value


def audited(action):
    """Failure recording starts only after the wrapped transaction has exited.

    Caller-owned transactions retain responsibility for their rollback boundary;
    no failure writer is invoked while that supplied Session remains active.
    """
    def decorate(function):
        parameters = signature(function)
        @wraps(function)
        def wrapped(self, *args, **kwargs):
            if _attempt.get() is not None:
                return function(self, *args, **kwargs)
            owner = getattr(self, "auth_service", self)
            store = getattr(owner, "store", None)
            writer = getattr(store, "audit", None) if store is not None else getattr(self, "audit", None)
            attempt = Attempt()
            token = _attempt.set(attempt)
            try:
                with request_context(_request.get()):
                    try:
                        return function(self, *args, **kwargs)
                    except Exception as error:
                        try:
                            bound = parameters.bind(self, *args, **kwargs).arguments
                            supplied = bound.get("session", bound.get("supplied"))
                            active = supplied is not None and callable(getattr(supplied, "in_transaction", None)) and supplied.in_transaction()
                        except Exception:
                            active = True  # An uncertain boundary cannot open another connection.
                        if active and _scope.get() is not None:
                            _scope.get().failure_deferred = True
                        if writer is not None and not active:
                            try:
                                writer.failure(action, error, actor=attempt.actor)
                            except Exception:
                                pass  # A failed diagnostic must never mask the original fixed error.
                        raise
            finally:
                _attempt.reset(token)
        return wrapped
    return decorate
