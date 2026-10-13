// T22 real browser: no pre-known row/evidence/fact/release IDs and no API mocks.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createHash, randomUUID } from 'node:crypto'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
let input = ''
for await (const chunk of process.stdin) {
  input += chunk
  if (Buffer.byteLength(input) > 65536) throw new Error('T22 browser fixture is too large')
}
const fixture = JSON.parse(input)
assert.match(fixture.origin, /^http:\/\/127\.0\.0\.1:[0-9]+$/)
const cache = resolve(root, '.cache/t22-ui', randomUUID())
await mkdir(cache, { recursive: true })
const checks = [], pageErrors = [], blockedRequests = [], publicRequests = []
let browser, preparer, reviewer, report
const ids = {}, checkFields = ['original_value', 'claim_kind', 'unit', 'period', 'scope',
  'evidence_location', 'missingness', 'footnote', 'statistics_context', 'date_context']
const classification = { claim_kind: 'minimum_requirement', unit_code: 'points', period: 'not_applicable',
  statistics_basis: 'not_applicable', statistic_population: null, statistic_denominator: null,
  cohort_year: null, survey_period: null, date_event_id: null }
const explicitChecks = checkFields.map(field => ({ field,
  status: ['statistics_context', 'date_context'].includes(field) ? 'not_applicable' : 'accepted' }))
function passed(message) { checks.push(message) }
function safeError(error) {
  let message = String(error?.message ?? error)
  for (const secret of [fixture.preparer_cookie, fixture.reviewer_cookie]) {
    if (secret) message = message.split(secret).join('[redacted fixture]')
  }
  return message.replace(/https?:\/\/[^\s"'<>]+/g, '[URL]').slice(0, 3000)
}
async function setupPage(cookie) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  await context.addCookies([{ name: '__Host-admissions-session', value: cookie,
    domain: '127.0.0.1', path: '/', secure: true, httpOnly: true, sameSite: 'Lax' }])
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url())
    if (url.origin !== fixture.origin) {
      blockedRequests.push(url.origin + url.pathname)
      await route.abort('blockedbyclient')
      return
    }
    const headers = await request.allHeaders()
    assert.ok(!headers.authorization, 'No Bearer token is supplied to the browser')
    if (url.pathname.startsWith('/public/v2/')) {
      publicRequests.push({ path: url.pathname, cookie: Boolean(headers.cookie) })
      assert.ok(!headers.cookie, 'Public reads must omit the private cookie')
    }
    await route.continue()
  })
  const page = await context.newPage()
  page.setDefaultTimeout(45000)
  page.on('pageerror', error => pageErrors.push(safeError(error)))
  await page.goto(fixture.origin)
  return page
}
function privateResponse(response) {
  assert.equal(response.headers()['cache-control'], 'no-store')
  assert.equal(response.headers()['referrer-policy'], 'no-referrer')
}
async function api(page, path, { method = 'GET', body, key, csrf = true } = {}) {
  return page.evaluate(async ({ path, method, body, key, csrf }) => {
    const headers = { Accept: 'application/json' }
    if (method !== 'GET' && csrf) {
      const proof = await fetch('/api/v2/auth/csrf', { credentials: 'same-origin', cache: 'no-store' })
      if (proof.status !== 200) return { status: proof.status }
      headers['X-CSRF-Token'] = (await proof.json()).data.csrf_token
    }
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    if (key) headers['Idempotency-Key'] = key
    const response = await fetch('/api/v2/' + path, { method, credentials: 'same-origin', cache: 'no-store',
      headers, ...(body !== undefined ? { body: JSON.stringify(body) } : {}) })
    return { status: response.status, body: await response.json(), headers: Object.fromEntries(response.headers) }
  }, { path, method, body, key, csrf })
}
async function anonymous(page) {
  return page.evaluate(async () => {
    const response = await fetch('/public/v2/offerings?entry_year=2026', { credentials: 'omit', cache: 'no-store' })
    return { status: response.status, body: await response.json(), headers: Object.fromEntries(response.headers) }
  })
}
async function clickResponse(page, selector, path, method = 'POST', keyboard = false) {
  const pending = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v2/' + path
    && response.request().method() === method)
  if (keyboard) {
    await page.getByTestId(selector).focus()
    await page.keyboard.press('Enter')
  } else await page.getByTestId(selector).click()
  const response = await pending
  privateResponse(response)
  if (method !== 'GET') {
    assert.equal(response.request().headers().origin, fixture.origin)
    assert.ok(response.request().headers()['x-csrf-token'])
  }
  const envelope = await response.json()
  assert.equal(envelope.meta.request_id, response.headers()['x-request-id'])
  return { status: response.status(), data: envelope.data, envelope,
    request: method !== 'GET' ? response.request().postDataJSON() : undefined,
    key: response.request().headers()['idempotency-key'] }
}
function requireStatus(result, expected, operation) {
  assert.equal(result.status, expected, operation + ' HTTP status')
  return result.data ?? result.body?.data
}
async function selectedFact(page, factId) {
  await page.getByTestId('review-fact-id').fill(factId)
  const result = await clickResponse(page, 'review-load', 'admin/review-candidates/' + factId, 'GET')
  requireStatus(result, 200, 'Candidate detail')
  await page.getByTestId('review-detail').waitFor()
  return result.data
}
async function checkReview(page, conflictIds) {
  for (const { field, status } of explicitChecks) await page.getByTestId('review-check-' + field).selectOption(status)
  for (const id of conflictIds) await page.getByTestId('review-conflict-' + id).selectOption('INCORRECT_VALUE')
}
async function publicView(page, releaseId) {
  // Public exploration is explicitly opened by the reader; it must remain
  // discoverable without adding inputs to the initial closed visitor view.
  if (!await page.getByTestId('public-year').isVisible()) {
    await page.getByTestId('public-toggle').click()
    await page.getByTestId('public-year').waitFor()
  }
  await page.getByTestId('public-year').fill('2026')
  const pending = page.waitForResponse(response => new URL(response.url()).pathname === '/public/v2/offerings')
  await page.getByTestId('public-refresh').click()
  const response = await pending
  assert.equal(response.status(), 200)
  const envelope = await response.json()
  assert.equal(response.headers()['cache-control'], 'no-store')
  if (releaseId) {
    assert.equal(envelope.data.items.length, 1)
    assert.equal(envelope.data.items[0].release_id, releaseId)
    await page.getByTestId('public-result').filter({ hasText: releaseId }).waitFor()
  } else {
    assert.deepEqual(envelope.data.items, [])
    assert.equal(envelope.data.coverage.status, 'no_published_records')
  }
  const text = JSON.stringify(envelope.data)
  for (const forbidden of ['owner_user_id', 'file_id', 'responsible_user_id', 'entry_url', 'https://source-sentinel.invalid/DEMO_2026']) {
    assert.ok(!text.includes(forbidden), 'No private source binding in public projection')
  }
  return envelope.data
}

try {
  const moduleName = process.env.T22_PLAYWRIGHT_MODULE ?? resolve(process.env.USERPROFILE ?? '',
    '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs')
  const playwright = await import(pathToFileURL(resolve(moduleName)).href)
  browser = await playwright.chromium.launch({ headless: true, channel: 'msedge' })
  preparer = await setupPage(fixture.preparer_cookie)
  reviewer = await setupPage(fixture.reviewer_cookie)
  await preparer.getByTestId('source-save').waitFor()
  await reviewer.getByTestId('review-search').waitFor()
  await reviewer.getByTestId('public-toggle').waitFor()
  assert.equal(await reviewer.getByTestId('public-year').count(), 0)
  const publicInitial = await anonymous(reviewer)
  assert.equal(publicInitial.status, 200); assert.deepEqual(publicInitial.body.data.items, [])
  passed('Two independent synthetic server sessions and an actually empty anonymous catalog use separate private/public mounts')

  await preparer.getByTestId('source-dataset').fill(fixture.dataset_id)
  await preparer.getByTestId('source-dataset-revision').fill(String(fixture.dataset_revision))
  await preparer.getByTestId('source-reference').fill('DEMO_T22_BROWSER_SOURCE')
  await preparer.getByTestId('source-publisher').fill('DEMO_T22_SYNTHETIC_PUBLISHER')
  await preparer.getByTestId('source-url').fill('https://source-sentinel.invalid/DEMO_2026')
  await preparer.getByTestId('source-data-type').selectOption('entry_requirements')
  await preparer.getByTestId('source-scope').fill('DEMO_2026_EXPLICIT_SYNTHETIC_SCOPE')
  await preparer.getByTestId('source-authority').selectOption('not_official')
  await preparer.getByTestId('source-manual-permission').selectOption('granted')
  await preparer.getByTestId('source-publication-permission').selectOption('granted')
  await preparer.getByTestId('source-auto-permission').selectOption('denied')
  await preparer.getByTestId('source-basis').fill('DEMO_T22_SYNTHETIC_MANUAL_AND_PUBLIC_PERMISSION')
  await preparer.getByTestId('source-permission-reference').fill('DEMO_T22_PERMISSION')
  await preparer.getByTestId('source-recheck').fill('1')
  await preparer.getByTestId('source-manual-enabled').check()
  await preparer.getByTestId('source-confirm').check()
  const source = requireStatus(await clickResponse(preparer, 'source-save', 'admin/sources', 'POST', true), 200, 'Source registration')
  const original = JSON.stringify(fixture.rows, null, 2).replaceAll('\n', '\r\n')
  const bytes = Buffer.from(original, 'utf8')
  assert.ok(bytes.length < 4096, 'The explicitly selected original span is bounded')
  await preparer.getByTestId('original-file-input').setInputFiles({ name: 'DEMO_T22_SOURCE.json', mimeType: 'application/json', buffer: bytes })
  await preparer.getByTestId('original-confirm').check()
  const file = requireStatus(await clickResponse(preparer, 'original-upload', 'admin/source-files'), 200, 'Original upload')
  assert.equal(file.sha256, createHash('sha256').update(bytes).digest('hex'))
  await preparer.getByTestId('import-confirm').check()
  const imported = requireStatus(await clickResponse(preparer, 'import-submit', 'admin/imports'), 200, 'Import')
  assert.equal(imported.status, 'staged'); assert.equal(imported.staged_rows, 2)
  ids.import_id = imported.id
  passed('Keyboard-confirmed source, exact CRLF original upload and two-row import are performed through real T21 services')

  await preparer.getByTestId('prep-import-id').fill(imported.id)
  const discovered = requireStatus(await clickResponse(preparer, 'prep-load', 'admin/imports/' + imported.id + '/rows', 'GET'), 200, 'Row discovery')
  const rows = discovered.rows
  assert.equal(rows.length, 2); assert.notEqual(rows[0].row_id, rows[1].row_id)
  const first = rows.find(item => item.row.value_text === '600.00')
  const second = rows.find(item => item.row.value_text === '601.00')
  assert.ok(first && second, 'Original values and server row UUIDs must be actually discovered')
  const incomplete = requireStatus(await api(preparer, 'admin/facts', { method: 'POST', body: {
    import_id: imported.id, import_row_id: first.row_id, classification, evidence_id: null, confirmed: true } }),
  200, 'Explicit incomplete candidate')
  assert.equal(incomplete.state, 'draft'); assert.equal(incomplete.evidence_id, null)
  await selectedFact(reviewer, incomplete.id)
  assert.match(await reviewer.getByTestId('review-detail').innerText(), /缺|未知|未|证据/)
  const missingEvidence = await api(reviewer, 'admin/review-decisions', { method: 'POST', body: {
    fact_id: incomplete.id, expected_fact_version: 1, expected_case_revision: 0, action: 'approve',
    checks: explicitChecks, conflict_resolutions: [], return_reason: null, confirmed: true } })
  assert.equal(missingEvidence.status, 422)
  passed('A legitimately incomplete typed candidate remains draft; its visible missing evidence cannot be approved even with ten asserted checks')
  await preparer.getByTestId('prep-row-' + first.row_id).check()
  await preparer.getByText('重新选择自己的原文并核对哈希', { exact: true }).click()
  await preparer.getByTestId('prep-original-file').setInputFiles({ name: 'DEMO_T22_SOURCE.json', mimeType: 'application/json', buffer: bytes })
  await preparer.getByTestId('prep-original-status').filter({ hasText: '一致' }).waitFor()
  await preparer.getByTestId('prep-document-reference').fill('DEMO_T22_DOCUMENT')
  await preparer.getByTestId('prep-language').selectOption('und')
  await preparer.getByTestId('prep-document-confirm').check()
  const document = requireStatus(await clickResponse(preparer, 'prep-create-document', 'admin/evidence/documents'), 200, 'Document registration')
  await preparer.getByTestId('prep-version-confirm').check()
  const version = requireStatus(await clickResponse(preparer, 'prep-create-version', 'admin/evidence/versions'), 200, 'Version registration')
  await preparer.getByTestId('prep-byte-start').fill('0')
  await preparer.getByTestId('prep-byte-end').fill(String(bytes.length))
  await preparer.getByTestId('prep-snippet-confirm').check()
  const snippet = requireStatus(await clickResponse(preparer, 'prep-create-snippet', 'admin/evidence/snippets'), 200, 'Snippet preparation')
  assert.equal(snippet.text, original)
  assert.equal(snippet.document_sha256, file.sha256)
  ids.evidence_id = snippet.id
  await preparer.getByTestId('prep-claim').selectOption('minimum_requirement')
  await preparer.getByTestId('prep-unit').selectOption('points')
  await preparer.getByTestId('prep-period').selectOption('not_applicable')
  await preparer.getByTestId('prep-statistics-basis').selectOption('not_applicable')
  await preparer.getByTestId('prep-fact-confirm').check()
  const fact = requireStatus(await clickResponse(preparer, 'prep-create-fact', 'admin/facts'), 200, 'Typed candidate')
  assert.equal(fact.value_text, '600.00'); assert.equal(fact.hard_rule, false)
  const rivalResponse = await api(preparer, 'admin/facts', { method: 'POST', body: {
    import_id: imported.id, import_row_id: second.row_id, classification, evidence_id: snippet.id, confirmed: true } })
  const rival = requireStatus(rivalResponse, 200, 'Conflicting typed candidate')
  ids.fact_id = fact.id; ids.rival_id = rival.id
  passed('Real discovered row UUIDs produce an explicitly confirmed document/version/byte span/classification and an actual immutable conflicting fact')

  await reviewer.getByTestId('review-dataset').fill(fixture.dataset_id)
  await reviewer.getByTestId('review-year').fill('2026')
  requireStatus(await clickResponse(reviewer, 'review-search', 'admin/review-candidates', 'GET'), 200, 'Candidate discovery')
  const detail = await selectedFact(reviewer, fact.id)
  assert.equal(detail.fact.id, fact.id)
  assert.ok(detail.fact.conflicting_ids.includes(rival.id))
  assert.equal(detail.evidence.text, original)
  for (const field of checkFields) assert.equal(await reviewer.getByTestId('review-check-' + field).inputValue(), '')
  assert.equal(await reviewer.getByTestId('review-confirm').isChecked(), false)
  assert.equal(await reviewer.getByTestId('review-decide').isDisabled(), true)
  const literalText = await reviewer.getByTestId('review-detail').innerText()
  assert.ok(literalText.includes(fixture.rows[0].footnote_text))
  assert.equal(await reviewer.getByTestId('review-detail').locator('img,script,a').count(), 0)
  assert.equal(await reviewer.evaluate(() => window.__t22Xss), undefined)
  const baseDecision = { fact_id: fact.id, expected_fact_version: 1, expected_case_revision: 0,
    action: 'approve', checks: explicitChecks,
    conflict_resolutions: detail.fact.conflicting_ids.map(fact_id => ({ fact_id, reason_code: 'INCORRECT_VALUE' })),
    return_reason: null, confirmed: true }
  const self = await api(preparer, 'admin/review-decisions', { method: 'POST', body: baseDecision })
  assert.equal(self.status, 403)
  const unresolved = await api(reviewer, 'admin/review-decisions', { method: 'POST', body: { ...baseDecision, conflict_resolutions: [] } })
  assert.equal(unresolved.status, 409)
  const missingCsrf = await api(reviewer, 'admin/review-decisions', { method: 'POST', body: baseDecision, csrf: false })
  assert.equal(missingCsrf.status, 403)
  passed('Bounded original and candidate are shown side by side with escaped XSS; blank ten checks, self-review403, unresolved conflict409 and missing-CSRF403 are truthful')

  const now = new Date(fixture.now)
  const until = new Date(now.getTime() + 60 * 60 * 1000)
  const currentBefore = requireStatus(await api(reviewer, 'admin/releases/current?dataset_id=' + fixture.dataset_id + '&entry_year=2026'), 200, 'Current release metadata')
  const unapproved = { dataset_id: fixture.dataset_id, expected_dataset_revision: currentBefore.dataset_revision,
    entry_year: 2026, kind: 'test_fixture', valid_from: now.toISOString(), valid_until: until.toISOString(),
    members: [{ fact_id: fact.id, expected_case_revision: 1, expected_decision_id: randomUUID(), public_evidence: false }],
    replaces_release_id: null, expected_replaced_state_revision: null, confirmed: true }
  assert.equal((await api(reviewer, 'admin/releases/precheck', { method: 'POST', body: unapproved })).status, 409)
  assert.equal((await api(reviewer, 'admin/releases', { method: 'POST', body: unapproved, key: randomUUID() })).status, 409)
  assert.deepEqual((await anonymous(reviewer)).body.data.items, [])
  passed('A real unapproved publication precheck/write fails409 and creates no public release; preview never uses administrator metadata')

  await reviewer.getByTestId('review-action').selectOption('approve')
  await checkReview(reviewer, detail.fact.conflicting_ids)
  await reviewer.getByTestId('review-confirm').check()
  let decision = requireStatus(await clickResponse(reviewer, 'review-decide', 'admin/review-decisions'), 200, 'Human approval')
  assert.equal(decision.current_approved, true)
  ids.decision_id = decision.decision_id
  const stale = await api(reviewer, 'admin/review-decisions', { method: 'POST', body: baseDecision })
  assert.equal(stale.status, 409)
  passed('A separate synthetic reviewer explicitly approves all fields and conflicts; stale case revision409 preserves the successful decision')

  const raceBody = { ...baseDecision, expected_case_revision: decision.case_revision }
  const raced = await Promise.all([0, 1].map(() => api(reviewer, 'admin/review-decisions', { method: 'POST', body: raceBody })))
  assert.deepEqual(raced.map(result => result.status).sort(), [200, 409])
  decision = raced.find(result => result.status === 200).body.data
  assert.equal(decision.case_revision, 2)
  const refreshedDetail = await selectedFact(reviewer, fact.id)
  assert.equal(refreshedDetail.case.case_revision, decision.case_revision)
  ids.decision_id = decision.decision_id
  passed('Two actual concurrent ASGI decisions with the same CAS produce exactly one success and one409; refreshed UI reads the winning revision')

  await reviewer.getByTestId('release-dataset').fill(fixture.dataset_id)
  await reviewer.getByTestId('release-year').fill('2026')
  requireStatus(await clickResponse(reviewer, 'release-load-current', 'admin/releases/current', 'GET'), 200, 'Release context')
  await reviewer.getByTestId('release-kind').selectOption('test_fixture')
  await reviewer.getByTestId('release-valid-from').fill(now.toISOString())
  await reviewer.getByTestId('release-valid-until').fill(until.toISOString())
  // The native form starts with one blank member, never an implicit selection.
  await reviewer.getByTestId('release-member-fact-0').fill(fact.id)
  await reviewer.getByTestId('release-member-case-0').fill(String(decision.case_revision))
  await reviewer.getByTestId('release-member-decision-0').fill(decision.decision_id)
  assert.equal(await reviewer.getByTestId('release-member-public-0').isChecked(), false)
  assert.equal(await reviewer.getByTestId('release-precheck-confirm').isChecked(), false)
  assert.equal(await reviewer.getByTestId('release-precheck').isDisabled(), true)
  await reviewer.getByTestId('release-precheck-confirm').check()
  const prechecked = requireStatus(await clickResponse(reviewer, 'release-precheck', 'admin/releases/precheck'), 200, 'Publication precheck')
  assert.equal(prechecked.status, 'precheck_passed')
  assert.equal(await reviewer.getByTestId('release-publish-confirm').isChecked(), false)
  assert.equal(await reviewer.getByTestId('release-publish').isDisabled(), true)
  // A changed request must invalidate readiness/confirmation; it is not a permit.
  await reviewer.getByTestId('release-valid-until').fill(new Date(until.getTime() + 60000).toISOString())
  assert.equal(await reviewer.getByTestId('release-precheck-result').count(), 0)
  assert.equal(await reviewer.getByTestId('release-publish-confirm').isChecked(), false)
  await reviewer.getByTestId('release-precheck-confirm').check()
  requireStatus(await clickResponse(reviewer, 'release-precheck', 'admin/releases/precheck'), 200, 'Updated precheck')
  await reviewer.getByTestId('release-publish-confirm').check()
  const publishedResponse = await clickResponse(reviewer, 'release-publish', 'admin/releases')
  const published = requireStatus(publishedResponse, 200, 'Publication')
  ids.first_release_id = published.release_id
  assert.equal(published.kind, 'test_fixture'); assert.equal(published.state, 'published')
  const retry = await api(reviewer, 'admin/releases', { method: 'POST', body: publishedResponse.request, key: publishedResponse.key })
  assert.equal(retry.status, 200); assert.equal(retry.body.data.release_id, published.release_id)
  assert.equal(retry.body.data.replayed, true)
  const exposed = await publicView(reviewer, published.release_id)
  assert.equal(exposed.items[0].facts[0].evidence_id, null)
  passed('Payload changes invalidate precheck; explicit publish commits a test release, exact retry replays it, and anonymous UI shows its genuine current ID')

  // Publication changes dataset revision. Reusing the original CAS for a new
  // replacement must fail instead of silently replacing a concurrent head.
  const stalePublish = { ...publishedResponse.request, valid_until: new Date(until.getTime() + 120000).toISOString(),
    replaces_release_id: published.release_id, expected_replaced_state_revision: published.state_revision }
  assert.equal((await api(reviewer, 'admin/releases', { method: 'POST', body: stalePublish, key: randomUUID() })).status, 409)
  requireStatus(await clickResponse(reviewer, 'release-load-current', 'admin/releases/current', 'GET'), 200, 'Fresh dataset revision')
  await reviewer.getByTestId('release-replace').check()
  await reviewer.getByTestId('release-member-public-0').check()
  await reviewer.getByTestId('release-valid-until').fill(new Date(until.getTime() + 120000).toISOString())
  await reviewer.getByTestId('release-precheck-confirm').check()
  requireStatus(await clickResponse(reviewer, 'release-precheck', 'admin/releases/precheck'), 200, 'Replacement precheck')
  await reviewer.getByTestId('release-publish-confirm').check()
  const replaced = requireStatus(await clickResponse(reviewer, 'release-publish', 'admin/releases'), 200, 'Replacement')
  assert.notEqual(replaced.release_id, published.release_id)
  assert.equal(replaced.replaces_release_id, published.release_id)
  ids.final_release_id = replaced.release_id
  const old = await api(reviewer, 'admin/releases/' + published.release_id)
  // Strict management detail uses current T19 proofs. The old replaced root
  // remains immutable history in PostgreSQL, but cannot pass current reads.
  assert.equal(old.status, 409)
  const replacementPublic = await publicView(reviewer, replaced.release_id)
  assert.equal(replacementPublic.items[0].facts[0].evidence_id, snippet.id)
  assert.ok(!(await reviewer.getByTestId('public-result').innerText()).includes(published.release_id))
  passed('Stale dataset CAS409 leaves the head intact; explicit replacement preserves old history and updates the real anonymous release projection')

  await reviewer.getByTestId('review-detail').screenshot({ path: resolve(cache, 'review-desktop.png') })
  await reviewer.getByTestId('public-result').screenshot({ path: resolve(cache, 'public-current.png') })
  await reviewer.setViewportSize({ width: 390, height: 844 })
  assert.ok(await reviewer.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  await reviewer.screenshot({ path: resolve(cache, 'review-mobile.png'), fullPage: true })
  for (const page of [preparer, reviewer]) {
    assert.deepEqual(await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage), cookies: document.cookie })),
      { local: [], session: [], cookies: '' })
    assert.equal(await page.evaluate(() => window.__t22Xss), undefined)
  }
  passed('Desktop and 390px native forms remain usable without overflow; original HTML is literal and proofs stay out of browser storage')

  requireStatus(await clickResponse(reviewer, 'release-load-current', 'admin/releases/current', 'GET'), 200, 'Current withdrawal reference')
  await reviewer.getByTestId('release-withdraw-reason').selectOption('ADMIN_REQUEST')
  assert.equal(await reviewer.getByTestId('release-withdraw-confirm').isChecked(), false)
  await reviewer.getByTestId('release-withdraw-confirm').check()
  const withdrawn = requireStatus(await clickResponse(reviewer, 'release-withdraw', 'admin/releases/' + replaced.release_id + '/withdraw'), 200, 'Withdrawal')
  assert.equal(withdrawn.state, 'withdrawn')
  await publicView(reviewer, null)
  assert.ok(!(await reviewer.getByTestId('public-result').innerText()).includes(replaced.release_id))
  const forbiddenReopen = await api(reviewer, 'admin/releases', { method: 'POST', body: publishedResponse.request, key: publishedResponse.key })
  assert.equal(forbiddenReopen.status, 409)
  passed('Explicit CAS withdrawal commits and removes the public card; an old idempotent publication cannot revive a replaced/withdrawn release')

  const beforeReturn = await selectedFact(reviewer, fact.id)
  await reviewer.getByTestId('review-action').selectOption('return')
  await checkReview(reviewer, beforeReturn.fact.conflicting_ids)
  await reviewer.getByTestId('review-return-reason').selectOption('INVALID_VALUE')
  await reviewer.getByTestId('review-confirm').check()
  const returned = requireStatus(await clickResponse(reviewer, 'review-decide', 'admin/review-decisions'), 200, 'Explicit return')
  assert.equal(returned.action, 'return'); assert.equal(returned.current_approved, false)
  assert.equal(returned.case_revision, decision.case_revision + 1)
  const returnedDetail = await selectedFact(reviewer, fact.id)
  assert.equal(returnedDetail.case.current_approved, false)
  assert.equal(returnedDetail.case.chosen_fact_id, null)
  await publicView(reviewer, null)
  passed('A separately confirmed finite-reason return persists a new case revision and removes current approval without reopening any public version')

  assert.deepEqual(pageErrors, []); assert.deepEqual(blockedRequests, [])
  assert.ok(publicRequests.length >= 4 && publicRequests.every(request => !request.cookie))
  report = { status: 'passed', browser: await browser.version(), checks, page_errors: pageErrors,
    blocked_requests: blockedRequests, public_request_count: publicRequests.length, ids, cache_directory: cache,
    not_executed: ['Real Keycloak login/MFA', 'Real source or legal review', 'Production release/deployment', 'T23 or subsequent tasks'] }
} catch (error) {
  report = { status: 'failed', checks, error: safeError(error), page_errors: pageErrors,
    blocked_requests: blockedRequests, cache_directory: cache }
  if (reviewer) await reviewer.screenshot({ path: resolve(cache, 'review-failure.png'), fullPage: true }).catch(() => {})
  if (preparer) await preparer.screenshot({ path: resolve(cache, 'preparation-failure.png'), fullPage: true }).catch(() => {})
  process.exitCode = 1
} finally {
  if (browser) await browser.close()
  await writeFile(resolve(cache, 'report.json'), JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report))
}
