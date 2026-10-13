import type { ProfileVersionData } from '../../profiles/client'
import { snapshotHash } from '../../profiles/client'
import { adaptationOf } from '../../profiles/form'
import { utcMicros } from '../validation'
import { wire } from '../revisions/validation'
import { exact, hash, integer, member, nullable, utc, uuid } from '../../catalog/validation'
import type { MarkReadInput, NotificationContextData, NotificationData, NotificationPage, NotificationPreferenceData, PreferenceInput } from '../../../../../../packages/contracts/v2/notifications/generated'

export const reasons = ['MEMBER_ADDED', 'MEMBER_REMOVED', 'BUSINESS_CHANGED', 'RELEASE_WINDOW_CHANGED', 'RULESET_CHANGED', 'RELEASE_WITHDRAWN', 'REFERENCE_REPLACED'] as const
export const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value))
export function validContext(value: unknown): value is NotificationContextData {
  return exact(value, ['schema_version', 'can_read', 'can_manage_preferences', 'can_mark_read', 'is_synthetic', 'delivery_channel', 'external_delivery_enabled'])
    && value.schema_version === 'v2.t36' && ['can_read', 'can_manage_preferences', 'can_mark_read', 'is_synthetic'].every(key => typeof value[key] === 'boolean')
    && value.delivery_channel === 'in_app' && value.external_delivery_enabled === false
}
export function validPreference(value: unknown): value is NotificationPreferenceData {
  if (!exact(value, ['version', 'enabled', 'profile_id', 'profile_version_id', 'profile_sha256', 'is_synthetic', 'updated_at'])
    || !integer(value.version, 0) || typeof value.enabled !== 'boolean' || typeof value.is_synthetic !== 'boolean'
    || !nullable(value.profile_id, uuid) || !nullable(value.profile_version_id, uuid) || !nullable(value.profile_sha256, hash) || !nullable(value.updated_at, utc)) return false
  const bound = [value.profile_id, value.profile_version_id, value.profile_sha256]
  return (value.enabled ? bound.every(item => item !== null) : bound.every(item => item === null))
    && (value.version === 0) === (value.updated_at === null) && (value.version !== 0 || value.enabled === false)
}
export function validNotification(value: unknown): value is NotificationData {
  if (!exact(value, ['id', 'version', 'event_id', 'assessment_id', 'profile_id', 'profile_version_id', 'profile_sha256', 'is_synthetic', 'reason', 'needs_review', 'dataset_id', 'entry_year', 'offering_id', 'offering_version', 'before_release_id', 'after_release_id', 'created_at', 'expires_at', 'read_at'])
    || !['id', 'event_id', 'assessment_id', 'profile_id', 'profile_version_id', 'dataset_id', 'offering_id'].every(key => uuid(value[key]))
    || !integer(value.version, 1, 2) || !hash(value.profile_sha256) || typeof value.is_synthetic !== 'boolean' || !member(value.reason, reasons)
    || value.needs_review !== (value.reason !== 'REFERENCE_REPLACED') || !integer(value.entry_year, 1, 9999) || !integer(value.offering_version)
    || !nullable(value.before_release_id, uuid) || !nullable(value.after_release_id, uuid) || value.before_release_id === null && value.after_release_id === null
    || !utc(value.created_at) || !utc(value.expires_at) || !nullable(value.read_at, utc)) return false
  const readAt = value.read_at as string | null
  return utcMicros(value.created_at) < utcMicros(value.expires_at) && (value.version === 2) === (readAt !== null)
    && (readAt === null || utcMicros(value.created_at) <= utcMicros(readAt) && utcMicros(readAt) < utcMicros(value.expires_at))
}
export const cursor = (value: unknown): value is string => typeof value === 'string' && value.length >= 1 && value.length <= 1024 && !/[\u0000-\u0020\u007f-\u009f]/.test(value) && !/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/.test(value)
export function validPage(value: unknown): value is NotificationPage {
  return exact(value, ['items', 'next_cursor']) && Array.isArray(value.items) && value.items.length <= 20 && value.items.every(validNotification)
    && new Set(value.items.map(item => item.id)).size === value.items.length && nullable(value.next_cursor, cursor)
}
export function validPreferenceInput(value: unknown): value is PreferenceInput {
  return exact(value, ['expected_version', 'enabled', 'profile_id', 'student_confirmed']) && integer(value.expected_version, 0)
    && typeof value.enabled === 'boolean' && nullable(value.profile_id, uuid) && value.enabled === (value.profile_id !== null) && value.student_confirmed === true
}
export function validReadInput(value: unknown): value is MarkReadInput {
  return exact(value, ['expected_version', 'student_confirmed']) && integer(value.expected_version) && value.student_confirmed === true
}
export function sameContent(before: NotificationData, after: NotificationData): boolean {
  return Object.keys(before).every(key => key === 'version' || key === 'read_at' || before[key as keyof NotificationData] === after[key as keyof NotificationData])
}

// Reuse the existing closed profile contract; enabling never invents a profile.
export async function validSelectedProfile(value: unknown): Promise<boolean> {
  if (!wire('ProfileVersionData', value)) return false
  const profile = value as ProfileVersionData
  const adaptation = adaptationOf(profile.profile)
  return profile.profile_sha256 === await snapshotHash(profile.profile)
    && profile.adaptation.status === adaptation.status
    && profile.adaptation.reason === adaptation.reason
    && utcMicros(profile.confirmed_at) < utcMicros(profile.expires_at)
}
