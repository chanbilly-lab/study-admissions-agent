import { reactive } from 'vue'
import type { SessionData } from '../auth/client'
import type { ProfileVersionData } from '../profiles/client'
import type { ScopeKey, AssessmentRequest } from '../../../../../packages/contracts/v2/assessments/generated'
import { createCatalogApi, CatalogError, offeringKey, validQuery, matchesQuery } from './client'
import type { CatalogApi, ListV2PublicOfferingsQuery, PublicConfigData, PublicEvidenceData, PublicOfferingData, PublicOfferingsData } from './client'
import { canonicalHash, exact, uuid, scopeFingerprint, validConfig, validEvidence, validPage, validOffering, validScopeKey } from './validation'
import { createEligibilityApi, EligibilityError } from '../eligibility/client'
import type { EligibilityApi, AssessmentContextData, AssessmentData } from '../eligibility/client'
import { bindProfile, extraScopeFields, validAssessment, validContext, validProfile } from '../eligibility/validation'
export type CatalogQuery = Omit<ListV2PublicOfferingsQuery, 'entry_year'> & { entry_year: number | null }
export type AdditionalScopeField = typeof extraScopeFields[number]
export function useAdmissionsWorkspace(apis: { catalogApi?: CatalogApi; eligibilityApi?: EligibilityApi } = {}, onSessionExpired = () => {}) {
  const catalog = apis.catalogApi ?? createCatalogApi(), eligibility = apis.eligibilityApi ?? createEligibilityApi()
  const state = reactive({ query: { entry_year: null, limit: 20 } as CatalogQuery, config: null as PublicConfigData | null, page: null as PublicOfferingsData | null,
    publicStatus: 'idle' as 'idle' | 'loading' | 'ready' | 'error', publicMessage: '', publicError: null as number | null,
    selectedKey: null as string | null, compareKeys: [] as string[], evidence: null as PublicEvidenceData | null, evidenceBusy: false, evidenceMessage: '',
    context: null as AssessmentContextData | null, profile: null as ProfileVersionData | null, stage: 'application' as 'application' | 'enrollment', confirmed: false,
    scope: Object.fromEntries(extraScopeFields.map(k => [k, null])) as Record<AdditionalScopeField, ScopeKey | null>,
    result: null as AssessmentData | null, history: null as AssessmentData | null, assessmentId: '', replayConfirmed: false,
    privateBusy: false, privateMessage: '', privateError: null as number | null, coreAllowed: false })
  let actor: SessionData | null = null, profileEpoch = -1, disposed = false, publicGeneration = 0, privateGeneration = 0, evidenceGeneration = 0
  let publicAbort: AbortController | null = null, privateAbort: AbortController | null = null, evidenceAbort: AbortController | null = null
  const items = new Map<string, PublicOfferingData>()
  const copy = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T
  function closeEvidence() { evidenceGeneration++; evidenceAbort?.abort(); evidenceAbort = null; state.evidence = null; state.evidenceBusy = false; state.evidenceMessage = '' }
  function clearPrivate(clearProfile = false, preserveResult = false) {
    privateGeneration++; privateAbort?.abort(); privateAbort = null; state.privateBusy = false; state.privateMessage = ''; state.privateError = null
    if (!preserveResult) state.result = null
    state.history = null; state.confirmed = false; state.replayConfirmed = false; state.assessmentId = ''
    if (clearProfile) { state.profile = null; state.context = null }
  }
  function clearSelection() { state.selectedKey = null; state.compareKeys = []; items.clear(); closeEvidence(); clearPrivate() }
  function selectedOffering(): PublicOfferingData | null { return state.selectedKey === null ? null : items.get(state.selectedKey) ?? null }
  function compareItems(): PublicOfferingData[] { return state.compareKeys.map(k => items.get(k)).filter((v): v is PublicOfferingData => Boolean(v)) }
  const access = () => !disposed && actor !== null && state.coreAllowed
  function setAccess(next: SessionData | null, allowed: boolean) {
    if (next !== actor || allowed !== state.coreAllowed) { clearPrivate(true); closeEvidence(); actor = next; state.coreAllowed = next !== null && allowed === true; profileEpoch = -1 }
  }
  async function setProfile(version: ProfileVersionData | null, epoch = 0) {
    if (epoch === profileEpoch && version?.version_id === state.profile?.version_id && version?.profile_sha256 === state.profile?.profile_sha256) return
    clearPrivate(); closeEvidence(); state.profile = null; profileEpoch = epoch
    if (version === null || !access()) return
    const generation = privateGeneration, frozen = copy(version)
    try {
      if (!await validProfile(frozen) || frozen.is_synthetic !== actor!.is_synthetic) throw new EligibilityError(200)
      if (generation === privateGeneration && access()) state.profile = frozen
    } catch { if (generation === privateGeneration) { state.privateError = 200; state.privateMessage = '所选画像版本未通过校验，不能用于评估。' } }
  }
  function setFilters(patch: Partial<CatalogQuery>) {
    publicGeneration++; publicAbort?.abort(); state.query = { ...state.query, ...patch }; delete state.query.cursor
    state.page = null; state.publicStatus = 'idle'; state.publicMessage = ''; state.publicError = null; clearSelection()
  }
  function publicFailure(error: unknown) { const e = error instanceof CatalogError ? error : new CatalogError(0); state.publicStatus = 'error'; state.publicError = e.status; state.publicMessage = e.message; state.page = null; clearSelection() }
  async function loadConfig() {
    const generation = ++publicGeneration; publicAbort?.abort(); const pending = new AbortController(); publicAbort = pending
    try { const config = await catalog.config(pending.signal); if (generation !== publicGeneration || disposed) return
      if (!validConfig(config)) throw new CatalogError(200)
      state.config = copy(config)
    } catch (error) { if (generation === publicGeneration && !pending.signal.aborted && !disposed) publicFailure(error) }
  }
  async function loadPage(cursor?: string) {
    const query = copy({ ...state.query, ...(cursor === undefined ? {} : { cursor }) })
    if (!validQuery(query)) { publicFailure(new CatalogError(422)); return }
    const generation = ++publicGeneration; publicAbort?.abort(); const pending = new AbortController(); publicAbort = pending
    state.publicStatus = 'loading'; state.publicMessage = ''; state.publicError = null; state.confirmed = false; closeEvidence(); clearPrivate()
    try {
      const config = await catalog.config(pending.signal)
      if (generation !== publicGeneration || disposed) return
      if (!validConfig(config)) throw new CatalogError(200)
      state.config = copy(config)
      if (!config.business_available) throw new CatalogError(503)
      const page = copy(await catalog.offerings(query, pending.signal))
      if (generation !== publicGeneration || disposed) return
      if (!validPage(page) || page.page.limit !== (query.limit ?? 20) || page.items.some(item => !matchesQuery(item, query) || item.is_synthetic !== config.allow_test_fixture_read)) throw new CatalogError(200)
      for (const item of page.items) {
        const key = offeringKey(item), previous = items.get(key)
        if (previous && await canonicalHash(previous) !== await canonicalHash(item)) throw new CatalogError(200)
        if (generation !== publicGeneration || disposed) return
        items.set(key, copy(item))
      }
      state.page = copy(page); state.query = query; state.publicStatus = 'ready'
      state.publicMessage = page.coverage.status === 'no_published_records' ? '当前范围没有可读取的已发布资料；不代表不存在招生机会。' : '仅展示当前有证据的已发布资料，覆盖分母未知。'
    } catch (error) { if (generation === publicGeneration && !disposed && !pending.signal.aborted) publicFailure(error) }
  }
  async function search() { clearSelection(); delete state.query.cursor; return loadPage() }
  async function nextPage() { if (state.page?.page.has_more && state.page.page.next_cursor) return loadPage(state.page.page.next_cursor) }
  function selectOffering(value: string | PublicOfferingData) {
    const key = typeof value === 'string' ? value : offeringKey(value), item = items.get(key)
    if (!item || !validOffering(item)) return
    clearPrivate(); closeEvidence(); state.selectedKey = key
    state.scope = Object.fromEntries(extraScopeFields.map(k => [k, copy(item.scope[k])])) as Record<AdditionalScopeField, ScopeKey>
  }
  function toggleCompare(value: string | PublicOfferingData) {
    const key = typeof value === 'string' ? value : offeringKey(value)
    if (!items.has(key)) return
    if (state.compareKeys.includes(key)) state.compareKeys = state.compareKeys.filter(k => k !== key)
    else if (state.compareKeys.length < 4) state.compareKeys.push(key)
    else state.publicMessage = '最多比较 4 个确切项目版本；不会生成排名或录取概率。'
  }
  function setStage(stage: 'application' | 'enrollment') { if (stage !== state.stage && ['application', 'enrollment'].includes(stage)) { clearPrivate(); closeEvidence(); state.stage = stage } }
  function setScope(field: AdditionalScopeField, value: ScopeKey | null) { if (extraScopeFields.includes(field) && (value === null || validScopeKey(value))) { clearPrivate(); closeEvidence(); state.scope[field] = copy(value) } }
  function setConfirmed(confirmed: boolean) { state.confirmed = confirmed === true && access() && state.profile !== null && selectedOffering() !== null }
  function setReplayConfirmed(confirmed: boolean) { state.replayConfirmed = confirmed === true && access() }
  function setAssessmentId(id: string) { if (typeof id !== 'string' || id.length > 64 || id === state.assessmentId) return; clearPrivate(false, true); state.assessmentId = id }
  function privateFailure(error: unknown) {
    const e = error instanceof EligibilityError ? error : new EligibilityError(0); clearPrivate(); state.privateError = e.status; state.privateMessage = e.message
    if ([401, 403, 503, 200, 0].includes(e.status)) { state.context = null; state.profile = null }
    if (e.status === 401) onSessionExpired()
  }
  async function refreshContext() {
    if (!access()) return
    clearPrivate(); const generation = privateGeneration, pending = new AbortController(); privateAbort = pending; state.privateBusy = true
    try { const context = await eligibility.context(pending.signal); if (generation !== privateGeneration || !access()) return
      if (!validContext(context) || context.is_synthetic !== actor!.is_synthetic) throw new EligibilityError(200)
      state.context = copy(context)
    } catch (error) { if (generation === privateGeneration && !pending.signal.aborted) privateFailure(error) }
    finally { if (generation === privateGeneration) state.privateBusy = false }
  }
  function canEvaluate(): boolean { return access() && state.profile !== null && state.context?.can_evaluate === true && selectedOffering() !== null && ['CN', 'GB'].includes(selectedOffering()!.scope.country) && !state.privateBusy }
  async function evaluateSelected() {
    if (!canEvaluate() || state.confirmed !== true) { state.privateMessage = '请读取当前确认画像、选择项目并明确确认评估范围。'; return }
    const profile = copy(state.profile!), item = copy(selectedOffering()!), scope = copy(state.scope), stage = state.stage
    clearPrivate(); const generation = privateGeneration, pending = new AbortController(); privateAbort = pending; state.privateBusy = true
    try {
      const target = { country: item.scope.country as 'CN' | 'GB', dataset_id: item.scope.dataset_id, institution_id: item.institution_id, program_id: item.program_id, offering_id: item.id, offering_version: item.version, scope_sha256: await scopeFingerprint(item.scope) }
      if (generation !== privateGeneration || !access()) return
      const request: AssessmentRequest = { profile_id: profile.profile_id, profile_version_id: profile.version_id, release_id: item.release_id, target, stage, ...scope, confirmed: true }
      const result = copy(await eligibility.evaluate(request, pending.signal))
      if (generation !== privateGeneration || !access()) return
      if (!await validAssessment(result) || !bindProfile(result, profile) || result.release_id !== item.release_id || result.requirements_version !== item.requirements_version || result.catalogue_is_synthetic !== item.is_synthetic || result.stage !== stage || result.replayed || await canonicalHash(result.target) !== await canonicalHash(target)) throw new EligibilityError(200)
      if (generation !== privateGeneration || !access()) return
      state.result = copy(result); state.assessmentId = result.assessment_id; state.privateMessage = '已保存本次明确确认的评估快照。结论与当前有效性分别显示。'
    } catch (error) { if (generation === privateGeneration && !pending.signal.aborted) privateFailure(error) }
    finally { if (generation === privateGeneration) state.privateBusy = false }
  }
  async function historical(id: string, replay: boolean) {
    if (!access() || !uuid(id) || !(replay ? state.context?.can_replay : state.context?.can_read) || replay && !state.replayConfirmed) { state.privateMessage = '请明确填写评估 ID，并确认重放。'; return }
    clearPrivate(false, true); const generation = privateGeneration, pending = new AbortController(); privateAbort = pending; state.privateBusy = true
    try {
      const data = copy(replay ? await eligibility.replay(id, { confirmed: true }, pending.signal) : await eligibility.get(id, pending.signal))
      if (generation !== privateGeneration || !access()) return
      if (!await validAssessment(data) || data.assessment_id !== id || data.replayed !== replay || data.profile_is_synthetic !== actor!.is_synthetic) throw new EligibilityError(200)
      if (generation !== privateGeneration || !access()) return
      state.history = copy(data); state.assessmentId = id; state.privateMessage = '历史快照不会覆盖本次项目评估；当前有效性单独显示。'
    } catch (error) { if (generation === privateGeneration && !pending.signal.aborted) privateFailure(error) }
    finally { if (generation === privateGeneration) state.privateBusy = false }
  }
  async function openEvidence(id: string) {
    const selected = selectedOffering()
    if (!selected || !uuid(id) || !selected.facts.some(fact => fact.evidence_id === id)) { closeEvidence(); state.evidenceMessage = '此引用不在所选发布的公开证据范围内。'; return }
    closeEvidence(); const item = copy(selected), generation = evidenceGeneration, pending = new AbortController(); evidenceAbort = pending; state.evidenceBusy = true
    try {
      const evidence = copy(await catalog.evidence(id, item.release_id, pending.signal))
      if (generation !== evidenceGeneration || disposed) return
      if (!await validEvidence(evidence) || evidence.evidence_id !== id || evidence.release_id !== item.release_id || evidence.requirements_version !== item.requirements_version || evidence.offering_id !== item.id || evidence.offering_version !== item.version || evidence.entry_year !== item.entry_year || evidence.is_synthetic !== item.is_synthetic || await canonicalHash(evidence.scope) !== await canonicalHash(item.scope)) throw new CatalogError(200)
      if (generation !== evidenceGeneration || disposed) return
      state.evidence = copy(evidence)
    } catch (error) { if (generation === evidenceGeneration && !pending.signal.aborted) state.evidenceMessage = (error instanceof CatalogError ? error : new CatalogError(0)).message }
    finally { if (generation === evidenceGeneration) state.evidenceBusy = false }
  }
  function dispose() { disposed = true; publicGeneration++; publicAbort?.abort(); clearSelection(); clearPrivate(true); actor = null }
  return { state, selectedOffering, compareItems, canEvaluate, loadConfig, setAccess, setProfile, setFilters, search, nextPage, selectOffering, toggleCompare, refreshContext, evaluateSelected, openEvidence, closeEvidence, readAssessment: (id = state.assessmentId) => historical(id, false), replayAssessment: (id = state.assessmentId) => historical(id, true), setStage, setScope, setConfirmed, setReplayConfirmed, setAssessmentId, dispose }
}
