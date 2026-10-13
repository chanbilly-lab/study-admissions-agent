"""M0 modular monolith. No table creation, imports, external calls, or real profiles at startup."""
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .api.v2 import create_v2_app
from .catalog import catalog_list, read_offering
from .database import make_engine
from .eligibility import DATA_AS_OF, RULESET_VERSION, evaluate
from .models import EligibilityResultRecord, EvidenceRecord, OfferingRecord, PlanDraftRecord, ProfileVersionRecord
from .planning import build_draft
from .providers import LiveProviderUnavailable, provider_for
from .schemas import CheckRequest, Eligibility, Envelope, Evidence, Meta, Offering, PlanDraft, Profile, ProfileInput, RuntimeConfig
from .settings import Settings, assert_m0_allowed

security = HTTPBearer(auto_error=False)
DEMO_USERS = {"demo-alice-token": "demo_alice", "demo-bob-token": "demo_bob"}


def demo_owner(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)]):
    if credentials is None or credentials.scheme.lower() != "bearer" or credentials.credentials not in DEMO_USERS:
        raise HTTPException(status_code=401, detail="需要服务端演示凭据；仅供本地合成数据演示", headers={"WWW-Authenticate": "Bearer"})
    return DEMO_USERS[credentials.credentials]


def session_dependency(request: Request):
    with Session(request.app.state.engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(session_dependency)]
OwnerDep = Annotated[str, Depends(demo_owner)]


def create_app(settings: Settings | None = None) -> FastAPI:
    assert_m0_allowed(legacy_demo_mode=settings.legacy_demo_mode if settings is not None else None)
    settings = settings or Settings()
    app = FastAPI(title="DEMO 升学咨询 M0", version="0.1.0",
                  description="仅合成 DEMO 数据和演示凭据；不提供真实招生结论、录取概率或自动申请。")
    app.state.settings = settings
    app.state.engine = make_engine(settings)
    app.state.provider = provider_for(settings.model_mode)
    app.add_middleware(CORSMiddleware,
                       allow_origins=list({settings.cors_origin, "http://127.0.0.1:5173", "http://localhost:5173"}),
                       allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def request_identity(request, call_next):
        request.state.request_id = uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    def envelope(request, data, profile_version=None):
        return Envelope(data=data, meta=Meta(request_id=request.state.request_id, data_as_of=DATA_AS_OF,
                                             profile_version=profile_version, ruleset_version=RULESET_VERSION,
                                             demo_mode=True, model_mode=settings.model_mode))

    def private_profile(session, identifier, owner):
        record = session.scalar(select(ProfileVersionRecord).where(ProfileVersionRecord.id == identifier,
                                                                   ProfileVersionRecord.owner_id == owner))
        if record is None:
            raise HTTPException(404, "画像版本不存在")
        return Profile.model_validate(record.payload)

    def selected_offerings(session, ids):
        offerings = []
        for identifier in ids:
            record = session.get(OfferingRecord, identifier)
            if record is None:
                raise HTTPException(404, "项目不存在")
            offerings.append(read_offering(session, record))
        return offerings

    def compute(session, profile, offerings, owner):
        results = [evaluate(session, profile, offering, settings) for offering in offerings]
        for result in results:
            session.add(EligibilityResultRecord(id=result.id, owner_id=owner, profile_version_id=profile.id,
                                                offering_id=result.offering_id, ruleset_version=RULESET_VERSION,
                                                payload=result.model_dump(mode="json")))
        return results

    @app.get("/health/live")
    def health_live():
        return {"status": "ok", "demo_mode": True}

    @app.get("/health/ready")
    def health_ready(session: SessionDep):
        try:
            session.execute(text("SELECT 1"))
            session.execute(select(OfferingRecord.id).limit(1)).first()
        except Exception:
            raise HTTPException(503, "数据库连接或 M0 迁移未就绪")
        return {"status": "ok", "demo_mode": True}

    @app.get("/v1/config", response_model=Envelope[RuntimeConfig])
    def config(request: Request):
        return envelope(request, RuntimeConfig(supported_province=settings.supported_province, entry_year=settings.entry_year,
                                                model_mode=settings.model_mode, demo_mode=True, live_available=False))

    @app.get("/v1/profiles", response_model=Envelope[list[Profile]])
    def list_profiles(request: Request, session: SessionDep, owner: OwnerDep):
        rows = session.scalars(select(ProfileVersionRecord).where(ProfileVersionRecord.owner_id == owner).order_by(ProfileVersionRecord.id))
        return envelope(request, [Profile.model_validate(row.payload) for row in rows])

    @app.post("/v1/profiles", response_model=Envelope[Profile], status_code=201)
    def create_profile(request: Request, payload: ProfileInput, session: SessionDep, owner: OwnerDep):
        if payload.province != settings.supported_province:
            raise HTTPException(422, "M0 仅支持配置的一个生源省份；请核验配置")
        identifier = f"DEMO_PROFILE_{uuid4().hex}"
        profile = Profile(**payload.model_dump(), id=identifier, version=1, owner_id=owner)
        session.add(ProfileVersionRecord(id=identifier, profile_id=identifier, owner_id=owner, version=1,
                                         is_synthetic=True, payload=profile.model_dump(mode="json")))
        session.commit()
        return envelope(request, profile, profile.version)

    @app.get("/v1/profiles/{identifier}", response_model=Envelope[Profile])
    def get_profile(identifier: str, request: Request, session: SessionDep, owner: OwnerDep):
        profile = private_profile(session, identifier, owner)
        return envelope(request, profile, profile.version)

    @app.get("/v1/offerings", response_model=Envelope[list[Offering]])
    def list_offerings(request: Request, session: SessionDep, country: Literal["CN", "GB"] | None = None,
                       entry_year: Annotated[int | None, Query(ge=2026, le=2100)] = None, province: str | None = None):
        province = province or settings.supported_province
        if province != settings.supported_province:
            raise HTTPException(422, "M0 尚未支持该生源省份")
        return envelope(request, catalog_list(session, country, entry_year or settings.entry_year, province))

    @app.get("/v1/offerings/{identifier}", response_model=Envelope[Offering])
    def get_offering(identifier: str, request: Request, session: SessionDep):
        record = session.get(OfferingRecord, identifier)
        if record is None:
            raise HTTPException(404, "项目不存在")
        return envelope(request, read_offering(session, record))

    @app.get("/v1/evidence/{identifier}", response_model=Envelope[Evidence])
    def get_evidence(identifier: str, request: Request, session: SessionDep):
        record = session.get(EvidenceRecord, identifier)
        if record is None:
            raise HTTPException(404, "合成证据不存在")
        return envelope(request, Evidence.model_validate(record.payload))

    @app.post("/v1/eligibility/check", response_model=Envelope[list[Eligibility]])
    def check(request: Request, payload: CheckRequest, session: SessionDep, owner: OwnerDep):
        profile = private_profile(session, payload.profile_version_id, owner)
        offerings = selected_offerings(session, payload.offering_ids)
        results = compute(session, profile, offerings, owner)
        session.commit()
        return envelope(request, results, profile.version)

    @app.post("/v1/plans/drafts", response_model=Envelope[PlanDraft], status_code=201)
    def create_draft(request: Request, payload: CheckRequest, session: SessionDep, owner: OwnerDep):
        profile = private_profile(session, payload.profile_version_id, owner)
        offerings = selected_offerings(session, payload.offering_ids)
        results = compute(session, profile, offerings, owner)  # Recompute; never trust client supplied conclusions.
        try:
            plan = build_draft(session, profile, offerings, results, app.state.provider, settings.model_mode)
        except LiveProviderUnavailable as error:
            session.rollback()
            raise HTTPException(503, str(error))
        session.add(PlanDraftRecord(id=plan.id, owner_id=owner, profile_version_id=profile.id, payload=plan.model_dump(mode="json")))
        session.commit()
        return envelope(request, plan, profile.version)

    @app.get("/v1/plans/{identifier}", response_model=Envelope[PlanDraft])
    def get_plan(identifier: str, request: Request, session: SessionDep, owner: OwnerDep):
        record = session.scalar(select(PlanDraftRecord).where(PlanDraftRecord.id == identifier, PlanDraftRecord.owner_id == owner))
        if record is None:
            raise HTTPException(404, "计划草案不存在")
        profile = private_profile(session, record.profile_version_id, owner)
        return envelope(request, PlanDraft.model_validate(record.payload), profile.version)

    app.mount("/v2", create_v2_app())
    return app


app = create_app()
