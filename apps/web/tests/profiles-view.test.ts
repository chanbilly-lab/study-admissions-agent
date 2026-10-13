import { webcrypto } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ProfileView from '../src/views/ProfileView.vue'
import PrivacyPanel from '../src/features/privacy/PrivacyPanel.vue'
import AuthView from '../src/features/auth/AuthView.vue'
import { ProfileError } from '../src/features/profiles/client'
import { PrivacyError, type AdmissionData } from '../src/features/privacy/client'
import { actor, otherActor, deferred, profileApi, rootId, version, versionId } from './profilesFixtures'
import { allowed, declared, privacyApi } from './privacyFixtures'

let wrapper: VueWrapper | undefined
beforeEach(() => vi.stubGlobal('crypto', webcrypto))
afterEach(() => { wrapper?.unmount(); wrapper = undefined; vi.restoreAllMocks(); vi.unstubAllGlobals() })
const find = (id: string) => wrapper!.get(`[data-testid="${id}"]`)
async function scope(key: string, value: string) {
  await find(`profile-${key}-status`).setValue('known')
  await find(`profile-${key}-value`).setValue(value)
}
async function current() {
  await find('profile-list').trigger('click'); await flushPromises()
  await find(`profile-load-${rootId}`).trigger('click'); await flushPromises()
}

describe('profile confirmation uses the real DOM and retains full versions', () => {
  it.each([null, actor])('does not collect any student input while actor/core admission is absent', async currentActor => {
    const api = profileApi()
    wrapper = mount(ProfileView, { props: { actor: currentActor, coreAllowed: false, api } })
    await flushPromises()
    expect(wrapper.find('input').exists()).toBe(false)
    expect(wrapper.find('form').exists()).toBe(false)
    expect(api.context).not.toHaveBeenCalled()
  })

  it('keeps empty numbers distinct from zero and sends independent exact decimal slots only after confirmation', async () => {
    const api = profileApi(), storage = vi.spyOn(Storage.prototype, 'setItem')
    wrapper = mount(ProfileView, { props: { actor, coreAllowed: true, api } }); await flushPromises()
    expect(wrapper.find('form').exists()).toBe(false)
    await find('profile-new').trigger('click')
    expect(find('profile-entry-year').element).toHaveProperty('value', '')
    expect(find('profile-weekly-hours').element).toHaveProperty('value', '')
    expect(wrapper.find('[data-testid="profile-grade-add-key"]').exists()).toBe(false)
    await find('profile-entry-year').setValue('2027')
    await scope('residence_region', 'HK'); await scope('course_system', 'gaokao')
    await scope('applicant_category', 'cn_mainland'); await scope('exam_province', 'Zhejiang'); await scope('pathway', 'gaokao')
    expect(find('profile-residence_region-value').text()).toContain('中国香港')
    await find('profile-grade-add-key').setValue('math'); await find('profile-grade-add').trigger('click')
    await find('grade-math-achieved-status').setValue('provided')
    expect(find('grade-math-achieved-value').element).toHaveProperty('value', '')
    expect(find('grade-math-achieved-scale').element).toHaveProperty('value', '')
    expect(find('grade-math-achieved-value').attributes('type')).toBeUndefined()
    await find('grade-math-achieved-value').setValue('0'); await find('grade-math-achieved-scale').setValue('150')
    await find('grade-math-achieved-unit').setValue('points')
    await find('grade-math-predicted-status').setValue('provided')
    await find('grade-math-predicted-value').setValue('149.000001'); await find('grade-math-predicted-scale').setValue('150')
    await find('grade-math-predicted-unit').setValue('points')
    await find('profile-weekly-hours').setValue('0')
    expect(find('profile-save').attributes('disabled')).toBeDefined()
    await wrapper.get('form').trigger('submit'); expect(api.create).not.toHaveBeenCalled()
    await find('profile-confirmation').setValue(true)
    await find('profile-weekly-hours').setValue('')
    expect(find('profile-confirmation').element).toHaveProperty('checked', false)
    await find('profile-weekly-hours').setValue('0'); await find('profile-confirmation').setValue(true)
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="profile-current"]').exists()).toBe(true))
    expect(api.create).toHaveBeenCalledWith(expect.objectContaining({ confirmed: true, profile: expect.objectContaining({
      weekly_hours: '0', residence_region: { status: 'known', value: 'HK' }, assessments: { math: {
        achieved: { status: 'provided', value: '0', scale: '150', unit: 'points' },
        predicted: { status: 'provided', value: '149.000001', scale: '150', unit: 'points' },
      } },
    }) }), expect.any(String), expect.any(AbortSignal))
    expect(wrapper.find('form').exists()).toBe(false)
    expect(wrapper.text()).toContain('本人声明'); expect(wrapper.text()).toContain('尚无可用资格结果')
    expect(storage).not.toHaveBeenCalled()
  })

  it('loads read-only, explicitly edits and clears a supplied grade to missing/null without changing history', async () => {
    const original = version(), api = profileApi({ current: vi.fn(async () => original) })
    wrapper = mount(ProfileView, { props: { actor, coreAllowed: true, api } }); await flushPromises(); await current()
    expect(wrapper.find('form').exists()).toBe(false)
    await find('profile-edit').trigger('click')
    expect(find('grade-math-achieved-value').element).toHaveProperty('value', '0')
    await find('grade-math-achieved-value').setValue('125.25'); await find('grade-math-achieved-value').setValue('')
    await find('profile-confirmation').setValue(true)
    expect(find('profile-save').attributes('disabled')).toBeDefined()
    await find('grade-math-achieved-status').setValue('missing')
    expect(find('profile-confirmation').element).toHaveProperty('checked', false)
    await find('profile-confirmation').setValue(true); await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(find('profile-current-version').text()).toBe('2'))
    expect(api.append).toHaveBeenCalledWith(rootId, expect.objectContaining({ expected_current_version: 1,
      profile: expect.objectContaining({ weekly_hours: null, assessments: { math: {
        achieved: { status: 'missing', value: null, scale: null, unit: null },
        predicted: { status: 'pending', value: null, scale: null, unit: null },
      } } }),
    }), expect.any(AbortSignal))
    await find('profile-history-version-id').setValue(versionId); await find('profile-history-load').trigger('click'); await flushPromises()
    expect(find('profile-history-result').text()).toContain('0 / 100 points')
    expect(find('profile-current-version').text()).toBe('2')
    expect(original.profile.assessments.math!.achieved.value).toBe('0')
  })

  it('retains a CAS-conflicted draft until an explicit current-version read binds a fresh CAS', async () => {
    const api = profileApi({ append: vi.fn().mockRejectedValue(new ProfileError(409)),
      current: vi.fn().mockResolvedValueOnce(version()).mockResolvedValueOnce(version({ version: 3 })) })
    wrapper = mount(ProfileView, { props: { actor, coreAllowed: true, api } }); await flushPromises(); await current()
    await find('profile-edit').trigger('click'); await find('profile-weekly-hours').setValue('2')
    await find('profile-confirmation').setValue(true); await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(find('profile-conflict').text()).toContain('保存未确认')
    expect(find('profile-weekly-hours').element).toHaveProperty('value', '2')
    expect(find('profile-confirmation').element).toHaveProperty('checked', false)
    expect(find('profile-save').attributes('disabled')).toBeDefined()
    expect(api.current).toHaveBeenCalledOnce(); expect(api.append).toHaveBeenCalledOnce()
    await find('profile-reload-current').trigger('click'); await flushPromises()
    expect(find('profile-current-version').text()).toBe('3')
    expect(find('profile-weekly-hours').element).toHaveProperty('value', '2')
    expect(wrapper.find('[data-testid="profile-conflict"]').exists()).toBe(false)
    expect(find('profile-confirmation').element).toHaveProperty('checked', false)
    expect(api.append).toHaveBeenCalledOnce()
  })

  it('explicitly changing to an unsupported identity clears only the draft and removes high-school score questions', async () => {
    const saved = version(), api = profileApi({ current: vi.fn(async () => saved) })
    wrapper = mount(ProfileView, { props: { actor, coreAllowed: true, api } }); await flushPromises(); await current()
    await find('profile-edit').trigger('click'); await find('profile-applicant_category-value').setValue('hmt_joint')
    expect(wrapper.find('[data-testid="grade-math-achieved-status"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="profile-grade-add-key"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('旧确认版完整保留')
    expect(saved.profile.assessments.math!.achieved.value).toBe('0')
    expect(find('profile-current').text()).toContain('0 / 100 points')
  })
})

describe('privacy changes synchronously invalidate private profile state', () => {
  it.each(['age', 'withdraw', 'refresh', 'actor'] as const)('emits false before a pending %s response completes', async action => {
    const pending = deferred<AdmissionData>(), api = privacyApi({ admission: vi.fn(async () => allowed()) })
    if (action === 'age') api.declareAge = vi.fn(() => pending.promise)
    if (action === 'withdraw') api.withdraw = vi.fn(() => pending.promise)
    if (action === 'refresh' || action === 'actor') api.admission = vi.fn().mockResolvedValueOnce(allowed()).mockReturnValueOnce(pending.promise)
    wrapper = mount(PrivacyPanel, { props: { actor, api } }); await flushPromises()
    expect(wrapper.emitted('admissionChanged')!.at(-1)).toEqual([true])
    if (action === 'age') {
      await wrapper.get('input[value="unknown"]').setValue(true); await find('age-confirmation').setValue(true)
      await wrapper.get('form').trigger('submit')
    } else if (action === 'withdraw') await find('withdraw-core').trigger('click')
    else if (action === 'refresh') await wrapper.get('button.privacy-refresh').trigger('click')
    else await wrapper.setProps({ actor: otherActor })
    expect(wrapper.emitted('admissionChanged')!.at(-1)).toEqual([false])
    pending.reject(new PrivacyError(503)); await flushPromises()
    expect(wrapper.emitted('admissionChanged')!.at(-1)).toEqual([false])
    expect(wrapper.text()).not.toContain('服务端已返回撤回后的当前状态')
  })

  it('clears already displayed grades while withdrawal is in flight and never restores a late read or the old consent automatically', async () => {
    const pendingWithdrawal = deferred<AdmissionData>(), pendingRead = deferred<ReturnType<typeof version>>()
    const profiles = profileApi({ current: vi.fn().mockResolvedValueOnce(version()).mockReturnValueOnce(pendingRead.promise) })
    const privacy = privacyApi({ admission: vi.fn(async () => allowed()), withdraw: vi.fn(() => pendingWithdrawal.promise) })
    const api = { loginPath: '/api/v2/auth/login', session: vi.fn(async () => actor),
      csrf: vi.fn(async () => ({ csrf_token: 'T'.repeat(43), expires_at: actor.expires_at })), logout: vi.fn(async () => ({ logged_out: true as const })) }
    wrapper = mount(AuthView, { props: { api, privacyApi: privacy, profileApi: profiles },
      global: { stubs: { SharingPanel: true, AdminView: true, ReviewReleaseView: true } } })
    await flushPromises(); await current()
    expect(find('profile-current').text()).toContain('0 / 100 points')
    await find(`profile-load-${rootId}`).trigger('click')
    const signal = vi.mocked(profiles.current).mock.calls[1][1]!
    await find('withdraw-core').trigger('click')
    expect(signal.aborted).toBe(true)
    expect(wrapper.find('[data-testid="profile-current"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="profile-list"]').exists()).toBe(false)
    pendingRead.resolve(version()); await flushPromises()
    expect(wrapper.find('[data-testid="profile-current"]').exists()).toBe(false)
    pendingWithdrawal.resolve(declared({ consent_status: 'withdrawn', core_consultation_allowed: false, reason: 'consent_withdrawn' })); await flushPromises()
    await find('core-confirmation').setValue(true); await wrapper.findAll('.privacy-form')[1].trigger('submit'); await flushPromises()
    expect(wrapper.find('[data-testid="profile-new"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="profile-current"]').exists()).toBe(false)
    expect(profiles.current).toHaveBeenCalledTimes(2)
  })
})
