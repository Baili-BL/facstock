/**
 * 财经新闻 API 模块
 */

async function apiFetch(path) {
  const res = await fetch(path)
  const text = await res.text()
  if (text.startsWith('<')) throw new Error('网络异常，请稍后重试')
  const json = JSON.parse(text)
  if (!json.success) throw new Error(json.error || '接口错误')
  return json.data
}

export const news = {
  list: () => apiFetch('/api/news'),
}
