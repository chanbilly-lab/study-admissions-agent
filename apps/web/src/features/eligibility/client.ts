import type { AssessmentContextData, AssessmentData, AssessmentRequest, ReplayRequest } from '../../../../../packages/contracts/v2/assessments/generated'
import { createSessionApi, SessionError } from '../auth/client'
import { canonicalHash, exact, prefixBase, uuid, validMeta } from '../catalog/validation'
import { validAssessment, validContext, validRequest } from './validation'
export type { AssessmentContextData, AssessmentData, AssessmentRequest, ReplayRequest }
export class EligibilityError extends Error {
  constructor(public readonly status: number) { super(({ 401: '会话已失效，请重新登录。', 403: '本人准入或对象权限已失效，私人评估已清空。', 404: '指定评估不存在或不可读取。', 409: '画像或项目依据已变化，请明确重新读取并确认。', 422: '评估输入未通过校验。', 503: '评估服务尚未开放或暂不可用。' }[status] ?? '评估响应未通过验证，结果未确认。')); this.name = 'EligibilityError' }
}
export interface EligibilityApi {
  context(signal?: AbortSignal): Promise<AssessmentContextData>
  evaluate(request: AssessmentRequest, signal?: AbortSignal): Promise<AssessmentData>
  get(id: string, signal?: AbortSignal): Promise<AssessmentData>
  replay(id: string, request: ReplayRequest, signal?: AbortSignal): Promise<AssessmentData>
}
export function createEligibilityApi(prefix = import.meta.env.VITE_AUTH_API_BASE_URL ?? '/api', fetcher: typeof fetch = fetch): EligibilityApi {
  let base: string
  try { base = prefixBase(prefix) + '/eligibility' } catch { throw new EligibilityError(422) }
  const session = createSessionApi(prefix, fetcher)
  async function request<T>(path: string, signal?: AbortSignal, input?: AssessmentRequest | ReplayRequest): Promise<T> {
    let token: string | undefined
    try {
      let bodyText: string | undefined, frozen: AssessmentRequest | ReplayRequest | undefined
      if (input) {
        if ('target' in input ? !validRequest(input) : !exact(input, ['confirmed']) || input.confirmed !== true) throw new EligibilityError(422)
        bodyText = JSON.stringify(input); if (new TextEncoder().encode(bodyText).length > 16384) throw new EligibilityError(422)
        frozen = JSON.parse(bodyText) as typeof input
        token = (await session.csrf(signal)).csrf_token
      }
      const response = await fetcher(base + path, { method: input ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal, headers: { Accept: 'application/json', ...(input ? { 'Content-Type': 'application/json', 'X-CSRF-Token': token! } : {}) }, ...(input ? { body: bodyText } : {}) })
      if (response.status !== 200) throw new EligibilityError(response.status)
      const body: unknown = await response.json()
      if (!exact(body, ['data', 'meta']) || !exact(body.meta, ['api_version', 'request_id', 'data_as_of', 'profile_version_id', 'release_id', 'ruleset_version', 'profile_mode', 'data_mode', 'model_mode']) || body.meta.data_mode !== 'verified' || body.meta.model_mode !== 'disabled') throw new EligibilityError(200)
      if (path === '/context') {
        if (!validContext(body.data) || !validMeta(body.meta, response)) throw new EligibilityError(200)
      } else {
        if (!await validAssessment(body.data)) throw new EligibilityError(200)
        const data = body.data as AssessmentData
        if (!validMeta(body.meta, response, data.profile_version_id, data.profile_is_synthetic)) throw new EligibilityError(200)
        if (frozen && 'target' in frozen) {
          if (data.profile_id !== frozen.profile_id || data.profile_version_id !== frozen.profile_version_id || data.release_id !== frozen.release_id || data.stage !== frozen.stage || data.replayed || await canonicalHash(data.target) !== await canonicalHash(frozen.target)) throw new EligibilityError(200)
        } else if (path !== '/context') {
          const id = path.split('/')[2]
          if (data.assessment_id !== id || data.replayed !== path.endsWith('/replay')) throw new EligibilityError(200)
        }
      }
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
      return body.data as T
    } catch (error) { if (error instanceof EligibilityError || signal?.aborted) throw error; if (error instanceof SessionError) throw new EligibilityError(error.status); throw new EligibilityError(0) } finally { token = undefined }
  }
  return { context: signal => request('/context', signal), evaluate: (input, signal) => request('/evaluations', signal, input),
    get(id, signal) { if (!uuid(id)) throw new EligibilityError(422); return request('/evaluations/' + id, signal) },
    replay(id, input, signal) { if (!uuid(id) || !exact(input, ['confirmed']) || input.confirmed !== true) throw new EligibilityError(422); return request('/evaluations/' + id + '/replay', signal, input) } }
}
