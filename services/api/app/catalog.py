from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from .models import OfferingRecord, RuleRecord
from .schemas import Offering


def read_offering(session: Session, record: OfferingRecord) -> Offering:
    payload = dict(record.payload)
    payload["rules"] = [item.payload for item in session.scalars(
        select(RuleRecord).where(RuleRecord.offering_id == record.id).order_by(RuleRecord.id)
    )]
    return Offering.model_validate(payload)


def catalog_list(session: Session, country, entry_year, province):
    statement = select(OfferingRecord).where(OfferingRecord.entry_year == entry_year)
    if country is not None:
        statement = statement.where(OfferingRecord.country == country)
    # GB applies to the confirmed applicant identity, not a Chinese recruitment province.
    statement = statement.where(or_(OfferingRecord.province == province, OfferingRecord.country == "GB"))
    return [read_offering(session, item) for item in session.scalars(statement.order_by(OfferingRecord.id))]
