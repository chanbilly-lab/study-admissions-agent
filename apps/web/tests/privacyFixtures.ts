import { vi } from 'vitest'
import type { SessionData } from '../src/features/auth/client'
import type { AdmissionData, PrivacyApi, PrivacyNoticeData } from '../src/features/privacy/client'

export const actor: SessionData = { authenticated: true, user_id: '0e3ef957-3cdd-4f44-8147-b0fe1d46b8f8', expires_at: '2030-10-02T12:00:00Z', is_synthetic: true, private_business_available: false }
export const otherActor: SessionData = { ...actor, user_id: '4bb88d93-b551-4b5a-a027-83a95a0c8476' }
export const noticeId = '6d414865-2e62-40e8-b0a1-37dd949a31bc'
export const consentId = '169545a6-f5fd-4ec9-a74c-3750f50253bf'

export function notice(overrides: Partial<PrivacyNoticeData> = {}): PrivacyNoticeData {
  return { policy_version: 'T08_product_v1', notice_id: noticeId, notice_version: 'DEMO_notice_v1', notice_hash: 'a'.repeat(64),
    text: 'DEMO合成告知，仅用于离线验收。', is_synthetic: true, readiness: true, readiness_reason: 'test_fixture_ready', purposes: ['core_consultation'],
    age_policy: { under_14: 'public_only', age_14_17: 'private_disabled', age_18_plus: 'self_declaration_and_confirmation', unknown: 'public_only', guardian_verification_available: false, declaration_is_verification: false },
    retention_policy: { file_types: ['pdf', 'utf8_csv', 'json'], max_file_bytes: 10485760, private_data_max_months: 24, online_deletion_max_days: 30, sanitized_logs_max_days: 30, audit_authorization_max_months: 24, backup_max_days: 35, cleanup_implemented: false }, ...overrides }
}
export function admission(overrides: Partial<AdmissionData> = {}): AdmissionData {
  return { user_id: actor.user_id, revision: 0, age_band: null, age_assurance: 'unknown', declared_at: null, declaration_expires_at: null,
    policy_version: 'T08_product_v1', notice_id: noticeId, notice_version: 'DEMO_notice_v1', consent_id: null, consent_status: 'not_confirmed',
    core_consultation_allowed: false, reason: 'age_missing', readiness: true, is_synthetic: true, private_business_available: false, ...overrides }
}
export function declared(overrides: Partial<AdmissionData> = {}) {
  return admission({ revision: 1, age_band: '18_plus', age_assurance: 'declared', declared_at: '2026-10-03T00:00:00Z', declaration_expires_at: '2030-10-02T12:00:00Z', reason: 'consent_missing', ...overrides })
}
export function allowed(overrides: Partial<AdmissionData> = {}) {
  return declared({ revision: 2, consent_id: consentId, consent_status: 'active', core_consultation_allowed: true, reason: 'allowed', ...overrides })
}
export function privacyApi(overrides: Partial<PrivacyApi> = {}) {
  return { notice: vi.fn(async () => notice()), admission: vi.fn(async () => admission()), declareAge: vi.fn(async () => declared()),
    confirmCore: vi.fn(async () => allowed()), withdraw: vi.fn(async () => declared({ revision: 3, consent_id: consentId, consent_status: 'withdrawn', reason: 'consent_withdrawn' })), ...overrides }
}
export function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((success, failure) => { resolve = success; reject = failure })
  return { promise, resolve, reject }
}
