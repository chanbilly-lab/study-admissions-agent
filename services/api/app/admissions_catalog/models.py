"""Independent candidate metadata; M0 and authentication metadata stay separate."""

from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKeyConstraint, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class CatalogBase(DeclarativeBase):
    pass


def exact_text(length: int):
    return String(length).with_variant(String(length, collation="C"), "postgresql")


def reference_checks(prefix: str, *, name: bool = False):
    fields = ("reference_key", "name") if name else ("reference_key",)
    checks = []
    for field in fields:
        maximum = 200 if field == "name" else 100
        checks.append(CheckConstraint(f"length({field}) BETWEEN 1 AND {maximum}",
                                      name=f"ck_{prefix}_{field}_length"))
        checks.append(CheckConstraint(
            f"(is_synthetic = true AND substr({field}, 1, 5) = 'DEMO_') OR "
            f"(is_synthetic = false AND upper(substr({field}, 1, 5)) <> 'DEMO_')",
            name=f"ck_{prefix}_{field}_synthetic"))
    checks.append(CheckConstraint("reference_key ~ '^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$'",
                                  name=f"ck_{prefix}_reference_ascii").ddl_if(dialect="postgresql"))
    return tuple(checks)


def scope_checks(prefix: str, fields: tuple[str, ...]):
    checks = []
    for field in fields:
        column = f"{field}_key"
        checks.append(CheckConstraint(
            f"length({column}) BETWEEN 1 AND 106 AND "
            f"({column} IN ('unknown', 'not_applicable') OR "
            f"(substr({column}, 1, 6) = 'known:' AND length({column}) > 6))",
            name=f"ck_{prefix}_{field}_key"))
        checks.append(CheckConstraint(
            f"octet_length({column}) <= 106 AND "
            f"{column} ~ '^(unknown|not_applicable|known:[A-Za-z0-9][A-Za-z0-9_.:+-]{{0,99}})$'",
            name=f"ck_{prefix}_{field}_ascii").ddl_if(dialect="postgresql"))
    return tuple(checks)


PROGRAM_SCOPE_FIELDS = ("degree", "course", "campus", "teaching_language", "progression_pathway")
OFFERING_SCOPE_FIELDS = ("intake", "application_cycle", "channel", "course_system", "pathway",
                         "applicant_category", "province", "exam_system", "subject_scope", "batch_group")


class CatalogDataset(CatalogBase):
    __tablename__ = "catalog_datasets"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    reference_key: Mapped[str] = mapped_column(exact_text(100), nullable=False)
    data_mode: Mapped[str] = mapped_column(String(8), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    visibility: Mapped[str] = mapped_column(String(7), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        UniqueConstraint("reference_key", name="uq_catalog_dataset_reference"),
        UniqueConstraint("id", "is_synthetic", name="uq_catalog_dataset_mode"),
        CheckConstraint("(data_mode = 'demo' AND is_synthetic = true) OR "
                        "(data_mode = 'verified' AND is_synthetic = false)", name="ck_catalog_dataset_mode"),
        CheckConstraint("visibility = 'private'", name="ck_catalog_dataset_visibility"),
        CheckConstraint("revision BETWEEN 1 AND 2147483647", name="ck_catalog_dataset_revision"),
        *reference_checks("catalog_dataset"),
    )


class CatalogInstitution(CatalogBase):
    __tablename__ = "catalog_institutions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    reference_key: Mapped[str] = mapped_column(exact_text(100), nullable=False)
    name: Mapped[str] = mapped_column(exact_text(200), nullable=False)
    country: Mapped[str] = mapped_column(exact_text(2), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("dataset_id", "is_synthetic"),
                             ("catalog_datasets.id", "catalog_datasets.is_synthetic"),
                             ondelete="RESTRICT", name="fk_catalog_institution_dataset"),
        UniqueConstraint("dataset_id", "id", "is_synthetic", name="uq_catalog_institution_parent"),
        UniqueConstraint("dataset_id", "reference_key", name="uq_catalog_institution_reference"),
        CheckConstraint("length(country) = 2 AND country = upper(country)", name="ck_catalog_institution_country"),
        CheckConstraint("country ~ '^[A-Z]{2}$'", name="ck_catalog_institution_country_ascii").ddl_if(dialect="postgresql"),
        *reference_checks("catalog_institution", name=True),
    )


class CatalogProgram(CatalogBase):
    __tablename__ = "catalog_programs"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    institution_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    reference_key: Mapped[str] = mapped_column(exact_text(100), nullable=False)
    name: Mapped[str] = mapped_column(exact_text(200), nullable=False)
    study_level: Mapped[str] = mapped_column(exact_text(16), nullable=False)
    degree_key: Mapped[str] = mapped_column(exact_text(106), nullable=False)
    course_key: Mapped[str] = mapped_column(exact_text(106), nullable=False)
    campus_key: Mapped[str] = mapped_column(exact_text(106), nullable=False)
    teaching_language_key: Mapped[str] = mapped_column(exact_text(106), nullable=False)
    progression_pathway_key: Mapped[str] = mapped_column(exact_text(106), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("dataset_id", "institution_id", "is_synthetic"),
                             ("catalog_institutions.dataset_id", "catalog_institutions.id", "catalog_institutions.is_synthetic"),
                             ondelete="RESTRICT", name="fk_catalog_program_institution"),
        UniqueConstraint("dataset_id", "id", "is_synthetic", name="uq_catalog_program_parent"),
        UniqueConstraint("dataset_id", "institution_id", "reference_key", "study_level",
                         *(f"{field}_key" for field in PROGRAM_SCOPE_FIELDS), name="uq_catalog_program_scope"),
        CheckConstraint("study_level = 'undergraduate'", name="ck_catalog_program_level"),
        *reference_checks("catalog_program", name=True),
        *scope_checks("catalog_program", PROGRAM_SCOPE_FIELDS),
    )


class AdmissionOffering(CatalogBase):
    __tablename__ = "catalog_offerings"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    program_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    reference_key: Mapped[str] = mapped_column(exact_text(100), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    entry_year: Mapped[int] = mapped_column(Integer, nullable=False)
    intake_key: Mapped[str] = mapped_column(exact_text(106), nullable=False)
    application_cycle_key: Mapped[str] = mapped_column(exact_text(106), nullable=False)
    channel_key: Mapped[str] = mapped_column(exact_text(106), nullable=False)
    course_system_key: Mapped[str] = mapped_column(exact_text(106), nullable=False)
    pathway_key: Mapped[str] = mapped_column(exact_text(106), nullable=False)
    applicant_category_key: Mapped[str] = mapped_column(exact_text(106), nullable=False)
    province_key: Mapped[str] = mapped_column(exact_text(106), nullable=False)
    exam_system_key: Mapped[str] = mapped_column(exact_text(106), nullable=False)
    subject_scope_key: Mapped[str] = mapped_column(exact_text(106), nullable=False)
    batch_group_key: Mapped[str] = mapped_column(exact_text(106), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("dataset_id", "program_id", "is_synthetic"),
                             ("catalog_programs.dataset_id", "catalog_programs.id", "catalog_programs.is_synthetic"),
                             ondelete="RESTRICT", name="fk_catalog_offering_program"),
        UniqueConstraint("dataset_id", "id", "is_synthetic", name="uq_catalog_offering_parent"),
        UniqueConstraint("dataset_id", "program_id", "entry_year",
                         *(f"{field}_key" for field in OFFERING_SCOPE_FIELDS), name="uq_catalog_offering_scope"),
        CheckConstraint("entry_year BETWEEN 1 AND 9999", name="ck_catalog_offering_year"),
        CheckConstraint("current_version BETWEEN 1 AND 2147483647", name="ck_catalog_offering_current_version"),
        *reference_checks("catalog_offering"),
        *scope_checks("catalog_offering", OFFERING_SCOPE_FIELDS),
    )


class AdmissionOfferingVersion(CatalogBase):
    __tablename__ = "catalog_offering_versions"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    offering_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(("dataset_id", "offering_id", "is_synthetic"),
                             ("catalog_offerings.dataset_id", "catalog_offerings.id", "catalog_offerings.is_synthetic"),
                             ondelete="RESTRICT", name="fk_catalog_version_offering"),
        UniqueConstraint("dataset_id", "offering_id", "version", name="uq_catalog_offering_version"),
        CheckConstraint("version BETWEEN 1 AND 2147483647", name="ck_catalog_offering_version"),
    )
