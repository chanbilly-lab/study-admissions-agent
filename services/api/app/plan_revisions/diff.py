"""Exact bounded comparison, with references separated from business changes."""

from ..api.v2.idempotency_canonical import canonical_request_hash
from .schemas import RevisionDiff, RevisionError, RevisionHistoryData


def _multiset(items):
    return sorted(canonical_request_hash(item) for item in items)


def compare_plans(old,new,*,source_business_changed=False):
    try:
        old=RevisionHistoryData.model_validate(old)
        new=RevisionHistoryData.model_validate(new)
        if type(source_business_changed) is not bool or old.pin.profile_id!=new.pin.profile_id or old.pin.is_synthetic!=new.pin.is_synthetic:
            raise ValueError()
        fields=[]
        if (old.pin.profile_version_id,old.pin.profile_sha256)!=(new.pin.profile_version_id,new.pin.profile_sha256):
            fields.append("profile_version")
        def tasks(value):
            return [{k:v for k,v in t.model_dump(mode="json").items() if k in
                {"kind","action_code","title","acceptance_criteria","assessment_key","basis","unit","scale","work_scope_sha256"}}
                for t in value.tasks]
        if _multiset(tasks(old))!=_multiset(tasks(new)):
            fields.append("task_business")
        def estimates(value):
            return [{"task":task,"estimated_hours":t.estimated_hours} for task,t in zip(tasks(value),value.tasks,strict=True)]
        if _multiset(estimates(old))!=_multiset(estimates(new)):
            fields.append("estimates")
        def edges(value):
            keys={t.task_key:canonical_request_hash(task) for task,t in zip(tasks(value),value.tasks,strict=True)}
            return [{"task":keys[t.task_key],"dependency":keys[key]} for t in value.tasks for key in t.dependency_keys]
        if _multiset(edges(old))!=_multiset(edges(new)):
            fields.append("dependencies")
        def dates(value):
            return [{k:v for k,v in r.model_dump(mode="json").items() if k not in {"assessment_id","deadline_key","event_id"}} for r in value.deadlines]
        if _multiset(dates(old))!=_multiset(dates(new)):
            fields.append("deadlines")
        def arrangement(value):
            raw=None if value.schedule is None else value.schedule.model_dump(mode="json")
            if raw is not None:
                keys={t.task_key:canonical_request_hash(task) for task,t in zip(tasks(value),value.tasks,strict=True)}
                raw.pop("generated_at")
                raw["tasks"]=_multiset([{**{k:v for k,v in t.items() if k not in {"task_key","assessment_ids","dependency_keys","deadline_keys"}},
                    "task":keys[t["task_key"]],"dependencies":sorted(keys[k] for k in t["dependency_keys"])} for t in raw["tasks"]])
                raw["allocations"]=_multiset([{**{k:v for k,v in a.items() if k not in {"task_key","slot_id"}},
                    "task":keys[a["task_key"]]} for a in raw["allocations"]])
            return raw
        if arrangement(old)!=arrangement(new):
            fields.append("schedule")
        def targets(value):
            return [{"target":r.target.model_dump(mode="json",exclude={"offering_version"}),"entry_year":r.entry_year,"stage":r.stage} for r in value.sources]
        if _multiset(targets(old))!=_multiset(targets(new)):
            fields.append("targets")
        def refs(value):
            return [r.model_dump(mode="json",exclude={"current_validity"}) for r in value.sources]
        if _multiset(refs(old))!=_multiset(refs(new)):
            fields.append("source_references")
        if source_business_changed:
            fields.append("source_business")
        business=any(k!="source_references" for k in fields)
        if not business:
            raise RevisionError(409)
        raw={"changed_fields":fields,"business_changed":business}
        return RevisionDiff(**raw,diff_sha256=canonical_request_hash(raw))
    except RevisionError:
        raise
    except (ValueError,TypeError,KeyError,AttributeError):
        raise RevisionError(422) from None
