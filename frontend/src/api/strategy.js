/**
 * 策略中心 API 模块
 *
 * 缓存策略：GET 接口 30s 内复用，支持业务级失效（scan.* 系列）。
 */

const _cache = new Map() // key: string → { data, ts }
const DEF_TTL = 30_000   // 30s

function cached(key, ttl = DEF_TTL, fetchFn) {
  const hit = _cache.get(key)
  if (hit && Date.now() - hit.ts < ttl) return Promise.resolve(hit.data)
  return fetchFn().then((d) => {
    _cache.set(key, { data: d, ts: Date.now() })
    return d
  })
}

export function invalidate(prefix) {
  if (!prefix) { _cache.clear(); return }
  for (const k of _cache.keys()) {
    if (k.startsWith(prefix)) _cache.delete(k)
  }
}

/**
 * 安全解析 JSON：避免后端未启动、代理 502、空 body 时 res.json() 抛 Unexpected end of JSON input
 */
async function parseJsonResponse(res, pathHint = '') {
  const text = await res.text()
  const trimmed = (text || '').trim()
  if (!trimmed) {
    const tip = !res.ok ? `HTTP ${res.status}` : '空响应'
    throw new Error(
      `${tip}（${pathHint || '接口'}）。请确认后端已启动（默认 localhost:5002）且 Vite 代理正常。`
    )
  }
  let json
  try {
    json = JSON.parse(trimmed)
  } catch {
    throw new Error(
      `响应不是 JSON（${pathHint || 'request'}，HTTP ${res.status}）：${trimmed.slice(0, 80)}…`
    )
  }
  return json
}

async function apiFetch(path, options = {}) {
  const res = await fetch(path, options)
  const json = await parseJsonResponse(res, path)
  if (!res.ok && json && !json.success) {
    throw new Error(json.error || `HTTP ${res.status}`)
  }
  if (json && json.success === false && json.error) throw new Error(json.error)
  return json.data ?? json
}

async function postJson(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const json = await parseJsonResponse(res, path)
  if (!res.ok && json && !json.success) {
    throw new Error(json.error || `HTTP ${res.status}`)
  }
  if (json && json.success === false && json.error) throw new Error(json.error)
  return json.data ?? json
}

/** 与后端 catalog 一致；接口不可用时下拉仍可选 */
export const WATCHLIST_STRATEGY_FALLBACK = [
  {
    id: 'rsi_extreme',
    name: 'RSI 超买超卖',
    description: 'RSI(14)：>70 超买，<30 超卖',
  },
  {
    id: 'ma_cross',
    name: '均线金叉 / 死叉',
    description: 'MA5 与 MA20 位置与交叉',
  },
  {
    id: 'breakout_20',
    name: '20 日区间突破',
    description: '收盘相对近 20 日（不含当日）高低点',
  },
  {
    id: 'macd_turn',
    name: 'MACD 柱状拐点',
    description: 'MACD 柱由负转正 / 由正转负',
  },
  {
    id: 'bollinger_position',
    name: '布林带位置',
    description: '收盘相对布林上下轨（20,2）',
  },
]

export const watchlist = {
  list:     ()    => apiFetch('/api/watchlist'),
  enriched: ()    => apiFetch('/api/watchlist/enriched'),
  add:   (code, name, sector) =>
    postJson('/api/watchlist/add', {
      code,
      name: name || '',
      ...(sector ? { sector } : {}),
    }),
  remove:(code) => postJson('/api/watchlist/remove',{ code }),
  check: (code) => apiFetch(`/api/watchlist/check/${code}`),
}

/** 自选列表 + TA-Lib / pandas 技术指标扫描 */
export const watchlistStrategy = {
  catalog: () =>
    cached('watchlist/strategy/catalog', 300_000, () =>
      apiFetch('/api/watchlist/strategy/catalog')
    ),
  /** @param {string|string[]} strategyIdOrIds 单个 id 或 id 数组 */
  run: (strategyIdOrIds) => {
    const ids = Array.isArray(strategyIdOrIds)
      ? strategyIdOrIds.map((x) => String(x || '').trim()).filter(Boolean)
      : [String(strategyIdOrIds || '').trim()].filter(Boolean)
    if (!ids.length) return Promise.reject(new Error('未选择策略'))
    if (ids.length === 1) {
      return postJson('/api/watchlist/strategy/run', { strategy_id: ids[0] })
    }
    return postJson('/api/watchlist/strategy/run', { strategy_ids: ids })
  },
  /** 策略列表请求失败时清缓存，便于重试 */
  invalidateCatalog: () => invalidate('watchlist/strategy'),
}

export const stock = {
  detail: (code) => apiFetch(`/api/stock/${code}`),
  quote: (code) => apiFetch(`/api/stock/${code}/quote`),
}

export const stocks = {
  /** 返回完整搜索载荷（含 stock_count / needs_sync，不能只取 data） */
  async search(keyword, limit = 20) {
    const res = await fetch(
      `/api/stocks/search?q=${encodeURIComponent(keyword)}&limit=${limit}`
    )
    const json = await res.json()
    if (!json.success && json.error) throw new Error(json.error)
    return {
      list: json.data || [],
      stockCount: json.stock_count ?? 0,
      needsSync: Boolean(json.needs_sync),
    }
  },
  async status() {
    const res = await fetch('/api/stocks/status')
    const json = await res.json()
    if (!json.success && json.error) throw new Error(json.error)
    return {
      count: json.count ?? 0,
      needsSync: Boolean(json.needs_sync),
    }
  },
  sync: () => postJson('/api/stocks/sync', {}),
}

export const scan = {
  start:   (params) => postJson('/api/scan/start',    params),
  cancel:  ()        => postJson('/api/scan/cancel',  {}),
  status:  ()        => apiFetch('/api/scan/status'),
  results: (scanId)  => scanId != null
    ? apiFetch(`/api/scan/results?scan_id=${scanId}`)
    : apiFetch('/api/scan/results'),
  history: (limit = 100) => cached(`scan/history?limit=${limit}`, 60_000,
                      () => apiFetch(`/api/scan/history?limit=${limit}`)),
  detail:  (id)      => apiFetch(`/api/scan/${id}`),
  /** DeepSeek：扫描小结 + CoT + 推荐（非投资建议） */
  aiSummary: (id)   => apiFetch(`/api/scan/${id}/ai-summary`),
  /** DeepSeek：单只股票基于扫描内指标与标签的简析（非投资建议） */
  stockAiAnalysis: (scanId, code) =>
    postJson(`/api/scan/${scanId}/stock-ai-analysis`, { code }),
  delete:  (id)      => { invalidate('scan/'); return apiFetch(`/api/scan/${id}`, { method: 'DELETE' }) },
}

export const alertRule = {
  list:    ()       => cached('bollinger/alerts', 30_000, () => apiFetch('/api/bollinger/alerts')),
  get:     (id)     => apiFetch(`/api/bollinger/alerts/${id}`),
  create:  (data)   => { invalidate('bollinger/alerts'); return postJson('/api/bollinger/alerts', data) },
  update:  (id, d)  => { invalidate('bollinger/alerts'); return postJson(`/api/bollinger/alerts/${id}`, d) },
  delete:  (id)     => { invalidate('bollinger/alerts'); return apiFetch(`/api/bollinger/alerts/${id}`, { method: 'DELETE' }) },
}

export const report = {
  list: () => apiFetch('/api/ai/reports'),
}
