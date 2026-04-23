import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { existsSync, readFileSync } from 'fs'
import chartingLibraryServe from './vite-plugins/chartingLibraryServe.js'

// 简单的中间件插件
function serveDistAssetsPlugin() {
  return {
    name: 'serve-dist-assets',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url.split('?')[0]
        if (url.startsWith('/assets/')) {
          const distAssetsDir = resolve(__dirname, '../dist/assets')
          const filename = url.replace('/assets/', '')
          const filePath = resolve(distAssetsDir, filename)
          if (existsSync(filePath)) {
            const content = readFileSync(filePath)
            const ext = filename.split('.').pop()
            const mimeTypes = {
              js: 'application/javascript',
              css: 'text/css',
              map: 'application/json'
            }
            res.setHeader('Content-Type', mimeTypes[ext] || 'application/octet-stream')
            res.end(content)
            return
          }
        }
        next()
      })
    }
  }
}

export default defineConfig({
  plugins: [vue(), chartingLibraryServe(), serveDistAssetsPlugin()],
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
      '/tv_udf': {
        target: 'http://localhost:5002',
        changeOrigin: true,
      },
      '^/s(?:/|$)': {
        target: 'http://localhost:5002',
        changeOrigin: true,
      },
      '/charting_library': {
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
