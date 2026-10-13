import specification from '../../../../../packages/contracts/v2/plans/openapi.json'
import type { ExecutionData, ExecutionPage, ExecutionContextData, PlanDraft, ScheduleDraft } from '../../../../../packages/contracts/v2/plans/generated'
import { canonicalHash, calendarDate, exact, integer, utc, uuid } from '../catalog/validation'

type Schema = { $ref?: string; type?: string; anyOf?: Schema[]; const?: unknown; enum?: unknown[]; properties?: Record<string, Schema>; required?: string[]; additionalProperties?: boolean; items?: Schema; minItems?: number; maxItems?: number; minimum?: number; maximum?: number; minLength?: number; maxLength?: number; pattern?: string; format?: string }
const schemas = specification.components.schemas as Record<string, Schema>
// Read only the committed plans schema. Unsupported shapes fail closed.
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
    if (s.type === 'string') return typeof v === 'string' && [...v].length >= (s.minLength ?? 0) && [...v].length <= (s.maxLength ?? 262144) && !/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/.test(v) && (!s.pattern || new RegExp(s.pattern).test(v)) && (s.format !== 'uuid' || uuid(v)) && (s.format !== 'date-time' || utc(v)) && (s.format !== 'date' || calendarDate(v))
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
export function utcMicros(value: string): bigint {
  if (!utc(value)) throw new Error('请输入带 Z 或 +00:00 的完整 UTC 时刻，最多六位小数。')
  const milliseconds = Date.parse(value.slice(0, 19) + 'Z')
  const fraction = value.slice(19).match(/^\.(\d{1,6})/)?.[1] ?? ''
  return BigInt(milliseconds) * 1000n + BigInt(fraction.padEnd(6, '0'))
}
export function hours(value: unknown, maximum = 1000): value is string {
  if (typeof value !== 'string' || !/^(0|[1-9][0-9]{0,6})(\.[0-9]{1,6})?$/.test(value)) return false
  return hourMicros(value) <= maximum * 3600000000
}
export function hourMicros(value: string): number { const [whole, fraction = ''] = value.split('.'); return Number(whole) * 3600000000 + Number(fraction.padEnd(6, '0')) * 3600 }
const unique = (values: readonly string[]) => new Set(values).size === values.length
const without = (v: object, key: string) => Object.fromEntries(Object.entries(v).filter(([k]) => k !== key))
const taskFields = ['kind','action_code','title','acceptance_criteria','assessment_key','basis','unit','scale','work_scope_sha256']
async function validDraft(draft: PlanDraft): Promise<boolean> {
  if (draft.draft_sha256 !== await canonicalHash(without(draft, 'draft_sha256')) || utcMicros(draft.generated_at) >= utcMicros(draft.expires_at) || !unique(draft.tasks.map(t => t.task_key)) || !unique(draft.assessment_refs.map(r => r.assessment_id)) || !unique(draft.deadline_refs.map(r => r.deadline_key)) || !unique(draft.warnings)) return false
  const tasks = new Map(draft.tasks.map(t => [t.task_key, t])), deadlines = new Map(draft.deadline_refs.map(r => [r.deadline_key, r])), sources = new Set(draft.assessment_refs.map(r => r.assessment_id))
  for (const d of draft.deadline_refs) if (!sources.has(d.assessment_id) || d.deadline_key !== await canonicalHash(without(d, 'deadline_key')) || d.date_event && (d.date_event.utc_instant !== null || d.date_event.id !== d.event_id)) return false
  for (const t of draft.tasks) {
    if (t.task_key !== await canonicalHash(Object.fromEntries(taskFields.map(k => [k, t[k as keyof typeof t]]))) || t.estimated_hours !== null && !hours(t.estimated_hours) || (t.estimated_hours === null) !== (t.estimate_source === 'unknown') || !unique(t.dependency_keys) || !unique(t.deadline_keys) || t.dependency_keys.includes(t.task_key) || t.dependency_keys.some(k => !tasks.has(k)) || t.assessment_ids.some(id => !sources.has(id)) || t.deadline_keys.some(k => !deadlines.has(k) || !t.assessment_ids.includes(deadlines.get(k)!.assessment_id))) return false
  }
  const visiting = new Set<string>(), done = new Set<string>()
  function visit(key: string): boolean { if (visiting.has(key)) return false; if (done.has(key)) return true; visiting.add(key); if (!tasks.get(key)!.dependency_keys.every(visit)) return false; visiting.delete(key); done.add(key); return true }
  return draft.tasks.every(t => visit(t.task_key))
}
async function validSchedule(s: ScheduleDraft, d: PlanDraft, config: ExecutionData['proposal']['schedule_configuration']): Promise<boolean> {
  if (s.schedule_sha256 !== await canonicalHash(without(s, 'schedule_sha256')) || s.draft_sha256 !== d.draft_sha256 || s.profile_id !== d.profile_id || s.profile_version_id !== d.profile_version_id || s.profile_sha256 !== d.profile_sha256 || s.is_synthetic !== d.is_synthetic || JSON.stringify(s.assessment_refs) !== JSON.stringify(d.assessment_refs) || JSON.stringify(s.deadline_refs) !== JSON.stringify(d.deadline_refs) || s.weekly_hours !== null && !hours(s.weekly_hours, 40) || !unique(s.tasks.map(t => t.task_key)) || s.tasks.length !== d.tasks.length || s.tasks.some(t => !d.tasks.some(k => k.task_key === t.task_key))) return false
  if (!config || utcMicros(s.horizon_start) >= utcMicros(s.horizon_end) || utcMicros(s.horizon_end) > utcMicros(d.expires_at) || !unique(config.slots.map(v=>v.slot_id)) || !unique(s.weeks.map(v=>v.week_start))) return false
  const allocations=[...s.allocations].sort((a,b)=>utcMicros(a.start_at)<utcMicros(b.start_at)?-1:1),tasks=new Map(s.tasks.map(t=>[t.task_key,t]))
  const displayWeek=(at:bigint)=>{const parts=new Intl.DateTimeFormat('en-US',{timeZone:s.display_timezone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(Number(at/1000n)));const get=(type:string)=>parts.find(p=>p.type===type)!.value;const day=new Date(0);day.setUTCFullYear(Number(get('year')),Number(get('month'))-1,Number(get('day')));day.setUTCHours(0,0,0,0);day.setUTCDate(day.getUTCDate()-(day.getUTCDay()+6)%7);return day.toISOString().slice(0,10)}
  for (const [i,a] of allocations.entries()) {
    const start=utcMicros(a.start_at),end=utcMicros(a.end_at),slot=config.slots.find(v=>v.slot_id===a.slot_id)
    if (end-start !== BigInt(a.duration_microseconds) || end<=start || !tasks.has(a.task_key) || start<utcMicros(s.horizon_start) || end>utcMicros(s.horizon_end) || !slot || start<utcMicros(slot.start_at) || end>utcMicros(slot.end_at) || i>0&&utcMicros(allocations[i-1]!.end_at)>start || !s.weeks.some(w=>w.week_start===a.week_start) || displayWeek(start)!==a.week_start || displayWeek(end-1n)!==a.week_start) return false
  }
  for (const t of s.tasks) {
    const original=d.tasks.find(v=>v.task_key===t.task_key)!,rows=allocations.filter(a=>a.task_key===t.task_key),sum=rows.reduce((n,a)=>n+a.duration_microseconds,0)
    const goal=config.internal_goals.find(g=>g.task_key===t.task_key)?.due_at??null
    if((goal===null)!==(t.internal_goal===null)||goal!==null&&utcMicros(goal)!==utcMicros(t.internal_goal!))return false
    if(t.action_code!==original.action_code||t.estimated_hours!==original.estimated_hours||JSON.stringify(t.assessment_ids)!==JSON.stringify(original.assessment_ids)||JSON.stringify(t.dependency_keys)!==JSON.stringify(original.dependency_keys)||t.assigned_microseconds!==sum||t.estimated_hours!==null&&(!hours(t.estimated_hours)||t.estimated_microseconds!==hourMicros(t.estimated_hours))||(t.estimated_hours===null)!==(t.estimated_microseconds===null)||(t.estimated_microseconds===null?t.remaining_microseconds!==null:t.remaining_microseconds!==t.estimated_microseconds-t.assigned_microseconds))return false
    if(t.status==='blocked'?(sum!==0||t.start_at!==null||t.end_at!==null):t.status==='milestone'?(t.estimated_microseconds!==0||sum!==0||t.start_at===null||t.end_at!==t.start_at):(t.estimated_microseconds===null||t.estimated_microseconds<=0||t.remaining_microseconds!==0||!rows.length||t.start_at!==rows[0]!.start_at||t.end_at!==rows.at(-1)!.end_at))return false
    if(t.status!=='blocked'&&(utcMicros(t.start_at!)<utcMicros(s.horizon_start)||utcMicros(t.end_at!)>utcMicros(s.horizon_end)||t.dependency_keys.some(k=>!tasks.has(k)||tasks.get(k)!.status==='blocked'||utcMicros(tasks.get(k)!.end_at!)>utcMicros(t.start_at!))||t.internal_goal!==null&&utcMicros(t.end_at!)>=utcMicros(t.internal_goal)))return false
  }
  for(const w of s.weeks){const assigned=allocations.filter(a=>a.week_start===w.week_start).reduce((n,a)=>n+a.duration_microseconds,0);if(w.assigned_microseconds!==assigned||w.capacity_microseconds!==(s.weekly_hours===null?null:hourMicros(s.weekly_hours))||w.capacity_microseconds!==null&&assigned>w.capacity_microseconds)return false}
  const blocked=s.tasks.filter(t=>t.status==='blocked').length
  if(s.status!==(blocked===0?'ready':blocked===s.tasks.length?'blocked':'partial'))return false
  return true
}
export async function validExecution(value: unknown): Promise<boolean> {
  if (!wire('ExecutionData', value)) return false
  const e = value as ExecutionData, p = e.proposal, d = p.effective_draft
  if (!await validDraft(d) || e.is_synthetic !== d.is_synthetic || e.created_at !== d.generated_at || e.expires_at !== d.expires_at || utcMicros(e.created_at) > utcMicros(p.created_at) || utcMicros(p.created_at) >= utcMicros(e.expires_at) || p.state_version > e.state_version || (e.state === 'confirmed') !== (e.confirmation !== null)) return false
  if ((p.schedule === null) !== (p.schedule_configuration === null) || p.estimate_overrides.some(v => !d.tasks.some(t => t.task_key === v.task_key && t.estimated_hours === v.estimated_hours))) return false
  if (p.schedule) {
    if (!await validSchedule(p.schedule, d, p.schedule_configuration) || p.schedule.generated_at !== p.created_at || ['horizon_start','horizon_end','display_timezone','weekly_hours'].some(k => (p.schedule as unknown as Record<string,unknown>)[k] !== (p.schedule_configuration as unknown as Record<string,unknown>)[k])) return false
  }
  const c = e.confirmation, completed = new Map(e.completed_tasks.map(t => [t.task_key, t]))
  if (!unique(e.completed_tasks.map(t => t.task_key)) || new Set(e.completed_tasks.map(t => t.completed_state_version)).size !== e.completed_tasks.length) return false
  if (c) {
    if (c.proposal_id !== p.id || c.confirmed_state_version <= p.state_version || c.confirmed_state_version > e.state_version || !p.schedule || p.schedule.status !== 'ready' || p.schedule.weekly_hours === null || utcMicros(c.confirmed_at) < utcMicros(p.created_at) || utcMicros(c.confirmed_at) >= utcMicros(p.schedule.horizon_end) || p.schedule.allocations.some(a => utcMicros(a.start_at) < utcMicros(c.confirmed_at)) || p.schedule.tasks.some(t=>t.status==='milestone'&&utcMicros(t.start_at!)<utcMicros(c.confirmed_at))) return false
  } else if (e.completed_tasks.length) return false
  return e.completed_tasks.every(t => { const task = d.tasks.find(k => k.task_key === t.task_key); return !!task && !!c && t.completed_state_version > c.confirmed_state_version && t.completed_state_version <= e.state_version && utcMicros(t.completed_at) >= utcMicros(c.confirmed_at) && utcMicros(t.completed_at)<utcMicros(e.expires_at) && task.dependency_keys.every(k => completed.has(k) && completed.get(k)!.completed_state_version < t.completed_state_version) })
}
export function validContext(value: unknown): value is ExecutionContextData { return wire('ExecutionContextData', value) && ((value as ExecutionContextData).reason !== 'processing_disabled' || ['can_create','can_read','can_edit','can_confirm','can_complete'].every(k => !(value as unknown as Record<string, unknown>)[k])) }
export function validPage(value: unknown): value is ExecutionPage { return wire('ExecutionPage', value) && unique((value as ExecutionPage).items.map(v => v.plan_id)) && (value as ExecutionPage).items.every(v => utcMicros(v.created_at) < utcMicros(v.expires_at) && (v.state === 'confirmed') === (v.confirmation_id !== null) && (v.state === 'confirmed' || v.completed_count === 0)) }
