"""Finite table ownership projections, shared by capture, export and erasure.

No table, SQL fragment, owner, path or handler comes from an HTTP request.
"""
from base64 import b64encode
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from sqlalchemy import delete, select, update

from ...auth.models import AuthOwnedResource
from ...auth.grants.models import AccessGrant, GrantAction, GrantField
from ...storage.models import StorageObject
from ...storage.protocol import StorageNamespace
from ...idempotency.models import IdempotencyRecord
from ...profiles.models import ProfileRoot, ProfileVersion
from ...privacy.models import PrivacyAdmissionRecord
from ...assessments.models import EligibilityAssessment
from ...plans.models import PlanRoot, PlanVersion, PlanTask, PlanTaskDependency, PlanSourceAssessment
from ...plan_execution.models import ExecutionHead, ExecutionProposal, ExecutionConfirmation, TaskCompletion
from ...plan_revisions.models import RevisionProposal, RevisionDecision, PlanReplacement
from ...jobs.models import CleanupPermit, DurableJob, InboxNotification, JobAttempt, NotificationPreference
from ...changes.models import AssessmentChangeImpact, PlanChangeImpact
from .ledger import canonical
from .models import RightsAttempt, RightsRequest, ErasedImpactCount
from .schemas import MAX_SCOPE_BYTES, RightsError, utc


def scalar(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return utc(value).isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def row_data(row):
    return {column.name: scalar(getattr(row, column.name)) for column in row.__table__.columns
        if column.name not in {"session_id", "actor_session_id", "lease_token", "worker_id"}}


def registry(owner):
    plans = select(PlanRoot.id).where(PlanRoot.owner_user_id == owner)
    jobs = select(DurableJob.id).where(DurableJob.owner_user_id == owner)
    grants = select(AccessGrant.id).where(AccessGrant.owner_user_id == owner)
    exports = select(RightsRequest.id).where(RightsRequest.owner_user_id == owner, RightsRequest.kind == "export")
    owned = lambda model: model.owner_user_id == owner
    # Children precede parents; deferred current pointers are checked at commit.
    return (
        (InboxNotification, owned(InboxNotification)),
        (NotificationPreference, owned(NotificationPreference)),
        (JobAttempt, JobAttempt.job_id.in_(jobs)),
        (DurableJob, owned(DurableJob)), (CleanupPermit, owned(CleanupPermit)),
        (GrantField, GrantField.grant_id.in_(grants)), (GrantAction, GrantAction.grant_id.in_(grants)),
        (AccessGrant, AccessGrant.owner_user_id == owner),
        (PlanReplacement, owned(PlanReplacement)), (RevisionDecision, owned(RevisionDecision)),
        (RevisionProposal, owned(RevisionProposal)),
        (PlanChangeImpact, owned(PlanChangeImpact)), (AssessmentChangeImpact, owned(AssessmentChangeImpact)),
        (TaskCompletion, owned(TaskCompletion)), (ExecutionConfirmation, owned(ExecutionConfirmation)),
        (ExecutionProposal, owned(ExecutionProposal)), (ExecutionHead, owned(ExecutionHead)),
        (PlanTaskDependency, PlanTaskDependency.plan_id.in_(plans)),
        (PlanTask, PlanTask.plan_id.in_(plans)), (PlanSourceAssessment, PlanSourceAssessment.plan_id.in_(plans)),
        (PlanVersion, owned(PlanVersion)), (PlanRoot, owned(PlanRoot)),
        (EligibilityAssessment, owned(EligibilityAssessment)),
        (ProfileVersion, owned(ProfileVersion)), (ProfileRoot, owned(ProfileRoot)),
        (StorageObject, (StorageObject.owner_user_id == owner) & (StorageObject.namespace == "student_private")),
        (IdempotencyRecord, (IdempotencyRecord.actor_user_id == owner) & IdempotencyRecord.operation.in_(("profile.create", "plan.confirm"))),
        (RightsAttempt, RightsAttempt.request_id.in_(exports)),
        (RightsRequest, (RightsRequest.owner_user_id == owner) & (RightsRequest.kind == "export")),
    )


def key_for(row):
    return [scalar(getattr(row, column.name)) for column in row.__table__.primary_key.columns]


def capture(session, owner, *, max_rows, cutoff=None):
    tables, total, files, artifacts = {}, 0, [], []
    for model, condition in registry(owner):
        rows = tuple(session.scalars(select(model).where(condition).order_by(*model.__table__.primary_key.columns)
            .limit(max_rows + 1)).all())
        total += len(rows)
        if total > max_rows:
            raise RightsError(422, "VALIDATION_ERROR")
        if cutoff is not None:
            for row in rows:
                for name in ("created_at", "confirmed_at", "assessment_at", "completed_at", "decided_at", "accepted_at", "updated_at"):
                    value = getattr(row, name, None)
                    if value is not None and utc(value) > cutoff:
                        raise RightsError()  # No authority for post-acceptance data from a damaged backup.
        tables[model.__tablename__] = [key_for(row) for row in rows]
        if model is StorageObject:
            files = [{"id": str(row.id), "sha256": row.sha256, "size_bytes": row.size_bytes,
                "status": row.status} for row in rows]
        if model is RightsRequest:
            artifacts = [{"id": str(row.artifact_id), "sha256": row.artifact_sha256,
                "size_bytes": row.artifact_size} for row in rows if row.artifact_id is not None]
    value = {"schema_version": "T40_v1", "owner_user_id": str(owner), "tables": tables, "files": files, "artifacts": artifacts}
    if len(canonical(value)) > MAX_SCOPE_BYTES:
        raise RightsError(422, "VALIDATION_ERROR")
    return value


def validate_scope(session, owner, scope, scope_sha256, *, max_rows, allow_subset=False):
    if type(scope) is not dict or sha256(canonical(scope)).hexdigest() != scope_sha256:
        raise RightsError()
    current = capture(session, owner, max_rows=max_rows)
    if not allow_subset and current != scope:
        raise RightsError(409, "CONFLICT")
    if allow_subset:
        if set(scope) != set(current) or scope["owner_user_id"] != str(owner) or scope["schema_version"] != "T40_v1":
            raise RightsError()
        for name, values in current["tables"].items():
            if any(key not in scope["tables"].get(name, []) for key in values):
                raise RightsError()
    return current


def private_files(scope):
    return tuple(scope["files"]) + tuple(scope["artifacts"])


def erase_files(backend, scope):
    # Missing file is idempotent completion; a present file must match captured bytes.
    from ...storage.protocol import StorageError
    for item in private_files(scope):
        identifier = UUID(item["id"])
        try:
            backend.read(StorageNamespace.student_private, identifier,
                expected_size=item["size_bytes"], expected_sha256=item["sha256"])
        except StorageError as error:
            if error.status_code != 404:
                raise
        result = backend.delete(StorageNamespace.student_private, identifier)
        if type(result) is not bool:
            raise RightsError()


def erase_rows(session, owner, scope):
    # Aggregate contains only public event IDs and counts, never a student ID.
    for model, field in ((AssessmentChangeImpact, "assessment_count"), (PlanChangeImpact, "plan_count")):
        rows = tuple(session.scalars(select(model).where(model.owner_user_id == owner)).all())
        counts = {}
        for row in rows:
            counts[row.event_id] = counts.get(row.event_id, 0) + 1
        for event, number in counts.items():
            aggregate = session.get(ErasedImpactCount, event, with_for_update=True)
            if aggregate is None:
                aggregate = ErasedImpactCount(event_id=event, assessment_count=0, plan_count=0)
                session.add(aggregate)
            setattr(aggregate, field, getattr(aggregate, field) + number)
            session.flush()
    for model, condition in registry(owner):
        expected = scope["tables"][model.__tablename__]
        actual = tuple(session.scalars(select(model).where(condition)).all())
        if any(key_for(row) not in expected for row in actual):
            raise RightsError()
        session.execute(delete(model).where(condition).execution_options(synchronize_session=False))
    session.execute(update(AuthOwnedResource).where(AuthOwnedResource.owner_user_id == owner)
        .values(status="deleted").execution_options(synchronize_session=False))


def export_bytes(session, owner, scope, backend, *, limit):
    collections, size = [], 0
    for model, condition in registry(owner):
        # Private hash-only idempotency keys are erased but are not useful exports.
        if model in (IdempotencyRecord, JobAttempt, DurableJob, CleanupPermit, RightsAttempt, RightsRequest):
            continue
        rows = tuple(session.scalars(select(model).where(condition).order_by(*model.__table__.primary_key.columns)).all())
        if [key_for(row) for row in rows] != scope["tables"][model.__tablename__]:
            raise RightsError(409, "CONFLICT")
        values = [row_data(row) for row in rows]
        size += len(canonical(values))
        if size > limit:
            raise RightsError(422, "EXPORT_LIMIT")
        collections.append({"collection": model.__tablename__, "row_count": len(values), "rows": values})
    files = []
    for item in scope["files"]:
        if item["status"] != "quarantined":
            continue
        content = backend.read(StorageNamespace.student_private, UUID(item["id"]),
            expected_size=item["size_bytes"], expected_sha256=item["sha256"])
        size += ((len(content) + 2) // 3) * 4
        if size > limit:
            raise RightsError(422, "EXPORT_LIMIT")
        files.append({"id": item["id"], "size_bytes": len(content), "sha256": item["sha256"],
            "content_base64": b64encode(content).decode("ascii")})
    admission_rows = tuple(session.scalars(select(PrivacyAdmissionRecord).where(PrivacyAdmissionRecord.user_id == owner)
        .order_by(PrivacyAdmissionRecord.revision).limit(5001)).all())
    if len(admission_rows) > 5000:
        raise RightsError(422, "EXPORT_LIMIT")
    collections.append({"collection": "privacy_admission_records", "row_count": len(admission_rows),
        "rows": [row_data(row) for row in admission_rows]})
    requests = tuple(session.scalars(select(RightsRequest).where(RightsRequest.owner_user_id == owner)
        .order_by(RightsRequest.accepted_at, RightsRequest.id).limit(5001)).all())
    if len(requests) > 5000:
        raise RightsError(422, "EXPORT_LIMIT")
    collections.append({"collection": "privacy_rights_requests", "row_count": len(requests),
        "rows": [{name: scalar(getattr(row, name)) for name in ("id", "kind", "status", "reason", "accepted_at", "completed_at")}
            for row in requests]})
    content = canonical({"schema_version": "T40_v1", "is_synthetic": True, "owner_user_id": str(owner),
        "collections": collections, "attachments": files,
        "history_notice": "历史版本不代表当前资格；本人声明不代表核验或学校确认。"})
    if len(content) > limit:
        raise RightsError(422, "EXPORT_LIMIT")
    return content
