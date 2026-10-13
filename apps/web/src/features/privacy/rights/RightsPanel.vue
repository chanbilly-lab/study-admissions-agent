<script setup lang="ts">
import { onUnmounted, watch } from 'vue'
import type { SessionData } from '../../auth/client'
import { useRights } from './useRights'
import type { RightsApi, RightsRequestData } from './client'
const props=defineProps<{actor:SessionData|null;api?:RightsApi}>()
const emit=defineEmits<{sessionExpired:[];processingStopped:[]}>()
const rights=useRights(props.api,()=>emit('sessionExpired'),()=>emit('processingStopped'))
const {state}=rights
const initialApi=props.api
function closeDrift(){rights.dispose();state.message='权利服务配置已变化，请收起并重新展开。'}
watch(()=>props.api,api=>{if(api!==initialApi)closeDrift()},{flush:'sync'})
watch(()=>props.actor,actor=>{if(props.api!==initialApi)closeDrift();else void rights.setActor(actor)},{immediate:true,deep:true,flush:'sync'})
onUnmounted(rights.dispose)
const label=(row:RightsRequestData)=>({queued:'已受理，等待处理',running:'正在处理',failed:'处理失败',cancelled:'处理已取消',completed:row.kind==='deletion'?'在线清理已完成':'导出已准备'}[row.status])
const reason=(value:string)=>({OK:'无处理错误',RETRYABLE_FAILURE:'处理遇到故障，等待有界重试',ATTEMPTS_EXHAUSTED:'重试上限已到，需要维护人员处理',EXPORT_LIMIT:'导出超过限额，未截断资料',AUTHORITY_REVOKED:'交付权限已失效',EXPIRED:'记录或工件已到期',LEASE_LOST:'作业执行权已变化',LEDGER_UNAVAILABLE:'最新恢复证明不可用',OWNER_DELETED:'删除已受理',RIGHTS_DISABLED:'功能未开放'} as Record<string,string>)[value] ?? '请重新读取状态'
function download() {
  const value=state.artifact
  if(!value||state.action||Date.parse(value.expires_at)<=Date.now()||!props.actor||Date.parse(props.actor.expires_at)<=Date.now())return
  const url=URL.createObjectURL(new Blob([value.content_json],{type:'application/json;charset=utf-8'}))
  const link=document.createElement('a');link.href=url;link.download=`my-data-${value.request_id}.json`
  try{link.click()}finally{URL.revokeObjectURL(url);state.artifact=null}
}
</script>
<template>
  <section aria-labelledby="rights-title" class="rights-panel" :aria-busy="!!state.action">
    <h2 id="rights-title">本人资料导出与删除</h2>
    <p>真实资料处理尚未开放。核心咨询用途撤回后，有效本人仍可请求查阅与删除；监护关系或管理员角色不授予他人权利。</p>
    <p v-if="actor?.is_synthetic" data-testid="rights-demo">DEMO · 合成身份与资料权利验收</p>
    <p v-if="state.message" role="status" data-testid="rights-message">{{state.message}}</p>
    <p v-if="!state.context" role="status">{{state.action?'正在读取本人权利状态…':'无法确认权利服务状态，请重新读取。'}}</p>
    <p v-else-if="!state.context.enabled" data-testid="rights-disabled">资料权利功能未开放，不收集资料或提交请求。</p>
    <p v-else-if="!actor">请登录后办理本人权利。</p>
    <p v-if="state.context?.deletion_accepted" data-testid="rights-accepted">删除已受理，相应用途与新采集关闭；已受理不表示全部资料已删除。退出页面不会取消后台清理。</p>
    <template v-if="actor && state.context?.enabled && !state.context.deletion_accepted">
      <label><input v-model="state.exportConfirmed" type="checkbox" data-testid="export-confirm">我明确请求导出本人已有资料，不请求其他用户资料。</label>
      <button type="button" data-testid="export-create" :disabled="!rights.canCreate('export')" @click="rights.create('export')">提交本人导出请求</button>
      <label><input v-model="state.deletionConfirmed" type="checkbox" data-testid="deletion-confirm">我明确请求删除本人私有资料，理解受理后关闭相应用途及清理范围。</label>
      <button type="button" data-testid="deletion-create" :disabled="!rights.canCreate('deletion')" @click="rights.create('deletion')">提交本人删除请求</button>
    </template>
    <article v-for="row in [state.export,state.deletion].filter(Boolean) as RightsRequestData[]" :key="row.request_id" :data-testid="`${row.kind}-status`">
      <h3>{{row.kind==='deletion'?'本人删除':'本人导出'}}：{{label(row)}}</h3>
      <dl><dt>受理标识</dt><dd>{{row.request_id}}</dd><dt>受理时间（UTC）</dt><dd>{{row.accepted_at}}</dd><template v-if="row.online_cleanup_due_at"><dt>在线清理期限（UTC）</dt><dd>{{row.online_cleanup_due_at}}</dd></template><dt>处理结果</dt><dd>{{reason(row.reason)}} · {{row.attempts}} 次尝试</dd><dt>最小责任记录上限（UTC）</dt><dd>{{row.retained_responsibility_until}}</dd></dl>
      <p v-if="row.kind==='deletion'">{{row.online_cleanup_complete?'本次服务器记录的在线范围已清理；最小责任记录和未到期备份仍按上限保留。':'在线清理未完成，请读取状态；受理或失败不代表全部删除。'}}</p>
      <button type="button" :data-testid="`${row.kind}-refresh`" :disabled="!!state.action" @click="rights.track(row.kind,row.request_id)">读取此请求状态</button>
      <button v-if="row.kind==='export' && row.status==='completed'" type="button" data-testid="export-content" :disabled="!!state.action" @click="rights.content">核验当前导出文件</button>
    </article>
    <template v-if="state.artifact"><p data-testid="export-ready">本人 JSON · {{state.artifact.size_bytes}} 字节 · {{state.artifact.sha256}} · 到期 {{state.artifact.expires_at}} UTC</p><button type="button" data-testid="export-download" :disabled="!!state.action" @click="download">下载本人 JSON 文件</button></template>
    <form v-if="actor" @submit.prevent="rights.track()"><h3>追踪已有本人请求</h3><label>请求类型<select v-model="state.lookupKind" data-testid="rights-kind"><option value="deletion">删除</option><option value="export">导出</option></select></label><label>受理标识<input v-model="state.lookupId" data-testid="rights-id" autocomplete="off" spellcheck="false"></label><button type="submit" data-testid="rights-track" :disabled="!!state.action">读取本人记录</button></form>
    <button type="button" data-testid="rights-refresh" :disabled="!!state.action" @click="rights.refresh">重新检查权利服务</button>
    <p>产品上限：在线清理 30 天；最小责任记录最长 24 个月；备份最长 35 天。不是法定期限，也不表示所有副本已消失。导出最大 10 MiB，超过会明确失败。页面不保存资料或自动轮询；刷新后可凭受理标识重新读取。</p>
  </section>
</template>
<style scoped>
.rights-panel{padding:24px;border:1px solid #dfe7dd;border-radius:12px;background:white;color:#193e35}.rights-panel h2{font-size:23px}.rights-panel p,.rights-panel dl{font-size:12px;line-height:1.9;margin:16px 0}.rights-panel label{display:flex;align-items:center;gap:12px;font-size:12px;margin:18px 0}.rights-panel input[type=checkbox]{width:18px;height:18px;accent-color:#315f48}.rights-panel button,.rights-panel select,.rights-panel input:not([type=checkbox]){padding:10px 14px;border:1px solid #afc1a7;border-radius:6px;background:#fff;color:#315f48;font-size:12px;max-width:100%}.rights-panel article,.rights-panel form{border-top:1px solid #dfe7dd;padding-top:18px;margin-top:20px}.rights-panel dd{margin:0 0 12px;overflow-wrap:anywhere}.rights-panel button{margin:5px 10px 5px 0}.rights-panel button:disabled{opacity:.45}.rights-panel :focus-visible{outline:3px solid #93bba0;outline-offset:3px}
</style>
