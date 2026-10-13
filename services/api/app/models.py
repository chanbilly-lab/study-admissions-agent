"""Scope and ownership are indexed columns; immutable wire snapshots use portable JSON."""

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class InstitutionRecord(Base):
    __tablename__ = "institutions"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    country: Mapped[str] = mapped_column(String(2))
    is_synthetic: Mapped[bool] = mapped_column(Boolean)


class OfferingRecord(Base):
    __tablename__ = "offerings"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"))
    country: Mapped[str] = mapped_column(String(2), index=True)
    entry_year: Mapped[int] = mapped_column(Integer, index=True)
    province: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    payload: Mapped[dict] = mapped_column(JSON)


class EvidenceRecord(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    document_version_id: Mapped[str] = mapped_column(String(100))
    document_sha256: Mapped[str] = mapped_column(String(64))
    raw_document: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)


class RuleRecord(Base):
    __tablename__ = "rules"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    offering_id: Mapped[str] = mapped_column(ForeignKey("offerings.id"), index=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"))
    version: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)


class ProfileVersionRecord(Base):
    __tablename__ = "profile_versions"
    __table_args__ = (UniqueConstraint("profile_id", "version", name="uq_profile_version"),)
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(100))
    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[int] = mapped_column(Integer)
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    payload: Mapped[dict] = mapped_column(JSON)


class EligibilityResultRecord(Base):
    __tablename__ = "eligibility_results"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    profile_version_id: Mapped[str] = mapped_column(ForeignKey("profile_versions.id"), index=True)
    offering_id: Mapped[str] = mapped_column(ForeignKey("offerings.id"))
    ruleset_version: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON)


class PlanDraftRecord(Base):
    __tablename__ = "plan_drafts"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(100), index=True)
    profile_version_id: Mapped[str] = mapped_column(ForeignKey("profile_versions.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
