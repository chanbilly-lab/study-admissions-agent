// Actual T33 Edge -> transparent loopback -> ASGI -> synthetic PostgreSQL.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { randomUUID } from 'node:crypto'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
let input = ''
for await (const chunk of process.stdin) {
  input += chunk
  if (Buffer.byteLength(input) > 16384) throw new Error('T33 fixture exceeds its bound')
}
const fixture = JSON.parse(input)
assert.match(fixture.origin, /^http:\/\/127\.0\.0\.1:[0-9]+$/)
const cache = resolve(root, '.cache/t33-ui', randomUUID())
await mkdir(cache, { recursive: true })
const checks = [], pageErrors = [], blockedRequests = [], events = [], publicRequests = []
const ids = { plan_id: null, state_version: null, completed_keys: [], other_plan_id: null }
let browser, page, report, step = 'initial'

function safeError(error) {
  let value = String(error?.message ?? error)
  for (const secret of [fixture.owner_cookie, fixture.other_cookie]) value = value.split(secret).join('[redacted]')
  return value.replace(/https?:\/\/[^\s"'<>]+/g, '[URL]').slice(0, 2500)
}
async function bounded(label, work, milliseconds = 45000) {
  let timer
  try { return await Promise.race([work(), new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error('T33 timeout: ' + label)), milliseconds)
  })]) } finally { clearTimeout(timer) }
}
async function checkpoint(value) {
  step = value
  await writeFile(resolve(cache, 'progress.json'), JSON.stringify({ step, checks, events }))
}
function passed(message) { checks.push(message) }
async function setupPage(cookie = fixture.owner_cookie) {
  const context = await bounded('new context', () => browser.newContext({ viewport: { width: 1280, height: 900 } }))
  await context.addCookies([{ name: '__Host-admissions-session', value: cookie,
    domain: '127.0.0.1', path: '/', secure: true, httpOnly: true, sameSite: 'Lax' }])
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url())
    if (url.origin !== fixture.origin) {
      blockedRequests.push(url.origin + url.pathname)
      await route.abort('blockedbyclient'); return
    }
    const headers = await bounded('request headers', () => request.allHeaders(), 10000)
    assert.ok(!headers.authorization)
    if (url.pathname.startsWith('/public/v2/')) {
      publicRequests.push({ path: url.pathname, cookie: Boolean(headers.cookie) })
      assert.ok(!headers.cookie, 'Public requests must omit private cookies')
    }
    await route.continue()
  })
  const result = await context.newPage()
  result.setDefaultTimeout(30000)
  result.on('pageerror', error => pageErrors.push(safeError(error)))
  result.on('response', response => {
    const path = new URL(response.url()).pathname
    if (path.startsWith('/api/v2/') || path.startsWith('/public/v2/')) {
      events.push({ path, method: response.request().method(), status: response.status() })
      if (events.length > 100) events.shift()
    }
  })
  await bounded('open page', () => result.goto(fixture.origin))
  return result
}
async function action(selector, path, method = 'GET', keyboard = false) {
  await checkpoint('UI ' + method + ' ' + path)
  const pending = page.waitForResponse(response => new URL(response.url()).pathname === path
    && response.request().method() === method)
  // A missing selector may fail before the response wait is awaited. Keep its
  // later timeout handled so the original safe failure report is still saved.
  void pending.catch(() => {})
  const element = typeof selector === 'string' ? page.getByTestId(selector) : selector
  await bounded('UI action ' + path, async () => {
    if (keyboard) { await element.focus(); await page.keyboard.press('Enter') }
    else await element.click()
  })
  const response = await bounded('UI response ' + path, () => pending)
  const headers = await bounded('response headers', () => response.allHeaders(), 10000)
  assert.equal(headers['cache-control'], 'no-store')
  assert.match(headers['x-request-id'], /^[0-9a-f]{32}$/)
  const requestHeaders = await response.request().allHeaders()
  if (method !== 'GET') {
    assert.equal(requestHeaders.origin, fixture.origin)
    assert.ok(requestHeaders['x-csrf-token'])
    if (path.endsWith('/confirm')) assert.match(requestHeaders['idempotency-key'], /^[A-Za-z0-9._:-]{1,128}$/)
    else assert.ok(!requestHeaders['idempotency-key'], 'Only plan confirmation accepts the key')
  }
  // The application discards non-200 bodies. Check real headers/status/DOM,
  // rather than waiting for an aborted body the UI intentionally never reads.
  const envelope = response.status() === 200
    ? await bounded('successful JSON', () => response.json(), 10000) : null
  if (envelope) {
    assert.equal(envelope.meta.request_id, headers['x-request-id'])
    if (path.startsWith('/api/')) {
      assert.equal(envelope.meta.data_mode, 'verified')
      assert.equal(envelope.meta.model_mode, 'disabled')
    }
  }
  await checkpoint('UI checked ' + method + ' ' + path + ' ' + response.status())
  return { status: response.status(), data: envelope?.data, meta: envelope?.meta,
    body: method === 'GET' ? null : response.request().postDataJSON(), key: requestHeaders['idempotency-key'] }
}
async function api(path, { method = 'GET', body, key, csrf = true } = {}) {
  await checkpoint('direct ' + method + ' ' + path)
  return bounded('direct API ' + path, () => page.evaluate(async ({ path, method, body, key, csrf }) => {
    const headers = { Accept: 'application/json' }
    if (method !== 'GET' && csrf) {
      const proof = await fetch('/api/v2/auth/csrf', { credentials: 'same-origin', cache: 'no-store' })
      if (proof.status !== 200) return { status: proof.status }
      headers['X-CSRF-Token'] = (await proof.json()).data.csrf_token
    }
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    if (key) headers['Idempotency-Key'] = key
    const response = await fetch('/api/v2/' + path, { method, credentials: 'same-origin', cache: 'no-store',
      redirect: 'error', headers, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) })
    return { status: response.status, data: response.status === 200 ? (await response.json()).data : null }
  }, { path, method, body, key, csrf }))
}
async function control(actionName) {
  return bounded('delivery control', () => page.evaluate(async actionName => {
    const response = await fetch('/__t33/control', actionName ? { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: actionName }) } : {})
    return response.json()
  }, actionName), 10000)
}
async function waitControl(key) {
  return bounded('wait actual delivery ' + key, async () => {
    while (true) {
      const state = await control()
      if (state[key]) return state
      await new Promise(resolve => setTimeout(resolve, 75))
    }
  })
}
async function openPlans() {
  if (await page.getByTestId('plans-workspace').count() === 0) await page.getByTestId('plans-toggle').click()
  await page.getByTestId('plans-workspace').waitFor()
  const proof = await action('plan-context-refresh', '/api/v2/plans/context')
  assert.equal(proof.status, 200); assert.equal(proof.data.can_read, true)
}
async function chooseProfile() {
  const listed = await action('profile-list', '/api/v2/profiles')
  assert.equal(listed.status, 200); assert.equal(listed.data.items.length, 1)
  const id = listed.data.items[0].profile_id
  const loaded = await action('profile-load-' + id, '/api/v2/profiles/' + id)
  assert.equal(loaded.status, 200)
  return loaded.data
}
async function createFromActualEvaluation(expected = 'conditional', historical = false) {
  const profile = await chooseProfile()
  if (await page.getByTestId('catalog-workspace').count() === 0) await page.getByTestId('catalog-toggle').click()
  await page.getByTestId('catalog-year').fill(String(fixture.year))
  await page.getByTestId('catalog-country').selectOption('CN')
  await page.getByTestId('catalog-province').selectOption('known:Zhejiang')
  const found = await action('catalog-search', '/public/v2/offerings')
  assert.equal(found.status, 200)
  const offering = found.data.items.find(item => item.facts.some(fact => fact.field_key === 'DEMO_T28_RULE')
    === (expected === 'conditional'))
  assert.ok(offering)
  await page.getByTestId('catalog-select-' + offering.id + '-' + offering.version).click()
  await action('catalog-context-refresh', '/api/v2/eligibility/context')
  await page.getByTestId('catalog-confirm').check()
  const evaluated = await action('catalog-evaluate', '/api/v2/eligibility/evaluations', 'POST')
  assert.equal(evaluated.status, 200); assert.equal(evaluated.data.eligibility.status, expected)
  assert.equal(evaluated.data.profile_version_id, profile.version_id)
  if (historical) {
    await page.getByTestId('assessment-history-id').fill(evaluated.data.assessment_id)
    const read = await action('assessment-history-read', '/api/v2/eligibility/evaluations/' + evaluated.data.assessment_id)
    assert.equal(read.status, 200); assert.equal(read.data.profile_version_id, profile.version_id)
    await page.getByTestId('plan-history-assessment-add').click()
  } else await page.getByTestId('plan-assessment-add').click()
  await openPlans()
  await page.getByTestId('plan-assessment-select-' + evaluated.data.assessment_id).check()
  assert.equal(await page.getByTestId('plan-create').isDisabled(), true)
  await page.getByTestId('plan-create-confirmation').check()
  const created = await action('plan-create', '/api/v2/plans', 'POST')
  assert.equal(created.status, 200)
  assert.deepEqual(created.body.assessment_ids, [evaluated.data.assessment_id])
  assert.equal(created.body.confirmed, true)
  for (const name of ['owner', 'clock', 'eligibility', 'source', 'profile', 'schedule']) assert.ok(!Object.hasOwn(created.body, name))
  assert.equal(created.meta.profile_version_id, profile.version_id)
  assert.equal(created.meta.profile_mode, 'synthetic')
  return { execution: created.data, profile }
}
function futureUtc(minutes) {
  // These are new, explicitly selected test slots. Existing wire timestamps
  // are never converted or reserialized by this test.
  const value = new Date(Date.parse(fixture.server_now) + minutes * 60000).toISOString()
  return value.replace(/\.\d{3}Z$/, '.123456Z')
}
async function fillSchedule() {
  if (await page.getByTestId('plan-schedule-enabled').count()) await page.getByTestId('plan-schedule-enabled').check()
  await page.getByTestId('plan-horizon-start').fill(futureUtc(5))
  await page.getByTestId('plan-horizon-end').fill(futureUtc(65))
  await page.getByTestId('plan-timezone').fill('Asia/Shanghai')
  await page.getByTestId('plan-weekly-hours').fill('0')
  await page.getByTestId('plan-slot-add').click()
  const start = page.locator('[data-testid^="plan-slot-start-"]').first()
  const end = page.locator('[data-testid^="plan-slot-end-"]').first()
  await start.fill(futureUtc(5)); await end.fill(futureUtc(65))
  await page.getByTestId('plan-availability-confirmation').check()
  await page.getByTestId('plan-rest-excluded').check()
}
async function saveWorkspace(planId) {
  // Every modified configuration is an explicit new availability declaration.
  await page.getByTestId('plan-availability-confirmation').check()
  await page.getByTestId('plan-rest-excluded').check()
  return action('plan-workspace-save', '/api/v2/plans/' + planId + '/workspace', 'POST')
}
async function armPlan(planId) {
  await action('plan-list', '/api/v2/plans')
  await control('arm')
  await bounded('hold actual plan GET', () => page.getByTestId('plan-load-' + planId).click())
  assert.equal((await waitControl('blocked')).response_status, 200)
}
async function switchActor(cookie, userId) {
  await page.context().addCookies([{ name: '__Host-admissions-session', value: cookie,
    domain: '127.0.0.1', path: '/', secure: true, httpOnly: true, sameSite: 'Lax' }])
  await action(page.getByRole('button', { name: '重新检查会话', exact: true }), '/api/v2/auth/session')
  await page.getByTestId('actor-id').filter({ hasText: userId }).waitFor()
}

try {
  const module = process.env.T33_PLAYWRIGHT_MODULE || resolve(process.env.USERPROFILE || '',
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs')
  const { chromium } = await import(pathToFileURL(module).href)
  browser = await bounded('launch Edge', () => chromium.launch({ channel: 'msedge', headless: true }))
  page = await setupPage()
  await page.getByTestId('actor-id').filter({ hasText: fixture.user_id }).waitFor()
  let { execution } = await createFromActualEvaluation('conditional', true)
  const planId = execution.plan_id
  ids.plan_id = planId
  assert.equal(execution.state, 'draft'); assert.equal(execution.state_version, 1)
  assert.equal(execution.proposal.schedule, null)
  const tasks = execution.proposal.effective_draft.tasks
  assert.ok(tasks.length >= 2 && tasks.some(task => task.dependency_keys.length))
  assert.ok(tasks.every(task => task.estimated_hours === null))
  passed('Actual Catalog evaluation and same-profile explicit history join a target and create a plan through current Cookie/CSRF, with no inferred estimates')

  await page.getByTestId('plan-estimate-' + tasks[0].task_key).fill('0')
  await fillSchedule()
  let saved = await saveWorkspace(planId)
  assert.equal(saved.status, 200)
  assert.equal(saved.body.estimate_overrides.find(item => item.task_key === tasks[0].task_key).estimated_hours, '0')
  assert.ok(saved.body.estimate_overrides.some(item => item.estimated_hours === null))
  assert.notEqual(saved.data.proposal.schedule.status, 'ready')
  assert.equal(await page.getByTestId('plan-submit-confirm').isDisabled(), true)
  passed('Explicit zero and missing estimates remain distinct; unavailable capacity cannot be silently confirmed')

  for (const task of tasks.slice(1)) await page.getByTestId('plan-estimate-' + task.task_key).fill('0.1')
  saved = await saveWorkspace(planId)
  assert.equal(saved.status, 200); assert.notEqual(saved.data.proposal.schedule.status, 'ready')
  assert.equal(saved.data.proposal.schedule.weekly_hours, '0')
  passed('Zero weekly capacity produces the actual server conflict instead of compressing rest or changing hours')
  await page.getByTestId('plan-weekly-hours').fill('1')
  saved = await saveWorkspace(planId)
  assert.equal(saved.status, 200); assert.equal(saved.data.proposal.schedule.status, 'ready')
  assert.equal(saved.body.schedule.slots[0].start_at, futureUtc(5))
  assert.equal(saved.data.proposal.schedule_configuration.slots[0].start_at, futureUtc(5))
  assert.equal(saved.data.proposal.schedule.constraints_complete, false)
  passed('Explicit future UTC slots retain six fractional digits and IANA display while official deadline completeness remains false')

  const external = await api('plans/' + planId + '/workspace', { method: 'POST',
    body: { ...saved.body, expected_version: saved.data.state_version } })
  assert.equal(external.status, 200)
  await page.getByTestId('plan-estimate-' + tasks[1].task_key).fill('0.2')
  const stale = await saveWorkspace(planId)
  assert.equal(stale.status, 409)
  await page.getByTestId('plan-conflict').waitFor()
  await page.getByTestId('plan-conflict').getByText('核对未提交参数（只读，不能执行）', { exact: true }).click()
  assert.equal(await page.getByTestId('plan-estimate-' + tasks[1].task_key).inputValue(), '0.2')
  assert.equal(await page.getByTestId('plan-confirm').count(), 0)
  assert.equal(await page.getByTestId('plan-ack-unknown').count(), 0)
  await bounded('CAS screenshot', () => page.screenshot({ path: resolve(cache, 'plans-cas-conflict.png'),
    fullPage: true, timeout: 15000 }), 20000)
  await bounded('focused CAS screenshot', () => page.getByTestId('plan-conflict').screenshot({
    path: resolve(cache, 'plans-cas-conflict-focused.png'), timeout: 15000 }), 20000)
  const writesAfterConflict = events.filter(event => event.path.endsWith('/workspace') && event.method === 'POST').length
  await new Promise(resolve => setTimeout(resolve, 250))
  assert.equal(events.filter(event => event.path.endsWith('/workspace') && event.method === 'POST').length, writesAfterConflict)
  const refreshed = await action('plan-reload-current', '/api/v2/plans/' + planId)
  assert.equal(refreshed.status, 200); assert.equal(refreshed.data.state_version, external.data.state_version)
  assert.equal(await page.getByTestId('plan-estimate-' + tasks[1].task_key).inputValue(), '0.2')
  saved = await saveWorkspace(planId)
  assert.equal(saved.status, 200); assert.equal(saved.data.proposal.schedule.status, 'ready')
  passed('A real external CAS write makes the stale UI save fail; local parameters survive and explicit reload supplies the new version without auto retry')

  assert.equal(await page.getByTestId('plan-submit-confirm').isDisabled(), true)
  await page.getByTestId('plan-confirm').check()
  assert.equal(await page.getByTestId('plan-submit-confirm').isDisabled(), true)
  await page.getByTestId('plan-ack-unknown').check()
  const confirmed = await action('plan-submit-confirm', '/api/v2/plans/' + planId + '/confirm', 'POST', true)
  assert.equal(confirmed.status, 200); assert.equal(confirmed.data.replayed, false)
  execution = confirmed.data.execution
  assert.equal(execution.state, 'confirmed'); assert.equal(execution.proposal.effective_draft.confirmed, false)
  assert.equal(confirmed.body.expected_draft_sha256, saved.data.proposal.effective_draft.draft_sha256)
  assert.equal(confirmed.body.expected_schedule_sha256, saved.data.proposal.schedule.schedule_sha256)
  assert.equal(confirmed.body.acknowledge_unverified_deadlines, true)
  assert.equal(await page.getByTestId('plan-workspace-save').count(), 0)
  passed('Separate final acknowledgement confirms personal preparation capacity; the source draft and unknown school deadlines are preserved')

  const child = tasks.find(task => task.dependency_keys.length)
  assert.equal((await api('plans/' + planId + '/tasks/' + child.task_key + '/complete', { method: 'POST',
    body: { expected_version: execution.state_version, confirmed: true } })).status, 409)
  assert.equal((await api('plans/' + planId + '/tasks/' + tasks[0].task_key + '/complete', { method: 'POST',
    body: { expected_version: execution.state_version, confirmed: true }, csrf: false })).status, 403)
  passed('Actual server dependency and CSRF guards reject premature completion without durable progress')
  let firstCompletion = null
  const pendingTasks = [...tasks], done = new Set()
  while (pendingTasks.length) {
    const index = pendingTasks.findIndex(task => task.dependency_keys.every(key => done.has(key)))
    assert.ok(index >= 0)
    const [task] = pendingTasks.splice(index, 1)
    await page.getByTestId('plan-task-confirm-' + task.task_key).check()
    const finished = await action('plan-task-complete-' + task.task_key,
      '/api/v2/plans/' + planId + '/tasks/' + task.task_key + '/complete', 'POST')
    assert.equal(finished.status, 200); assert.equal(finished.data.replayed, false)
    assert.equal(finished.data.execution.completed_tasks.find(item => item.task_key === task.task_key).source, 'student_declared')
    if (!firstCompletion) firstCompletion = { task_key: task.task_key, body: finished.body }
    execution = finished.data.execution; done.add(task.task_key)
  }
  ids.completed_keys = [...done]; ids.state_version = execution.state_version
  const repeatComplete = await api('plans/' + planId + '/tasks/' + firstCompletion.task_key + '/complete',
    { method: 'POST', body: firstCompletion.body })
  assert.equal(repeatComplete.status, 200); assert.equal(repeatComplete.data.replayed, true)
  assert.equal(repeatComplete.data.execution.state_version, execution.state_version)
  const repeatConfirm = await api('plans/' + planId + '/confirm', { method: 'POST', body: confirmed.body, key: confirmed.key })
  assert.equal(repeatConfirm.status, 200); assert.equal(repeatConfirm.data.replayed, true)
  assert.equal(repeatConfirm.data.confirmed_state_version, confirmed.data.confirmed_state_version)
  assert.equal(repeatConfirm.data.execution.completed_tasks.length, tasks.length)
  passed('Every task, including the zero milestone, requires explicit completion; exact original completion and confirmation retries return current progress once')

  await page.getByTestId('plan-history-version').fill('1')
  const history = await action('plan-history-load', '/api/v2/plans/' + planId + '/versions/1')
  assert.equal(history.status, 200); assert.equal(history.data.state_version, 1)
  assert.equal(history.data.confirmation, null); assert.deepEqual(history.data.completed_tasks, [])
  assert.equal(await page.getByTestId('plan-history-result').locator('[data-testid^="plan-task-complete-"]').count(), 0)
  await page.getByTestId('plan-current-state-version').filter({ hasText: String(execution.state_version) }).waitFor()
  passed('Read-only historical state 1 retains its original proposal and cannot replace current confirmed progress or supply write CAS')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByTestId('plans-workspace').scrollIntoViewIfNeeded()
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await bounded('mobile screenshot', () => page.screenshot({ path: resolve(cache, 'plans-mobile.png'), fullPage: true, timeout: 15000 }), 20000)
  await bounded('focused mobile plan screenshot', () => page.getByTestId('plan-current').screenshot({
    path: resolve(cache, 'plans-mobile-current.png'), timeout: 15000 }), 20000)
  await page.setViewportSize({ width: 1280, height: 900 })
  await action('plan-list', '/api/v2/plans', 'GET', true)
  await bounded('desktop screenshot', () => page.screenshot({ path: resolve(cache, 'plans-desktop.png'), fullPage: true, timeout: 15000 }), 20000)
  await bounded('focused desktop plan screenshot', () => page.getByTestId('plan-current').screenshot({
    path: resolve(cache, 'plans-desktop-current.png'), timeout: 15000 }), 20000)
  passed('Actual keyboard confirmation/list and 390px mobile plan, dependency and progress displays have no horizontal overflow')

  await armPlan(planId)
  await switchActor(fixture.other_cookie, fixture.other_user_id)
  await control('release'); await waitControl('completed')
  assert.equal(await page.getByTestId('plan-current').count(), 0)
  assert.equal(await page.getByTestId('plan-history-result').count(), 0)
  assert.equal((await api('plans/' + planId)).status, 404)
  passed('An actual A plan GET200 held at delivery cannot restore private plan/history after switching to B; cross-owner server read is denied')

  const other = await createFromActualEvaluation('unknown')
  ids.other_plan_id = other.execution.plan_id
  assert.ok(other.execution.proposal.effective_draft.tasks.every(task => task.action_code === 'VERIFY_UNKNOWN'))
  passed('An actually evaluated facts-only unknown target creates only verification work, without invented preparation or school rules')
  await armPlan(other.execution.plan_id)
  const admission = await api('me/admission')
  const withdrew = await action('withdraw-core', '/api/v2/me/consents/' + admission.data.consent_id, 'DELETE')
  assert.equal(withdrew.status, 200)
  await control('release'); await waitControl('completed')
  assert.equal(await page.getByTestId('plan-current').count(), 0)
  assert.equal((await api('plans/' + other.execution.plan_id)).status, 403)
  passed('Real core-purpose withdrawal clears private plan state immediately and an already-successful GET cannot revive it')

  await switchActor(fixture.owner_cookie, fixture.user_id)
  await openPlans()
  const listed = await action('plan-list', '/api/v2/plans')
  assert.equal(listed.status, 200)
  await action('plan-load-' + planId, '/api/v2/plans/' + planId)
  assert.equal(await page.getByTestId('plan-current').count(), 1)
  passed('An owner can explicitly read an existing plan before reselecting a profile; writes still require a current confirmed profile')
  await armPlan(planId)
  const logout = await action(page.getByRole('button', { name: '退出当前应用', exact: true }), '/api/v2/auth/logout', 'POST')
  assert.equal(logout.status, 200)
  await control('release'); await waitControl('completed')
  assert.equal(await page.getByTestId('plan-current').count(), 0)
  assert.equal(await page.getByTestId('plan-history-result').count(), 0)
  assert.equal((await api('auth/session')).status, 401)
  assert.deepEqual(await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage) })),
    { local: [], session: [] })
  await bounded('cleared screenshot', () => page.screenshot({ path: resolve(cache, 'plans-cleared.png'), fullPage: false, timeout: 15000 }), 20000)
  passed('Actual logout revokes the owner session, rejects late private responses and leaves no private browser persistence')
  assert.ok(publicRequests.length >= 2); assert.ok(publicRequests.every(request => !request.cookie))
  assert.deepEqual(pageErrors, []); assert.deepEqual(blockedRequests, [])
  report = { status: 'passed', browser: await browser.version(), checks, ids, page_errors: pageErrors,
    blocked_requests: blockedRequests, public_requests: publicRequests, network_events: events, cache_directory: cache,
    not_executed: ['Formal rule verification or real users', 'Production proxy/TLS/deployment', 'Official deadline completeness'] }
} catch (error) {
  await checkpoint('failure after ' + step)
  report = { status: 'failed', checks, ids, step, error: safeError(error), page_errors: pageErrors,
    blocked_requests: blockedRequests, network_events: events, cache_directory: cache }
  if (page) await bounded('failure screenshot', () => page.screenshot({ path: resolve(cache, 'failure.png'), fullPage: true, timeout: 10000 }), 12000).catch(() => {})
} finally {
  if (page) await bounded('release held GET', () => control('release'), 12000).catch(() => {})
  if (browser) await bounded('close browser', () => browser.close(), 15000).catch(() => {})
}
await writeFile(resolve(cache, 'result.json'), JSON.stringify(report, null, 2))
process.stdout.write(JSON.stringify(report) + '\n')
if (report.status !== 'passed') process.exitCode = 1
