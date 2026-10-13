import type { ExecutionData, HttpWorkspaceInput } from '../../../../../packages/contracts/v2/plans/generated'
import { hourMicros, hours, utcMicros } from './validation'
import { uuid } from '../catalog/validation'
export interface LocalWorkspace { estimates:Record<string,string>; scheduleEnabled:boolean; horizonStart:string;horizonEnd:string;timezone:string;weeklyHours:string;slots:{id:string;start:string;end:string}[];goals:Record<string,string>;availabilityConfirmed:boolean;restExcluded:boolean }
export function emptyLocal():LocalWorkspace{return{estimates:{},scheduleEnabled:false,horizonStart:'',horizonEnd:'',timezone:'',weeklyHours:'',slots:[],goals:{},availabilityConfirmed:false,restExcluded:false}}
export function fromExecution(e:ExecutionData):LocalWorkspace{const c=e.proposal.schedule_configuration;return{estimates:Object.fromEntries(e.proposal.effective_draft.tasks.map(t=>[t.task_key,t.estimated_hours??''])),scheduleEnabled:c!==null,horizonStart:c?.horizon_start??'',horizonEnd:c?.horizon_end??'',timezone:c?.display_timezone??'',weeklyHours:c?.weekly_hours??'',slots:c?.slots.map(s=>({id:s.slot_id,start:s.start_at,end:s.end_at}))??[],goals:Object.fromEntries(c?.internal_goals.map(g=>[g.task_key,g.due_at])??[]),availabilityConfirmed:false,restExcluded:false}}
export function workspaceInput(local:LocalWorkspace,current:ExecutionData):HttpWorkspaceInput{
 const keys=current.proposal.effective_draft.tasks.map(t=>t.task_key)
 if(Object.keys(local.estimates).some(k=>!keys.includes(k)))throw new Error('估时必须对应当前任务。')
 const estimates=keys.map(task_key=>{const value=local.estimates[task_key]??'';if(value!==''&&!hours(value))throw new Error('估时须为 0–1000 小时的十进制字符串，最多六位小数；空白表示未知。');return{task_key,estimated_hours:value===''?null:value}})
 if(!local.scheduleEnabled)return{expected_version:current.state_version,estimate_overrides:estimates,schedule:null}
 const start=utcMicros(local.horizonStart),end=utcMicros(local.horizonEnd)
 if(start>=end||end-start>84n*86400000000n||end>utcMicros(current.expires_at)||start<utcMicros(current.proposal.created_at))throw new Error('安排区间须有效、最多 84 天，并在服务端来源有效期内。')
 if(!/^(UTC|(?:Africa|America|Antarctica|Arctic|Asia|Atlantic|Australia|Europe|Indian|Pacific)\/[A-Za-z0-9_+\-/]+)$/.test(local.timezone))throw new Error('请明确填写 IANA 时区，例如 Asia/Shanghai。')
 try{new Intl.DateTimeFormat('zh-CN',{timeZone:local.timezone})}catch{throw new Error('显示时区无效。')}
 if(local.weeklyHours!==''&&!hours(local.weeklyHours,40))throw new Error('每周容量须为 0–40 小时；空白表示未知。')
 if(!local.availabilityConfirmed||!local.restExcluded)throw new Error('请分别确认可用时段以及已排除休息。')
 if(local.slots.length>256||new Set(local.slots.map(s=>s.id)).size!==local.slots.length)throw new Error('可用时段过多或重复。')
 const slots=local.slots.map(s=>{const a=utcMicros(s.start),b=utcMicros(s.end);if(!uuid(s.id)||a<start||b>end||a>=b||b-a>8n*3600000000n)throw new Error('每段可用时间须在区间内、为正且最多八小时。');return{slot_id:s.id,start_at:s.start,end_at:s.end}}).sort((a,b)=>utcMicros(a.start_at)<utcMicros(b.start_at)?-1:1)
 if(slots.some((s,i)=>i>0&&utcMicros(slots[i-1]!.end_at)>utcMicros(s.start_at))||slots.reduce((sum,s)=>sum+utcMicros(s.end_at)-utcMicros(s.start_at),0n)>520n*3600000000n)throw new Error('可用时段不可重叠，总量不得超过 520 小时。')
 const goals=Object.entries(local.goals).filter(([,v])=>v!=='').map(([task_key,due_at])=>{const at=utcMicros(due_at);if(!keys.includes(task_key)||at<start||at>end)throw new Error('内部目标须对应当前任务及安排区间。');return{task_key,due_at}})
 return{expected_version:current.state_version,estimate_overrides:estimates,schedule:{horizon_start:local.horizonStart,horizon_end:local.horizonEnd,display_timezone:local.timezone,weekly_hours:local.weeklyHours===''?null:local.weeklyHours,slots,internal_goals:goals,availability_confirmed:true,rest_excluded:true}}
}
export function localTime(value:string,zone:string):string{try{utcMicros(value);return new Intl.DateTimeFormat('zh-CN',{timeZone:zone,dateStyle:'medium',timeStyle:'long'}).format(new Date(value))+'（显示预览；提交保留原 UTC 微秒）'}catch{return'明确填写 UTC 时刻及 IANA 时区后显示预览。'}}
export const microHours=(n:number)=>String(n/3600000000)
