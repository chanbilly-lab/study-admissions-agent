"""Append-only annual request metadata, isolated from private T36 jobs."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, MetaData, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class AnnualUpdatesBase(DeclarativeBase):
    metadata = MetaData(schema="public")


class AnnualSourceCycle(AnnualUpdatesBase):
    __tablename__ = "annual_source_cycles"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    schedule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    cycle_year: Mapped[int] = mapped_column(Integer, nullable=False)
    config_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    config_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    config_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    plan_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        UniqueConstraint("schedule_id", "cycle_year", name="uq_annual_source_cycle"),
        CheckConstraint("schedule_id ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$'", name="ck_annual_schedule_id"),
        CheckConstraint("cycle_year BETWEEN 2000 AND 9998 AND config_revision BETWEEN 1 AND 2147483647 "
                        "AND request_count BETWEEN 1 AND 10 AND created_at>=scheduled_at", name="ck_annual_cycle_bounds"),
        CheckConstraint("(config_sha256 ~ '^[0-9a-f]{64}$' AND jsonb_typeof(config_snapshot)='object' "
                        "AND octet_length(config_snapshot::text)<=65536 "
                        "AND config_snapshot->>'schema_version'='annual.source.schedule.1' "
                        "AND config_snapshot->>'schedule_id'=schedule_id "
                        "AND config_snapshot->'revision'=to_jsonb(config_revision) "
                        "AND config_snapshot->'enabled'='true'::jsonb) IS TRUE", name="ck_annual_config_snapshot"),
        CheckConstraint("(jsonb_typeof(plan_payload)='object' AND octet_length(plan_payload::text)<=131072 "
                        "AND plan_payload->>'schema_version'='annual.source.plan.1' "
                        "AND plan_payload->>'cycle_id'=id::text "
                        "AND plan_payload->>'schedule_id'=schedule_id "
                        "AND plan_payload->'cycle_year'=to_jsonb(cycle_year) "
                        "AND plan_payload->'config_revision'=to_jsonb(config_revision) "
                        "AND plan_payload->>'config_sha256'=config_sha256 "
                        "AND jsonb_typeof(plan_payload->'requests')='array' "
                        "AND jsonb_array_length(plan_payload->'requests')=request_count) IS TRUE", name="ck_annual_plan_payload"),
    )


class AnnualSourceUpdateRequest(AnnualUpdatesBase):
    __tablename__ = "annual_source_update_requests"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    cycle_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey(AnnualSourceCycle.id, ondelete="RESTRICT"), nullable=False)
    target_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    exam_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entry_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (
        UniqueConstraint("cycle_id", "target_ref", name="uq_annual_source_target"),
        CheckConstraint("target_ref ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$'", name="ck_annual_target_ref"),
        CheckConstraint("(kind IN ('province_cutoffs','admission_observations') "
                        "AND exam_year BETWEEN 1 AND 9999 AND exam_year IS NOT NULL AND entry_year IS NULL) OR "
                        "(kind='entry_requirements' AND exam_year IS NULL AND entry_year BETWEEN 1 AND 9999 "
                        "AND entry_year IS NOT NULL)", name="ck_annual_target_year"),
        CheckConstraint("(payload_sha256 ~ '^[0-9a-f]{64}$' AND jsonb_typeof(payload)='object' "
                        "AND octet_length(payload::text)<=16384 "
                        "AND payload->>'id'=id::text AND payload->>'target_ref'=target_ref "
                        "AND payload->>'dataset_type'=kind "
                        "AND payload->'exam_year'=COALESCE(to_jsonb(exam_year),'null'::jsonb) "
                        "AND payload->'entry_year'=COALESCE(to_jsonb(entry_year),'null'::jsonb) "
                        "AND payload->>'status'='awaiting_collection' "
                        "AND payload->'source_evidence_year'='null'::jsonb "
                        "AND payload->'network_requested'='false'::jsonb "
                        "AND payload->'facts_updated'='false'::jsonb "
                        "AND payload->'published'='false'::jsonb) IS TRUE", name="ck_annual_request_payload"),
    )
