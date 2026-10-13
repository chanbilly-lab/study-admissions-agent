"""Independent append-only source metadata; authorization belongs to the service."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ...admissions_catalog.models import CatalogDataset, exact_text, reference_checks


class SourceBase(DeclarativeBase):
    pass


class CatalogSource(SourceBase):
    __tablename__ = "catalog_sources"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    reference_key: Mapped[str] = mapped_column(exact_text(100), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("dataset_id", "is_synthetic"),
                             (CatalogDataset.__table__.c.id, CatalogDataset.__table__.c.is_synthetic),
                             ondelete="RESTRICT", name="fk_catalog_source_dataset"),
        UniqueConstraint("dataset_id", "id", "is_synthetic", name="uq_catalog_source_parent"),
        UniqueConstraint("dataset_id", "reference_key", name="uq_catalog_source_reference"),
        CheckConstraint("current_version BETWEEN 1 AND 2147483647", name="ck_catalog_source_current_version"),
        *reference_checks("catalog_source"),
    )


class CatalogSourceVersion(SourceBase):
    __tablename__ = "catalog_source_versions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    source_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publisher: Mapped[str] = mapped_column(exact_text(200), nullable=False)
    entry_url: Mapped[str] = mapped_column(exact_text(2048), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_note: Mapped[str] = mapped_column(String(1000), nullable=False)
    authority_claim: Mapped[str] = mapped_column(String(16), nullable=False)
    manual_import_permission: Mapped[str] = mapped_column(String(7), nullable=False)
    publication_permission: Mapped[str] = mapped_column(String(7), nullable=False)
    automated_fetch_permission: Mapped[str] = mapped_column(String(7), nullable=False)
    license_basis: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    permission_record_reference: Mapped[str | None] = mapped_column(exact_text(100), nullable=True)
    recheck_days: Mapped[int] = mapped_column(Integer, nullable=False)
    manual_import_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    responsible_user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    permission_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recheck_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    auto_fetch_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("dataset_id", "source_id", "is_synthetic"),
                             ("catalog_sources.dataset_id", "catalog_sources.id", "catalog_sources.is_synthetic"),
                             ondelete="RESTRICT", name="fk_catalog_source_version_root"),
        UniqueConstraint("dataset_id", "source_id", "version", name="uq_catalog_source_version"),
        CheckConstraint("version BETWEEN 1 AND 2147483647", name="ck_catalog_source_version"),
        CheckConstraint("length(publisher) BETWEEN 1 AND 200", name="ck_catalog_source_publisher"),
        CheckConstraint("(is_synthetic = true AND substr(publisher, 1, 5) = 'DEMO_') OR "
                        "(is_synthetic = false AND upper(substr(publisher, 1, 5)) <> 'DEMO_')", name="ck_catalog_source_publisher_synthetic"),
        CheckConstraint("length(entry_url) BETWEEN 1 AND 2048 AND entry_url ~* '^https?://' "
                        "AND entry_url !~ '[[:space:]\\\\#]'", name="ck_catalog_source_url"),
        CheckConstraint("purpose = 'admissions_reference'", name="ck_catalog_source_purpose"),
        CheckConstraint("data_type IN ('entry_requirements', 'application_dates', 'regional_cutoffs', "
                        "'admission_observations', 'curriculum', 'outcomes', 'institution_directory')", name="ck_catalog_source_data_type"),
        CheckConstraint("length(scope_note) BETWEEN 1 AND 1000", name="ck_catalog_source_scope_note"),
        CheckConstraint("authority_claim IN ('unclassified', 'claimed_official', 'not_official')", name="ck_catalog_source_authority"),
        *(CheckConstraint(f"{field} IN ('pending', 'denied', 'granted')", name=f"ck_catalog_source_{field}")
          for field in ("manual_import_permission", "publication_permission", "automated_fetch_permission")),
        CheckConstraint("(manual_import_permission = 'pending' AND publication_permission = 'pending' AND "
                        "automated_fetch_permission = 'pending' AND license_basis IS NULL AND permission_record_reference IS NULL "
                        "AND permission_reviewed_at IS NULL) OR "
                        "((manual_import_permission <> 'pending' OR publication_permission <> 'pending' OR "
                        "automated_fetch_permission <> 'pending') AND license_basis IS NOT NULL AND "
                        "permission_record_reference IS NOT NULL AND permission_reviewed_at IS NOT NULL "
                        "AND permission_reviewed_at = created_at)", name="ck_catalog_source_permission_basis"),
        CheckConstraint("license_basis IS NULL OR length(license_basis) BETWEEN 1 AND 2000", name="ck_catalog_source_license_basis"),
        CheckConstraint("permission_record_reference IS NULL OR "
                        "permission_record_reference ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$'", name="ck_catalog_source_permission_reference"),
        CheckConstraint("permission_record_reference IS NULL OR "
                        "(is_synthetic = true AND substr(permission_record_reference, 1, 5) = 'DEMO_') OR "
                        "(is_synthetic = false AND upper(substr(permission_record_reference, 1, 5)) <> 'DEMO_')", name="ck_catalog_source_permission_synthetic"),
        CheckConstraint("recheck_days BETWEEN 1 AND 730", name="ck_catalog_source_recheck_days"),
        CheckConstraint("recheck_due_at > created_at AND recheck_due_at = "
                        "least(((created_at AT TIME ZONE 'UTC') + recheck_days * interval '1 day') AT TIME ZONE 'UTC', "
                        "((created_at AT TIME ZONE 'UTC') + interval '24 months') AT TIME ZONE 'UTC')", name="ck_catalog_source_recheck_due"),
        CheckConstraint("manual_import_enabled = false OR manual_import_permission = 'granted'", name="ck_catalog_source_manual_enabled"),
        CheckConstraint("auto_fetch_enabled = false", name="ck_catalog_source_no_fetch"),
    )
