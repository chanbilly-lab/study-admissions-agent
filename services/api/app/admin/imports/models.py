"""Independent import snapshots; staged values are never reviewed facts."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Index,
                        Integer, String, Text, UniqueConstraint, Uuid)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..sources.models import CatalogSource, CatalogSourceVersion
from ...admissions_catalog.models import AdmissionOffering, AdmissionOfferingVersion
from ...storage.models import StorageObject


class ImportsBase(DeclarativeBase):
    pass


class ImportBatch(ImportsBase):
    __tablename__ = "import_batches"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    file_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String(4), nullable=False)
    parser_schema_version: Mapped[str] = mapped_column(String(6), nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    total_rows: Mapped[int | None] = mapped_column(Integer)
    staged_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("dataset_id", "source_id", "source_version"),
            (CatalogSourceVersion.__table__.c.dataset_id, CatalogSourceVersion.__table__.c.source_id,
             CatalogSourceVersion.__table__.c.version), ondelete="RESTRICT", name="fk_import_source_version"),
        ForeignKeyConstraint(("dataset_id", "source_id", "is_synthetic"),
            (CatalogSource.__table__.c.dataset_id, CatalogSource.__table__.c.id,
             CatalogSource.__table__.c.is_synthetic), ondelete="RESTRICT", name="fk_import_source_mode"),
        ForeignKeyConstraint(("file_id",), (StorageObject.__table__.c.id,), ondelete="RESTRICT", name="fk_import_file"),
        UniqueConstraint("dataset_id", "source_id", "source_version", "file_sha256", "format",
                         "parser_schema_version", name="uq_import_natural_content"),
        UniqueConstraint("id", "dataset_id", "is_synthetic", name="uq_import_candidate_parent"),
        CheckConstraint("source_version BETWEEN 1 AND 2147483647 AND version = 1", name="ck_import_versions"),
        CheckConstraint("file_sha256 ~ '^[0-9a-f]{64}$' AND file_size BETWEEN 1 AND 1048576", name="ck_import_file"),
        CheckConstraint("format IN ('json','csv') AND parser_schema_version = 'T15_v1'", name="ck_import_format"),
        CheckConstraint("status IN ('staged','rejected','deleted')", name="ck_import_status"),
        CheckConstraint("(total_rows IS NULL OR total_rows BETWEEN 0 AND 200) AND staged_rows BETWEEN 0 AND 200 AND error_count BETWEEN 0 AND 2800", name="ck_import_counts"),
        CheckConstraint("status = 'deleted' OR (status = 'staged' AND total_rows IS NOT NULL AND total_rows > 0 AND staged_rows = total_rows AND error_count = 0) OR (status = 'rejected' AND staged_rows = 0 AND error_count > 0)", name="ck_import_result"),
        Index("ix_import_actor_created", "actor_user_id", "created_at", "id"),
    )


class ImportCandidateRow(ImportsBase):
    __tablename__ = "import_candidate_rows"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    import_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    offering_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    offering_version: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_year: Mapped[int] = mapped_column(Integer, nullable=False)
    source_record_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    fact_type: Mapped[str] = mapped_column(String(11), nullable=False)
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    value_kind: Mapped[str] = mapped_column(String(7), nullable=False)
    value_text: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(Text)
    missing_reason: Mapped[str | None] = mapped_column(String(32))
    footnote_state: Mapped[str] = mapped_column(String(7), nullable=False)
    footnote_text: Mapped[str | None] = mapped_column(Text)
    locator: Mapped[str | None] = mapped_column(Text)
    review_state: Mapped[str] = mapped_column(String(5), nullable=False)
    evidence_state: Mapped[str] = mapped_column(String(10), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("import_id", "dataset_id", "is_synthetic"),
            (ImportBatch.__table__.c.id, ImportBatch.__table__.c.dataset_id, ImportBatch.__table__.c.is_synthetic),
            ondelete="RESTRICT", name="fk_import_row_batch_mode"),
        ForeignKeyConstraint(("dataset_id", "offering_id", "offering_version"),
            (AdmissionOfferingVersion.__table__.c.dataset_id, AdmissionOfferingVersion.__table__.c.offering_id,
             AdmissionOfferingVersion.__table__.c.version), ondelete="RESTRICT", name="fk_import_row_offering_version"),
        ForeignKeyConstraint(("dataset_id", "offering_id", "is_synthetic"),
            (AdmissionOffering.__table__.c.dataset_id, AdmissionOffering.__table__.c.id,
             AdmissionOffering.__table__.c.is_synthetic), ondelete="RESTRICT", name="fk_import_row_offering_mode"),
        UniqueConstraint("import_id", "row_number", name="uq_import_row_number"),
        CheckConstraint("row_number BETWEEN 1 AND 201 AND entry_year BETWEEN 1 AND 9999 AND offering_version BETWEEN 1 AND 2147483647", name="ck_import_row_scope"),
        CheckConstraint("fact_type IN ('requirement','score','fee','material','date','statistic') AND value_kind IN ('text','decimal')", name="ck_import_row_type"),
        CheckConstraint("source_record_reference ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$' AND field_key ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$'", name="ck_import_row_identifiers"),
        CheckConstraint("(is_synthetic AND left(source_record_reference,5) = 'DEMO_') OR (NOT is_synthetic AND upper(left(source_record_reference,5)) <> 'DEMO_')", name="ck_import_row_namespace"),
        CheckConstraint("(value_text IS NULL AND missing_reason IS NOT NULL) OR (value_text IS NOT NULL AND missing_reason IS NULL)", name="ck_import_row_missing"),
        CheckConstraint("missing_reason IS NULL OR missing_reason IN ('not_provided','not_applicable','not_published','unavailable','ambiguous')", name="ck_import_row_missing_reason"),
        CheckConstraint("value_text IS NULL OR (octet_length(value_text) BETWEEN 1 AND 4096 AND (value_kind <> 'decimal' OR (length(value_text) <= 64 AND value_text ~ '^-?(0|[1-9][0-9]*)([.][0-9]+)?$')))", name="ck_import_row_value"),
        CheckConstraint("(unit IS NULL OR octet_length(unit) BETWEEN 1 AND 4096) AND (footnote_text IS NULL OR octet_length(footnote_text) BETWEEN 1 AND 4096) AND (locator IS NULL OR octet_length(locator) BETWEEN 1 AND 4096)", name="ck_import_row_text"),
        CheckConstraint("(footnote_state = 'present' AND footnote_text IS NOT NULL) OR (footnote_state IN ('none','unknown') AND footnote_text IS NULL)", name="ck_import_row_footnote"),
        CheckConstraint("review_state = 'draft' AND evidence_state = 'unresolved'", name="ck_import_row_unreviewed"),
    )


class ImportRowError(ImportsBase):
    __tablename__ = "import_row_errors"
    import_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    row_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    field: Mapped[str] = mapped_column(String(23), primary_key=True)
    code: Mapped[str] = mapped_column(String(24), primary_key=True)
    __table_args__ = (
        ForeignKeyConstraint(("import_id",), (ImportBatch.__table__.c.id,), ondelete="RESTRICT", name="fk_import_error_batch"),
        CheckConstraint("row_number BETWEEN 0 AND 201", name="ck_import_error_row"),
        CheckConstraint("field IN ('document','offering_id','offering_version','entry_year','source_record_reference','fact_type','field_key','value_kind','value_text','unit','missing_reason','footnote_state','footnote_text','locator')", name="ck_import_error_field"),
        CheckConstraint("code IN ('INVALID_ENCODING','INPUT_TOO_LARGE','INVALID_STRUCTURE','EMPTY_IMPORT','TOO_MANY_ROWS','INVALID_HEADER','DUPLICATE_KEY','MISSING_FIELD','UNEXPECTED_FIELD','INVALID_FIELD','FIELD_TOO_LARGE','INVALID_INTEGER','INVALID_UUID','INVALID_DECIMAL','MISSING_VALUE_REASON','INVALID_FOOTNOTE','SCOPE_MISMATCH','NAMESPACE_MISMATCH')", name="ck_import_error_code"),
    )
