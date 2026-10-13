"""Explicit finite worker runner; never constructs credentials or migrations."""
from uuid import uuid4
if __package__:
    from .app.jobs.service import JobsService
    from .app.notifications.schemas import NotificationError
else:
    from app.jobs.service import JobsService
    from app.notifications.schemas import NotificationError


def run_once(service,*,worker_id=None):
    if not isinstance(service,JobsService):
        raise NotificationError()
    service._ready()
    worker_id=worker_id if worker_id is not None else uuid4()
    service.enqueue_outbox(limit=100)
    claim=service.claim(worker_id)
    if claim is None:
        return None
    try:
        return service.run_claim(claim)
    except NotificationError as error:
        if error.status_code==503:
            return service.retry_claim(claim)
        raise


def drain(service,*,max_steps=100,worker_id=None):
    if type(max_steps) is not int or not 1<=max_steps<=100:
        raise NotificationError(422)
    worker_id=worker_id if worker_id is not None else uuid4()
    results=[]
    for _ in range(max_steps):
        result=run_once(service,worker_id=worker_id)
        if result is None:
            break
        results.append(result)
    return tuple(results)
