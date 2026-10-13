import { createApp } from 'vue'
import './styles.css'

const mode = import.meta.env.VITE_APP_MODE
if (mode === 'auth') {
  const { default: AuthView } = await import('./features/auth/AuthView.vue')
  createApp(AuthView).mount('#app')
} else if (mode === 'reference') {
  const { default: ReferenceView } = await import('./features/reference/ReferenceView.vue')
  createApp(ReferenceView).mount('#app')
} else if (mode === undefined || mode === '' || mode === 'demo') {
  const { default: App } = await import('./App.vue')
  createApp(App).mount('#app')
} else {
  throw new Error('VITE_APP_MODE 必须是 demo、auth 或 reference。')
}
