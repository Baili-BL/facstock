/**
 * 策略智能体 API 客户端
 * 对接后端 /api/agents/* 端点
 */

import { ref } from 'vue'

const BASE = '/api'

// ─── 通用请求 ────────────────────────────────────────────────────────────

async function apiPost(path, body = {}, options = {}) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    ...options,
  })
  const json = await res.json()
  if (!json.success) throw new Error(json.error || '请求失败')
  return json
}

async function apiGet(path) {
  const res = await fetch(path)
  const json = await res.json()
  if (!json.success) throw new Error(json.error || '请求失败')
  return json
}

// ─── Agent 元信息 ────────────────────────────────────────────────────────

export async function fetchAgentPrompts() {
  const json = await apiGet(`${BASE}/agents/prompts`)
  return json.data // AgentProfile[]
}

// ─── 单个 Agent 分析 ────────────────────────────────────────────────────

/**
 * @param {string} agentId - jun | qiao | jia | speed | trend | quant
 * @returns {Promise<{structured: object, analysis: string, tokens_used: number}>}
 */
export async function analyzeWithAgent(agentId) {
  return apiPost(`${BASE}/agents/analyze/${agentId}`)
}

// ─── 批量分析（全场共识）─────────────────────────────────────────────────

/**
 * 并行跑全部 6 个 Agent，返回共识 + 头寸卡片 + TOP 3
 *
 * @returns {Promise<{
 *   scan_time: string,
 *   consensus: { consensusPct, bullCount, bearCount, neutralCount },
 *   agentResults: Array<{
 *     agent_id, agent_name, success,
 *     structured: {
 *       agentId, agentName, stance, confidence,
 *       marketCommentary, positionAdvice, riskWarning,
 *       recommendedStocks: Array<StockRecommendation>
 *     },
 *     analysis: string,
 *     tokens_used: number
 *   }>,
 *   consensusOpportunities: Array<{
 *     rank, title, badge, badgeKind, meta, chg, flowLabel
 *   }>,
 *   lastUpdated: string
 * }>}
 */
export async function batchAnalyzeAgents() {
  return apiPost(`${BASE}/agents/batch`)
}

// ─── 共识计算工具（前端 fallback）────────────────────────────────────────

/**
 * 根据 agentResults 计算全局共识百分比
 * @param {Array} agentResults
 */
export function computeClientConsensus(agentResults) {
  const valid = agentResults.filter(r => r.success && r.structured)
  if (!valid.length) return { consensusPct: 50, bullCount: 0, bearCount: 0, neutralCount: 0 }
  let totalWeight = 0
  let weightedSum = 0
  const counts = { bull: 0, bear: 0, neutral: 0 }
  for (const r of valid) {
    const { stance, confidence = 50 } = r.structured
    counts[stance] = (counts[stance] || 0) + 1
    const wm = { bull: 1, neutral: 0, bear: -1 }
    weightedSum += (wm[stance] || 0) * confidence
    totalWeight += confidence
  }
  const pct = totalWeight > 0 ? Math.round(50 + (weightedSum / totalWeight) * 50) : 50
  return {
    consensusPct: Math.max(0, Math.min(100, pct)),
    bullCount: counts.bull || 0,
    bearCount: counts.bear || 0,
    neutralCount: counts.neutral || 0,
  }
}

// ─── stance → UI 映射 ───────────────────────────────────────────────────

export const STANCE_META = {
  bull:     { tagLabel: '看多', tone: 'bull' },
  bear:     { tagLabel: '看空', tone: 'bear' },
  neutral:  { tagLabel: '中性', tone: 'neutral' },
}

export function stanceMeta(stance) {
  return STANCE_META[stance] || STANCE_META.neutral
}

// ─── 缓存：避免重复请求 ──────────────────────────────────────────────────

const _cache = new Map()
const CACHE_TTL = 60_000 // 1 分钟

export function cached(key, fn) {
  const hit = _cache.get(key)
  if (hit && Date.now() - hit.ts < CACHE_TTL) return Promise.resolve(hit.val)
  return fn().then(val => {
    _cache.set(key, { val, ts: Date.now() })
    return val
  })
}

export function clearCache() {
  _cache.clear()
}
