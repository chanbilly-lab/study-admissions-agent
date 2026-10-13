// T29: actual Edge -> loopback ASGI -> isolated synthetic PostgreSQL.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { randomUUID } from 'node:crypto'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
let input = ''
for await (const chunk of process.stdin) {
  input += chunk
  if (Buffer.byteLength(input) > 16384) throw new Error('T29 fixture is too large')
}
const fixture = JSON.parse(input)
assert.match(fixture.origin, /^http:\/\/127\.0\.0\.1:[0-9]+$/)
const cache = resolve(root, '.cache/t29-ui', randomUUID())
await mkdir(cache, { recursive: true })
const checks = [], pageErrors = [], blockedRequests = [], publicRequests = [], events = []
const ids = { profile_id: null, assessment_ids: [] }
let browser, page, report, step = 'initial'

function safeError(error) {
  let text = String(error?.message ?? error)
  for (const secret of [fixture.owner_cookie, fixture.other_cookie]) text = text.split(secret).join('[redacted]')
  return text.replace(/https?:\/\/[^\s"'<>]+/g, '[URL]').slice(0, 3000)
}
async function bounded(label, work, milliseconds = 45000) {
  let timer
  try { return await Promise.race([work(), new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error('T29 timeout: ' + label)), milliseconds)
  })]) } finally { clearTimeout(timer) }
}
async function checkpoint(value) {
  step = value
  await writeFile(resolve(cache, 'progress.json'), JSON.stringify({ step, checks, events }))
}
function passed(message) { checks.push(message) }
async function setupPage() {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  await context.addCookies([{ name: '__Host-admissions-session', value: fixture.owner_cookie,
    domain: '127.0.0.1', path: '/', secure: true, httpOnly: true, sameSite: 'Lax' }])
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url())
    if (url.origin !== fixture.origin) {
      blockedRequests.push(url.origin + url.pathname)
      await route.abort('blockedbyclient')
      return
    }
    const headers = await bounded('request headers', () => request.allHeaders(), 10000)
    assert.ok(!headers.authorization, 'No Bearer token enters the browser')
    if (url.pathname.startsWith('/public/v2/')) {
      publicRequests.push({ path: url.pathname, cookie: Boolean(headers.cookie) })
      assert.ok(!headers.cookie, 'Anonymous public reads must omit the private cookie')
    }
    await route.continue()
  })
  const result = await context.newPage()
  result.setDefaultTimeout(45000)
  result.on('pageerror', error => pageErrors.push(safeError(error)))
  result.on('response', response => {
    const path = new URL(response.url()).pathname
    if (path.startsWith('/api/v2/') || path.startsWith('/public/v2/')) {
      events.push({ path, method: response.request().method(), status: response.status() })
      if (events.length > 60) events.shift()
    }
  })
  await result.goto(fixture.origin)
  return result
}
async function action(selector, path, method = 'GET', keyboard = false) {
  await checkpoint('UI ' + method + ' ' + path)
  const pending = page.waitForResponse(response => new URL(response.url()).pathname === path
    && response.request().method() === method)
  const element = typeof selector === 'string' ? page.getByTestId(selector) : selector
  if (keyboard) { await element.focus(); await page.keyboard.press('Enter') }
  else await element.click()
  const response = await bounded('UI response ' + path, () => pending)
  assert.equal(response.headers()['cache-control'], 'no-store')
  assert.match(response.headers()['x-request-id'], /^[0-9a-f]{32}$/)
  if (method !== 'GET') {
    assert.equal(response.request().headers().origin, fixture.origin)
    assert.ok(response.request().headers()['x-csrf-token'])
    assert.ok(!response.request().headers()['idempotency-key'], 'Assessment writes have no idempotency contract')
  }
  // Failed responses are deliberately not parsed by the application. Avoid
  // waiting on browser response.json() for their aborted/unconsumed bodies.
  const envelope = response.status() === 200 ? await bounded('success JSON', () => response.json(), 10000) : null
  if (envelope) assert.equal(envelope.meta.request_id, response.headers()['x-request-id'])
  return { status: response.status(), data: envelope?.data, envelope,
    request: method === 'GET' ? null : response.request().postDataJSON() }
}
async function api(path, { method = 'GET', body, csrf = true } = {}) {
  return bounded('direct API ' + path, () => page.evaluate(async ({ path, method, body, csrf }) => {
    const headers = { Accept: 'application/json' }
    if (method !== 'GET' && csrf) {
      const proof = await fetch('/api/v2/auth/csrf', { credentials: 'same-origin', cache: 'no-store' })
      if (proof.status !== 200) return { status: proof.status }
      headers['X-CSRF-Token'] = (await proof.json()).data.csrf_token
    }
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    const response = await fetch('/api/v2/' + path, { method, credentials: 'same-origin', cache: 'no-store',
      headers, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) })
    return { status: response.status, data: response.status === 200 ? (await response.json()).data : null }
  }, { path, method, body, csrf }))
}
async function control(action) {
  return bounded('delivery control', () => page.evaluate(async action => {
    const response = await fetch('/__t29/control', action ? { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) } : {})
    return response.json()
  }, action))
}
async function waitControl(key) {
  return bounded('wait actual delivery ' + key, async () => {
    while (true) {
      const value = await control()
      if (value[key]) return value
      await new Promise(resolve => setTimeout(resolve, 75))
    }
  })
}
async function chooseProfile() {
  const listed = await action('profile-list', '/api/v2/profiles')
  assert.equal(listed.status, 200)
  assert.equal(listed.data.items.length, 1)
  const id = listed.data.items[0].profile_id
  const loaded = await action('profile-load-' + id, '/api/v2/profiles/' + id)
  assert.equal(loaded.status, 200)
  await page.getByTestId('profile-current-version-id').filter({ hasText: loaded.data.version_id }).waitFor()
  return loaded.data
}
async function selectTarget(item) {
  await page.getByTestId('catalog-select-' + item.id + '-' + item.version).click()
  if (await page.getByTestId('catalog-context-refresh').isVisible()) {
    const context = await action('catalog-context-refresh', '/api/v2/eligibility/context')
    assert.equal(context.status, 200)
    assert.equal(context.data.can_evaluate, true)
  }
  await page.getByTestId('catalog-confirm').waitFor()
}
async function evaluate(expected, profile, item) {
  assert.equal(await page.getByTestId('catalog-evaluate').isDisabled(), true)
  await page.getByTestId('catalog-confirm').check()
  const result = await action('catalog-evaluate', '/api/v2/eligibility/evaluations', 'POST')
  assert.equal(result.status, 200)
  assert.equal(result.data.eligibility.status, expected)
  assert.equal(result.data.profile_version_id, profile.version_id)
  assert.equal(result.data.profile_sha256, profile.profile_sha256)
  assert.equal(result.data.release_id, item.release_id)
  assert.equal(result.data.target.offering_id, item.id)
  assert.equal(result.data.target.offering_version, item.version)
  assert.equal(result.data.requirements_version, item.requirements_version)
  assert.equal(result.data.stage, 'application')
  assert.equal(result.request.confirmed, true)
  for (const forbidden of ['owner', 'role', 'clock', 'assessment_at', 'eligibility', 'expression'])
    assert.ok(!Object.hasOwn(result.request, forbidden))
  for (const dimension of ['competition_context', 'preference_fit', 'data_quality'])
    assert.equal(result.data[dimension].status, 'unknown')
  const statusText = { eligible: '符合已核查资格条件', ineligible: '明确不满足已核查条件',
    conditional: '须完成适用后补义务', unknown: '资格未知，仍需核验' }
  await page.getByTestId('assessment-current-result').getByTestId('assessment-status').filter({ hasText: statusText[expected] }).waitFor()
  ids.assessment_ids.push(result.data.assessment_id)
  return result.data
}
async function appendGrade(profile, key, value, scale) {
  const snapshot = structuredClone(profile.profile)
  snapshot.assessments[key].achieved = { status: 'provided', value, scale, unit: 'points' }
  const result = await api('profiles/' + profile.profile_id + '/versions', { method: 'POST', body: {
    profile: snapshot, confirmed: true, expected_current_version: profile.version } })
  assert.equal(result.status, 200)
  // Read the new actual current version through the existing T24 UI. A cached
  // earlier snapshot is never passed as the next eligibility profile.
  const loaded = await action('profile-load-' + profile.profile_id, '/api/v2/profiles/' + profile.profile_id)
  assert.equal(loaded.status, 200)
  assert.equal(loaded.data.version_id, result.data.version.version_id)
  assert.equal(await page.getByTestId('assessment-current-result').count(), 0)
  return loaded.data
}
async function armHistory(assessment) {
  await page.getByTestId('assessment-history-id').fill(assessment.assessment_id)
  await control('arm')
  await page.getByTestId('assessment-history-read').click()
  const state = await waitControl('blocked')
  assert.equal(state.response_status, 200)
}
async function switchActor(cookie, userId) {
  await page.context().addCookies([{ name: '__Host-admissions-session', value: cookie,
    domain: '127.0.0.1', path: '/', secure: true, httpOnly: true, sameSite: 'Lax' }])
  await action(page.getByRole('button', { name: '重新检查会话', exact: true }), '/api/v2/auth/session')
  await page.getByTestId('actor-id').filter({ hasText: userId }).waitFor()
}

try {
  const module = process.env.T29_PLAYWRIGHT_MODULE || resolve(process.env.USERPROFILE || '',
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs')
  const { chromium } = await import(pathToFileURL(module).href)
  browser = await chromium.launch({ channel: 'msedge', headless: true })
  page = await setupPage()
  await page.getByTestId('actor-id').filter({ hasText: fixture.user_id }).waitFor()
  const profile = await chooseProfile()
  ids.profile_id = profile.profile_id
  await page.getByTestId('catalog-toggle').click()
  await page.getByTestId('catalog-workspace').waitFor()
  assert.equal(await page.getByTestId('catalog-year').inputValue(), '')
  passed('Catalog opens explicitly with no guessed current year or private profile fallback')
  await page.getByTestId('catalog-year').fill(String(fixture.year))
  await page.getByTestId('catalog-country').selectOption('CN')
  await page.getByTestId('catalog-province').selectOption('known:Zhejiang')
  await page.getByTestId('catalog-limit').selectOption('1')
  let result = await action('catalog-search', '/public/v2/offerings', 'GET', true)
  assert.equal(result.status, 200)
  assert.equal(result.data.items.length, 1)
  assert.equal(result.data.page.has_more, true)
  const first = result.data.items[0]
  await page.getByTestId('catalog-compare-' + first.id + '-' + first.version).check()
  result = await action('catalog-next', '/public/v2/offerings')
  assert.equal(result.status, 200)
  const second = result.data.items[0]
  assert.notEqual(second.id, first.id)
  assert.equal(second.program_id, first.program_id)
  await page.getByTestId('catalog-compare-' + second.id + '-' + second.version).check()
  assert.equal(result.data.page.has_more, false)
  passed('Actual anonymous SQL pagination and cross-page comparison preserve two exact targets sharing one program name')
  await page.getByTestId('catalog-limit').selectOption('20')
  result = await action('catalog-search', '/public/v2/offerings')
  assert.equal(result.status, 200)
  assert.equal(result.data.items.length, 2)
  const known = result.data.items.find(item => item.facts.some(fact => fact.field_key === 'DEMO_T28_RULE'))
  const unknown = result.data.items.find(item => item.id !== known.id)
  assert.equal(known.ruleset_version, null)
  const quoted = unknown.facts.find(fact => fact.footnote_state === 'present')
  const card = page.getByTestId('catalog-offering-' + unknown.id + '-' + unknown.version)
  await card.locator('summary').click()
  const quote = await action(card.getByTestId('catalog-evidence-' + quoted.evidence_id), '/public/v2/evidence/' + quoted.evidence_id)
  assert.equal(quote.status, 200)
  await page.getByTestId('public-evidence-quote').filter({ hasText: '<img' }).waitFor()
  assert.equal(await page.getByTestId('public-evidence-dialog').locator('img').count(), 0)
  assert.equal(await page.evaluate(() => window.__t29Xss ?? null), null)
  await page.keyboard.press('Escape')
  assert.equal(await page.getByTestId('public-evidence-dialog').isVisible(), false)
  assert.equal(await card.getByTestId('catalog-evidence-' + quoted.evidence_id).evaluate(element => element === document.activeElement), true)
  passed('Only actual public member evidence is fetched; HTML remains literal and Escape restores keyboard focus')
  await selectTarget(known)
  const conditional = await evaluate('conditional', profile, known)
  assert.equal(conditional.eligibility.obligations[0].assessment_key, 'math')
  assert.equal(conditional.eligibility.obligations[0].deferral.application_deadline_status, 'before')
  assert.equal(conditional.eligibility.obligations[0].deferral.supplement_deadline_status, 'before')
  passed('Actual typed missing math is conditional only with independently published policy and main/supplement evidence')
  const goodProfile = await appendGrade(profile, 'math', '95', '150')
  await selectTarget(known)
  await evaluate('eligible', goodProfile, known)
  passed('Explicit new confirmed profile version clears old result and evaluates achieved marks without predicted fallback')
  const badProfile = await appendGrade(goodProfile, 'gaokao_total', '500', '750')
  await selectTarget(known)
  const failed = await evaluate('ineligible', badProfile, known)
  passed('A complete applicable required failure is ineligible; all non-qualification dimensions remain unknown')
  await selectTarget(unknown)
  await evaluate('unknown', badProfile, unknown)
  passed('An actually published facts-only target with no trusted rule binding remains unknown, with no client inference from facts')
  await page.getByTestId('assessment-history-id').fill(failed.assessment_id)
  result = await action('assessment-history-read', '/api/v2/eligibility/evaluations/' + failed.assessment_id)
  assert.equal(result.status, 200)
  await page.getByTestId('assessment-replay-confirm').check()
  result = await action('assessment-replay', '/api/v2/eligibility/evaluations/' + failed.assessment_id + '/replay', 'POST')
  assert.equal(result.status, 200)
  assert.equal(result.data.replayed, true)
  assert.equal(result.data.assessment_at, failed.assessment_at)
  assert.equal(result.data.result_sha256, failed.result_sha256)
  passed('Explicit historical read and confirmed replay preserve original server time and result SHA')
  assert.equal((await api('eligibility/evaluations', { method: 'POST', body: {}, csrf: false })).status, 403)
  passed('Actual private write without current CSRF is rejected, without a client success result')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByTestId('catalog-workspace').scrollIntoViewIfNeeded()
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
  await page.screenshot({ path: resolve(cache, 'catalog-mobile.png'), fullPage: true, timeout: 15000 })
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.screenshot({ path: resolve(cache, 'catalog-desktop.png'), fullPage: true, timeout: 15000 })
  passed('390px mobile and keyboard query/evidence workflow have no horizontal overflow')
  await armHistory(failed)
  await switchActor(fixture.other_cookie, fixture.other_user_id)
  await control('release'); await waitControl('completed')
  assert.equal(await page.getByTestId('assessment-result').count(), 0)
  assert.equal((await api('eligibility/evaluations/' + failed.assessment_id)).status, 404)
  passed('A real successful A GET held at delivery cannot restore A data after switching to B; server still denies cross-owner history')
  const otherProfile = await chooseProfile()
  await selectTarget(known)
  const otherResult = await evaluate('conditional', otherProfile, known)
  await armHistory(otherResult)
  const withdrawal = await action('withdraw-core', '/api/v2/me/consents/' +
    (await api('me/admission')).data.consent_id, 'DELETE')
  assert.equal(withdrawal.status, 200)
  await control('release'); await waitControl('completed')
  assert.equal(await page.getByTestId('assessment-result').count(), 0)
  assert.equal((await api('eligibility/evaluations/' + otherResult.assessment_id)).status, 403)
  passed('Actual purpose withdrawal immediately clears B private results; its already-successful delayed GET cannot revive them')
  await switchActor(fixture.owner_cookie, fixture.user_id)
  await chooseProfile()
  assert.equal((await action('catalog-context-refresh', '/api/v2/eligibility/context')).status, 200)
  await armHistory(failed)
  result = await action(page.getByRole('button', { name: '退出当前应用', exact: true }), '/api/v2/auth/logout', 'POST')
  assert.equal(result.status, 200)
  await control('release'); await waitControl('completed')
  assert.equal(await page.getByTestId('assessment-result').count(), 0)
  assert.equal((await api('auth/session')).status, 401)
  assert.deepEqual(await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage) })),
    { local: [], session: [] })
  passed('Real logout revokes A session, rejects late successful history and leaves no private browser persistence')
  assert.ok(publicRequests.length >= 4)
  assert.ok(publicRequests.every(request => !request.cookie))
  assert.deepEqual(pageErrors, []); assert.deepEqual(blockedRequests, [])
  report = { status: 'passed', browser: await browser.version(), checks, page_errors: pageErrors,
    blocked_requests: blockedRequests, public_requests: publicRequests, network_events: events, ids, cache_directory: cache,
    not_executed: ['Real Keycloak or students', 'Formal rule/policy verification', 'Production deployment'] }
} catch (error) {
  await checkpoint('failure after ' + step)
  report = { status: 'failed', checks, step, error: safeError(error), page_errors: pageErrors,
    blocked_requests: blockedRequests, network_events: events, cache_directory: cache }
  if (page) try { await page.screenshot({ path: resolve(cache, 'failure.png'), fullPage: true, timeout: 10000 }) } catch {}
} finally {
  if (page) try { await control('release') } catch {}
  if (browser) await browser.close()
}
await writeFile(resolve(cache, 'report.json'), JSON.stringify(report, null, 2))
process.stdout.write(JSON.stringify(report) + '\n')
if (report.status !== 'passed') process.exitCode = 1
