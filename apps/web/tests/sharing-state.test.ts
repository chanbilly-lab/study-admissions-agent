import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SharingError, type GrantMutationData, type GrantListData } from '../src/features/sharing/client'
import { useSharing } from '../src/features/sharing/useSharing'
import { actor, otherActor, deferred, grant, grants, mutation, policy, sharingApi, now, resourceId, grantId } from './sharingFixtures'
import { consentId } from './privacyFixtures'
beforeEach(() => vi.spyOn(Date, 'now').mockReturnValue(now))
function fill(model: ReturnType<typeof useSharing>) {
  Object.assign(model.state, { resourceType: 'profile', resourceId, resourceVersion: 1, granteeId: otherActor.user_id,
    fields: ['status'], actions: ['read'], expiryUtc: '2026-10-04T00:00:00', confirmed: true })
}
describe('current sharing state', () => {
  it('loads anonymous policy without reading grant metadata or collecting inputs', async () => {
    const api = sharingApi(), model = useSharing(api)
    await model.setActor(null)
    expect(api.list).not.toHaveBeenCalled(); expect(model.canCreate()).toBe(false); expect(model.state.confirmed).toBe(false)
  })
  it('closed settings suppress positive actions but allow current owner revocation', async () => {
    const api = sharingApi({ policy: vi.fn(async () => policy({ sharing_available: false, readiness_reason: 'disabled' })),
      list: vi.fn(async () => grants({ sharing_available: false, actor_declaration_id: null, owner_consent_id: null, items: [grant()], total: 1 })) })
    const model = useSharing(api); await model.setActor(actor); fill(model)
    expect(model.canCreate()).toBe(false); expect(model.canRevoke(grant())).toBe(true)
    await model.create(); expect(api.create).not.toHaveBeenCalled()
    await model.revoke(grant()); expect(api.revoke).toHaveBeenCalledOnce()
  })
  it.each(['issued', 'received'] as const)('policy failure retains %s management with only a negative action', async direction => {
    const current = direction === 'issued' ? actor : otherActor
    const api = sharingApi({ policy: vi.fn().mockRejectedValue(new SharingError(503)),
      list: vi.fn(async queried => grants({ user_id: current.user_id, items: queried === direction ? [grant()] : [], total: queried === direction ? 1 : 0 })),
      revoke: vi.fn(async () => mutation({ user_id: current.user_id, grant: grant({ state: 'revoked', revoked_at: '2026-10-03T00:00:02Z' }) })) })
    const model = useSharing(api); await model.setActor(current); await model.chooseDirection(direction)
    expect(model.state.status).toBe('ready'); expect(model.state.policy).toBeNull(); expect(model.state.list?.items).toHaveLength(1)
    expect(model.state.policyError).toContain('创建和接受保持关闭')
    fill(model); model.state.acceptConfirmed[grantId] = true
    expect(model.canCreate()).toBe(false); expect(model.canAccept(grant())).toBe(false); expect(model.canRevoke(grant())).toBe(true)
    await model.create(); await model.accept(grant())
    expect(api.create).not.toHaveBeenCalled(); expect(api.accept).not.toHaveBeenCalled()
    await model.revoke(grant()); expect(api.revoke).toHaveBeenCalledOnce()
    expect(model.state.message).toContain('服务端已确认撤销')
    expect(model.state.policyError).toContain('创建和接受保持关闭')
  })
  it('management 401 still clears identity despite an independent policy failure', async () => {
    const expired = vi.fn()
    const model = useSharing(sharingApi({ policy: vi.fn().mockRejectedValue(new SharingError(503)), list: vi.fn().mockRejectedValue(new SharingError(401)) }), expired)
    await model.setActor(actor); expect(expired).toHaveBeenCalledOnce()
    expect(model.state.list).toBeNull(); expect(model.state.status).toBe('error')
  })
  it('requires every concrete choice and separate unselected confirmation', async () => {
    const api = sharingApi(), model = useSharing(api); await model.setActor(actor)
    await model.create(); expect(api.create).not.toHaveBeenCalled()
    fill(model); model.state.confirmed = false
    expect(model.inputReady()).toBe(false); await model.create(); expect(api.create).not.toHaveBeenCalled()
    model.state.confirmed = true; await model.create()
    expect(api.create).toHaveBeenCalledWith({ resource_type: 'profile', resource_id: resourceId, expected_resource_version: 1, grantee_user_id: otherActor.user_id,
      fields: ['status'], actions: ['read'], expires_at: '2026-10-04T00:00:00.000Z', confirmed: true, expected_revision: 0,
      owner_consent_id: consentId, sharing_policy_version: policy().policy_version, sharing_policy_hash: policy().text_sha256 }, expect.any(AbortSignal))
    expect(model.state.message).toContain('待接受'); expect(model.state.confirmed).toBe(false)
  })
  it.each(['', '2026-02-30T12:00', '2026-10-02T00:00', '2026-12-01T00:00', '2026-10-04T00:00+08:00'])('rejects missing/invalid/past/overlong/ambiguous expiry %s', async expiry => {
    const model = useSharing(sharingApi()); await model.setActor(actor); fill(model); model.state.expiryUtc = expiry
    expect(model.inputReady()).toBe(false)
  })
  it('handles native numeric v-model and refuses fractional versions or self-grants', async () => {
    const model = useSharing(sharingApi()); await model.setActor(actor); fill(model)
    expect(model.inputReady()).toBe(true); model.state.resourceVersion = 1.5; expect(model.inputReady()).toBe(false)
    model.state.resourceVersion = '1'; model.state.granteeId = actor.user_id; expect(model.inputReady()).toBe(false)
  })
  it('does not infer current owner purpose permission from an adult declaration', async () => {
    const model = useSharing(sharingApi({ list: vi.fn(async () => grants({ owner_consent_id: null })) })); await model.setActor(actor)
    fill(model); expect(model.canCreate()).toBe(false)
  })
  it('lets a recipient with a current adult declaration accept without student/core references', async () => {
    const pending = grant(), accepted = grant({ state: 'accepted', version: 2, accepted_at: '2026-10-03T00:00:01Z', access_active: true })
    const api = sharingApi({ list: vi.fn(async direction => grants({ user_id: otherActor.user_id, owner_consent_id: null, items: direction === 'received' ? [pending] : [], total: direction === 'received' ? 1 : 0 })) })
    const model = useSharing(api); await model.setActor(otherActor); await model.chooseDirection('received')
    expect(model.canAccept(pending)).toBe(true); await model.accept(pending); expect(api.accept).not.toHaveBeenCalled()
    model.state.acceptConfirmed[grantId] = true; await model.accept(pending)
    expect(api.accept).toHaveBeenCalledWith(grantId, { confirmed: true, expected_version: 1, sharing_policy_version: policy().policy_version, sharing_policy_hash: policy().text_sha256 }, expect.any(AbortSignal))
    expect(model.canAccept(accepted)).toBe(false)
  })
  it('recipient can reject pending or leave accepted sharing despite missing age or closed configuration', async () => {
    const api = sharingApi({ list: vi.fn(async direction => grants({ user_id: otherActor.user_id, actor_declaration_id: null, owner_consent_id: null,
      sharing_available: false, items: direction === 'received' ? [grant()] : [], total: direction === 'received' ? 1 : 0 })),
      revoke: vi.fn(async () => mutation({ user_id: otherActor.user_id, grant: grant({ state: 'revoked', revoked_at: '2026-10-03T00:00:02Z' }) })) })
    const model = useSharing(api); await model.setActor(otherActor); await model.chooseDirection('received')
    expect(model.canAccept(grant())).toBe(false); expect(model.canRevoke(grant())).toBe(true)
    await model.revoke(grant()); expect(api.revoke).toHaveBeenCalledWith(grantId, expect.any(AbortSignal))
  })
  it('does not accept expired grants or mismatched policy versions', async () => {
    const model = useSharing(sharingApi({ list: vi.fn(async () => grants({ user_id: otherActor.user_id })) }))
    await model.setActor(otherActor); await model.chooseDirection('received')
    expect(model.canAccept(grant({ expires_at: '2026-10-02T00:00:00Z' }))).toBe(false)
    expect(model.canAccept(grant({ sharing_policy_version: 'old' }))).toBe(false)
  })
  it('clears stale access during mutation and prevents duplicate submission or refresh', async () => {
    const pending = deferred<GrantMutationData>(), api = sharingApi({ create: vi.fn(() => pending.promise) })
    const model = useSharing(api); await model.setActor(actor); fill(model)
    const writing = model.create(); await model.create(); await model.refresh()
    expect(api.create).toHaveBeenCalledOnce(); expect(model.state.list).toBeNull(); expect(model.state.action).toBe('create')
    pending.resolve(mutation()); await writing; expect(model.state.action).toBeNull()
  })
  it('never reports revocation success after network or forbidden refusal', async () => {
    const api = sharingApi({ list: vi.fn(async () => grants({ items: [grant()], total: 1 })), revoke: vi.fn().mockRejectedValue(new SharingError(0)) })
    const model = useSharing(api); await model.setActor(actor); await model.revoke(grant())
    expect(model.state.status).toBe('error'); expect(model.state.list).toBeNull(); expect(model.state.message).toContain('未确认')
    expect(api.revoke).toHaveBeenCalledOnce()
  })
  it('rereads a conflict without replaying positive confirmation', async () => {
    const api = sharingApi({ create: vi.fn().mockRejectedValue(new SharingError(409)), list: vi.fn().mockResolvedValueOnce(grants()).mockResolvedValueOnce(grants({ revision: 4 })) })
    const model = useSharing(api); await model.setActor(actor); fill(model); await model.create()
    expect(api.create).toHaveBeenCalledOnce(); expect(model.state.list?.revision).toBe(4); expect(model.state.confirmed).toBe(false)
    expect(model.state.message).toContain('再次明确确认')
  })
  it('rejects list mappings from another actor or wrong grant direction', async () => {
    const model = useSharing(sharingApi({ list: vi.fn(async () => grants({ items: [grant({ owner_user_id: otherActor.user_id, grantee_user_id: actor.user_id })], total: 1 })) }))
    await model.setActor(actor); expect(model.state.status).toBe('error'); expect(model.state.list).toBeNull()
  })
  it.each([
    { user_id: otherActor.user_id },
    { grant: grant({ fields: ['status', 'version'] }) },
  ])('rejects a creation response for the wrong actor or a broader scope', async override => {
    const api = sharingApi({ create: vi.fn(async () => mutation(override)) }), model = useSharing(api)
    await model.setActor(actor); fill(model); await model.create()
    expect(model.state.status).toBe('error'); expect(model.state.list).toBeNull()
    expect(model.state.message).toContain('未确认')
  })
  it('ignores an old mutation after switching accounts and clears its confirmation', async () => {
    const pending = deferred<GrantMutationData>()
    const api = sharingApi({ create: vi.fn(() => pending.promise), list: vi.fn().mockResolvedValueOnce(grants()).mockResolvedValueOnce(grants({ user_id: otherActor.user_id })) })
    const model = useSharing(api); await model.setActor(actor); fill(model)
    const writing = model.create(); await model.setActor(otherActor); pending.resolve(mutation()); await writing
    expect(model.state.list?.user_id).toBe(otherActor.user_id); expect(model.state.action).toBeNull()
    expect(model.state.confirmed).toBe(false); expect(model.state.message).toBe('')
  })
  it('ignores an old successful list or 401 after an actor switch', async () => {
    const pending = deferred<GrantListData>(), expired = vi.fn()
    const api = sharingApi({ list: vi.fn().mockImplementationOnce(() => pending.promise).mockResolvedValueOnce(grants({ user_id: otherActor.user_id })) })
    const model = useSharing(api, expired); const old = model.setActor(actor); await Promise.resolve(); await Promise.resolve()
    await model.setActor(otherActor); pending.reject(new SharingError(401)); await old
    expect(model.state.list?.user_id).toBe(otherActor.user_id); expect(expired).not.toHaveBeenCalled()
    expect(model.state.confirmed).toBe(false); expect(model.state.granteeId).toBe('')
  })
  it('clears current identity on 401 and never restores disposed state', async () => {
    const expired = vi.fn(), model = useSharing(sharingApi({ list: vi.fn().mockRejectedValue(new SharingError(401)) }), expired)
    await model.setActor(actor); expect(expired).toHaveBeenCalledOnce(); expect(model.state.list).toBeNull()
    const pending = deferred<GrantListData>(), api = sharingApi({ list: vi.fn(() => pending.promise) }), other = useSharing(api)
    const reading = other.setActor(actor); await Promise.resolve(); await Promise.resolve(); other.dispose()
    pending.resolve(grants()); await reading; expect(other.state.policy).toBeNull(); expect(other.state.list).toBeNull()
  })
})
