import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, '') },
      '/public': { target: 'http://127.0.0.1:8002', changeOrigin: true, rewrite: (path) => path.replace(/^\/public/, '') },
      '/qa': { target: 'http://127.0.0.1:8003', changeOrigin: true, rewrite: (path) => path.replace(/^\/qa/, '') },
      '/reference': { target: 'http://127.0.0.1:8004', changeOrigin: true, rewrite: (path) => path.replace(/^\/reference/, '') },
    },
  },
  test: { environment: 'jsdom', clearMocks: true, restoreMocks: true, include: ['tests/**/*.test.ts'] },
})
