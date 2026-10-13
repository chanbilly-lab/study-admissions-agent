"""Independent T35 application profile, with zero-IO closed construction."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from ..audit.context import current_actor, failure_handled, request_context
from ..auth.config import AuthFlowError
from ..plan_revisions.router import REQUEST_MODELS,router
from ..settings import V2RuntimeSettings
from .plans import create_plans_v2_app
from .v2.errors import ApiError,STATUS_CODES,error_response,request_id


def create_revisions_v2_app(settings:V2RuntimeSettings|None=None,*,identity_service=None,profile_service=None,
                            assessment_service=None,execution_service=None,revision_service=None):
    runtime=V2RuntimeSettings.model_validate(settings) if settings is not None else V2RuntimeSettings()
    if revision_service is not None:
        from ..plan_revisions.service import RevisionService
        if (not isinstance(revision_service,RevisionService) or revision_service.execution_service is not execution_service
            or revision_service.auth_service is not identity_service or revision_service.profile_service is not profile_service
            or revision_service.plans_service.eligibility_service is not assessment_service):
            raise AuthFlowError(503,"SERVICE_UNAVAILABLE")
        revision_service._validate()
    app=create_plans_v2_app(runtime,identity_service=identity_service,profile_service=profile_service,
        assessment_service=assessment_service,execution_service=execution_service)
    app.title,app.version="升学咨询 T35 explicit plan revisions","v2.t35"
    app.state.revision_service=revision_service
    app.include_router(router)
    if revision_service is not None:
        previous=app.router.lifespan_context
        @asynccontextmanager
        async def lifespan(application):
            async with previous(application):
                await run_in_threadpool(revision_service.store.assert_schema_ready)
                yield
        app.router.lifespan_context=lifespan

    @app.middleware("http")
    async def revision_context(request,call_next):
        path=request.scope["path"].removeprefix(request.scope.get("root_path",""))
        if path!="/plan-revisions" and not path.startswith("/plan-revisions/"):
            return await call_next(request)
        with request_context(request_id(request)):
            try:
                response=await call_next(request)
            except Exception:
                response=error_response(request,500,"INTERNAL_ERROR")
            if response.status_code>=400 and identity_service is not None and not failure_handled():
                status=response.status_code if response.status_code in STATUS_CODES else 500
                try:
                    await run_in_threadpool(identity_service.store.audit.failure,"authorization.owned.execute",
                        ApiError(status,STATUS_CODES[status]),actor=current_actor())
                except Exception:
                    pass
            response.headers.update({"Cache-Control":"no-store","Pragma":"no-cache","Referrer-Policy":"no-referrer"})
            return response

    original=app.openapi
    def revisions_openapi():
        document=original()
        components=document.setdefault("components",{}).setdefault("schemas",{})
        for model in REQUEST_MODELS:
            definition=model.model_json_schema(ref_template="#/components/schemas/{model}")
            components.update(definition.pop("$defs",{}))
            components[model.__name__]=definition
        for path,operations in document["paths"].items():
            if path!="/plan-revisions" and not path.startswith("/plan-revisions/"):
                continue
            for method,operation in operations.items():
                if method not in {"get","post"}:
                    continue
                security={"SessionCookie":[]}
                if method=="post":
                    security.update({"CsrfHeader":[],"RequestOrigin":[]})
                operation["security"]=[security]
                for parameter in operation.get("parameters",[]):
                    if parameter.get("in")=="path" and parameter.get("name") in {"plan_id","revision_id"}:
                        parameter["schema"]={"type":"string","format":"uuid"}
        return document
    app.openapi=revisions_openapi
    return app


def create_revisions_app(settings:V2RuntimeSettings|None=None,**services):
    app=FastAPI(title="Explicit private revision application",docs_url=None,redoc_url=None,openapi_url=None)
    app.mount("/v2",create_revisions_v2_app(settings,**services))
    return app
