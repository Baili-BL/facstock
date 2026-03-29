/**
 * 财经新闻 API 模块
 */

const CACHE_KEY = 'news_cache'
const CACHE_TTL = 60 * 1000 // 1分钟本地缓存

function getCache() {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    if (!raw) return null
    const { data, time } = JSON.parse(raw)
    if (Date.now() - time > CACHE_TTL) {
      localStorage.removeItem(CACHE_KEY)
      return null
    }
    return data
  } catch {
    return null
  }
}

function setCache(data) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({ data, time: Date.now() }))
  } catch {}
}

async function apiFetch(path, options = {}) {
  const res = await fetch(path, options)
  const text = await res.text()
  if (text.startsWith('<')) throw new Error('网络异常，请稍后重试')
  const json = JSON.parse(text)
  if (!json.success) throw new Error(json.error || '接口错误')
  return json.data
}

export const news = {
  list: (force = false) => {
    if (!force) {
      const cached = getCache()
      if (cached) return Promise.resolve(cached)
    }
    const q = force ? '?force=1' : ''
    return apiFetch(`/api/news${q}`).then((data) => {
      setCache(data)
      return data
    })
  },
  clearCache: () => localStorage.removeItem(CACHE_KEY),
}
