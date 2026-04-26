/**
 * 策略智能体 API 客户端
 * 对接后端 /api/agents/* 和 /api/junge/* 端点
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

export async function fetchAgentArchitecture() {
  const json = await apiGet(`${BASE}/agents/architecture`)
  return json.data
}

// ─── 单个 Agent 分析 ────────────────────────────────────────────────────

/**
 * @param {string} agentId - jun | qiao | jia | speed | trend | quant
 * @returns {Promise<{structured: object, analysis: string, tokens_used: number}>}
 */
export async function analyzeWithAgent(agentId) {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), 180_000)
  let res
  try {
    res = await fetch(`${BASE}/agents/analyze/${agentId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
      signal: ctrl.signal,
    })
  } catch (e) {
    if (e?.name === 'AbortError') {
      throw new Error('分析超时（超过 3 分钟），请稍后重试')
    }
    throw e
  } finally {
    clearTimeout(t)
  }
  let json
  try {
    json = await res.json()
  } catch {
    throw new Error('服务器返回非 JSON')
  }
  if (!json.success) throw new Error(json.error || '请求失败')
  if (json.agent_success === false) {
    const err = new Error(json.error || '智能体分析失败，请稍后重试')
    err.name = 'AgentBackendError'
    err.payload = json
    throw err
  }
  const { success: _s, agent_success: _a, error: _e, ...rest } = json
  return rest
}

// ─── 批量分析（全场共识）─────────────────────────────────────────────────

/**
 * 并行跑全部 Agent 或层次化分析
 *
 * @param {object} options
 * @param {string} options.mode - 'parallel' | 'hierarchical'
 * @returns {Promise<{
 *   scan_time: string,
 *   mode: string,
 *   consensus: { consensusPct, bullCount, bearCount, neutralCount, weightedConfidence },
 *   agentResults: Array<{
 *     agent_id, agent_name, success, status,
 *     structured: {
 *       agentId, agentName, stance, confidence,
 *       marketCommentary, positionAdvice, riskWarning,
 *       recommendedStocks: Array<StockRecommendation>
 *     },
 *     analysis: string,
 *     thinking: string,
 *     tokens_used: number,
 *     execution_time_ms: number,
 *     retry_count: number,
 *   }>,
 *   consensusOpportunities: Array<{
 *     rank, title, code, badge, badgeKind, meta, chg, flowLabel,
 *     adviseTypes: string[], signals: string[]
 *   }>,
 *   master: {
 *     marketCoreIntent: string,
 *     marketPhase: string,
 *     riskAppetite: string,
 *     agentPriority: string[],
 *     keyTheme: string,
 *     riskFactors: string[],
 *     coordinationNotes: string,
 *   } | null,
 *   synthesis: string,
 *   execution_log: Array<{
 *     timestamp, phase, agent_id, status, message
 *   }>,
 *   success_rate: number,
 *   lastUpdated: string
 * }>}
 */
export async function batchAnalyzeAgents(options = {}) {
  const mode = options.mode || 'parallel'
  return apiPost(`${BASE}/agents/batch`, { mode })
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

// ─── JunGeTrader API ─────────────────────────────────────────────────────────

/**
 * JunGeTrader API 客户端
 * 对接 /api/junge/* 端点
 */

/**
 * 获取大盘市场状态
 * @returns {Promise<{indexData: object, condition: object, timestamp: string}>}
 */
export async function fetchJungeMarket() {
  const json = await apiGet(`${BASE}/junge/market`)
  return json.data
}

/**
 * 获取热点板块
 * @param {number} limit - 板块数量，默认10
 * @returns {Promise<Array<{name, code, change, leader, leaderChange}>>}
 */
export async function fetchJungeSectors(limit = 10) {
  const json = await apiGet(`${BASE}/junge/sectors?limit=${limit}`)
  return json.data
}

/**
 * 执行钧哥每日扫描
 * @param {object} opts
 * @param {number} opts.sectors - 热点板块数量，默认5
 * @param {boolean} opts.enhance - 是否启用 AI 增强，默认true
 * @returns {Promise<{
 *   scanTime: string,
 *   elapsedSeconds: number,
 *   scanMode: string,
 *   market: object,
 *   hotSectors: array,
 *   stats: object,
 *   recommendations: array,
 *   candidates: array,
 *   agentResult: object,
 *   summary: string,
 * }>}
 */
export async function runJungeScan({ sectors = 5, enhance = true } = {}) {
  return apiPost(`${BASE}/junge/scan`, { sectors, enhance })
}

/**
 * 获取 JunGeTrader 状态
 * @returns {Promise<{lastScanTime, lastHotSectorsCount, lastResultsCount, hasAiResult}>}
 */
export async function fetchJungeStatus() {
  const json = await apiGet(`${BASE}/junge/status`)
  return json.data
}

/**
 * 获取最近一次 AI 增强分析结果
 * @returns {Promise<object>}
 */
export async function fetchJungeAiResult() {
  return apiGet(`${BASE}/junge/ai-result`)
}

// ─── 新架构：Qwen + AKShare + DeepSeek 流式分析 ──────────────────────────────

/**
 * 意图识别接口
 * @param {string} userInput - 用户输入
 * @returns {Promise<object>}
 */
export async function analyzeIntent(userInput) {
  return apiPost(`${BASE}/analyze/intent`, { user_input: userInput })
}

/**
 * 新架构流式分析
 * @param {object} options
 * @param {string} options.userInput - 用户输入
 * @param {string[]} options.stockCodes - 关注的股票代码
 * @param {object} options.context - 额外上下文
 * @returns {Promise<ReadableStream>} SSE 流
 */
export async function analyzeStream({ userInput, stockCodes = [], context = {} }) {
  const response = await fetch(`${BASE}/analyze/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_input: userInput,
      stock_codes: stockCodes,
      context
    })
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }

  return response.body
}

/**
 * 解析 SSE 流
 * @param {ReadableStream} stream - SSE 流
 * @param {object} callbacks - 回调函数
 */
export function parseStreamEvents(stream, callbacks = {}) {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const { onStatus, onIntent, onData, onAnalysis, onThinking, onStructured, onDone, onError } = callbacks

  function processLine(line) {
    if (!line.startsWith('data: ')) return

    try {
      const data = JSON.parse(line.slice(6))

      switch (data.type) {
        case 'status':
          onStatus?.(data.message)
          break
        case 'intent':
          onIntent?.(data)
          break
        case 'data':
          onData?.(data)
          break
        case 'analysis':
          onAnalysis?.(data.content)
          break
        case 'thinking':
          onThinking?.(data.content)
          break
        case 'structured':
          onStructured?.(data.data)
          break
        case 'done':
          onDone?.(data)
          break
        case 'error':
          onError?.(data.error)
          break
        case 'close':
          return true  // 结束
      }
    } catch (e) {
      console.warn('[parseStreamEvents] Parse error:', e)
    }
    return false
  }

  return new Promise((resolve, reject) => {
    function read() {
      reader.read().then(({ done, value }) => {
        if (done) {
          resolve()
          return
        }

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (processLine(line)) {
            reader.cancel()
            resolve()
            return
          }
        }

        read()
      }).catch(reject)
    }

    read()
  })
}

// ─── Agent 分析历史 ─────────────────────────────────────────────────────────

/**
 * 获取今日分析结果（如有）
 * @param {string} agentId
 * @returns {Promise<object|null>}
 */
export async function fetchTodayAnalysis(agentId) {
  try {
    const json = await apiGet(`${BASE}/agents/${agentId}/analysis/today`)
    return json.data || null
  } catch {
    return null
  }
}

/**
 * 获取 Agent Prompt 详情
 * @param {string} agentId
 * @returns {Promise<{id, name, role, tagline, adviseType, system_prompt, user_prompt_template}>}
 */
export async function fetchAgentInfo(agentId) {
  const json = await apiGet(`${BASE}/agents/${agentId}/prompt`)
  return json.data || {}
}

/**
 * 获取单个 Agent 完整资料（策略详情页用）
 * @param {string} agentId
 * @returns {Promise<AgentProfile>}
 */
export async function fetchAgentProfile(agentId) {
  const json = await apiGet(`${BASE}/agents/${agentId}/prompt`)
  return json.data || {}
}

// ─── 飞书推送管理 ────────────────────────────────────────────────────────────

/**
 * 获取飞书推送状态（调度器状态 + 最近推送历史）
 * @returns {Promise<object>}
 */
export async function fetchAgentPushStatus() {
  const json = await apiGet(`${BASE}/agents/push/status`)
  return json.data
}

/**
 * 更新飞书推送配置
 * @param {object} config
 * @param {boolean} [config.enabled]
 * @param {string}  [config.webhook_url]
 * @param {string[]} [config.agent_ids]
 * @param {number}   [config.top_stocks_per_agent]
 * @param {number}   [config.consensus_top_n]
 * @param {number}   [config.analysis_max_workers]
 * @returns {Promise<object>}
 */
export async function updateAgentPushConfig(config) {
  return apiPost(`${BASE}/agents/push/config`, config)
}

/**
 * 手动触发一次飞书推送
 * @param {object} opts
 * @param {string[]} [opts.agent_ids]      — 指定 Agent，默认用配置中的
 * @param {string}   [opts.slot_key]       — 时段 key
 * @param {string}   [opts.slot_label]     — 时段标签
 * @param {string}   [opts.webhook_url]    — 临时 webhook（可选）
 * @param {boolean}  [opts.dry_run]        — 是否仅生成不发送
 * @returns {Promise<object>}
 */
export async function triggerAgentPush(opts = {}) {
  return apiPost(`${BASE}/agents/push/trigger`, opts)
}

/**
 * 测试飞书 Webhook 连通性
 * @param {string} webhookUrl — 可选，用当前配置的则不传
 * @returns {Promise<{success: boolean, message: string}>}
 */
export async function testFeishuWebhook(webhookUrl) {
  const body = webhookUrl ? { webhook_url: webhookUrl } : {}
  return apiPost(`${BASE}/feishu/test`, body)
}

// ─── 飞书推送管理 API（新版，基于数据库）──────────────────────────────────────

/**
 * 获取完整推送状态（数据库配置 + 调度器状态）
 * @returns {Promise<object>}
 */
export async function fetchPushStatus() {
  const json = await apiGet(`${BASE}/push/status`)
  return json.data
}

/**
 * 保存推送配置（数据库 + 运行时服务）
 * @param {object} cfg
 * @param {string[]} [cfg.agentIds]   — 选中的 Agent ID 列表
 * @param {string}  [cfg.webhookUrl] — Webhook URL
 * @param {number}  [cfg.topStocksPerAgent]
 * @param {number}  [cfg.consensusTopN]
 * @param {number}  [cfg.analysisMaxWorkers]
 * @param {boolean} [cfg.enabled]
 * @param {Array}   [cfg.slotUpdates] — [{key, enabled, label, time}]
 * @returns {Promise<object>}
 */
export async function savePushConfig(cfg) {
  const json = await apiPost(`${BASE}/push/config`, cfg)
  return json.data
}

/**
 * 获取推送历史
 * @param {number} limit
 * @returns {Promise<Array>}
 */
export async function fetchPushHistory(limit = 30) {
  const json = await apiGet(`${BASE}/push/history?limit=${limit}`)
  return json.data
}

/**
 * 获取单条推送记录详情（含完整 digest）
 * @param {number} recordId
 * @returns {Promise<object>}
 */
export async function fetchPushRecord(recordId) {
  const json = await apiGet(`${BASE}/push/record/${recordId}`)
  return json.data
}

/**
 * 手动触发一次推送（新版）
 * @param {object} opts
 * @param {string[]} [opts.agent_ids]
 * @param {string}   [opts.slot_key]
 * @param {string}   [opts.slot_label]
 * @param {string}   [opts.webhook_url]
 * @param {boolean}  [opts.dry_run]
 * @param {boolean}  [opts.include_payload]
 * @returns {Promise<object>}
 */
export async function triggerPush(opts = {}) {
  return apiPost(`${BASE}/push/trigger`, opts)
}

/**
 * 获取推送配置变更日志
 * @param {number} limit
 * @returns {Promise<Array>}
 */
export async function fetchPushConfigLogs(limit = 50) {
  const json = await apiGet(`${BASE}/push/config-logs?limit=${limit}`)
  return json.data
}

/**
 * 删除指定配置变更日志
 * @param {number} logId
 * @returns {Promise<void>}
 */
export async function deletePushConfigLog(logId) {
  const res = await fetch(`${BASE}/push/config-logs/${logId}`, { method: 'DELETE' })
  const json = await res.json()
  if (!json.success) throw new Error(json.error || '删除失败')
}
