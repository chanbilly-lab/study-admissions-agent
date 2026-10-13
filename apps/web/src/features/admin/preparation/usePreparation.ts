import { reactive } from 'vue'
import { contentBytes, readOriginal, uuid } from '../client'
import { ReviewWorkspaceError, strictInteger, type ReviewWorkspaceApi, type SessionData, type ImportRowsData,
  type DocumentData, type VersionData, type SnippetData, type TypedCandidate, type Classification } from '../reviews/client'
const classificationDraft = () => ({ claim: '' as Classification['claim_kind'] | '', unit: '' as Classification['unit_code'] | '',
  period: '' as Classification['period'] | '', basis: '' as Classification['statistics_basis'] | '', population: '', denominator: '',
  cohort: '' as string | number, survey: '', dateId: '' })
export function usePreparation(api: ReviewWorkspaceApi, expired: () => void = () => {}) {
  const state = reactive({ importId: '', page: null as ImportRowsData | null, rowId: '', reference: '', language: '' as DocumentData['language'] | '',
    original: '', originalMatched: false, originalMessage: '', byteStart: '' as string | number, byteEnd: '' as string | number,
    document: null as DocumentData | null, version: null as VersionData | null, snippet: null as SnippetData | null, fact: null as TypedCandidate | null,
    classification: classificationDraft(), confirmed: { document: false, version: false, snippet: false, fact: false }, busy: '', message: '', error: false })
  let actor: SessionData | null = null, generation = 0, pending: AbortController | undefined
  function invalidate() { generation++; pending?.abort(); state.busy = ''; state.message = ''; state.error = false }
  function clearOutputs() { state.document = null; state.version = null; state.snippet = null; state.fact = null; state.confirmed = { document: false, version: false, snippet: false, fact: false } }
  function reset() { invalidate(); state.page = null; state.rowId = ''; state.importId = ''; state.reference = ''; state.language = '';
    state.original = ''; state.originalMatched = false; state.originalMessage = ''; state.byteStart = ''; state.byteEnd = ''; state.classification = classificationDraft(); clearOutputs() }
  function setActor(value: SessionData | null) { reset(); actor = value }
  function failure(error: unknown) { clearOutputs(); state.error = true; state.message = error instanceof ReviewWorkspaceError ? error.message : '准备步骤未确认成功。'
    if (error instanceof ReviewWorkspaceError && [401, 403, 503].includes(error.status)) { const message = state.message; reset(); state.message = message; state.error = true; if (error.status === 401) expired() } }
  async function operation<T>(name: string, run: (signal: AbortSignal) => Promise<T>, apply: (result: T) => void) {
    if (!actor || state.busy) return
    const current = ++generation; pending?.abort(); pending = new AbortController(); state.busy = name; state.message = ''; state.error = false
    try { const result = await run(pending.signal); if (current === generation) apply(result) }
    catch (error) { if (current === generation) failure(error) }
    finally { if (current === generation) state.busy = '' }
  }
  function scopeChanged() { invalidate(); state.page = null; state.rowId = ''; state.original = ''; state.originalMatched = false; clearOutputs() }
  function selectRow(id: string) { invalidate(); state.rowId = id; clearOutputs(); state.reference = ''; state.language = ''; state.byteStart = ''; state.byteEnd = ''; state.classification = classificationDraft() }
  function definitionChanged() { invalidate(); clearOutputs() }
  function originalChanged() { invalidate(); state.originalMatched = false; state.originalMessage = ''; clearOutputs() }
  function spanChanged() { invalidate(); state.snippet = null; state.fact = null; state.confirmed.snippet = false; state.confirmed.fact = false }
  function classificationChanged() { invalidate(); state.fact = null; state.confirmed.fact = false }
  function selected() { return state.page?.rows.find(item => item.row_id === state.rowId) ?? null }
  async function loadRows(next = false) {
    if (!uuid(state.importId)) return
    const id = state.importId, token = next ? state.page?.next_cursor ?? undefined : undefined
    if (next && !token) return
    clearOutputs(); state.rowId = ''; state.originalMatched = false; state.original = ''
    await operation('rows', signal => api.rows(id, token, signal), result => { if (result.import_id !== id) throw new ReviewWorkspaceError(200); state.page = result; state.message = '已读取当前有权批次的有效候选行；不是已审核事实。' })
  }
  async function verifyOriginal() {
    state.originalMatched = false; clearOutputs()
    if (!state.page) return
    const expected = state.page.file_sha256, text = state.original
    await operation('original', async () => {
      const bytes = contentBytes(text)
      return [...new Uint8Array(await crypto.subtle.digest('SHA-256', Uint8Array.from(bytes)))].map(value => value.toString(16).padStart(2, '0')).join('')
    }, digest => { state.originalMatched = digest === expected; state.originalMessage = digest === expected ? '本机原文 SHA-256 与服务器原批一致；仍须明确选择字节范围。' : '本机原文哈希不一致，准备操作保持关闭。' })
  }
  async function chooseOriginal(file: File) {
    originalChanged(); await operation('file', async () => readOriginal(file), text => { state.original = text })
    if (state.original) await verifyOriginal()
  }
  function ready() { return !!actor && !state.busy && !!state.page && !!selected() && state.originalMatched }
  function canDocument() { return ready() && !state.document && state.confirmed.document && !!state.language && /^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$/.test(state.reference) }
  async function createDocument() {
    if (!canDocument()) return
    const page = state.page!, input = { dataset_id: page.dataset_id, source_id: page.source_id, source_version: page.source_version,
      document_reference: state.reference, language: state.language as DocumentData['language'], confirmed: true as const }
    state.confirmed.document = false
    await operation('document', signal => api.document(input, signal), result => {
      if (result.dataset_id !== page.dataset_id || result.source_id !== page.source_id || result.source_version !== page.source_version || result.is_synthetic !== actor?.is_synthetic) throw new ReviewWorkspaceError(200)
      state.document = result; state.message = '文档登记这一步已提交；版本、片段和事实仍未完成。'
    })
  }
  function canVersion() { return ready() && !!state.document && !state.version && state.confirmed.version }
  async function createVersion() {
    if (!canVersion()) return
    const page = state.page!, document = state.document!
    state.confirmed.version = false
    await operation('version', signal => api.version({ document_id: document.id, expected_current_version: document.current_version, file_id: page.file_id,
      file_sha256: page.file_sha256, confirmed: true }, signal), result => {
      if (result.document_id !== document.id || result.document_sha256 !== page.file_sha256 || result.is_synthetic !== actor?.is_synthetic) throw new ReviewWorkspaceError(200)
      state.version = result; state.message = '原文件版本这一步已提交；尚无审核决定或发布。'
    })
  }
  function span() {
    const start = strictInteger(state.byteStart, 0, 1048575), end = strictInteger(state.byteEnd, 1, 1048576)
    if (start === null || end === null || end <= start || end - start > 4096) return null
    try { const bytes = contentBytes(state.original); if (end > bytes.length) return null; new TextDecoder('utf-8', { fatal: true }).decode(bytes.slice(start, end)) }
    catch { return null }
    return { start, end }
  }
  function canSnippet() { return ready() && !!state.version && state.confirmed.snippet && !!span() }
  async function createSnippet() {
    if (!canSnippet()) return
    const row = selected()!.row, version = state.version!, interval = span()!; state.confirmed.snippet = false; state.fact = null
    await operation('snippet', signal => api.snippet({ document_id: version.document_id, document_version: version.version,
      offering_id: row.offering_id, offering_version: row.offering_version, entry_year: row.entry_year, byte_start: interval.start, byte_end: interval.end, confirmed: true }, signal), result => {
      if (result.offering_id !== row.offering_id || result.offering_version !== row.offering_version || result.entry_year !== row.entry_year || result.document_sha256 !== state.page!.file_sha256) throw new ReviewWorkspaceError(200)
      state.snippet = result; state.message = '有界片段这一步已提交。定位与字面引用不代表人工审核。'
    })
  }
  function classification(): Classification | null {
    const draft = state.classification, cohort = draft.cohort === '' ? null : strictInteger(draft.cohort, 1, 9999)
    if (!draft.claim || !draft.unit || !draft.period || !draft.basis || (draft.cohort !== '' && cohort === null) || (draft.dateId !== '' && !uuid(draft.dateId))) return null
    return { claim_kind: draft.claim, unit_code: draft.unit, period: draft.period, statistics_basis: draft.basis,
      statistic_population: draft.population === '' ? null : draft.population, statistic_denominator: draft.denominator === '' ? null : draft.denominator,
      cohort_year: cohort, survey_period: draft.survey === '' ? null : draft.survey, date_event_id: draft.dateId === '' ? null : draft.dateId }
  }
  function canFact() { return ready() && !!state.snippet && state.confirmed.fact && !!classification() }
  async function createFact() {
    if (!canFact()) return
    const page = state.page!, row = selected()!, evidence = state.snippet!; state.confirmed.fact = false
    await operation('fact', signal => api.fact({ import_id: page.import_id, import_row_id: row.row_id, classification: classification()!, evidence_id: evidence.id, confirmed: true }, signal), result => {
      if (result.import_id !== page.import_id || result.import_row_id !== row.row_id || result.evidence_id !== evidence.id || result.hard_rule !== false || result.publication_eligible !== false) throw new ReviewWorkspaceError(200)
      state.fact = result; state.message = '类型化候选这一步已提交。仍不可作为硬规则或已发布资料；需另一个账号独立审核。'
    })
  }
  function dispose() { reset(); actor = null }
  return { state, setActor, dispose, selected, loadRows, scopeChanged, selectRow, definitionChanged, originalChanged, spanChanged, classificationChanged,
    verifyOriginal, chooseOriginal, canDocument, createDocument, canVersion, createVersion, canSnippet, createSnippet, canFact, createFact }
}
