/**
 * 市场数据 API 模块
 * 所有 /api/market/* 请求统一出口
 */

async function apiFetch(path) {
  const res = await fetch(path)
  const json = await res.json()
  if (!json.success) throw new Error(json.error || '接口错误')
  return json.data
}

export const market = {
  overview: ()    => apiFetch('/api/market/overview'),
  flow:    ()     => apiFetch('/api/market/flow'),
  limit:   ()     => apiFetch('/api/market/limit'),
  turnover:()     => apiFetch('/api/market/turnover'),
  sectors: ()     => apiFetch('/api/market/sectors'),
  summary: ()     => apiFetch('/api/market/summary'),
}

export const hotSectors = () => apiFetch('/api/hot-sectors')
