import { vi } from 'vitest'
import type { SharingApi, SharingPolicyData, GrantData, GrantListData, GrantMutationData } from '../src/features/sharing/client'
import { actor, otherActor, consentId, noticeId } from './privacyFixtures'
export { actor, otherActor, deferred } from './privacyFixtures'
export const resourceId = '7665e851-b1e2-4c19-a4dd-e647b93146a7'
export const grantId = 'ed0c1a6e-3e12-4c10-bcc2-c3ec6859d322'
export const now = Date.parse('2026-10-03T00:00:00Z')
export function policy(overrides: Partial<SharingPolicyData> = {}): SharingPolicyData {
  return { policy_version: 'T09_sharing_v1', text: 'DEMO 合成共享告知；核心用途不包含第三方共享。', text_sha256: 'b'.repeat(64),
    sharing_available: true, readiness_reason: 'synthetic_test_ready', is_synthetic: true, max_duration_seconds: 2592000,
    scope_matrix: ['profile', 'plan', 'attachment', 'export', 'job'].map(kind => ({ resource_type: kind as GrantData['resource_type'], fields: ['status', 'version'], actions: ['read', 'list'] })),
    guardian_verification_available: false, private_business_available: false, ...overrides }
}
export function grant(overrides: Partial<GrantData> = {}): GrantData {
  return { id: grantId, resource_type: 'profile', resource_id: resourceId, resource_version: 1, owner_user_id: actor.user_id, grantee_user_id: otherActor.user_id,
    fields: ['status'], actions: ['read'], created_at: '2026-10-03T00:00:00Z', expires_at: '2026-10-04T00:00:00Z', accepted_at: null, revoked_at: null,
    state: 'pending', version: 1, sharing_policy_version: 'T09_sharing_v1', is_synthetic: true, access_active: false, ...overrides }
}
export function grants(overrides: Partial<GrantListData> = {}): GrantListData {
  return { user_id: actor.user_id, revision: 0, actor_declaration_id: noticeId, owner_consent_id: consentId, sharing_available: true,
    total: 0, items: [], page: { limit: 20, has_more: false, next_cursor: null }, ...overrides }
}
export function mutation(overrides: Partial<GrantMutationData> = {}): GrantMutationData { return { user_id: actor.user_id, revision: 1, grant: grant(), ...overrides } }
export function sharingApi(overrides: Partial<SharingApi> = {}) {
  return { policy: vi.fn(async () => policy()), list: vi.fn(async () => grants()), create: vi.fn(async () => mutation()),
    accept: vi.fn(async () => mutation({ user_id: otherActor.user_id, grant: grant({ state: 'accepted', version: 2, accepted_at: '2026-10-03T00:00:01Z', access_active: true }) })),
    revoke: vi.fn(async () => mutation({ grant: grant({ state: 'revoked', version: 2, revoked_at: '2026-10-03T00:00:02Z' }) })), ...overrides }
}
