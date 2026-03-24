/**
 * 策略中心 API 模块
 */

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
  list:  ()    => apiFetch('/api/watchlist'),
  add:   (code) => postJson('/api/watchlist/add',   { code }),
  remove:(code) => postJson('/api/watchlist/remove',{ code }),
  check: (code) => apiFetch(`/api/watchlist/check/${code}`),
}

export const stock = {
  detail: (code) => apiFetch(`/api/stock/${code}`),
}

export const scan = {
  start:   (params) => postJson('/api/scan/start',    params),
  cancel:  ()        => postJson('/api/scan/cancel',  {}),
  status:  ()        => apiFetch('/api/scan/status'),
  results: (scanId)  => scanId != null
    ? apiFetch(`/api/scan/results?scan_id=${scanId}`)
    : apiFetch('/api/scan/results'),
  history: ()        => apiFetch('/api/scan/history'),
  detail:  (id)      => apiFetch(`/api/scan/${id}`),
  delete:  (id)      => apiFetch(`/api/scan/${id}`,  { method: 'DELETE' }),
}
