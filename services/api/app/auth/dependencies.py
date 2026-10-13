"""Server-only identity and fixed object dependencies for future private routes.

Importing this module does not construct a provider or load persistence. No
client owner, role, or cached Principal participates in authentication.
"""

from uuid import UUID

from fastapi import Depends, Request

from ..api.v2.errors import ApiError
from .config import AuthFlowError
from .router import SESSION_COOKIE, _cookie


def current_principal(request: Request):
    # Mark before any failure so private GET refusals are also never cached.
    request.state.private_access = True
    service = getattr(request.app.state, "identity_service", None)
    if service is None:
        raise ApiError(503, "SERVICE_UNAVAILABLE")
    cookie = _cookie(request, SESSION_COOKIE)
    if cookie is None:
        raise ApiError(401, "UNAUTHORIZED")
    try:
        return service.get_principal(cookie)
    except AuthFlowError as error:
        raise ApiError(error.status_code, error.code) from None


def authorization_service(request: Request):
    request.state.private_access = True
    service = getattr(request.app.state, "authorization_service", None)
    if service is None:
        raise ApiError(503, "SERVICE_UNAVAILABLE")
    return service


def owned_resource(kind: str, action: str = "read", *, resource_param: str = "resource_id"):
    """Bind a server-chosen kind/action to a path UUID, never a request owner.

    This authorizes a read snapshot. Mutation and delayed execution must use
    Authorizer's same-transaction executor again at the point of operation.
    """
    def resolve(request: Request, principal=Depends(current_principal),
                authorizer=Depends(authorization_service)):
        raw_id = request.path_params.get(resource_param)
        try:
            resource_id = raw_id if isinstance(raw_id, UUID) else UUID(raw_id)
        except (ValueError, TypeError, AttributeError):
            raise ApiError(404, "NOT_FOUND") from None
        from .authorization import AuthorizationError
        try:
            return authorizer.require_owned(principal, kind, resource_id, action)
        except AuthorizationError as error:
            raise ApiError(error.status_code, error.code) from None
    return resolve
