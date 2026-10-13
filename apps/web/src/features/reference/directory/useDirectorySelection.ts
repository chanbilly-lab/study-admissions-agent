import { computed, onBeforeUnmount, reactive } from 'vue'
import type { DirectoryInstitution, DirectoryProgram, DirectorySelectionEvent, InstitutionsDirectoryData, ProgramsDirectoryData } from '../../../../../../packages/contracts/referenceDirectory'
import { createDirectoryApi, DirectoryError, validateDirectoryData, validInstitution, validProgram } from './client'
import type { DirectoryApi, DirectoryRequest } from './client'

type Status = 'idle' | 'loading' | 'ready' | 'empty' | 'unavailable' | 'error'
export type DirectoryPurpose = 'curricula' | 'outcomes'
interface SelectionState {
  country: string
  institutionQuery: string
  programQuery: string
  institutions: InstitutionsDirectoryData | null
  programs: ProgramsDirectoryData | null
  institution: DirectoryInstitution | null
  program: DirectoryProgram | null
  institutionStatus: Status
  programStatus: Status
  institutionMessage: string
  programMessage: string
  requiresProgram: boolean
  disabled: boolean
}
export function useDirectorySelection(changed: (selection: DirectorySelectionEvent) => void, api: DirectoryApi = createDirectoryApi()) {
  const state = reactive<SelectionState>({ country: '', institutionQuery: '', programQuery: '', institutions: null, programs: null,
    institution: null, program: null, institutionStatus: 'idle', programStatus: 'idle', institutionMessage: '', programMessage: '',
    requiresProgram: true, disabled: false })
  let disposed = false, institutionGeneration = 0, programGeneration = 0
  let institutionAbort: AbortController | null = null, programAbort: AbortController | null = null
  let purpose: DirectoryPurpose | null = null, contextKey: string | null = null
  const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T
  const institutionBusy = computed(() => state.institutionStatus === 'loading')
  const programBusy = computed(() => state.programStatus === 'loading')
  function notify() {
    if (purpose === null || contextKey === null) return
    changed({ purpose, context_key: contextKey, institution: state.institution === null ? null : copy(state.institution), program: state.program === null ? null : copy(state.program) })
  }
  function invalidateProgram(clearQuery = false) {
    programGeneration++; programAbort?.abort(); programAbort = null
    state.programs = null; state.program = null; state.programStatus = 'idle'; state.programMessage = ''
    if (clearQuery) state.programQuery = ''
  }
  function invalidateInstitutions() {
    institutionGeneration++; institutionAbort?.abort(); institutionAbort = null
    state.institutions = null; state.institution = null; state.institutionStatus = 'idle'; state.institutionMessage = ''
    invalidateProgram(true); notify()
  }
  function setContext(nextPurpose: DirectoryPurpose, nextContext: string, requiresProgram: boolean, disabled: boolean) {
    if (purpose === nextPurpose && contextKey === nextContext && state.requiresProgram === requiresProgram && state.disabled === disabled) return
    purpose = nextPurpose; contextKey = nextContext; state.requiresProgram = requiresProgram; state.disabled = disabled
    invalidateInstitutions()
  }
  function setCountry(value: string) {
    if (value === state.country) return
    state.country = value; invalidateInstitutions()
  }
  function setInstitutionQuery(value: string) {
    if (value === state.institutionQuery) return
    state.institutionQuery = value; invalidateInstitutions()
  }
  function setProgramQuery(value: string) {
    if (value === state.programQuery) return
    state.programQuery = value; invalidateProgram(); notify()
  }
  function selectInstitution(id: string) {
    const item = !state.disabled && state.institutions?.directory_available ? state.institutions.items.find(option => option.id === id) : undefined
    invalidateProgram(true)
    state.institution = item && validInstitution(item) ? copy(item) : null
    notify()
  }
  function selectProgram(id: string) {
    const institution = state.institution
    const item = !state.disabled && state.requiresProgram && institution !== null && state.programs?.directory_available
      ? state.programs.items.find(option => option.id === id) : undefined
    state.program = item && institution !== null && validProgram(item) && item.institution_id === institution.id && item.country === institution.country ? copy(item) : null
    notify()
  }
  function message(data: InstitutionsDirectoryData | ProgramsDirectoryData, subject: string): string {
    return !data.directory_available ? `可信${subject}目录尚未启用，当前没有可选择的记录。未使用研究候选、演示或未发布资料补充。`
      : data.items.length === 0 ? `本次目录页未返回已发布的${subject}匹配，请重新搜索或调整条件；这不代表对象不存在。`
      : '仅展示本页已发布身份记录。请选择一项；同名对象仍分别保留。'
  }
  async function searchInstitutions(nextPage = false) {
    if (disposed || purpose === null || contextKey === null || state.disabled || institutionBusy.value) return
    const previous = state.institutions, token = nextPage ? previous?.page.next_cursor ?? null : null
    if (nextPage && (token === null || previous?.catalog_watermark === null)) return
    const expectedWatermark = nextPage ? previous?.catalog_watermark : undefined
    const request: DirectoryRequest = { resource: 'institutions', filters: { q: state.institutionQuery.trim(), country: state.country || null, institution_id: null }, cursor: token }
    invalidateInstitutions()
    const generation = institutionGeneration, abort = new AbortController()
    institutionAbort = abort; state.institutionStatus = 'loading'
    try {
      const raw = await api.institutions({ q: request.filters.q, country: request.filters.country, cursor: token }, abort.signal)
      if (disposed || abort.signal.aborted || generation !== institutionGeneration) return
      const data = validateDirectoryData(copy(raw), request)
      if (data.resource !== 'institutions' || nextPage && data.catalog_watermark !== expectedWatermark) throw new DirectoryError(409)
      state.institutions = copy(data)
      state.institutionStatus = !data.directory_available ? 'unavailable' : data.items.length === 0 ? 'empty' : 'ready'
      state.institutionMessage = message(data, '学校')
    } catch (error) {
      if (!disposed && generation === institutionGeneration && !abort.signal.aborted) {
        state.institutions = null; state.institutionStatus = 'error'
        state.institutionMessage = (error instanceof DirectoryError ? error : new DirectoryError(0)).message
      }
    } finally { if (generation === institutionGeneration) institutionAbort = null }
  }
  async function searchPrograms(nextPage = false) {
    if (disposed || purpose === null || contextKey === null || state.disabled || !state.requiresProgram || programBusy.value || !state.institution || !state.institutions?.directory_available) return
    const institution = copy(state.institution), institutionWatermark = state.institutions.catalog_watermark
    const previous = state.programs, token = nextPage ? previous?.page.next_cursor ?? null : null
    if (nextPage && (token === null || previous?.catalog_watermark === null)) return
    const expectedWatermark = nextPage ? previous?.catalog_watermark : institutionWatermark
    const request: DirectoryRequest = { resource: 'programs', filters: { q: state.programQuery.trim(), country: state.country || null, institution_id: institution.id }, cursor: token }
    invalidateProgram(); notify()
    const generation = programGeneration, abort = new AbortController()
    programAbort = abort; state.programStatus = 'loading'
    try {
      const raw = await api.programs({ q: request.filters.q, country: request.filters.country, institution_id: institution.id, cursor: token }, abort.signal)
      if (disposed || abort.signal.aborted || generation !== programGeneration || state.institution?.id !== institution.id) return
      const data = validateDirectoryData(copy(raw), request)
      if (!data.directory_available) {
        invalidateInstitutions(); state.institutionStatus = 'unavailable'; state.institutionMessage = message(data, '学校与专业')
        return
      }
      if (data.resource !== 'programs' || data.catalog_watermark !== expectedWatermark || data.catalog_watermark !== institutionWatermark
        || data.items.some(item => item.country !== institution.country)) throw new DirectoryError(409)
      state.programs = copy(data)
      state.programStatus = !data.directory_available ? 'unavailable' : data.items.length === 0 ? 'empty' : 'ready'
      state.programMessage = message(data, '专业')
    } catch (error) {
      if (!disposed && generation === programGeneration && !abort.signal.aborted) {
        if (error instanceof DirectoryError && error.status === 409) {
          invalidateInstitutions(); state.institutionStatus = 'error'; state.institutionMessage = error.message
        } else {
          state.programs = null; state.programStatus = 'error'
          state.programMessage = (error instanceof DirectoryError ? error : new DirectoryError(0)).message
        }
      }
    } finally { if (generation === programGeneration) programAbort = null }
  }
  function dispose() {
    if (disposed) return
    disposed = true; invalidateInstitutions()
  }
  onBeforeUnmount(dispose)
  return { state, institutionBusy, programBusy, setContext, setCountry, setInstitutionQuery, setProgramQuery,
    selectInstitution, selectProgram, searchInstitutions: () => searchInstitutions(), nextInstitutions: () => searchInstitutions(true),
    searchPrograms: () => searchPrograms(), nextPrograms: () => searchPrograms(true), dispose }
}
