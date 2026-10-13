// Optional local E2E smoke test. Requires running API/web and Playwright 1.62.1.
// Uses an isolated headless browser; never touches a user's browser profile.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
const { chromium } = await import(process.env.M0_PLAYWRIGHT_MODULE ?? 'playwright')
const root = resolve(import.meta.dirname, '..')
const base = 'http://127.0.0.1:5173'
const browser = await chromium.launch({ headless: true, channel: 'msedge' })
const checks = [], errors = []
let page
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  // Offline: all application traffic must stay on the two test services.
  await context.route('**/*', route => {
    const origin = new URL(route.request().url()).origin
    return origin === base || origin === 'http://127.0.0.1:8000' ? route.continue() : route.abort()
  })
  page = await context.newPage()
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(base)
  await page.locator('.offering-card').nth(3).waitFor()
  assert.match(await page.locator('.demo-banner').innerText(), /合成数据/)
  assert.match(await page.locator('.mode-badge').innerText(), /mock/)
  checks.push('DEMO/mock labels and four projects loaded from running API')
  await page.locator('#profile-select').selectOption('')
  await page.locator('#display-name').fill('DEMO_浏览器验收')
  await page.locator('#score-gaokao_total').fill('620')
  await page.locator('#score-math').fill('120')
  await page.locator('#score-english_language').fill('')
  await page.locator('#confirm-profile').check()
  const createdResponse = page.waitForResponse(r => r.url().endsWith('/v1/profiles') && r.request().method() === 'POST')
  await page.getByRole('button', { name: '确认并保存合成画像', exact: true }).click()
  const created = await (await createdResponse).json()
  await page.waitForFunction(id => document.querySelector('#profile-select').value === id, created.data.id)
  assert.equal(created.data.is_synthetic, true)
  assert.equal('english_language' in created.data.assessments, false)
  checks.push('Explicitly confirmed profile persisted; blank language remains missing')
  const boxes = page.locator('.offering-card input[type=checkbox]')
  for (let i = 0; i < 4; i++) await boxes.nth(i).check()
  const eligibilityResponse = page.waitForResponse(r => r.url().endsWith('/v1/eligibility/check'))
  await page.getByRole('button', { name: '运行确定性资格检查 →', exact: true }).click()
  const eligibility = await (await eligibilityResponse).json()
  assert.deepEqual(Object.fromEntries(eligibility.data.map(r => [r.offering_id, r.status])), {
    DEMO_CN_MATH: 'eligible', DEMO_GB_DEFERRED: 'conditional',
    DEMO_GB_MISSING_DEADLINE: 'unknown', DEMO_GB_NO_DEFERRAL: 'unknown',
  })
  await page.locator('.result-card').nth(3).waitFor()
  for (const result of eligibility.data) {
    assert.ok((await page.locator('.result-card').filter({ hasText: result.offering_id === 'DEMO_CN_MATH' ? '国内示例' : result.reasons[0].rule_id }).innerText()).includes(result.status))
  }
  checks.push('Missing language: eligible / conditional / unknown / unknown rendered with real results')
  await mkdir(resolve(root, '.cache'), { recursive: true })
  await page.locator('.result-card').first().getByRole('button').first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByText('SHA256', { exact: true }).waitFor()
  assert.match(await dialog.innerText(), /不是真实官方招生依据/)
  assert.match(await dialog.innerText(), /适用项目/)
  assert.match(await dialog.locator('.hash').innerText(), /^[a-f0-9]{64}$/)
  await page.screenshot({ path: resolve(root, '.cache/m0-evidence.png') })
  await page.getByRole('button', { name: '关闭证据', exact: true }).click()
  checks.push('Synthetic evidence dialog displays source, project scope, hash and locator')
  const draftResponse = page.waitForResponse(r => r.url().endsWith('/v1/plans/drafts'))
  await page.getByRole('button', { name: '生成未确认计划草案 →', exact: true }).click()
  const draft = await (await draftResponse).json()
  await page.locator('.task-card').nth(3).waitFor()
  assert.equal(draft.data.status, 'draft')
  assert.equal(draft.data.tasks.length, 4)
  assert.ok(draft.data.tasks.every(t => t.user_confirmed === false))
  assert.equal(draft.data.tasks.find(t => t.offering_id === 'DEMO_GB_MISSING_DEADLINE').target_date, null)
  assert.ok(!(await page.locator('#plan').innerText()).includes('23:59'))
  checks.push('Unconfirmed draft generated; unpublished deadline remains null without invented time')
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: resolve(root, '.cache/m0-workspace.png') })
  await page.locator('#score-math').fill('90')
  assert.equal(await page.locator('.result-card').count(), 0)
  assert.equal(await page.locator('.task-card').count(), 0)
  await page.locator('#confirm-profile').check()
  const updatedResponse = page.waitForResponse(r => r.url().endsWith('/v1/profiles') && r.request().method() === 'POST')
  await page.getByRole('button', { name: '确认并保存合成画像', exact: true }).click()
  const updated = await (await updatedResponse).json()
  await page.waitForFunction(id => document.querySelector('#profile-select').value === id, updated.data.id)
  const secondResponse = page.waitForResponse(r => r.url().endsWith('/v1/eligibility/check'))
  await page.getByRole('button', { name: '运行确定性资格检查 →', exact: true }).click()
  const second = await (await secondResponse).json()
  assert.equal(second.data.find(r => r.offering_id === 'DEMO_CN_MATH').status, 'ineligible')
  checks.push('Profile edit invalidates old results/draft; achieved low math becomes ineligible')
  const bobResponse = page.waitForResponse(r => r.url().endsWith('/v1/profiles') && r.request().method() === 'GET')
  await page.locator('#demo-user').selectOption('bob')
  const bob = await (await bobResponse).json()
  assert.ok(bob.data.every(p => p.owner_id === 'demo_bob'))
  assert.ok(!bob.data.some(p => p.id === created.data.id || p.id === updated.data.id))
  assert.equal(await page.locator('.result-card').count(), 0)
  assert.equal(await page.locator('.task-card').count(), 0)
  checks.push('User switch clears conclusions and excludes Alice profile IDs')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.evaluate(() => window.scrollTo(0, 0))
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
  checks.push('390px viewport has no document horizontal overflow')
  assert.deepEqual(errors, [])
  const report = { status: 'passed', browser: await browser.version(), checks, page_errors: errors }
  await writeFile(resolve(root, '.cache/browser-smoke.json'), JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 2))
} catch (error) {
  if (page) {
    await page.screenshot({ path: resolve(root, '.cache/m0-browser-failure.png') }).catch(() => {})
    console.error('PAGE ALERTS:', await page.getByRole('alert').allTextContents())
    console.error('INVALID INPUTS:', await page.locator('input:invalid').evaluateAll(inputs => inputs.map(i => ({ id: i.id, value: i.value, message: i.validationMessage }))))
  }
  throw error
} finally { await browser.close() }
