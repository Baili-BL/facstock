/**
 * 题材挖掘 API 模块（含 session 缓存、错误提示）
 */

const TICAI_ALL_CACHE_KEY = 'facstock_ticai_all_v2'
/** 未点「刷新」时，在此时间内复用缓存、不发请求 */
const ALL_CACHE_TTL_MS = 3 * 60 * 1000

function tradingDayKey() {
  try {
    return new Date().toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' })
  } catch {
    return new Date().toDateString()
  }
}

function apiBase() {
  const v = import.meta.env?.VITE_API_BASE
  if (v && String(v).trim()) return String(v).replace(/\/$/, '')
  return ''
}

function buildUrl(path) {
  const base = apiBase()
  if (!base) return path
  return `${base}${path.startsWith('/') ? path : '/' + path}`
}

/** 深度排序键后序列化，用于判断两次 payload 是否一致 */
function canonicalStringify(value) {
  if (value === null || typeof value !== 'object') {
    return JSON.stringify(value)
  }
  if (Array.isArray(value)) {
    return `[${value.map(canonicalStringify).join(',')}]`
  }
  return `{${Object.keys(value)
    .sort()
    .map((k) => JSON.stringify(k) + ':' + canonicalStringify(value[k]))
    .join(',')}}`
}

function readAllCache() {
  try {
    const raw = sessionStorage.getItem(TICAI_ALL_CACHE_KEY)
    if (!raw) return null
    const o = JSON.parse(raw)
    if (!o || typeof o.savedAt !== 'number' || !o.payload) return null
    if (o.dayKey !== tradingDayKey()) return null
    return o
  } catch {
    return null
  }
}

function writeAllCache(payload) {
  try {
    sessionStorage.setItem(
      TICAI_ALL_CACHE_KEY,
      JSON.stringify({
        savedAt: Date.now(),
        dayKey: tradingDayKey(),
        sig: canonicalStringify(payload),
        payload,
      })
    )
  } catch {
    /* quota / private mode */
  }
}

async function parseJsonResponse(res, url) {
  const ct = (res.headers.get('content-type') || '').toLowerCase()
  const text = await res.text()
  if (res.status === 301 || res.status === 302 || res.status === 307 || res.status === 308) {
    throw new Error(
      `接口返回重定向 ${res.status}，请确认：1) 后端已启动(如 5001)；2) 开发时用 Vite 代理；3) 生产环境在 .env 设置 VITE_API_BASE 指向 Flask 根地址`
    )
  }
  if (!res.ok) {
    throw new Error(`请求失败 HTTP ${res.status}${text ? ': ' + text.slice(0, 120) : ''}`)
  }
  if (!ct.includes('json') && text.trim().startsWith('<')) {
    throw new Error('返回了 HTML 而非 JSON（常被 302 到登录页或前端首页），请检查 API 地址与代理')
  }
  let json
  try {
    json = JSON.parse(text)
  } catch {
    throw new Error('响应不是合法 JSON，可能被重定向到静态页')
  }
  return json
}

async function apiFetch(path) {
  const res = await fetch(buildUrl(path))
  const json = await parseJsonResponse(res, path)
  if (!json.success) throw new Error(json.error || '接口错误')
  return json.data
}

async function postJson(path, body) {
  const res = await fetch(buildUrl(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const json = await parseJsonResponse(res, path)
  if (!json.success) throw new Error(json.error || '接口错误')
  return json.data
}

export const ticai = {
  themes: () => apiFetch('/api/ticai/themes'),

  /**
   * 全量题材数据
   * @param {{ force?: boolean, refreshFirst?: boolean }} options
   *   force=true 强制拉接口（绕过前端 TTL）；false 时在 TTL 内且缓存存在则直接返回缓存
   *   refreshFirst=true 先调后端 /api/ticai/refresh 清除 MySQL+Redis，再重新抓取
   * @returns {Promise<{ data: object, market_change: number, fromCache?: boolean, unchanged?: boolean }>}
   */
  async all(options = {}) {
    const force = !!options.force
    const refreshFirst = !!options.refreshFirst
    const cached = readAllCache()
    const now = Date.now()

    if (!force && cached && now - cached.savedAt < ALL_CACHE_TTL_MS) {
      return { ...cached.payload, fromCache: true, unchanged: true }
    }

    // refreshFirst=true：先清后端 MySQL+Redis，确保下次拿到新数据
    if (refreshFirst) {
      try {
        await this.refresh()
      } catch (e) {
        console.warn('[ticai] refresh() failed, continue anyway:', e)
      }
    }

    const res = await fetch(buildUrl('/api/ticai/all'))
    const json = await parseJsonResponse(res, '/api/ticai/all')
    if (!json.success) throw new Error(json.error || '接口错误')

    const payload = {
      data: json.data || {},
      market_change: json.market_change ?? 0,
    }
    const newSig = canonicalStringify(payload)
    const sameAsCache = cached && cached.sig === newSig

    if (!sameAsCache || force) {
      writeAllCache(payload)
    } else {
      try {
        sessionStorage.setItem(
          TICAI_ALL_CACHE_KEY,
          JSON.stringify({
            savedAt: now,
            dayKey: tradingDayKey(),
            sig: newSig,
            payload,
          })
        )
      } catch {
        /* ignore */
      }
    }

    return {
      ...payload,
      fromCache: false,
      unchanged: sameAsCache,
    }
  },

  /** 强制刷新：清除后端 MySQL+Redis 缓存，下次 all() 会走完整 pipeline */
  async refresh() {
    await postJson('/api/ticai/refresh', {})
  },

  /** 清除题材全量缓存（例如退出登录前可调用） */
  clearAllCache() {
    try {
      sessionStorage.removeItem(TICAI_ALL_CACHE_KEY)
    } catch {
      /* ignore */
    }
  },

  kline: (code) => apiFetch(`/api/ticai/kline/${code}`),
  reports: () => apiFetch('/api/ticai/reports'),
  report: (date) => apiFetch(`/api/ticai/reports/${date}`),
  performance: () => apiFetch('/api/ticai/performance/summary'),
  todayPerf: () => apiFetch('/api/ticai/performance/today'),
  updatePerf: () => postJson('/api/ticai/performance/update', {}),
  stockHistory: (code) => apiFetch(`/api/ticai/stock/${code}/history`),
}
