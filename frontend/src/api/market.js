/**
 * 市场数据 API 模块
 * 所有 /api/market/* 请求统一出口
 *
 * 缓存策略：同接口同参数 30s 内复用，支持业务级失效。
 */

const _cache = new Map() // key: string → { data, ts }
const DEF_TTL = 30_000   // 默认 30s

function cached(key, ttl = DEF_TTL, fetchFn) {
  const hit = _cache.get(key)
  if (hit && Date.now() - hit.ts < ttl && !hit.data.then) return hit.data
  if (hit && hit.data && hit.data.then) return hit.data
  const prom = fetchFn().then(d => {
    _cache.set(key, { data: d, ts: Date.now() })
    return d
  }).catch(err => {
    _cache.delete(key)
    throw err
  })
  _cache.set(key, { data: prom, ts: Date.now() })
  return prom
}

function invalidate(prefix) {
  if (!prefix) { _cache.clear(); return }
  for (const k of _cache.keys()) {
    if (k.startsWith(prefix)) _cache.delete(k)
  }
}

async function apiFetch(path, cacheKey, ttl) {
  const res = await fetch(path)
  const json = await res.json()
  if (!json.success) throw new Error(json.error || '接口错误')
  return json.data
}

export const market = {
  /** A 股交易时段（后端北京时间判定） */
  session:   () => cached('market/session',   15_000, () => apiFetch('/api/market/session',     'market/session')),
  overview:  () => cached('market/overview',  30_000, () => apiFetch('/api/market/overview',    'market/overview')),
  snapshot:  () => cached('market/snapshot/v2',  15_000, () => apiFetch('/api/market/snapshot',    'market/snapshot/v2')),
  flow:      () => cached('market/flow',      30_000, () => apiFetch('/api/market/flow',         'market/flow')),
  limit:     () => cached('market/limit',     15_000, () => apiFetch('/api/market/limit',        'market/limit')),
  turnover:  () => cached('market/turnover',  30_000, () => apiFetch('/api/market/turnover',    'market/turnover')),
  sectors:   () => cached('market/sectors',   30_000, () => apiFetch('/api/market/sectors',     'market/sectors')),
  sectorsConcept: () => cached('market/sectors/concept', 30_000,
                    () => apiFetch('/api/market/sectors/concept', 'market/sectors/concept')),
  /** @param {'industry'|'concept'|'region'} kind */
  sectorMainFundFlow: (kind = 'industry') => cached(
    `market/sectors/main-fund-flow/${kind}`,
    30_000,
    () => apiFetch(`/api/market/sectors/main-fund-flow?kind=${encodeURIComponent(kind)}`, `market/sectors/main-fund-flow/${kind}`)
  ),
  summary:   () => cached('market/summary',   30_000, () => apiFetch('/api/market/summary',      'market/summary')),
  /** 三大指数近3天分时数据 */
  indexMini: () => cached('market/index-mini', 60_000, () => apiFetch('/api/market/index-mini', 'market/index-mini')),
  invalidate,
}

export const hotSectors = () => cached('market/hot-sectors', 30_000,
    () => apiFetch('/api/hot-sectors', 'market/hot-sectors'))

export const macroSummary = () => cached('macro/summary', 60_000,
    () => apiFetch('/api/macro/summary', 'macro/summary'))

export const macroFlashReport = () => cached('macro/flash-report', 60_000,
    () => apiFetch('/api/macro/flash-report', 'macro/flash-report'))
