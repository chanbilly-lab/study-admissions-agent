"""Independent immutable source versions and scoped derivative snippets."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Integer,
                        String, Text, UniqueConstraint, Uuid)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..admin.sources.models import CatalogSource, CatalogSourceVersion
from ..admissions_catalog.models import AdmissionOffering, AdmissionOfferingVersion
from ..storage.models import StorageObject


class EvidenceBase(DeclarativeBase):
    pass


class Document(EvidenceBase):
    __tablename__ = "evidence_documents"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_version: Mapped[int] = mapped_column(Integer, nullable=False)
    document_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    language: Mapped[str] = mapped_column(String(7), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("dataset_id", "source_id", "source_version"),
            (CatalogSourceVersion.__table__.c.dataset_id, CatalogSourceVersion.__table__.c.source_id,
             CatalogSourceVersion.__table__.c.version), ondelete="RESTRICT", name="fk_evidence_document_source_version"),
        ForeignKeyConstraint(("dataset_id", "source_id", "is_synthetic"),
            (CatalogSource.__table__.c.dataset_id, CatalogSource.__table__.c.id,
             CatalogSource.__table__.c.is_synthetic), ondelete="RESTRICT", name="fk_evidence_document_source_mode"),
        UniqueConstraint("id", "dataset_id", "is_synthetic", name="uq_evidence_document_parent"),
        UniqueConstraint("dataset_id", "source_id", "source_version", "document_reference", name="uq_evidence_document_reference"),
        CheckConstraint("source_version BETWEEN 1 AND 2147483647 AND current_version BETWEEN 0 AND 2147483647", name="ck_evidence_document_versions"),
        CheckConstraint("document_reference ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$'", name="ck_evidence_document_reference"),
        CheckConstraint("(is_synthetic AND left(document_reference,5) = 'DEMO_') OR (NOT is_synthetic AND upper(left(document_reference,5)) <> 'DEMO_')", name="ck_evidence_document_namespace"),
        CheckConstraint("language IN ('zh-Hans','zh-Hant','en','und')", name="ck_evidence_document_language"),
    )


class DocumentVersion(EvidenceBase):
    __tablename__ = "evidence_document_versions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    document_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    file_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    document_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str] = mapped_column(String(16), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("document_id", "dataset_id", "is_synthetic"),
            (Document.__table__.c.id, Document.__table__.c.dataset_id, Document.__table__.c.is_synthetic),
            ondelete="RESTRICT", name="fk_evidence_version_document"),
        ForeignKeyConstraint(("file_id",), (StorageObject.__table__.c.id,), ondelete="RESTRICT", name="fk_evidence_version_file"),
        UniqueConstraint("document_id", "version", name="uq_evidence_document_version"),
        UniqueConstraint("document_id", "document_sha256", name="uq_evidence_document_hash"),
        UniqueConstraint("document_id", "version", "dataset_id", "is_synthetic", name="uq_evidence_version_parent"),
        CheckConstraint("version BETWEEN 1 AND 2147483647", name="ck_evidence_version_number"),
        CheckConstraint("document_sha256 ~ '^[0-9a-f]{64}$'", name="ck_evidence_version_hash"),
        CheckConstraint("size_bytes BETWEEN 1 AND 1048576 AND media_type IN ('application/json','text/csv')", name="ck_evidence_version_file"),
    )


class EvidenceSnippet(EvidenceBase):
    __tablename__ = "evidence_snippets"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    document_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    document_version: Mapped[int] = mapped_column(Integer, nullable=False)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    offering_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    offering_version: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_year: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(7), nullable=False)
    byte_start: Mapped[int] = mapped_column(Integer, nullable=False)
    byte_end: Mapped[int] = mapped_column(Integer, nullable=False)
    line_start: Mapped[int] = mapped_column(Integer, nullable=False)
    line_end: Mapped[int] = mapped_column(Integer, nullable=False)
    snippet_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("document_id", "document_version", "dataset_id", "is_synthetic"),
            (DocumentVersion.__table__.c.document_id, DocumentVersion.__table__.c.version,
             DocumentVersion.__table__.c.dataset_id, DocumentVersion.__table__.c.is_synthetic),
            ondelete="RESTRICT", name="fk_evidence_snippet_document_version"),
        ForeignKeyConstraint(("dataset_id", "offering_id", "offering_version"),
            (AdmissionOfferingVersion.__table__.c.dataset_id, AdmissionOfferingVersion.__table__.c.offering_id,
             AdmissionOfferingVersion.__table__.c.version), ondelete="RESTRICT", name="fk_evidence_snippet_offering_version"),
        ForeignKeyConstraint(("dataset_id", "offering_id", "is_synthetic"),
            (AdmissionOffering.__table__.c.dataset_id, AdmissionOffering.__table__.c.id,
             AdmissionOffering.__table__.c.is_synthetic), ondelete="RESTRICT", name="fk_evidence_snippet_offering_mode"),
        UniqueConstraint("document_id", "document_version", "offering_id", "offering_version", "byte_start", "byte_end", name="uq_evidence_snippet_span"),
        CheckConstraint("document_version BETWEEN 1 AND 2147483647 AND offering_version BETWEEN 1 AND 2147483647 AND entry_year BETWEEN 1 AND 9999", name="ck_evidence_snippet_scope"),
        CheckConstraint("byte_start >= 0 AND byte_end > byte_start AND byte_end <= 1048576 AND byte_end - byte_start <= 4096", name="ck_evidence_snippet_bytes"),
        CheckConstraint("line_start >= 1 AND line_end >= line_start AND line_end <= 1048576", name="ck_evidence_snippet_lines"),
        CheckConstraint("octet_length(text) = byte_end - byte_start AND octet_length(text) BETWEEN 1 AND 4096", name="ck_evidence_snippet_text"),
        CheckConstraint("snippet_sha256 ~ '^[0-9a-f]{64}$' AND scope_sha256 ~ '^[0-9a-f]{64}$'", name="ck_evidence_snippet_hashes"),
        CheckConstraint("language IN ('zh-Hans','zh-Hant','en','und')", name="ck_evidence_snippet_language"),
    )
