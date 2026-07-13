import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/research': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // 前缀匹配确保 /research/stream/* 等子路径也被代理
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
