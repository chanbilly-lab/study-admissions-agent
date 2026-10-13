<script setup lang="ts">
import { ref } from 'vue'
import type { SessionData } from '../features/auth/client'
import PrivacyPanel from '../features/privacy/PrivacyPanel.vue'
import type { PrivacyApi } from '../features/privacy/client'
import SharingPanel from '../features/sharing/SharingPanel.vue'
import type { SharingApi } from '../features/sharing/client'
import RightsPanel from '../features/privacy/rights/RightsPanel.vue'
import type { RightsApi } from '../features/privacy/rights/client'
defineProps<{actor:SessionData|null;privacyApi?:PrivacyApi;sharingApi?:SharingApi;rightsApi?:RightsApi}>()
const emit=defineEmits<{sessionExpired:[];admissionChanged:[allowed:boolean]}>()
const expanded=ref(false), epoch=ref(0), sharingEpoch=ref(0)
function admissionChanged(allowed:boolean){emit('admissionChanged',allowed);sharingEpoch.value++}
function stopped(){admissionChanged(false);epoch.value++}
</script>
<template><div class="settings-view">
  <PrivacyPanel :key="`privacy-${epoch}`" :actor="actor" :api="privacyApi" @session-expired="emit('sessionExpired')" @admission-changed="admissionChanged" />
  <section><h2>资料权利与保留说明</h2><p>导出和删除需要本人明确请求。已受理、失败与在线完成分别显示。</p><button type="button" data-testid="rights-toggle" :aria-expanded="expanded" aria-controls="rights-workspace" @click="expanded=!expanded">{{expanded?'收起本人权利入口':'展开本人权利入口'}}</button></section>
  <RightsPanel v-if="expanded" id="rights-workspace" :actor="actor" :api="rightsApi" @session-expired="emit('sessionExpired')" @processing-stopped="stopped" />
  <SharingPanel :key="`sharing-${sharingEpoch}`" :actor="actor" :api="sharingApi" @session-expired="emit('sessionExpired')" />
</div></template>
<style scoped>.settings-view{display:grid;gap:24px;min-width:0}.settings-view>section{padding:24px;background:#f8faf5;border:1px solid #d9e4d3;border-radius:10px}.settings-view>section h2{font-size:23px}.settings-view>section p{font-size:12px;line-height:1.9;margin:14px 0}.settings-view>section button{padding:12px 16px;background:white;border:1px solid #bdcebe;border-radius:7px;color:#315f48}.settings-view button:focus-visible{outline:3px solid #93bba0;outline-offset:3px}</style>
