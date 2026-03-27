import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  root: '.',
  publicDir: '../public',
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api/news': {
        target: 'http://localhost:5002',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://localhost:5002',
        changeOrigin: true,
      },
      '/strategy': {
        target: 'http://localhost:5002',
        changeOrigin: true,
      },
      '/sectors': {
        target: 'http://localhost:5002',
        changeOrigin: true,
      },
      '/ticai': {
        target: 'http://localhost:5002',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: '../dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
      },
    },
  },
})
