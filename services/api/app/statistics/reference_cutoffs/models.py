"""Independent local reference metadata, with no M0 or offering foreign keys."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (CheckConstraint, DateTime, ForeignKey, Integer, LargeBinary,
                        String, UniqueConstraint, Uuid)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class ReferenceCutoffsBase(DeclarativeBase):
    pass


class SourceVersion(ReferenceCutoffsBase):
    __tablename__ = "reference_cutoff_sources"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    original_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    body_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    __table_args__ = (
        CheckConstraint("original_sha256 ~ '^[0-9a-f]{64}$'", name="ck_ref_source_hash"),
        CheckConstraint("body_bytes BETWEEN 1 AND 2097152 AND octet_length(raw_body)=body_bytes",
                        name="ck_ref_source_bytes"),
        CheckConstraint("jsonb_typeof(payload)='object' AND octet_length(payload::text)<=16384",
                        name="ck_ref_source_payload"),
    )


class CutoffBatch(ReferenceCutoffsBase):
    __tablename__ = "reference_cutoff_batches"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    source_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey(SourceVersion.id, ondelete="RESTRICT"), nullable=False)
    batch_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        CheckConstraint("batch_key='ZJ2026_ORDINARY_CUTOFF_3'", name="ck_ref_batch_scope"),
        CheckConstraint("manifest_sha256 ~ '^[0-9a-f]{64}$'", name="ck_ref_batch_hash"),
        CheckConstraint("jsonb_typeof(manifest)='object' AND octet_length(manifest::text)<=65536",
                        name="ck_ref_batch_manifest"),
        CheckConstraint("(state='candidate' AND state_version=0) OR "
                        "(state='approved_local' AND state_version=1) OR "
                        "(state='withdrawn' AND state_version=2)", name="ck_ref_batch_state"),
    )


class CutoffRecord(ReferenceCutoffsBase):
    __tablename__ = "reference_cutoff_records"
    batch_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey(CutoffBatch.id, ondelete="RESTRICT"), primary_key=True)
    record_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    line_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    __table_args__ = (
        UniqueConstraint("batch_id", "line_kind", name="uq_ref_record_line_kind"),
        CheckConstraint("record_key ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$' AND "
                        "upper(substr(record_key,1,5)) <> 'DEMO_'", name="ck_ref_record_key"),
        CheckConstraint("(line_kind='segment_first' AND value=494) OR "
                        "(line_kind='segment_second' AND value=266) OR "
                        "(line_kind='special_category' AND value=594)", name="ck_ref_record_reviewed_fact"),
        CheckConstraint("jsonb_typeof(payload)='object' AND octet_length(payload::text)<=8192",
                        name="ck_ref_record_payload"),
    )


class ReviewEvent(ReferenceCutoffsBase):
    __tablename__ = "reference_cutoff_reviews"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    batch_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey(CutoffBatch.id, ondelete="RESTRICT"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    review_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    proof_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    proof: Mapped[dict] = mapped_column(JSONB, nullable=False)
    __table_args__ = (
        UniqueConstraint("batch_id", "sequence", name="uq_ref_review_sequence"),
        CheckConstraint("(sequence=1 AND decision='approve_local') OR (sequence=2 AND decision='withdraw')",
                        name="ck_ref_review_decision"),
        CheckConstraint("manifest_sha256 ~ '^[0-9a-f]{64}$' AND original_sha256 ~ '^[0-9a-f]{64}$' AND "
                        "proof_sha256 ~ '^[0-9a-f]{64}$'", name="ck_ref_review_hashes"),
        CheckConstraint("review_ref='USER_ZJ2026_ORDINARY_3'", name="ck_ref_review_human"),
        CheckConstraint("jsonb_typeof(proof)='object' AND octet_length(proof::text)<=16384",
                        name="ck_ref_review_proof"),
    )
