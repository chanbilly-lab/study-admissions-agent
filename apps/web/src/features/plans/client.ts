import type { CompleteInput, CompleteResult, ConfirmInput, ConfirmResult, ExecutionContextData, ExecutionData, ExecutionPage, HttpWorkspaceInput, PlanCreateInput } from '../../../../../packages/contracts/v2/plans/generated'
import { createSessionApi, SessionError } from '../auth/client'
import { exact, hash, integer, prefixBase, uuid, validMeta, utc } from '../catalog/validation'
import { validContext, validExecution, validPage, wire, utcMicros } from './validation'
export type { CompleteInput, CompleteResult, ConfirmInput, ConfirmResult, ExecutionContextData, ExecutionData, ExecutionPage, HttpWorkspaceInput, PlanCreateInput }
export class PlanError extends Error {
  constructor(public readonly status: number) { super(({401:'会话已失效，请重新登录。',403:'本人用途或对象权限已失效，私有计划已清空。',404:'计划不存在或不可读取，私有内容已清空。',409:'计划版本或来源证明已变化。请明确重新读取，再核对未提交参数。',422:'输入未通过校验，操作未确认。',503:'计划服务未开放或暂不可用，私有内容已清空。',200:'计划响应未通过验证，私有内容已清空。'}[status] ?? '网络响应未确认。请读取服务端状态，勿重复创建或编辑。')); this.name='PlanError' }
}
export interface PlanApi {
  context(signal?:AbortSignal):Promise<ExecutionContextData>
  list(query?:{limit?:number;cursor?:string},signal?:AbortSignal):Promise<ExecutionPage>
  create(input:PlanCreateInput,signal?:AbortSignal):Promise<ExecutionData>
  get(id:string,signal?:AbortSignal):Promise<ExecutionData>
  history(id:string,version:number,signal?:AbortSignal):Promise<ExecutionData>
  workspace(id:string,input:HttpWorkspaceInput,signal?:AbortSignal):Promise<ExecutionData>
  confirm(id:string,input:ConfirmInput,key:string,signal?:AbortSignal):Promise<ConfirmResult>
  complete(id:string,task:string,input:CompleteInput,signal?:AbortSignal):Promise<CompleteResult>
}
export function sameInput(a:unknown,b:unknown):boolean {
  const normalize=(v:unknown):unknown=>Array.isArray(v)?v.map(normalize):v!==null&&typeof v==='object'?Object.fromEntries(Object.entries(v).sort().map(([k,x])=>[k,normalize(x)])):utc(v)?utcMicros(v).toString():v
  return JSON.stringify(normalize(a))===JSON.stringify(normalize(b))
}
export function createPlanApi(prefix=import.meta.env.VITE_AUTH_API_BASE_URL ?? '/api',fetcher:typeof fetch=fetch):PlanApi {
  let base:string; try{base=prefixBase(prefix)+'/plans'}catch{throw new PlanError(422)}
  const session=createSessionApi(prefix,fetcher)
  async function request<T>(path:string,output:string,signal?:AbortSignal,input?:object,inputName?:string,key?:string):Promise<T>{
    let token:string|undefined,successfulResponse=false
    try{
      if(input && (!inputName || !wire(inputName,input)))throw new PlanError(422)
      const body=input?JSON.stringify(input):undefined
      if(body&&new TextEncoder().encode(body).length>65536)throw new PlanError(422)
      const frozen=body?JSON.parse(body) as Record<string,unknown>:undefined
      if(key!==undefined&&!/^[A-Za-z0-9._:-]{1,128}$/.test(key))throw new PlanError(422)
      if(input)token=(await session.csrf(signal)).csrf_token
      const response=await fetcher(base+path,{method:input?'POST':'GET',credentials:'same-origin',cache:'no-store',redirect:'error',signal,headers:{Accept:'application/json',...(input?{'Content-Type':'application/json','X-CSRF-Token':token!}:{}),...(key?{'Idempotency-Key':key}:{})},...(body?{body}:{})})
      if(response.status!==200)throw new PlanError(response.status)
      successfulResponse=true
      const raw=await response.text();if(new TextEncoder().encode(raw).length>2097152)throw new PlanError(200)
      const envelope:unknown=JSON.parse(raw)
      if(!exact(envelope,['data','meta'])||!wire(output,envelope.data)||!exact(envelope.meta,['api_version','request_id','data_as_of','profile_version_id','release_id','ruleset_version','profile_mode','data_mode','model_mode'])||envelope.meta.data_mode!=='verified'||envelope.meta.model_mode!=='disabled')throw new PlanError(200)
      const data=envelope.data
      if(output==='ExecutionContextData' || output==='ExecutionPage'){
        if(!validMeta(envelope.meta,response)||(output==='ExecutionContextData'?!validContext(data):!validPage(data)))throw new PlanError(200)
      }else{
        const e=(output==='ExecutionData'?data:(data as unknown as CompleteResult).execution) as ExecutionData
        if(!await validExecution(e)||!validMeta(envelope.meta,response,e.proposal.effective_draft.profile_version_id,e.is_synthetic))throw new PlanError(200)
        const parts=path.split('/'),id=parts[1]
        if(id&&e.plan_id!==id)throw new PlanError(200)
        if(path.includes('/versions/')&&e.state_version!==Number(parts[3]))throw new PlanError(200)
        if(frozen){
          if(path===''){
            if(e.state!=='draft'||e.state_version!==1||!sameInput(e.proposal.effective_draft.assessment_refs.map(r=>r.assessment_id).sort(),[...(frozen.assessment_ids as string[])].sort()))throw new PlanError(200)
          }else if(path.endsWith('/workspace')){
            if(e.state!=='draft'||e.state_version!==(frozen.expected_version as number)+1||!sameInput(e.proposal.estimate_overrides,frozen.estimate_overrides)||!sameInput(e.proposal.schedule_configuration,frozen.schedule))throw new PlanError(200)
          }else if(path.endsWith('/confirm')){
            const result=data as unknown as ConfirmResult
            if(!e.confirmation||result.confirmed_state_version!==e.confirmation.confirmed_state_version||result.confirmed_state_version!==(frozen.expected_version as number)+1||e.proposal.effective_draft.draft_sha256!==frozen.expected_draft_sha256||e.proposal.schedule?.schedule_sha256!==frozen.expected_schedule_sha256||!result.replayed&&e.state_version!==result.confirmed_state_version)throw new PlanError(200)
          }else if(path.endsWith('/complete')){
            const result=data as unknown as CompleteResult,completion=e.completed_tasks.find(c=>c.task_key===parts[3])
            if(!completion||completion.completed_state_version!==(frozen.expected_version as number)+1||!result.replayed&&e.state_version!==completion.completed_state_version)throw new PlanError(200)
          }
        }
      }
      if(signal?.aborted)throw new DOMException('Aborted','AbortError')
      return data as T
    }catch(error){if(error instanceof PlanError||signal?.aborted)throw error;if(error instanceof SessionError)throw new PlanError(error.status);throw new PlanError(successfulResponse?200:0)}finally{token=undefined}
  }
  const idPath=(id:string)=>{if(!uuid(id))throw new PlanError(422);return '/'+id}
  return{context:s=>request('/context','ExecutionContextData',s),list(query={},s){if(!Object.keys(query).every(k=>k==='limit'||k==='cursor')||query.limit!==undefined&&!integer(query.limit,1,20)||query.cursor!==undefined&&(typeof query.cursor!=='string'||!query.cursor.length||query.cursor.length>1024))throw new PlanError(422);const p=new URLSearchParams();if(query.limit!==undefined)p.set('limit',String(query.limit));if(query.cursor!==undefined)p.set('cursor',query.cursor);return request(p.size?'?'+p:'','ExecutionPage',s)},create:(v,s)=>request('','ExecutionData',s,v,'PlanCreateInput'),get:(id,s)=>request(idPath(id),'ExecutionData',s),history(id,v,s){if(!integer(v))throw new PlanError(422);return request(idPath(id)+'/versions/'+v,'ExecutionData',s)},workspace:(id,v,s)=>request(idPath(id)+'/workspace','ExecutionData',s,v,'HttpWorkspaceInput'),confirm:(id,v,key,s)=>request(idPath(id)+'/confirm','ConfirmResult',s,v,'ConfirmInput',key),complete(id,task,v,s){if(!hash(task))throw new PlanError(422);return request(idPath(id)+'/tasks/'+task+'/complete','CompleteResult',s,v,'CompleteInput')}}
}
