import { reactive } from 'vue'
import type { PublicOfferingData } from '../../../../../packages/contracts/v2/public_catalog/generated'
import { validOffering } from '../catalog/validation'
import { createQAApi, QAError, type QAApi, type QAAnswerData, type QAContextData, type RetrievalRequest } from './client'
import { bindsOffering, intents, requestFor, sameValue, validAnswer, validContext } from './validation'

export function useQA(api: QAApi = createQAApi()) {
  const state = reactive({ expanded: false, target: null as PublicOfferingData | null, context: null as QAContextData | null,
    intent: null as RetrievalRequest['intent'] | null, keywords: '', result: null as QAAnswerData | null,
    busy: false, status: 'idle' as 'idle' | 'checking' | 'asking' | 'ready' | 'unknown' | 'error', message: '', error: null as number | null })
  let generation = 0, pending: AbortController | null = null, disposed = false
  function cancel() { generation++; pending?.abort(); pending = null; state.busy = false }
  function clearResult() { cancel(); state.result = null; state.message = ''; state.error = null; state.status = 'idle' }
  function setTarget(value: PublicOfferingData | null) {
    clearResult(); state.context = null; state.intent = null; state.keywords = ''
    state.target = value && validOffering(value) ? JSON.parse(JSON.stringify(value)) as PublicOfferingData : null
    if (value && !state.target) state.message = '所选公开项目未通过验证，请明确重新查询。'
  }
  function setExpanded(value: boolean) {
    if (typeof value !== 'boolean' || disposed) return
    clearResult(); state.context = null; state.intent = null; state.keywords = ''; state.expanded = value
  }
  function setIntent(value: string) {
    clearResult(); state.intent = (intents as readonly string[]).includes(value) ? value as RetrievalRequest['intent'] : null
  }
  function setKeywords(value: string) { clearResult(); state.keywords = typeof value === 'string' ? value : '' }
  function currentRequest(): RetrievalRequest | null {
    if (!state.target || !state.intent) return null
    try { return requestFor(state.target, state.intent, state.keywords === '' ? [] : state.keywords.split('\n')) } catch { return null }
  }
  function canAsk() { return !disposed && state.expanded && !state.busy && state.context?.can_ask === true && currentRequest() !== null }
  async function perform(kind: 'checking' | 'asking', work: (signal: AbortSignal) => Promise<void>) {
    cancel(); const g = generation, controller = new AbortController(); pending = controller
    state.result = null; state.error = null; state.message = ''; state.status = kind; state.busy = true
    try { await work(controller.signal) }
    catch (error) { if (g === generation && !disposed && !controller.signal.aborted) { state.context = null; state.result = null; state.status = 'error'; state.error = error instanceof QAError ? error.status : 200; state.message = error instanceof QAError ? error.message : new QAError(200).message } }
    finally { if (g === generation && !disposed) { pending = null; state.busy = false } }
  }
  async function checkContext() {
    if (disposed || !state.expanded || state.busy) return
    state.context = null
    await perform('checking', async signal => {
      const g = generation, context = await api.context(signal)
      if (signal.aborted || g !== generation || disposed) return
      if (!validContext(context)) throw new QAError(200)
      state.context = JSON.parse(JSON.stringify(context)) as QAContextData; state.status = 'ready'
      state.message = context.can_ask ? '合成离线问答入口可用。请核对当前项目与问题类型后明确提问。' : context.disabled_reason === 'MODEL_DISABLED' ? new QAError(503, 'MODEL_DISABLED').message : new QAError(503, context.disabled_reason ?? 'QA_UNAVAILABLE').message
    })
  }
  async function ask() {
    if (!canAsk()) return
    const input = currentRequest()!, expected = JSON.parse(JSON.stringify(input)) as RetrievalRequest, target = JSON.parse(JSON.stringify(state.target)) as PublicOfferingData
    await perform('asking', async signal => {
      const g = generation, answer = await api.answer(input, signal)
      if (signal.aborted || g !== generation || disposed) return
      if (!await validAnswer(answer, expected) || !bindsOffering(answer, target)) throw new QAError(200)
      if (signal.aborted || g !== generation || disposed || !sameValue(target, state.target)) return
      state.result = JSON.parse(JSON.stringify(answer)) as QAAnswerData; state.status = answer.status === 'unknown' ? 'unknown' : 'ready'
      state.message = answer.status === 'unknown' ? '当前无法形成有依据的引用回答。未知项保持未知，不补造数字、日期或资格。' : '以下为本次核验通过的公开类型化引用；不表示本人资格或录取结论。'
    })
  }
  function dispose() { disposed = true; clearResult(); state.context = null; state.target = null; state.intent = null; state.keywords = ''; state.expanded = false }
  return { state, setTarget, setExpanded, setIntent, setKeywords, currentRequest, canAsk, checkContext, ask, dispose }
}
