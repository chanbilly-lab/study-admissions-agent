import type { AdmissionData, AgeDeclarationInput, CoreConsentInput, PrivacyNoticeData } from '../../../../../packages/contracts/v2/identity/generated'
import { createSessionApi, SessionError } from '../auth/client'

export type { AdmissionData, AgeDeclarationInput, CoreConsentInput, PrivacyNoticeData }
export type AgeBand = AgeDeclarationInput['age_band']

export interface PrivacyApi {
  notice(signal?: AbortSignal): Promise<PrivacyNoticeData>
  admission(signal?: AbortSignal): Promise<AdmissionData>
  declareAge(input: AgeDeclarationInput, signal?: AbortSignal): Promise<AdmissionData>
  confirmCore(input: CoreConsentInput, signal?: AbortSignal): Promise<AdmissionData>
  withdraw(consentId: string, signal?: AbortSignal): Promise<AdmissionData>
}

const messages: Record<number, string> = {
  401: '当前应用会话已失效，请重新登录。',
  403: '当前请求未获准。资料处理未就绪、年龄政策或安全请求校验可能阻止了提交。',
  404: '当前 API 未开放隐私设置，资料处理保持关闭。',
  409: '告知或本人设置已发生变化。请重新读取，并再次明确确认。',
  422: '提交内容不符合当前隐私契约，请重新读取设置。',
  503: '隐私服务未启用或暂不可用，无法确认本次操作。',
}

export class PrivacyError extends Error {
  constructor(public readonly status: number, message = messages[status] ?? '无法读取隐私设置，请稍后重试。') {
    super(message)
    this.name = 'PrivacyError'
  }
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
function fields(value: Record<string, unknown>, keys: readonly string[]) {
  return Object.keys(value).length === keys.length && keys.every((key) => key in value)
}
function uuid(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
}
function nullable(value: unknown, validate: (value: unknown) => boolean) { return value === null || validate(value) }
function utcDate(value: unknown): value is string {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value) && Number.isFinite(Date.parse(value))
}
function string(value: unknown): value is string { return typeof value === 'string' }
function member(value: unknown, choices: readonly string[]) { return string(value) && choices.includes(value) }
const reasons = ['allowed', 'processing_disabled', 'age_missing', 'age_expired', 'notice_changed', 'policy_changed', 'consent_missing', 'consent_withdrawn', 'consent_invalidated', 'role_missing']

export function isAdmissionData(value: unknown): value is AdmissionData {
  if (!record(value) || !fields(value, ['user_id', 'revision', 'age_band', 'age_assurance', 'declared_at', 'declaration_expires_at', 'policy_version', 'notice_id', 'notice_version', 'consent_id', 'consent_status', 'core_consultation_allowed', 'reason', 'readiness', 'is_synthetic', 'private_business_available'])) return false
  return uuid(value.user_id) && Number.isSafeInteger(value.revision) && Number(value.revision) >= 0
    && (value.age_band === null || value.age_band === '18_plus') && member(value.age_assurance, ['unknown', 'declared'])
    && nullable(value.declared_at, utcDate) && nullable(value.declaration_expires_at, utcDate)
    && string(value.policy_version) && nullable(value.notice_id, uuid) && nullable(value.notice_version, string)
    && nullable(value.consent_id, uuid) && member(value.consent_status, ['not_confirmed', 'active', 'withdrawn', 'invalidated'])
    && typeof value.core_consultation_allowed === 'boolean' && member(value.reason, reasons)
    && typeof value.readiness === 'boolean' && typeof value.is_synthetic === 'boolean' && value.private_business_available === false
}

export function isPrivacyNoticeData(value: unknown): value is PrivacyNoticeData {
  if (!record(value) || !fields(value, ['policy_version', 'notice_id', 'notice_version', 'notice_hash', 'text', 'is_synthetic', 'readiness', 'readiness_reason', 'purposes', 'age_policy', 'retention_policy'])) return false
  if (!string(value.policy_version) || !nullable(value.notice_id, uuid) || !nullable(value.notice_version, string)
    || !string(value.notice_hash) || !string(value.text) || typeof value.is_synthetic !== 'boolean' || typeof value.readiness !== 'boolean'
    || !member(value.readiness_reason, ['processing_disabled', 'test_fixture_ready'])
    || !Array.isArray(value.purposes) || !value.purposes.every((purpose) => purpose === 'core_consultation')) return false
  const age = value.age_policy
  const retention = value.retention_policy
  return record(age) && fields(age, ['under_14', 'age_14_17', 'age_18_plus', 'unknown', 'guardian_verification_available', 'declaration_is_verification'])
    && age.under_14 === 'public_only' && age.age_14_17 === 'private_disabled' && age.age_18_plus === 'self_declaration_and_confirmation'
    && age.unknown === 'public_only' && age.guardian_verification_available === false && age.declaration_is_verification === false
    && record(retention) && fields(retention, ['file_types', 'max_file_bytes', 'private_data_max_months', 'online_deletion_max_days', 'sanitized_logs_max_days', 'audit_authorization_max_months', 'backup_max_days', 'cleanup_implemented'])
    && Array.isArray(retention.file_types) && retention.file_types.every((type) => member(type, ['pdf', 'utf8_csv', 'json']))
    && retention.max_file_bytes === 10485760 && retention.private_data_max_months === 24 && retention.online_deletion_max_days === 30
    && retention.sanitized_logs_max_days === 30 && retention.audit_authorization_max_months === 24 && retention.backup_max_days === 35 && retention.cleanup_implemented === false
}

export function createPrivacyApi(basePrefix = import.meta.env.VITE_AUTH_API_BASE_URL ?? '/api', fetcher: typeof fetch = fetch): PrivacyApi {
  // Reuse the same-origin CSRF client. The proof exists only in a local call;
  // neither the privacy state nor browser storage receives it.
  const sessionApi = createSessionApi(basePrefix, fetcher)
  const prefix = basePrefix.replace(/\/$/, '')
  async function request<T>(path: string, validate: (value: unknown) => value is T, options: RequestInit): Promise<T> {
    let response: Response
    try {
      response = await fetcher(`${prefix}/v2/${path}`, { credentials: 'same-origin', cache: 'no-store', redirect: 'error', ...options })
    } catch (error) {
      if (options.signal?.aborted) throw error
      throw new PrivacyError(0, '无法连接隐私服务。本次提交或撤回状态无法确认，请重新读取。')
    }
    if (response.status !== 200) throw new PrivacyError(response.status)
    let body: unknown
    try { body = await response.json() } catch { throw new PrivacyError(200, '隐私服务返回了无法读取的响应。') }
    if (!record(body) || !fields(body, ['data', 'meta']) || !record(body.meta) || !validate(body.data)) {
      throw new PrivacyError(200, '隐私响应不符合契约，资料处理保持关闭。')
    }
    return body.data
  }
  async function write(path: string, method: 'POST' | 'DELETE', input: AgeDeclarationInput | CoreConsentInput | undefined, signal?: AbortSignal) {
    let token: string
    try { token = (await sessionApi.csrf(signal)).csrf_token }
    catch (error) {
      if (error instanceof SessionError) throw new PrivacyError(error.status)
      throw error
    }
    if (signal?.aborted) throw new DOMException('Request aborted', 'AbortError')
    return request(path, isAdmissionData, { method, signal,
      headers: { Accept: 'application/json', 'X-CSRF-Token': token, ...(input ? { 'Content-Type': 'application/json' } : {}) },
      ...(input ? { body: JSON.stringify(input) } : {}) })
  }
  return {
    notice: (signal) => request('privacy/notices/current', isPrivacyNoticeData, { method: 'GET', headers: { Accept: 'application/json' }, signal }),
    admission: (signal) => request('me/admission', isAdmissionData, { method: 'GET', headers: { Accept: 'application/json' }, signal }),
    declareAge: (input, signal) => write('me/age-declarations', 'POST', input, signal),
    confirmCore: (input, signal) => write('me/consents', 'POST', input, signal),
    withdraw: (consentId, signal) => {
      if (!uuid(consentId)) return Promise.reject(new PrivacyError(0, '用途确认标识无效。'))
      return write(`me/consents/${consentId}`, 'DELETE', undefined, signal)
    },
  }
}
