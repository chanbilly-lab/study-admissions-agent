"""Append-only suggestions and decisions; original plan rows remain untouched."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..plan_execution.models import ExecutionHead, ExecutionProposal


class RevisionsBase(DeclarativeBase):
    pass


class RevisionProposal(RevisionsBase):
    __tablename__="revision_proposals"
    id:Mapped[UUID]=mapped_column(primary_key=True)
    owner_user_id:Mapped[UUID]=mapped_column(nullable=False)
    is_synthetic:Mapped[bool]=mapped_column(Boolean,nullable=False)
    old_plan_id:Mapped[UUID]=mapped_column(nullable=False)
    new_plan_id:Mapped[UUID]=mapped_column(nullable=False)
    old_source_version_id:Mapped[UUID]=mapped_column(nullable=False)
    new_source_version_id:Mapped[UUID]=mapped_column(nullable=False)
    old_proposal_id:Mapped[UUID]=mapped_column(nullable=False)
    new_proposal_id:Mapped[UUID]=mapped_column(nullable=False)
    expected_old_state_version:Mapped[int]=mapped_column(Integer,nullable=False)
    expected_new_state_version:Mapped[int]=mapped_column(Integer,nullable=False)
    request_sha256:Mapped[str]=mapped_column(String(64),nullable=False)
    payload_sha256:Mapped[str]=mapped_column(String(64),nullable=False)
    payload:Mapped[dict]=mapped_column(JSONB,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    audit_event_id:Mapped[UUID]=mapped_column(nullable=False)
    __table_args__=(
        UniqueConstraint("owner_user_id","request_sha256",name="uq_revision_natural_request"),
        UniqueConstraint("id","old_plan_id","new_plan_id","owner_user_id","is_synthetic",name="uq_revision_relationship_scope"),
        ForeignKeyConstraint(("old_plan_id","old_source_version_id","owner_user_id","is_synthetic"),
            (ExecutionHead.plan_id,ExecutionHead.source_version_id,ExecutionHead.owner_user_id,ExecutionHead.is_synthetic),
            name="fk_revision_old_owner",ondelete="RESTRICT"),
        ForeignKeyConstraint(("new_plan_id","new_source_version_id","owner_user_id","is_synthetic"),
            (ExecutionHead.plan_id,ExecutionHead.source_version_id,ExecutionHead.owner_user_id,ExecutionHead.is_synthetic),
            name="fk_revision_new_owner",ondelete="RESTRICT"),
        ForeignKeyConstraint(("old_proposal_id","old_plan_id"),(ExecutionProposal.id,ExecutionProposal.plan_id),name="fk_revision_old_proposal",ondelete="RESTRICT"),
        ForeignKeyConstraint(("new_proposal_id","new_plan_id"),(ExecutionProposal.id,ExecutionProposal.plan_id),name="fk_revision_new_proposal",ondelete="RESTRICT"),
        CheckConstraint("old_plan_id<>new_plan_id AND expected_old_state_version BETWEEN 2 AND 2147483647 AND expected_new_state_version BETWEEN 1 AND 2147483647",name="ck_revision_distinct_pins"),
        CheckConstraint("length(request_sha256)=64 AND request_sha256 ~ '^[0-9a-f]{64}$' AND length(payload_sha256)=64 AND payload_sha256 ~ '^[0-9a-f]{64}$'",name="ck_revision_hashes"),
        CheckConstraint("jsonb_typeof(payload)='object' AND octet_length(payload::text)<=2097152",name="ck_revision_payload"),
        CheckConstraint("expires_at>created_at AND expires_at<=(((created_at AT TIME ZONE 'UTC')+interval '24 months') AT TIME ZONE 'UTC')",name="ck_revision_retention"),
        Index("ix_revision_owner_created","owner_user_id","created_at","id"),
    )


class RevisionDecision(RevisionsBase):
    __tablename__="revision_decisions"
    id:Mapped[UUID]=mapped_column(primary_key=True)
    revision_id:Mapped[UUID]=mapped_column(nullable=False)
    old_plan_id:Mapped[UUID]=mapped_column(nullable=False)
    new_plan_id:Mapped[UUID]=mapped_column(nullable=False)
    owner_user_id:Mapped[UUID]=mapped_column(nullable=False)
    is_synthetic:Mapped[bool]=mapped_column(Boolean,nullable=False)
    action:Mapped[str]=mapped_column(String(8),nullable=False)
    revision_version:Mapped[int]=mapped_column(Integer,nullable=False)
    request_sha256:Mapped[str]=mapped_column(String(64),nullable=False)
    decided_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    audit_event_id:Mapped[UUID]=mapped_column(nullable=False)
    __table_args__=(
        UniqueConstraint("revision_id",name="uq_revision_single_decision"),
        UniqueConstraint("id","revision_id","old_plan_id","new_plan_id","owner_user_id","is_synthetic",name="uq_revision_decision_scope"),
        UniqueConstraint("id","revision_id","old_plan_id","new_plan_id","owner_user_id","is_synthetic","action",name="uq_revision_decision_action_scope"),
        ForeignKeyConstraint(("revision_id","old_plan_id","new_plan_id","owner_user_id","is_synthetic"),
            (RevisionProposal.id,RevisionProposal.old_plan_id,RevisionProposal.new_plan_id,RevisionProposal.owner_user_id,RevisionProposal.is_synthetic),
            name="fk_revision_decision_scope",ondelete="RESTRICT"),
        CheckConstraint("action IN ('accept','reject') AND revision_version=2",name="ck_revision_decision"),
        CheckConstraint("length(request_sha256)=64 AND request_sha256 ~ '^[0-9a-f]{64}$'",name="ck_revision_decision_hash"),
        CheckConstraint("expires_at>decided_at AND expires_at<=(((decided_at AT TIME ZONE 'UTC')+interval '24 months') AT TIME ZONE 'UTC')",name="ck_revision_decision_retention"),
    )


class PlanReplacement(RevisionsBase):
    __tablename__="plan_replacement_links"
    id:Mapped[UUID]=mapped_column(primary_key=True)
    revision_id:Mapped[UUID]=mapped_column(nullable=False)
    decision_id:Mapped[UUID]=mapped_column(nullable=False)
    old_plan_id:Mapped[UUID]=mapped_column(nullable=False)
    new_plan_id:Mapped[UUID]=mapped_column(nullable=False)
    owner_user_id:Mapped[UUID]=mapped_column(nullable=False)
    is_synthetic:Mapped[bool]=mapped_column(Boolean,nullable=False)
    action:Mapped[str]=mapped_column(String(8),nullable=False)
    accepted_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    audit_event_id:Mapped[UUID]=mapped_column(nullable=False)
    __table_args__=(
        UniqueConstraint("old_plan_id",name="uq_revision_old_successor"),
        UniqueConstraint("new_plan_id",name="uq_revision_new_predecessor"),
        UniqueConstraint("revision_id",name="uq_revision_single_relationship"),
        ForeignKeyConstraint(("decision_id","revision_id","old_plan_id","new_plan_id","owner_user_id","is_synthetic","action"),
            (RevisionDecision.id,RevisionDecision.revision_id,RevisionDecision.old_plan_id,RevisionDecision.new_plan_id,RevisionDecision.owner_user_id,RevisionDecision.is_synthetic,RevisionDecision.action),
            name="fk_revision_accepted_decision",ondelete="RESTRICT"),
        CheckConstraint("old_plan_id<>new_plan_id AND action='accept'",name="ck_revision_relationship_distinct"),
        CheckConstraint("expires_at>accepted_at AND expires_at<=(((accepted_at AT TIME ZONE 'UTC')+interval '24 months') AT TIME ZONE 'UTC')",name="ck_revision_relationship_retention"),
    )
