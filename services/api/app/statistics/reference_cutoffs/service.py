"""Explicit local import/review and bounded SELECT-only reads; never networking."""

from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
import re
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from .models import CutoffBatch, CutoffRecord, ReviewEvent, SourceVersion
from .schemas import (CutoffItem, ImportManifest, LocalBatch, LocalCutoffData,
                      LocalStatisticalQuery, REVIEW_REF, ReviewProof, SourceInput, utc)
from ...api.v2.schemas import PageInfo

CAPTURE_SHA256 = "b9fd87a8a202b37d6ff9e4f1efb8fdef394213448ffe983b9f5e7361e4dfb38a"
CAPTURE_BYTES = 68359
ORDER = {"segment_first": 0, "segment_second": 1, "special_category": 2}
TABLE_NAMES = ("reference_cutoff_sources", "reference_cutoff_batches",
               "reference_cutoff_records", "reference_cutoff_reviews")


class ReferenceError(ValueError):
    def __init__(self, code="LOCAL_REFERENCE_REJECTED"):
        self.code = code
        super().__init__(code)


def _pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ReferenceError()
        result[key] = value
    return result


def bounded_json(payload: bytes) -> dict:
    try:
        if type(payload) is not bytes or not 1 <= len(payload) <= 65536:
            raise ReferenceError()
        from ...ingestion.structured import _lexical_bounds
        decoded = payload.decode("utf-8")
        _lexical_bounds(decoded)
        result = json.loads(decoded, object_pairs_hook=_pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ReferenceError()))
        if type(result) is not dict:
            raise ReferenceError()
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ReferenceError() from None


def canonical_json(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_manifest(value: ImportManifest | dict) -> bytes:
    # This is the execution adapter hash, not the original research JSON hash.
    # The full model supplies explicit defaults and UTC Z timestamps.
    model = ImportManifest.model_validate(value)
    current = model.model_dump(mode="json")
    current["records"] = sorted(current["records"], key=lambda row: ORDER[row["line_kind"]])
    return canonical_json(current)


def manifest_digest(value: ImportManifest | dict) -> str:
    return sha256(canonical_manifest(value)).hexdigest()


def batch_identity(value: ImportManifest | dict) -> UUID:
    return uuid5(NAMESPACE_URL, "reference.cutoffs.local.batch:" + manifest_digest(value))


class _Body(HTMLParser):
    """Read the fixed source's ordinary-category table, without executing HTML."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.text = []
        self.depth = 0
        self.row = None
        self.cell = None
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.tables.append([])
        if self.depth == 1 and tag == "tr":
            self.row = []
        if self.depth == 1 and tag in {"td", "th"}:
            self.cell = []

    def handle_endtag(self, tag):
        if self.depth == 1 and tag in {"td", "th"} and self.cell is not None:
            if self.row is not None:
                self.row.append("".join(self.cell).strip())
            self.cell = None
        if self.depth == 1 and tag == "tr" and self.row is not None:
            self.tables[-1].append(self.row)
            self.row = None
        if tag == "table":
            self.depth -= 1
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, value):
        if self.hidden:
            return
        self.text.append(value)
        if self.cell is not None:
            self.cell.append(value)


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def validate_original(manifest: ImportManifest, raw_body: bytes) -> None:
    try:
        if (type(raw_body) is not bytes or len(raw_body) != manifest.source.body_bytes
                or len(raw_body) != CAPTURE_BYTES or manifest.source.original_sha256 != CAPTURE_SHA256
                or sha256(raw_body).hexdigest() != CAPTURE_SHA256):
            raise ReferenceError("ORIGINAL_SOURCE_MISMATCH")
        html = raw_body.decode("utf-8")
        begin, end = "<!--ZJEG_RSS.content.begin-->", "<!--ZJEG_RSS.content.end-->"
        if html.count(begin) != 1 or html.count(end) != 1:
            raise ReferenceError("ORIGINAL_SOURCE_MISMATCH")
        body = html.split(begin, 1)[1].split(end, 1)[0]
        parser = _Body()
        parser.feed(body)
        parser.close()
        if (not parser.tables or len(parser.tables[0]) != 2
                or [_compact(cell) for cell in parser.tables[0][0]] != ["普通类", "第一段", "第二段"]
                or [_compact(cell) for cell in parser.tables[0][1]] != ["分数线", "494", "266"]):
            raise ReferenceError("SOURCE_TABLE_MISMATCH")
        plain = _compact("".join(parser.text))
        for row in manifest.records:
            if row.line_kind in {"segment_first", "segment_second"}:
                label, column = ("第一段", 2) if row.line_kind == "segment_first" else ("第二段", 3)
                excerpt = f"普通类 {label}；分数线 {row.value}"
                locator = f"content_start/table[1]/row[2]/column[{column}]"
                if row.excerpt != excerpt or row.locator != locator:
                    raise ReferenceError("SOURCE_LOCATOR_MISMATCH")
            elif (row.locator != "content_start/ordinary_note[1]" or _compact(row.excerpt) not in plain
                  or "特殊类型招生控制线594分" not in _compact(row.excerpt)):
                raise ReferenceError("SOURCE_LOCATOR_MISMATCH")
        if manifest.source.title not in html or manifest.source.published_label not in html:
            raise ReferenceError("SOURCE_METADATA_MISMATCH")
    except (ValueError, TypeError, UnicodeError, IndexError):
        raise ReferenceError("ORIGINAL_SOURCE_MISMATCH") from None


def local_database_url(raw: str):
    try:
        if type(raw) is not str or not 1 <= len(raw) <= 4096:
            raise ValueError()
        url = make_url(raw)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        if (url.drivername != "postgresql+psycopg" or url.host not in {"127.0.0.1", "localhost", "::1"}
                or url.database != "reference_zj_2026" or not url.username or not url.password
                or url.query or url.username.upper().startswith("DEMO_") or url.password == "demo_local_only"):
            raise ValueError()
        return url
    except Exception:
        raise ReferenceError("EXPLICIT_LOCAL_REFERENCE_DATABASE_REQUIRED") from None


def require_reader(connection) -> None:
    """Recheck the actual role and fixed table privileges; metadata is not a GRANT."""
    flags = connection.execute(text("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
                                    "FROM pg_roles WHERE rolname=current_user")).one()
    if any(flags):
        raise ReferenceError("SELECT_ONLY_ROLE_REQUIRED")
    if connection.execute(text("SELECT has_schema_privilege(current_user,'public','CREATE')")).scalar_one():
        raise ReferenceError("SELECT_ONLY_ROLE_REQUIRED")
    for table in TABLE_NAMES:
        permission = connection.execute(text("SELECT has_table_privilege(current_user,:name,'SELECT'), "
            "has_table_privilege(current_user,:name,'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')"), {"name": table}).one()
        if permission[0] is not True or permission[1] is not False:
            raise ReferenceError("SELECT_ONLY_ROLE_REQUIRED")
    heads = connection.execute(text("SELECT version_num FROM reference_cutoffs_alembic_version")).scalars().all()
    if heads != ["0001_ref_cutoffs"]:
        raise ReferenceError("REFERENCE_SCHEMA_MISMATCH")


def _events(session: Session, batch: CutoffBatch, source: SourceVersion) -> tuple[ReviewEvent, ...]:
    events = tuple(session.scalars(select(ReviewEvent).where(ReviewEvent.batch_id == batch.id)
                                   .order_by(ReviewEvent.sequence)).all())
    if len(events) != batch.state_version or len(events) > 2:
        raise ReferenceError("REFERENCE_INTEGRITY_MISMATCH")
    for index, event in enumerate(events, 1):
        if (event.sequence != index or event.manifest_sha256 != batch.manifest_sha256
                or event.original_sha256 != source.original_sha256 or event.review_ref != REVIEW_REF
                or sha256(canonical_json(event.proof)).hexdigest() != event.proof_sha256):
            raise ReferenceError("REFERENCE_INTEGRITY_MISMATCH")
        if index == 1:
            proof = ReviewProof.model_validate(event.proof)
            if (event.decision != "approve_local" or proof.batch_id != batch.id
                    or proof.manifest_sha256 != batch.manifest_sha256 or proof.original_sha256 != source.original_sha256
                    or utc(event.recorded_at) != proof.confirmed_at):
                raise ReferenceError("REFERENCE_INTEGRITY_MISMATCH")
        else:
            if (event.decision != "withdraw" or event.proof.get("schema_version") != "reference.cutoffs.withdrawal.1"
                    or event.proof.get("batch_id") != str(batch.id)
                    or event.proof.get("manifest_sha256") != batch.manifest_sha256
                    or event.proof.get("original_sha256") != source.original_sha256):
                raise ReferenceError("REFERENCE_INTEGRITY_MISMATCH")
    return events


def verified_batch(session: Session, batch: CutoffBatch):
    manifest = ImportManifest.model_validate(batch.manifest)
    payload = canonical_manifest(manifest)
    if (batch.id != batch_identity(manifest) or batch.manifest_sha256 != sha256(payload).hexdigest()
            or batch.batch_key != manifest.batch_key or batch.state not in {"candidate", "approved_local", "withdrawn"}
            or batch.state_version != {"candidate": 0, "approved_local": 1, "withdrawn": 2}[batch.state]):
        raise ReferenceError("REFERENCE_INTEGRITY_MISMATCH")
    source = session.get(SourceVersion, batch.source_id)
    if source is None or source.payload != manifest.source.model_dump(mode="json"):
        raise ReferenceError("REFERENCE_INTEGRITY_MISMATCH")
    if source.original_sha256 != manifest.source.original_sha256 or source.body_bytes != manifest.source.body_bytes:
        raise ReferenceError("REFERENCE_INTEGRITY_MISMATCH")
    validate_original(manifest, bytes(source.raw_body))
    rows = tuple(session.scalars(select(CutoffRecord).where(CutoffRecord.batch_id == batch.id)).all())
    if len(rows) != 3:
        raise ReferenceError("REFERENCE_INTEGRITY_MISMATCH")
    stored = []
    for row in rows:
        item = CutoffItem.model_validate(row.payload)
        if item.record_key != row.record_key or item.line_kind != row.line_kind or item.value != row.value:
            raise ReferenceError("REFERENCE_INTEGRITY_MISMATCH")
        stored.append(item.model_dump(mode="json"))
    expected = sorted((row.model_dump(mode="json") for row in manifest.records), key=lambda row: ORDER[row["line_kind"]])
    if sorted(stored, key=lambda row: ORDER[row["line_kind"]]) != expected:
        raise ReferenceError("REFERENCE_INTEGRITY_MISMATCH")
    return manifest, source, _events(session, batch, source)


def import_batch(session: Session, manifest: ImportManifest | dict, raw_body: bytes) -> dict:
    current = ImportManifest.model_validate(manifest)
    validate_original(current, raw_body)
    canonical = canonical_manifest(current)
    digest = sha256(canonical).hexdigest()
    session.execute(text("SELECT pg_advisory_xact_lock(202626611)"))
    existing = session.scalar(select(CutoffBatch).where(CutoffBatch.batch_key == current.batch_key).with_for_update())
    if existing is not None:
        verified_batch(session, existing)
        if existing.manifest_sha256 != digest:
            raise ReferenceError("REFERENCE_BATCH_CONFLICT")
        return {"batch_id": str(existing.id), "manifest_sha256": digest,
                "state": existing.state, "inserted": False, "record_count": 3}
    source = session.scalar(select(SourceVersion).where(SourceVersion.original_sha256 == current.source.original_sha256))
    if source is None:
        source = SourceVersion(id=uuid5(NAMESPACE_URL, "reference.cutoffs.source:" + current.source.original_sha256),
            original_sha256=current.source.original_sha256, body_bytes=len(raw_body), raw_body=raw_body,
            payload=current.source.model_dump(mode="json"))
        session.add(source)
        session.flush()
    elif source.payload != current.source.model_dump(mode="json") or bytes(source.raw_body) != raw_body:
        raise ReferenceError("REFERENCE_SOURCE_CONFLICT")
    batch = CutoffBatch(id=batch_identity(current), source_id=source.id, batch_key=current.batch_key,
        manifest_sha256=digest, manifest=json.loads(canonical), state="candidate", state_version=0,
        created_at=datetime.now(timezone.utc))
    session.add(batch)
    session.flush()
    for item in current.records:
        session.add(CutoffRecord(batch_id=batch.id, record_key=item.record_key, line_kind=item.line_kind,
                                value=item.value, payload=item.model_dump(mode="json")))
    session.flush()
    verified_batch(session, batch)
    return {"batch_id": str(batch.id), "manifest_sha256": digest, "state": "candidate",
            "inserted": True, "record_count": 3}


def approve_batch(session: Session, proof: ReviewProof | dict) -> dict:
    current = ReviewProof.model_validate(proof)
    batch = session.scalar(select(CutoffBatch).where(CutoffBatch.id == current.batch_id).with_for_update())
    if batch is None:
        raise ReferenceError("REFERENCE_BATCH_NOT_FOUND")
    manifest, source, events = verified_batch(session, batch)
    if current.manifest_sha256 != batch.manifest_sha256 or current.original_sha256 != source.original_sha256:
        raise ReferenceError("REVIEW_PROOF_MISMATCH")
    if current.confirmed_at < manifest.source.retrieved_at or current.confirmed_at > datetime.now(timezone.utc):
        raise ReferenceError("REVIEW_PROOF_TIME_INVALID")
    proof_payload = current.model_dump(mode="json")
    proof_sha = sha256(canonical_json(proof_payload)).hexdigest()
    if batch.state == "withdrawn":
        raise ReferenceError("WITHDRAWN_REFERENCE_CANNOT_REOPEN")
    if batch.state == "approved_local":
        if events[0].proof_sha256 != proof_sha:
            raise ReferenceError("REVIEW_PROOF_CONFLICT")
        return {"batch_id": str(batch.id), "state": batch.state, "approved": False}
    event = ReviewEvent(id=uuid5(NAMESPACE_URL, "reference.cutoffs.review:" + proof_sha), batch_id=batch.id,
        sequence=1, decision="approve_local", manifest_sha256=batch.manifest_sha256,
        original_sha256=source.original_sha256, review_ref=current.review_ref,
        recorded_at=current.confirmed_at, proof_sha256=proof_sha, proof=proof_payload)
    session.add(event)
    session.flush()
    batch.state, batch.state_version = "approved_local", 1
    session.flush()
    verified_batch(session, batch)
    return {"batch_id": str(batch.id), "state": "approved_local", "approved": True}


def withdraw_batch(session: Session, batch_id: UUID, *, reason: str, review_ref: str = REVIEW_REF) -> dict:
    if type(reason) is not str or not 1 <= len(reason) <= 500 or not reason.strip() or any(ord(c) < 32 for c in reason):
        raise ReferenceError("WITHDRAWAL_REASON_REQUIRED")
    if review_ref != REVIEW_REF:
        raise ReferenceError("REVIEW_PROOF_MISMATCH")
    batch = session.scalar(select(CutoffBatch).where(CutoffBatch.id == batch_id).with_for_update())
    if batch is None:
        raise ReferenceError("REFERENCE_BATCH_NOT_FOUND")
    _, source, _ = verified_batch(session, batch)
    if batch.state == "withdrawn":
        return {"batch_id": str(batch.id), "state": "withdrawn", "withdrawn": False}
    if batch.state != "approved_local":
        raise ReferenceError("APPROVED_REFERENCE_REQUIRED")
    now = datetime.now(timezone.utc)
    proof = {"schema_version": "reference.cutoffs.withdrawal.1", "batch_id": str(batch.id),
        "manifest_sha256": batch.manifest_sha256, "original_sha256": source.original_sha256,
        "review_ref": REVIEW_REF, "reason": reason, "recorded_at": now.isoformat()}
    digest = sha256(canonical_json(proof)).hexdigest()
    session.add(ReviewEvent(id=uuid5(NAMESPACE_URL, "reference.cutoffs.withdrawal:" + digest), batch_id=batch.id,
        sequence=2, decision="withdraw", manifest_sha256=batch.manifest_sha256, original_sha256=source.original_sha256,
        review_ref=REVIEW_REF, recorded_at=now, proof_sha256=digest, proof=proof))
    session.flush()
    batch.state, batch.state_version = "withdrawn", 2
    session.flush()
    verified_batch(session, batch)
    return {"batch_id": str(batch.id), "state": "withdrawn", "withdrawn": True}


def query_cutoffs(session: Session, query: LocalStatisticalQuery) -> LocalCutoffData:
    current = LocalStatisticalQuery.model_validate(query.model_dump())
    filters = current.model_dump(exclude={"limit", "cursor"})
    page = PageInfo(limit=current.limit, next_cursor=None, has_more=False)

    def missing(reason):
        return LocalCutoffData(filters=filters, page=page, reference_available=False, missing_reason=reason)

    if current.region_key in {"hk", "mo", "tw"}:
        return missing("not_applicable")
    if current.region_key != "cn_region_11" or current.year != 2026:
        return missing("not_collected")
    if current.subject_category not in {None, "普通类"} or current.batch is not None or current.round is not None:
        return missing("scope_not_supported")
    batches = session.scalars(select(CutoffBatch)).all()
    if not batches:
        return missing("not_collected")
    if len(batches) != 1:
        raise ReferenceError("REFERENCE_INTEGRITY_MISMATCH")
    batch = batches[0]
    manifest, _, events = verified_batch(session, batch)
    if batch.state == "withdrawn":
        return missing("withdrawn")
    if batch.state != "approved_local":
        return missing("review_pending")
    return LocalCutoffData(filters=filters, page=page, reference_available=True, missing_reason=None,
        source=manifest.source, batch=LocalBatch(batch_id=batch.id, manifest_sha256=batch.manifest_sha256,
            review_ref=events[0].review_ref, approved_at=utc(events[0].recorded_at)),
        items=tuple(sorted(manifest.records, key=lambda row: ORDER[row.line_kind])))
