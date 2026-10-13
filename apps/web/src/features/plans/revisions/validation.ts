import specification from '../../../../../../packages/contracts/v2/revisions/openapi.json'
import { calendarDate, canonicalHash, integer, uuid } from '../../catalog/validation'
import { utcMicros, validExecution } from '../validation'
import type { ExecutionData } from '../client'
import type { ProfileVersionData } from '../../profiles/client'
import type { PlanPin, RevisionContextData, RevisionData, RevisionHistoryData } from '../../../../../../packages/contracts/v2/revisions/generated'

type Schema = { $ref?: string; type?: string; anyOf?: Schema[]; const?: unknown; enum?: unknown[]; properties?: Record<string, Schema>; required?: string[]; additionalProperties?: boolean; items?: Schema; minItems?: number; maxItems?: number; minimum?: number; maximum?: number; minLength?: number; maxLength?: number; pattern?: string; format?: string }
const schemas = specification.components.schemas as Record<string, Schema>

// Only the committed revisions contract is accepted. No guessed response fields.
export function wire(name: string, value: unknown): boolean {
  let nodes = 0
  function check(s: Schema | undefined, v: unknown, depth: number): boolean {
    if (!s || ++nodes > 100000 || depth > 40) return false
    if (s.$ref) return check(schemas[s.$ref.split('/').pop()!], v, depth + 1)
    if (s.anyOf) return s.anyOf.some(option => check(option, v, depth + 1))
    if (Object.hasOwn(s, 'const') && s.const !== v || s.enum && !s.enum.includes(v)) return false
    if (s.type === 'null') return v === null
    if (s.type === 'boolean') return typeof v === 'boolean'
    if (s.type === 'integer' || s.type === 'number') return typeof v === 'number' && Number.isSafeInteger(v) && v >= (s.minimum ?? -Number.MAX_SAFE_INTEGER) && v <= (s.maximum ?? Number.MAX_SAFE_INTEGER)
    if (s.type === 'string') {
      if (typeof v !== 'string' || [...v].length < (s.minLength ?? 0) || [...v].length > (s.maxLength ?? 262144) || /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/.test(v) || s.pattern && !new RegExp(s.pattern).test(v)) return false
      if (s.format === 'uuid') return uuid(v)
      if (s.format === 'date-time') { try { utcMicros(v); return true } catch { return false } }
      if (s.format === 'date') return calendarDate(v)
      if (s.format === 'time') return /^(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\.[0-9]{1,6})?$/.test(v)
      return !s.format
    }
    if (s.type === 'array') return Array.isArray(v) && v.length >= (s.minItems ?? 0) && v.length <= (s.maxItems ?? 4096) && v.every(item => check(s.items, item, depth + 1))
    if (s.type === 'object') {
      if (v === null || typeof v !== 'object' || Array.isArray(v) || Object.getPrototypeOf(v) !== Object.prototype || !s.properties || s.additionalProperties !== false) return false
      const object = v as Record<string, unknown>
      return (s.required ?? []).every(k => Object.hasOwn(object, k)) && Object.keys(object).every(k => Object.hasOwn(s.properties!, k) && check(s.properties![k], object[k], depth + 1))
    }
    return false
  }
  return check(schemas[name], value, 0)
}

export const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value))
export const equal = (a: unknown, b: unknown): boolean => JSON.stringify(order(a)) === JSON.stringify(order(b))
function order(v: unknown): unknown { return Array.isArray(v) ? v.map(order) : v !== null && typeof v === 'object' ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([k, x]) => [k, order(x)])) : v }
export const unique = (values: readonly string[]): boolean => new Set(values).size === values.length
export const hashWithout = (value: object, key: string): Promise<string> => canonicalHash(Object.fromEntries(Object.entries(value).filter(([k]) => k !== key)))

export function sameCurrent(a: ExecutionData | null, b: ExecutionData | null): boolean {
  if (!a || !b) return a === b
  const pin = (e: ExecutionData) => [e.plan_id, e.source_plan_version_id, e.source_draft_sha256, e.state_version, e.state, e.proposal.id, e.proposal.effective_draft.profile_id, e.proposal.effective_draft.profile_version_id, e.proposal.effective_draft.profile_sha256, e.proposal.effective_draft.draft_sha256, e.proposal.schedule?.schedule_sha256 ?? null, e.is_synthetic]
  return equal(pin(a), pin(b))
}
export function bindsProfile(e: ExecutionData, p: ProfileVersionData): boolean {
  const d = e.proposal.effective_draft
  return d.profile_id === p.profile_id && d.profile_version_id === p.version_id && d.profile_sha256 === p.profile_sha256 && e.is_synthetic === p.is_synthetic
}
export async function validNewPlan(e: unknown, p: ProfileVersionData): Promise<boolean> {
  return await validExecution(e) && (e as ExecutionData).state === 'draft' && (e as ExecutionData).completed_tasks.length === 0 && bindsProfile(e as ExecutionData, p) && integer((e as ExecutionData).state_version)
}

export function pinMatches(e: ExecutionData, p: PlanPin): boolean {
  const d=e.proposal.effective_draft
  return p.plan_id===e.plan_id && p.source_plan_version_id===e.source_plan_version_id && p.state_version===e.state_version && p.state===e.state && p.proposal_id===e.proposal.id && p.proposal_state_version===e.proposal.state_version && p.source_draft_sha256===e.source_draft_sha256 && p.draft_sha256===d.draft_sha256 && p.schedule_sha256===(e.proposal.schedule?.schedule_sha256??null) && p.profile_id===d.profile_id && p.profile_version_id===d.profile_version_id && p.profile_sha256===d.profile_sha256 && p.confirmation_id===(e.confirmation?.id??null) && p.is_synthetic===e.is_synthetic
}
export function validContext(value: unknown): value is RevisionContextData {
  return wire('RevisionContextData',value) && ((value as RevisionContextData).reason!=='processing_disabled'||['can_read_history','can_propose','can_decide'].every(k=>!(value as unknown as Record<string,unknown>)[k]))
}
export async function validHistory(value: unknown): Promise<boolean> {
  if(!wire('RevisionHistoryData',value))return false
  const h=value as RevisionHistoryData,p=h.pin,tasks=new Map(h.tasks.map(t=>[t.task_key,t])),sources=new Set(h.sources.map(s=>s.assessment_id)),deadlines=new Set(h.deadlines.map(d=>d.deadline_key))
  if(p.proposal_state_version>p.state_version||(p.state==='confirmed')!==(p.confirmation_id!==null)||utcMicros(h.created_at)>=utcMicros(h.expires_at)||tasks.size!==h.tasks.length||sources.size!==h.sources.length||deadlines.size!==h.deadlines.length||!unique(h.completion_refs.map(c=>c.completion_id))||!unique(h.completion_refs.map(c=>c.task_key))||!unique(h.completion_refs.map(c=>String(c.completed_state_version))))return false
  const taskFields=['kind','action_code','title','acceptance_criteria','assessment_key','basis','unit','scale','work_scope_sha256']
  for(const t of h.tasks){
    if(t.task_key!==await canonicalHash(Object.fromEntries(taskFields.map(k=>[k,t[k as keyof typeof t]])))||!unique(t.assessment_ids)||!unique(t.dependency_keys)||!unique(t.deadline_keys)||t.dependency_keys.includes(t.task_key)||t.dependency_keys.some(k=>!tasks.has(k))||t.assessment_ids.some(id=>!sources.has(id))||t.deadline_keys.some(k=>!deadlines.has(k)))return false
  }
  const active=new Set<string>(),done=new Set<string>()
  const visit=(k:string):boolean=>{if(active.has(k))return false;if(done.has(k))return true;active.add(k);if(!tasks.get(k)!.dependency_keys.every(visit))return false;active.delete(k);done.add(k);return true}
  if(!h.tasks.every(t=>visit(t.task_key)))return false
  for(const d of h.deadlines){if(!sources.has(d.assessment_id)||d.precision===null&&(d.local_date!==null||d.local_time!==null)||d.precision==='unknown'&&(d.local_date!==null||d.local_time!==null||d.timezone!==null)||d.precision==='date'&&(d.local_date===null||d.local_time!==null)||['minute','second'].includes(d.precision??'')&&(d.local_date===null||d.local_time===null))return false}
  if(p.state==='draft'&&h.completion_refs.length)return false
  const completed=new Map(h.completion_refs.map(c=>[c.task_key,c]))
  for(const c of h.completion_refs){const t=tasks.get(c.task_key);if(!t||c.confirmation_id!==p.confirmation_id||c.completed_state_version>p.state_version||utcMicros(c.completed_at)<utcMicros(h.created_at)||utcMicros(c.completed_at)>=utcMicros(h.expires_at)||t.dependency_keys.some(k=>!completed.has(k)||completed.get(k)!.completed_state_version>=c.completed_state_version))return false}
  const s=h.schedule
  if((s===null)!==(p.schedule_sha256===null))return false
  if(s){
    if(utcMicros(s.generated_at)<utcMicros(h.created_at)||utcMicros(s.generated_at)>=utcMicros(h.expires_at)||utcMicros(s.horizon_start)>=utcMicros(s.horizon_end)||utcMicros(s.horizon_end)>utcMicros(h.expires_at)||!unique(s.tasks.map(t=>t.task_key))||s.tasks.length!==h.tasks.length)return false
    const allocations=[...s.allocations].sort((a,b)=>utcMicros(a.start_at)<utcMicros(b.start_at)?-1:1)
    for(const [i,a] of allocations.entries())if(!tasks.has(a.task_key)||utcMicros(a.end_at)-utcMicros(a.start_at)!==BigInt(a.duration_microseconds)||a.duration_microseconds<=0||utcMicros(a.start_at)<utcMicros(s.horizon_start)||utcMicros(a.end_at)>utcMicros(s.horizon_end)||i>0&&utcMicros(allocations[i-1]!.end_at)>utcMicros(a.start_at))return false
    for(const t of s.tasks){const original=tasks.get(t.task_key),rows=allocations.filter(a=>a.task_key===t.task_key);if(!original||t.action_code!==original.action_code||t.estimated_hours!==original.estimated_hours||!equal(t.dependency_keys,original.dependency_keys)||t.assigned_microseconds!==rows.reduce((sum,a)=>sum+a.duration_microseconds,0)||t.status==='scheduled'&&(!rows.length||t.start_at!==rows[0]!.start_at||t.end_at!==rows.at(-1)!.end_at||t.remaining_microseconds!==0)||t.status==='milestone'&&(rows.length!==0||t.estimated_microseconds!==0||t.start_at===null||t.end_at!==t.start_at)||t.status==='blocked'&&(rows.length!==0||t.start_at!==null||t.end_at!==null))return false}
  }
  return true
}
export async function validRevision(value: unknown): Promise<boolean> {
  if(!wire('RevisionData',value))return false
  const r=value as RevisionData,a=r.old.pin,b=r.new.pin,d=r.decision,x=r.replacement
  if(!await validHistory(r.old)||!await validHistory(r.new)||a.plan_id===b.plan_id||a.state!=='confirmed'||b.state!=='draft'||a.profile_id!==b.profile_id||a.is_synthetic!==b.is_synthetic||a.is_synthetic!==r.is_synthetic||r.new.completion_refs.length||!unique(r.diff.changed_fields)||r.diff.business_changed!==true||r.diff.diff_sha256!==await hashWithout(r.diff,'diff_sha256'))return false
  if(utcMicros(r.created_at)<utcMicros(r.old.created_at)||utcMicros(r.created_at)<utcMicros(r.new.created_at)||utcMicros(r.created_at)>=utcMicros(r.expires_at)||utcMicros(r.expires_at)>utcMicros(r.old.expires_at)||utcMicros(r.expires_at)>utcMicros(r.new.expires_at))return false
  if(!d){if(r.status!=='proposed'||r.revision_version!==1||x!==null)return false}
  else if(r.revision_version!==2||r.status!==(d.action==='accept'?'accepted':'rejected')||utcMicros(d.decided_at)<utcMicros(r.created_at)||utcMicros(d.decided_at)>=utcMicros(r.expires_at)||(d.action==='accept')!==(x!==null)||x&&(x.old_plan_id!==a.plan_id||x.new_plan_id!==b.plan_id||utcMicros(x.accepted_at)!==utcMicros(d.decided_at)))return false
  return r.proposal_sha256===await canonicalHash(Object.fromEntries(['revision_id','old','new','diff','created_at','expires_at','is_synthetic'].map(k=>[k,r[k as keyof RevisionData]])))
}
