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
  const prom = fetchFn().then(d => {
    _cache.set(key, { data: d, ts: Date.now() })
    return d
  })
  _cache.set(key, { data: prom, ts: Date.now() })
  return prom
}

export function invalidate(prefix) {
  if (!prefix) { _cache.clear(); return }
  for (const k of _cache.keys()) {
    if (k.startsWith(prefix)) _cache.delete(k)
  }
}

async function apiFetch(path, options = {}) {
  const res = await fetch(path, options)
  const json = await res.json()
  if (!json.success && json.error) throw new Error(json.error)
  return json.data ?? json
}

async function postJson(path, body) {
  return apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

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
