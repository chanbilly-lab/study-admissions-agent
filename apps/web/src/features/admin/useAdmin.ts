import { reactive } from 'vue'
import type { SessionData } from '../auth/client'
import { AdminError, createAdminApi, contentBytes, readOriginal, sourceDefinitionKeys, uuid,
  type AdminApi, type AdminContextData, type AdminSourceData, type SourceDefinition, type FileData, type ImportResult } from './client'

export function emptySourceDraft() {
  return { datasetId: '', datasetRevision: '' as string | number, reference: '', publisher: '', url: '', dataType: '' as SourceDefinition['data_type'] | '',
    scope: '', authority: 'unclassified' as SourceDefinition['authority_claim'], manual: 'pending' as SourceDefinition['manual_import_permission'],
    publication: 'pending' as SourceDefinition['publication_permission'], automated: 'pending' as SourceDefinition['automated_fetch_permission'],
    basis: '', permissionReference: '', recheckDays: '' as string | number, manualEnabled: false, confirmed: false }
}
export type SourceDraft = ReturnType<typeof emptySourceDraft>
function positive(value: string | number, max = 2_147_483_647): number | null {
  const text = String(value)
  if (!/^[0-9]+$/.test(text)) return null
  const result = Number(text)
  return Number.isSafeInteger(result) && result >= 1 && result <= max ? result : null
}
function definition(draft: SourceDraft): SourceDefinition | null {
  const days = positive(draft.recheckDays, 730)
  const recorded = [draft.manual, draft.publication, draft.automated].some(permission => permission !== 'pending')
  if (!draft.publisher.trim() || !draft.url || !draft.scope.trim() || !draft.dataType || !days
    || (recorded && (!draft.basis.trim() || !/^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$/.test(draft.permissionReference)))
    || (!recorded && (draft.basis !== '' || draft.permissionReference !== ''))
    || (draft.manualEnabled && draft.manual !== 'granted')) return null
  try {
    if (/[\s\\\x00-\x1f\x7f-\x9f]/.test(draft.url)) return null
    const url = new URL(draft.url)
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.hash) return null
  } catch { return null }
  return { publisher: draft.publisher, entry_url: draft.url, purpose: 'admissions_reference', data_type: draft.dataType,
    scope_note: draft.scope, authority_claim: draft.authority, manual_import_permission: draft.manual,
    publication_permission: draft.publication, automated_fetch_permission: draft.automated,
    license_basis: recorded ? draft.basis : null, permission_record_reference: recorded ? draft.permissionReference : null,
    recheck_days: days, manual_import_enabled: draft.manualEnabled }
}

export function useAdmin(api: AdminApi = createAdminApi(), onSessionExpired: () => void = () => {}) {
  const state = reactive<{
    status: 'idle' | 'loading' | 'ready' | 'error'; context: AdminContextData | null; busy: string | null; message: string; notice: 'info' | 'error';
    draft: SourceDraft; source: AdminSourceData | null; sourceQueryId: string; sourceQueryVersion: string | number;
    mode: 'create' | 'revise'; filename: string; contentType: 'application/json' | 'text/csv'; content: string;
    fileConfirmed: boolean; file: FileData | null; importConfirmed: boolean; result: ImportResult | null; importQueryId: string;
  }>({ status: 'idle', context: null, busy: null, message: '', notice: 'info', draft: emptySourceDraft(), source: null,
    sourceQueryId: '', sourceQueryVersion: '', mode: 'create', filename: '', contentType: 'application/json', content: '',
    fileConfirmed: false, file: null, importConfirmed: false, result: null, importQueryId: '' })
  let actor: SessionData | null = null, generation = 0, pending: AbortController | undefined
  let requestKey: string | undefined, requestPayload: string | undefined, sourceCreateId: string | undefined
  function clearReceipt() {
    state.file = null; state.result = null; state.fileConfirmed = false; state.importConfirmed = false
    requestKey = undefined; requestPayload = undefined
  }
  function clearSource() { state.source = null; clearReceipt(); state.content = ''; state.filename = '' }
  function reset() {
    state.context = null; clearSource(); state.draft = emptySourceDraft(); state.sourceQueryId = ''; state.sourceQueryVersion = ''
    state.importQueryId = ''; state.mode = 'create'; state.contentType = 'application/json'; sourceCreateId = undefined; state.message = ''
  }
  function begin(action: string) {
    const current = ++generation
    pending?.abort(); pending = new AbortController(); state.busy = action; state.message = ''; state.notice = 'info'
    return { current, signal: pending.signal }
  }
  function failure(error: unknown) {
    state.message = error instanceof AdminError ? error.message : '结果无法确认，请重新读取后再操作。'
    state.result = null; state.draft.confirmed = false; state.fileConfirmed = false; state.importConfirmed = false
    if (error instanceof AdminError && [401, 403, 503].includes(error.status)) {
      reset(); state.message = error.message; state.status = 'error'
      if (error.status === 401) onSessionExpired()
    }
    state.notice = 'error'
  }
  async function refresh() {
    if (state.busy) return
    const { current, signal } = begin('context'); reset()
    if (!actor) { state.status = 'idle'; state.busy = null; return }
    state.status = 'loading'
    try {
      const context = await api.context(signal)
      if (current !== generation) return
      if (context.is_synthetic !== actor.is_synthetic) throw new AdminError(200, '管理模式与当前主体不一致，状态已清空。')
      state.context = context; state.status = 'ready'
    } catch (error) { if (current === generation) { state.status = 'error'; failure(error) } }
    finally { if (current === generation) state.busy = null }
  }
  function setActor(value: SessionData | null) {
    generation++; pending?.abort(); actor = value; state.busy = null; reset()
    return refresh()
  }
  function canManage() { return !!actor && state.status === 'ready' && !!state.context?.can_manage_sources && !state.busy }
  function canImport() { return !!actor && state.status === 'ready' && !!state.context?.can_import && !state.busy }
  function invalidatePending() {
    generation++; pending?.abort(); state.busy = null; state.message = ''; state.notice = 'info'
  }
  function sourceChanged() { invalidatePending(); clearReceipt(); state.draft.confirmed = false; sourceCreateId = undefined }
  function queryChanged() { invalidatePending(); clearSource(); state.draft.confirmed = false }
  function originalChanged() { invalidatePending(); clearReceipt() }
  function switchMode(mode: 'create' | 'revise') { if (!state.busy) { state.mode = mode; sourceChanged() } }
  function checkSource(value: AdminSourceData, id: string, datasetId?: string) {
    if (!actor || value.is_synthetic !== actor.is_synthetic || value.source_id !== id || (datasetId && value.dataset_id !== datasetId)) {
      throw new AdminError(200, '来源响应与本次请求不匹配，未确认保存。')
    }
  }
  function applySource(value: AdminSourceData) {
    clearSource(); state.source = value; state.sourceQueryId = value.source_id; state.sourceQueryVersion = ''
    state.draft = { datasetId: value.dataset_id, datasetRevision: value.dataset_revision, reference: '', publisher: value.publisher,
      url: value.entry_url, dataType: value.data_type, scope: value.scope_note, authority: value.authority_claim,
      manual: value.manual_import_permission, publication: value.publication_permission, automated: value.automated_fetch_permission,
      basis: value.license_basis ?? '', permissionReference: value.permission_record_reference ?? '', recheckDays: value.recheck_days,
      manualEnabled: value.manual_import_enabled, confirmed: false }
    state.mode = 'revise'; sourceCreateId = undefined
  }
  function canSave() {
    if (!canManage() || !state.draft.confirmed || !definition(state.draft) || !positive(state.draft.datasetRevision)) return false
    if (state.mode === 'revise') return !!state.source
    const demo = state.context!.is_synthetic
    return uuid(state.draft.datasetId) && /^[A-Za-z0-9][A-Za-z0-9_.:+-]{0,99}$/.test(state.draft.reference)
      && (demo ? state.draft.reference.startsWith('DEMO_') && state.draft.publisher.startsWith('DEMO_')
        : !state.draft.reference.toUpperCase().startsWith('DEMO_') && !state.draft.publisher.toUpperCase().startsWith('DEMO_'))
  }
  async function saveSource() {
    if (!canSave()) return
    const value = definition(state.draft)!, old = state.source, revision = positive(state.draft.datasetRevision)!, mode = state.mode
    sourceCreateId ??= crypto.randomUUID()
    const sourceId = mode === 'create' ? sourceCreateId : old!.source_id
    const input = { source: { id: sourceId, dataset_id: state.draft.datasetId, reference_key: state.draft.reference,
      is_synthetic: state.context!.is_synthetic, definition: value }, expected_dataset_revision: revision, confirmed: true as const }
    const { current, signal } = begin('source'); clearReceipt(); state.draft.confirmed = false
    try {
      const result = mode === 'create' ? await api.register(input, signal) : await api.revise(sourceId,
        { definition: value, expected_dataset_revision: revision, expected_source_version: old!.version, confirmed: true }, signal)
      if (current !== generation) return
      checkSource(result, sourceId, mode === 'create' ? input.source.dataset_id : old!.dataset_id)
      if (result.version !== (mode === 'create' ? 1 : old!.version + 1)
        || sourceDefinitionKeys.some(key => result[key] !== value[key])) throw new AdminError(200, '返回的来源版本或声明与本次确认不一致。')
      applySource(result); state.message = '服务端已保存来源声明版本。这不是事实审核或资料发布。'
    } catch (error) { if (current === generation) { state.source = null; failure(error) } }
    finally { if (current === generation) state.busy = null }
  }
  async function loadSource() {
    if (!canManage() || !uuid(state.sourceQueryId)) return
    const id = state.sourceQueryId, rawVersion = String(state.sourceQueryVersion)
    const version = rawVersion === '' ? undefined : positive(state.sourceQueryVersion)
    if (version === null) { state.message = '来源版本须为严格正整数。'; return }
    const { current, signal } = begin('source-read'); clearSource()
    try {
      const result = await api.source(id, version, signal)
      if (current !== generation) return
      checkSource(result, id)
      if (version !== undefined && result.version !== version) throw new AdminError(200)
      applySource(result); state.message = '已读取来源版本；上传及导入仍由服务端重验当前许可和期限。'
    } catch (error) { if (current === generation) failure(error) }
    finally { if (current === generation) state.busy = null }
  }
  async function chooseFile(file: File) {
    if (!canImport()) return
    const { current } = begin('file-read'); clearReceipt(); state.content = ''; state.filename = ''
    try {
      const content = await readOriginal(file)
      if (current !== generation) return
      if (!/\.(json|csv)$/i.test(file.name)) throw new AdminError(422, '仅选择 .json 或 .csv UTF-8 原文。')
      state.content = content; state.filename = file.name
      state.contentType = /\.csv$/i.test(file.name) ? 'text/csv' : 'application/json'
    } catch (error) { if (current === generation) failure(error) }
    finally { if (current === generation) state.busy = null }
  }
  function canUpload() {
    return canImport() && !!state.source?.manual_import_enabled && state.source.manual_import_permission === 'granted'
      && state.fileConfirmed && !!state.filename && !!state.content
  }
  async function upload() {
    if (!canUpload()) return
    const source = state.source!, input = { source_id: source.source_id, source_version: source.version, filename: state.filename,
      content_type: state.contentType, content_utf8: state.content, confirmed: true as const }
    const { current, signal } = begin('upload'); clearReceipt()
    try {
      const bytes = contentBytes(input.content_utf8)
      const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', Uint8Array.from(bytes)))].map(value => value.toString(16).padStart(2, '0')).join('')
      if (current !== generation) return
      const result = await api.upload(input, signal)
      if (current !== generation) return
      if (!actor || state.source?.source_id !== input.source_id || state.source.version !== input.source_version
        || result.is_synthetic !== actor.is_synthetic || result.sha256 !== digest || result.size_bytes !== bytes.length
        || result.namespace !== 'source_quarantine' || result.status !== 'quarantined' || result.media_type !== input.content_type) {
        throw new AdminError(200, '隔离文件回执与原文字节不一致，未确认上传。')
      }
      state.file = result; state.message = '服务端已隔离保存原文字节。隔离不代表安全扫描、审核或发布。'
    } catch (error) { if (current === generation) failure(error) }
    finally { if (current === generation) state.busy = null }
  }
  function canSubmitImport() { return canImport() && !!state.source && !!state.file && state.importConfirmed }
  async function submitImport() {
    if (!canSubmitImport()) return
    const source = state.source!, file = state.file!
    const input = { dataset_id: source.dataset_id, source_id: source.source_id, source_version: source.version,
      file_id: file.id, file_sha256: file.sha256, format: file.media_type === 'application/json' ? 'json' as const : 'csv' as const, confirmed: true as const }
    const fingerprint = JSON.stringify(input)
    if (fingerprint !== requestPayload || !requestKey) { requestPayload = fingerprint; requestKey = crypto.randomUUID() }
    const key = requestKey, { current, signal } = begin('import'); state.result = null; state.importConfirmed = false
    try {
      const result = await api.import(input, key, signal)
      if (current !== generation) return
      state.result = result; state.importQueryId = result.id
      state.message = result.status === 'staged' ? '服务端已暂存候选：draft / unresolved，尚未审核或发布。'
        : '服务端已拒绝整批导入：暂存候选为 0，请按固定错误位置修正原文。'
    } catch (error) { if (current === generation) failure(error) }
    finally { if (current === generation) state.busy = null }
  }
  async function loadImport() {
    if (!canImport() || !uuid(state.importQueryId)) return
    const id = state.importQueryId, { current, signal } = begin('import-read'); state.result = null
    try {
      const result = await api.result(id, signal)
      if (current !== generation) return
      if (result.id !== id) throw new AdminError(200, '导入回执与请求不匹配。')
      state.result = result; state.message = '已按当前权限重新读取导入回执。候选状态不代表资料已发布。'
    } catch (error) { if (current === generation) failure(error) }
    finally { if (current === generation) state.busy = null }
  }
  function dispose() { generation++; pending?.abort(); actor = null; state.busy = null; reset(); state.status = 'idle' }
  return { state, setActor, refresh, dispose, canManage, canImport, canSave, saveSource, loadSource, sourceChanged, queryChanged,
    originalChanged, switchMode, chooseFile, canUpload, upload, canSubmitImport, submitImport, loadImport }
}
