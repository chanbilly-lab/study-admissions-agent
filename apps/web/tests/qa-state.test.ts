import { webcrypto } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useQA } from '../src/features/qa/useQA'
import { QAError } from '../src/features/qa/client'
import { answer, api, closedContext, clone, context, deferred, rehash, target, uid, unknown } from './qaFixtures'
beforeEach(() => vi.stubGlobal('crypto', webcrypto)); afterEach(() => vi.unstubAllGlobals())

async function ready(port = api()) {
  const state = useQA(port); state.setTarget(target()); state.setExpanded(true); state.setIntent('requirements'); await state.checkContext()
  expect(state.canAsk()).toBe(true); return state
}
describe('T39 explicit scoped QA state', () => {
  it('does no IO on construction, target changes or expansion, and never fills an intent', () => {
    const port = api(), workspace = useQA(port); workspace.setTarget(target()); workspace.setExpanded(true)
    expect(port.context).not.toHaveBeenCalled(); expect(port.answer).not.toHaveBeenCalled(); expect(workspace.state.intent).toBeNull(); expect(workspace.canAsk()).toBe(false)
  })
  it('requires a fresh explicit capability check and refuses a closed service even after selecting an intent', async () => {
    const port = api({ context: vi.fn(async () => closedContext()) }), workspace = useQA(port)
    workspace.setTarget(target()); workspace.setExpanded(true); workspace.setIntent('requirements'); await workspace.ask(); expect(port.answer).not.toHaveBeenCalled()
    await workspace.checkContext(); await workspace.ask(); expect(workspace.canAsk()).toBe(false); expect(workspace.state.message).toContain('未启用'); expect(port.answer).not.toHaveBeenCalled()
  })
  it('keeps number/unit/footnote literals and clears the result when a keyword changes', async () => {
    const workspace = await ready(); await workspace.ask()
    expect(workspace.state.result?.citations[0]?.fact.value_text).toBe('60.00'); expect(workspace.state.result?.citations[0]?.fact.normalized_value).toBe('60')
    workspace.setKeywords('数学'); expect(workspace.state.result).toBeNull(); expect(workspace.state.context?.can_ask).toBe(true)
    workspace.setKeywords('数学\n数学'); expect(workspace.canAsk()).toBe(false)
  })
  it.each(['target', 'intent', 'keywords', 'collapse', 'dispose'] as const)('ignores a successful answer delivered after %s invalidation even if the port ignores abort', async change => {
    const hold = deferred<ReturnType<typeof answer>>(), port = api({ answer: vi.fn(async () => hold.promise) }), workspace = await ready(port)
    const work = workspace.ask(); expect(workspace.state.busy).toBe(true)
    const signal = vi.mocked(port.answer).mock.calls[0]![1]!
    if (change === 'target') workspace.setTarget(target({ ...target().facts[0]!, field_key: 'DEMO_other' }))
    if (change === 'intent') workspace.setIntent('fees')
    if (change === 'keywords') workspace.setKeywords('费用')
    if (change === 'collapse') workspace.setExpanded(false)
    if (change === 'dispose') workspace.dispose()
    expect(signal.aborted).toBe(true); hold.resolve(answer()); await work
    expect(workspace.state.result).toBeNull(); expect(workspace.state.busy).toBe(false); expect(workspace.state.message).not.toContain('核验通过')
  })
  it('ignores a late context after a target change and requires another explicit check', async () => {
    const hold = deferred<ReturnType<typeof context>>(), port = api({ context: vi.fn(async () => hold.promise) }), workspace = useQA(port)
    workspace.setTarget(target()); workspace.setExpanded(true); workspace.setIntent('requirements'); const work = workspace.checkContext()
    workspace.setTarget({ ...target(), id: uid(99) }); hold.resolve(context()); await work
    expect(workspace.state.context).toBeNull(); expect(workspace.state.intent).toBeNull(); expect(workspace.canAsk()).toBe(false)
  })
  it('rechecking context removes an old answer before any response arrives', async () => {
    const port = api(), workspace = await ready(port); await workspace.ask(); expect(workspace.state.result).not.toBeNull()
    const hold = deferred<ReturnType<typeof context>>(); vi.mocked(port.context).mockImplementationOnce(async () => hold.promise)
    const work = workspace.checkContext(); expect(workspace.state.result).toBeNull(); expect(workspace.state.context).toBeNull()
    hold.resolve(context()); await work; expect(workspace.state.result).toBeNull()
  })
  it('rejects a mutated request from an injected port instead of confirming a different intent', async () => {
    const port = api({ answer: vi.fn(async input => { input.intent = 'fees'; return answer(target(), input) }) }), workspace = await ready(port)
    await workspace.ask(); expect(workspace.state.result).toBeNull(); expect(workspace.state.error).toBe(200); expect(workspace.state.context).toBeNull()
  })
  it('rejects a self-consistent citation whose changed unit is absent from the selected public facts', async () => {
    const data = answer(); data.citations[0]!.fact.unit = 'GBP'; rehash(data.citations[0]!)
    const workspace = await ready(api({ answer: vi.fn(async () => data) })); await workspace.ask()
    expect(workspace.state.error).toBe(200); expect(workspace.state.result).toBeNull()
  })
  it.each([503, 429, 409] as const)('clears capability and keeps failures separate from success at status %s', async status => {
    const port = api({ answer: vi.fn(async () => { throw new QAError(status, status === 503 ? 'MODEL_TIMEOUT' : status === 429 ? 'BUDGET_EXHAUSTED' : 'CITATION_CONFLICT') }) }), workspace = await ready(port)
    await workspace.ask(); await workspace.ask()
    expect(workspace.state.result).toBeNull(); expect(workspace.state.error).toBe(status); expect(workspace.canAsk()).toBe(false); expect(port.answer).toHaveBeenCalledTimes(1)
  })
  it('accepts a bounded provider abstention and an unresolved public-scope result without inventing a reason', async () => {
    for (const data of [unknown(), unknown(target(), undefined, true)]) {
      const workspace = await ready(api({ answer: vi.fn(async () => clone(data)) })); await workspace.ask()
      expect(workspace.state.status).toBe('unknown'); expect(workspace.state.error).toBeNull(); expect(workspace.state.result?.citations).toEqual([])
    }
  })
})
