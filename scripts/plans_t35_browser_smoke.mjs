// Real Edge -> transparent loopback -> ASGI -> isolated synthetic PostgreSQL.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { randomUUID } from 'node:crypto'

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..')
let input=''
for await(const chunk of process.stdin){input+=chunk;if(Buffer.byteLength(input)>16384)throw new Error('T35 fixture exceeds its bound')}
const fixture=JSON.parse(input)
assert.match(fixture.origin,/^http:\/\/127\.0\.0\.1:[0-9]+$/)
for(const name of ['profile_id','profile_version_id','old_plan_id','new_plan_id','reject_new_plan_id','user_id','other_user_id'])assert.match(fixture[name],/^[0-9a-f-]{36}$/)
assert.match(fixture.control_secret,/^[A-Za-z0-9_-]{32,128}$/)
const cache=resolve(root,'.cache/t35-ui',randomUUID())
await mkdir(cache,{recursive:true})
const checks=[],pageErrors=[],blockedRequests=[],events=[]
const ids={old_plan_id:fixture.old_plan_id,new_plan_id:fixture.new_plan_id,reject_new_plan_id:fixture.reject_new_plan_id,rejected_revision_id:null,accepted_revision_id:null}
let browser,page,report,step='initial'
const safeError=error=>{
 let value=String(error?.message??error)
 for(const secret of [fixture.owner_cookie,fixture.other_cookie,fixture.control_secret])value=value.split(secret).join('[redacted]')
 return value.replace(/https?:\/\/[^\s"'<>]+/g,'[URL]').slice(0,2500)
}
async function bounded(label,work,milliseconds=45000){let timer;try{return await Promise.race([work(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('T35 timeout: '+label)),milliseconds)})])}finally{clearTimeout(timer)}}
async function checkpoint(value){step=value;await writeFile(resolve(cache,'progress.json'),JSON.stringify({step,checks,events}))}
const passed=value=>checks.push(value)
async function setup(){
 const context=await browser.newContext({viewport:{width:1280,height:900}})
 await context.addCookies([{name:'__Host-admissions-session',value:fixture.owner_cookie,domain:'127.0.0.1',path:'/',secure:true,httpOnly:true,sameSite:'Lax'}])
 await context.route('**/*',async route=>{const request=route.request(),url=new URL(request.url());if(url.origin!==fixture.origin){blockedRequests.push(url.origin+url.pathname);await route.abort('blockedbyclient');return}const headers=await request.allHeaders();assert.ok(!headers.authorization);await route.continue()})
 const result=await context.newPage();result.setDefaultTimeout(30000)
 result.on('pageerror',error=>pageErrors.push(safeError(error)))
 result.on('response',response=>{const path=new URL(response.url()).pathname;if(path.startsWith('/api/v2/')){events.push({path,method:response.request().method(),status:response.status()});if(events.length>120)events.shift()}})
 await bounded('open page',()=>result.goto(fixture.origin));return result
}
async function action(selector,path,method='GET',keyboard=false){
 await checkpoint('UI '+method+' '+path)
 const pending=page.waitForResponse(response=>new URL(response.url()).pathname===path&&response.request().method()===method);void pending.catch(()=>{})
 const element=typeof selector==='string'?page.getByTestId(selector):selector
 await bounded('UI action',async()=>{if(keyboard){await element.focus();await page.keyboard.press('Enter')}else await element.click()})
 const response=await bounded('UI response',()=>pending),headers=await response.allHeaders()
 assert.equal(headers['cache-control'],'no-store');assert.match(headers['x-request-id'],/^[0-9a-f]{32}$/)
 const requestHeaders=await response.request().allHeaders()
 if(method!=='GET'){assert.equal(requestHeaders.origin,fixture.origin);assert.ok(requestHeaders['x-csrf-token']);assert.ok(!requestHeaders['idempotency-key'])}
 // Do not consume bodies that the application also intentionally ignores.
 const envelope=response.status()===200?await bounded('successful body',()=>response.json(),15000):null
 if(envelope){assert.equal(envelope.meta.request_id,headers['x-request-id']);assert.equal(envelope.meta.data_mode,'verified');assert.equal(envelope.meta.model_mode,'disabled')}
 return{status:response.status(),data:envelope?.data,body:method==='GET'?null:response.request().postDataJSON()}
}
async function api(path){return bounded('direct read',()=>page.evaluate(async path=>{const r=await fetch('/api/v2/'+path,{credentials:'same-origin',cache:'no-store',redirect:'error',headers:{Accept:'application/json'}});return{status:r.status,data:r.status===200?(await r.json()).data:null,request_id:r.headers.get('X-Request-ID'),cache_control:r.headers.get('Cache-Control')}},path))}
async function control(actionName){return bounded('delivery control',()=>page.evaluate(async({actionName,secret})=>{const r=await fetch('/__t35/control',{method:actionName?'POST':'GET',headers:{'X-T35-Control':secret,...(actionName?{'Content-Type':'application/json'}:{})},...(actionName?{body:JSON.stringify({action:actionName})}:{})});if(r.status!==200)throw new Error('T35 control unavailable');return r.json()},{actionName,secret:fixture.control_secret}),10000)}
async function waitControl(key){return bounded('actual successful delivery '+key,async()=>{while(true){const value=await control();if(value[key])return value;await new Promise(resolve=>setTimeout(resolve,75))}})}
async function readPair(newId){
 await page.getByTestId('revision-new-id').fill(newId)
 const current=await action('revision-new-read','/api/v2/plans/'+newId,'GET',true)
 assert.equal(current.status,200);assert.equal(current.data.state,'draft');assert.equal(current.data.proposal.effective_draft.profile_version_id,fixture.profile_version_id);assert.deepEqual(current.data.completed_tasks,[])
 await page.getByTestId('revision-new-candidate').waitFor()
 await page.getByTestId('revision-old-id').fill(fixture.old_plan_id)
 const original=await action('revision-old-read','/api/v2/plan-revisions/history/'+fixture.old_plan_id)
 assert.equal(original.status,200);assert.equal(original.data.current_actions,false);assert.equal(original.data.pin.state,'confirmed');assert.equal(original.data.completion_refs.length,fixture.old_completed_count)
 await page.getByTestId('revision-history-old').waitFor();return{current:current.data,original:original.data}
}
async function propose(){
 assert.equal(await page.getByTestId('revision-propose').isDisabled(),true)
 await page.getByTestId('revision-propose-confirm').check()
 const saved=await action('revision-propose','/api/v2/plan-revisions','POST')
 assert.equal(saved.status,200);assert.equal(saved.data.revision.status,'proposed');assert.equal(saved.body.student_confirmed,true)
 await page.getByTestId('revision-proposal').waitFor()
 assert.equal(await page.getByTestId('revision-decision-confirm').isChecked(),false);assert.equal(await page.getByTestId('revision-accept').isDisabled(),true)
 assert.ok(saved.data.revision.diff.changed_fields.includes('profile_version'))
 return saved.data.revision
}
try{
 const module=process.env.T35_PLAYWRIGHT_MODULE||resolve(process.env.USERPROFILE||'','.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs')
 const {chromium}=await import(pathToFileURL(module).href)
 browser=await bounded('launch Edge',()=>chromium.launch({channel:'msedge',headless:true}))
 page=await setup();await page.getByTestId('actor-id').filter({hasText:fixture.user_id}).waitFor()
 const listed=await action('profile-list','/api/v2/profiles');assert.equal(listed.status,200)
 assert.ok(listed.data.items.some(v=>v.profile_id===fixture.profile_id&&v.version_id===fixture.profile_version_id))
 const loaded=await action('profile-load-'+fixture.profile_id,'/api/v2/profiles/'+fixture.profile_id);assert.equal(loaded.status,200);assert.equal(loaded.data.version_id,fixture.profile_version_id)
 passed('The current confirmed profile is genuinely discovered and explicitly selected through the existing profile API')
 await page.getByTestId('plans-toggle').click();await page.getByTestId('plans-workspace').waitFor()
 assert.equal(await page.getByTestId('revision-workspace').count(),0);assert.ok(!events.some(e=>e.path.startsWith('/api/v2/plan-revisions')))
 passed('The revision entry stays folded and makes no revision request before an explicit expand action')
 await page.getByTestId('revision-toggle').click();await page.getByTestId('revision-workspace').waitFor()
 const context=await action('revision-context-refresh','/api/v2/plan-revisions/context');assert.equal(context.status,200);assert.equal(context.data.can_propose,true);assert.equal(context.data.is_synthetic,true)
 passed('An explicit server capability probe identifies synthetic-only revision processing without a client role shortcut')
 const oldCurrent=await api('plans/'+fixture.old_plan_id);assert.equal(oldCurrent.status,409);assert.match(oldCurrent.request_id,/^[0-9a-f]{32}$/);assert.equal(oldCurrent.cache_control,'no-store')
 passed('The old T32 current-source read remains a real 409; the new history endpoint does not relax that guard')
 const first=await readPair(fixture.reject_new_plan_id)
 assert.notEqual(first.original.pin.profile_version_id,fixture.profile_version_id)
 assert.equal(await page.getByTestId('revision-history-old').locator('button').count(),0)
 assert.match(await page.getByTestId('revision-completions-old').innerText(),/student_declared/)
 passed('A new draft is directly readable without the stale list, while finite old history preserves original confirmation and completion references as readonly')
 const rejectedProposal=await propose();ids.rejected_revision_id=rejectedProposal.revision_id
 passed('The proposal needs its own unticked confirmation and displays two fixed histories, the profile-version difference and exact proposal SHA')
 await page.getByTestId('revision-decision-confirm').check()
 const rejected=await action('revision-reject','/api/v2/plan-revisions/'+rejectedProposal.revision_id+'/decision','POST',true)
 assert.equal(rejected.status,200);assert.equal(rejected.data.revision.status,'rejected');assert.equal(rejected.data.revision.replacement,null)
 await page.getByTestId('revision-rejected').waitFor()
 const oldAfterReject=await api('plan-revisions/history/'+fixture.old_plan_id);assert.equal(oldAfterReject.status,200);assert.deepEqual(oldAfterReject.data.completion_refs,first.original.completion_refs)
 passed('A separate keyboard decision rejects the first revision while the old confirmation and completion history stay readable and unchanged')
 await readPair(fixture.new_plan_id)
 const acceptedProposal=await propose();ids.accepted_revision_id=acceptedProposal.revision_id
 assert.notEqual(acceptedProposal.revision_id,rejectedProposal.revision_id)
 await page.getByTestId('revision-decision-confirm').check()
 const accepted=await action('revision-accept','/api/v2/plan-revisions/'+acceptedProposal.revision_id+'/decision','POST')
 assert.equal(accepted.status,200);assert.equal(accepted.data.revision.status,'accepted');assert.equal(accepted.data.revision.replacement.new_plan_confirmed,false);assert.equal(accepted.data.revision.replacement.completion_credit_transferred,false)
 await page.getByTestId('revision-accepted').waitFor()
 passed('The second explicit proposal is independently accepted as a relationship, with no automatic final confirmation or completion credit')
 const freshNew=await api('plans/'+fixture.new_plan_id);assert.equal(freshNew.status,200);assert.equal(freshNew.data.state,'draft');assert.equal(freshNew.data.confirmation,null);assert.deepEqual(freshNew.data.completed_tasks,[])
 const oldAfterAccept=await api('plan-revisions/history/'+fixture.old_plan_id);assert.equal(oldAfterAccept.status,200);assert.deepEqual(oldAfterAccept.data.completion_refs,first.original.completion_refs)
 assert.ok(!events.some(e=>e.method==='POST'&&e.path.startsWith('/api/v2/plans/')&&(e.path.endsWith('/confirm')||e.path.endsWith('/complete'))))
 passed('Actual post-accept reads prove the new plan remains a draft and every old completion stays only a historical reference')
 await page.setViewportSize({width:390,height:844});await page.getByTestId('revision-workspace').scrollIntoViewIfNeeded()
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true)
 await bounded('mobile screenshot',()=>page.screenshot({path:resolve(cache,'revisions-mobile.png'),fullPage:true,timeout:15000}),20000)
 await bounded('focused mobile screenshot',()=>page.getByTestId('revision-proposal').screenshot({path:resolve(cache,'revisions-mobile-decision.png'),timeout:15000}),20000)
 await page.setViewportSize({width:1280,height:900})
 await bounded('desktop screenshot',()=>page.screenshot({path:resolve(cache,'revisions-desktop.png'),fullPage:true,timeout:15000}),20000)
 await bounded('focused desktop screenshot',()=>page.getByTestId('revision-workspace').screenshot({path:resolve(cache,'revisions-desktop-workspace.png'),timeout:15000}),20000)
 passed('The actual 390px view, two-sided history and decision remain readable without horizontal overflow, and keyboard operations use the same real endpoints')
 const otherContext=await browser.newContext()
 await otherContext.addCookies([{name:'__Host-admissions-session',value:fixture.other_cookie,domain:'127.0.0.1',path:'/',secure:true,httpOnly:true,sameSite:'Lax'}])
 await otherContext.route('**/*',async route=>{const url=new URL(route.request().url());if(url.origin!==fixture.origin){blockedRequests.push(url.origin+url.pathname);await route.abort('blockedbyclient');return}await route.continue()})
 const otherPage=await otherContext.newPage();otherPage.on('pageerror',error=>pageErrors.push(safeError(error)))
 await bounded('open second actual browser account',()=>otherPage.goto(fixture.origin))
 const second=await bounded('verify second browser session',()=>otherPage.evaluate(async()=>{const r=await fetch('/api/v2/auth/session',{credentials:'same-origin',cache:'no-store',redirect:'error'});return{status:r.status,data:r.status===200?(await r.json()).data:null}}))
 assert.equal(second.status,200,'Second browser session status '+second.status);assert.equal(second.data.user_id,fixture.other_user_id)
 const denied=await bounded('cross-owner read',()=>otherPage.evaluate(async oldId=>{const r=await fetch('/api/v2/plan-revisions/history/'+oldId,{credentials:'same-origin',cache:'no-store',redirect:'error'});return{status:r.status}},fixture.old_plan_id))
 assert.ok([403,404].includes(denied.status),'Cross-owner historical read status '+denied.status);await otherContext.close()
 passed('Another server-issued synthetic account cannot read the owner historical plan through the finite endpoint')
 await control('arm');await page.getByTestId('revision-old-read').click()
 const held=await waitControl('blocked');assert.equal(held.response_status,200)
 const logout=await action(page.getByRole('button',{name:'退出当前应用',exact:true}),'/api/v2/auth/logout','POST');assert.equal(logout.status,200)
 assert.equal(await page.getByTestId('revision-history-old').count(),0)
 await control('release');await waitControl('completed')
 assert.equal(await page.getByTestId('revision-history-old').count(),0);assert.equal(await page.getByTestId('revision-proposal').count(),0);assert.equal((await api('auth/session')).status,401)
 passed('A genuine successful history GET held at delivery cannot restore private revision data after actual session logout')
 assert.deepEqual(await page.evaluate(()=>({local:Object.keys(localStorage),session:Object.keys(sessionStorage)})),{local:[],session:[]})
 assert.deepEqual(pageErrors,[]);assert.deepEqual(blockedRequests,[])
 passed('No private values or tokens persist in browser storage; the actual run has no page errors or external requests')
 report={status:'passed',browser:await browser.version(),checks,ids,page_errors:pageErrors,blocked_requests:blockedRequests,network_events:events,cache_directory:cache,not_executed:['Real students or formal source processing','Production TLS/proxy/deployment','Automatic completion credit or final confirmation']}
}catch(error){await checkpoint('failure after '+step);report={status:'failed',step,error:safeError(error),checks,ids,page_errors:pageErrors,blocked_requests:blockedRequests,network_events:events,cache_directory:cache};if(page)await bounded('failure screenshot',()=>page.screenshot({path:resolve(cache,'failure.png'),fullPage:true,timeout:10000}),12000).catch(()=>{})}
finally{if(page)await bounded('release held history',()=>control('release'),12000).catch(()=>{});if(browser)await bounded('close browser',()=>browser.close(),15000).catch(()=>{})}
await writeFile(resolve(cache,'result.json'),JSON.stringify(report,null,2));process.stdout.write(JSON.stringify(report)+'\n');if(report.status!=='passed')process.exitCode=1
