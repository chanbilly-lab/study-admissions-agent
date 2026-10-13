// T21 real-browser driver: synthetic cookies arrive through stdin only.
// Runtime API responses are never mocked; only non-loopback egress is blocked.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createHash, randomUUID } from 'node:crypto'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
let input = ''
for await (const chunk of process.stdin) {
  input += chunk
  if (Buffer.byteLength(input) > 65536) throw new Error('T21 browser fixture is too large')
}
const fixture = JSON.parse(input)
assert.match(fixture.origin, /^http:\/\/127\.0\.0\.1:[0-9]+$/)
const cache = resolve(root, '.cache/t21-ui', randomUUID())
await mkdir(cache, { recursive: true })
const checks = [], pageErrors = [], blockedRequests = []
let browser, admin, student, report
const fileHashes = []
function passed(message) { checks.push(message) }
function safeError(error) {
  let message = String(error?.message ?? error)
  for (const secret of [fixture.admin_cookie, fixture.student_cookie, fixture.control_key]) {
    if (secret) message = message.split(secret).join('[redacted fixture]')
  }
  return message.replace(/https?:\/\/[^\s"'<>]+/g, '[URL]').slice(0, 3000)
}
async function setupPage(cookie) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  await context.addCookies([{ name: '__Host-admissions-session', value: cookie,
    domain: '127.0.0.1', path: '/', secure: true, httpOnly: true, sameSite: 'Lax' }])
  await context.route('**/*', async route => {
    const url = new URL(route.request().url())
    if (url.origin !== fixture.origin) {
      blockedRequests.push(url.origin + url.pathname)
      await route.abort('blockedbyclient')
      return
    }
    assert.ok(!route.request().headers().authorization, 'No Bearer credential is supplied to the browser')
    await route.continue()
  })
  const page = await context.newPage()
  page.setDefaultTimeout(20000)
  page.on('pageerror', error => pageErrors.push(safeError(error)))
  await page.goto(fixture.origin)
  return page
}
function privateResponse(response) {
  assert.equal(response.headers()['cache-control'], 'no-store')
  assert.equal(response.headers()['referrer-policy'], 'no-referrer')
}
async function noBrowserSecrets(page) {
  assert.deepEqual(await page.evaluate(() => ({ local: Object.keys(localStorage),
    session: Object.keys(sessionStorage), readableCookies: document.cookie })),
  { local: [], session: [], readableCookies: '' })
}

async function api(page, path, { method = 'GET', input, key, csrf = true } = {}) {
  return page.evaluate(async ({ path, method, input, key, csrf }) => {
    const headers = { Accept: 'application/json' }
    if (method !== 'GET' && csrf) {
      const proof = await fetch('/api/v2/auth/csrf', { credentials: 'same-origin', cache: 'no-store' })
      if (proof.status !== 200) return { status: proof.status }
      headers['X-CSRF-Token'] = (await proof.json()).data.csrf_token
    }
    if (input !== undefined) headers['Content-Type'] = 'application/json'
    if (key) headers['Idempotency-Key'] = key
    const response = await fetch('/api/v2/' + path, { method, credentials: 'same-origin', cache: 'no-store',
      headers, ...(input !== undefined ? { body: JSON.stringify(input) } : {}) })
    return { status: response.status, body: await response.json(), headers: Object.fromEntries(response.headers) }
  }, { path, method, input, key, csrf })
}
async function upload(page, rows, name) {
  // File input preserves actual CRLF original bytes rather than a textarea
  // newline normalization. T14 validates the original, T15 parses candidates.
  const content = JSON.stringify(rows, null, 2).replaceAll('\n', '\r\n')
  const bytes = Buffer.from(content, 'utf8')
  await page.getByTestId('original-file-input').setInputFiles({ name, mimeType: 'application/json', buffer: bytes })
  await page.getByTestId('original-confirm').waitFor()
  assert.equal(await page.getByTestId('original-confirm').isChecked(), false)
  assert.equal(await page.getByTestId('original-upload').isDisabled(), true)
  await page.getByTestId('original-confirm').check()
  const written = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/admin/source-files'
    && r.request().method() === 'POST')
  await page.getByTestId('original-upload').click()
  const response = await written
  assert.equal(response.status(), 200); privateResponse(response)
  assert.equal(response.request().headers().origin, fixture.origin)
  assert.ok(response.request().headers()['x-csrf-token'])
  assert.equal(response.request().postDataJSON().content_utf8, content)
  const file = (await response.json()).data
  const expectedHash = createHash('sha256').update(bytes).digest('hex')
  assert.equal(file.sha256, expectedHash); assert.equal(file.size_bytes, bytes.length)
  assert.equal(file.namespace, 'source_quarantine'); assert.equal(file.status, 'quarantined')
  assert.ok(!('filename' in file) && !('owner_user_id' in file) && !('path' in file))
  fileHashes.push(expectedHash)
  await page.getByTestId('file-receipt').waitFor()
  return file
}
async function submitImport(page) {
  assert.equal(await page.getByTestId('import-confirm').isChecked(), false)
  assert.equal(await page.getByTestId('import-submit').isDisabled(), true)
  await page.getByTestId('import-confirm').check()
  const written = page.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/admin/imports'
    && r.request().method() === 'POST')
  await page.getByTestId('import-submit').click()
  const response = await written
  assert.equal(response.status(), 200); privateResponse(response)
  assert.equal(response.request().headers().origin, fixture.origin)
  assert.ok(response.request().headers()['x-csrf-token'])
  assert.match(response.request().headers()['idempotency-key'], /^[0-9a-f-]{36}$/)
  const body = await response.json()
  assert.equal(body.meta.request_id, response.headers()['x-request-id'])
  await page.getByTestId('import-result').waitFor()
  return { result: body.data, request: response.request().postDataJSON(), key: response.request().headers()['idempotency-key'] }
}

try {
  const moduleName = process.env.T21_PLAYWRIGHT_MODULE ?? resolve(process.env.USERPROFILE ?? '',
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs')
  const playwright = await import(pathToFileURL(resolve(moduleName)).href)
  browser = await playwright.chromium.launch({ headless: true, channel: 'msedge' })
  admin = await setupPage(fixture.admin_cookie)
  student = await setupPage(fixture.student_cookie)
  await admin.getByTestId('source-save').waitFor()
  await student.getByTestId('context-status').waitFor()
  const studentContext = await api(student, 'admin/context')
  assert.equal(studentContext.status, 403)
  assert.equal(studentContext.headers['cache-control'], 'no-store')
  assert.equal(await student.getByTestId('source-save').count(), 0)
  assert.equal(await student.getByTestId('original-upload').count(), 0)
  passed('Server-issued admin and student cookies use separate real contexts; student GET403 and management forms are absent')

  const publisher = 'DEMO_<img src="https://source-sentinel.invalid/x" onerror="window.__t21Xss=1">'
  const scope = 'DEMO_2026 synthetic scope <script>window.__t21Xss=1</script>'
  await admin.getByTestId('source-dataset').fill(fixture.dataset_id)
  await admin.getByTestId('source-dataset-revision').fill(String(fixture.dataset_revision))
  await admin.getByTestId('source-reference').fill('DEMO_T21_BROWSER_SOURCE')
  await admin.getByTestId('source-publisher').fill(publisher)
  await admin.getByTestId('source-url').fill('https://source-sentinel.invalid/DEMO_2026?metadata_only=1')
  await admin.getByTestId('source-data-type').selectOption('entry_requirements')
  await admin.getByTestId('source-scope').fill(scope)
  await admin.getByTestId('source-authority').selectOption('claimed_official')
  await admin.getByTestId('source-manual-permission').selectOption('granted')
  await admin.getByTestId('source-publication-permission').selectOption('denied')
  await admin.getByTestId('source-auto-permission').selectOption('pending')
  await admin.getByTestId('source-basis').fill('DEMO_T21_SYNTHETIC_MANUAL_ONLY')
  await admin.getByTestId('source-permission-reference').fill('DEMO_T21_PERMISSION')
  await admin.getByTestId('source-recheck').fill('1')
  await admin.getByTestId('source-manual-enabled').check()
  assert.equal(await admin.getByTestId('source-confirm').isChecked(), false)
  assert.equal(await admin.getByTestId('source-save').isDisabled(), true)
  await admin.getByTestId('source-confirm').check()
  const registration = admin.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/admin/sources'
    && r.request().method() === 'POST')
  // Real keyboard activation demonstrates an operable labeled native button.
  await admin.getByTestId('source-save').focus()
  await admin.keyboard.press('Enter')
  const registered = await registration
  assert.equal(registered.status(), 200); privateResponse(registered)
  assert.equal(registered.request().headers().origin, fixture.origin)
  assert.ok(registered.request().headers()['x-csrf-token'])
  const source = (await registered.json()).data
  assert.equal(source.publisher, publisher); assert.equal(source.scope_note, scope)
  assert.equal(source.auto_fetch_enabled, false); assert.ok(!('responsible_user_id' in source))
  await admin.getByTestId('source-result').waitFor()
  assert.ok((await admin.getByTestId('source-result').innerText()).includes(publisher))
  assert.equal(await admin.getByTestId('source-result').locator('img,script,a').count(), 0)
  assert.equal(await admin.evaluate(() => window.__t21Xss), undefined)
  assert.deepEqual(blockedRequests, [])
  passed('Keyboard confirmed source registration uses actual CSRF/Origin; escaped publisher/scope and metadata URL produce no external visit or XSS')

  const registrationInput = registered.request().postDataJSON()
  const studentWrite = await api(student, 'admin/sources', { method: 'POST', input: registrationInput })
  assert.equal(studentWrite.status, 403)
  assert.equal(studentWrite.headers['cache-control'], 'no-store')
  passed('Authenticated student with an actual session CSRF proof still cannot register a source')

  // Existing T14 JSON syntax deliberately rejects a BOM. The HTTP/UI layer
  // must preserve it, return the actual 422, and never strip it to fake success.
  const bomOriginal = '\uFEFF' + JSON.stringify(fixture.rows)
  await admin.getByTestId('original-file-input').setInputFiles({ name: 'DEMO_T21_BOM.json',
    mimeType: 'application/json', buffer: Buffer.from(bomOriginal, 'utf8') })
  await admin.getByTestId('original-confirm').check()
  const bomRejected = admin.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/admin/source-files'
    && r.request().method() === 'POST')
  await admin.getByTestId('original-upload').click()
  const bomResponse = await bomRejected
  assert.equal(bomResponse.status(), 422); privateResponse(bomResponse)
  assert.equal(bomResponse.request().postDataJSON().content_utf8, bomOriginal)
  await admin.getByTestId('admin-message').filter({ hasText: /未确认/ }).waitFor()
  assert.equal(await admin.getByTestId('file-receipt').count(), 0)
  passed('JSON BOM is sent unchanged and existing strict storage rejects422; the UI never strips bytes or reports an upload success')

  const badRows = structuredClone(fixture.rows)
  badRows[1].value_text = 'DEMO_T21_PRIVATE_BAD_DECIMAL'
  await upload(admin, badRows, 'DEMO_T21_BAD.json')
  const rejected = await submitImport(admin)
  assert.equal(rejected.result.status, 'rejected')
  assert.equal(rejected.result.total_rows, 3); assert.equal(rejected.result.staged_rows, 0)
  assert.ok(rejected.result.errors.some(error => error.code === 'INVALID_DECIMAL'))
  assert.ok(!JSON.stringify(rejected.result).includes('DEMO_T21_PRIVATE_BAD_DECIMAL'))
  assert.ok((await admin.getByTestId('import-result').innerText()).includes('拒绝'))
  assert.ok(!(await admin.getByTestId('import-errors').innerText()).includes('DEMO_T21_PRIVATE_BAD_DECIMAL'))
  passed('CRLF original bytes are preserved; bad decimal gives a durable whole-batch rejection with zero staged candidates and safe errors')

  await upload(admin, fixture.rows, 'DEMO_T21_VALID.json')
  const staged = await submitImport(admin)
  assert.equal(staged.result.status, 'staged'); assert.equal(staged.result.staged_rows, 3)
  assert.equal(staged.result.error_count, 0)
  const resultText = await admin.getByTestId('import-result').innerText()
  assert.match(resultText, /待|候选|审核|未发布/)
  passed('Three complete original records, including two fields sharing one source reference, stage as unreviewed candidates through real services')

  const replay = await api(admin, 'admin/imports', { method: 'POST', input: staged.request, key: staged.key })
  assert.equal(replay.status, 200); assert.equal(replay.body.data.id, staged.result.id)
  assert.equal(replay.body.data.replayed, true); assert.equal(replay.headers['cache-control'], 'no-store')
  const missingCsrf = await api(admin, 'admin/imports', { method: 'POST', input: staged.request,
    key: randomUUID(), csrf: false })
  assert.equal(missingCsrf.status, 403)
  assert.equal(missingCsrf.headers['cache-control'], 'no-store')
  passed('Browser retry with the exact idempotency key returns the same receipt; a current cookie without CSRF is rejected403')

  await noBrowserSecrets(admin); await noBrowserSecrets(student)
  await admin.getByTestId('admin-workspace').screenshot({ path: resolve(cache, 'admin-desktop.png') })
  await admin.setViewportSize({ width: 390, height: 844 })
  await student.setViewportSize({ width: 390, height: 844 })
  assert.ok(await admin.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  assert.ok(await student.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  await admin.getByTestId('admin-workspace').screenshot({ path: resolve(cache, 'admin-mobile.png') })
  passed('Desktop and 390px layouts have no horizontal overflow; both contexts keep proofs out of readable cookies and browser storage')

  const control = await fetch(fixture.origin + '/__test__/revoke-admin', { method: 'POST',
    headers: { 'X-T21-Fixture-Key': fixture.control_key } })
  assert.equal(control.status, 200)
  const revoked = await api(admin, 'admin/imports', { method: 'POST', input: staged.request, key: staged.key })
  assert.equal(revoked.status, 403)
  // The already-rendered page must also respond to a real server refusal.
  await admin.getByTestId('import-query-id').fill(staged.result.id)
  const staleRead = admin.waitForResponse(r => new URL(r.url()).pathname === '/api/v2/admin/imports/' + staged.result.id)
  await admin.getByTestId('import-query-button').click()
  assert.equal((await staleRead).status(), 403)
  await admin.getByTestId('context-status').filter({ hasText: /未获授权/ }).waitFor()
  assert.equal(await admin.getByTestId('source-save').count(), 0)
  assert.equal(await admin.getByTestId('import-result').count(), 0)
  passed('Server role revocation rejects receipt replay and current UI reads; stale management forms and private results are cleared')

  assert.deepEqual(pageErrors, []); assert.deepEqual(blockedRequests, [])
  report = { status: 'passed', browser: await browser.version(), checks, page_errors: pageErrors,
    blocked_requests: blockedRequests, file_hashes: fileHashes, cache_directory: cache,
    not_executed: ['Real Keycloak login/MFA', 'Real sources or student data', 'Production deployment/TLS',
      'Human legal/source-permission review', 'T22 review/publication UI'] }
} catch (error) {
  report = { status: 'failed', checks, error: safeError(error), page_errors: pageErrors,
    blocked_requests: blockedRequests, cache_directory: cache }
  if (admin) await admin.screenshot({ path: resolve(cache, 'admin-failure.png'), fullPage: true }).catch(() => {})
  process.exitCode = 1
} finally {
  if (browser) await browser.close()
  await writeFile(resolve(cache, 'report.json'), JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report))
}
