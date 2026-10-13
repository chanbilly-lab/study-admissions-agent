<script setup lang="ts">
import { ref } from 'vue'
import StatisticsView from '../statistics/StatisticsView.vue'
import CurriculaView from '../curricula/CurriculaView.vue'
import OutcomesView from '../outcomes/OutcomesView.vue'
const section = ref<'statistics' | 'curricula' | 'outcomes'>('statistics')
</script>

<template>
  <main class="reference-shell">
    <header class="reference-hero">
      <div class="hero-copy">
        <p class="hero-label">升学咨询 · 资料工作台</p>
        <h1>全国参考资料</h1>
        <p class="hero-description">先选择年度与范围，再核对数值、原文和复核状态。缺失资料会明确说明。</p>
      </div>
      <ul class="reference-mode" aria-label="当前查询模式">
        <li>本地参考查询</li><li>模型关闭</li><li>由你明确查询</li>
      </ul>
    </header>
    <p class="notice warning scope-notice"><strong>参考资料与个人资格分开</strong><br />目标为各普通高考生源省份逐省适配；实际省份、年度、专业规则未覆盖时资格保持未知。历史分数不代表录取概率。</p>
    <nav class="reference-nav" aria-label="参考资料类别">
      <button type="button" :aria-pressed="section === 'statistics'" aria-controls="reference-content" @click="section = 'statistics'"><strong>历史统计</strong><span>分段线、控制线与录取观测</span></button>
      <button type="button" :aria-pressed="section === 'curricula'" aria-controls="reference-content" @click="section = 'curricula'"><strong>培养方案</strong><span>按入学届核对课程与版本</span></button>
      <button type="button" :aria-pressed="section === 'outcomes'" aria-controls="reference-content" @click="section = 'outcomes'"><strong>毕业结果</strong><span>核对实际人群与统计局限</span></button>
    </nav>
    <div id="reference-content">
      <StatisticsView v-if="section === 'statistics'" />
      <CurriculaView v-else-if="section === 'curricula'" />
      <OutcomesView v-else />
    </div>
    <footer class="reference-footer">来源、适用年度与缺口随查询结果展示；本入口不会确认画像、提交申请或生成录取概率。</footer>
  </main>
</template>

<style scoped>
.reference-shell{max-width:1140px;margin:auto;padding:40px 24px 28px}.reference-hero{display:flex;justify-content:space-between;align-items:center;gap:28px;margin-bottom:24px;padding:32px;border:1px solid var(--border);border-radius:var(--radius,14px);background:var(--paper);box-shadow:var(--shadow,0 8px 28px #173c3608)}.hero-label{font-size:12px;font-weight:650;letter-spacing:1px;color:var(--primary);margin-bottom:12px}.hero-copy h1{font-size:clamp(28px,4vw,38px);line-height:1.2;letter-spacing:-1px}.hero-description{max-width:560px;margin-top:14px;font-size:15px;color:var(--muted)}.reference-mode{display:flex;flex-direction:column;align-items:flex-end;gap:9px;list-style:none;margin:0;padding:0;flex-shrink:0}.reference-mode li{padding:7px 12px;border:1px solid var(--border);border-radius:999px;background:var(--surface,#f4f8f5);font-size:12px;color:var(--ink);white-space:nowrap}.scope-notice{margin-bottom:24px}.scope-notice strong{font-size:14px}.reference-nav{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:22px}.reference-nav button{min-height:82px;display:flex;flex-direction:column;align-items:flex-start;justify-content:center;gap:6px;padding:16px 20px;border:1px solid var(--border);border-radius:10px;background:var(--paper);color:var(--ink);text-align:left;transition:background .15s,border-color .15s}.reference-nav button strong{font-size:16px}.reference-nav button span{font-size:12px;color:var(--muted);line-height:1.6}.reference-nav button:hover{border-color:var(--primary)}.reference-nav button[aria-pressed=true]{background:var(--primary);border-color:var(--primary);color:#fff}.reference-nav button[aria-pressed=true] span{color:#e4f0e9}.reference-footer{font-size:12px;color:var(--muted);line-height:1.8;padding:0 4px}@media(max-width:700px){.reference-shell{padding:22px 14px}.reference-hero{padding:24px 20px;align-items:flex-start;flex-direction:column;gap:20px}.reference-mode{flex-direction:row;flex-wrap:wrap;align-items:flex-start;gap:7px}.reference-nav{gap:8px}.reference-nav button{padding:13px 10px;min-height:76px}.reference-nav button strong{font-size:14px}.reference-nav button span{font-size:11px}}@media(max-width:420px){.reference-nav{grid-template-columns:1fr}.reference-nav button{min-height:58px;flex-direction:row;justify-content:space-between;align-items:center;gap:12px;padding:12px 16px}.reference-nav button span{max-width:160px;text-align:right}}@media(prefers-reduced-motion:reduce){.reference-nav button{transition:none}}
</style>
