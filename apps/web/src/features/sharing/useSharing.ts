import { reactive } from 'vue'
import type { SessionData } from '../auth/client'
import { createSharingApi, SharingError, uuid, type SharingApi, type SharingPolicyData, type GrantListData,
  type GrantData, type GrantMutationData, type Direction, type ResourceType, type SharedField, type SharedAction } from './client'

export function useSharing(api: SharingApi = createSharingApi(), onSessionExpired: () => void = () => {}) {
  const state = reactive<{
    status: 'loading' | 'ready' | 'error'; policy: SharingPolicyData | null; list: GrantListData | null;
    direction: Direction; message: string; policyError: string; action: 'create' | 'accept' | 'revoke' | null;
    resourceType: ResourceType | ''; resourceId: string; resourceVersion: string | number; granteeId: string;
    fields: SharedField[]; actions: SharedAction[]; expiryUtc: string; confirmed: boolean; acceptConfirmed: Record<string, boolean>;
  }>({ status: 'loading', policy: null, list: null, direction: 'issued', message: '', policyError: '', action: null,
    resourceType: '', resourceId: '', resourceVersion: '', granteeId: '', fields: [], actions: [], expiryUtc: '', confirmed: false, acceptConfirmed: {} })
  let actor: SessionData | null = null
  let generation = 0
  let pending: AbortController | undefined
  function clearInput() {
    state.resourceType = ''; state.resourceId = ''; state.resourceVersion = ''; state.granteeId = ''
    state.fields = []; state.actions = []; state.expiryUtc = ''; state.confirmed = false; state.acceptConfirmed = {}
  }
  function begin() {
    const current = ++generation
    pending?.abort(); pending = new AbortController()
    state.list = null; state.message = ''; state.confirmed = false; state.acceptConfirmed = {}
    return { current, signal: pending.signal }
  }
  function checkList(list: GrantListData) {
    if (!actor || list.user_id !== actor.user_id || list.items.some(grant => grant.is_synthetic !== actor!.is_synthetic
      || (state.direction === 'issued' ? grant.owner_user_id : grant.grantee_user_id) !== actor!.user_id)) {
      throw new SharingError(200, '授权列表与当前会话不匹配，共享状态已清空。')
    }
  }
  function failure(error: unknown) {
    state.list = null; state.status = 'error'
    state.message = error instanceof SharingError ? error.message : '共享状态无法确认，请重新读取。'
    if (error instanceof SharingError && error.status === 401) onSessionExpired()
  }
  async function refresh(afterId?: string) {
    if (state.action) return
    const { current, signal } = begin()
    state.status = 'loading'; state.policy = null; state.policyError = ''
    try {
      // Management reads are independent of the positive policy gate. A broken
      // notice must not prevent the actor reducing an existing permission.
      const [policy, listed] = await Promise.allSettled([
        api.policy(signal), actor ? api.list(state.direction, afterId, signal) : Promise.resolve(null),
      ])
      if (current !== generation) return
      if (policy.status === 'rejected' && policy.reason instanceof SharingError && policy.reason.status === 401) throw policy.reason
      if (policy.status === 'fulfilled') state.policy = policy.value
      if (listed.status === 'rejected') throw listed.reason
      if (listed.value) { checkList(listed.value); state.list = listed.value }
      if (policy.status === 'rejected') {
        if (!state.list) throw policy.reason
        state.policyError = '共享告知暂不可读取，创建和接受保持关闭。已有授权仍可撤销、拒绝或退出。'
      }
      state.status = 'ready'
    } catch (error) { if (current === generation) failure(error) }
  }
  function setActor(value: SessionData | null) {
    actor = value; state.action = null; state.direction = 'issued'; clearInput()
    return refresh()
  }
  function chooseDirection(direction: Direction) {
    if (state.action || direction === state.direction) return Promise.resolve()
    state.direction = direction; clearInput(); return refresh()
  }
  function available() {
    return state.status === 'ready' && !state.action && actor?.is_synthetic === true && state.policy?.is_synthetic === true
      && state.policy.sharing_available && state.list?.sharing_available === true
  }
  function canCreate() { return available() && state.direction === 'issued' && !!state.list?.actor_declaration_id && !!state.list.owner_consent_id }
  function canAccept(grant: GrantData) {
    return available() && state.direction === 'received' && !!state.list?.actor_declaration_id
      && grant.grantee_user_id === actor?.user_id && grant.state === 'pending' && grant.revoked_at === null
      && grant.sharing_policy_version === state.policy?.policy_version && Date.parse(grant.expires_at) > Date.now()
  }
  function canRevoke(grant: GrantData) {
    return state.status === 'ready' && !state.action && !!actor && grant.state !== 'revoked'
      && (state.direction === 'issued' ? actor.user_id === grant.owner_user_id : actor.user_id === grant.grantee_user_id)
  }
  function expiryIso() {
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/.test(state.expiryUtc)) return null
    const value = state.expiryUtc.length === 16 ? state.expiryUtc + ':00Z' : state.expiryUtc + 'Z'
    const date = new Date(value)
    if (!Number.isFinite(date.getTime()) || date.toISOString().slice(0, 19) !== value.slice(0, 19)) return null
    return date.toISOString()
  }
  function inputReady() {
    const scope = state.policy?.scope_matrix.find(item => item.resource_type === state.resourceType)
    const expiry = expiryIso()
    const version = Number(String(state.resourceVersion).trim())
    return canCreate() && state.confirmed && uuid(state.resourceId.trim()) && uuid(state.granteeId.trim())
      && state.granteeId.trim().toLowerCase() !== actor?.user_id.toLowerCase()
      && Number.isSafeInteger(version) && version >= 1 && scope !== undefined
      && state.fields.length > 0 && new Set(state.fields).size === state.fields.length && state.fields.every(field => scope.fields.includes(field))
      && state.actions.length > 0 && new Set(state.actions).size === state.actions.length && state.actions.every(action => scope.actions.includes(action))
      && expiry !== null && Date.parse(expiry) > Date.now() && Date.parse(expiry) - Date.now() <= state.policy!.max_duration_seconds * 1000
  }
  function checkMutation(result: GrantMutationData, action: 'create' | 'accept' | 'revoke', id?: string, input?: Parameters<SharingApi['create']>[0] | null) {
    if (!actor || result.user_id !== actor.user_id || result.grant.is_synthetic !== actor.is_synthetic
      || (action === 'accept' ? result.grant.grantee_user_id !== actor.user_id
        : action === 'create' ? result.grant.owner_user_id !== actor.user_id
          : result.grant.owner_user_id !== actor.user_id && result.grant.grantee_user_id !== actor.user_id)
      || (id && result.grant.id !== id)
      || (action === 'create' && (result.grant.state !== 'pending' || result.grant.access_active))
      || (action === 'accept' && (result.grant.state !== 'accepted' || result.grant.accepted_at === null))
      || (action === 'revoke' && (result.grant.state !== 'revoked' || result.grant.access_active))) {
      throw new SharingError(200, '服务端授权状态与当前操作不匹配，本次操作未确认。')
    }
    if (input && (result.grant.resource_id.toLowerCase() !== input.resource_id.toLowerCase()
      || result.grant.resource_type !== input.resource_type || result.grant.resource_version !== input.expected_resource_version
      || result.grant.grantee_user_id.toLowerCase() !== input.grantee_user_id.toLowerCase()
      || result.grant.sharing_policy_version !== input.sharing_policy_version
      || Date.parse(result.grant.expires_at) !== Date.parse(input.expires_at)
      || [...result.grant.fields].sort().join(',') !== [...input.fields].sort().join(',')
      || [...result.grant.actions].sort().join(',') !== [...input.actions].sort().join(','))) {
      throw new SharingError(200, '服务端授权范围与本次明确确认不匹配，本次创建未确认。')
    }
  }
  async function mutate(action: 'create' | 'accept' | 'revoke', grant?: GrantData) {
    if (!actor || state.action || state.status !== 'ready' || !state.list || (action !== 'revoke' && !state.policy)) return
    if (action === 'create' && !inputReady()) return
    if (action === 'accept' && (!grant || !canAccept(grant) || !state.acceptConfirmed[grant.id])) return
    if (action === 'revoke' && (!grant || !canRevoke(grant))) return
    const list = state.list, policy = state.policy
    const input = action === 'create' ? {
      resource_type: state.resourceType as ResourceType, resource_id: state.resourceId.trim(), expected_resource_version: Number(state.resourceVersion),
      grantee_user_id: state.granteeId.trim(), fields: [...state.fields], actions: [...state.actions], expires_at: expiryIso()!, confirmed: true as const,
      expected_revision: list.revision, owner_consent_id: list.owner_consent_id!, sharing_policy_version: policy!.policy_version, sharing_policy_hash: policy!.text_sha256,
    } : null
    const { current, signal } = begin(); state.action = action
    try {
      const result = action === 'create' ? await api.create(input!, signal)
        : action === 'accept' ? await api.accept(grant!.id, { confirmed: true, expected_version: grant!.version, sharing_policy_version: policy!.policy_version, sharing_policy_hash: policy!.text_sha256 }, signal)
        : await api.revoke(grant!.id, signal)
      if (current !== generation) return
      checkMutation(result, action, grant?.id, input)
      clearInput()
      const latest = await api.list(state.direction, undefined, signal)
      if (current !== generation) return
      checkList(latest); state.list = latest; state.status = 'ready'
      state.message = action === 'create' ? '服务端已创建待接受授权；受权人须在自己的会话中独立接受。'
        : action === 'accept' ? '服务端已返回接受结果；是否当前有效以重新读取的状态为准。' : '服务端已确认撤销，并重新读取当前授权列表。'
    } catch (error) {
      if (current !== generation) return
      state.action = null
      if (error instanceof SharingError && error.status === 409) {
        await refresh()
        if (state.status === 'ready') state.message = error.message
      } else failure(error)
    } finally { if (current === generation) state.action = null }
  }
  function dispose() { ++generation; pending?.abort(); actor = null; state.policy = null; state.list = null; state.policyError = ''; state.action = null; clearInput() }
  return { state, setActor, refresh, chooseDirection, canCreate, canAccept, canRevoke, inputReady,
    create: () => mutate('create'), accept: (grant: GrantData) => mutate('accept', grant), revoke: (grant: GrantData) => mutate('revoke', grant), dispose }
}
