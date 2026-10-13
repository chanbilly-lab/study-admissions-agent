"""Finite anonymous T39 routes; no free prompt or user authority input."""

import json

from fastapi import APIRouter, Depends, Request

from ..api.v2.errors import ApiError, STATUS_CODES
from ..api.v2.router import ERROR_RESPONSES, REQUEST_ID_HEADER, foundation_meta, no_config_query
from ..api.v2.schemas import Envelope, ErrorDetail
from ..model_gateway.schemas import GatewayError
from .http_schemas import QAAnswerData, QAContextData
from .schemas import QAError, RetrievalRequest

MAX_BODY_BYTES = 16384
router = APIRouter(responses=ERROR_RESPONSES)


def translate(error):
    status = error.status_code
    if status not in {422, 409, 429, 503}:
        status = 503
    return ApiError(status, STATUS_CODES[status], details=[ErrorDetail(field_path="qa", code=error.code,
        message="问答请求未完成，请查看当前状态并明确重试")])


def current_service(request):
    service = request.app.state.qa_service
    if service is None:
        code = "MODEL_DISABLED" if request.app.state.runtime_settings.model_mode == "disabled" else "QA_UNAVAILABLE"
        raise ApiError(503, "SERVICE_UNAVAILABLE", details=[ErrorDetail(field_path="qa", code=code, message="问答入口当前不可用")])
    try:
        service.preflight()
    except (QAError, GatewayError) as error:
        raise translate(error) from None
    return service


def reject_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


async def parse_body(request):
    try:
        if (request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json"
            or "idempotency-key" in request.headers):
            raise ValueError()
        size = request.headers.get("content-length")
        if size is not None and (not size.isascii() or not size.isdigit() or len(size) > 8 or int(size) > MAX_BODY_BYTES):
            raise ValueError()
        data = bytearray()
        async for part in request.stream():
            if len(data) + len(part) > MAX_BODY_BYTES:
                raise ValueError()
            data.extend(part)
        raw = json.loads(data.decode("utf-8"), object_pairs_hook=reject_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        return RetrievalRequest.model_validate(raw)
    except Exception:
        raise translate(QAError(422)) from None


@router.get("/qa/context", response_model=Envelope[QAContextData], operation_id="getV2QAContext",
    dependencies=[Depends(no_config_query)], responses={200: {"headers": REQUEST_ID_HEADER}})
def get_context(request: Request):
    if request.app.state.qa_service is None:
        runtime = request.app.state.runtime_settings
        data = QAContextData(schema_version="v2.t39", can_ask=False, model_mode=runtime.model_mode,
            live_available=False, real_processing_enabled=False, allow_test_fixture_read=False, demo_banner=None,
            disabled_reason="MODEL_DISABLED" if runtime.model_mode == "disabled" else "QA_UNAVAILABLE",
            budget_unit="conservative_utf8_bytes")
    else:
        try:
            data = current_service(request).context()
        except (QAError, GatewayError) as error:
            raise translate(error) from None
    return Envelope(data=data, meta=foundation_meta(request))


@router.post("/qa/answers", response_model=Envelope[QAAnswerData], operation_id="answerV2QA",
    dependencies=[Depends(no_config_query)], responses={200: {"headers": REQUEST_ID_HEADER}},
    openapi_extra={"requestBody": {"required": True, "content": {"application/json": {
        "schema": {"$ref": "#/components/schemas/RetrievalRequest"}}}}})
async def answer(request: Request):
    service = current_service(request)
    body = await parse_body(request)
    try:
        data = QAAnswerData.model_validate(await service.answer(body))
    except (QAError, GatewayError) as error:
        raise translate(error) from None
    return Envelope(data=data, meta=foundation_meta(request))
