"""Fixed maintenance plans and a server-only T40 replay seam; no command runner."""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .archive import BackupError


class DatabaseTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True,
                              revalidate_instances="always", allow_inf_nan=False)
    host: Literal["127.0.0.1", "::1"]
    port: Annotated[StrictInt, Field(ge=1, le=65535)]
    database: Annotated[str, Field(pattern=r"^t44_synthetic_[a-z0-9_]{8,48}$")]
    username: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{2,62}$")]


def _target(value: DatabaseTarget) -> DatabaseTarget:
    if type(value) is not DatabaseTarget:
        raise BackupError("BACKUP_INVALID")
    try:
        return DatabaseTarget.model_validate(value.model_dump())
    except ValueError:
        raise BackupError("BACKUP_INVALID") from None


@dataclass(frozen=True)
class MaintenancePlan:
    argv: tuple[str, ...]
    required_preconditions: tuple[str, ...]
    execution_supported: Literal[False] = False
    traffic_ready: Literal[False] = False


def _artifact(value: Path) -> str:
    # Dedicated convention, not proof that a path exists, is empty, or has safe ACL.
    if type(value) is not type(Path()) or not value.is_absolute() or value.name != "business.dump":
        raise BackupError("BACKUP_INVALID")
    if re.fullmatch(r"t44_synthetic_[a-z0-9_]{8,48}", value.parent.name) is None or any(part == ".." for part in value.parts):
        raise BackupError("BACKUP_INVALID")
    return str(value)


def _connection(target: DatabaseTarget) -> tuple[str, ...]:
    return ("--host", target.host, "--port", str(target.port), "--username", target.username,
            "--dbname", target.database, "--no-password")


def dump_plan(source: DatabaseTarget, artifact: Path) -> MaintenancePlan:
    """Plan only; caller must separately prove synthetic source and unused output."""
    source = _target(source)
    return MaintenancePlan(("pg_dump", *_connection(source), "--format=custom", "--no-owner",
                            "--no-privileges", "--file", _artifact(artifact)),
                           ("source_synthetic_verified", "artifact_absent_verified", "external_credentials_prepared",
                            "ledger_and_anchor_excluded", "explicit_operator_execution_required"))


def restore_plan(source: DatabaseTarget, target: DatabaseTarget, artifact: Path) -> MaintenancePlan:
    """Plan only for a different synthetic DB; never clean, create, or force overwrite."""
    source, target = _target(source), _target(target)
    # A new database name is required even when the host or port differs.
    if source.database == target.database:
        raise BackupError("BACKUP_INVALID")
    return MaintenancePlan(("pg_restore", *_connection(target), "--single-transaction", "--exit-on-error",
                            "--no-owner", "--no-privileges", _artifact(artifact)),
                           ("new_empty_target_verified", "package_authenticated_and_unexpired",
                            "external_credentials_prepared", "traffic_stopped", "latest_external_ledger_and_anchor_present",
                            "explicit_operator_execution_required", "t40_replay_then_ensure_ready_required"))


_SERVER_ASSEMBLY = object()


@dataclass(frozen=True)
class _MaintenanceContext:
    guard: object = field(repr=False)
    target: DatabaseTarget
    assembly: object = field(repr=False)


def assemble_maintenance_context(guard, target: DatabaseTarget) -> _MaintenanceContext:
    """Server-internal dependency assembly, never from an HTTP body or actor checkbox.

    Synthetic naming is only an additional bound. Authority is the already trusted
    T40 dependency; this function does not authenticate an operator or open traffic.
    """
    from services.api.app.privacy.rights.guard import RightsGuard

    target = _target(target)
    if type(guard) is not RightsGuard:
        raise BackupError("BACKUP_GUARD_UNAVAILABLE")
    guard.validate_configuration()
    url = guard.engine.url
    if (url.host, url.port, url.database) != (target.host, target.port, target.database):
        raise BackupError("BACKUP_GUARD_UNAVAILABLE")
    return _MaintenanceContext(guard, target, _SERVER_ASSEMBLY)


@dataclass(frozen=True)
class ReplayReceipt:
    ledger_sequence: int
    ledger_sha256: str
    rights_replayed: Literal[True] = True
    traffic_ready: Literal[False] = False
    public_release_ready: Literal[False] = False


def replay_after_restore(context: _MaintenanceContext) -> ReplayReceipt:
    """Explicit trusted maintenance only; T40 handles current ledger/file/DB barriers."""
    if type(context) is not _MaintenanceContext or context.assembly is not _SERVER_ASSEMBLY:
        raise BackupError("BACKUP_GUARD_UNAVAILABLE")
    current = assemble_maintenance_context(context.guard, context.target)
    proof = current.guard.replay()
    if current.guard.ensure_ready() != proof:
        raise BackupError("BACKUP_GUARD_UNAVAILABLE")
    return ReplayReceipt(ledger_sequence=proof.sequence, ledger_sha256=proof.chain_sha256)
