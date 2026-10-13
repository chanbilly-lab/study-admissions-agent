"""Explicit maintenance commands. Never fetch, migrate, grant, or seed on import."""

import argparse
import json
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from .schemas import ImportManifest, ReviewProof
from .service import (ReferenceError, approve_batch, bounded_json, import_batch,
                      local_database_url, withdraw_batch)


def read_bounded(path: str, limit: int) -> bytes:
    file = Path(path)
    if not file.is_file():
        raise ReferenceError("BOUNDED_LOCAL_FILE_REQUIRED")
    with file.open("rb") as handle:
        value = handle.read(limit + 1)
    if not 1 <= len(value) <= limit:
        raise ReferenceError("BOUNDED_LOCAL_FILE_REQUIRED")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="One explicitly reviewed local Zhejiang 2026 reference batch")
    sub = parser.add_subparsers(dest="command", required=True)
    importing = sub.add_parser("import")
    importing.add_argument("--manifest", required=True)
    importing.add_argument("--raw-source", required=True)
    approving = sub.add_parser("approve")
    approving.add_argument("--review", required=True)
    withdrawing = sub.add_parser("withdraw")
    withdrawing.add_argument("--batch-id", required=True, type=UUID)
    withdrawing.add_argument("--reason", required=True)
    args = parser.parse_args()
    engine = None
    try:
        raw = os.environ.get("REFERENCE_CUTOFFS_DATABASE_URL")
        url = local_database_url(raw)
        # Parse and bind the bounded local inputs before opening the maintenance connection.
        if args.command == "import":
            manifest = ImportManifest.model_validate(bounded_json(read_bounded(args.manifest, 65536)))
            body = read_bounded(args.raw_source, 2 * 1024 * 1024)
        elif args.command == "approve":
            proof = ReviewProof.model_validate(bounded_json(read_bounded(args.review, 65536)))
        engine = create_engine(url, hide_parameters=True, echo=False, connect_args={"connect_timeout": 5})
        with Session(engine) as session, session.begin():
            if args.command == "import":
                result = import_batch(session, manifest, body)
            elif args.command == "approve":
                result = approve_batch(session, proof)
            else:
                result = withdraw_batch(session, args.batch_id, reason=args.reason)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except ReferenceError as error:
        print(json.dumps({"error": error.code}))
        return 1
    except Exception:
        # SQL URLs, driver errors, paths, input values, and tracebacks are never printed.
        print(json.dumps({"error": "LOCAL_REFERENCE_OPERATION_FAILED"}))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
