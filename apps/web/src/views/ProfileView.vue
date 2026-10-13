<script setup lang="ts">
import { onUnmounted, watch } from 'vue'
import type { SessionData } from '../features/auth/client'
import type { ProfileApi } from '../features/profiles/client'
import type { ProfileVersionData } from '../../../../packages/contracts/v2/profiles/generated'
import { useProfiles } from '../features/profiles/useProfiles'
import ProfileForm from '../features/profiles/ProfileForm.vue'
import ProfileVersionSummary from '../features/profiles/ProfileVersionSummary.vue'
const props = defineProps<{ actor: SessionData | null; coreAllowed: boolean; api?: ProfileApi }>()
const emit = defineEmits<{ sessionExpired: []; profileInvalidated: []; profileSelected: [version: ProfileVersionData | null] }>()
const profiles = useProfiles(props.api, () => emit('sessionExpired'), () => emit('profileInvalidated'))
const { state } = profiles
watch(() => [props.actor, props.coreAllowed] as const, ([actor, allowed]) => { void profiles.setAccess(actor, allowed) }, { immediate: true, flush: 'sync' })
watch(() => [state.current, state.editing, state.dirty, state.conflict, state.appendUnconfirmed, state.busy, state.status, props.actor, props.coreAllowed] as const,
  () => emit('profileSelected', props.actor && props.coreAllowed && state.status === 'ready' && !state.busy && !state.editing && !state.dirty && !state.conflict && !state.appendUnconfirmed ? state.current : null),
  { immediate: true, flush: 'sync' })
onUnmounted(profiles.dispose)
</script>
<template>
  <section class="profile-workspace" data-testid="profile-workspace" aria-labelledby="profile-workspace-title" :aria-busy="!!state.busy">
    <header class="profile-heading"><div><p class="profile-kicker">STUDENT DECLARATIONS</p><h2 id="profile-workspace-title">本人画像与确认版本</h2><p>课程、申请身份与考试省份分别声明；每次完整保存都需要本人明确确认。</p></div><button type="button" class="profile-secondary" data-testid="profile-context-refresh" :disabled="!actor || !coreAllowed || !!state.busy" @click="profiles.refresh">重新检查画像入口</button></header>
    <div class="profile-boundary"><strong>真实资料处理尚未开放</strong><p>本页面复用当前服务端画像权限，仅隔离合成验收可操作。没有姓名、证件、生日或附件；不会判断资格、录取概率或代提交申请。</p></div>
    <p v-if="state.context?.is_synthetic" class="profile-demo"><strong>DEMO · 合成画像验收</strong> · 使用合成学生声明，不能视为真实成绩核验或官方招生依据。</p>
    <p v-if="!actor" class="profile-status">尚未登录，不读取私人画像，也不显示学生输入。</p>
    <p v-else-if="!coreAllowed" class="profile-status">当前核心用途未获有效确认或正在变化，私人状态已清空。请先检查上方隐私设置。</p>
    <p v-else-if="state.status === 'loading'" class="profile-status" role="status">正在向服务端检查当前画像权限…</p>
    <p v-else-if="!state.context" class="profile-status">画像入口关闭、不可用或当前主体未获授权。不会使用 M0 画像作为回退。</p>
    <p v-if="state.message" data-testid="profile-message" class="profile-message" :class="{ error: state.error }" :role="state.error ? 'alert' : 'status'">{{ state.message }}</p>
    <template v-if="state.context">
      <div class="profile-actions"><button v-if="state.context.can_create" type="button" class="profile-primary" data-testid="profile-new" :disabled="!!state.busy" @click="profiles.newProfile">新建本人完整画像</button><button v-if="state.context.can_read" type="button" class="profile-secondary" data-testid="profile-list" :disabled="!!state.busy" @click="profiles.list()">读取本人画像列表</button></div>
      <p class="profile-status">服务端能力：首建 {{ state.context.can_create ? '可操作' : '关闭' }} / 读取 {{ state.context.can_read ? '可操作' : '关闭' }} / 追加 {{ state.context.can_append ? '可操作' : '关闭' }}；每次操作仍即时重验。</p>
      <div v-if="state.page" class="profile-list"><p v-if="!state.page.items.length">当前没有可读取的本人画像引用。旧用途失效的画像不会自动恢复。</p><button v-for="item in state.page.items" :key="item.profile_id" type="button" class="profile-list-item" :data-testid="`profile-load-${item.profile_id}`" :disabled="!!state.busy" @click="profiles.load(item.profile_id)"><span>{{ item.is_synthetic ? 'DEMO' : '本人声明' }} · 第 {{ item.version }} 版</span><small>{{ item.profile_id }}</small></button><button v-if="state.page.next_cursor" type="button" class="profile-secondary" data-testid="profile-next" :disabled="!!state.busy" @click="profiles.list(true)">读取下一页</button></div>
      <ProfileVersionSummary v-if="state.current" :version="state.current" />
      <div v-if="state.current" class="profile-actions"><button v-if="state.context.can_append && !state.editing" type="button" class="profile-primary" data-testid="profile-edit" :disabled="!!state.busy" @click="profiles.editCurrent">明确编辑此当前版本</button><button v-if="state.editing" type="button" class="profile-secondary" data-testid="profile-discard-draft" :disabled="!!state.busy" @click="profiles.discardDraft">放弃草稿，恢复已读版本</button></div>
      <div v-if="state.conflict || state.appendUnconfirmed" class="profile-conflict" data-testid="profile-conflict"><strong>{{ state.conflict ? '版本冲突，保存未确认' : '追加结果未确认' }}</strong><p>本人草稿保留，确认勾选已撤销。不会自动重试或覆盖当前版。请明确读取当前版，核对后再重新确认。</p><button v-if="state.current" type="button" data-testid="profile-reload-current" class="profile-secondary" :disabled="!!state.busy" @click="profiles.load(state.current.profile_id, true)">读取当前版并保留草稿待核对</button><button v-else type="button" class="profile-secondary" :disabled="!!state.busy" @click="profiles.refresh">重新检查入口与本人列表</button></div>
      <div v-if="state.current && state.context.can_read" class="profile-history"><label>明确读取历史版本 UUID<input v-model="state.historyVersionId" data-testid="profile-history-version-id" autocomplete="off" :disabled="!!state.busy" @input="state.history = null; state.draft.confirmed = false"></label><button type="button" class="profile-secondary" data-testid="profile-history-load" :disabled="!!state.busy || !state.historyVersionId" @click="profiles.history">只读历史版本</button></div>
      <ProfileVersionSummary v-if="state.history" :version="state.history" history />
      <template v-if="state.editing">
        <p class="profile-draft" data-testid="profile-draft-warning">{{ state.dirty ? '草稿已有变更，尚未确认。' : '当前编辑草稿尚未重新确认。' }} 旧确认版本保留；后续结果必须绑定新的确认版本。资格检查尚未开放。</p>
        <p v-if="state.routeCleared" class="profile-message">已按本次明确切换的课程、身份或路线清除不适用的草稿成绩与选科；旧确认版完整保留，不自动转换成绩。</p>
        <ProfileForm :draft="state.draft" :busy="!!state.busy" :can-save="profiles.canSave()" :validation="profiles.validationMessage()" :synthetic="state.context.is_synthetic" @changed="profiles.changed" @add="profiles.addGrade" @remove="profiles.removeGrade" @save="profiles.save" />
      </template>
    </template>
  </section>
</template>
<style scoped>
.profile-workspace{grid-column:1/-1;min-width:0;border:1px solid #dce6d7;background:#fff;border-radius:12px;padding:30px;color:#254538}.profile-heading{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:22px}.profile-kicker{font-size:10px;letter-spacing:2px;color:#819178;margin-bottom:8px}.profile-heading h2{font-size:24px}.profile-heading p:last-child{font-size:11px;color:#7a8974;margin-top:9px;line-height:1.9}.profile-boundary{background:#f1f4e7;border:1px solid #d8dfc7;border-radius:8px;padding:16px 18px}.profile-boundary strong{font-size:13px}.profile-boundary p{font-size:11px;color:#6f7f66;margin-top:6px;line-height:1.9}.profile-demo,.profile-status{font-size:11px;color:#75846a;line-height:1.9;margin:17px 0}.profile-demo{padding:13px 16px;background:#edf4e5;border:1px solid #d3dfc8;border-radius:7px}.profile-actions{display:flex;flex-wrap:wrap;gap:12px;margin:18px 0}.profile-secondary,.profile-primary,.profile-list-item{background:white;border:1px solid #b9cebd;color:#426b4c;border-radius:7px;padding:11px 14px;font-size:11px}.profile-primary{background:#1b6453;color:#fff;border-color:#1b6453}.profile-message,.profile-conflict{padding:14px 17px;border:1px solid #d4e1ce;background:#f6f9f0;border-radius:7px;font-size:12px;margin:20px 0;line-height:1.9;overflow-wrap:anywhere}.profile-message.error,.profile-conflict{background:#fcf2e5;border-color:#e8d3b3;color:#875f36}.profile-conflict button{margin-top:13px}.profile-draft{font-size:12px;line-height:1.9;border-left:2px solid #99b183;padding-left:13px;margin-top:25px;color:#61764f}.profile-list{display:grid;gap:12px;grid-template-columns:repeat(2,minmax(0,1fr));font-size:11px;line-height:1.9}.profile-list-item{text-align:left;min-width:0}.profile-list-item small{display:block;font-size:10px;margin-top:8px;overflow-wrap:anywhere}.profile-history{display:flex;align-items:flex-end;gap:12px;margin-top:23px}.profile-history label{display:flex;flex:1;flex-direction:column;gap:8px;font-size:11px;min-width:0}.profile-history input{width:100%;min-width:0;padding:11px;border:1px solid #c9d8c6;border-radius:6px;font-size:11px}.profile-workspace button:disabled{background:#f0f3eb;color:#8e9d86;border-color:#dfe6d8}.profile-workspace :is(input,button):focus-visible{outline:3px solid #8cb6a4;outline-offset:3px}@media(max-width:650px){.profile-workspace{padding:24px 17px}.profile-heading{flex-direction:column;align-items:flex-start}.profile-heading h2{font-size:22px}.profile-list{grid-template-columns:1fr}.profile-history{flex-direction:column;align-items:stretch}.profile-actions>*{flex:1}.profile-heading button{width:100%}}
</style>
