"""Append-only date candidates in the caller's catalog transaction."""

from contextlib import contextmanager
from datetime import timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .date_models import CatalogDateEvent
from .date_schemas import DateEventData, DateEventInput
from .dates import normalize_date_event
from .models import AdmissionOffering, AdmissionOfferingVersion
from .store import CATALOG_HEAD, CatalogStore, CatalogStoreError, _input, _uuid


class DateEventStore(CatalogStore):
    def assert_schema_ready(self, required_head: str = CATALOG_HEAD) -> None:
        if required_head not in {"0002_catalog_dates_t12", CATALOG_HEAD}:
            raise CatalogStoreError()
        super().assert_schema_ready(required_head=required_head)

    @contextmanager
    def _work(self, session):
        with super()._work(session):
            bind = session.get_bind(mapper=CatalogDateEvent)
            if getattr(bind, "engine", bind) is not self.engine:
                raise CatalogStoreError()
            yield

    @staticmethod
    def _date_output(session, row) -> DateEventData:
        parent = session.execute(select(AdmissionOffering).where(
            AdmissionOffering.id == row.offering_id, AdmissionOffering.dataset_id == row.dataset_id,
            AdmissionOffering.is_synthetic == row.is_synthetic)
            .execution_options(populate_existing=True)).scalar_one_or_none()
        if parent is None:
            raise CatalogStoreError()
        fields = {column.name: getattr(row, column.name) for column in row.__table__.columns}
        fields["entry_year"] = parent.entry_year
        candidate = fields["calculated_utc_instant"]
        if candidate is not None:
            if candidate.tzinfo is None or candidate.utcoffset() is None:
                raise CatalogStoreError()
            fields["calculated_utc_instant"] = candidate.astimezone(timezone.utc)
        try:
            # Data re-runs the pinned conversion; mismatch never repairs a row.
            return DateEventData.model_validate(fields)
        except (ValidationError, ValueError, TypeError):
            raise CatalogStoreError() from None

    def create_date_event(self, session: Session, data: DateEventInput, *, expected_dataset_revision: int) -> DateEventData:
        data = _input(DateEventInput, data)
        resolution = normalize_date_event(data)
        with self._work(session):
            dataset = self._dataset(session, data.dataset_id, expected_revision=expected_dataset_revision)
            self._matching_mode(dataset, data)
            offering = self._parent(session, AdmissionOffering, data.offering_id, data.dataset_id, data.is_synthetic)
            if offering.entry_year != data.entry_year:
                raise CatalogStoreError(409, "CATALOG_CONFLICT")
            version = session.execute(select(AdmissionOfferingVersion).where(
                AdmissionOfferingVersion.dataset_id == data.dataset_id,
                AdmissionOfferingVersion.offering_id == data.offering_id,
                AdmissionOfferingVersion.version == data.offering_version,
                AdmissionOfferingVersion.is_synthetic == data.is_synthetic)
                .with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
            if version is None:
                raise CatalogStoreError(404, "NOT_FOUND")
            self._advance(dataset)
            row = CatalogDateEvent(**data.model_dump(exclude={"entry_year"}), **resolution.model_dump(),
                                   utc_instant=None, review_state="draft", evidence_state="unresolved")
            session.add(row)
            session.flush()
            return self._date_output(session, row)

    def get_date_event(self, session: Session, identifier: UUID) -> DateEventData:
        identifier = _uuid(identifier)
        with self._work(session):
            row = session.execute(select(CatalogDateEvent).where(CatalogDateEvent.id == identifier)
                .execution_options(populate_existing=True)).scalar_one_or_none()
            if row is None:
                raise CatalogStoreError(404, "NOT_FOUND")
            return self._date_output(session, row)
