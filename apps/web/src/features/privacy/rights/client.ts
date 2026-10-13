import type { ExportContent, RightsContext, RightsRequestData } from '../../../../../../packages/contracts/v2/rights/generated'
import { createSessionApi, SessionError } from '../../auth/client'

export type { ExportContent, RightsContext, RightsRequestData }
export type RightsKind = RightsRequestData['kind']
export interface RightsApi {
  context(signal?: AbortSignal): Promise<RightsContext>
  create(kind: RightsKind, signal?: AbortSignal): Promise<RightsRequestData>
  get(kind: RightsKind, id: string, signal?: AbortSignal): Promise<RightsRequestData>
  content(id: string, signal?: AbortSignal): Promise<ExportContent>
}
export class RightsError extends Error {
  constructor(public readonly status: number) { super(({401:'当前会话已失效，请重新登录。',403:'当前操作未获准，请重新读取本人设置。',404:'无法读取此本人受理记录。',409:'当前状态已变化，请重新读取。',422:'请求或响应不符合资料权利契约。',503:'资料权利服务未开放或最新恢复证明不可用。'} as Record<number,string>)[status] ?? '本次资料权利操作无法确认，请重新读取。'); this.name='RightsError' }
}
export const uuid = (v: unknown): v is string => typeof v === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(v)
const record = (v: unknown): v is Record<string,unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const fields = (v: Record<string,unknown>, keys: string[]) => Object.keys(v).length === keys.length && keys.every(k=>k in v)
const member = (v: unknown, choices: readonly string[]) => typeof v === 'string' && choices.includes(v)
const integer = (v: unknown, low: number, high: number) => typeof v === 'number' && Number.isSafeInteger(v) && low <= v && v <= high
export function utc(v: unknown): v is string { return typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(v) && Number.isFinite(Date.parse(v)) && new Date(v).toISOString().slice(0,19) === v.slice(0,19) }
const nullableDate = (v: unknown) => v === null || utc(v)
const reasons = ['OK','RIGHTS_DISABLED','AUTHORITY_REVOKED','OWNER_DELETED','EXPIRED','EXPORT_LIMIT','RETRYABLE_FAILURE','ATTEMPTS_EXHAUSTED','LEASE_LOST','LEDGER_UNAVAILABLE']
export function isContext(v: unknown): v is RightsContext {
  return record(v) && fields(v,['enabled','real_rights_ready','reason','deletion_accepted','online_cleanup_days','responsibility_retention_months','backup_retention_days','max_export_bytes'])
    && typeof v.enabled === 'boolean' && v.real_rights_ready === false && member(v.reason,reasons) && typeof v.deletion_accepted === 'boolean'
    && v.online_cleanup_days === 30 && v.responsibility_retention_months === 24 && v.backup_retention_days === 35 && integer(v.max_export_bytes,1,10485760)
}
export function isRequest(v: unknown): v is RightsRequestData {
  if (!record(v) || !fields(v,['request_id','kind','status','reason','attempts','accepted_at','online_cleanup_due_at','completed_at','artifact_expires_at','online_cleanup_complete','retained_responsibility_until','backup_retention_days','is_synthetic'])) return false
  return uuid(v.request_id) && member(v.kind,['export','deletion']) && member(v.status,['queued','running','failed','completed','cancelled']) && member(v.reason,reasons)
    && integer(v.attempts,0,5) && utc(v.accepted_at) && nullableDate(v.online_cleanup_due_at) && nullableDate(v.completed_at) && nullableDate(v.artifact_expires_at)
    && utc(v.retained_responsibility_until) && Date.parse(v.retained_responsibility_until)>Date.parse(v.accepted_at)
    && v.backup_retention_days === 35 && v.is_synthetic === true && typeof v.online_cleanup_complete === 'boolean'
    && v.online_cleanup_complete === (v.kind === 'deletion' && v.status === 'completed') && (v.status === 'completed') === (v.completed_at !== null)
    && (v.kind === 'deletion') === (v.online_cleanup_due_at !== null) && (v.completed_at === null || Date.parse(String(v.completed_at))>=Date.parse(v.accepted_at))
}
export async function isContent(v: unknown): Promise<boolean> {
  if (!record(v) || !fields(v,['request_id','content_type','content_json','size_bytes','sha256','expires_at','is_synthetic']) || !uuid(v.request_id)
    || v.content_type !== 'application/json' || typeof v.content_json !== 'string' || !integer(v.size_bytes,1,10485760)
    || typeof v.sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(v.sha256) || !utc(v.expires_at) || Date.parse(v.expires_at)<=Date.now() || v.is_synthetic !== true) return false
  try {
    const bytes=new TextEncoder().encode(v.content_json)
    if (bytes.length !== v.size_bytes || bytes.length>10485760 || !record(JSON.parse(v.content_json))) return false
    const digest=await crypto.subtle.digest('SHA-256',bytes)
    return Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('') === v.sha256
  } catch { return false }
}
export function createRightsApi(prefix=import.meta.env.VITE_AUTH_API_BASE_URL ?? '/api', fetcher: typeof fetch=fetch): RightsApi {
  const session=createSessionApi(prefix,fetcher) // Same-origin prefix validation and existing CSRF flow.
  const base=prefix.replace(/\/$/,'')
  const path=(kind: RightsKind,id?:string) => {
    if (!member(kind,['export','deletion']) || (id!==undefined && !uuid(id))) throw new RightsError(422)
    return `privacy/${kind === 'export' ? 'exports' : 'deletions'}${id ? '/'+id : ''}`
  }
  async function read(path: string, signal?: AbortSignal, write=false): Promise<unknown> {
    let token: string|undefined
    if(write) { try { token=(await session.csrf(signal)).csrf_token } catch(e) { if(e instanceof SessionError) throw new RightsError(e.status); throw e } }
    if(signal?.aborted) throw new DOMException('Aborted','AbortError')
    let response: Response
    try { response=await fetcher(`${base}/v2/${path}`,{method:write?'POST':'GET',credentials:'same-origin',cache:'no-store',redirect:'error',signal,
      headers:{Accept:'application/json',...(write?{'Content-Type':'application/json','X-CSRF-Token':token!}:{})},...(write?{body:JSON.stringify({owner_confirmed:true})}:{})}) }
    catch(e) { if(signal?.aborted) throw e; throw new RightsError(0) }
    if(response.status!==200) throw new RightsError(response.status)
    let body: unknown
    try {
      const reader=response.body?.getReader();if(!reader)throw new RightsError(422)
      const parts:Uint8Array[]=[];let size=0
      const limit=path.endsWith('/content')?24*1048576:65536
      try{for(;;){const next=await reader.read();if(next.done)break;size+=next.value.byteLength;if(size>limit){await reader.cancel();throw new RightsError(422)}parts.push(next.value)}}finally{reader.releaseLock()}
      const bytes=new Uint8Array(size);let offset=0;for(const part of parts){bytes.set(part,offset);offset+=part.byteLength}
      body=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes))
    } catch { throw new RightsError(422) }
    if(!record(body)||!fields(body,['data','meta'])||!record(body.meta)||!fields(body.meta,['api_version','request_id','data_as_of','profile_version_id','release_id','ruleset_version','profile_mode','data_mode','model_mode'])
      ||typeof body.meta.request_id!=='string'||!/^[0-9a-f]{32}$/.test(body.meta.request_id)||!member(body.meta.data_mode,['demo','verified'])
      ||!member(body.meta.model_mode,['disabled','mock'])||body.meta.api_version!=='v2'
      ||body.meta.data_as_of!==null||body.meta.profile_version_id!==null||body.meta.release_id!==null||body.meta.ruleset_version!==null||body.meta.profile_mode!==null) throw new RightsError(422)
    return body.data
  }
  async function request(kind: RightsKind,id: string|undefined,signal?: AbortSignal) {
    const value=await read(path(kind,id),signal,id===undefined)
    if(!isRequest(value)||value.kind!==kind||(id!==undefined&&value.request_id!==id)) throw new RightsError(422)
    return value
  }
  return {context:async signal=>{const value=await read('privacy/rights/context',signal);if(!isContext(value)) throw new RightsError(422);return value},
    create:(kind,signal)=>request(kind,undefined,signal),get:(kind,id,signal)=>request(kind,id,signal),
    content:async(id,signal)=>{path('export',id);const value=await read(path('export',id)+'/content',signal);if(!await isContent(value)||(value as ExportContent).request_id!==id) throw new RightsError(422);return value as ExportContent}}
}
