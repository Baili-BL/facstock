/**
 * 量化回测 API
 */

const DEF_TTL = 30_000
const _cache = new Map()

function cached(key, ttl, fetchFn) {
  const hit = _cache.get(key)
  if (hit && Date.now() - hit.ts < ttl) return Promise.resolve(hit.data)
  return fetchFn().then(d => { _cache.set(key, { data: d, ts: Date.now() }); return d })
}

async function parseJsonResponse(res, pathHint) {
  const text = await res.text()
  const trimmed = (text || '').trim()
  if (!trimmed) throw new Error(`HTTP ${res.status}（${pathHint}）`)
  let json
  try { json = JSON.parse(trimmed) } catch { throw new Error(`响应不是 JSON: ${trimmed.slice(0, 80)}`) }
  return json
}

async function apiFetch(path, options = {}) {
  const res = await fetch(path, options)
  const json = await parseJsonResponse(res, path)
  if (!res.ok && json && !json.success) throw new Error(json.error || `HTTP ${res.status}`)
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
  if (!res.ok && json && !json.success) throw new Error(json.error || `HTTP ${res.status}`)
  if (json && json.success === false && json.error) throw new Error(json.error)
  return json.data ?? json
}

/** 获取内置策略模板目录（含参数定义） */
export function backtestCatalog() {
  return cached('backtest/catalog', 300_000, () => apiFetch('/api/backtest/catalog'))
}

/** 执行量化回测 */
export function backtestRun(body) {
  return postJson('/api/backtest/run', body)
}
