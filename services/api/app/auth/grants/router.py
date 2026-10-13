"""Cookie control-plane routes; closed assembly imports no SQL/provider modules."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...api.v2.errors import ApiError
from ...api.v2.router import ERROR_RESPONSES, REQUEST_ID_HEADER, foundation_meta, no_config_query, unique_query_parameters
from ...api.v2.schemas import Envelope, OfferingQuery
from ..dependencies import current_principal
from .policy import sharing_policy
from .schemas import AcceptGrantInput, CreateGrantInput, GrantListData, GrantMutationData, SharingPolicyData


router = APIRouter(responses=ERROR_RESPONSES)


class GrantQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    direction: Literal["issued", "received"] = "issued"
    limit: int = Field(default=20, ge=1, le=100)
    after_id: UUID | None = None

    @field_validator("limit", mode="before")
    @classmethod
    def integer_parameter(cls, value):
        return OfferingQuery.integer_parameter(value)


def sharing_service(request: Request):
    request.state.private_access = True
    service = getattr(request.app.state, "sharing_service", None)
    if service is None:
        raise ApiError(503, "SERVICE_UNAVAILABLE")
    return service


@router.get("/sharing/policy", response_model=Envelope[SharingPolicyData], operation_id="getV2SharingPolicy",
            dependencies=[Depends(no_config_query)], responses={200: {"headers": REQUEST_ID_HEADER}})
def policy(request: Request):
    request.state.private_access = True
    service = getattr(request.app.state, "sharing_service", None)
    return Envelope(data=service.get_policy() if service is not None else sharing_policy(False), meta=foundation_meta(request))


@router.get("/access-grants", response_model=Envelope[GrantListData], operation_id="listV2AccessGrants",
            dependencies=[Depends(unique_query_parameters)], responses={200: {"headers": REQUEST_ID_HEADER}})
def list_grants(request: Request, query: Annotated[GrantQuery, Query()], principal=Depends(current_principal),
                service=Depends(sharing_service)):
    return Envelope(data=service.list_grants(principal, query.direction, query.limit, query.after_id), meta=foundation_meta(request))


@router.post("/access-grants", response_model=Envelope[GrantMutationData], operation_id="createV2AccessGrant",
             dependencies=[Depends(no_config_query)], responses={200: {"headers": REQUEST_ID_HEADER}})
def create_grant(request: Request, payload: CreateGrantInput, principal=Depends(current_principal), service=Depends(sharing_service)):
    return Envelope(data=service.create_grant(principal, payload), meta=foundation_meta(request))


@router.post("/access-grants/{grant_id}/accept", response_model=Envelope[GrantMutationData], operation_id="acceptV2AccessGrant",
             dependencies=[Depends(no_config_query)], responses={200: {"headers": REQUEST_ID_HEADER}})
def accept_grant(request: Request, grant_id: UUID, payload: AcceptGrantInput, principal=Depends(current_principal),
                 service=Depends(sharing_service)):
    return Envelope(data=service.accept_grant(principal, grant_id, payload), meta=foundation_meta(request))


@router.delete("/access-grants/{grant_id}", response_model=Envelope[GrantMutationData], operation_id="revokeV2AccessGrant",
               dependencies=[Depends(no_config_query)], responses={200: {"headers": REQUEST_ID_HEADER}})
async def revoke_grant(request: Request, grant_id: UUID, principal=Depends(current_principal), service=Depends(sharing_service)):
    from starlette.concurrency import run_in_threadpool
    async for chunk in request.stream():
        if chunk:
            raise RequestValidationError([{"type": "extra_forbidden", "loc": ("body",)}])
    result = await run_in_threadpool(service.revoke_grant, principal, grant_id)
    return Envelope(data=result, meta=foundation_meta(request))
