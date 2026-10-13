"""Read-only local input screening. Not a runtime or public-release approval."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import ssl
from urllib.parse import unquote, urlsplit

IMAGE_PATTERNS = {
    "PYTHON_IMAGE": r"python:3\.12\.\d+-slim-bookworm@sha256:[0-9a-f]{64}",
    "NODE_IMAGE": r"node:24\.\d+\.\d+-bookworm-slim@sha256:[0-9a-f]{64}",
    "NGINX_IMAGE": r"nginx:\d+\.\d+\.\d+-bookworm@sha256:[0-9a-f]{64}",
    "POSTGRES_IMAGE": r"postgres:16\.\d+-bookworm@sha256:[0-9a-f]{64}",
}
FILE_LIMITS = {
    "STUDY_TLS_CERT_FILE": 1024 * 1024,
    "STUDY_TLS_KEY_FILE": 1024 * 1024,
    "STUDY_DB_PASSWORD_FILE": 4096,
    "STUDY_LEDGER_PASSWORD_FILE": 4096,
    "STUDY_BUSINESS_URL_FILE": 16 * 1024,
    "STUDY_LEDGER_URL_FILE": 16 * 1024,
}


def inspect_inputs() -> list[str]:
    errors: list[str] = []
    for key, pattern in IMAGE_PATTERNS.items():
        if re.fullmatch(pattern, os.environ.get(key, "")) is None:
            errors.append(f"{key}:FIXED_VERSION_DIGEST_REQUIRED")
    for key, name in (("STUDY_API_IMAGE", "study-api"), ("STUDY_WEB_IMAGE", "study-web"), ("STUDY_TOOLS_IMAGE", "study-tools")):
        if re.fullmatch(re.escape(name) + r":[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}", os.environ.get(key, "")) is None:
            errors.append(f"{key}:LOCAL_VERSION_TAG_REQUIRED")
        elif os.environ[key].endswith(":latest"):
            errors.append(f"{key}:LATEST_FORBIDDEN")
    host = os.environ.get("STUDY_SITE_HOST", "")
    label = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    if len(host) > 253 or re.fullmatch(label + r"(?:\." + label + r")+", host) is None:
        errors.append("STUDY_SITE_HOST:LOWERCASE_DNS_HOST_REQUIRED")
    port = os.environ.get("STUDY_HTTPS_PORT", "8443")
    if not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535:
        errors.append("STUDY_HTTPS_PORT:INVALID")
    files: dict[str, Path] = {}
    contents: dict[str, bytes] = {}
    workspace = Path(__file__).resolve().parents[1]
    for key, limit in FILE_LIMITS.items():
        try:
            path = Path(os.environ.get(key, ""))
            if not path.is_absolute() or not path.is_file() or path.is_symlink():
                raise ValueError("file")
            if path.resolve().is_relative_to(workspace):
                raise ValueError("external file required")
            with path.open("rb") as handle:
                raw = handle.read(limit + 1)
            if not raw or len(raw) > limit:
                raise ValueError("length")
            if key.endswith("PASSWORD_FILE"):
                text = raw.decode("utf-8").rstrip("\r\n")
                if len(text) < 32 or any(character.isspace() for character in text):
                    raise ValueError("password")
            files[key] = path
            contents[key] = raw
        except (OSError, ValueError, UnicodeError):
            errors.append(f"{key}:BOUNDED_REGULAR_FILE_REQUIRED")
    if len(set(path.resolve() for path in files.values())) != len(files):
        errors.append("SECRETS:DISTINCT_FILES_REQUIRED")
    for key, password_key, host_name, owner, database in (
        ("STUDY_BUSINESS_URL_FILE", "STUDY_DB_PASSWORD_FILE", "db", "study_owner", "study_business"),
        ("STUDY_LEDGER_URL_FILE", "STUDY_LEDGER_PASSWORD_FILE", "ledger_db", "study_ledger_owner", "study_ledger"),
    ):
        if key not in contents or password_key not in contents:
            continue
        try:
            value = contents[key].decode("utf-8").strip()
            url = urlsplit(value)
            password = contents[password_key].decode("utf-8").rstrip("\r\n")
            if (any(character.isspace() for character in value)
                    or url.scheme not in {"postgresql", "postgresql+psycopg"}
                    or url.hostname != host_name or url.port not in {None, 5432}
                    or unquote(url.username or "") != owner
                    or unquote(url.password or "") != password
                    or url.path != "/" + database or url.query or url.fragment):
                raise ValueError("target")
        except (ValueError, UnicodeError):
            errors.append(f"{key}:FIXED_TARGET_AND_MATCHING_PASSWORD_REQUIRED")
    if "STUDY_TLS_CERT_FILE" in files and "STUDY_TLS_KEY_FILE" in files:
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(str(files["STUDY_TLS_CERT_FILE"]), str(files["STUDY_TLS_KEY_FILE"]), password="")
        except (OSError, ValueError, ssl.SSLError):
            errors.append("TLS:UNENCRYPTED_MATCHING_CERTIFICATE_KEY_REQUIRED")
    return errors


def main() -> int:
    try:
        errors = inspect_inputs()
    except Exception:
        errors = ["INPUT_SCREENING_FAILED"]
    print(json.dumps({"configuration_structure_valid": not errors, "errors": errors,
                      "runtime_verified": False, "public_deployment_authorized": False}, ensure_ascii=True))
    return 78 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
