import { describe, expect, it, vi } from 'vitest'
import { PrivacyError, type AdmissionData, type AgeBand } from '../src/features/privacy/client'
import { useAdmission } from '../src/features/privacy/useAdmission'
import { actor, otherActor, admission, allowed, declared, notice, noticeId, consentId, privacyApi, deferred } from './privacyFixtures'

describe('current privacy admission state', () => {
  it('reads public notice without demanding a login or sending age', async () => {
    const api = privacyApi()
    const model = useAdmission(api)
    await model.setActor(null)
    expect(api.admission).not.toHaveBeenCalled()
    expect(model.state.notice?.text).toContain('DEMO')
    expect(model.canSubmit()).toBe(false)
    model.dispose()
  })
  it('keeps writes closed when the notice is not ready', async () => {
    const api = privacyApi({ notice: vi.fn(async () => notice({ readiness: false, readiness_reason: 'processing_disabled' })), admission: vi.fn(async () => admission({ readiness: false, reason: 'processing_disabled' })) })
    const model = useAdmission(api)
    await model.setActor(actor)
    model.state.ageBand = '18_plus'
    model.state.ageConfirmed = true
    model.state.coreConfirmed = true
    await model.declareAge()
    await model.confirmCore()
    expect(api.declareAge).not.toHaveBeenCalled()
    expect(api.confirmCore).not.toHaveBeenCalled()
    expect(model.state.admission?.core_consultation_allowed).toBe(false)
  })
  it('requires separate unchecked confirmations and uses each current revision', async () => {
    const api = privacyApi()
    const model = useAdmission(api)
    await model.setActor(actor)
    model.state.ageBand = '18_plus'
    await model.declareAge()
    expect(api.declareAge).not.toHaveBeenCalled()
    model.state.ageConfirmed = true
    await model.declareAge()
    expect(api.declareAge).toHaveBeenCalledWith({ age_band: '18_plus', confirmed: true, notice_id: noticeId, expected_revision: 0 }, expect.any(AbortSignal))
    expect(model.state.admission?.age_assurance).toBe('declared')
    expect(model.state.admission?.core_consultation_allowed).toBe(false)
    expect(model.state.ageConfirmed).toBe(false)
    await model.confirmCore()
    expect(api.confirmCore).not.toHaveBeenCalled()
    model.state.coreConfirmed = true
    await model.confirmCore()
    expect(api.confirmCore).toHaveBeenCalledWith({ purpose: 'core_consultation', confirmed: true, notice_id: noticeId, expected_revision: 1 }, expect.any(AbortSignal))
    expect(model.state.admission?.core_consultation_allowed).toBe(true)
    expect(model.state.admission?.private_business_available).toBe(false)
  })
  it.each<AgeBand>(['unknown', 'under_14', '14_17'])('sends %s explicitly and accepts only the server unknown/closed response', async (ageBand) => {
    const api = privacyApi({ admission: vi.fn(async () => allowed()), declareAge: vi.fn(async () => admission({ revision: 3, consent_status: 'invalidated' })) })
    const model = useAdmission(api)
    await model.setActor(actor)
    model.state.ageBand = ageBand
    model.state.ageConfirmed = true
    await model.declareAge()
    expect(api.declareAge).toHaveBeenCalledWith({ age_band: ageBand, confirmed: true, notice_id: noticeId, expected_revision: 2 }, expect.any(AbortSignal))
    expect(model.state.admission?.age_band).toBeNull()
    expect(model.state.admission?.core_consultation_allowed).toBe(false)
    expect(model.state.admission?.consent_status).toBe('invalidated')
  })
  it('clears permission while awaiting a write and rejects double submissions', async () => {
    const pending = deferred<AdmissionData>()
    const api = privacyApi({ admission: vi.fn(async () => allowed()), declareAge: vi.fn(() => pending.promise) })
    const model = useAdmission(api)
    await model.setActor(actor)
    model.state.ageBand = 'unknown'
    model.state.ageConfirmed = true
    const first = model.declareAge()
    await model.declareAge()
    expect(api.declareAge).toHaveBeenCalledTimes(1)
    expect(model.state.admission).toBeNull()
    pending.resolve(admission({ revision: 3 }))
    await first
    expect(model.state.admission?.core_consultation_allowed).toBe(false)
  })
  it('allows withdrawal of an existing active consent when processing readiness is false', async () => {
    const api = privacyApi({ notice: vi.fn(async () => notice({ readiness: false, readiness_reason: 'processing_disabled' })), admission: vi.fn(async () => allowed({ readiness: false, core_consultation_allowed: false, reason: 'processing_disabled' })) })
    const model = useAdmission(api)
    await model.setActor(actor)
    expect(model.canSubmit()).toBe(false)
    await model.withdraw()
    expect(api.withdraw).toHaveBeenCalledWith(consentId, expect.any(AbortSignal))
    expect(model.state.admission?.consent_status).toBe('withdrawn')
  })
  it('does not claim a withdrawal succeeded after network failure', async () => {
    const api = privacyApi({ admission: vi.fn(async () => allowed()), withdraw: vi.fn().mockRejectedValue(new PrivacyError(0, '撤回状态未确认')) })
    const model = useAdmission(api)
    await model.setActor(actor)
    await model.withdraw()
    expect(model.state.status).toBe('error')
    expect(model.state.admission).toBeNull()
    expect(model.state.message).toBe('撤回状态未确认')
  })
  it('re-reads a revision conflict without silently repeating consent', async () => {
    const api = privacyApi({ admission: vi.fn().mockResolvedValueOnce(declared()).mockResolvedValueOnce(declared({ revision: 4 })), confirmCore: vi.fn().mockRejectedValue(new PrivacyError(409)) })
    const model = useAdmission(api)
    await model.setActor(actor)
    model.state.coreConfirmed = true
    await model.confirmCore()
    expect(api.confirmCore).toHaveBeenCalledTimes(1)
    expect(api.admission).toHaveBeenCalledTimes(2)
    expect(model.state.admission?.revision).toBe(4)
    expect(model.state.coreConfirmed).toBe(false)
    expect(model.state.message).toContain('再次明确确认')
  })
  it.each(['age_expired', 'notice_changed', 'policy_changed'] as const)('does not confirm a declaration the server marked %s', async (reason) => {
    const api = privacyApi({ admission: vi.fn(async () => declared({ reason })) })
    const model = useAdmission(api)
    await model.setActor(actor)
    model.state.coreConfirmed = true
    await model.confirmCore()
    expect(model.canConfirm()).toBe(false)
    expect(api.confirmCore).not.toHaveBeenCalled()
    expect(model.state.admission?.core_consultation_allowed).toBe(false)
  })
  it('drops the old read after a withdrawal begins', async () => {
    const old = deferred<AdmissionData>()
    const api = privacyApi({ admission: vi.fn().mockResolvedValueOnce(allowed()).mockImplementationOnce(() => old.promise).mockResolvedValueOnce(allowed()) })
    const model = useAdmission(api)
    await model.setActor(actor)
    const oldRead = model.refresh()
    await model.refresh()
    await model.withdraw()
    old.resolve(allowed())
    await oldRead
    expect(model.state.admission?.consent_status).toBe('withdrawn')
    expect(model.state.admission?.core_consultation_allowed).toBe(false)
  })
  it('clears actor-bound state and ignores an old successful or 401 reply after switching user', async () => {
    const old = deferred<AdmissionData>()
    const expired = vi.fn()
    const api = privacyApi({ admission: vi.fn().mockImplementationOnce(() => old.promise).mockResolvedValueOnce(admission({ user_id: otherActor.user_id })) })
    const model = useAdmission(api, expired)
    const oldRead = model.setActor(actor)
    await model.setActor(otherActor)
    expect(model.state.ageBand).toBe('')
    old.reject(new PrivacyError(401))
    await oldRead
    expect(model.state.admission?.user_id).toBe(otherActor.user_id)
    expect(expired).not.toHaveBeenCalled()
  })
  it('rejects an admission mapped to a different user or synthetic identity', async () => {
    const api = privacyApi({ admission: vi.fn(async () => allowed({ user_id: otherActor.user_id })) })
    const model = useAdmission(api)
    await model.setActor(actor)
    expect(model.state.status).toBe('error')
    expect(model.state.admission).toBeNull()
    expect(model.state.message).toContain('不匹配')
  })
  it('reports current 401 to the session owner and clears all admission', async () => {
    const expired = vi.fn()
    const model = useAdmission(privacyApi({ admission: vi.fn().mockRejectedValue(new PrivacyError(401)) }), expired)
    await model.setActor(actor)
    expect(expired).toHaveBeenCalledTimes(1)
    expect(model.state.admission).toBeNull()
  })
  it('disposal aborts a pending read and prevents it from restoring consent', async () => {
    const pending = deferred<AdmissionData>()
    const api = privacyApi({ admission: vi.fn(() => pending.promise) })
    const model = useAdmission(api)
    const reading = model.setActor(actor)
    const signal = vi.mocked(api.admission).mock.calls[0][0]
    model.dispose()
    expect(signal?.aborted).toBe(true)
    pending.resolve(allowed())
    await reading
    expect(model.state.admission).toBeNull()
    expect(model.state.notice).toBeNull()
  })
})
