// Actual T41 Edge keyboard -> loopback HTTP -> isolated synthetic PostgreSQL.
import assert from 'node:assert/strict'
import { mkdir,writeFile,readFile } from 'node:fs/promises'
import { dirname,resolve } from 'node:path'
import { fileURLToPath,pathToFileURL } from 'node:url'
import { randomUUID,createHash } from 'node:crypto'
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..')
let input='';for await(const part of process.stdin){input+=part;assert.ok(Buffer.byteLength(input)<=16384)}
const fixture=JSON.parse(input);assert.match(fixture.origin,/^http:\/\/127\.0\.0\.1:[0-9]+$/)
const cache=resolve(root,'.cache/t41-ui',randomUUID());await mkdir(cache,{recursive:true})
const checks=[],pageErrors=[],blockedRequests=[],events=[]
let browser,page,step='initial',report
function redact(e){let v=String(e?.message??e);for(const key of ['cookie','renewed_cookie','control'])v=v.split(fixture[key]).join('[redacted]');return v.replace(/https?:\/\/[^\s"'<>]+/g,'[URL]').slice(0,2500)}
function pass(value){step=value;checks.push(value)}
async function key(selector,space=false){const item=page.getByTestId(selector);await item.focus();await page.keyboard.press(space?'Space':'Enter')}
async function response(path,method,work,status=200){const pending=page.waitForResponse(r=>new URL(r.url()).pathname===path&&r.request().method()===method);await work();const result=await pending;assert.equal(result.status(),status);if(status===200){assert.equal(result.headers()['cache-control'],'no-store');return (await result.json()).data}return null}
async function control(action){return page.evaluate(async({action,proof})=>{const r=await fetch('/__t41/control',{method:action?'POST':'GET',cache:'no-store',headers:{'X-T41-Control':proof,...(action?{'Content-Type':'application/json'}:{})},...(action?{body:JSON.stringify({action})}:{})});if(r.status!==200)throw Error('Control failed');return r.json()},{action,proof:fixture.control})}
async function waitControl(field){const end=Date.now()+30000;for(;;){const value=await control();if(value[field])return value;if(Date.now()>end)throw Error('Control timeout');await new Promise(r=>setTimeout(r,75))}}
try{
 const {chromium}=await import(pathToFileURL(resolve(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs')).href)
 browser=await chromium.launch({channel:'msedge',headless:true})
 const context=await browser.newContext({viewport:{width:1280,height:900},acceptDownloads:true})
 const cookie=value=>({name:'__Host-admissions-session',value,domain:'127.0.0.1',path:'/',secure:true,httpOnly:true,sameSite:'Lax'})
 await context.addCookies([cookie(fixture.cookie)])
 await context.route('**/*',async route=>{const req=route.request(),url=new URL(req.url());if(url.origin!==fixture.origin){blockedRequests.push(url.pathname);await route.abort();return}const headers=await req.allHeaders();assert.ok(!headers.authorization);await route.continue()})
 page=await context.newPage();page.setDefaultTimeout(20000);page.on('pageerror',e=>pageErrors.push(redact(e)))
 page.on('response',r=>{const p=new URL(r.url()).pathname;if(p.startsWith('/api/'))events.push({path:p,method:r.request().method(),status:r.status()})})
 await page.goto(fixture.origin);await page.getByTestId('actor-id').waitFor()
 assert.equal(await page.getByTestId('actor-id').textContent(),fixture.user_id)
 assert.equal(events.filter(e=>e.path.includes('/privacy/rights/')||e.path.includes('/privacy/exports')||e.path.includes('/privacy/deletions')).length,0)
 pass('Pre-registered synthetic Cookie session; folded rights makes zero rights calls')
 const revoked=await response(`/api/v2/access-grants/${fixture.grant_id}`,'DELETE',()=>key(`revoke-grant-${fixture.grant_id}`))
 assert.equal(revoked.grant.state,'revoked');assert.equal(revoked.grant.access_active,false)
 pass('Keyboard revokes exact shared grant and current access closes')
 const withdrawal=page.waitForResponse(r=>new URL(r.url()).pathname.startsWith('/api/v2/me/consents/')&&r.request().method()==='DELETE')
 await key('withdraw-core');assert.equal((await withdrawal).status(),200)
 assert.equal(await page.evaluate(async id=>(await fetch('/api/v2/profiles/'+id,{cache:'no-store'})).status,fixture.profile_id),403)
 pass('Core withdrawal immediately blocks old private profile')
 await response('/api/v2/privacy/rights/context','GET',()=>key('rights-toggle'))
 await page.getByTestId('export-confirm').waitFor()
 assert.equal(await page.getByTestId('export-create').isDisabled(),true)
 await key('export-confirm',true)
 const exported=await response('/api/v2/privacy/exports','POST',()=>key('export-create'))
 assert.equal(exported.status,'queued');assert.equal(exported.online_cleanup_complete,false)
 assert.equal(await page.getByTestId('export-confirm').isChecked(),false)
 pass('Separate keyboard confirmation; own export remains available after core withdrawal')
 await page.getByTestId('rights-kind').selectOption('export');await page.getByTestId('rights-id').fill(fixture.foreign_export_id)
 await response(`/api/v2/privacy/exports/${fixture.foreign_export_id}`,'GET',()=>key('rights-track'),404)
 await page.getByTestId('rights-message').filter({hasText:'无法读取'}).waitFor()
 pass('Foreign actual request UUID returns 404 without other-user status')
 assert.equal((await control('run')).worker.status,'completed')
 await response(`/api/v2/privacy/exports/${exported.request_id}`,'GET',()=>key('export-refresh'))
 const content=await response(`/api/v2/privacy/exports/${exported.request_id}/content`,'GET',()=>key('export-content'))
 await page.getByTestId('export-download').waitFor()
 const downloading=page.waitForEvent('download');await key('export-download');const download=await downloading
 const bytes=await readFile(await download.path());assert.equal(bytes.length,content.size_bytes);assert.equal(createHash('sha256').update(bytes).digest('hex'),content.sha256)
 const parsed=JSON.parse(bytes.toString('utf8'));assert.equal(parsed.owner_user_id,fixture.user_id);assert.equal(parsed.is_synthetic,true)
 assert.ok(parsed.collections.some(c=>c.collection==='student_profile_versions'&&c.row_count===1));assert.ok(parsed.attachments.length===1)
 pass('Explicit own JSON download verifies actual original bytes and SHA, with no HTML rendering')
 await control('arm');await key('export-content');const held=await waitControl('blocked');assert.equal(held.delayed_status,200)
 await key('rights-toggle');await control('release');await waitControl('completed')
 await response('/api/v2/privacy/rights/context','GET',()=>key('rights-toggle'))
 assert.equal(await page.getByTestId('export-download').count(),0)
 pass('Closing panel clears content and ignores genuinely successful delayed HTTP200')
 await key('deletion-confirm',true)
 const deleted=await response('/api/v2/privacy/deletions','POST',()=>key('deletion-create'))
 assert.equal(deleted.status,'queued');assert.equal(deleted.online_cleanup_complete,false)
 await page.getByTestId('rights-accepted').waitFor();assert.ok((await page.getByTestId('deletion-status').textContent()).includes('在线清理未完成'))
 pass('Deletion accepted immediately stops private use; accepted never says complete')
 assert.equal((await control('fail')).worker.status,'failed')
 await response(`/api/v2/privacy/deletions/${deleted.request_id}`,'GET',()=>key('deletion-refresh'))
 assert.ok((await page.getByTestId('deletion-status').textContent()).includes('重试上限已到'))
 pass('Real file deletion failure persists and explicit refresh traces failure')
 const logout=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v2/auth/logout'&&r.request().method()==='POST')
 await page.getByRole('button',{name:'退出当前应用',exact:true}).focus();await page.keyboard.press('Enter');assert.equal((await logout).status(),200)
 assert.equal((await control('retry')).worker.online_cleanup_complete,true)
 assert.equal(await page.getByTestId('export-download').count(),0)
 pass('Logout clears browser private state; trusted finite retry completes accepted cleanup')
 await context.addCookies([cookie(fixture.renewed_cookie)])
 await page.getByRole('button',{name:'重新检查会话',exact:true}).click();await page.getByTestId('actor-id').waitFor()
 await page.getByTestId('rights-accepted').waitFor();await page.getByTestId('rights-id').fill(deleted.request_id)
 await page.getByTestId('rights-kind').selectOption('deletion')
 await response(`/api/v2/privacy/deletions/${deleted.request_id}`,'GET',()=>key('rights-track'))
 assert.ok((await page.getByTestId('deletion-status').textContent()).includes('在线范围已清理'))
 assert.ok((await page.getByTestId('deletion-status').textContent()).includes('未到期备份'))
 await page.getByTestId('admission-decision').waitFor()
 await page.getByText('正在读取共享设置…',{exact:true}).waitFor({state:'hidden'})
 assert.deepEqual(await page.evaluate(()=>({local:localStorage.length,session:sessionStorage.length})),{local:0,session:0})
 pass('Separate valid synthetic session reads completed receipt; responsibility and backup retention remain explicit')
 assert.deepEqual(pageErrors,[]);assert.deepEqual(blockedRequests,[])
 report={status:'passed',browser:await browser.version(),checks,page_errors:pageErrors,blocked_requests:blockedRequests,events,cache_directory:cache}
}catch(error){report={status:'failed',step,error:redact(error),checks,page_errors:pageErrors,blocked_requests:blockedRequests,events,cache_directory:cache};process.exitCode=1}
finally{if(page){await page.screenshot({path:resolve(cache,'final.png'),fullPage:true}).catch(()=>{})}if(browser)await browser.close();await writeFile(resolve(cache,'result.json'),JSON.stringify(report,null,2));process.stdout.write(JSON.stringify(report))}
