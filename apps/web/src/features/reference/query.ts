import { onBeforeUnmount, ref, shallowRef } from 'vue'
import type { ReferenceData } from '../../../../../packages/contracts/reference'
import { fetchReference } from './client'
import type { ReferenceRequest } from './client'

export function useReferenceQuery() {
  const result = shallowRef<ReferenceData | null>(null), loading = ref(false), error = ref('')
  let generation = 0, controller: AbortController | undefined
  function clear() {
    generation += 1; controller?.abort(); controller = undefined
    result.value = null; error.value = ''; loading.value = false
  }
  async function run(request: ReferenceRequest) {
    clear()
    const current = generation, abort = new AbortController()
    controller = abort; loading.value = true
    const timeout = window.setTimeout(() => abort.abort(), 15000)
    try {
      const response = await fetchReference({ ...request, filters: { ...request.filters } }, abort.signal)
      if (current === generation && !abort.signal.aborted) result.value = response
    } catch {
      if (current === generation) error.value = '查询未完成。请检查本地参考服务与网络后重试；没有使用演示或其他年度资料。'
    } finally {
      window.clearTimeout(timeout)
      if (current === generation) { loading.value = false; controller = undefined }
    }
  }
  onBeforeUnmount(clear)
  return { result, loading, error, clear, run }
}
