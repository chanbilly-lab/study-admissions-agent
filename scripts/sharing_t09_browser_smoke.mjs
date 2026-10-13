// T09: two independent synthetic signed identities, isolated loopback test app.
// No real domain content, deployed IdP, external network or browser token storage.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { randomBytes, randomUUID } from 'node:crypto'
import { mkdir, writeFile } from 'node:fs/promises'
import net from 'node:net'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const webOrigin = 'http://127.0.0.1:5189', apiOrigin = 'http://127.0.0.1:8000', idpOrigin = 'https://127.0.0.1:9449'
const allowedOrigins = new Set([webOrigin, apiOrigin, idpOrigin])
const cacheParent = resolve(root, '.cache/t09-ui'), cache = resolve(cacheParent, randomUUID())
const fixtureKey = randomBytes(32).toString('base64url'), children = [], checks = [], pageErrors = [], blockedRequests = []
let browser, owner, recipient, report
function passed(message) { checks.push(message); console.log(`T09 check ${checks.length}: ${message}`) }
function safeMessage(error) {
  return String(error?.message ?? error).replace(/https?:\/\/[^\s"'<>]+/g, value => {
    try { const url = new URL(value); return url.origin + url.pathname } catch { return '[redacted URL]' }
  }).replace(/(?:code|state|nonce|code_verifier|id_token|csrf_token)=[^\s&]+/gi, '[redacted proof]')
}
async function assertPortFree(port) {
  const server = net.createServer()
  await new Promise((success, failure) => { server.once('error', () => failure(new Error(`T09 port ${port} occupied; existing processes preserved`))); server.listen(port, '127.0.0.1', success) })
  await new Promise(success => server.close(success))
}
function launch(command, args, env) {
  const child = spawn(command, args, { cwd: root, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  let diagnostic = ''
  for (const stream of [child.stdout, child.stderr]) stream.on('data', chunk => { diagnostic = (diagnostic + chunk.toString()).slice(-4096) })
  child.on('error', error => { diagnostic = safeMessage(error) }); children.push(child)
  return { child, diagnostic: () => diagnostic }
}
async function waitReady(url, process, headers = {}) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (process.child.exitCode !== null) throw new Error(`T09 child exited: ${safeMessage(process.diagnostic())}`)
    try { const response = await fetch(url, { headers, signal: AbortSignal.timeout(700) }); if (response.ok) return response } catch { /* Fixed bounded loopback readiness. */ }
    await new Promise(success => setTimeout(success, 200))
  }
  throw new Error(`T09 startup timed out: ${safeMessage(process.diagnostic())}`)
}
async function control(path) {
  assert.ok(['/__test__/sharing-closed', '/__test__/expire-grants', '/__test__/advance', '/__test__/notice-damaged'].includes(path))
  const response = await fetch(apiOrigin + path, { method: 'POST', headers: { 'X-T09-Fixture-Key': fixtureKey } }); assert.equal(response.status, 200)
}
function protectedResponse(response) { assert.equal(response.headers()['cache-control'], 'no-store'); assert.equal(response.headers()['referrer-policy'], 'no-referrer') }
async function storageEmpty(page) {
  assert.deepEqual(await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage), readableCookie: document.cookie })), { local: [], session: [], readableCookie: '' })
}
async function setupPage() {
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 900 } })
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url())
    if (!allowedOrigins.has(url.origin)) { blockedRequests.push(url.origin + url.pathname); await route.abort('blockedbyclient'); return }
    assert.ok(!request.headers().authorization, 'Browser does not receive a Bearer token')
    assert.ok(!/\/api\/v2\/(?:profiles|admin|plans|attachments)/.test(url.pathname), 'No real or future business request')
    await route.continue()
  })
  const page = await context.newPage(); page.setDefaultTimeout(15000); page.setDefaultNavigationTimeout(30000)
  page.on('pageerror', error => pageErrors.push(safeMessage(error)))
  page.on('websocket', socket => { if (new URL(socket.url()).host !== '127.0.0.1:5189') blockedRequests.push(socket.url()) })
  return page
}
async function login(page, identity, expectedId) {
  await page.goto(webOrigin); await page.getByRole('link', { name: '通过身份供应商登录' }).waitFor()
  await page.getByTestId('sharing-demo').waitFor()
  assert.equal(await page.locator('form').count(), 0)
  const started = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/auth/login')
  await page.getByRole('link', { name: '通过身份供应商登录' }).click()
  assert.equal((await started).status(), 302)
  const callback = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/auth/callback')
  await page.getByRole('button', { name: identity === 'owner' ? '登录合成授权人' : '登录合成受权人', exact: true }).click()
  assert.equal((await callback).status(), 303)
  await page.getByTestId('actor-id').waitFor(); assert.equal(await page.getByTestId('actor-id').innerText(), expectedId)
  await page.getByTestId('declare-age').waitFor()
  await page.locator('input[value="18_plus"]').check(); await page.getByTestId('age-confirmation').check()
  const declared = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/me/age-declarations')
  await page.getByTestId('declare-age').click(); const result = await declared; assert.equal(result.status(), 200); protectedResponse(result)
  await page.getByTestId('age-assurance').filter({ hasText: '本人声明，未独立核验' }).waitFor()
}
async function reread(page) {
  const replied = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/access-grants' && r.request().method() === 'GET')
  await page.getByRole('button', { name: '重新读取共享设置', exact: true }).click()
  assert.equal((await replied).status(), 200)
  await page.getByRole('button', { name: '本人授出', exact: true }).waitFor()
}
async function projection(page, id) {
  return page.evaluate(async id => {
    const response = await fetch('/api/v2/__test__/projection/' + id, { credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(10000) })
    return { status: response.status, body: await response.json() }
  }, id)
}
async function received(page) {
  const replied = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/access-grants' && new URL(r.url()).searchParams.get('direction') === 'received')
  await page.getByRole('button', { name: '本人收到', exact: true }).click()
  assert.equal((await replied).status(), 200)
  await page.locator('button[aria-pressed="true"]').filter({ hasText: '本人收到' }).waitFor()
}
async function createGrant(page, fixture, expiry) {
  await page.getByTestId('grant-kind').selectOption('profile')
  await page.getByTestId('grant-resource').fill(fixture.resource_id)
  await page.getByTestId('grant-resource-version').fill(String(fixture.resource_version))
  await page.getByTestId('grant-grantee').fill(fixture.recipient_id)
  await page.getByTestId('grant-expiry').fill(expiry)
  await page.getByTestId('grant-field-status').check(); await page.getByTestId('grant-action-read').check()
  assert.equal(await page.getByTestId('grant-confirmation').isChecked(), false)
  assert.equal(await page.getByTestId('create-grant').isDisabled(), true)
  await page.getByTestId('grant-confirmation').check()
  const written = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/access-grants' && r.request().method() === 'POST')
  await page.getByTestId('create-grant').click(); const response = await written
  assert.equal(response.status(), 200); protectedResponse(response)
  const input = response.request().postDataJSON()
  assert.deepEqual(Object.keys(input).sort(), ['actions', 'confirmed', 'expected_resource_version', 'expected_revision', 'expires_at', 'fields', 'grantee_user_id', 'owner_consent_id', 'resource_id', 'resource_type', 'sharing_policy_hash', 'sharing_policy_version'])
  assert.equal(input.confirmed, true); assert.match(input.expires_at, /Z$/)
  assert.equal(response.request().headers().origin, webOrigin); assert.ok(response.request().headers()['x-csrf-token'])
  const value = (await response.json()).data.grant
  assert.equal(value.state, 'pending'); assert.equal(value.access_active, false)
  assert.ok(!('owner_consent_id' in value) && !('recipient_declaration_id' in value))
  await page.getByTestId(`grant-${value.id}`).waitFor()
  return value
}

try {
  for (const port of [5189, 8000, 9449]) await assertPortFree(port)
  await mkdir(cacheParent, { recursive: true })
  const fixtureProcess = launch(process.env.T09_PYTHON ?? resolve(root, '.venv/Scripts/python.exe'), ['-B', resolve(root, 'tests/e2e/sharing_t09_fixture.py'), '--cache-dir', cache, '--web-origin', webOrigin, '--api-port', '8000', '--idp-port', '9449'], { ...process.env, T09_FIXTURE_CONTROL_KEY: fixtureKey, PYTHONDONTWRITEBYTECODE: '1' })
  const fixture = await (await waitReady(apiOrigin + '/__test__/ready', fixtureProcess, { 'X-T09-Fixture-Key': fixtureKey })).json()
  assert.equal(fixture.is_synthetic, true)
  const vite = launch(process.execPath, [resolve(root, 'apps/web/node_modules/vite/bin/vite.js'), resolve(root, 'apps/web'), '--config', resolve(root, 'apps/web/vite.config.ts'), '--host', '127.0.0.1', '--port', '5189', '--strictPort'], { ...process.env, VITE_APP_MODE: 'auth', VITE_AUTH_API_BASE_URL: '/api' })
  await waitReady(webOrigin, vite)
  const moduleName = process.env.T09_PLAYWRIGHT_MODULE ?? resolve(process.env.USERPROFILE ?? '', '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs')
  const playwright = await import(moduleName.startsWith('.') || moduleName.includes(':') || moduleName.startsWith('/') ? pathToFileURL(resolve(moduleName)).href : moduleName)
  browser = await playwright.chromium.launch({ headless: true, channel: 'msedge' })
  owner = await setupPage(); recipient = await setupPage()
  await login(owner, 'owner', fixture.user_id)
  await owner.getByTestId('core-confirmation').check()
  const confirmed = owner.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/me/consents' && r.request().method() === 'POST')
  await owner.getByTestId('confirm-core').click(); assert.equal((await confirmed).status(), 200)
  await owner.getByTestId('withdraw-core').waitFor(); await reread(owner)
  await login(recipient, 'recipient', fixture.recipient_id); await reread(recipient)
  assert.equal(await recipient.getByTestId('create-grant').count(), 0)
  passed('Two separate signed synthetic sessions: owner has explicit student/core; recipient has adult declaration without a role or core grant')

  const expires = new Date(Date.now() + 300000).toISOString().slice(0, 19)
  const first = await createGrant(owner, fixture, expires)
  assert.equal((await projection(recipient, fixture.resource_id)).status, 404)
  await received(recipient); await recipient.getByTestId(`grant-${first.id}`).waitFor()
  assert.equal(await recipient.getByTestId(`accept-confirm-${first.id}`).isChecked(), false)
  assert.equal(await recipient.getByTestId(`accept-grant-${first.id}`).isDisabled(), true)
  passed('Explicit exact-version field/action/UTC creation is pending; selected UUID alone gives no access and recipient confirmation stays unchecked')

  await recipient.getByTestId(`accept-confirm-${first.id}`).check()
  const accepted = recipient.waitForResponse(r => new URL(r.url()).pathname === `/api/v2/access-grants/${first.id}/accept`)
  await recipient.getByTestId(`accept-grant-${first.id}`).click(); const acceptance = await accepted
  assert.equal(acceptance.status(), 200); protectedResponse(acceptance)
  assert.deepEqual(Object.keys(acceptance.request().postDataJSON()).sort(), ['confirmed', 'expected_version', 'sharing_policy_hash', 'sharing_policy_version'])
  await recipient.getByTestId('grant-effective').filter({ hasText: '当前有效' }).waitFor()
  const shared = await projection(recipient, fixture.resource_id)
  assert.equal(shared.status, 200); assert.deepEqual(shared.body.requested_fields, ['status']); assert.equal(shared.body.status, 'active'); assert.equal(shared.body.version, null)
  assert.deepEqual(Object.keys(shared.body).sort(), ['is_synthetic', 'requested_fields', 'resource_id', 'resource_type', 'status', 'version'])
  passed('Recipient independently accepts in own session; current shared seam returns only selected metadata, no owner proof or domain payload')

  await reread(owner); await owner.getByTestId('grant-effective').filter({ hasText: '当前有效' }).waitFor()
  await owner.screenshot({ path: resolve(cache, 'sharing-desktop.png'), fullPage: true })
  await owner.locator('.sharing-panel').screenshot({ path: resolve(cache, 'sharing-desktop-panel.png') })
  await recipient.setViewportSize({ width: 390, height: 844 })
  assert.ok(await recipient.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  await owner.setViewportSize({ width: 390, height: 844 })
  assert.ok(await owner.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  const sizes = await owner.locator('input[type="checkbox"]').evaluateAll(inputs => inputs.map(input => ({ width: input.getBoundingClientRect().width, height: input.getBoundingClientRect().height })))
  assert.ok(sizes.length >= 1 && sizes.every(size => size.width >= 16 && size.width <= 20 && size.height >= 16 && size.height <= 20))
  await owner.screenshot({ path: resolve(cache, 'sharing-mobile.png'), fullPage: true })
  await owner.locator('.sharing-panel').screenshot({ path: resolve(cache, 'sharing-mobile-panel.png') })
  await storageEmpty(owner); await storageEmpty(recipient)
  passed('Desktop/390px layouts retain compact checkboxes and no overflow; both isolated contexts have no tokens or readable cookies/storage')

  const revoked = owner.waitForResponse(r => new URL(r.url()).pathname === `/api/v2/access-grants/${first.id}` && r.request().method() === 'DELETE')
  await owner.getByTestId(`revoke-grant-${first.id}`).click(); const withdrawal = await revoked
  assert.equal(withdrawal.status(), 200); protectedResponse(withdrawal); assert.equal(withdrawal.request().postData(), null)
  assert.equal((await withdrawal.json()).data.grant.state, 'revoked')
  await owner.getByTestId(`grant-${first.id}`).filter({ hasText: '已撤销' }).waitFor()
  await reread(recipient); await recipient.getByTestId(`grant-${first.id}`).filter({ hasText: '已撤销' }).waitFor()
  assert.equal(await recipient.getByTestId(`accept-grant-${first.id}`).count(), 0)
  assert.equal((await projection(recipient, fixture.resource_id)).status, 404)
  passed('Owner bodyless revocation is confirmed by HTTP; received list shows revoked and old shared access is denied')

  const second = await createGrant(owner, fixture, expires)
  await reread(recipient); await recipient.getByTestId(`grant-${second.id}`).waitFor()
  const refused = recipient.waitForResponse(r => new URL(r.url()).pathname === `/api/v2/access-grants/${second.id}` && r.request().method() === 'DELETE')
  await recipient.getByTestId(`revoke-grant-${second.id}`).click()
  assert.equal((await refused).status(), 200)
  await recipient.getByTestId(`grant-${second.id}`).filter({ hasText: '已撤销' }).waitFor()
  passed('Recipient can refuse a pending grant without acquiring a student role or accepting any scope')

  // Recipient revocation advances the owner's revision. Refresh explicitly;
  // never replay a stale positive confirmation behind the user's back.
  await reread(owner)
  const third = await createGrant(owner, fixture, expires)
  await reread(recipient); await recipient.getByTestId(`grant-${third.id}`).waitFor()
  await recipient.getByTestId(`accept-confirm-${third.id}`).check()
  await recipient.getByTestId(`accept-grant-${third.id}`).click()
  await recipient.getByTestId(`grant-${third.id}`).getByTestId('grant-effective').filter({ hasText: '当前有效' }).waitFor()
  await control('/__test__/expire-grants'); await reread(recipient)
  await recipient.getByTestId(`grant-${third.id}`).getByTestId('grant-effective').filter({ hasText: '无有效访问' }).waitFor()
  assert.equal((await projection(recipient, fixture.resource_id)).status, 404)
  passed('Expired grant remains historically accepted while current access is false; shared read is denied')

  await reread(owner)
  const fourth = await createGrant(owner, fixture, new Date(Date.now() + 1800000).toISOString().slice(0, 19))
  await reread(recipient); await recipient.getByTestId(`grant-${fourth.id}`).waitFor()
  await control('/__test__/notice-damaged')
  await reread(owner); await reread(recipient)
  await owner.getByTestId('sharing-policy-unavailable').waitFor()
  await recipient.getByTestId('sharing-policy-unavailable').waitFor()
  assert.equal(await owner.getByTestId('create-grant').count(), 0)
  assert.equal(await recipient.getByTestId(`accept-grant-${fourth.id}`).count(), 0)
  assert.equal(await owner.getByTestId(`revoke-grant-${third.id}`).isEnabled(), true)
  assert.equal(await recipient.getByTestId(`revoke-grant-${third.id}`).innerText(), '退出此项共享')
  await owner.locator('.sharing-panel').screenshot({ path: resolve(cache, 'sharing-policy-unavailable.png') })
  const negative = recipient.waitForResponse(r => new URL(r.url()).pathname === `/api/v2/access-grants/${fourth.id}` && r.request().method() === 'DELETE')
  await recipient.getByTestId(`revoke-grant-${fourth.id}`).click()
  const decreased = await negative; assert.equal(decreased.status(), 200); protectedResponse(decreased)
  await recipient.getByTestId(`grant-${fourth.id}`).filter({ hasText: '已撤销' }).waitFor()
  passed('Damaged notice returns policy 503 but independent management lists retain owner revoke and recipient refusal/exit; recipient DELETE still succeeds')

  await control('/__test__/sharing-closed'); await reread(owner)
  await owner.getByTestId('sharing-closed').waitFor()
  assert.equal(await owner.getByTestId('create-grant').count(), 0)
  assert.equal(await owner.getByTestId(`revoke-grant-${third.id}`).count(), 1)
  await owner.screenshot({ path: resolve(cache, 'sharing-closed.png'), fullPage: true })
  passed('Closed sharing hides collection while existing owner revocation remains available')

  await control('/__test__/advance')
  await recipient.getByRole('button', { name: '重新读取共享设置', exact: true }).click()
  await recipient.getByRole('link', { name: '通过身份供应商登录' }).waitFor()
  assert.equal(await recipient.getByTestId('actor-id').count(), 0)
  assert.equal(await recipient.locator('.sharing-grant').count(), 0); assert.equal(await recipient.locator('form').count(), 0)
  await storageEmpty(recipient); assert.deepEqual(pageErrors, []); assert.deepEqual(blockedRequests, [])
  passed('Current sharing 401 clears identity, grants and confirmations; all requests stay on fixed loopback origins without page errors')
  report = { status: 'passed', browser: await browser.version(), mode: 'auth', data: 'synthetic-only', checks, page_errors: pageErrors, blocked_requests: blockedRequests,
    not_executed: ['Production PostgreSQL (independent security tests)', 'Real Keycloak/accounts/deployment/TLS', 'Real student/domain payload or file sharing', 'Legal/controller review or guardian verification', 'Production grant-duration policy'], cache_directory: cache }
} catch (error) {
  report = { status: 'failed', checks, error: safeMessage(error), page_errors: pageErrors, blocked_requests: blockedRequests, cache_directory: cache }
  if (owner) await owner.screenshot({ path: resolve(cache, 'sharing-failure.png'), fullPage: true, timeout: 5000 }).catch(() => {})
  process.exitCode = 1
} finally {
  if (browser) await browser.close()
  for (const child of children.reverse()) if (child.exitCode === null) { child.kill(); await new Promise(success => { child.once('exit', success); setTimeout(success, 1500).unref() }) }
  if (report) { await writeFile(resolve(cache, 'report.json'), JSON.stringify(report, null, 2)).catch(() => {}); console.log(JSON.stringify(report, null, 2)) }
}
