"""An append-only external ledger plus a trusted anchor outside business backups.

The anchor is never reconstructed from restored database contents. A failed
append/anchor/business commit leaves traffic closed until explicit replay.
"""
from contextlib import contextmanager
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import SecretBytes
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from .models import LedgerEvent, LedgerHead
from .schemas import LedgerEventData, LedgerProof, RightsError, ZERO_HASH


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def chain_hash(previous, sequence, event):
    return sha256(canonical({"previous_sha256": previous, "sequence": sequence, "event": event})).hexdigest()


class FileAnchor:
    """Explicit maintenance-owned root. No constructor or import creates files."""
    def __init__(self, root: Path, signing_key: SecretBytes):
        if not isinstance(root, Path) or not root.is_absolute() or not isinstance(signing_key, SecretBytes):
            raise RightsError()
        if len(signing_key.get_secret_value()) < 32:
            raise RightsError()
        self.root, self.key = root, signing_key
        self._initial = (root, signing_key)

    def _validate(self):
        if self.root != self._initial[0] or self.key is not self._initial[1]:
            raise RightsError()
        for path in (self.root, *self.root.parents):
            if path.is_symlink() or (path.exists() and bool(getattr(path.stat(), "st_file_attributes", 0) & 1024)):
                raise RightsError()
        if not self.root.is_dir():
            raise RightsError()

    @contextmanager
    def locked(self):
        self._validate()
        lock = self.root / "anchor.lock"
        descriptor = None
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            yield
        except RightsError:
            raise
        except Exception:
            raise RightsError() from None
        finally:
            if descriptor is not None:
                os.close(descriptor)
                lock.unlink(missing_ok=True)

    def read(self):
        self._validate()
        path = self.root / "latest.json"
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024:
                raise ValueError()
            document = json.loads(path.read_bytes())
            if set(document) != {"proof", "signature"}:
                raise ValueError()
            expected = hmac.new(self.key.get_secret_value(), canonical(document["proof"]), "sha256").hexdigest()
            if not isinstance(document["signature"], str) or not hmac.compare_digest(expected, document["signature"]):
                raise ValueError()
            return LedgerProof.model_validate_json(canonical(document["proof"]))
        except Exception:
            raise RightsError() from None

    def write_locked(self, proof, *, previous):
        self._validate()
        proof = LedgerProof.model_validate(proof)
        if previous is None:
            if (self.root / "latest.json").exists() or proof.sequence != 0 or proof.chain_sha256 != ZERO_HASH:
                raise RightsError()
        else:
            previous = LedgerProof.model_validate(previous)
            if self.read() != previous or proof.ledger_id != previous.ledger_id or proof.sequence != previous.sequence + 1:
                raise RightsError()
        payload = proof.model_dump(mode="json")
        data = canonical({"proof": payload, "signature": hmac.new(self.key.get_secret_value(), canonical(payload), "sha256").hexdigest()})
        temporary = self.root / ("anchor-" + uuid4().hex + ".tmp")
        try:
            with temporary.open("xb") as target:
                target.write(data)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, self.root / "latest.json")
        finally:
            temporary.unlink(missing_ok=True)


class ExternalLedger:
    def __init__(self, engine, anchor: FileAnchor):
        if engine.dialect.name != "postgresql" or type(anchor) is not FileAnchor:
            raise RightsError()
        self.engine, self.anchor = engine, anchor
        self._initial = (engine, anchor)

    def validate_configuration(self):
        if self.engine is not self._initial[0] or self.anchor is not self._initial[1] or type(self.anchor) is not FileAnchor:
            raise RightsError()
        # No I/O: disabled factories can safely validate their configuration.
        if self.anchor.root != self.anchor._initial[0] or self.anchor.key is not self.anchor._initial[1]:
            raise RightsError()

    def assert_schema_ready(self):
        self.validate_configuration()
        try:
            with self.engine.connect() as connection:
                if connection.execute(text("SELECT version_num FROM rights_ledger_alembic_version")).scalars().all() != ["0001_ledger_t40"]:
                    raise ValueError()
                state = connection.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgrelid='privacy_ledger_events'::regclass AND tgname='privacy_ledger_events_no_mutation' AND NOT tgisinternal")).scalar_one_or_none()
                if state not in {"O", "A"}:
                    raise ValueError()
            for model in (LedgerHead, LedgerEvent):
                if not set(model.__table__.columns.keys()) <= {v["name"] for v in inspect(self.engine).get_columns(model.__tablename__)}:
                    raise ValueError()
        except Exception:
            raise RightsError() from None

    def location(self):
        """Current physical namespace, never inferred from an Engine identity."""
        self.validate_configuration()
        with self.engine.connect() as connection:
            return (self.engine.url.host, self.engine.url.port, self.engine.url.database,
                connection.scalar(text("SELECT current_schema()")))

    def bootstrap(self):
        """Explicit trusted maintenance, only a new empty ledger and absent anchor."""
        self.assert_schema_ready()
        with self.anchor.locked():
            with Session(self.engine) as session, session.begin():
                if session.get(LedgerHead, 1) is not None or session.scalar(select(LedgerEvent.sequence).limit(1)) is not None:
                    raise RightsError()
                proof = LedgerProof(ledger_id=uuid4(), sequence=0, chain_sha256=ZERO_HASH)
                session.add(LedgerHead(id=1, **proof.model_dump()))
            self.anchor.write_locked(proof, previous=None)
        return proof

    def _verified(self, session, *, lock=False):
        if session.execute(text("SELECT version_num FROM rights_ledger_alembic_version")).scalars().all() != ["0001_ledger_t40"]:
            raise RightsError()
        anchor = self.anchor.read()
        head = session.get(LedgerHead, 1, populate_existing=True, with_for_update=lock)
        if head is None:
            raise RightsError()
        proof = LedgerProof(ledger_id=head.ledger_id, sequence=head.sequence, chain_sha256=head.chain_sha256)
        if proof != anchor:
            raise RightsError()
        records = tuple(session.scalars(select(LedgerEvent).order_by(LedgerEvent.sequence).limit(10001)).all())
        if len(records) != proof.sequence:
            raise RightsError()
        previous, events = ZERO_HASH, []
        for sequence, row in enumerate(records, 1):
            event = LedgerEventData.model_validate_json(canonical(row.event))
            if row.sequence != sequence or row.event_id != event.event_id or row.previous_sha256 != previous:
                raise RightsError()
            current = chain_hash(previous, sequence, event.model_dump(mode="json"))
            if not hmac.compare_digest(row.chain_sha256, current):
                raise RightsError()
            previous = current
            events.append(event)
        if previous != proof.chain_sha256:
            raise RightsError()
        return proof, tuple(events)

    def snapshot(self):
        self.validate_configuration()
        try:
            with Session(self.engine) as session, session.begin():
                proof, events = self._verified(session)
            # Detect an anchor transition after the SQL snapshot.
            if self.anchor.read() != proof:
                raise RightsError()
            return proof, events
        except Exception:
            raise RightsError() from None

    def append(self, event):
        self.validate_configuration()
        event = LedgerEventData.model_validate(event)
        try:
            with self.anchor.locked():
                with Session(self.engine) as session, session.begin():
                    previous, _ = self._verified(session, lock=True)
                    if session.scalar(select(LedgerEvent.sequence).where(LedgerEvent.event_id == event.event_id)) is not None:
                        raise RightsError()
                    sequence = previous.sequence + 1
                    payload = event.model_dump(mode="json")
                    proof = LedgerProof(ledger_id=previous.ledger_id, sequence=sequence,
                        chain_sha256=chain_hash(previous.chain_sha256, sequence, payload))
                    session.add(LedgerEvent(sequence=sequence, event_id=event.event_id, event=payload,
                        previous_sha256=previous.chain_sha256, chain_sha256=proof.chain_sha256))
                    head = session.get(LedgerHead, 1)
                    head.sequence, head.chain_sha256 = proof.sequence, proof.chain_sha256
                self.anchor.write_locked(proof, previous=previous)
            return proof
        except Exception:
            # Do not manufacture an anchor from a partially committed ledger.
            raise RightsError() from None
