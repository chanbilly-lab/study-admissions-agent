// T06 only: fresh browser context, local TLS IdP and an isolated synthetic DB.
// No existing browser profile, M0 server, production account or network is used.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { randomBytes, randomUUID } from 'node:crypto'
import { mkdir, writeFile } from 'node:fs/promises'
import net from 'node:net'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const webOrigin = 'http://127.0.0.1:5186'
const apiOrigin = 'http://127.0.0.1:8000'
const idpOrigin = 'https://127.0.0.1:9444'
const allowedOrigins = new Set([webOrigin, apiOrigin, idpOrigin])
const cacheParent = resolve(root, '.cache/t06-browser')
const cache = resolve(cacheParent, randomUUID())
const fixtureKey = randomBytes(32).toString('base64url')
const children = []
const checks = []
const pageErrors = []
const blockedRequests = []
let browser, page, report

function safeMessage(error) {
  return String(error?.message ?? error).replace(/https?:\/\/[^\s"'<>]+/g, (value) => {
    try { const url = new URL(value); return url.origin + url.pathname }
    catch { return '[redacted URL]' }
  }).replace(/(?:code|state|nonce|code_verifier|id_token)=[^\s&]+/gi, '[redacted proof]')
}

async function assertPortFree(port) {
  const server = net.createServer()
  await new Promise((resolvePromise, reject) => {
    server.once('error', () => reject(new Error(`T06 port ${port} is occupied; existing processes are preserved`)))
    server.listen(port, '127.0.0.1', resolvePromise)
  })
  await new Promise(resolvePromise => server.close(resolvePromise))
}

function launch(command, args, env) {
  const child = spawn(command, args, { cwd: root, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  let diagnostics = ''
  for (const stream of [child.stdout, child.stderr]) {
    stream.on('data', chunk => { diagnostics = (diagnostics + chunk.toString()).slice(-4096) })
  }
  child.on('error', error => { diagnostics = safeMessage(error) })
  children.push(child)
  return { child, diagnostics: () => diagnostics }
}

async function waitReady(url, processInfo, headers = {}) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (processInfo.child.exitCode !== null) {
      throw new Error(`T06 child exited before readiness: ${safeMessage(processInfo.diagnostics())}`)
    }
    try {
      const response = await fetch(url, { headers, signal: AbortSignal.timeout(700) })
      if (response.ok) return response
    } catch { /* bounded startup wait; only the fixed loopback URL is called */ }
    await new Promise(resolvePromise => setTimeout(resolvePromise, 200))
  }
  throw new Error(`T06 local startup did not complete: ${safeMessage(processInfo.diagnostics())}`)
}

async function control(path, method = 'POST') {
  assert.ok(['/__test__/advance', '/__test__/disable', '/__test__/stats'].includes(path))
  const response = await fetch(apiOrigin + path, { method, headers: { 'X-T06-Fixture-Key': fixtureKey } })
  assert.equal(response.status, 200)
  return response.json()
}

function protectedResponse(response) {
  assert.equal(response.headers()['cache-control'], 'no-store')
  assert.equal(response.headers()['referrer-policy'], 'no-referrer')
}

function safeCookies(headers, expectedName) {
  const cookie = headers.filter(h => h.name.toLowerCase() === 'set-cookie').map(h => h.value)
    .find(value => value.startsWith(expectedName + '=') && !value.includes('Max-Age=0'))
  assert.ok(cookie, `${expectedName} must be set`)
  for (const attribute of ['Secure', 'HttpOnly', 'SameSite=lax', 'Path=/']) {
    assert.ok(cookie.toLowerCase().includes(attribute.toLowerCase()))
  }
  assert.ok(!/;\s*Domain=/i.test(cookie))
}

async function emptyBrowserStorage(target) {
  assert.deepEqual(await target.evaluate(() => ({
    local: Object.keys(localStorage), session: Object.keys(sessionStorage), readableCookie: document.cookie,
  })), { local: [], session: [], readableCookie: '' })
}

async function newContext() {
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 900 } })
  // Self-signed TLS is accepted only in this disposable test context. All other
  // origins are denied, including analytics/fonts/real identity providers.
  await context.route('**/*', async route => {
    const request = route.request()
    const url = new URL(request.url())
    if (!allowedOrigins.has(url.origin)) {
      blockedRequests.push(url.origin + url.pathname)
      await route.abort('blockedbyclient')
      return
    }
    assert.ok(!request.headers().authorization, 'Browser must never receive/send an IdP Bearer token')
    if (url.origin === webOrigin && url.pathname.startsWith('/api/v2/auth/')) {
      assert.ok(!/profiles|admin/.test(url.pathname))
      if (url.pathname.endsWith('/login')) assert.equal(url.search, '')
    }
    await route.continue()
  })
  context.on('page', target => {
    target.on('pageerror', error => pageErrors.push(safeMessage(error)))
    target.on('websocket', socket => {
      const url = new URL(socket.url())
      if (url.host !== '127.0.0.1:5186') blockedRequests.push(url.origin + url.pathname)
    })
  })
  return context
}

async function beginLogin(target) {
  await target.goto(webOrigin)
  const link = target.getByRole('link', { name: '通过身份供应商登录' })
  await link.waitFor()
  assert.equal(await link.getAttribute('href'), '/api/v2/auth/login')
  const started = target.waitForResponse(response => new URL(response.url()).pathname === '/api/v2/auth/login')
  await link.click()
  const response = await started
  assert.equal(response.status(), 302)
  protectedResponse(response)
  safeCookies(await response.headersArray(), '__Host-admissions-login')
  const authorizationUrl = new URL(response.headers().location)
  assert.equal(authorizationUrl.origin, idpOrigin)
  assert.equal(authorizationUrl.pathname, '/realms/t06/protocol/openid-connect/auth')
  assert.equal(authorizationUrl.searchParams.get('redirect_uri'), webOrigin + '/api/v2/auth/callback')
  assert.equal(authorizationUrl.searchParams.get('code_challenge_method'), 'S256')
  assert.equal(authorizationUrl.searchParams.get('scope'), 'openid')
  assert.ok(!authorizationUrl.searchParams.has('return_path'))
  await target.getByRole('heading', { name: 'DEMO · 本机合成身份供应商' }).waitFor()
  return authorizationUrl
}

try {
  for (const port of [5186, 8000, 9444]) await assertPortFree(port)
  await mkdir(cacheParent, { recursive: true })
  const python = process.env.T06_PYTHON ?? resolve(root, '.venv/Scripts/python.exe')
  const fixture = launch(python, ['-B', resolve(root, 'tests/e2e/auth_t06_fixture.py'), '--cache-dir', cache,
    '--web-origin', webOrigin, '--api-port', '8000', '--idp-port', '9444'],
    { ...process.env, T06_FIXTURE_CONTROL_KEY: fixtureKey, PYTHONDONTWRITEBYTECODE: '1' })
  const readiness = await (await waitReady(apiOrigin + '/__test__/ready', fixture,
    { 'X-T06-Fixture-Key': fixtureKey })).json()
  assert.equal(readiness.is_synthetic, true)
  const vite = launch(process.execPath, [resolve(root, 'apps/web/node_modules/vite/bin/vite.js'), resolve(root, 'apps/web'),
    '--config', resolve(root, 'apps/web/vite.config.ts'), '--host', '127.0.0.1', '--port', '5186', '--strictPort'],
    { ...process.env, VITE_APP_MODE: 'auth', VITE_AUTH_API_BASE_URL: '/api' })
  // The existing project root and unchanged proxy are used without modifying M0.
  await waitReady(webOrigin, vite)
  const bundledPlaywright = resolve(process.env.USERPROFILE ?? '',
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs')
  const moduleName = process.env.T06_PLAYWRIGHT_MODULE ?? bundledPlaywright
  const playwright = await import(moduleName.startsWith('.') || moduleName.includes(':') || moduleName.startsWith('/')
    ? pathToFileURL(resolve(moduleName)).href : moduleName)
  browser = await playwright.chromium.launch({ headless: true, channel: 'msedge' })
  const context = await newContext()
  page = await context.newPage()
  await beginLogin(page)
  const callbackPromise = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v2/auth/callback')
  await page.getByRole('button', { name: '继续使用合成主体', exact: true }).click()
  const callback = await callbackPromise
  assert.equal(callback.status(), 303)
  assert.equal(callback.headers().location, '/')
  protectedResponse(callback)
  safeCookies(await callback.headersArray(), '__Host-admissions-session')
  await page.getByTestId('actor-id').waitFor()
  assert.equal(await page.getByTestId('actor-id').innerText(), readiness.user_id)
  assert.match(await page.getByTestId('synthetic-banner').innerText(), /DEMO/)
  checks.push('Fixed top-level authorization, real RS256 verification and registered synthetic actor')
  const session = await page.evaluate(async () => {
    const response = await fetch('/api/v2/auth/session', { credentials: 'same-origin', cache: 'no-store' })
    return { status: response.status, body: await response.json(), cache: response.headers.get('cache-control') }
  })
  assert.equal(session.status, 200)
  assert.deepEqual(Object.keys(session.body.data).sort(), ['authenticated', 'expires_at', 'is_synthetic', 'private_business_available', 'user_id'])
  assert.equal(session.body.data.authenticated, true)
  assert.equal(session.body.data.private_business_available, false)
  assert.equal(session.body.data.user_id, readiness.user_id)
  assert.equal(session.cache, 'no-store')
  const cookies = await context.cookies()
  assert.ok(cookies.some(cookie => cookie.name === '__Host-admissions-session' && cookie.secure
    && cookie.httpOnly && cookie.sameSite === 'Lax' && cookie.path === '/'))
  await emptyBrowserStorage(page)
  assert.equal(await page.locator('input').count(), 0)
  assert.equal(await page.getByRole('button', { name: /注册/ }).count(), 0)
  assert.equal(await page.getByRole('button', { name: '退出当前应用', exact: true }).count(), 1)
  checks.push('Secure HttpOnly host cookie actually sent on loopback; no readable cookie/token/browser storage')
  await page.reload()
  await page.getByTestId('actor-id').waitFor()
  assert.equal(await page.getByTestId('actor-id').innerText(), readiness.user_id)
  await page.screenshot({ path: resolve(cache, 'auth-desktop.png'), fullPage: true })
  checks.push('Page reload reads the same server-side session without persisted frontend credentials')
  await page.setViewportSize({ width: 390, height: 844 })
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  await page.screenshot({ path: resolve(cache, 'auth-mobile.png'), fullPage: true })
  checks.push('390px responsive view has no horizontal overflow')

  const csrfProof = await page.evaluate(async () => {
    const response = await fetch('/api/v2/auth/csrf', { credentials: 'same-origin', cache: 'no-store' })
    return { status: response.status, body: await response.json(), cache: response.headers.get('cache-control') }
  })
  assert.equal(csrfProof.status, 200)
  assert.equal(csrfProof.cache, 'no-store')
  assert.ok(/^[A-Za-z0-9_-]{43}$/.test(csrfProof.body.data.csrf_token))
  assert.equal(csrfProof.body.data.expires_at, session.body.data.expires_at)
  const secondProof = await page.evaluate(async () => (await (await fetch('/api/v2/auth/csrf', {
    credentials: 'same-origin', cache: 'no-store',
  })).json()).data)
  assert.ok(csrfProof.body.data.csrf_token === secondProof.csrf_token, 'CSRF is stable within the same session')
  const rejectedWrites = await page.evaluate(async () => {
    const statuses = []
    for (const headers of [{}, { 'X-CSRF-Token': 'U'.repeat(43) }]) {
      const response = await fetch('/api/v2/auth/logout', { method: 'POST', credentials: 'same-origin', headers })
      statuses.push(response.status)
    }
    const stillActive = await fetch('/api/v2/auth/session', { credentials: 'same-origin' })
    return { statuses, stillActive: stillActive.status }
  })
  assert.deepEqual(rejectedWrites, { statuses: [403, 403], stillActive: 200 })
  await emptyBrowserStorage(page)
  assert.ok(!(await page.locator('body').innerText()).includes(csrfProof.body.data.csrf_token), 'CSRF is not rendered in the page')
  checks.push('Stable session-bound CSRF is memory-only; missing/wrong proofs return 403 without revocation')

  // Hold an actual successful server read while the user exits. Aborting the
  // request and generation checks together prevent a late response restoring UI.
  let capturedRead
  let announceCaptured
  let releaseRead
  const captured = new Promise(resolvePromise => { announceCaptured = resolvePromise })
  const release = new Promise(resolvePromise => { releaseRead = resolvePromise })
  const delayedRead = async route => {
    capturedRead = await route.fetch({ maxRedirects: 0 })
    assert.equal(capturedRead.status(), 200)
    announceCaptured()
    await release
    await route.fulfill({ response: capturedRead }).catch(() => {}) // cancelled by logout
  }
  await page.route('**/api/v2/auth/session', delayedRead, { times: 1 })
  await page.getByRole('button', { name: '重新检查会话', exact: true }).click()
  let captureTimeout
  try {
    await Promise.race([captured, new Promise((_, reject) => {
      captureTimeout = setTimeout(() => reject(new Error('T06 delayed server read was not captured')), 15000)
    })])
  } finally { clearTimeout(captureTimeout) }
  assert.equal(await page.getByTestId('actor-id').count(), 0)
  const logoutPromise = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v2/auth/logout')
  await page.getByRole('button', { name: '退出当前应用', exact: true }).click()
  const exited = await logoutPromise
  assert.equal(exited.status(), 200)
  protectedResponse(exited)
  assert.deepEqual((await exited.json()).data, { logged_out: true })
  assert.equal(exited.request().headers().origin, webOrigin)
  assert.ok(exited.request().headers()['x-csrf-token'], 'Logout header includes memory CSRF')
  assert.equal(exited.request().postData(), null)
  const cleared = (await exited.headersArray()).filter(h => h.name.toLowerCase() === 'set-cookie')
    .some(h => h.value.startsWith('__Host-admissions-session=') && h.value.includes('Max-Age=0'))
  assert.ok(cleared, 'Success clears the host session cookie')
  releaseRead()
  await page.getByRole('link', { name: '通过身份供应商登录' }).waitFor()
  await page.unroute('**/api/v2/auth/session', delayedRead)
  assert.equal(await page.getByTestId('actor-id').count(), 0)
  await emptyBrowserStorage(page)
  checks.push('Confirmed logout clears UI/cookie; an in-flight successful read cannot restore identity')

  // Replay the old cookie in a separate disposable browser context. This proves
  // database revocation, rather than merely observing the original cookie delete.
  const replayContext = await newContext()
  await replayContext.addCookies(cookies)
  const replayPage = await replayContext.newPage()
  await replayPage.goto(webOrigin)
  await replayPage.getByRole('link', { name: '通过身份供应商登录' }).waitFor()
  await replayContext.addCookies(cookies)
  const revokedRead = await replayPage.evaluate(async () => (await fetch('/api/v2/auth/session', {
    credentials: 'same-origin',
  })).status)
  await replayContext.addCookies(cookies) // 401 clears cookies; replay the original value again for POST.
  const repeatedExit = await replayPage.evaluate(async token => {
    const logoutResponse = await fetch('/api/v2/auth/logout', {
      method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF-Token': token },
    })
    return logoutResponse.status
  }, csrfProof.body.data.csrf_token)
  assert.deepEqual({ session: revokedRead, repeatedLogout: repeatedExit }, { session: 401, repeatedLogout: 401 })
  await replayContext.close()
  await page.reload()
  await page.getByRole('link', { name: '通过身份供应商登录' }).waitFor()
  assert.equal(await page.getByTestId('actor-id').count(), 0)
  checks.push('Revoked cookie remains invalid on real HTTP reads/repeated logout; reload cannot revive session')

  await beginLogin(page)
  const reloginPromise = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v2/auth/callback')
  await page.getByRole('button', { name: '继续使用合成主体', exact: true }).click()
  assert.equal((await reloginPromise).status(), 303)
  await page.getByTestId('actor-id').waitFor()
  checks.push('A new explicit signed login creates a fresh application session')

  const unknownContext = await newContext()
  const unknownPage = await unknownContext.newPage()
  await beginLogin(unknownPage)
  const deniedPromise = unknownPage.waitForResponse(response => new URL(response.url()).pathname === '/api/v2/auth/callback')
  await unknownPage.getByRole('button', { name: '使用未登记合成主体', exact: true }).click()
  const denied = await deniedPromise
  assert.equal(denied.status(), 403)
  protectedResponse(denied)
  const deniedBody = await denied.json()
  assert.equal(deniedBody.error.code, 'FORBIDDEN')
  assert.ok(!JSON.stringify(deniedBody).includes('T06_SYNTHETIC_NOT_REGISTERED'))
  assert.ok(!(await unknownContext.cookies()).some(cookie => cookie.name === '__Host-admissions-session'))
  const stats = await control('/__test__/stats', 'GET')
  assert.equal(stats.user_count, 1)
  assert.equal(stats.code_exchanges, 3)
  assert.equal(stats.jwks_reads, 3)
  checks.push('Unregistered signed subject returns safe 403; no auto-registration or session')
  await unknownContext.close()

  await control('/__test__/advance')
  const expiredPromise = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v2/auth/csrf')
  await page.getByRole('button', { name: '退出当前应用', exact: true }).click()
  assert.equal((await expiredPromise).status(), 401)
  await page.getByRole('link', { name: '通过身份供应商登录' }).waitFor()
  assert.equal(await page.getByTestId('actor-id').count(), 0)
  await emptyBrowserStorage(page)
  checks.push('Expired session cannot obtain CSRF; logout treats 401 as invalid and clears displayed identity')
  await control('/__test__/disable')
  const closedPromise = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v2/auth/session')
  await page.getByRole('button', { name: '重新检查会话', exact: true }).click()
  assert.equal((await closedPromise).status(), 503)
  assert.match(await page.getByRole('alert').innerText(), /未启用或暂不可用/)
  assert.equal(await page.getByRole('link', { name: '通过身份供应商登录' }).count(), 0)
  assert.equal(await page.getByTestId('actor-id').count(), 0)
  checks.push('Disabled service returns visible 503 without synthetic fallback or login link')
  assert.deepEqual(pageErrors, [])
  assert.deepEqual(blockedRequests, [])
  checks.push('All browser requests stayed on fixed loopback origins; no browser page errors')
  report = { status: 'passed', browser: await browser.version(), mode: 'auth', data: 'synthetic-only',
    checks, page_errors: pageErrors, blocked_requests: blockedRequests,
    not_executed: ['Real Keycloak deployment/accounts', 'Production TLS', 'Administrator MFA/recovery', 'Keycloak SSO/all-device logout'],
    cache_directory: cache }
} catch (error) {
  if (page) await page.screenshot({ path: resolve(cache, 'auth-failure.png'), fullPage: true }).catch(() => {})
  report = { status: 'failed', checks, error: safeMessage(error), page_errors: pageErrors,
    blocked_requests: blockedRequests, cache_directory: cache }
  process.exitCode = 1
} finally {
  if (browser) await browser.close()
  // Only children created above are stopped; occupied/user-owned processes are preserved.
  for (const child of children.reverse()) {
    if (child.exitCode === null) {
      child.kill()
      await new Promise(resolvePromise => {
        child.once('exit', resolvePromise)
        setTimeout(resolvePromise, 1500).unref()
      })
    }
  }
  if (report) {
    await writeFile(resolve(cache, 'report.json'), JSON.stringify(report, null, 2)).catch(() => {})
    console.log(JSON.stringify(report, null, 2))
  }
}
