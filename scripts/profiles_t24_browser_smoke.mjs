// Actual T24 UI -> ASGI -> PostgreSQL. No profile/admission API mocking.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { randomUUID } from 'node:crypto'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
let input = ''
for await (const chunk of process.stdin) {
  input += chunk
  if (Buffer.byteLength(input) > 16384) throw new Error('T24 synthetic fixture is too large')
}
const fixture = JSON.parse(input)
assert.match(fixture.origin, /^http:\/\/127\.0\.0\.1:[0-9]+$/)
const cache = resolve(root, '.cache/t24-ui', randomUUID())
await mkdir(cache, { recursive: true })
const checks = [], pageErrors = [], blockedRequests = [], writes = [], events = []
const ids = { profile_id: null, version_ids: [], post_withdraw_profile_id: null, post_withdraw_version_id: null }
let browser, page, report, step = 'initial page'

function safeError(error) {
  return String(error?.message ?? error).split(fixture.cookie).join('[redacted fixture]')
    .replace(/https?:\/\/[^\s"'<>]+/g, '[URL]').slice(0, 3500)
}
async function bounded(label, work, milliseconds = 30000) {
  let timer
  try {
    return await Promise.race([work(), new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error('T24 harness timeout: ' + label)), milliseconds)
    })])
  } finally { clearTimeout(timer) }
}
function progress() { return JSON.stringify({ step, checks, events }) }
function passed(message) {
  checks.push(message)
  void writeFile(resolve(cache, 'progress.json'), progress()).catch(() => {})
}
async function checkpoint(value) {
  step = value
  await writeFile(resolve(cache, 'progress.json'), progress())
}
async function setupPage() {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  await context.addCookies([{ name: '__Host-admissions-session', value: fixture.cookie,
    domain: '127.0.0.1', path: '/', secure: true, httpOnly: true, sameSite: 'Lax' }])
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url())
    if (url.origin !== fixture.origin) {
      blockedRequests.push(url.origin + url.pathname)
      await route.abort('blockedbyclient')
      return
    }
    const headers = await bounded('request headers', () => request.allHeaders(), 10000)
    assert.ok(!headers.authorization, 'No Bearer token goes into the browser')
    if (request.method() === 'POST' && url.pathname.startsWith('/api/v2/profiles')) writes.push(url.pathname)
    await route.continue()
  })
  const result = await context.newPage()
  result.setDefaultTimeout(30000)
  result.on('pageerror', error => pageErrors.push(safeError(error)))
  result.on('response', response => {
    const pathname = new URL(response.url()).pathname
    if (pathname.startsWith('/api/v2/')) {
      events.push({ method: response.request().method(), path: pathname, status: response.status() })
      if (events.length > 30) events.shift()
      void writeFile(resolve(cache, 'progress.json'), progress()).catch(() => {})
    }
  })
  await result.goto(fixture.origin)
  return result
}
async function control(page, action) {
  return bounded('test control ' + (action ?? 'read'), () => page.evaluate(async action => {
    const response = await fetch('/__t24/control', action ? { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) } : {})
    return response.json()
  }, action), 10000)
}
async function waitControl(page, field) {
  return bounded('real HTTP delay ' + field, async () => {
    for (;;) {
      const current = await control(page)
      if (current[field] === true) return current
      await new Promise(resolve => setTimeout(resolve, 100))
    }
  }, 25000)
}
async function api(page, path, { method = 'GET', body } = {}) {
  await checkpoint('direct API start: ' + method + ' ' + path)
  const result = await bounded('direct API ' + method + ' ' + path, () => page.evaluate(async ({ path, method, body }) => {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 20000)
    try {
    const headers = { Accept: 'application/json' }
    if (method !== 'GET') {
      const csrf = await fetch('/api/v2/auth/csrf', { credentials: 'same-origin', cache: 'no-store', signal: controller.signal })
      if (csrf.status !== 200) return { status: csrf.status }
      headers['X-CSRF-Token'] = (await csrf.json()).data.csrf_token
    }
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    const response = await fetch('/api/v2/' + path, { method, credentials: 'same-origin', cache: 'no-store',
      headers, signal: controller.signal, ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
    return { status: response.status, body: await response.json() }
    } finally { clearTimeout(timer) }
  }, { path, method, body }), 25000)
  await checkpoint('direct API completed: ' + method + ' ' + path + ' status ' + result.status)
  return result
}
async function clickResponse(page, selector, path, method = 'POST', keyboard = false) {
  await checkpoint('UI action start: ' + method + ' ' + path)
  const pending = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v2/' + path
    && response.request().method() === method)
  const button = typeof selector === 'string' ? page.getByTestId(selector) : selector
  if (keyboard) { await bounded('focus UI action', () => button.focus()); await bounded('keyboard UI action', () => page.keyboard.press('Enter')) }
  else await bounded('click UI action ' + path, () => button.click())
  await checkpoint('UI action sent: ' + method + ' ' + path)
  const response = await bounded('UI response ' + path, () => pending)
  await checkpoint('UI response received: ' + method + ' ' + path + ' status ' + response.status())
  assert.equal(response.headers()['cache-control'], 'no-store')
  assert.equal(response.headers()['referrer-policy'], 'no-referrer')
  if (method !== 'GET') {
    assert.equal(response.request().headers().origin, fixture.origin)
    assert.match(response.request().headers()['x-csrf-token'], /^[A-Za-z0-9_-]{43}$/)
  }
  // The application deliberately rejects non-200 responses by status without
  // consuming their body. Chromium/Playwright may leave that body unfinished;
  // test the actual status, safe headers and resulting UI instead of waiting
  // for a body the application never reads. Success DTOs remain fully checked.
  assert.match(response.headers()['x-request-id'], /^[0-9a-f]{32}$/)
  const envelope = response.status() === 200
    ? await bounded('UI response JSON ' + path, () => response.json(), 10000) : undefined
  await checkpoint('UI response checked: ' + method + ' ' + path)
  if (envelope) assert.equal(envelope.meta?.request_id, response.headers()['x-request-id'])
  return { status: response.status(), data: envelope?.data, envelope,
    key: response.request().headers()['idempotency-key'],
    request: method === 'GET' ? undefined : response.request().postDataJSON() }
}
async function setControl(page, selector, value) {
  const input = page.getByTestId(selector)
  if (await input.evaluate(element => element.tagName) === 'SELECT') await input.selectOption(value)
  else await input.fill(value)
}
async function scope(page, field, status, value) {
  await setControl(page, 'profile-' + field + '-status', status)
  if (status === 'known') await setControl(page, 'profile-' + field + '-value', value)
}
async function addGrade(page, key) {
  if (await page.getByTestId('grade-' + key + '-achieved-status').count()) return
  await setControl(page, 'profile-grade-add-key', key)
  await page.getByTestId('profile-grade-add').click()
}
async function grade(page, key, kind, status, value, scale, unit) {
  await addGrade(page, key)
  const prefix = 'grade-' + key + '-' + kind + '-'
  await setControl(page, prefix + 'status', status)
  if (status === 'provided') {
    await page.getByTestId(prefix + 'value').fill(value)
    await page.getByTestId(prefix + 'scale').fill(scale)
    await setControl(page, prefix + 'unit', unit)
  }
}
function requireVersion(result, expectedNumber, append = false) {
  assert.equal(result.status, 200)
  const version = result.data.version
  assert.equal(version.version, expectedNumber)
  assert.equal(version.source, 'student_declared')
  assert.equal(version.is_synthetic, true)
  assert.equal(result.envelope.meta.profile_version_id, version.version_id)
  assert.equal(result.envelope.meta.profile_mode, 'synthetic')
  assert.equal(result.request.confirmed, true)
  for (const field of ['owner', 'owner_user_id', 'roles', 'is_synthetic', 'verified', 'consent_id']) {
    assert.equal(Object.hasOwn(result.request, field), false)
  }
  if (append) assert.equal(result.key, undefined)
  else assert.match(result.key, /^[A-Za-z0-9._:-]{1,128}$/)
  return version
}
async function save(page, expectedNumber, { append = true, keyboard = false } = {}) {
  await page.getByTestId('profile-confirmation').check()
  const path = append ? 'profiles/' + ids.profile_id + '/versions' : 'profiles'
  const result = await clickResponse(page, 'profile-save', path, 'POST', keyboard)
  const version = requireVersion(result, expectedNumber, append)
  if (!ids.profile_id) ids.profile_id = version.profile_id
  ids.version_ids.push(version.version_id)
  await page.getByTestId('profile-current-version-id').filter({ hasText: version.version_id }).waitFor()
  return version
}

try {
  const moduleName = process.env.T24_PLAYWRIGHT_MODULE ?? resolve(process.env.USERPROFILE ?? '',
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs')
  const playwright = await import(pathToFileURL(resolve(moduleName)).href)
  browser = await playwright.chromium.launch({ headless: true, channel: 'msedge' })
  page = await setupPage()
  await page.getByTestId('actor-id').filter({ hasText: fixture.user_id }).waitFor()
  await page.getByTestId('age-confirmation').waitFor()
  assert.equal(await page.getByTestId('profile-entry-year').count(), 0)
  await page.locator('input[name="age-band"][value="18_plus"]').check()
  assert.equal(await page.getByTestId('declare-age').isDisabled(), true)
  await page.getByTestId('age-confirmation').check()
  const declared = await clickResponse(page, 'declare-age', 'me/age-declarations')
  assert.equal(declared.status, 200); assert.equal(declared.data.age_assurance, 'declared')
  assert.equal(declared.data.core_consultation_allowed, false)
  await page.getByTestId('core-confirmation').check()
  const consent = await clickResponse(page, 'confirm-core', 'me/consents')
  assert.equal(consent.status, 200); assert.equal(consent.data.core_consultation_allowed, true)
  await page.getByTestId('profile-new').waitFor()
  await page.getByTestId('profile-new').click()
  await page.getByTestId('profile-entry-year').waitFor()
  passed('A registered synthetic student establishes adult declaration and core consent through actual UI writes before any profile inputs appear')

  assert.equal(await page.getByTestId('profile-entry-year').inputValue(), '')
  assert.equal(await page.getByTestId('profile-weekly-hours').inputValue(), '')
  assert.equal(await page.locator('[data-testid^="grade-"]').count(), 0)
  assert.equal(await page.getByTestId('profile-save').isDisabled(), true)
  await page.getByTestId('profile-entry-year').fill('2027')
  await scope(page, 'residence_region', 'known', 'HK')
  await scope(page, 'course_system', 'known', 'gaokao')
  await scope(page, 'applicant_category', 'known', 'cn_mainland')
  await scope(page, 'exam_province', 'known', 'Zhejiang')
  await scope(page, 'pathway', 'known', 'gaokao')
  passed('The empty form supplies no score, scale, hours or year defaults, and residence remains separate from course, identity and province')

  await grade(page, 'gaokao_total', 'achieved', 'provided', '625.25', '750', 'points')
  await grade(page, 'gaokao_total', 'predicted', 'provided', '700.000001', '750', 'points')
  await grade(page, 'math', 'achieved', 'provided', '0', '150', 'points')
  await page.getByTestId('profile-preferences-enabled').check()
  await page.getByTestId('profile-preferred-fields').fill('DEMO engineering')
  await page.getByTestId('profile-preferred-GB').check()
  await page.getByTestId('profile-budget-enabled').check()
  await page.getByTestId('profile-budget-amount').fill('25000')
  await setControl(page, 'profile-budget-currency', 'GBP')
  assert.equal(await page.getByTestId('profile-save').isDisabled(), true)
  const first = await save(page, 1, { append: false, keyboard: true })
  assert.equal(first.profile.assessments.gaokao_total.achieved.value, '625.25')
  assert.equal(first.profile.assessments.gaokao_total.predicted.value, '700.000001')
  assert.equal(first.profile.assessments.math.achieved.value, '0')
  assert.equal(first.profile.assessments.math.predicted.value, null)
  assert.deepEqual(first.profile.preferences.preferred_fields, ['DEMO engineering'])
  assert.deepEqual(first.profile.preferences.preferred_countries, ['GB'])
  assert.deepEqual(first.profile.preferences.budget, { amount: '25000', currency: 'GBP' })
  assert.equal(first.adaptation.status, 'unknown'); assert.equal(first.adaptation.reason, 'ADAPTER_NOT_IMPLEMENTED')
  passed('Keyboard-confirmed create persists exact achieved/predicted decimal strings and explicit zero with matching server version Meta and no eligibility claim')

  await page.getByTestId('profile-edit').click()
  await page.getByTestId('grade-gaokao_total-achieved-value').fill('')
  await setControl(page, 'grade-gaokao_total-achieved-status', 'missing')
  await page.getByTestId('profile-weekly-hours').fill('0')
  assert.equal(await page.getByTestId('profile-confirmation').isChecked(), false)
  assert.equal(await page.getByTestId('profile-save').isDisabled(), true)
  const second = await save(page, 2)
  assert.equal(second.profile.assessments.gaokao_total.achieved.value, null)
  assert.equal(second.profile.assessments.gaokao_total.predicted.value, '700.000001')
  assert.equal(second.profile.weekly_hours, '0')
  passed('Editing clears confirmation; clearing a previously nonzero achieved score persists null while predicted and weekly zero remain independent')

  await page.getByTestId('profile-history-version-id').fill(first.version_id)
  const history = await clickResponse(page, 'profile-history-load', 'profiles/' + first.profile_id + '/versions/' + first.version_id, 'GET')
  assert.equal(history.status, 200); assert.equal(history.data.version_id, first.version_id)
  assert.equal(history.data.profile.assessments.gaokao_total.achieved.value, '625.25')
  assert.equal(await page.getByTestId('profile-current-version').innerText(), '2')
  passed('The real immutable first version remains readable independently of the current second version and its CAS')

  await page.getByTestId('profile-edit').click()
  await page.getByTestId('profile-weekly-hours').fill('2')
  await page.getByTestId('profile-confirmation').check()
  await checkpoint('external CAS context start')
  const external = await bounded('external CAS context', () => setupPage())
  await checkpoint('external CAS context ready')
  const concurrent = await api(external, 'profiles/' + ids.profile_id + '/versions', { method: 'POST', body: {
    profile: { ...second.profile, weekly_hours: '1' }, confirmed: true, expected_current_version: 2 } })
  assert.equal(concurrent.status, 200); assert.equal(concurrent.body.data.version.version, 3)
  await checkpoint('external CAS append committed; attempt original stale UI save')
  ids.version_ids.push(concurrent.body.data.version.version_id)
  await bounded('bring original CAS page to front', () => page.bringToFront(), 10000)
  const beforeConflict = writes.length
  const conflict = await clickResponse(page, 'profile-save', 'profiles/' + ids.profile_id + '/versions')
  assert.equal(conflict.status, 409)
  await page.getByTestId('profile-conflict').waitFor()
  assert.equal(await page.getByTestId('profile-weekly-hours').inputValue(), '2')
  assert.equal(await page.getByTestId('profile-confirmation').isChecked(), false)
  assert.equal(await page.getByTestId('profile-save').isDisabled(), true)
  assert.equal(writes.length, beforeConflict + 1)
  await checkpoint('capture actual CAS conflict')
  await page.screenshot({ path: resolve(cache, 'profile-cas-conflict.png'), fullPage: true, timeout: 15000 })
  await clickResponse(page, 'profile-reload-current', 'profiles/' + ids.profile_id, 'GET')
  await page.getByTestId('profile-current-version-id').filter({ hasText: concurrent.body.data.version.version_id }).waitFor()
  await bounded('close external CAS context', () => external.context().close(), 10000)
  passed('A second real context appends version three; stale UI CAS409 preserves its draft, clears confirmation and requires explicit current reread')

  await scope(page, 'course_system', 'unknown')
  assert.equal(await page.locator('[data-testid^="grade-"]').count(), 0)
  assert.equal(await page.getByTestId('profile-grade-add').count(), 0)
  const unknown = await save(page, 4)
  assert.deepEqual(unknown.profile.assessments, {})
  assert.equal(unknown.adaptation.status, 'unknown'); assert.equal(unknown.adaptation.reason, 'MISSING_SCOPE')
  passed('Explicit unknown course hides ordinary-gaokao inputs and saves no gaokao assessments or fabricated applicability')

  await page.getByTestId('profile-edit').click()
  await scope(page, 'course_system', 'known', 'gaokao')
  await scope(page, 'applicant_category', 'known', 'hmt_joint')
  assert.equal(await page.getByTestId('profile-grade-add').count(), 0)
  await scope(page, 'course_system', 'known', 'HKDSE')
  assert.equal(await page.locator('[data-testid^="grade-"]').count(), 0)
  assert.equal(await page.getByTestId('profile-grade-add').count(), 0)
  const unsupported = await save(page, 5)
  assert.equal(unsupported.adaptation.status, 'unsupported')
  assert.deepEqual(unsupported.profile.assessments, {})
  passed('An unadapted joint-exam identity and HKDSE course hide new gaokao inquiry; the saved unsupported intent consumes no earlier scores')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByTestId('profile-edit').click()
  await scope(page, 'course_system', 'known', 'gaokao')
  await scope(page, 'applicant_category', 'known', 'cn_mainland')
  await scope(page, 'pathway', 'known', 'uk_undergraduate')
  await grade(page, 'ielts_overall', 'achieved', 'pending')
  await grade(page, 'ielts_overall', 'predicted', 'provided', '7.5', '9', 'band')
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
  await checkpoint('capture mobile form')
  await page.getByTestId('profile-workspace').screenshot({ path: resolve(cache, 'profile-mobile.png'), timeout: 15000 })
  const uk = await save(page, 6, { keyboard: true })
  assert.equal(uk.profile.pathway.value, 'uk_undergraduate')
  assert.equal(uk.profile.assessments.ielts_overall.achieved.status, 'pending')
  assert.equal(uk.profile.assessments.ielts_overall.achieved.value, null)
  assert.equal(uk.profile.assessments.ielts_overall.predicted.value, '7.5')
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
  passed('A 390px mobile form supports keyboard confirmation and explicit UK language inquiry while pending remains missing rather than a permission')

  await page.setViewportSize({ width: 1280, height: 900 })
  await checkpoint('capture desktop version')
  await page.getByTestId('profile-workspace').screenshot({ path: resolve(cache, 'profile-desktop.png'), timeout: 15000 })
  const withdrawn = await clickResponse(page, 'withdraw-core', 'me/consents/' + consent.data.consent_id, 'DELETE')
  assert.equal(withdrawn.status, 200); assert.equal(withdrawn.data.core_consultation_allowed, false)
  await page.waitForFunction(() => document.querySelector('[data-testid="profile-entry-year"]') === null)
  assert.equal(await page.getByTestId('profile-current').count(), 0)
  assert.equal(await page.getByTestId('profile-history-result').count(), 0)
  const oldDenied = await api(page, 'profiles/' + ids.profile_id)
  assert.ok([403, 409].includes(oldDenied.status))
  passed('Actual core withdrawal immediately clears draft/current/history and the backend denies the old confirmed profile')

  await page.getByTestId('core-confirmation').check()
  const reconfirmed = await clickResponse(page, 'confirm-core', 'me/consents')
  assert.equal(reconfirmed.status, 200)
  await page.getByTestId('profile-new').waitFor()
  assert.equal(await page.getByTestId('profile-current').count(), 0)
  const deniedAgain = await api(page, 'profiles/' + ids.profile_id)
  assert.ok([403, 409].includes(deniedAgain.status))
  // Explicitly start a new full declaration, rather than reviving an old proof.
  await page.getByTestId('profile-new').click()
  await page.getByTestId('profile-entry-year').fill('2027')
  await page.getByTestId('profile-confirmation').check()
  const postWithdraw = requireVersion(await clickResponse(page, 'profile-save', 'profiles'), 1)
  ids.post_withdraw_profile_id = postWithdraw.profile_id
  ids.post_withdraw_version_id = postWithdraw.version_id
  assert.notEqual(postWithdraw.profile_id, ids.profile_id)
  await page.getByTestId('profile-current-version-id').filter({ hasText: postWithdraw.version_id }).waitFor()
  passed('Reconfirmation does not revive the original consent-bound version; a new full explicit UI declaration receives a distinct profile root')

  await page.getByTestId('profile-history-version-id').fill(postWithdraw.version_id)
  await control(page, 'arm')
  await checkpoint('arm real successful profile GET before logout')
  await page.getByTestId('profile-history-load').click()
  const pendingState = await waitControl(page, 'blocked')
  assert.equal(pendingState.response_status, 200)
  await checkpoint('real profile GET200 executed; response delivery is held')
  const logout = await clickResponse(page, page.getByRole('button', { name: '退出当前应用', exact: true }), 'auth/logout')
  assert.equal(logout.status, 200)
  await control(page, 'release')
  await waitControl(page, 'completed')
  await page.waitForFunction(() => document.querySelector('[data-testid="actor-id"]') === null)
  assert.equal(await page.getByTestId('profile-entry-year').count(), 0)
  assert.equal(await page.getByTestId('profile-current').count(), 0)
  assert.equal(await page.getByTestId('profile-history-result').count(), 0)
  assert.equal((await api(page, 'auth/session')).status, 401)
  const storage = await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage) }))
  assert.deepEqual(storage, { local: [], session: [] })
  await page.screenshot({ path: resolve(cache, 'profile-logged-out.png'), fullPage: true, timeout: 15000 })
  passed('Logout revokes the real session while an already-successful delayed profile GET is pending; its late delivery cannot restore any private form or history')

  assert.deepEqual(pageErrors, []); assert.deepEqual(blockedRequests, [])
  report = { status: 'passed', browser: await browser.version(), checks, page_errors: pageErrors,
    blocked_requests: blockedRequests, network_events: events, ids, cache_directory: cache,
    not_executed: ['Real Keycloak login', 'Real student data or formal privacy processing', 'Rules/eligibility evaluation', 'Production deployment'] }
} catch (error) {
  await checkpoint('failure after: ' + step)
  report = { status: 'failed', checks, step, error: safeError(error), page_errors: pageErrors,
    blocked_requests: blockedRequests, network_events: events, cache_directory: cache }
  if (page) await bounded('failure screenshot', () => page.screenshot({ path: resolve(cache, 'profile-failure.png'), fullPage: true, timeout: 10000 }), 12000).catch(() => {})
  process.exitCode = 1
} finally {
  if (browser) await bounded('browser close', () => browser.close(), 10000).catch(() => {})
  await writeFile(resolve(cache, 'result.json'), JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report))
}
