"""One current selection and immutable human decision/resolution histories."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKeyConstraint,
                        Index, Integer, String, UniqueConstraint, Uuid)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..facts.models import FactCandidate


class ReviewsBase(DeclarativeBase):
    pass


class ReviewCase(ReviewsBase):
    __tablename__ = "review_cases"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    logical_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    chosen_fact_id: Mapped[UUID | None] = mapped_column(Uuid)
    current_decision_id: Mapped[UUID | None] = mapped_column(Uuid)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("logical_key_hash", name="uq_review_logical_key"),
        UniqueConstraint("id", "logical_key_hash", name="uq_review_case_scope"),
        ForeignKeyConstraint(("chosen_fact_id", "logical_key_hash"),
            (FactCandidate.__table__.c.id, FactCandidate.__table__.c.logical_key_hash),
            ondelete="RESTRICT", name="fk_review_case_chosen_fact"),
        CheckConstraint("logical_key_hash ~ '^[0-9a-f]{64}$' AND revision BETWEEN 0 AND 2147483647", name="ck_review_case_revision"),
        CheckConstraint("(revision = 0 AND chosen_fact_id IS NULL AND current_decision_id IS NULL) OR (revision > 0 AND current_decision_id IS NOT NULL)", name="ck_review_case_pointer"),
        CheckConstraint("updated_at >= created_at", name="ck_review_case_times"),
    )


class ReviewDecision(ReviewsBase):
    __tablename__ = "review_decisions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    case_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    case_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    logical_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fact_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    action: Mapped[str] = mapped_column(String(7), nullable=False)
    checks: Mapped[list] = mapped_column(JSONB, nullable=False)
    return_reason: Mapped[str | None] = mapped_column(String(24))
    fact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    conflicts_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    audit_event_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("case_id", "logical_key_hash"),
            (ReviewCase.__table__.c.id, ReviewCase.__table__.c.logical_key_hash),
            ondelete="RESTRICT", name="fk_review_decision_case"),
        ForeignKeyConstraint(("fact_id", "logical_key_hash"),
            (FactCandidate.__table__.c.id, FactCandidate.__table__.c.logical_key_hash),
            ondelete="RESTRICT", name="fk_review_decision_fact"),
        UniqueConstraint("case_id", "case_revision", name="uq_review_decision_revision"),
        UniqueConstraint("id", "case_id", name="uq_review_decision_pointer"),
        UniqueConstraint("id", "fact_id", "logical_key_hash", name="uq_review_resolution_parent"),
        CheckConstraint("case_revision BETWEEN 1 AND 2147483647 AND action IN ('approve','return')", name="ck_review_decision_action"),
        CheckConstraint("(action = 'approve' AND return_reason IS NULL) OR (action = 'return' AND return_reason IS NOT NULL AND return_reason IN ('INVALID_VALUE','MISSING_EVIDENCE','SCOPE_MISMATCH','UNIT_MISMATCH','PERIOD_UNCLEAR','MISSING_CONTEXT','FOOTNOTE_UNRESOLVED','SOURCE_UNAVAILABLE','CONFLICT_UNRESOLVED','UNSUPPORTED_LITERAL'))", name="ck_review_return_reason"),
        CheckConstraint("jsonb_typeof(checks) = 'array' AND jsonb_array_length(checks) = 10 AND octet_length(checks::text) <= 4096", name="ck_review_checks"),
        CheckConstraint("logical_key_hash ~ '^[0-9a-f]{64}$' AND fact_sha256 ~ '^[0-9a-f]{64}$' AND conflicts_sha256 ~ '^[0-9a-f]{64}$'", name="ck_review_decision_hashes"),
        Index("ix_review_decision_fact", "fact_id", "case_revision"),
    )


# Deferred only to break the case/history insertion cycle. The commit checks
# the current pointer belongs to this case; service checks its revision/action.
ReviewCase.__table__.append_constraint(ForeignKeyConstraint(
    (ReviewCase.__table__.c.current_decision_id, ReviewCase.__table__.c.id),
    (ReviewDecision.__table__.c.id, ReviewDecision.__table__.c.case_id),
    ondelete="RESTRICT", deferrable=True, initially="DEFERRED", use_alter=True,
    name="fk_review_case_current_decision"))


class ReviewConflictResolution(ReviewsBase):
    __tablename__ = "review_conflict_resolutions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    decision_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    selected_fact_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    other_fact_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    logical_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("decision_id", "selected_fact_id", "logical_key_hash"),
            (ReviewDecision.__table__.c.id, ReviewDecision.__table__.c.fact_id,
             ReviewDecision.__table__.c.logical_key_hash), ondelete="RESTRICT", name="fk_review_resolution_decision"),
        ForeignKeyConstraint(("other_fact_id", "logical_key_hash"),
            (FactCandidate.__table__.c.id, FactCandidate.__table__.c.logical_key_hash),
            ondelete="RESTRICT", name="fk_review_resolution_other"),
        UniqueConstraint("decision_id", "other_fact_id", name="uq_review_resolution_other"),
        CheckConstraint("selected_fact_id <> other_fact_id AND logical_key_hash ~ '^[0-9a-f]{64}$'", name="ck_review_resolution_scope"),
        CheckConstraint("reason_code IN ('SELECTED_SUPPORTED','INCORRECT_VALUE','WRONG_CONTEXT','DUPLICATE_OR_EQUIVALENT')", name="ck_review_resolution_reason"),
    )
