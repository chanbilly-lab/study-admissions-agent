"""Explicit T08 HTTP profile. Public draft remains database-free when closed."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError

from ..api.v2.errors import ApiError
from ..api.v2.router import ERROR_RESPONSES, REQUEST_ID_HEADER, foundation_meta, no_config_query
from ..api.v2.schemas import Envelope
from ..auth.dependencies import current_principal
from .config import PrivacySettings
from .policy import notice_data
from .schemas import AdmissionData, AgeDeclarationInput, CoreConsentInput, PrivacyNoticeData


router = APIRouter(responses=ERROR_RESPONSES, dependencies=[Depends(no_config_query)])


def privacy_service(request: Request):
    request.state.private_access = True
    service = getattr(request.app.state, "privacy_service", None)
    if service is None:
        raise ApiError(503, "SERVICE_UNAVAILABLE")
    return service


@router.get("/privacy/notices/current", response_model=Envelope[PrivacyNoticeData],
            operation_id="getV2PrivacyNotice", responses={200: {"headers": REQUEST_ID_HEADER}})
def current_notice(request: Request):
    # Never cache draft readiness across server policy changes either.
    request.state.private_access = True
    service = getattr(request.app.state, "privacy_service", None)
    result = service.current_notice() if service is not None else notice_data(
        getattr(request.app.state, "privacy_settings", PrivacySettings()))
    return Envelope(data=result, meta=foundation_meta(request))


@router.get("/me/admission", response_model=Envelope[AdmissionData], operation_id="getV2Admission",
            responses={200: {"headers": REQUEST_ID_HEADER}})
def admission(request: Request, principal=Depends(current_principal), service=Depends(privacy_service)):
    return Envelope(data=service.get_admission(principal), meta=foundation_meta(request))


@router.post("/me/age-declarations", response_model=Envelope[AdmissionData], operation_id="declareV2Age",
             responses={200: {"headers": REQUEST_ID_HEADER}})
def declare_age(request: Request, payload: AgeDeclarationInput, principal=Depends(current_principal),
                service=Depends(privacy_service)):
    return Envelope(data=service.declare_age(principal, payload), meta=foundation_meta(request))


@router.post("/me/consents", response_model=Envelope[AdmissionData], operation_id="confirmV2CoreConsent",
             responses={200: {"headers": REQUEST_ID_HEADER}})
def confirm_core(request: Request, payload: CoreConsentInput, principal=Depends(current_principal),
                 service=Depends(privacy_service)):
    return Envelope(data=service.confirm_core(principal, payload), meta=foundation_meta(request))


@router.delete("/me/consents/{consent_id}", response_model=Envelope[AdmissionData],
               operation_id="withdrawV2CoreConsent", responses={200: {"headers": REQUEST_ID_HEADER}})
async def withdraw_core(request: Request, consent_id: UUID, principal=Depends(current_principal),
                        service=Depends(privacy_service)):
    from starlette.concurrency import run_in_threadpool
    async for chunk in request.stream():
        if chunk:
            raise RequestValidationError([{"type": "extra_forbidden", "loc": ("body",)}])
    result = await run_in_threadpool(service.withdraw_core, principal, consent_id)
    return Envelope(data=result, meta=foundation_meta(request))
