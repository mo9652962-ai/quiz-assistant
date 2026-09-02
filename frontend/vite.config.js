import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => ({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: 15173,
    proxy: {
      '/api': {
        target: mode === 'test'
          ? (process.env.VITE_API_TARGET || 'http://127.0.0.1:28765')
          : (process.env.VITE_API_TARGET || 'http://127.0.0.1:8765'),
        changeOrigin: false,
      },
    },
  },
  build: {
    sourcemap: true,
  },
}))
