import { computed, reactive } from 'vue'
import type { Eligibility, Evidence, Meta, Offering, PlanDraft, Profile, ProfileInput, RuntimeConfig } from '../../../packages/contracts/index'
import { createApi, type DemoUser, type M0Api } from './api'

type BusyOperation = 'load' | 'save' | 'check' | 'draft' | 'evidence'
export interface WorkspaceState {
  user: DemoUser; config: RuntimeConfig | null; profiles: Profile[]; offerings: Offering[];
  selectedProfileId: string; selectedOfferingIds: string[]; profileDirty: boolean;
  results: Eligibility[]; plan: PlanDraft | null; evidence: Evidence | null;
  error: string; meta: Meta | null; busy: Record<BusyOperation, boolean>;
}
export function useWorkspace(api: M0Api = createApi()) {
  const state = reactive<WorkspaceState>({
    user: 'alice', config: null, profiles: [], offerings: [], selectedProfileId: '', selectedOfferingIds: [], profileDirty: false,
    results: [], plan: null, evidence: null, error: '', meta: null,
    busy: { load: false, save: false, check: false, draft: false, evidence: false },
  })
  let session = 0, context = 0, evidenceRequest = 0
  const profile = computed(() => state.profiles.find((item) => item.id === state.selectedProfileId) ?? null)
  const canCheck = computed(() => !!profile.value && !state.profileDirty && state.selectedOfferingIds.length > 0 && !state.busy.load && !state.busy.save && !state.busy.check && !state.busy.draft)
  const canDraft = computed(() => canCheck.value && state.results.length > 0 && !state.busy.draft)
  function invalidate() {
    context++; evidenceRequest++
    state.results = []; state.plan = null; state.evidence = null; state.error = ''
    state.busy.check = false; state.busy.draft = false; state.busy.evidence = false
  }
  function selectProfile(id: string) { invalidate(); state.selectedProfileId = id; state.profileDirty = !id }
  function markProfileEdited() { invalidate(); state.profileDirty = true }
  function selectOfferings(ids: string[]) { invalidate(); state.selectedOfferingIds = ids }
  function report(error: unknown) { state.error = error instanceof Error ? error.message : '请求失败，请检查后端日志。' }
  async function load() {
    const currentSession = ++session, user = state.user
    state.busy.load = true; state.error = ''
    try {
      const config = await api.config(user)
      if (currentSession !== session) return
      const [profiles, offerings] = await Promise.all([
        api.profiles(user), api.offerings(user, { entry_year: config.data.entry_year, province: config.data.supported_province }),
      ])
      if (currentSession !== session) return
      state.config = config.data; state.profiles = profiles.data; state.offerings = offerings.data; state.meta = profiles.meta
      state.selectedProfileId = profiles.data[0]?.id ?? ''; state.profileDirty = !state.selectedProfileId
    } catch (error) { if (currentSession === session) report(error) }
    finally { if (currentSession === session) state.busy.load = false }
  }
  async function switchUser(user: DemoUser) {
    session++; invalidate(); state.user = user
    state.config = null; state.profiles = []; state.offerings = []; state.selectedProfileId = ''; state.selectedOfferingIds = []; state.meta = null
    state.profileDirty = false; state.busy.save = false
    await load()
  }
  async function saveProfile(input: ProfileInput) {
    if (state.busy.save || state.busy.load) return
    const currentSession = session, user = state.user
    state.busy.save = true; state.error = ''
    try {
      const response = await api.createProfile(user, input)
      if (currentSession !== session) return
      invalidate(); state.profiles = [...state.profiles, response.data]; state.selectedProfileId = response.data.id; state.profileDirty = false; state.meta = response.meta
    } catch (error) { if (currentSession === session) report(error) }
    finally { if (currentSession === session) state.busy.save = false }
  }
  async function check() {
    if (!canCheck.value) return
    const currentSession = session, currentContext = context, user = state.user
    const input = { profile_version_id: state.selectedProfileId, offering_ids: [...state.selectedOfferingIds] }
    state.busy.check = true; state.error = ''; state.plan = null; state.results = []
    try {
      const response = await api.check(user, input)
      if (currentSession !== session || currentContext !== context) return
      state.results = response.data; state.meta = response.meta
    } catch (error) { if (currentSession === session && currentContext === context) report(error) }
    finally { if (currentSession === session && currentContext === context) state.busy.check = false }
  }
  async function draft() {
    if (!canDraft.value) return
    const currentSession = session, currentContext = context, user = state.user
    state.busy.draft = true; state.error = ''; state.plan = null
    try {
      const response = await api.draft(user, { profile_version_id: state.selectedProfileId, offering_ids: [...state.selectedOfferingIds] })
      if (currentSession !== session || currentContext !== context) return
      state.plan = response.data; state.results = response.data.eligibility_results; state.meta = response.meta
    } catch (error) { if (currentSession === session && currentContext === context) report(error) }
    finally { if (currentSession === session && currentContext === context) state.busy.draft = false }
  }
  async function showEvidence(id: string) {
    const currentSession = session, currentContext = context, currentRequest = ++evidenceRequest, user = state.user
    state.busy.evidence = true; state.evidence = null; state.error = ''
    try {
      const response = await api.evidence(user, id)
      if (currentSession !== session || currentContext !== context || currentRequest !== evidenceRequest) return
      state.evidence = response.data
    } catch (error) { if (currentSession === session && currentContext === context && currentRequest === evidenceRequest) report(error) }
    finally { if (currentSession === session && currentContext === context && currentRequest === evidenceRequest) state.busy.evidence = false }
  }
  function closeEvidence() { evidenceRequest++; state.evidence = null; state.busy.evidence = false }
  return { state, profile, canCheck, canDraft, load, switchUser, saveProfile, check, draft, showEvidence, closeEvidence, selectProfile, selectOfferings, markProfileEdited }
}
