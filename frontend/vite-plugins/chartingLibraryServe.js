import { readFileSync, existsSync, statSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const CL_ROOT = resolve(__dirname, '..', '..', 'charting_library')

const MIME = {
  html: 'text/html; charset=utf-8',
  js: 'application/javascript; charset=utf-8',
  mjs: 'application/javascript; charset=utf-8',
  css: 'text/css; charset=utf-8',
  json: 'application/json; charset=utf-8',
  map: 'application/json; charset=utf-8',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
  svg: 'image/svg+xml',
  woff: 'font/woff',
  woff2: 'font/woff2',
  ttf: 'font/ttf',
  cur: 'image/x-icon',
  wasm: 'application/wasm',
}

function middleware(req, res, next) {
  const raw = req.url?.split('?')[0] || ''
  if (!raw.startsWith('/charting_library')) return next()

  // 文件有两种布局：
  // 1. 直接在 CL_ROOT 下的：mobile_white.html, datafeeds/, bundles/
  // 2. TradingView 主库在 CL_ROOT/charting_library/ 子目录下
  //    当 TV 请求 charting_library.standalone.js（来自 library_path=""）
  //    实际路径是 CL_ROOT/charting_library/charting_library.standalone.js
  const rel = raw.replace(/^\/charting_library\/?/, '') || 'mobile_white.html'
  if (rel.includes('..')) return next()

  // 先尝试直接路径（mobile_white.html, bundles/*, datafeeds/*）
  let abs = resolve(CL_ROOT, rel)
  if (existsSync(abs) && statSync(abs).isFile()) {
    const ext = (rel.split('.').pop() || '').toLowerCase()
    res.setHeader('Content-Type', MIME[ext] || 'application/octet-stream')
    res.end(readFileSync(abs))
    return
  }

  // 再尝试 CL_ROOT/charting_library/ 子目录（TV 主库文件）
  abs = resolve(CL_ROOT, 'charting_library', rel)
  if (abs.startsWith(CL_ROOT) && existsSync(abs) && statSync(abs).isFile()) {
    const ext = (rel.split('.').pop() || '').toLowerCase()
    res.setHeader('Content-Type', MIME[ext] || 'application/octet-stream')
    res.end(readFileSync(abs))
    return
  }

  next()
}

export default function chartingLibraryServe() {
  return {
    name: 'charting-library-serve',
    configureServer(server) {
      server.middlewares.use(middleware)
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware)
    },
  }
}
