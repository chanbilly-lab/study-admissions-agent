"""Fixed release snapshots, mutable CAS visibility, and immutable change traces."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKeyConstraint,
                        Index, Integer, String, UniqueConstraint, Uuid, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..admin.sources.models import CatalogSourceVersion
from ..admissions_catalog.models import AdmissionOfferingVersion, CatalogDataset
from ..evidence.models import EvidenceSnippet
from ..facts.models import FactCandidate
from ..reviews.models import ReviewDecision
from ..storage.models import StorageObject


class ReleasesBase(DeclarativeBase):
    pass


class CatalogRelease(ReleasesBase):
    __tablename__ = "catalog_releases"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    entry_year: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    requirements_version: Mapped[str] = mapped_column(String(64), nullable=False)
    ruleset_version: Mapped[str | None] = mapped_column(String(64))
    replaces_release_id: Mapped[UUID | None] = mapped_column(Uuid)
    publisher_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    audit_event_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("dataset_id", "is_synthetic"),
            (CatalogDataset.__table__.c.id, CatalogDataset.__table__.c.is_synthetic),
            ondelete="RESTRICT", name="fk_release_dataset_mode"),
        UniqueConstraint("id", "dataset_id", "entry_year", "is_synthetic", name="uq_release_scope"),
        UniqueConstraint("content_sha256", name="uq_release_content"),
        CheckConstraint("version = 1 AND entry_year BETWEEN 1 AND 9999", name="ck_release_version"),
        CheckConstraint("(kind = 'formal' AND is_synthetic = false) OR (kind = 'test_fixture' AND is_synthetic = true)", name="ck_release_kind"),
        CheckConstraint("valid_from < valid_until AND ruleset_version IS NULL", name="ck_release_interval_rules"),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$' AND requirements_version ~ '^[0-9a-f]{64}$'", name="ck_release_hashes"),
        CheckConstraint("replaces_release_id IS NULL OR replaces_release_id <> id", name="ck_release_no_self_replace"),
    )


CatalogRelease.__table__.append_constraint(ForeignKeyConstraint(
    (CatalogRelease.__table__.c.replaces_release_id, CatalogRelease.__table__.c.dataset_id,
     CatalogRelease.__table__.c.entry_year, CatalogRelease.__table__.c.is_synthetic),
    (CatalogRelease.__table__.c.id, CatalogRelease.__table__.c.dataset_id,
     CatalogRelease.__table__.c.entry_year, CatalogRelease.__table__.c.is_synthetic),
    ondelete="RESTRICT", name="fk_release_replaces_scope"))


class CatalogReleaseMember(ReleasesBase):
    __tablename__ = "catalog_release_members"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    release_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    entry_year: Mapped[int] = mapped_column(Integer, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fact_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    logical_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    case_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    offering_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    offering_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    file_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    fact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_metadata_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    public_evidence: Mapped[bool] = mapped_column(Boolean, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("release_id", "dataset_id", "entry_year", "is_synthetic"),
            (CatalogRelease.__table__.c.id, CatalogRelease.__table__.c.dataset_id,
             CatalogRelease.__table__.c.entry_year, CatalogRelease.__table__.c.is_synthetic),
            ondelete="RESTRICT", name="fk_release_member_scope"),
        ForeignKeyConstraint(("fact_id", "logical_key_hash"),
            (FactCandidate.__table__.c.id, FactCandidate.__table__.c.logical_key_hash),
            ondelete="RESTRICT", name="fk_release_member_fact"),
        ForeignKeyConstraint(("decision_id", "fact_id", "logical_key_hash"),
            (ReviewDecision.__table__.c.id, ReviewDecision.__table__.c.fact_id, ReviewDecision.__table__.c.logical_key_hash),
            ondelete="RESTRICT", name="fk_release_member_decision"),
        ForeignKeyConstraint(("dataset_id", "offering_id", "offering_version"),
            (AdmissionOfferingVersion.__table__.c.dataset_id, AdmissionOfferingVersion.__table__.c.offering_id,
             AdmissionOfferingVersion.__table__.c.version), ondelete="RESTRICT", name="fk_release_member_offering"),
        ForeignKeyConstraint(("dataset_id", "source_id", "source_version"),
            (CatalogSourceVersion.__table__.c.dataset_id, CatalogSourceVersion.__table__.c.source_id,
             CatalogSourceVersion.__table__.c.version), ondelete="RESTRICT", name="fk_release_member_source"),
        ForeignKeyConstraint(("evidence_id",), (EvidenceSnippet.__table__.c.id,), ondelete="RESTRICT", name="fk_release_member_evidence"),
        ForeignKeyConstraint(("file_id",), (StorageObject.__table__.c.id,), ondelete="RESTRICT", name="fk_release_member_file"),
        UniqueConstraint("release_id", "fact_id", name="uq_release_member_fact"),
        UniqueConstraint("release_id", "logical_key_hash", name="uq_release_member_logical"),
        CheckConstraint("entry_year BETWEEN 1 AND 9999 AND case_revision BETWEEN 1 AND 2147483647 AND offering_version BETWEEN 1 AND 2147483647 AND source_version BETWEEN 1 AND 2147483647", name="ck_release_member_versions"),
        CheckConstraint("logical_key_hash ~ '^[0-9a-f]{64}$' AND fact_sha256 ~ '^[0-9a-f]{64}$' AND scope_sha256 ~ '^[0-9a-f]{64}$' AND evidence_sha256 ~ '^[0-9a-f]{64}$' AND source_sha256 ~ '^[0-9a-f]{64}$' AND file_sha256 ~ '^[0-9a-f]{64}$' AND file_metadata_sha256 ~ '^[0-9a-f]{64}$'", name="ck_release_member_hashes"),
        CheckConstraint("jsonb_typeof(snapshot) = 'object' AND octet_length(snapshot::text) <= 524288", name="ck_release_member_snapshot"),
    )


class CatalogReleaseState(ReleasesBase):
    __tablename__ = "catalog_release_states"
    release_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    entry_year: Mapped[int] = mapped_column(Integer, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(9), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    replaced_by_release_id: Mapped[UUID | None] = mapped_column(Uuid)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("release_id", "dataset_id", "entry_year", "is_synthetic"),
            (CatalogRelease.__table__.c.id, CatalogRelease.__table__.c.dataset_id,
             CatalogRelease.__table__.c.entry_year, CatalogRelease.__table__.c.is_synthetic),
            ondelete="RESTRICT", name="fk_release_state_scope"),
        ForeignKeyConstraint(("replaced_by_release_id", "dataset_id", "entry_year", "is_synthetic"),
            (CatalogRelease.__table__.c.id, CatalogRelease.__table__.c.dataset_id,
             CatalogRelease.__table__.c.entry_year, CatalogRelease.__table__.c.is_synthetic),
            ondelete="RESTRICT", name="fk_release_state_successor"),
        CheckConstraint("status IN ('published','withdrawn','replaced') AND revision BETWEEN 1 AND 2147483647", name="ck_release_state_revision"),
        CheckConstraint("(status = 'replaced' AND replaced_by_release_id IS NOT NULL AND replaced_by_release_id <> release_id) OR (status IN ('published','withdrawn') AND replaced_by_release_id IS NULL)", name="ck_release_state_successor"),
        Index("uq_release_current_published", "dataset_id", "entry_year", unique=True,
              postgresql_where=text("status = 'published'")),
    )


class ChangeEvent(ReleasesBase):
    __tablename__ = "catalog_change_events"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    release_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    entry_year: Mapped[int] = mapped_column(Integer, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    event_type: Mapped[str] = mapped_column(String(9), nullable=False)
    state_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    related_release_id: Mapped[UUID | None] = mapped_column(Uuid)
    reason_code: Mapped[str | None] = mapped_column(String(18))
    actor_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    audit_event_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("release_id", "dataset_id", "entry_year", "is_synthetic"),
            (CatalogRelease.__table__.c.id, CatalogRelease.__table__.c.dataset_id,
             CatalogRelease.__table__.c.entry_year, CatalogRelease.__table__.c.is_synthetic),
            ondelete="RESTRICT", name="fk_release_event_scope"),
        ForeignKeyConstraint(("related_release_id", "dataset_id", "entry_year", "is_synthetic"),
            (CatalogRelease.__table__.c.id, CatalogRelease.__table__.c.dataset_id,
             CatalogRelease.__table__.c.entry_year, CatalogRelease.__table__.c.is_synthetic),
            ondelete="RESTRICT", name="fk_release_event_related"),
        UniqueConstraint("release_id", "state_revision", name="uq_release_event_revision"),
        CheckConstraint("(event_type = 'published' AND state_revision = 1 AND related_release_id IS NULL AND reason_code IS NULL) OR (event_type = 'replaced' AND state_revision BETWEEN 2 AND 2147483647 AND related_release_id IS NOT NULL AND related_release_id <> release_id AND reason_code IS NULL) OR (event_type = 'withdrawn' AND state_revision BETWEEN 2 AND 2147483647 AND related_release_id IS NULL AND reason_code IS NOT NULL AND reason_code IN ('INCORRECT_FACT','RIGHTS_REVOKED','SOURCE_UNAVAILABLE','ADMIN_REQUEST'))", name="ck_release_event_shape"),
    )


class OutboxEvent(ReleasesBase):
    __tablename__ = "catalog_outbox"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(7), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("event_id",), (ChangeEvent.__table__.c.id,), ondelete="RESTRICT", name="fk_release_outbox_event"),
        UniqueConstraint("event_id", name="uq_release_outbox_event"),
        CheckConstraint("status = 'pending'", name="ck_release_outbox_pending"),
    )
