<script setup lang="ts">
import type { ExecutionData } from '../../../../../packages/contracts/v2/plans/generated'
import { localTime, type LocalWorkspace } from './form'
const props=defineProps<{local:LocalWorkspace;current:ExecutionData;disabled:boolean}>()
const emit=defineEmits<{changed:[];save:[]}>()
function addSlot(){props.local.slots.push({id:crypto.randomUUID(),start:'',end:''});emit('changed')}
function removeSlot(id:string){props.local.slots=props.local.slots.filter(s=>s.id!==id);emit('changed')}
</script>
<template>
 <form class="workspace-form" data-testid="plan-workspace-form" @submit.prevent="emit('save')">
  <fieldset :disabled="disabled"><legend>1 / 核对任务估时</legend><p>空白是未知，0 是零工时里程碑。估时可修改，不代表教育诊断或保证结果。</p>
   <div class="estimates"><label v-for="task in current.proposal.effective_draft.tasks" :key="task.task_key">{{ task.title }}<span>小时<input v-model="local.estimates[task.task_key]" :data-testid="`plan-estimate-${task.task_key}`" type="text" inputmode="decimal" autocomplete="off" placeholder="未知" @input="emit('changed')"></span></label></div>
  </fieldset>
  <fieldset :disabled="disabled"><legend>2 / 本人明确安排可用时间</legend><label class="check"><input v-model="local.scheduleEnabled" type="checkbox" data-testid="plan-schedule-enabled" @change="emit('changed')"><span>本次保存包括容量安排（取消则仅保存估时）</span></label>
   <template v-if="local.scheduleEnabled"><p>请填写完整 UTC 时刻，末尾为 Z 或 +00:00，最多六位小数。IANA 时区仅用于显示；不按设备时区推断可用时间。</p>
    <div class="field-grid"><label>区间开始 · UTC<input v-model="local.horizonStart" data-testid="plan-horizon-start" placeholder="YYYY-MM-DDTHH:mm:ss.ffffffZ" autocomplete="off" @input="emit('changed')"></label><label>区间结束 · UTC<input v-model="local.horizonEnd" data-testid="plan-horizon-end" placeholder="YYYY-MM-DDTHH:mm:ss.ffffffZ" autocomplete="off" @input="emit('changed')"></label><label>显示时区 · IANA<input v-model="local.timezone" data-testid="plan-timezone" placeholder="例如 Asia/Shanghai" autocomplete="off" @input="emit('changed')"></label><label>每周最多小时 · 0–40<input v-model="local.weeklyHours" data-testid="plan-weekly-hours" type="text" inputmode="decimal" placeholder="未知" autocomplete="off" @input="emit('changed')"></label></div>
    <p class="preview">{{ localTime(local.horizonStart,local.timezone) }}</p>
    <div v-for="slot in local.slots" :key="slot.id" class="slot"><div class="field-grid"><label>可用时段开始 · UTC<input v-model="slot.start" :data-testid="`plan-slot-start-${slot.id}`" autocomplete="off" @input="emit('changed')"></label><label>可用时段结束 · UTC<input v-model="slot.end" :data-testid="`plan-slot-end-${slot.id}`" autocomplete="off" @input="emit('changed')"></label></div><p class="preview">{{ localTime(slot.start,local.timezone) }}</p><button type="button" class="secondary" @click="removeSlot(slot.id)">移除此时段</button></div>
    <button type="button" class="secondary" data-testid="plan-slot-add" :disabled="local.slots.length>=256" @click="addSlot">添加可用时段</button>
    <details><summary>可选：本人内部完成目标</summary><p>内部目标不是学校截止；任务必须在该时刻之前完成。</p><label v-for="task in current.proposal.effective_draft.tasks" :key="task.task_key">{{ task.title }} · UTC<input v-model="local.goals[task.task_key]" :data-testid="`plan-goal-${task.task_key}`" placeholder="不设置" autocomplete="off" @input="emit('changed')"></label></details>
    <label class="check"><input v-model="local.availabilityConfirmed" type="checkbox" data-testid="plan-availability-confirmation"><span>我明确确认这些时间确实可用。</span></label><label class="check"><input v-model="local.restExcluded" type="checkbox" data-testid="plan-rest-excluded"><span>我已排除休息及其他占用，不要求自动增加工作量。</span></label>
   </template>
  </fieldset><button class="primary" type="submit" data-testid="plan-workspace-save" :disabled="disabled">保存估时与安排方案</button>
 </form>
</template>
<style scoped>
fieldset{min-width:0;border:1px solid #dbe4d5;border-radius:8px;padding:20px;margin:20px 0}legend{font-size:13px;padding:0 7px}p,.preview{font-size:11px;line-height:1.9;color:#788674}label{display:flex;flex-direction:column;gap:7px;font-size:11px;line-height:1.8;min-width:0}input:not([type=checkbox]){width:100%;min-width:0;border:1px solid #c8d6c0;border-radius:6px;padding:10px 12px;background:#fff;color:#365b45;font-size:11px}.field-grid,.estimates{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:15px}.estimates label{padding:12px;background:#f6f8f2;border-radius:6px}.estimates span{display:flex;align-items:center;gap:9px}.check{display:flex;flex-direction:row;gap:10px;align-items:flex-start;margin:18px 0}.check input{width:17px;height:17px;flex:0 0 17px;margin:2px 0 0}.slot{border-top:1px solid #e2e8db;padding-top:18px;margin-top:18px}button{border:1px solid #b9cdb5;border-radius:6px;padding:11px 15px;font-size:11px;color:#436647;background:#fff}.primary{background:#1b6453;color:white;border-color:#1b6453}button:disabled{background:#edf1e8;color:#8e9985}details{margin:20px 0;font-size:11px}details label{margin:15px 0}summary{cursor:pointer}fieldset:disabled{opacity:.65}:focus-visible{outline:3px solid #8cb6a4;outline-offset:3px}@media(max-width:650px){.field-grid,.estimates{grid-template-columns:1fr}fieldset{padding:17px 13px}}
</style>
