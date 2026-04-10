/**
 * 自定义因子 Prompt 工程 — DeepSeek 生成
 */

export async function getFactorTemplate() {
  const res = await fetch('/api/strategy/factor/template')
  const json = await res.json()
  if (!json.success) throw new Error(json.error || '加载模板失败')
  return json.data
}

export async function getFactorStatus() {
  const res = await fetch('/api/strategy/factor/status')
  const json = await res.json()
  if (!json.success) throw new Error(json.error || '状态请求失败')
  return json
}

/**
 * @param {string} instruction
 * @returns {Promise<{ code: string, model?: string, tokens_used?: number, template_version?: string }>}
 */
export async function generateFactor(instruction) {
  const res = await fetch('/api/strategy/factor/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instruction }),
  })
  const json = await res.json()
  if (!json.success) {
    const err = new Error(json.error || '生成失败')
    err.filtered = Boolean(json.filtered)
    err.status = res.status
    throw err
  }
  return json.data
}
