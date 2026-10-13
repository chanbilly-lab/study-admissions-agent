// T08 synthetic-only: fresh browser context, loopback TLS IdP and isolated DB.
// Historical T05/T06 fixtures are preserved. No external network or real account.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { randomBytes, randomUUID } from 'node:crypto'
import { mkdir, writeFile } from 'node:fs/promises'
import net from 'node:net'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const webOrigin = 'http://127.0.0.1:5188'
const apiOrigin = 'http://127.0.0.1:8000' // Existing unchanged Vite proxy.
const idpOrigin = 'https://127.0.0.1:9448'
const allowedOrigins = new Set([webOrigin, apiOrigin, idpOrigin])
const cacheParent = resolve(root, '.cache/t08-ui')
const cache = resolve(cacheParent, randomUUID())
const fixtureKey = randomBytes(32).toString('base64url')
const children = [], checks = [], pageErrors = [], blockedRequests = []
function passed(message) { checks.push(message); console.log(`T08 check ${checks.length}: ${message}`) }
let browser, page, report

function safeMessage(error) {
  return String(error?.message ?? error).replace(/https?:\/\/[^\s"'<>]+/g, (value) => {
    try { const url = new URL(value); return url.origin + url.pathname } catch { return '[redacted URL]' }
  }).replace(/(?:code|state|nonce|code_verifier|id_token|csrf_token)=[^\s&]+/gi, '[redacted proof]')
}
async function assertPortFree(port) {
  const server = net.createServer()
  await new Promise((success, failure) => {
    server.once('error', () => failure(new Error(`T08 port ${port} occupied; existing processes preserved`)))
    server.listen(port, '127.0.0.1', success)
  })
  await new Promise(success => server.close(success))
}
function launch(command, args, env) {
  const child = spawn(command, args, { cwd: root, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  let diagnostic = ''
  for (const stream of [child.stdout, child.stderr]) stream.on('data', chunk => { diagnostic = (diagnostic + chunk.toString()).slice(-4096) })
  child.on('error', error => { diagnostic = safeMessage(error) })
  children.push(child)
  return { child, diagnostic: () => diagnostic }
}
async function waitReady(url, child, headers = {}) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (child.child.exitCode !== null) throw new Error(`T08 startup child exited: ${safeMessage(child.diagnostic())}`)
    try { const response = await fetch(url, { headers, signal: AbortSignal.timeout(700) }); if (response.ok) return response }
    catch { /* Bounded readiness checks on a fixed loopback URL. */ }
    await new Promise(success => setTimeout(success, 200))
  }
  throw new Error(`T08 startup timed out: ${safeMessage(child.diagnostic())}`)
}
async function control(path) {
  assert.ok(['/__test__/advance', '/__test__/privacy-closed'].includes(path))
  const response = await fetch(apiOrigin + path, { method: 'POST', headers: { 'X-T08-Fixture-Key': fixtureKey } })
  assert.equal(response.status, 200)
}
function protectedResponse(response) {
  assert.equal(response.headers()['cache-control'], 'no-store')
  assert.equal(response.headers()['referrer-policy'], 'no-referrer')
}
async function storageEmpty() {
  assert.deepEqual(await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage), readableCookie: document.cookie })),
    { local: [], session: [], readableCookie: '' })
}
async function admissionRequest() {
  return page.evaluate(async () => {
    const response = await fetch('/api/v2/me/admission', { credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(10000) })
    return { status: response.status, body: await response.json() }
  })
}
async function ageSubmit(band, expectedStatus = 200) {
  await page.locator(`input[value="${band}"]`).check()
  await page.getByTestId('age-confirmation').check()
  const replied = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/me/age-declarations')
  await page.getByTestId('declare-age').click()
  const response = await replied
  assert.equal(response.status(), expectedStatus)
  protectedResponse(response)
  assert.equal(response.request().headers().origin, webOrigin)
  assert.ok(response.request().headers()['x-csrf-token'])
  const body = response.request().postDataJSON()
  assert.deepEqual(Object.keys(body).sort(), ['age_band', 'confirmed', 'expected_revision', 'notice_id'])
  assert.equal(body.age_band, band)
  assert.equal(body.confirmed, true)
  return response
}
async function confirmCore() {
  await page.getByTestId('core-confirmation').check()
  const replied = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/me/consents' && r.request().method() === 'POST')
  await page.getByTestId('confirm-core').click()
  const response = await replied
  assert.equal(response.status(), 200)
  protectedResponse(response)
  assert.deepEqual(Object.keys(response.request().postDataJSON()).sort(), ['confirmed', 'expected_revision', 'notice_id', 'purpose'])
  assert.equal(response.request().postDataJSON().purpose, 'core_consultation')
  await page.getByTestId('withdraw-core').waitFor()
  assert.match(await page.getByTestId('admission-decision').innerText(), /门槛已满足.*业务仍未开放/)
}

try {
  for (const port of [5188, 8000, 9448]) await assertPortFree(port)
  await mkdir(cacheParent, { recursive: true })
  const fixture = launch(process.env.T08_PYTHON ?? resolve(root, '.venv/Scripts/python.exe'),
    ['-B', resolve(root, 'tests/e2e/privacy_t08_fixture.py'), '--cache-dir', cache, '--web-origin', webOrigin, '--api-port', '8000', '--idp-port', '9448'],
    { ...process.env, T08_FIXTURE_CONTROL_KEY: fixtureKey, PYTHONDONTWRITEBYTECODE: '1' })
  const readiness = await (await waitReady(apiOrigin + '/__test__/ready', fixture, { 'X-T08-Fixture-Key': fixtureKey })).json()
  assert.equal(readiness.is_synthetic, true)
  const vite = launch(process.execPath, [resolve(root, 'apps/web/node_modules/vite/bin/vite.js'), resolve(root, 'apps/web'), '--config', resolve(root, 'apps/web/vite.config.ts'), '--host', '127.0.0.1', '--port', '5188', '--strictPort'],
    { ...process.env, VITE_APP_MODE: 'auth', VITE_AUTH_API_BASE_URL: '/api' })
  await waitReady(webOrigin, vite)
  const bundledPlaywright = resolve(process.env.USERPROFILE ?? '', '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs')
  const moduleName = process.env.T08_PLAYWRIGHT_MODULE ?? bundledPlaywright
  const playwright = await import(moduleName.startsWith('.') || moduleName.includes(':') || moduleName.startsWith('/') ? pathToFileURL(resolve(moduleName)).href : moduleName)
  browser = await playwright.chromium.launch({ headless: true, channel: 'msedge' })
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 900 } })
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url())
    if (!allowedOrigins.has(url.origin)) { blockedRequests.push(url.origin + url.pathname); await route.abort('blockedbyclient'); return }
    assert.ok(!request.headers().authorization, 'No browser Bearer token')
    assert.ok(!/\/api\/v2\/(?:profiles|admin|plans|attachments)/.test(url.pathname), 'No future business request')
    await route.continue()
  })
  page = await context.newPage()
  page.setDefaultTimeout(15000)
  page.setDefaultNavigationTimeout(30000)
  page.on('pageerror', error => pageErrors.push(safeMessage(error)))
  page.on('websocket', socket => { if (new URL(socket.url()).host !== '127.0.0.1:5188') blockedRequests.push(socket.url()) })
  await page.goto(webOrigin)
  await page.getByRole('link', { name: '通过身份供应商登录' }).waitFor()
  await page.getByTestId('privacy-demo').waitFor()
  assert.equal(await page.locator('form').count(), 0)
  const login = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/auth/login')
  await page.getByRole('link', { name: '通过身份供应商登录' }).click()
  const started = await login
  assert.equal(started.status(), 302)
  assert.equal(new URL(started.headers().location).origin, idpOrigin)
  const callback = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/auth/callback')
  await page.getByRole('button', { name: '继续使用合成主体', exact: true }).click()
  assert.equal((await callback).status(), 303)
  await page.getByTestId('actor-id').waitFor()
  await page.getByTestId('declare-age').waitFor()
  assert.equal(await page.getByTestId('actor-id').innerText(), readiness.user_id)
  assert.equal(await page.getByTestId('declare-age').isDisabled(), true)
  assert.equal(await page.getByTestId('core-confirmation').count(), 0)
  passed('Anonymous policy requires no fields; signed loopback login restores the explicitly registered synthetic actor')

  const ageResponse = await ageSubmit('18_plus')
  const firstAge = (await ageResponse.json()).data
  assert.equal(firstAge.age_assurance, 'declared')
  assert.equal(firstAge.core_consultation_allowed, false)
  assert.equal(firstAge.private_business_available, false)
  await page.getByTestId('core-confirmation').waitFor()
  assert.match(await page.getByTestId('age-assurance').innerText(), /本人声明，未独立核验/)
  assert.equal(await page.getByTestId('core-confirmation').isChecked(), false)
  assert.equal(await page.getByTestId('confirm-core').isDisabled(), true)
  passed('Adult declaration is labelled declared, not verified; separate purpose confirmation stays unchecked')
  await confirmCore()
  await storageEmpty()
  assert.equal(await page.locator('input[type="date"],input[type="file"],input[name="guardian"]').count(), 0)
  await page.screenshot({ path: resolve(cache, 'privacy-desktop.png'), fullPage: true })
  passed('Explicit core-purpose confirmation uses current revision and leaves private business unavailable')
  await page.setViewportSize({ width: 390, height: 844 })
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  const radioSizes = await page.locator('input[type="radio"]').evaluateAll(inputs => inputs.map(input => {
    const box = input.getBoundingClientRect()
    return { width: box.width, height: box.height }
  }))
  assert.equal(radioSizes.length, 4)
  assert.ok(radioSizes.every(size => size.width >= 16 && size.width <= 20 && size.height >= 16 && size.height <= 20), 'Radio controls must stay compact despite global input styles')
  await page.screenshot({ path: resolve(cache, 'privacy-mobile.png'), fullPage: true })
  passed('390px layout has compact radio controls, no overflow, DOB/guardian/file fields or browser-readable secrets')

  const withdrawal = page.waitForResponse(r => /\/api\/v2\/me\/consents\/[0-9a-f-]+$/.test(new URL(r.url()).pathname) && r.request().method() === 'DELETE')
  await page.getByTestId('withdraw-core').click()
  const withdrawn = await withdrawal
  assert.equal(withdrawn.status(), 200)
  protectedResponse(withdrawn)
  assert.equal(withdrawn.request().postData(), null)
  assert.equal((await withdrawn.json()).data.core_consultation_allowed, false)
  await page.getByTestId('admission-decision').filter({ hasText: '已撤回' }).waitFor()
  const afterWithdrawal = await admissionRequest()
  assert.equal(afterWithdrawal.status, 200)
  assert.equal(afterWithdrawal.body.data.consent_status, 'withdrawn')
  assert.equal(afterWithdrawal.body.data.core_consultation_allowed, false)
  await page.reload()
  await page.getByTestId('admission-decision').filter({ hasText: '已撤回' }).waitFor()
  passed('Bodyless withdrawal is confirmed by real HTTP; cleared permission remains closed after reload')

  await confirmCore()
  console.log('T08 progress: reconfirmed withdrawn purpose')
  await ageSubmit('unknown', 403)
  console.log('T08 progress: unknown declaration returned 403')
  // The UI intentionally does not consume arbitrary error JSON. In Chromium,
  // response.json() for this abandoned fetch body can wait indefinitely. HTTP
  // security tests validate the error envelope; this browser test checks the
  // actual refusal and a subsequent authoritative read instead.
  await page.getByRole('alert').waitFor()
  console.log('T08 progress: refusal visible')
  assert.equal(await page.getByTestId('admission-decision').count(), 0)
  await page.getByRole('button', { name: '重新读取隐私设置', exact: true }).click()
  console.log('T08 progress: reread requested after refusal')
  await page.getByTestId('age-assurance').filter({ hasText: '未知' }).waitFor()
  const deniedState = await admissionRequest()
  assert.equal(deniedState.body.data.age_band, null)
  assert.equal(deniedState.body.data.age_assurance, 'unknown')
  assert.equal(deniedState.body.data.consent_status, 'invalidated')
  assert.equal(deniedState.body.data.core_consultation_allowed, false)
  assert.equal(await page.getByTestId('core-confirmation').count(), 0)
  passed('Nonadult/unknown declaration returns 403 but commits old adult/consent invalidation; UI clears permission and rereads unknown')

  await ageSubmit('18_plus')
  await page.getByTestId('core-confirmation').waitFor()
  await confirmCore()
  await control('/__test__/privacy-closed')
  await page.getByRole('button', { name: '重新读取隐私设置', exact: true }).click()
  await page.getByText('正式告知尚未就绪', { exact: true }).waitFor()
  assert.equal(await page.locator('form').count(), 0)
  await page.getByTestId('withdraw-core').waitFor()
  await page.screenshot({ path: resolve(cache, 'privacy-closed.png'), fullPage: true })
  passed('Unready notice hides collection forms while existing owner withdrawal remains available')

  await control('/__test__/advance')
  const expired = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/me/admission')
  await page.getByRole('button', { name: '重新读取隐私设置', exact: true }).click()
  assert.equal((await expired).status(), 401)
  await page.getByRole('link', { name: '通过身份供应商登录' }).waitFor()
  assert.equal(await page.getByTestId('actor-id').count(), 0)
  assert.equal(await page.getByTestId('admission-decision').count(), 0)
  assert.equal(await page.locator('form').count(), 0)
  await storageEmpty()
  passed('Current privacy 401 clears parent identity, admission and confirmations; no token/cookie/browser storage')
  assert.deepEqual(pageErrors, [])
  assert.deepEqual(blockedRequests, [])
  passed('All browser requests stayed on fixed loopback origins without page errors')
  report = { status: 'passed', browser: await browser.version(), mode: 'auth', data: 'synthetic-only', checks, page_errors: pageErrors, blocked_requests: blockedRequests,
    not_executed: ['Production PostgreSQL (independent security tests)', 'Real Keycloak deployment/accounts', 'Production TLS and legal/controller review', 'Guardian verification', 'Real student data/cleanup/jobs'], cache_directory: cache }
} catch (error) {
  report = { status: 'failed', checks, error: safeMessage(error), page_errors: pageErrors, blocked_requests: blockedRequests, cache_directory: cache }
  console.log(JSON.stringify(report, null, 2))
  await writeFile(resolve(cache, 'report.json'), JSON.stringify(report, null, 2)).catch(() => {})
  if (page) await page.screenshot({ path: resolve(cache, 'privacy-failure.png'), fullPage: true, timeout: 5000 }).catch(() => {})
  process.exitCode = 1
} finally {
  if (browser) await browser.close()
  for (const child of children.reverse()) {
    if (child.exitCode === null) {
      child.kill()
      await new Promise(success => { child.once('exit', success); setTimeout(success, 1500).unref() })
    }
  }
  if (report) {
    await writeFile(resolve(cache, 'report.json'), JSON.stringify(report, null, 2)).catch(() => {})
    console.log(JSON.stringify(report, null, 2))
  }
}
