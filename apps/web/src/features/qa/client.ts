import type { QAAnswerData, QAContextData, RetrievalRequest } from '../../../../../packages/contracts/v2/qa/generated'
import { exact, member, prefixBase, validMeta } from '../catalog/validation'
import { validAnswer, validContext, validRequest } from './validation'
export type { QAAnswerData, QAContextData, RetrievalRequest }

export const errorCodes = ['MODEL_DISABLED', 'LIVE_UNAVAILABLE', 'MODEL_TIMEOUT', 'BUDGET_EXHAUSTED', 'CONCURRENCY_LIMIT', 'KEY_LIMIT', 'BUDGET_UNAVAILABLE', 'INVALID_PROVIDER_RESPONSE', 'PROVIDER_FAILURE', 'CITATION_CONFLICT', 'QA_UNAVAILABLE', 'INVALID_RETRIEVAL_INPUT'] as const
export type QAErrorCode = typeof errorCodes[number]
const messages: Record<QAErrorCode, string> = {
  MODEL_DISABLED: '模型问答未启用。公开目录与确定性资格检查仍可独立使用。',
  LIVE_UNAVAILABLE: '真实模型未开放，本次没有回退到演示回答。',
  MODEL_TIMEOUT: '问答等待超时，本次没有确认回答。不会自动重试。',
  BUDGET_EXHAUSTED: '共享问答额度已达到上限，本次没有回答。不会自动重试。',
  CONCURRENCY_LIMIT: '当前问答并发已达到上限，请稍后明确重新检查入口。',
  KEY_LIMIT: '当前问答预算不可受理，本次没有回答。',
  BUDGET_UNAVAILABLE: '问答预算服务不可用，本次没有回答。',
  INVALID_PROVIDER_RESPONSE: '模型返回内容未通过验证，本次没有确认回答。',
  PROVIDER_FAILURE: '模型接口失败，本次没有回退回答。',
  CITATION_CONFLICT: '引用、适用范围或当前发布已变化。请重新读取项目并明确检查入口。',
  QA_UNAVAILABLE: '证据问答不可用或返回内容未通过验证，本次没有确认回答。',
  INVALID_RETRIEVAL_INPUT: '请核对明确项目、问题类型与最多五个合法关键词。',
}
export class QAError extends Error {
  readonly code: QAErrorCode
  constructor(public readonly status: number, code?: QAErrorCode) {
    const fixed = code ?? (status === 409 ? 'CITATION_CONFLICT' : status === 429 ? 'BUDGET_EXHAUSTED' : status === 422 ? 'INVALID_RETRIEVAL_INPUT' : 'QA_UNAVAILABLE')
    super(messages[fixed]); this.name = 'QAError'; this.code = fixed
  }
}
export interface QAApi {
  context(signal?: AbortSignal): Promise<QAContextData>
  answer(input: RetrievalRequest, signal?: AbortSignal): Promise<QAAnswerData>
}
async function readJson(response: Response): Promise<unknown> {
  if (!/^application\/json(?:\s*;|$)/i.test(response.headers.get('Content-Type') ?? '')) throw new Error('Invalid QA response')
  const reader = response.body?.getReader()
  if (!reader) throw new Error('Invalid QA response')
  let total = 0
  const chunks: Uint8Array[] = []
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      total += value.byteLength
      if (total > 524288) { void reader.cancel(); throw new Error('Invalid QA response') }
      chunks.push(value)
    }
  } finally { reader.releaseLock() }
  const bytes = new Uint8Array(total)
  let offset = 0
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength }
  return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)) as unknown
}
async function responseError(response: Response): Promise<QAError> {
  try {
    const body = await readJson(response)
    if (!exact(body, ['error']) || !exact(body.error, ['code', 'message', 'request_id', 'details']) || typeof body.error.request_id !== 'string' || !/^[0-9a-f]{32}$/.test(body.error.request_id) || response.headers.get('X-Request-ID') !== body.error.request_id || !response.headers.get('Cache-Control')?.split(',').some(v => v.trim().toLowerCase() === 'no-store') || !Array.isArray(body.error.details) || body.error.details.length > 20) return new QAError(response.status)
    const codes = body.error.details.filter(item => exact(item, ['field_path', 'code', 'message']) && member(item.code, errorCodes)).map(item => item.code as QAErrorCode)
    return new QAError(response.status, codes.length === 1 ? codes[0] : undefined)
  } catch { return new QAError(response.status) }
}
export function createQAApi(prefix = '/qa', fetcher: typeof fetch = fetch): QAApi {
  let base: string
  try { base = prefixBase(prefix) } catch { throw new QAError(422) }
  async function call(path: string, input?: RetrievalRequest, signal?: AbortSignal): Promise<QAContextData | QAAnswerData> {
    if (input !== undefined && (input === null || typeof input !== 'object' || Object.getPrototypeOf(input) !== Object.prototype)) throw new QAError(422)
    const normalized = input === undefined ? undefined : { ...input, keywords: input.keywords === undefined ? [] : input.keywords }
    if (normalized !== undefined && !validRequest(normalized)) throw new QAError(422)
    const frozen = normalized === undefined ? undefined : JSON.parse(JSON.stringify(normalized)) as RetrievalRequest
    const body = frozen === undefined ? undefined : JSON.stringify(frozen)
    if (body !== undefined && new TextEncoder().encode(body).byteLength > 16384) throw new QAError(422)
    let successful = false
    try {
      const response = await fetcher(base + path, { method: frozen === undefined ? 'GET' : 'POST', headers: { Accept: 'application/json', ...(frozen === undefined ? {} : { 'Content-Type': 'application/json' }) }, body, credentials: 'omit', cache: 'no-store', redirect: 'error', signal })
      successful = response.status === 200
      if (!successful) throw await responseError(response)
      const envelope = await readJson(response)
      if (!exact(envelope, ['data', 'meta']) || !validMeta(envelope.meta, response)) throw new QAError(200)
      const mode = (envelope.meta as { data_mode: string; model_mode: string })
      if (frozen === undefined) {
        if (!validContext(envelope.data) || envelope.data.model_mode !== mode.model_mode || envelope.data.allow_test_fixture_read && mode.data_mode !== 'demo') throw new QAError(200)
      } else if (!await validAnswer(envelope.data, frozen) || mode.model_mode !== 'mock' || mode.data_mode !== 'demo') throw new QAError(200)
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
      return envelope.data as QAContextData | QAAnswerData
    } catch (error) {
      if (error instanceof QAError || signal?.aborted) throw error
      throw new QAError(successful ? 200 : 0)
    }
  }
  return { context: signal => call('/qa/context', undefined, signal) as Promise<QAContextData>, answer: (input, signal) => call('/qa/answers', input, signal) as Promise<QAAnswerData> }
}
