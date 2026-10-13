"""Independent immutable candidates and append-only historical conflict edges."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKeyConstraint,
                        Index, Integer, String, UniqueConstraint, Uuid)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..admin.imports.models import ImportBatch, ImportCandidateRow
from ..admissions_catalog.date_models import CatalogDateEvent
from ..admissions_catalog.models import AdmissionOffering, AdmissionOfferingVersion
from ..evidence.models import EvidenceSnippet


class FactsBase(DeclarativeBase):
    pass


class FactCandidate(FactsBase):
    __tablename__ = "fact_candidates"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    import_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    import_row_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    offering_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    offering_version: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_year: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_id: Mapped[UUID | None] = mapped_column(Uuid)
    date_event_id: Mapped[UUID | None] = mapped_column(Uuid)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    classification_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    natural_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    logical_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    value_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    row_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    date_sha256: Mapped[str | None] = mapped_column(String(64))
    evidence_sha256: Mapped[str | None] = mapped_column(String(64))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("import_id", "dataset_id", "is_synthetic"),
            (ImportBatch.__table__.c.id, ImportBatch.__table__.c.dataset_id,
             ImportBatch.__table__.c.is_synthetic), ondelete="RESTRICT", name="fk_fact_batch_mode"),
        ForeignKeyConstraint(("import_row_id",), (ImportCandidateRow.__table__.c.id,),
            ondelete="RESTRICT", name="fk_fact_import_row"),
        ForeignKeyConstraint(("dataset_id", "offering_id", "offering_version"),
            (AdmissionOfferingVersion.__table__.c.dataset_id, AdmissionOfferingVersion.__table__.c.offering_id,
             AdmissionOfferingVersion.__table__.c.version), ondelete="RESTRICT", name="fk_fact_offering_version"),
        ForeignKeyConstraint(("dataset_id", "offering_id", "is_synthetic"),
            (AdmissionOffering.__table__.c.dataset_id, AdmissionOffering.__table__.c.id,
             AdmissionOffering.__table__.c.is_synthetic), ondelete="RESTRICT", name="fk_fact_offering_mode"),
        ForeignKeyConstraint(("evidence_id",), (EvidenceSnippet.__table__.c.id,),
            ondelete="RESTRICT", name="fk_fact_evidence"),
        ForeignKeyConstraint(("date_event_id",), (CatalogDateEvent.__table__.c.id,),
            ondelete="RESTRICT", name="fk_fact_date"),
        UniqueConstraint("natural_key_hash", name="uq_fact_natural"),
        UniqueConstraint("id", "logical_key_hash", name="uq_fact_conflict_parent"),
        CheckConstraint("version = 1 AND offering_version BETWEEN 1 AND 2147483647 AND entry_year BETWEEN 1 AND 9999", name="ck_fact_versions"),
        CheckConstraint("jsonb_typeof(payload) = 'object' AND octet_length(payload::text) <= 262144", name="ck_fact_payload"),
        CheckConstraint("classification_hash ~ '^[0-9a-f]{64}$' AND natural_key_hash ~ '^[0-9a-f]{64}$' AND logical_key_hash ~ '^[0-9a-f]{64}$' AND value_hash ~ '^[0-9a-f]{64}$' AND row_sha256 ~ '^[0-9a-f]{64}$' AND scope_sha256 ~ '^[0-9a-f]{64}$'", name="ck_fact_hashes"),
        CheckConstraint("(date_event_id IS NULL AND date_sha256 IS NULL) OR (date_event_id IS NOT NULL AND date_sha256 IS NOT NULL AND date_sha256 ~ '^[0-9a-f]{64}$')", name="ck_fact_date_hash"),
        CheckConstraint("(evidence_id IS NULL AND evidence_sha256 IS NULL) OR (evidence_id IS NOT NULL AND evidence_sha256 IS NOT NULL AND evidence_sha256 ~ '^[0-9a-f]{64}$')", name="ck_fact_evidence_hash"),
        Index("ix_fact_logical_key", "logical_key_hash", "id"),
    )


class FactConflict(FactsBase):
    __tablename__ = "fact_conflicts"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    left_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    right_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    logical_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("left_id", "logical_key_hash"),
            (FactCandidate.__table__.c.id, FactCandidate.__table__.c.logical_key_hash),
            ondelete="RESTRICT", name="fk_fact_conflict_left"),
        ForeignKeyConstraint(("right_id", "logical_key_hash"),
            (FactCandidate.__table__.c.id, FactCandidate.__table__.c.logical_key_hash),
            ondelete="RESTRICT", name="fk_fact_conflict_right"),
        UniqueConstraint("left_id", "right_id", name="uq_fact_conflict_pair"),
        CheckConstraint("left_id < right_id AND logical_key_hash ~ '^[0-9a-f]{64}$'", name="ck_fact_conflict_pair"),
        Index("ix_fact_conflict_right", "right_id", "left_id"),
    )
