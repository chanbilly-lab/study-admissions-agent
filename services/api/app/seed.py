"""Idempotent, offline import of immutable DEMO fixtures. Private profiles are never seeded."""
from hashlib import sha256
import json
from pathlib import Path

from sqlalchemy.orm import Session

from .database import make_engine
from .models import EvidenceRecord, InstitutionRecord, OfferingRecord, RuleRecord
from .schemas import Evidence, Institution, Offering
from .settings import Settings, assert_m0_allowed

FIXTURE_PATH = Path(__file__).resolve().parents[3] / "data" / "fixtures" / "demo_catalog.json"


def seed(engine, fixture_path=FIXTURE_PATH):
    assert_m0_allowed()
    # Retain M0 dotenv conflict validation even when the caller supplies an engine.
    Settings()
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    if fixture.get("is_synthetic") is not True:
        raise ValueError("Only explicitly synthetic fixtures may be imported in M0")
    institutions = [Institution.model_validate(item) for item in fixture["institutions"]]
    documents = [(Evidence.model_validate(item["evidence"]), item["raw_document"]) for item in fixture["documents"]]
    offerings = [Offering.model_validate(item) for item in fixture["offerings"]]
    for evidence, raw in documents:
        if sha256(raw.encode("utf-8")).hexdigest() != evidence.document_sha256 or evidence.excerpt not in raw:
            raise ValueError(f"Invalid original-document hash or excerpt: {evidence.id}")
    inserted = {"institutions": 0, "evidence": 0, "offerings": 0, "rules": 0}

    def add_immutable(session, record, group):
        existing = session.get(type(record), record.id)
        if existing is None:
            session.add(record)
            inserted[group] += 1
        else:
            for column in record.__table__.columns:
                if getattr(existing, column.name) != getattr(record, column.name):
                    raise ValueError(f"Immutable fixture conflict for {record.id}; existing data preserved")

    with Session(engine) as session, session.begin():
        for item in institutions:
            add_immutable(session, InstitutionRecord(**item.model_dump()), "institutions")
        session.flush()
        for item, raw in documents:
            add_immutable(session, EvidenceRecord(id=item.id, document_version_id=item.document_version_id,
                                                 document_sha256=item.document_sha256, raw_document=raw,
                                                 payload=item.model_dump(mode="json")), "evidence")
        session.flush()
        for item in offerings:
            # Rules have separate versioned records, not a duplicated source of truth in catalog payloads.
            payload = item.model_dump(mode="json")
            payload["rules"] = []
            add_immutable(session, OfferingRecord(id=item.id, institution_id=item.institution_id,
                                                 country=item.country, entry_year=item.entry_year, province=item.province,
                                                 is_synthetic=True, payload=payload), "offerings")
        session.flush()
        for item in offerings:
            for rule in item.rules:
                add_immutable(session, RuleRecord(id=rule.id, offering_id=item.id, evidence_id=rule.evidence_id,
                                                 version=rule.version, payload=rule.model_dump(mode="json")), "rules")
    return inserted


if __name__ == "__main__":
    engine = make_engine(Settings())
    try:
        print(json.dumps(seed(engine), ensure_ascii=False))
    finally:
        engine.dispose()
