<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'
import type { SessionData } from '../../auth/client'
import type { ProfileVersionData } from '../../profiles/client'
import type { NotificationApi, NotificationData } from './client'
import { useNotifications } from './useNotifications'

const props = defineProps<{ actor: SessionData | null; coreAllowed: boolean; profile: ProfileVersionData | null; profileEpoch: number; api?: NotificationApi }>()
const emit = defineEmits<{ privateInvalidated: []; sessionExpired: [] }>()
const workspace = useNotifications({ api: props.api }, () => emit('privateInvalidated'), () => emit('sessionExpired'))
const { state } = workspace
watch(() => [props.actor, props.coreAllowed, props.profileEpoch] as const, ([actor, core, epoch]) => workspace.setAccess(actor, core, epoch), { immediate: true, flush: 'sync' })
watch(() => [props.profile, props.actor, props.coreAllowed, props.profileEpoch] as const, ([profile]) => { void workspace.setProfile(profile) }, { immediate: true, flush: 'sync' })
onMounted(() => { if (props.actor && props.coreAllowed) void workspace.refreshContext() })
onUnmounted(workspace.dispose)
const messages: Record<NotificationData['reason'], string> = {
  MEMBER_ADDED: '原目标的发布资料新增了字段，请重新核验适用要求。',
  MEMBER_REMOVED: '原目标的发布资料移除了字段，请重新核验原依据。',
  BUSINESS_CHANGED: '原目标的要求或业务内容已有变化，请重新核验。',
  RELEASE_WINDOW_CHANGED: '原发布的适用区间已有变化，请重新核验。',
  RULESET_CHANGED: '原目标的规则版本已有变化，请重新核验。',
  RELEASE_WITHDRAWN: '原发布已撤回，请重新核验当前依据。',
  REFERENCE_REPLACED: '版本引用已有变化，本条未标记业务变化；旧引用不会自动恢复为当前依据。',
}
const checked = (event: Event) => (event.target as HTMLInputElement).checked
</script>

<template>
  <section class="notifications-panel" data-testid="notifications-workspace" aria-labelledby="notifications-title" :aria-busy="state.busy">
    <header><div><p class="kicker">IN APP · REVIEW · PREFERENCE</p><h3 id="notifications-title">原依据变化后，留下一条待核对提示。</h3><p>仅站内显示，不发送邮件、短信或系统推送。提醒不会代替资格检查或本人计划确认。</p></div><span class="tag">站内提醒</span></header>
    <p class="boundary">真实资料处理尚未开放。变更提醒不表示符合资格或被录取，也不会修改已确认计划或完成记录。</p>
    <p v-if="!actor || !coreAllowed" class="message">当前会话和核心用途有效后才能读取本人提醒；准入变化时内容即时清空。</p>
    <template v-else>
      <button type="button" class="secondary" data-testid="notifications-context-refresh" :disabled="state.busy" @click="workspace.refreshContext()">重新检查提醒入口</button>
      <p v-if="state.context?.is_synthetic" class="demo">DEMO · 合成站内提醒验收，不是真实招生通知。</p>
      <p v-if="state.message" class="message" data-testid="notifications-message" :class="{ error: state.error !== null }" :role="state.error === null ? 'status' : 'alert'">{{ state.message }}</p>
      <div v-if="state.conflict" class="conflict" data-testid="notifications-conflict"><strong>操作未确认，请明确重读。</strong><p>不会自动重复保存或把提醒标为已读。读取最新偏好或提醒后，重新核对服务端状态。</p></div>
      <template v-if="state.context">
        <section class="preferences">
          <div class="section-heading"><h4>本人站内提醒偏好</h4><button type="button" class="secondary" data-testid="notifications-preferences-read" :disabled="!workspace.canRead()" @click="workspace.readPreferences()">明确读取偏好</button></div>
          <p class="note">偏好默认为关闭。开启仅对本次登录与所选画像生效；重新登录或修改画像后须重新确认。关闭无需选择画像，仍须当前核心用途有效。</p>
          <div v-if="state.preferences" data-testid="notifications-preferences">
            <p>服务端版本 {{ state.preferences.version }} · {{ state.preferences.enabled ? '已开启站内提醒' : '已关闭站内提醒' }}</p>
            <dl v-if="state.preferences.enabled"><div><dt>绑定画像根</dt><dd>{{ state.preferences.profile_id }}</dd></div><div><dt>绑定确认版</dt><dd>{{ state.preferences.profile_version_id }}</dd></div></dl>
            <p v-if="state.profile" class="note" data-testid="notifications-selected-profile">本次明确选择：画像第 {{ state.profile.version }} 版 · {{ state.profile.version_id }}</p>
            <p v-else class="note">尚未明确选择当前确认画像，不能开启；可按服务端能力明确关闭。</p>
            <label class="check"><input type="checkbox" data-testid="notifications-enabled" :checked="state.enabled" :disabled="state.busy || state.conflict || !state.context.can_manage_preferences" @change="workspace.setEnabled(checked($event))"><span>接收此本人确认画像的站内发布变更提醒</span></label>
            <label class="check"><input type="checkbox" data-testid="notifications-preference-confirm" :checked="state.confirmed" :disabled="!workspace.canSave()" @change="workspace.setConfirmed(checked($event))"><span>我明确确认这次偏好选择。开启会绑定本次选择的当前确认画像，不开启外部消息渠道。</span></label>
            <button type="button" class="primary" data-testid="notifications-preferences-save" :disabled="!workspace.canSave() || !state.confirmed" @click="workspace.savePreferences()">明确保存偏好</button>
          </div>
        </section>
        <section class="inbox">
          <div class="section-heading"><h4>本人可读提醒</h4><button type="button" class="secondary" data-testid="notifications-read" :disabled="!workspace.canRead()" @click="workspace.readNotifications()">明确读取提醒</button></div>
          <p class="note">不依赖旧计划的当前来源读取；原用途、画像和私有期限仍由服务端核验。不自动重放评估或打开历史。</p>
          <div v-if="state.page" data-testid="notifications-page">
            <p class="note">本页 {{ state.page.items.length }} 条，不代表完整资料覆盖。</p>
            <p v-if="!state.page.items.length">本页没有可读站内提醒。</p>
            <article v-for="item in state.page.items" :key="item.id" class="notification" :class="{ review: item.needs_review }" :data-testid="`notification-${item.id}`">
              <div class="section-heading"><h5>{{ item.needs_review ? '原依据待复核' : '版本引用变化' }}</h5><span>{{ item.read_at ? '已读' : '未读' }}</span></div>
              <p>{{ messages[item.reason] }}</p>
              <p>入学年 {{ item.entry_year }} · 项目版本 {{ item.offering_version }}；此提醒没有资格或录取结论。</p>
              <details><summary>核对原版本引用（只读）</summary><dl><div><dt>提醒</dt><dd>{{ item.id }}</dd></div><div><dt>项目</dt><dd>{{ item.offering_id }}</dd></div><div><dt>原本人评估</dt><dd>{{ item.assessment_id }}</dd></div><div><dt>原画像确认版</dt><dd>{{ item.profile_version_id }}</dd></div><div><dt>原发布</dt><dd>{{ item.before_release_id ?? '无原发布引用' }}</dd></div><div><dt>后续发布</dt><dd>{{ item.after_release_id ?? '无后续发布引用' }}</dd></div><div><dt>事件</dt><dd>{{ item.event_id }}</dd></div><div><dt>生成 / 到期</dt><dd>{{ item.created_at }} / {{ item.expires_at }}</dd></div></dl></details>
              <p v-if="item.read_at" class="note" :data-testid="`notification-read-at-${item.id}`">服务端已读时间 {{ item.read_at }} · 读取版本 {{ item.version }}</p>
              <button v-else type="button" class="secondary" :data-testid="`notification-mark-read-${item.id}`" :disabled="!workspace.canMarkRead(item.id)" @click="workspace.markRead(item.id)">明确标记已读</button>
            </article>
            <button v-if="state.page.next_cursor" type="button" class="secondary" data-testid="notifications-next" :disabled="!workspace.canRead()" @click="workspace.nextPage()">明确读取下一页</button>
          </div>
        </section>
      </template>
    </template>
  </section>
</template>

<style scoped>
.notifications-panel{min-width:0;margin-top:22px;padding:24px;background:#fafbf7;border:1px solid #dce5d3;border-radius:9px;color:#294c3b}header{display:flex;justify-content:space-between;gap:16px}.kicker{font-size:10px;letter-spacing:1.4px;color:#849578}h3{font-size:21px;line-height:1.6;margin:0}h4{font-size:14px;margin:0}h5{font-size:13px;margin:0}p{font-size:11px;line-height:1.9;overflow-wrap:anywhere}.tag{border:1px solid #d6e1c8;border-radius:20px;padding:8px 12px;font-size:10px;white-space:nowrap;align-self:start}.boundary,.message,.demo,.conflict{margin:18px 0;padding:14px 16px;border-radius:7px;background:#f2f6e9;border:1px solid #dce5cf}.demo{color:#8a7245;background:#faf3e5}.error,.conflict{color:#8b653c;background:#fcf1e6;border-color:#ead7bd}.preferences,.inbox{border-top:1px solid #dde6d3;padding-top:20px;margin-top:24px}.section-heading{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:14px}.section-heading>span{font-size:10px;white-space:nowrap}.note{color:#7e8f70}.primary,.secondary{border:1px solid #baccb5;border-radius:6px;padding:10px 15px;font-size:11px;line-height:1.8;background:white;color:#426c47}.primary{background:#1b6453;color:white;border-color:#1b6453}button:disabled{background:#eef2e7;color:#909d82;border-color:#dde5d3}.check{display:flex;gap:10px;align-items:start;font-size:11px;line-height:1.9;margin:18px 0}.check input{width:17px;height:17px;flex:0 0 17px;margin:3px 0 0}.check span{min-width:0;overflow-wrap:anywhere}.notification{min-width:0;background:white;border:1px solid #dce5cf;border-radius:8px;margin:16px 0;padding:17px}.notification.review{border-color:#e6d7be}details{font-size:11px;border-top:1px solid #e1e8d8;margin:14px 0;padding-top:12px}summary{cursor:pointer;font-weight:600;line-height:1.9}dl>div{margin:10px 0}dt{font-size:10px;color:#859475}dd{font-size:10px;line-height:1.9;margin:4px 0 0;overflow-wrap:anywhere}.notifications-panel :focus-visible{outline:3px solid #8cb6a4;outline-offset:3px}@media(max-width:650px){.notifications-panel{padding:20px 13px}header,.section-heading{flex-wrap:wrap}.notification{padding:14px 12px}h3{font-size:19px}}
</style>
