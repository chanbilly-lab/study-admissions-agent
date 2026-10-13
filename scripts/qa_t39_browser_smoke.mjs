// T39 actual Edge/public HTTP/PG; routes only block non-loopback requests.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { randomUUID } from 'node:crypto'
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
let input = ''
for await (const chunk of process.stdin) { input += chunk; assert.ok(Buffer.byteLength(input) <= 16384) }
const fixture = JSON.parse(input)
assert.match(fixture.origin, /^http:\/\/127\.0\.0\.1:[0-9]+$/)
const cache = resolve(root, '.cache/t39-ui', randomUUID())
await mkdir(cache, { recursive: true })
const checks = [], pageErrors = [], blockedRequests = [], apiConfigRequests = [], events = []
let browser, page, report, step = 'start'
function safeError(error) { return String(error?.message ?? error).split(fixture.control).join('[redacted]').replace(/https?:\/\/[^\s"'<>]+/g, '[URL]').slice(0, 2500) }
async function bounded(label, work, ms = 30000) {
  let timer
  try { return await Promise.race([work(), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('T39 timeout: ' + label)), ms) })]) }
  finally { clearTimeout(timer) }
}
function passed(message) { checks.push(message); step = message }
async function action(selector, path, method = 'GET', keyboard = false) {
  const pending = page.waitForResponse(r => new URL(r.url()).pathname === path && r.request().method() === method)
  const element = page.getByTestId(selector)
  if (keyboard) { await element.focus(); await page.keyboard.press('Enter') } else await element.click()
  const response = await bounded(path, () => pending)
  assert.equal(response.status(), 200)
  assert.equal(response.headers()['cache-control'], 'no-store')
  assert.match(response.headers()['x-request-id'], /^[0-9a-f]{32}$/)
  const envelope = await bounded('body', () => response.json())
  assert.equal(envelope.meta.request_id, response.headers()['x-request-id'])
  return { data: envelope.data, request: method === 'POST' ? response.request().postDataJSON() : null }
}
async function control(action) {
  return bounded('control', () => page.evaluate(async ({ action, proof }) => {
    const response = await fetch('/__t39/control', { method: action ? 'POST' : 'GET', cache: 'no-store',
      headers: { 'X-T39-Control': proof, ...(action ? { 'Content-Type': 'application/json' } : {}) },
      ...(action ? { body: JSON.stringify({ action }) } : {}) })
    if (response.status !== 200) throw new Error('Control unavailable')
    return response.json()
  }, { action, proof: fixture.control }))
}
async function waitControl(field) {
  return bounded('actual completed response ' + field, async () => {
    for (;;) { const state = await control(); if (state[field]) return state; await new Promise(r => setTimeout(r, 75)) }
  })
}
try {
  const module = resolve(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs')
  const { chromium } = await import(pathToFileURL(module).href)
  browser = await chromium.launch({ channel: 'msedge', headless: true })
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url())
    if (url.origin !== fixture.origin) { blockedRequests.push(url.pathname); await route.abort('blockedbyclient'); return }
    const headers = await request.allHeaders()
    assert.ok(!headers.authorization && !headers.cookie, 'Anonymous public QA carries no identity or private cookie')
    if (url.pathname.startsWith('/api/v2/')) apiConfigRequests.push(url.pathname)
    if (url.pathname.startsWith('/qa/v2/')) events.push({ path: url.pathname, method: request.method() })
    await route.continue()
  })
  page = await context.newPage()
  page.setDefaultTimeout(30000)
  page.on('pageerror', error => pageErrors.push(safeError(error)))
  await page.goto(fixture.origin)
  await page.getByTestId('catalog-toggle').waitFor()
  assert.equal(events.length, 0)
  passed('Initial screen issues no QA request')
  await action('catalog-toggle', '/public/v2/config', 'GET', true)
  await page.getByTestId('catalog-year').fill(String(fixture.year))
  const listing = await action('catalog-search', '/public/v2/offerings')
  assert.equal(listing.data.items[0].id, fixture.offering_id)
  await page.getByTestId(`catalog-select-${fixture.offering_id}-${fixture.version}`).click()
  await page.getByTestId('qa-toggle').click()
  assert.equal(events.length, 0)
  passed('Actual published project is explicitly selected; opening QA performs no fetch')
  await page.getByTestId('qa-intent').selectOption('requirements')
  const capability = await action('qa-context-refresh', '/qa/v2/qa/context', 'GET', true)
  assert.equal(capability.data.can_ask, true)
  assert.equal(capability.data.model_mode, 'mock')
  assert.equal(capability.data.live_available, false)
  await page.getByTestId('qa-demo').waitFor()
  passed('Explicit server check shows DEMO/mock and closed live')
  const answer = await action('qa-ask', '/qa/v2/qa/answers', 'POST', true)
  assert.equal(answer.data.status, 'answered')
  assert.equal(answer.request.offering_id, fixture.offering_id)
  assert.equal(answer.request.release_id, fixture.release_id)
  assert.deepEqual(Object.keys(answer.request).sort(), ['entry_year','intent','keywords','offering_id','offering_version','release_id','scope'].sort())
  assert.ok(!JSON.stringify(answer.request).match(/profile_id|owner_id|grades|question|prompt/))
  await page.getByTestId('qa-result').waitFor()
  assert.equal(await page.getByTestId('qa-fact-value').textContent(), '600.00')
  passed('Actual PG-backed answer keeps exact 600.00 and sends only finite public scope')
  const citation = answer.data.citations[0]
  await page.getByTestId(`qa-original-${citation.id}`).locator('summary').click()
  assert.equal(await page.getByTestId(`qa-original-${citation.id}`).locator('pre').textContent(), citation.evidence.quote)
  assert.equal(await page.getByTestId(`qa-citation-${citation.id}`).locator('script,img,iframe,a[href]').count(), 0)
  passed('Returned source quote is shown as plain text with no executable element or link')
  await page.getByTestId('qa-intent').selectOption('fees')
  assert.equal(await page.getByTestId('qa-result').count(), 0)
  const unknown = await action('qa-ask', '/qa/v2/qa/answers', 'POST')
  assert.equal(unknown.data.status, 'unknown')
  assert.deepEqual(unknown.data.citations, [])
  await page.getByTestId('qa-unknown').waitFor()
  passed('Intent change clears old answer; missing fee facts remain unknown')
  await page.getByTestId('qa-intent').selectOption('requirements')
  await control('arm')
  await page.getByTestId('qa-ask').click()
  const delayed = await waitControl('blocked')
  assert.equal(delayed.status, 200)
  await page.getByTestId('qa-intent').selectOption('fees')
  assert.equal(await page.getByTestId('qa-result').count(), 0)
  await control('release'); await waitControl('completed')
  assert.equal(await page.getByTestId('qa-result').count(), 0)
  passed('Changed intent rejects delivery of a completed actual successful old answer')
  await page.getByTestId('qa-toggle').click()
  assert.equal(await page.getByTestId('qa-workspace').count(), 0)
  assert.deepEqual(await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage) })), { local: [], session: [] })
  passed('Fold/unmount leaves no response or browser persistence; no private student records were read')
  assert.deepEqual([...apiConfigRequests].sort(), ['/api/v2/auth/session', '/api/v2/privacy/notices/current', '/api/v2/sharing/policy'])
  assert.deepEqual(pageErrors, []); assert.deepEqual(blockedRequests, [])
  report = { status: 'passed', browser: await browser.version(), checks, page_errors: pageErrors,
    blocked_requests: blockedRequests, api_config_requests: apiConfigRequests, network_events: events, cache_directory: cache }
} catch (error) {
  report = { status: 'failed', step, error: safeError(error), checks, page_errors: pageErrors,
    blocked_requests: blockedRequests, api_config_requests: apiConfigRequests, network_events: events, cache_directory: cache }
} finally {
  if (page) try { await control('release') } catch {}
  if (browser) await browser.close()
}
await writeFile(resolve(cache, 'report.json'), JSON.stringify(report, null, 2))
process.stdout.write(JSON.stringify(report) + '\n')
if (report.status !== 'passed') process.exitCode = 1
