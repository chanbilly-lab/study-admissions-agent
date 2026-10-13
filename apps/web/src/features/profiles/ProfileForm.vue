<script setup lang="ts">
import { computed, ref } from 'vue'
import { allowedAssessments, asksGaokao, asksLanguage, assessmentKeys, assessmentLabels, scopeFields, type AssessmentKey, type ProfileDraft, type ScopeField } from './form'
const props = defineProps<{ draft: ProfileDraft; busy: boolean; canSave: boolean; validation: string; synthetic: boolean }>()
const emit = defineEmits<{ changed: [route?: boolean]; add: [key: AssessmentKey]; remove: [key: AssessmentKey]; save: [] }>()
const addKey = ref<AssessmentKey | ''>('')
const slots = ['achieved', 'predicted'] as const
const choices: Record<ScopeField, [string, string][]> = {
  residence_region: [['CN', '中国大陆'], ['HK', '中国香港'], ['MO', '中国澳门'], ['TW', '中国台湾']],
  course_system: [['gaokao', '普通高考'], ['HKDSE', 'HKDSE（未适配）'], ['A_levels', 'A-levels（未适配）'], ['taiwan_exam', '台湾学测（未适配）']],
  applicant_category: [['cn_mainland', '大陆普通高考申请身份'], ['hmt_joint', '港澳台联招身份（未适配）'], ['other', '其他申请身份（未适配）']],
  exam_province: [['DEMO_PROVINCE', 'DEMO 合成生源省份'], ...[['Beijing','北京'],['Tianjin','天津'],['Hebei','河北'],['Shanxi','山西'],['InnerMongolia','内蒙古'],['Liaoning','辽宁'],['Jilin','吉林'],['Heilongjiang','黑龙江'],['Shanghai','上海'],['Jiangsu','江苏'],['Zhejiang','浙江'],['Anhui','安徽'],['Fujian','福建'],['Jiangxi','江西'],['Shandong','山东'],['Henan','河南'],['Hubei','湖北'],['Hunan','湖南'],['Guangdong','广东'],['Guangxi','广西'],['Hainan','海南'],['Chongqing','重庆'],['Sichuan','四川'],['Guizhou','贵州'],['Yunnan','云南'],['Tibet','西藏'],['Shaanxi','陕西'],['Gansu','甘肃'],['Qinghai','青海'],['Ningxia','宁夏'],['Xinjiang','新疆']] as [string,string][]],
  pathway: [['gaokao', '普通高考本科'], ['uk_undergraduate', '英国本科'], ['other', '其他路线（未适配）']],
}
const available = computed(() => allowedAssessments(props.draft).filter(key => !props.draft.grades[key]))
const retainedHidden = computed(() => assessmentKeys.filter(key => props.draft.grades[key] && !allowedAssessments(props.draft).includes(key)))
const inputValue = (event: Event) => (event.target as HTMLInputElement).value
function statusChanged(key: ScopeField) { if (props.draft.scopes[key].status !== 'known') props.draft.scopes[key].value = ''; emit('changed', ['course_system', 'pathway', 'applicant_category'].includes(key)) }
function scopeChanged(key: ScopeField) { emit('changed', ['course_system', 'pathway', 'applicant_category'].includes(key)) }
function add() { if (addKey.value) { emit('add', addKey.value); addKey.value = '' } }
function slotChanged(key: AssessmentKey, slot: typeof slots[number]) {
  const value = props.draft.grades[key]![slot]
  if (value.status !== 'provided') { value.value = ''; value.scale = ''; value.unit = '' }
  emit('changed')
}
</script>

<template>
  <form class="profile-form" @submit.prevent="emit('save')">
    <fieldset :disabled="busy">
      <legend>01 / 本科意向与独立范围</legend>
      <label>入学年（须明确填写）<input :value="draft.entryYear" data-testid="profile-entry-year" inputmode="numeric" autocomplete="off" @input="draft.entryYear = inputValue($event); emit('changed')"><small>英国暂定 2027 仅为目标提示；未输入时不会保存默认年份。</small></label>
      <div class="profile-scope-grid">
        <div v-for="field in scopeFields" :key="field.key" class="scope-field">
          <label>{{ field.label }}状态<select v-model="draft.scopes[field.key].status" :data-testid="`profile-${field.key}-status`" @change="statusChanged(field.key)"><option value="unknown">未知 / 未提供</option><option value="known">本人明确选择</option><option value="not_applicable">明确不适用</option></select></label>
          <label v-if="draft.scopes[field.key].status === 'known'">{{ field.label }}<select v-model="draft.scopes[field.key].value" :data-testid="`profile-${field.key}-value`" @change="scopeChanged(field.key)"><option value="">请选择，不自动推断</option><option v-for="[value, label] in choices[field.key].filter(([value]) => value !== 'DEMO_PROVINCE' || synthetic)" :key="value" :value="value">{{ label }}</option><option v-if="draft.scopes[field.key].value && !choices[field.key].some(([value]) => value === draft.scopes[field.key].value)" :value="draft.scopes[field.key].value">已保存代码：{{ draft.scopes[field.key].value }}</option></select></label>
          <details v-if="draft.scopes[field.key].status === 'known'" class="profile-advanced"><summary>其他已知范围 / 高级代码</summary><label>明确提供的范围代码<input v-model="draft.scopes[field.key].value" autocomplete="off" :data-testid="`profile-${field.key}-custom`" @input="scopeChanged(field.key)"></label></details>
          <small>{{ field.hint }} 省名选择仅记录意向，不代表招生规则或代码映射已完成。</small>
        </div>
      </div>
    </fieldset>
    <fieldset :disabled="busy">
      <legend>02 / 逐路线成绩</legend>
      <p class="profile-note">{{ asksGaokao(draft) ? '普通高考资料仍待规则适配；实得和预测独立，不产生资格结论。' : '未知或未适配课程 / 身份 / 路线：仅记录最少意向，不套用普通高考字段。' }}</p>
      <p v-if="asksLanguage(draft)" class="profile-note">英国本科语言询问是独立声明；语言成绩空缺不表示学校允许后补。</p>
      <p v-if="retainedHidden.length" class="profile-notice">原确认版包含当前分组未展示的声明，保持原值：{{ retainedHidden.map(key => assessmentLabels[key]).join('、') }}。本次不自动转换或删除；明确切换范围时才清理新草稿，旧版本保留。</p>
      <label v-if="asksGaokao(draft)">选科代码（逗号分隔，可空）<input v-model="draft.subjects" data-testid="profile-subjects" autocomplete="off" @input="emit('changed')"><small>如 physics,chemistry；未选择不自动填写。</small></label>
      <div v-if="available.length" class="profile-add"><label>添加本人声明的成绩<select v-model="addKey" data-testid="profile-grade-add-key"><option value="">请选择成绩项</option><option v-for="key in available" :key="key" :value="key">{{ assessmentLabels[key] }}</option></select></label><button type="button" data-testid="profile-grade-add" :disabled="!addKey" @click="add">添加成绩项</button></div>
      <section v-for="key in allowedAssessments(draft).filter(key => draft.grades[key])" :key="key" class="grade-card">
        <div class="grade-heading"><h4>{{ assessmentLabels[key] }}</h4><button type="button" :data-testid="`grade-${key}-remove`" @click="emit('remove', key)">移除本次声明</button></div>
        <div class="grade-slots">
          <div v-for="slot in slots" :key="slot">
            <h5>{{ slot === 'achieved' ? '实得成绩' : '预测成绩' }}</h5>
            <label>状态<select v-model="draft.grades[key]![slot].status" :data-testid="`grade-${key}-${slot}-status`" @change="slotChanged(key, slot)"><option value="missing">未提供</option><option value="provided">明确提供</option><option value="pending">待出成绩（不等于后补许可）</option><option value="not_applicable">不适用</option></select></label>
            <template v-if="draft.grades[key]![slot].status === 'provided'">
              <label>成绩<input :value="draft.grades[key]![slot].value" :data-testid="`grade-${key}-${slot}-value`" inputmode="decimal" autocomplete="off" @input="draft.grades[key]![slot].value = inputValue($event); emit('changed')"></label>
              <label>明确满分<input :value="draft.grades[key]![slot].scale" :data-testid="`grade-${key}-${slot}-scale`" inputmode="decimal" autocomplete="off" @input="draft.grades[key]![slot].scale = inputValue($event); emit('changed')"></label>
              <label>单位<select v-model="draft.grades[key]![slot].unit" :data-testid="`grade-${key}-${slot}-unit`" @change="emit('changed')"><option value="">须明确选择单位</option><option value="points">分值 points</option><option value="band">等级 band</option></select></label>
            </template>
          </div>
        </div>
        <small>没有默认满分；空白不变成 0。没有成绩时请选择“未提供”，待出成绩不会自动判为可后补。</small>
      </section>
    </fieldset>
    <fieldset :disabled="busy">
      <legend>03 / 可用时数与本人偏好</legend>
      <label>每周可安排时数（可空）<input :value="draft.weeklyHours" data-testid="profile-weekly-hours" inputmode="decimal" autocomplete="off" @input="draft.weeklyHours = inputValue($event); emit('changed')"><small>空白为未知；0 表示明确没有容量；上限 40 小时，不是学习效果承诺。</small></label>
      <label class="profile-choice"><input v-model="draft.preferencesEnabled" type="checkbox" data-testid="profile-preferences-enabled" @change="emit('changed')">明确记录本人偏好（可不提供）</label>
      <template v-if="draft.preferencesEnabled">
        <label>专业兴趣（每行一项）<textarea v-model="draft.preferredFields" data-testid="profile-preferred-fields" rows="3" @input="emit('changed')"></textarea><small>至多 10 项；兴趣不等于已达成资格。</small></label>
        <div class="profile-country"><label v-for="country in ['CN', 'GB'] as const" :key="country" class="profile-choice"><input v-model="draft.preferredCountries" type="checkbox" :value="country" :data-testid="`profile-preferred-${country}`" @change="emit('changed')">{{ country === 'CN' ? '中国' : '英国' }}</label></div>
        <label class="profile-choice"><input v-model="draft.budgetEnabled" type="checkbox" data-testid="profile-budget-enabled" @change="emit('changed')">本人明确提供预算</label>
        <div v-if="draft.budgetEnabled" class="profile-budget"><label>预算数额<input :value="draft.budgetAmount" data-testid="profile-budget-amount" inputmode="decimal" autocomplete="off" @input="draft.budgetAmount = inputValue($event); emit('changed')"></label><label>币种<select v-model="draft.budgetCurrency" data-testid="profile-budget-currency" @change="emit('changed')"><option value="">须明确选择</option><option value="CNY">人民币 CNY</option><option value="GBP">英镑 GBP</option></select></label></div>
      </template>
    </fieldset>
    <p v-if="validation" class="profile-validation" role="status">{{ validation }}</p>
    <label class="profile-choice profile-confirm"><input v-model="draft.confirmed" type="checkbox" data-testid="profile-confirmation" :disabled="busy">我已逐项核对以上完整草稿，明确确认本次保存为新的本人声明版本。不会自动确认资格、计划或申请。</label>
    <button type="submit" class="profile-primary" data-testid="profile-save" :disabled="!canSave || busy">{{ busy ? '保存结果尚未确认…' : '明确确认并保存新版本' }}</button>
  </form>
</template>

<style scoped>
.profile-form{margin-top:24px}.profile-form fieldset{border:0;border-top:1px solid #dee7d9;min-width:0;padding:22px 0;margin-top:12px}.profile-form legend{font-size:15px;font-weight:600;padding-right:12px}.profile-form label{display:flex;flex-direction:column;gap:8px;font-size:12px;color:#536e58;margin:13px 0;min-width:0}.profile-form input,.profile-form select,.profile-form textarea{width:100%;min-width:0;background:#fff;border:1px solid #c9d8c6;border-radius:6px;padding:10px;font-size:12px;color:#254f3c}.profile-form small,.profile-note{font-size:11px;line-height:1.9;color:#7a8b73;display:block}.profile-scope-grid,.grade-slots,.profile-budget{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.scope-field{background:#f7f9f4;padding:14px;border-radius:8px;min-width:0}.profile-advanced{font-size:10px;color:#778d71;margin:10px 0}.profile-advanced summary{cursor:pointer}.profile-add{display:flex;align-items:flex-end;gap:12px;margin-top:16px}.profile-add label{flex:1}.profile-add button{margin-bottom:13px}.profile-form button{background:#fff;border:1px solid #b9cebd;color:#426b4c;border-radius:7px;padding:11px 14px;font-size:11px}.grade-card{border:1px solid #dce6d7;border-radius:9px;padding:20px;margin-top:18px;min-width:0}.grade-heading{display:flex;justify-content:space-between;gap:15px;align-items:center}.grade-heading h4{font-size:14px}.grade-slots h5{font-size:12px;margin-top:20px}.profile-form .profile-choice{flex-direction:row;align-items:flex-start;gap:10px;line-height:1.9}.profile-choice input[type=checkbox]{width:16px;height:16px;min-height:16px;flex:0 0 16px;padding:0;margin-top:3px;accent-color:#266a54}.profile-country{display:flex;gap:24px}.profile-confirm{padding:15px;border:1px solid #d7e2cc;background:#f1f6ea;border-radius:8px}.profile-form .profile-primary{background:#1b6453;color:#fff;border-color:#1b6453}.profile-form button:disabled{background:#f0f3eb;color:#8e9d86;border-color:#dfe6d8}.profile-validation,.profile-notice{font-size:12px;line-height:1.9;color:#875f36;background:#fcf2e5;border:1px solid #e8d3b3;padding:12px 15px;border-radius:7px}.profile-form :is(input,button,select,textarea,summary):focus-visible{outline:3px solid #8cb6a4;outline-offset:3px}@media(max-width:650px){.profile-scope-grid,.grade-slots,.profile-budget{grid-template-columns:1fr;gap:12px}.profile-add{flex-direction:column;align-items:stretch;gap:0}.grade-card{padding:16px}.grade-heading{align-items:flex-start;flex-direction:column}.profile-form .profile-primary{width:100%}}
</style>
