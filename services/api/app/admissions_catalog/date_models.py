"""Candidate dates use separate metadata, preserving the T11 five-table base."""

from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKeyConstraint, Integer, String, Text, Time, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .models import AdmissionOffering, AdmissionOfferingVersion, exact_text, reference_checks


class DatesBase(DeclarativeBase):
    pass


class CatalogDateEvent(DatesBase):
    __tablename__ = "catalog_date_events"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    offering_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    offering_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_key: Mapped[str] = mapped_column(exact_text(100), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    precision: Mapped[str] = mapped_column(String(7), nullable=False)
    local_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    local_time: Mapped[time | None] = mapped_column(Time(timezone=False), nullable=True)
    timezone: Mapped[str | None] = mapped_column(exact_text(100), nullable=True)
    source_alignment: Mapped[str] = mapped_column(String(8), nullable=False)
    evidence_reference: Mapped[str | None] = mapped_column(exact_text(100), nullable=True)
    conversion_status: Mapped[str] = mapped_column(String(20), nullable=False)
    calculated_utc_instant: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    utc_instant: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_state: Mapped[str] = mapped_column(String(5), nullable=False)
    evidence_state: Mapped[str] = mapped_column(String(10), nullable=False)
    tzdata_version: Mapped[str] = mapped_column(String(16), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("dataset_id", "offering_id", "offering_version"),
            (AdmissionOfferingVersion.__table__.c.dataset_id, AdmissionOfferingVersion.__table__.c.offering_id,
             AdmissionOfferingVersion.__table__.c.version), ondelete="RESTRICT", name="fk_catalog_date_version"),
        ForeignKeyConstraint(("dataset_id", "offering_id", "is_synthetic"),
            (AdmissionOffering.__table__.c.dataset_id, AdmissionOffering.__table__.c.id,
             AdmissionOffering.__table__.c.is_synthetic), ondelete="RESTRICT", name="fk_catalog_date_offering"),
        UniqueConstraint("dataset_id", "offering_id", "offering_version", "reference_key", name="uq_catalog_date_reference"),
        CheckConstraint("offering_version BETWEEN 1 AND 2147483647", name="ck_catalog_date_version"),
        CheckConstraint("event_type IN ('application_open', 'application_deadline', 'equal_consideration', "
                        "'materials_deadline', 'language_supplement', 'score_supplement', 'offer_acceptance', "
                        "'scholarship_deadline', 'enrollment')", name="ck_catalog_date_event_type"),
        CheckConstraint("length(original_text) BETWEEN 1 AND 4000", name="ck_catalog_date_original_text"),
        CheckConstraint("precision IN ('date', 'minute', 'second', 'unknown')", name="ck_catalog_date_precision"),
        CheckConstraint("(precision = 'unknown' AND local_date IS NULL AND local_time IS NULL AND timezone IS NULL) OR "
                        "(precision = 'date' AND local_date IS NOT NULL AND local_time IS NULL) OR "
                        "(precision IN ('minute', 'second') AND local_date IS NOT NULL AND local_time IS NOT NULL)",
                        name="ck_catalog_date_local_fields"),
        CheckConstraint("local_time IS NULL OR (local_time >= TIME '00:00:00' AND local_time < TIME '24:00:00' AND "
                        "((precision = 'minute' AND extract(second FROM local_time) = 0) OR "
                        "(precision = 'second' AND extract(second FROM local_time) = floor(extract(second FROM local_time)))))",
                        name="ck_catalog_date_time_precision"),
        CheckConstraint("timezone IS NULL OR (length(timezone) BETWEEN 1 AND 100 AND "
                        "(timezone = 'UTC' OR timezone ~ '^(Africa|America|Antarctica|Arctic|Asia|Atlantic|Australia|Europe|Indian|Pacific)/[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+)*$'))",
                        name="ck_catalog_date_timezone"),
        CheckConstraint("source_alignment IN ('pending', 'conflict')", name="ck_catalog_date_source_alignment"),
        CheckConstraint("evidence_reference IS NULL OR "
                        "evidence_reference ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$'", name="ck_catalog_date_evidence_reference"),
        CheckConstraint("evidence_reference IS NULL OR "
                        "(is_synthetic = true AND substr(evidence_reference, 1, 5) = 'DEMO_') OR "
                        "(is_synthetic = false AND upper(substr(evidence_reference, 1, 5)) <> 'DEMO_')",
                        name="ck_catalog_date_evidence_synthetic"),
        CheckConstraint("conversion_status IN ('unique', 'date_only', 'unknown', 'missing_timezone', 'ambiguous', "
                        "'nonexistent', 'source_conflict', 'out_of_range')", name="ck_catalog_date_conversion_status"),
        CheckConstraint("(source_alignment = 'conflict' AND conversion_status = 'source_conflict' AND calculated_utc_instant IS NULL) OR "
                        "(source_alignment = 'pending' AND conversion_status <> 'source_conflict')", name="ck_catalog_date_conflict"),
        CheckConstraint("(conversion_status = 'unique' AND calculated_utc_instant IS NOT NULL AND "
                        "precision IN ('minute', 'second') AND local_date IS NOT NULL AND local_time IS NOT NULL AND timezone IS NOT NULL) OR "
                        "(conversion_status <> 'unique' AND calculated_utc_instant IS NULL)", name="ck_catalog_date_calculated_utc"),
        CheckConstraint("utc_instant IS NULL AND review_state = 'draft' AND evidence_state = 'unresolved'",
                        name="ck_catalog_date_unreviewed"),
        CheckConstraint("tzdata_version = '2026.4'", name="ck_catalog_date_tzdata_version"),
        *reference_checks("catalog_date"),
    )
