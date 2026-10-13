import type { DecisionInput, PlanPin, ProposeInput, RevisionContextData, RevisionData, RevisionHistoryData, RevisionResult } from '../../../../../../packages/contracts/v2/revisions/generated'
import { createSessionApi, SessionError } from '../../auth/client'
import { exact, prefixBase, uuid, validMeta } from '../../catalog/validation'
import { validContext, validHistory, validRevision, wire } from './validation'
export type { DecisionInput, PlanPin, ProposeInput, RevisionContextData, RevisionData, RevisionHistoryData, RevisionResult }

export class RevisionError extends Error {
  constructor(public readonly status: number) {
    super(({401:'会话已失效，请重新登录。',403:'当前用途或对象权限已失效，私人修订内容已清空。',404:'计划或修订不存在或不可读取，私人内容已清空。',409:'两侧计划或修订版本已变化。操作已锁定，请明确重新读取并重新核对。',422:'修订输入未通过校验，本次操作未确认。',503:'修订服务未开放或暂不可用，私人内容已清空。',200:'修订响应未通过验证，私人内容已清空。'}[status]??'网络结果未确认。请明确读取服务端状态，不会自动再次写入。'))
    this.name='RevisionError'
  }
}
export interface RevisionApi {
  context(signal?:AbortSignal):Promise<RevisionContextData>
  history(planId:string,signal?:AbortSignal):Promise<RevisionHistoryData>
  propose(input:ProposeInput,signal?:AbortSignal):Promise<RevisionResult>
  get(id:string,signal?:AbortSignal):Promise<RevisionData>
  decide(id:string,input:DecisionInput,signal?:AbortSignal):Promise<RevisionResult>
}
export function createRevisionApi(prefix=import.meta.env.VITE_AUTH_API_BASE_URL??'/api',fetcher:typeof fetch=fetch):RevisionApi {
  let base:string;try{base=prefixBase(prefix)+'/plan-revisions'}catch{throw new RevisionError(422)}
  const session=createSessionApi(prefix,fetcher)
  const id=(value:string)=>{if(!uuid(value))throw new RevisionError(422);return value}
  async function request<T>(path:string,name:string,signal?:AbortSignal,input?:ProposeInput|DecisionInput):Promise<T>{
    let token:string|undefined,successful=false
    try{
      if(input&&!wire('old_plan_id' in input?'ProposeInput':'DecisionInput',input))throw new RevisionError(422)
      if(input&&'old_plan_id' in input&&input.old_plan_id===input.new_plan_id)throw new RevisionError(422)
      const body=input?JSON.stringify(input):undefined
      if(body&&new TextEncoder().encode(body).length>65536)throw new RevisionError(422)
      const frozen=body?JSON.parse(body) as ProposeInput|DecisionInput:undefined
      if(input)token=(await session.csrf(signal)).csrf_token
      const response=await fetcher(base+path,{method:input?'POST':'GET',credentials:'same-origin',cache:'no-store',redirect:'error',signal,headers:{Accept:'application/json',...(input?{'Content-Type':'application/json','X-CSRF-Token':token!}:{})},...(body?{body}:{})})
      if(response.status!==200)throw new RevisionError(response.status)
      successful=true
      const raw=await response.text();if(new TextEncoder().encode(raw).length>2097152)throw new RevisionError(200)
      const envelope:unknown=JSON.parse(raw)
      if(!exact(envelope,['data','meta'])||!wire(name,envelope.data)||!exact(envelope.meta,['api_version','request_id','data_as_of','profile_version_id','release_id','ruleset_version','profile_mode','data_mode','model_mode'])||envelope.meta.data_mode!=='verified'||envelope.meta.model_mode!=='disabled')throw new RevisionError(200)
      const data=envelope.data
      if(name==='RevisionContextData'){
        if(!validContext(data)||!validMeta(envelope.meta,response))throw new RevisionError(200)
      }else if(name==='RevisionHistoryData'){
        const h=data as unknown as RevisionHistoryData
        if(!await validHistory(h)||!validMeta(envelope.meta,response,h.pin.profile_version_id,h.pin.is_synthetic)||h.pin.plan_id!==path.split('/')[2])throw new RevisionError(200)
      }else{
        const r=(name==='RevisionResult'?(data as unknown as RevisionResult).revision:data) as RevisionData
        if(!await validRevision(r)||!validMeta(envelope.meta,response,r.new.pin.profile_version_id,r.is_synthetic))throw new RevisionError(200)
        if(path&&r.revision_id!==path.split('/')[1])throw new RevisionError(200)
        if(frozen){
          if('old_plan_id' in frozen){if(r.old.pin.plan_id!==frozen.old_plan_id||r.new.pin.plan_id!==frozen.new_plan_id||r.old.pin.state_version!==frozen.expected_old_state_version||r.new.pin.state_version!==frozen.expected_new_state_version)throw new RevisionError(200)}
          else if(!r.decision||r.decision.action!==frozen.action||r.revision_version!==2||frozen.expected_revision_version!==1&&(data as unknown as RevisionResult).replayed!==true)throw new RevisionError(200)
        }
      }
      if(signal?.aborted)throw new DOMException('Aborted','AbortError')
      return data as T
    }catch(error){if(error instanceof RevisionError||signal?.aborted)throw error;if(error instanceof SessionError)throw new RevisionError(error.status);throw new RevisionError(successful?200:0)}finally{token=undefined}
  }
  return{context:s=>request('/context','RevisionContextData',s),history:(v,s)=>request('/history/'+id(v),'RevisionHistoryData',s),propose:(v,s)=>request('','RevisionResult',s,v),get:(v,s)=>request('/'+id(v),'RevisionData',s),decide:(v,input,s)=>request('/'+id(v)+'/decision','RevisionResult',s,input)}
}
