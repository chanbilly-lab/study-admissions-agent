import { vi } from 'vitest'
import type { NotificationApi, NotificationContextData, NotificationData, NotificationPage, NotificationPreferenceData } from '../src/features/plans/notifications/client'
import { actor, otherActor, version, clone, deferred } from './profilesFixtures'
import { id } from './catalogFixtures'
export { actor, otherActor, version, clone, deferred, id }
export const context = (fields: Partial<NotificationContextData> = {}): NotificationContextData => ({ schema_version: 'v2.t36', can_read: true, can_manage_preferences: true, can_mark_read: true, is_synthetic: true, delivery_channel: 'in_app', external_delivery_enabled: false, ...fields })
export function preference(enabled = false, number = enabled ? 1 : 0): NotificationPreferenceData {
  const p = version()
  return { version: number, enabled, profile_id: enabled ? p.profile_id : null, profile_version_id: enabled ? p.version_id : null,
    profile_sha256: enabled ? p.profile_sha256 : null, is_synthetic: true, updated_at: number ? '2026-10-04T01:00:00.123456Z' : null }
}
export function notification(read = false, fields: Partial<NotificationData> = {}): NotificationData {
  const p = version()
  return { id: id(1100), version: read ? 2 : 1, event_id: id(1101), assessment_id: id(1102), profile_id: p.profile_id, profile_version_id: p.version_id,
    profile_sha256: p.profile_sha256, is_synthetic: true, reason: 'BUSINESS_CHANGED', needs_review: true, dataset_id: id(100), entry_year: 2027,
    offering_id: id(1), offering_version: 1, before_release_id: id(103), after_release_id: id(1103), created_at: '2026-10-04T00:00:00.123456Z',
    expires_at: '2028-10-03T00:00:00.123456Z', read_at: read ? '2026-10-04T01:00:00.123456Z' : null, ...fields }
}
export function page(items = [notification()], next_cursor: string | null = null): NotificationPage { return { items, next_cursor } }
export function notificationApi(fields: Partial<NotificationApi> = {}): NotificationApi {
  let saved = preference()
  return { context: vi.fn(async () => context()), preferences: vi.fn(async () => clone(saved)),
    savePreferences: vi.fn(async input => { saved = preference(input.enabled, input.expected_version + 1); return clone(saved) }),
    list: vi.fn(async () => page()), markRead: vi.fn(async () => notification(true)), ...fields }
}
export function metadata(data: unknown, fields: Record<string, unknown> = {}) {
  const bound = data as { profile_version_id?: string | null; is_synthetic?: boolean }
  return { api_version: 'v2', request_id: 'f'.repeat(32), data_as_of: null, profile_version_id: bound.profile_version_id ?? null,
    release_id: null, ruleset_version: null, profile_mode: bound.profile_version_id ? bound.is_synthetic ? 'synthetic' : 'real' : null,
    data_mode: 'verified', model_mode: 'disabled', ...fields }
}
export function response(data: unknown, fields: Record<string, unknown> = {}) {
  return new Response(JSON.stringify({ data, meta: metadata(data, fields) }), { status: 200, headers: { 'X-Request-ID': 'f'.repeat(32), 'Cache-Control': 'no-store', 'Content-Type': 'application/json' } })
}
export const csrf = () => new Response(JSON.stringify({ data: { csrf_token: 'T'.repeat(43), expires_at: actor.expires_at }, meta: {} }), { status: 200 })
