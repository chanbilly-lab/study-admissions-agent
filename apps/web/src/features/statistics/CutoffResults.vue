<script setup lang="ts">
import type { LocalCutoffData, LocalCutoffLineKind, LocalCutoffMissingReason } from '../../../../../packages/contracts/reference'

defineProps<{ data: LocalCutoffData }>()
const lineKinds: Record<LocalCutoffLineKind, string> = {
  segment_first: '普通类第一段线', segment_second: '普通类第二段线', special_category: '特殊类型招生控制线',
}
const reasons: Record<LocalCutoffMissingReason, string> = {
  not_collected: '本地尚未采集此省份或年度，未使用其他年度或演示资料补充。这不代表官方未公布。',
  not_applicable: '所选港澳台路径不适用普通高考省线，需按独立招生体系查询。',
  scope_not_supported: '当前未接入所选科类、批次或轮次；本批仅浙江2026普通类三条省线。',
  withdrawn: '此批资料已从本地查询撤回，不再显示数值和旧证据。',
  review_pending: '此批资料尚未完成本地人工复核，暂不展示候选数值。',
}
</script>

<template>
  <div class="cutoff-result" data-testid="cutoff-results">
    <template v-if="data.reference_available && data.source && data.batch">
      <div class="cutoff-summary"><strong>2026年浙江普通类省级分数线</strong><span>真实官方来源 · 本地人工复核</span><p>仅本批三条省级线；不是全省各类别完整资料，也不是高校录取线或个性化资格结论。</p></div>
      <ul class="cutoff-cards" aria-label="本批省级分数线">
        <li v-for="item in data.items" :key="item.record_key" :data-line-kind="item.line_kind">
          <article :aria-labelledby="'cutoff-' + item.record_key">
            <p class="cutoff-scope">{{ item.exam_year }} · 浙江 · {{ item.subject_category }}</p>
            <h4 :id="'cutoff-' + item.record_key">{{ item.original_label }}</h4>
            <p class="cutoff-value">{{ item.value }}<span>分</span></p>
            <dl class="line-definition"><div><dt>线种</dt><dd>{{ lineKinds[item.line_kind] }}</dd></div><div><dt>适用说明</dt><dd>{{ item.line_kind === 'special_category' ? '特殊用途控制线，不能代替普通类分段线' : '普通类分段线，不能改称本科控制线' }}</dd></div></dl>
            <details class="record-evidence"><summary>查看此条原文与定位</summary><blockquote>{{ item.excerpt }}</blockquote><p>{{ item.locator }}</p></details>
          </article>
        </li>
      </ul>
      <div class="definition-gap" data-testid="cutoff-missing-definitions"><strong>关键口径仍有缺项</strong><p>满分：未知；加分定义：未知。所选来源未明确这两项，未推定满分或加分口径。</p><p>以上是非合成参考资料。没有进行录取概率、排名、学校要求或资格判断。</p></div>
      <section class="source-detail" aria-label="本批来源与本地复核">
        <div class="source-heading"><div><p class="source-label">核对依据</p><h3>来源与本地复核</h3></div><span class="source-badge">官方站点已核对</span></div>
        <a class="official-source" :href="data.source.url" target="_blank" rel="noopener noreferrer">{{ data.source.title }}<span>打开官方原文 · 新窗口</span></a>
        <dl class="source-facts">
          <div><dt>发布主体</dt><dd>{{ data.source.publisher }}</dd></div>
          <div><dt>官方公布原标签</dt><dd>{{ data.source.published_label }}<small>原文时区未明确，未转换为UTC或补齐截止时间。</small></dd></div>
          <div><dt>原文取得时间</dt><dd><time :datetime="data.source.retrieved_at">{{ data.source.retrieved_at }}</time><small>UTC；不是官方公布时间。</small></dd></div>
          <div><dt>本地人工复核</dt><dd>已完成本批本地查询复核<br /><time :datetime="data.batch.approved_at">{{ data.batch.approved_at }}</time><small>仅供本批本地查询；不表示正式公众发布。</small></dd></div>
          <div><dt>对外再分发许可</dt><dd>未知。未开放公众服务或全文再分发。</dd></div>
          <div><dt>覆盖分母与覆盖率</dt><dd>未知；不计算完整率，也不显示为0%。</dd></div>
        </dl>
        <details class="technical-evidence"><summary>查看原文字节、SHA256与复核记录</summary><dl>
          <div><dt>原文大小</dt><dd>{{ data.source.body_bytes }} 字节</dd></div>
          <div><dt>原文SHA256</dt><dd><code>{{ data.source.original_sha256 }}</code><small>对应取得的原HTML字节，不是模型生成或摘录摘要。</small></dd></div>
          <div><dt>复核状态与标识</dt><dd>{{ data.batch.state }}<br />{{ data.batch.review_ref }}</dd></div>
          <div><dt>批次标识</dt><dd>{{ data.batch.batch_id }}</dd></div>
          <div><dt>清单SHA256</dt><dd><code>{{ data.batch.manifest_sha256 }}</code></dd></div>
        </dl></details>
      </section>
    </template>
    <div v-else class="empty-state" data-testid="cutoff-missing">
      <strong v-if="data.missing_reason">{{ reasons[data.missing_reason] }}</strong>
      <p>当前范围没有可显示的本地复核记录。来源、批次与数值保持空值，不回填DEMO、其他省份或其他年度。</p>
      <p>覆盖分母未知，不计算覆盖率。没有生成个人资格或录取概率。</p>
    </div>
  </div>
</template>

<style scoped>
.cutoff-summary{display:flex;flex-wrap:wrap;align-items:center;gap:10px 16px;margin-bottom:20px}.cutoff-summary>strong{font-size:16px;color:var(--ink)}.cutoff-summary>span{font-size:12px;color:var(--primary)}.cutoff-summary>p{width:100%;font-size:14px;color:var(--muted)}.cutoff-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;list-style:none;padding:0;margin:0 0 20px}.cutoff-cards li{min-width:0}.cutoff-cards article{padding:22px 20px;height:100%;border:1px solid var(--border);border-radius:12px;background:var(--paper)}.cutoff-scope{font-size:12px;color:var(--muted);margin-bottom:10px}.cutoff-cards h4{font-size:17px;font-weight:650;color:var(--ink);line-height:1.5;margin:0}.cutoff-value{display:flex;align-items:baseline;gap:8px;margin:18px 0;color:var(--primary);font-size:42px;font-weight:650;line-height:1.1;font-variant-numeric:tabular-nums}.cutoff-value>span{font-size:14px;font-weight:400;color:var(--muted)}.line-definition{display:grid;gap:12px;margin:0}.line-definition>div{display:grid;gap:4px}dt{font-size:12px;font-weight:600;color:var(--muted)}dd{font-size:14px;margin:0;overflow-wrap:anywhere;line-height:1.8}.record-evidence{border-top:1px solid var(--border);margin-top:18px;padding-top:14px}.record-evidence summary,.technical-evidence summary{min-height:44px;cursor:pointer;font-size:13px;font-weight:600;line-height:1.8;color:var(--primary)}blockquote{margin:12px 0 8px;padding:12px;border-radius:6px;background:var(--surface,#f4f8f5);font-size:13px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8}.record-evidence>p{font-size:12px;color:var(--muted);overflow-wrap:anywhere;line-height:1.8}.definition-gap{padding:17px 20px;margin-bottom:24px;border:1px solid #e0d9bd;border-radius:10px;background:#faf7ee;color:#675828}.definition-gap strong{font-size:14px}.definition-gap p{font-size:13px;margin-top:6px}.source-detail{padding:24px;border:1px solid var(--border);border-radius:12px;background:var(--surface,#f4f8f5)}.source-heading{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-bottom:18px}.source-label{font-size:12px;font-weight:600;color:var(--primary);margin-bottom:6px}.source-badge{border:1px solid var(--border);border-radius:999px;background:var(--paper);padding:7px 10px;font-size:12px;white-space:nowrap;color:var(--ink)}.official-source{display:block;font-size:15px;font-weight:600;color:var(--primary);text-decoration:underline;text-underline-offset:4px;overflow-wrap:anywhere;line-height:1.8}.official-source>span{display:block;font-size:12px;font-weight:400;margin-top:5px;color:var(--muted)}.source-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px 26px;margin:22px 0 0}.source-facts>div{min-width:0;display:grid;gap:6px;align-content:start}small{display:block;margin-top:6px;font-size:12px;font-weight:400;color:var(--muted);line-height:1.8}.technical-evidence{margin-top:22px;border-top:1px solid var(--border);padding-top:16px}.technical-evidence dl{display:grid;gap:16px;margin:16px 0 0}.technical-evidence dl>div{display:grid;grid-template-columns:150px minmax(0,1fr);gap:12px}code{font-size:12px;overflow-wrap:anywhere}.empty-state{text-align:left}.empty-state>strong{font-size:15px;color:var(--ink)}.empty-state p{margin-top:10px}@media(max-width:900px){.cutoff-cards{grid-template-columns:1fr}.cutoff-cards article{padding:20px}.cutoff-value{font-size:38px;margin:14px 0}.line-definition{grid-template-columns:minmax(130px,1fr) minmax(0,2fr);gap:16px}}@media(max-width:620px){.source-detail{padding:20px 16px}.source-heading{align-items:flex-start;flex-direction:column;gap:12px}.source-facts{grid-template-columns:1fr}.technical-evidence dl>div{grid-template-columns:1fr;gap:5px}.line-definition{grid-template-columns:1fr;gap:12px}.cutoff-summary{align-items:flex-start;flex-direction:column;gap:8px}.definition-gap{padding:16px}}
</style>
