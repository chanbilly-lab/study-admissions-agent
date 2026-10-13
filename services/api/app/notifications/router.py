"""Five explicit private operations; bounded JSON and fixed errors."""
import json
from fastapi import APIRouter,Depends,Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from ..api.v2.errors import ApiError
from ..api.v2.router import ERROR_RESPONSES,foundation_meta
from ..auth.dependencies import current_principal
from ..profiles.router import _body_schema,_call,_id,_unique,_query as profile_query
from ..profiles.schemas import ProfileMeta
from .schemas import (MAX_BODY_BYTES,PreferenceInput,MarkReadInput,NotificationEnvelope,NotificationContextData,
    NotificationPreferenceData,NotificationData,NotificationPage)

REQUEST_MODELS=(PreferenceInput,MarkReadInput)
router=APIRouter(prefix="/notifications",responses=ERROR_RESPONSES)


def _service(request):
    request.state.private_access=True
    service=getattr(request.app.state,"notification_service",None)
    if service is None:
        raise ApiError(503,"SERVICE_UNAVAILABLE")
    return service


def _query(request,*,pagination=False):
    values=profile_query(request,pagination=pagination)
    if pagination and values.get("cursor") is not None and len(values["cursor"])>1024:
        raise ApiError(422,"VALIDATION_ERROR")
    return values


async def _body(request,model,principal):
    await _call(_service(request).preflight,principal)
    _query(request)
    if (len(request.headers.getlist("content-type"))!=1 or request.headers["content-type"].lower()!="application/json"
        or request.headers.getlist("idempotency-key")):
        raise ApiError(422,"VALIDATION_ERROR")
    content=bytearray()
    async for chunk in request.stream():
        if len(content)+len(chunk)>MAX_BODY_BYTES:
            raise ApiError(422,"VALIDATION_ERROR")
        content.extend(chunk)
    try:
        raw=json.loads(bytes(content).decode("utf-8"),object_pairs_hook=_unique,
            parse_constant=lambda value:(_ for _ in ()).throw(ValueError()))
        return model.model_validate(raw)
    except ValidationError as error:
        raise RequestValidationError([{**item,"loc":("body",*item["loc"])} for item in error.errors(include_input=False,include_context=False)]) from None
    except (ValueError,TypeError,UnicodeError,RecursionError):
        raise ApiError(422,"VALIDATION_ERROR") from None


def _response(request,value):
    fields=foundation_meta(request).model_dump()
    if isinstance(value,(NotificationPreferenceData,NotificationData)) and value.profile_version_id is not None:
        fields.update(profile_version_id=value.profile_version_id,profile_mode="synthetic" if value.is_synthetic else "real")
    return NotificationEnvelope(data=value,meta=ProfileMeta.model_validate(fields))


@router.get("/context",response_model=NotificationEnvelope[NotificationContextData],operation_id="getV2NotificationContext")
async def context(request:Request,principal=Depends(current_principal)):
    _query(request)
    service=getattr(request.app.state,"notification_service",None)
    value=(NotificationContextData(schema_version="v2.t36",can_read=False,can_manage_preferences=False,can_mark_read=False,
        is_synthetic=principal.is_synthetic,delivery_channel="in_app",external_delivery_enabled=False) if service is None else await _call(service.context,principal))
    return _response(request,value)


@router.get("/preferences",response_model=NotificationEnvelope[NotificationPreferenceData],operation_id="getV2NotificationPreferences")
async def preferences(request:Request,principal=Depends(current_principal)):
    _query(request)
    return _response(request,await _call(_service(request).get_preferences,principal))


@router.post("/preferences",response_model=NotificationEnvelope[NotificationPreferenceData],operation_id="updateV2NotificationPreferences",openapi_extra=_body_schema(PreferenceInput))
async def update(request:Request,principal=Depends(current_principal)):
    body=await _body(request,PreferenceInput,principal)
    return _response(request,await _call(_service(request).update_preferences,principal,body))


@router.get("",response_model=NotificationEnvelope[NotificationPage],operation_id="listV2Notifications")
async def list_notifications(request:Request,limit:str="20",cursor:str|None=None,principal=Depends(current_principal)):
    values=_query(request,pagination=True)
    return _response(request,await _call(_service(request).list_notifications,principal,**values))


@router.post("/{notification_id}/read",response_model=NotificationEnvelope[NotificationData],operation_id="markV2NotificationRead",openapi_extra=_body_schema(MarkReadInput))
async def read(request:Request,notification_id:str,principal=Depends(current_principal)):
    body=await _body(request,MarkReadInput,principal)
    return _response(request,await _call(_service(request).mark_read,principal,_id(notification_id),body))
