"""The notification tables share the explicit T36 migration metadata."""

from ..jobs.models import JobsBase, NotificationPreference, InboxNotification

NotificationsBase = JobsBase
