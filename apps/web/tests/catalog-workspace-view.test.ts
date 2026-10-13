import { webcrypto } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import AuthView from '../src/features/auth/AuthView.vue'
import ProfileView from '../src/views/ProfileView.vue'
import CatalogView from '../src/views/CatalogView.vue'
import OfferingCard from '../src/features/catalog/OfferingCard.vue'
import AssessmentResult from '../src/features/eligibility/AssessmentResult.vue'
import PublicEvidenceDialog from '../src/features/evidence/PublicEvidenceDialog.vue'
import { SessionError } from '../src/features/auth/client'
import { CatalogError } from '../src/features/catalog/client'
import { EligibilityError } from '../src/features/eligibility/client'
import { actor, otherActor, deferred, profileApi, rootId, version } from './profilesFixtures'
import { assessment, catalogApi, eligibilityApi, offering, publicEvidence, publicFact, publicPage, uid } from './catalogUiFixtures'

let wrapper: VueWrapper | undefined
const originalShow = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype,'showModal')
const originalClose = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype,'close')
beforeEach(() => {
  vi.stubGlobal('crypto',webcrypto)
  Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value:function (this: HTMLDialogElement) { this.setAttribute('open','') }})
  Object.defineProperty(HTMLDialogElement.prototype,'close',{configurable:true,value:function (this: HTMLDialogElement) { this.removeAttribute('open') }})
})
afterEach(() => { wrapper?.unmount(); wrapper = undefined; vi.restoreAllMocks(); vi.unstubAllGlobals(); document.body.innerHTML = ''
  if (originalShow) Object.defineProperty(HTMLDialogElement.prototype,'showModal',originalShow); else Reflect.deleteProperty(HTMLDialogElement.prototype,'showModal')
  if (originalClose) Object.defineProperty(HTMLDialogElement.prototype,'close',originalClose); else Reflect.deleteProperty(HTMLDialogElement.prototype,'close')
})
const find = (id: string) => wrapper!.get(`[data-testid="${id}"]`)
async function query() { await find('catalog-year').setValue('2027'); await wrapper!.get('form').trigger('submit'); await flushPromises() }
async function ready() {
  await query(); await find(`catalog-select-${uid(5)}-1`).trigger('click')
  await find('catalog-context-refresh').trigger('click'); await flushPromises()
  await vi.waitFor(() => expect(find('catalog-confirm').attributes('disabled')).toBeUndefined())
}
function view(overrides = {}, api = catalogApi(), privateApi = eligibilityApi()) {
  wrapper = mount(CatalogView,{ props: { actor, coreAllowed: true, profile: version(), profileEpoch: 0, catalogApi: api, eligibilityApi: privateApi, ...overrides } })
  return { api, privateApi }
}

describe('catalog entry and explicit query', () => {
  it('starts anonymous with no new request or input, then explicitly opens only public configuration', async () => {
    const api = catalogApi(), privateApi = eligibilityApi()
    wrapper = mount(AuthView,{ props: { catalogApi: api, eligibilityApi: privateApi, api: { loginPath: '/api/v2/auth/login', session: vi.fn().mockRejectedValue(new SessionError(401)), csrf: vi.fn(), logout: vi.fn() } }, global: { stubs: { PrivacyPanel: true, ProfileView: true, SharingPanel: true, AdminView: true, ReviewReleaseView: true } } })
    await flushPromises()
    expect(wrapper.find('input').exists()).toBe(false); expect(wrapper.find('form').exists()).toBe(false)
    expect(api.config).not.toHaveBeenCalled(); expect(privateApi.context).not.toHaveBeenCalled()
    await find('catalog-toggle').trigger('click'); await flushPromises()
    expect(api.config).toHaveBeenCalledOnce(); expect(api.offerings).not.toHaveBeenCalled()
    expect(privateApi.context).not.toHaveBeenCalled(); expect(find('catalog-year').element).toHaveProperty('value','')
    await find('catalog-toggle').trigger('click'); expect(wrapper.find('[data-testid="catalog-workspace"]').exists()).toBe(false)
  })

  it('keeps an empty year distinct from zero, and sends exact optional filters through a real form', async () => {
    const api = catalogApi({ offerings: vi.fn(async query => publicPage([],query.limit)) })
    view({ actor: null, coreAllowed: false, profile: null },api); await flushPromises()
    await wrapper!.get('form').trigger('submit'); expect(api.offerings).not.toHaveBeenCalled()
    expect(find('catalog-message').text()).toContain('明确年份')
    await find('catalog-year').setValue('0'); await wrapper!.get('form').trigger('submit'); expect(api.offerings).not.toHaveBeenCalled()
    await find('catalog-year').setValue('2027'); await find('catalog-country').setValue('GB')
    await find('catalog-province').setValue('not_applicable'); await find('catalog-pathway').setValue('known:uk_undergraduate')
    await find('catalog-course-system').setValue('not_applicable'); await find('catalog-applicant-category').setValue('known:cn_mainland'); await find('catalog-limit').setValue('1')
    await wrapper!.get('form').trigger('submit'); await flushPromises()
    expect(api.offerings).toHaveBeenCalledWith(expect.objectContaining({ entry_year: 2027, country: 'GB', province: 'not_applicable', pathway: 'known:uk_undergraduate', course_system: 'not_applicable', applicant_category: 'known:cn_mainland', limit: 1 }),expect.any(AbortSignal))
    expect(find('catalog-coverage').text()).toContain('没有可公开记录')
  })

  it('handles a changed cursor with an explicit restart and clears target/confirmation', async () => {
    const api = catalogApi({ offerings: vi.fn().mockResolvedValueOnce(publicPage([offering()],1,true)).mockRejectedValueOnce(new CatalogError(409)).mockResolvedValueOnce(publicPage([],1)) })
    view({},api); await flushPromises(); await find('catalog-limit').setValue('1'); await ready()
    await find('catalog-confirm').setValue(true); await find('catalog-next').trigger('click'); await flushPromises()
    expect(wrapper!.find('[data-testid="assessment-binding"]').exists()).toBe(false)
    expect(find('catalog-restart').text()).toContain('明确重新读取第一页')
    expect(api.offerings).toHaveBeenCalledTimes(2)
    await find('catalog-restart').trigger('click'); await flushPromises()
    expect(vi.mocked(api.offerings).mock.calls[2]![0]).not.toHaveProperty('cursor')
  })

  it('distinguishes an empty last page from a range without published records', async () => {
    const data = publicPage([]); data.coverage.status = 'partial'
    view({ actor: null,coreAllowed: false,profile: null },catalogApi({ offerings: vi.fn(async () => data) })); await flushPromises(); await query()
    expect(find('catalog-coverage').text()).toContain('部分公开资料')
    expect(wrapper!.text()).toContain('此页已结束'); expect(wrapper!.text()).not.toContain('当前查询范围没有可公开记录')
  })

  it('compares at most four exact release/offering/version identities and clears on filter changes', async () => {
    const rows = [offering(), offering({ version: 2 }), offering({ id: uid(20) }), offering({ id: uid(21) }), offering({ id: uid(22) })]
    view({ actor:null,coreAllowed:false,profile:null },catalogApi({ offerings: vi.fn(async () => publicPage(rows)) })); await flushPromises(); await query()
    for (const item of rows.slice(0,4)) await find(`catalog-compare-${item.id}-${item.version}`).setValue(true)
    expect(find('catalog-comparison').text()).toContain('4 / 4')
    expect(find(`catalog-compare-${uid(22)}-1`).attributes('disabled')).toBeDefined()
    expect(find('catalog-comparison').findAll('article')).toHaveLength(4)
    await find('catalog-country').setValue('GB')
    expect(wrapper!.find('[data-testid="catalog-comparison"]').exists()).toBe(false)
  })
})

describe('declared facts and original qualification are separate', () => {
  it('escapes literal markup and separates minimum, typical, historical and unknown date data', () => {
    const date = { event_type: 'application_deadline' as const, original_text: 'DEMO_只给日期', precision: 'date' as const, local_date: '2027-01-20', local_time: null, timezone: null, source_alignment: 'pending' as const, conversion_status: 'date_only' as const, calculated_utc_instant: null, utc_instant: null, tzdata_version: '2026.4' as const }
    wrapper = mount(OfferingCard,{ props: { offering: offering({ facts: [publicFact(),publicFact({ claim_kind:'typical_offer' }),publicFact({ claim_kind:'historical_statistic', statistic_denominator:'DEMO_graduates' }),publicFact({ fact_type:'date',value_kind:'text',value_text:'DEMO_只给日期',normalized_value:null,unit:null,unit_code:'ISO_DATE',date_resolution:date })] }) } })
    expect(wrapper.text()).toContain('最低要求'); expect(wrapper.text()).toContain('典型录取条件'); expect(wrapper.text()).toContain('历史统计'); expect(wrapper.text()).toContain('分母 DEMO_graduates')
    expect(wrapper.text()).toContain('时间 未知'); expect(wrapper.text()).toContain('官方 UTC 未核定'); expect(wrapper.text()).not.toContain('23:59')
    expect(wrapper.find('img').exists()).toBe(false); expect(wrapper.text()).toContain('<img')
  })

  it.each(['eligible','ineligible','conditional','unknown'] as const)('shows %s and three other dimensions as unknown', status => {
    wrapper = mount(AssessmentResult,{ props:{ result:assessment(status) } })
    expect(wrapper.classes()).toContain(status)
    expect(wrapper.text()).toContain('DEMO'); expect(wrapper.text()).toContain('不代表录取')
    expect(wrapper.findAll('.dimensions section')).toHaveLength(3)
    expect(wrapper.text()).toContain('历史竞争'); expect(wrapper.text()).toContain('偏好匹配'); expect(wrapper.text()).toContain('数据质量')
    if (status === 'conditional') { expect(wrapper.text()).toContain('数学 · 实得记录'); expect(wrapper.text()).toContain('没有官方截止日期或时刻') }
    else expect(wrapper.find('.obligations').exists()).toBe(false)
  })

  it.each(['withdrawn','replaced','needs_review','unavailable'] as const)('marks %s eligible history as invalid instead of current green qualification', validity => {
    wrapper = mount(AssessmentResult,{ props:{ result:assessment('eligible',{current_validity:validity}), historical:true } })
    expect(wrapper.classes()).toContain('historical-invalid'); expect(wrapper.classes()).not.toContain('eligible')
    expect(find('assessment-status').text()).toMatch(/^原评估：/); expect(wrapper.text()).toContain('不能当作当前资格')
  })
})

describe('confirmed private interaction and immediate invalidation', () => {
  it('requires explicit confirmation, clears it on stage/scope changes, and binds the returned assessment', async () => {
    const { privateApi } = view(); await flushPromises(); await ready()
    expect(find('catalog-evaluate').attributes('disabled')).toBeDefined()
    await find('catalog-confirm').setValue(true); expect(find('catalog-evaluate').attributes('disabled')).toBeUndefined()
    await find('catalog-stage').setValue('enrollment'); expect(find('catalog-confirm').element).toHaveProperty('checked',false)
    await find('catalog-confirm').setValue(true); await find('catalog-scope-intake').setValue('none'); expect(find('catalog-confirm').element).toHaveProperty('checked',false)
    await find('catalog-confirm').setValue(true); await find('catalog-evaluate').trigger('click')
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="assessment-current-result"]').exists()).toBe(true))
    expect(privateApi.evaluate).toHaveBeenCalledWith(expect.objectContaining({ confirmed:true,stage:'enrollment',intake:null,profile_id:version().profile_id,profile_version_id:version().version_id,release_id:uid(4),target:expect.objectContaining({offering_id:uid(5),offering_version:1}) }),expect.any(AbortSignal))
    expect(find('catalog-confirm').element).toHaveProperty('checked',false)
  })

  it('blocks an entry-year mismatch without changing the confirmed profile', async () => {
    const wrongYear = version({ profile:{...version().profile,entry_year:2028} })
    view({profile:wrongYear}); await flushPromises(); await ready(); await find('catalog-confirm').setValue(true)
    expect(find('catalog-evaluate').attributes('disabled')).toBeDefined(); expect(wrapper!.text()).toContain('入学年与目标不一致')
  })

  it.each(['actor','core','profile'] as const)('does not restore a late successful evaluation after %s changes', async change => {
    const pending = deferred<ReturnType<typeof assessment>>(), privateApi = eligibilityApi({ evaluate:vi.fn(() => pending.promise) })
    view({},catalogApi(),privateApi); await flushPromises(); await ready(); await find('catalog-confirm').setValue(true); await find('catalog-evaluate').trigger('click')
    await vi.waitFor(() => expect(privateApi.evaluate).toHaveBeenCalledOnce())
    await wrapper!.setProps(change === 'actor' ? {actor:otherActor} : change === 'core' ? {coreAllowed:false} : {profile:null,profileEpoch:1})
    expect(wrapper!.find('[data-testid="assessment-current-result"]').exists()).toBe(false)
    pending.resolve(assessment()); await flushPromises()
    expect(wrapper!.find('[data-testid="assessment-current-result"]').exists()).toBe(false)
    expect(wrapper!.find('[data-testid="assessment-history-result"]').exists()).toBe(false)
  })

  it.each([401,403,404,503])('shows %s without any private success or automatic retry', async status => {
    const privateApi = eligibilityApi({ evaluate:vi.fn().mockRejectedValue(new EligibilityError(status)) })
    view({},catalogApi(),privateApi); await flushPromises(); await ready(); await find('catalog-confirm').setValue(true); await find('catalog-evaluate').trigger('click')
    await vi.waitFor(() => expect(find('assessment-message').attributes('role')).toBe('alert'))
    expect(wrapper!.find('[data-testid="assessment-current-result"]').exists()).toBe(false); expect(privateApi.evaluate).toHaveBeenCalledOnce()
    expect(wrapper!.emitted('sessionExpired')?.length ?? 0).toBe(status === 401 ? 1 : 0)
  })

  it('requires a separate replay confirmation and clears history when its ID changes', async () => {
    const { privateApi } = view(); await flushPromises(); await find('catalog-context-refresh').trigger('click'); await flushPromises()
    await find('assessment-history-id').setValue(uid(12)); await find('assessment-history-read').trigger('click')
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="assessment-history-result"]').exists()).toBe(true))
    expect(find('assessment-replay').attributes('disabled')).toBeDefined()
    await find('assessment-replay-confirm').setValue(true); await find('assessment-replay').trigger('click')
    await vi.waitFor(() => expect(privateApi.replay).toHaveBeenCalledWith(uid(12),{confirmed:true},expect.any(AbortSignal)))
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="assessment-history-result"]').exists()).toBe(true))
    await find('assessment-history-id').setValue(uid(99))
    expect(wrapper!.find('[data-testid="assessment-history-result"]').exists()).toBe(false)
  })
})

describe('public evidence dialog and profile handoff', () => {
  it('selects the exact card before evidence and renders text/hash/locator without external markup', async () => {
    const { api } = view({actor:null,coreAllowed:false,profile:null}); await flushPromises(); await query()
    await find(`catalog-evidence-${uid(6)}`).trigger('click')
    await vi.waitFor(() => expect(find('public-evidence-quote').text()).toContain('DEMO_原文'))
    expect(api.evidence).toHaveBeenCalledWith(uid(6),uid(4),expect.any(AbortSignal))
    expect(find('public-evidence-dialog').element).toHaveProperty('open',true)
    expect(find('public-evidence-dialog').find('img').exists()).toBe(false)
    expect(find('public-evidence-dialog').text()).toContain('[0,'); expect(find('public-evidence-dialog').text()).toContain('claimed_official')
    expect(find('public-evidence-dialog').text()).toContain('不是真实官方招生依据')
    await find('public-evidence-dialog').trigger('cancel'); await flushPromises()
    expect(find('public-evidence-dialog').element).toHaveProperty('open',false)
  })

  it('opens a current assessment obligation only through its exact release and target', async () => {
    const api = catalogApi(), privateApi = eligibilityApi({ evaluate:vi.fn(async () => assessment('conditional')) })
    view({},api,privateApi); await flushPromises(); await ready(); await find('catalog-confirm').setValue(true); await find('catalog-evaluate').trigger('click')
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="assessment-current-result"]').exists()).toBe(true))
    await find(`assessment-evidence-${uid(6)}`).trigger('click')
    await vi.waitFor(() => expect(api.evidence).toHaveBeenCalledWith(uid(6),uid(4),expect.any(AbortSignal)))
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="public-evidence-quote"]').exists()).toBe(true))
  })

  it.each(['release','scope'] as const)('does not use a new selected target to read historical evidence with a different %s binding', async wrong => {
    const old = assessment('conditional',wrong === 'release' ? {release_id:uid(98)} : {target:{...assessment().target,scope_sha256:'9'.repeat(64)}})
    const api = catalogApi(), privateApi = eligibilityApi({get:vi.fn(async () => old)})
    view({},api,privateApi); await flushPromises(); await ready(); await find('assessment-history-id').setValue(uid(12)); await find('assessment-history-read').trigger('click')
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="assessment-history-result"]').exists()).toBe(true))
    await find(`assessment-evidence-${uid(6)}`).trigger('click')
    await vi.waitFor(() => expect(find('public-evidence-dialog').find('[role="alert"]').exists()).toBe(true))
    expect(api.evidence).not.toHaveBeenCalled(); expect(wrapper!.find('[data-testid="public-evidence-quote"]').exists()).toBe(false)
  })

  it('restores connected trigger focus on close and ignores opening after disposal', async () => {
    const button = document.createElement('button'); document.body.append(button); button.focus()
    wrapper = mount(PublicEvidenceDialog,{attachTo:document.body,props:{evidence:null,loading:false,message:''}})
    await wrapper.setProps({loading:true}); await flushPromises(); expect(find('public-evidence-dialog').element).toHaveProperty('open',true)
    await wrapper.setProps({loading:false,evidence:publicEvidence()}); await flushPromises()
    await wrapper.setProps({evidence:null}); await flushPromises(); expect(document.activeElement).toBe(button)
  })

  it('hands off only a read-only current confirmed version and clears synchronously at edit/read/access change', async () => {
    const pending = deferred<ReturnType<typeof version>>(), api = profileApi({ current:vi.fn().mockResolvedValueOnce(version()).mockImplementationOnce(() => pending.promise) })
    wrapper = mount(ProfileView,{props:{actor,coreAllowed:true,api}}); await flushPromises()
    await find('profile-list').trigger('click'); await flushPromises(); await find(`profile-load-${rootId}`).trigger('click'); await flushPromises()
    expect(wrapper.emitted('profileSelected')?.at(-1)?.[0]).toMatchObject({version_id:version().version_id})
    await find('profile-edit').trigger('click'); expect(wrapper.emitted('profileSelected')?.at(-1)?.[0]).toBeNull()
    await find('profile-discard-draft').trigger('click'); expect(wrapper.emitted('profileSelected')?.at(-1)?.[0]).toBeNull()
    await find(`profile-load-${rootId}`).trigger('click'); expect(wrapper.emitted('profileSelected')?.at(-1)?.[0]).toBeNull()
    await wrapper.setProps({coreAllowed:false}); pending.resolve(version()); await flushPromises()
    expect(wrapper.emitted('profileSelected')?.at(-1)?.[0]).toBeNull()
  })
})
