import { createHash } from 'node:crypto'
import { vi } from 'vitest'
import type { CitationData, QAAnswerData, QAContextData, RetrievalRequest } from '../../../packages/contracts/v2/qa/generated'
import type { PublicFactData, PublicOfferingData } from '../../../packages/contracts/v2/public_catalog/generated'
import type { QAApi } from '../src/features/qa/client'
import { requestFor } from '../src/features/qa/validation'
import { offering, publicEvidence, publicFact } from './catalogUiFixtures'
import { clone, hash } from './profilesFixtures'
export { clone, deferred } from './profilesFixtures'
export { uid } from './catalogUiFixtures'

export function target(fact: PublicFactData = publicFact({ footnote_text: 'DEMO_仅适用本范围' })): PublicOfferingData { return offering({ facts: [fact] }) }
export function request(item = target(), intent: RetrievalRequest['intent'] = 'requirements'): RetrievalRequest { return requestFor(item, intent) }
export function context(overrides: Partial<QAContextData> = {}): QAContextData {
  return { schema_version: 'v2.t39', can_ask: true, model_mode: 'mock', live_available: false, real_processing_enabled: false,
    allow_test_fixture_read: true, demo_banner: 'DEMO：合成测试资料，不是真实招生依据', disabled_reason: null, budget_unit: 'conservative_utf8_bytes', ...overrides }
}
export function closedContext(): QAContextData { return context({ can_ask: false, model_mode: 'disabled', allow_test_fixture_read: false, demo_banner: null, disabled_reason: 'MODEL_DISABLED' }) }
export function rehash(c: CitationData): CitationData {
  const { id: _id, version: _version, content_sha256: _sha, ...projection } = c
  c.content_sha256 = hash(projection)
  const digest = c.content_sha256
  const raw = digest.slice(0, 12) + '4' + digest.slice(13, 16) + ((parseInt(digest[16]!, 16) & 3) | 8).toString(16) + digest.slice(17, 32)
  c.id = `${raw.slice(0,8)}-${raw.slice(8,12)}-${raw.slice(12,16)}-${raw.slice(16,20)}-${raw.slice(20,32)}`
  return c
}
export function answer(item = target(), input = request(item)): QAAnswerData {
  const evidence = publicEvidence(item)
  evidence.quote = `DEMO_合成原文 <img src=https://source-sentinel.invalid/x onerror=window.__qa=1>\n${item.facts[0]!.value_text} ${item.facts[0]!.unit ?? ''}`
  evidence.snippet_sha256 = createHash('sha256').update(evidence.quote).digest('hex')
  evidence.locator.byte_end = new TextEncoder().encode(evidence.quote).length
  const citation = rehash({ id: evidence.evidence_id, version: 1, evidence_id: evidence.evidence_id, release_id: item.release_id, release_version: 1,
    requirements_version: item.requirements_version, offering_id: item.id, offering_version: item.version, entry_year: item.entry_year, scope: clone(item.scope),
    is_synthetic: true, field_key: item.facts[0]!.field_key, fact: clone(item.facts[0]!), evidence, content_sha256: '0'.repeat(64) })
  return { schema_version: 'v2.t39', status: 'answered', request: clone(input), model_scope: { dataset_id: item.scope.dataset_id, offering_id: item.id, offering_version: item.version, entry_year: item.entry_year },
    release_version: 1, requirements_version: item.requirements_version, content_sha256: item.content_sha256, citations: [citation], advice_codes: ['REVIEW_SOURCE'], unknown_reasons: [],
    is_synthetic: true, model_mode: 'mock', live_available: false, generated_at: '2026-10-04T06:00:00.123456Z' }
}
export function unknown(item = target(), input = request(item), unresolved = false): QAAnswerData {
  const result = answer(item, input); result.status = 'unknown'; result.citations = []; result.advice_codes = []
  if (unresolved) { result.model_scope = null; result.release_version = null; result.requirements_version = null; result.content_sha256 = null; result.is_synthetic = null; result.unknown_reasons = ['NO_PUBLIC_EVIDENCE'] }
  return result
}
export function api(overrides: Partial<QAApi> = {}, item = target()): QAApi { return { context: vi.fn(async () => context()), answer: vi.fn(async input => answer(item, input)), ...overrides } }
export function meta(mode = 'mock', dataMode = 'demo') { return { api_version: 'v2', request_id: 'a'.repeat(32), data_as_of: null, profile_version_id: null, release_id: null, ruleset_version: null, profile_mode: null, data_mode: dataMode, model_mode: mode } }
export function response(data: unknown, metadata = meta()): Response { return new Response(JSON.stringify({ data, meta: metadata }), { status: 200, headers: { 'Content-Type': 'application/json', 'X-Request-ID': metadata.request_id, 'Cache-Control': 'no-store' } }) }
export function failure(status: number, code: string): Response { return new Response(JSON.stringify({ error: { code: status === 409 ? 'CONFLICT' : 'SERVICE_UNAVAILABLE', message: 'RAW_SECRET_do_not_render', request_id: 'a'.repeat(32), details: [{ field_path: 'qa', code, message: 'RAW_SECRET_quote_prompt' }] } }), { status, headers: { 'Content-Type': 'application/json', 'X-Request-ID': 'a'.repeat(32), 'Cache-Control': 'no-store' } }) }
