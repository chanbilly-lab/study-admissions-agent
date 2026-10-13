import { createHash } from 'node:crypto'
import { vi } from 'vitest'
import type { SessionData } from '../src/features/auth/client'
import type { ProfileApi, ProfileContextData, ProfileSnapshot, ProfileVersionData } from '../src/features/profiles/client'
import { adaptationOf } from '../src/features/profiles/form'
export const actor: SessionData = { authenticated: true, user_id: '0e3ef957-3cdd-4f44-8147-b0fe1d46b8f8', expires_at: '2030-10-02T12:00:00Z', is_synthetic: true, private_business_available: false }
export const otherActor: SessionData = { ...actor, user_id: '4bb88d93-b551-4b5a-a027-83a95a0c8476' }
export const rootId = '65a4e557-ccbd-428a-a8ef-5393f4dc4e55', versionId = '1a19e89e-a5a1-41d4-9cbc-106fce48f9a9'
export const nextVersionId = '6891c456-237d-4c7c-afc3-b03f0ce1bf0d'
export const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value))
export function hash(value: unknown): string {
  function order(item: unknown): unknown { return Array.isArray(item) ? item.map(order) : item !== null && typeof item === 'object' ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([key, field]) => [key, order(field)])) : item }
  return createHash('sha256').update(JSON.stringify(order(value))).digest('hex')
}
export function snapshot(overrides: Partial<ProfileSnapshot> = {}): ProfileSnapshot {
  const known = (value: string) => ({ status: 'known' as const, value })
  return { study_level: 'bachelor', entry_year: 2027, residence_region: known('HK'), course_system: known('gaokao'),
    applicant_category: known('cn_mainland'), exam_province: known('DEMO_PROVINCE'), pathway: known('gaokao'), subjects: ['physics'],
    assessments: { math: { achieved: { status: 'provided', value: '0', scale: '100', unit: 'points' }, predicted: { status: 'pending', value: null, scale: null, unit: null } } },
    weekly_hours: null, preferences: null, ...overrides }
}
export function version(overrides: Partial<ProfileVersionData> = {}): ProfileVersionData {
  const profile = overrides.profile ?? snapshot()
  return { profile_id: rootId, version_id: versionId, version: 1, profile, profile_sha256: hash(profile), confirmed_at: '2026-10-03T00:00:00Z',
    source: 'student_declared', expires_at: '2028-10-03T00:00:00Z', is_synthetic: true, adaptation: adaptationOf(profile), ...overrides }
}
export const context = (overrides: Partial<ProfileContextData> = {}): ProfileContextData => ({ schema_version: 'v2.t23', can_create: true, can_read: true, can_append: true, reason: 'allowed', is_synthetic: true, ...overrides })
export function page() { const { profile_id, version_id, version: number, confirmed_at, expires_at, is_synthetic } = version(); return { items: [{ profile_id, version_id, version: number, confirmed_at, expires_at, is_synthetic }], next_cursor: null } }
export function profileApi(overrides: Partial<ProfileApi> = {}): ProfileApi {
  return { context: vi.fn(async () => context()), list: vi.fn(async () => page()), current: vi.fn(async () => version()), history: vi.fn(async () => version()),
    create: vi.fn(async input => ({ version: version({ profile: clone(input.profile) }), replayed: false })),
    append: vi.fn(async (_id, input) => ({ version: version({ version: input.expected_current_version + 1, version_id: nextVersionId, profile: clone(input.profile) }), replayed: false })), ...overrides }
}
export function deferred<T>() { let resolve!: (value: T) => void, reject!: (error: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
export function meta(value: unknown = null) {
  const data = value as { version?: ProfileVersionData; version_id?: string; is_synthetic?: boolean } | null
  const bound = data?.version && typeof data.version === 'object' ? data.version : data?.version_id ? data : null
  return { api_version: 'v2', request_id: 'a'.repeat(32), data_as_of: null, profile_version_id: bound?.version_id ?? null,
    release_id: null, ruleset_version: null, profile_mode: bound ? bound.is_synthetic ? 'synthetic' : 'real' : null, data_mode: 'verified', model_mode: 'disabled' }
}
export function response(data: unknown, metadata = meta(data)) { return new Response(JSON.stringify({ data, meta: metadata }), { status: 200 }) }
export const csrf = () => new Response(JSON.stringify({ data: { csrf_token: 'T'.repeat(43), expires_at: actor.expires_at }, meta: {} }), { status: 200 })
