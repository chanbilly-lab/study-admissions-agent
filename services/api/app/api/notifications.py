"""Independent closed T36 factory, inheriting all frozen private contracts."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool
from ..audit.context import current_actor,failure_handled,request_context
from ..auth.config import AuthFlowError
from ..notifications.router import REQUEST_MODELS,router
from ..settings import V2RuntimeSettings
from .revisions import create_revisions_v2_app
from .v2.errors import ApiError,STATUS_CODES,error_response,request_id


def create_notifications_v2_app(settings:V2RuntimeSettings|None=None,*,identity_service=None,profile_service=None,
    assessment_service=None,execution_service=None,revision_service=None,notification_service=None):
    runtime=V2RuntimeSettings.model_validate(settings) if settings is not None else V2RuntimeSettings()
    if notification_service is not None:
        from ..notifications.service import NotificationService
        if (not isinstance(notification_service,NotificationService) or notification_service.profile_service is not profile_service
            or notification_service.auth_service is not identity_service):
            raise AuthFlowError(503,"SERVICE_UNAVAILABLE")
        notification_service._validate()
    app=create_revisions_v2_app(runtime,identity_service=identity_service,profile_service=profile_service,
        assessment_service=assessment_service,execution_service=execution_service,revision_service=revision_service)
    app.title,app.version="升学咨询 T36 in-app notifications","v2.t36"
    app.state.notification_service=notification_service
    app.include_router(router)
    if notification_service is not None:
        previous=app.router.lifespan_context
        @asynccontextmanager
        async def lifespan(application):
            async with previous(application):
                await run_in_threadpool(notification_service.store.assert_schema_ready)
                yield
        app.router.lifespan_context=lifespan

    @app.middleware("http")
    async def notification_context(request,call_next):
        path=request.scope["path"].removeprefix(request.scope.get("root_path",""))
        if path!="/notifications" and not path.startswith("/notifications/"):
            return await call_next(request)
        with request_context(request_id(request)):
            try:
                response=await call_next(request)
            except Exception:
                response=error_response(request,500,"INTERNAL_ERROR")
            if response.status_code>=400 and identity_service is not None and not failure_handled():
                status=response.status_code if response.status_code in STATUS_CODES else 500
                try:
                    await run_in_threadpool(identity_service.store.audit.failure,"authorization.owned.check",
                        ApiError(status,STATUS_CODES[status]),actor=current_actor())
                except Exception:
                    pass
            response.headers.update({"Cache-Control":"no-store","Pragma":"no-cache","Referrer-Policy":"no-referrer"})
            return response

    original=app.openapi
    def notifications_openapi():
        document=original()
        components=document.setdefault("components",{}).setdefault("schemas",{})
        for model in REQUEST_MODELS:
            definition=model.model_json_schema(ref_template="#/components/schemas/{model}")
            components.update(definition.pop("$defs",{}));components[model.__name__]=definition
        for path,operations in document["paths"].items():
            if path!="/notifications" and not path.startswith("/notifications/"):
                continue
            for method,operation in operations.items():
                if method not in {"get","post"}:
                    continue
                security={"SessionCookie":[]}
                if method=="post":
                    security.update({"CsrfHeader":[],"RequestOrigin":[]})
                operation["security"]=[security]
                for parameter in operation.get("parameters",[]):
                    if parameter.get("in")=="path" and parameter.get("name")=="notification_id":
                        parameter["schema"]={"type":"string","format":"uuid"}
                    if parameter.get("in")=="query" and parameter.get("name")=="cursor":
                        parameter["schema"]={"type":"string","minLength":1,"maxLength":1024}
                    if parameter.get("in")=="query" and parameter.get("name")=="limit":
                        parameter["schema"]={"type":"integer","minimum":1,"maximum":20,"default":20}
        return document
    app.openapi=notifications_openapi
    return app


def create_notifications_app(settings:V2RuntimeSettings|None=None,**services):
    app=FastAPI(title="Explicit private notification application",docs_url=None,redoc_url=None,openapi_url=None)
    app.mount("/v2",create_notifications_v2_app(settings,**services))
    return app
