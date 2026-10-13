"""Storage references are constrained to the existing ownership/source authorities."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..admin.sources.models import CatalogSource, CatalogSourceVersion
from ..auth.models import AuthOwnedResource


class StorageBase(DeclarativeBase):
    pass


class StorageObject(StorageBase):
    __tablename__ = "storage_objects"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    namespace: Mapped[str] = mapped_column(String(17), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(14), nullable=False)
    media_type: Mapped[str] = mapped_column(String(16), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    owner_user_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    owned_resource_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    resource_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dataset_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    source_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    source_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(("owned_resource_id", "owner_user_id"),
            (AuthOwnedResource.__table__.c.id, AuthOwnedResource.__table__.c.owner_user_id),
            ondelete="RESTRICT", name="fk_storage_private_resource_owner"),
        ForeignKeyConstraint(("dataset_id", "source_id", "source_version"),
            (CatalogSourceVersion.__table__.c.dataset_id, CatalogSourceVersion.__table__.c.source_id,
             CatalogSourceVersion.__table__.c.version), ondelete="RESTRICT", name="fk_storage_source_version"),
        ForeignKeyConstraint(("dataset_id", "source_id", "is_synthetic"),
            (CatalogSource.__table__.c.dataset_id, CatalogSource.__table__.c.id, CatalogSource.__table__.c.is_synthetic),
            ondelete="RESTRICT", name="fk_storage_source_mode"),
        CheckConstraint("namespace IN ('student_private', 'source_quarantine')", name="ck_storage_namespace"),
        CheckConstraint("status IN ('quarantined', 'delete_pending', 'deleted')", name="ck_storage_status"),
        CheckConstraint("media_type IN ('application/pdf', 'text/csv', 'application/json')", name="ck_storage_media_type"),
        CheckConstraint("size_bytes BETWEEN 1 AND 10485760", name="ck_storage_size"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_storage_hash"),
        CheckConstraint("expires_at > created_at AND expires_at <= "
                        "((created_at AT TIME ZONE 'UTC') + interval '24 months') AT TIME ZONE 'UTC'", name="ck_storage_expiry"),
        CheckConstraint("(namespace = 'student_private' AND owner_user_id IS NOT NULL AND "
                        "owned_resource_id IS NOT NULL AND resource_version IS NOT NULL AND "
                        "owned_resource_id = id AND resource_version > 0 AND "
                        "dataset_id IS NULL AND source_id IS NULL AND source_version IS NULL) OR "
                        "(namespace = 'source_quarantine' AND owner_user_id IS NULL AND "
                        "owned_resource_id IS NULL AND resource_version IS NULL AND "
                        "dataset_id IS NOT NULL AND source_id IS NOT NULL AND source_version IS NOT NULL "
                        "AND source_version BETWEEN 1 AND 2147483647)", name="ck_storage_reference_shape"),
        Index("ix_storage_owner_state", "owner_user_id", "status", "id"),
        Index("ix_storage_source_version", "dataset_id", "source_id", "source_version"),
        Index("ix_storage_expiry", "status", "expires_at"),
    )
