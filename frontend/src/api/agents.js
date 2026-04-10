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

// ─── 演示模式 API ──────────────────────────────────────────────────────────

/**
 * 演示模式：不调后端 LLM，直接用预设数据展示流程
 * @param {string} agentId
 * @param {Function} onStep - 回调(step: {step, message, data})
 */
export async function demoAnalyzeAgent(agentId, onStep) {
  const steps = [
    { step: 1, message: '正在准备市场数据...', delay: 600 },
    { step: 2, message: '正在加载 Agent Prompt 模板...', delay: 400 },
    { step: 3, message: `正在调用 AI 模型分析「${agentId}」...`, delay: 1200 },
    { step: 4, message: '正在解析结构化分析结果...', delay: 500 },
    { step: 5, message: '正在聚合共识信号...', delay: 400 },
  ]

  // 逐步回调
  for (const s of steps) {
    await new Promise(r => setTimeout(r, s.delay))
    if (onStep) onStep(s)
  }

  // 返回模拟结果
  return {
    success: true,
    agent_id: agentId,
    agent_name: _agentNameMap[agentId] || agentId,
    name_brand: _agentBrandMap[agentId] || agentId,
    role_subtitle: _roleMap[agentId] || '',
    structured: _demoStructured[agentId] || _demoStructured.jun,
    analysis: _demoAnalysis[agentId] || _demoAnalysis.jun,
    tokens_used: 0,
  }
}

const _agentNameMap = {
  jun: '钧哥天下无双', qiao: '乔帮主', jia: '炒股养家',
  speed: '极速先锋', trend: '趋势追随者', quant: '量化之翼',
}
const _agentBrandMap = {
  jun: '钧哥', qiao: '乔帮主', jia: '炒股养家',
  speed: '极速先锋', trend: '趋势追随者', quant: '量化之翼',
}
const _roleMap = {
  jun: '龙头战法', qiao: '板块轮动', jia: '低位潜伏',
  speed: '打板专家', trend: '中线波段', quant: '算法回测',
}

const _demoStructured = {
  jun: {
    agentId: 'jun', agentName: '钧哥天下无双', stance: 'bull', confidence: 82,
    marketCommentary: '市场情绪亢奋，龙头股联动效应显著，连板个股情绪高涨，适合聚焦主线龙头。',
    positionAdvice: '维持8成仓位，重点配置当前主线龙头与连板强势股，跟随主力资金方向，积极参与情绪溢价。',
    riskWarning: '警惕高位分歧加大，随时关注炸板率变化，做好隔夜仓控管理。',
    recommendedStocks: [
      { name: '龙头股份', code: '600630.SH', role: '龙头', reason: '板块龙头连板，人气极高', chg_pct: 10.0 },
      { name: '宁德时代', code: '300750.SZ', role: '中军', reason: '行业龙头，机构锁仓', chg_pct: 5.5 },
    ],
  },
  qiao: {
    agentId: 'qiao', agentName: '乔帮主', stance: 'bull', confidence: 74,
    marketCommentary: '板块轮动有序，科技与消费交替上行，市场风格偏向成长，轮动节奏良好。',
    positionAdvice: '维持7成仓位，主线持仓为主，辅以波段降本，关注板块轮动节奏变化。',
    riskWarning: '警惕风格快速切换，保持组合灵活性，注意高位板块补跌风险。',
    recommendedStocks: [
      { name: '北方华创', code: '002371.SZ', role: '轮动龙头', reason: '半导体主线，业绩超预期', chg_pct: 4.8 },
    ],
  },
  jia: {
    agentId: 'jia', agentName: '炒股养家', stance: 'neutral', confidence: 65,
    marketCommentary: '市场高位震荡，安全边际有所下降，建议控制仓位，适度防御。',
    positionAdvice: '建议5-6成仓位，配置低估值高股息标的，左侧布局等待估值修复。',
    riskWarning: '高位震荡风险加大，左侧布局需严格止损纪律。',
    recommendedStocks: [
      { name: '长江电力', code: '600900.SH', role: '防御配置', reason: '高股息，低波动', chg_pct: 0.5 },
    ],
  },
  speed: {
    agentId: 'speed', agentName: '极速先锋', stance: 'bear', confidence: 60,
    marketCommentary: '打板情绪高潮，炸板率上升，隔夜溢价收窄，当前非理想打板时机。',
    positionAdvice: '收缩打板仓位至2成以下，优选首板与题材龙头，缩短持仓周期。',
    riskWarning: '高位打板风险极大，务必严格执行止损，隔夜仓不超3成。',
    recommendedStocks: [],
  },
  trend: {
    agentId: 'trend', agentName: '趋势追随者', stance: 'bull', confidence: 72,
    marketCommentary: '均线系统保持多头排列，中期上升趋势未破坏，回调是加仓机会。',
    positionAdvice: '维持7成仓位，回调至均线附近加仓，跌破20日线减仓保护利润。',
    riskWarning: '趋势破坏风险，若指数有效跌破均线系统需果断降仓。',
    recommendedStocks: [
      { name: '宁德时代', code: '300750.SZ', role: '趋势跟随', reason: '均线多头，趋势完好', chg_pct: 3.2 },
    ],
  },
  quant: {
    agentId: 'quant', agentName: '量化之翼', stance: 'bull', confidence: 68,
    marketCommentary: '多因子模型显示成长与动量因子共振向上，波动率处于中等偏低区间。',
    positionAdvice: '因子模型建议8成仓位，成长因子权重略高，等权配置，动态再平衡。',
    riskWarning: '量化模型存在失效风险，关注因子轮动信号，做好风险对冲。',
    recommendedStocks: [
      { name: '迈瑞医疗', code: '300760.SZ', role: '因子强势', reason: '动量因子得分高', chg_pct: 2.1 },
    ],
  },
}

const _demoAnalysis = {
  jun: '【市场解读】市场情绪亢奋，龙头股联动效应显著，连板个股情绪高涨，适合聚焦主线龙头。\n【策略建议】维持8成仓位，重点配置当前主线龙头与连板强势股，跟随主力资金方向，积极参与情绪溢价。\n【风险提示】警惕高位分歧加大，随时关注炸板率变化，做好隔夜仓控管理。\n推荐关注：龙头股份(600630.SH) - 龙头: 板块龙头连板，人气极高\n推荐关注：宁德时代(300750.SZ) - 中军: 行业龙头，机构锁仓',
  qiao: '【市场解读】板块轮动有序，科技与消费交替上行，市场风格偏向成长，轮动节奏良好。\n【策略建议】维持7成仓位，主线持仓为主，辅以波段降本，关注板块轮动节奏变化。\n【风险提示】警惕风格快速切换，保持组合灵活性，注意高位板块补跌风险。',
  jia: '【市场解读】市场高位震荡，安全边际有所下降，建议控制仓位，适度防御。\n【策略建议】建议5-6成仓位，配置低估值高股息标的，左侧布局等待估值修复。\n【风险提示】高位震荡风险加大，左侧布局需严格止损纪律。',
  speed: '【市场解读】打板情绪高潮，炸板率上升，隔夜溢价收窄，当前非理想打板时机。\n【策略建议】收缩打板仓位至2成以下，优选首板与题材龙头，缩短持仓周期。\n【风险提示】高位打板风险极大，务必严格执行止损，隔夜仓不超3成。',
  trend: '【市场解读】均线系统保持多头排列，中期上升趋势未破坏，回调是加仓机会。\n【策略建议】维持7成仓位，回调至均线附近加仓，跌破20日线减仓保护利润。\n【风险提示】趋势破坏风险，若指数有效跌破均线系统需果断降仓。',
  quant: '【市场解读】多因子模型显示成长与动量因子共振向上，波动率处于中等偏低区间。\n【策略建议】因子模型建议8成仓位，成长因子权重略高，等权配置，动态再平衡。\n【风险提示】量化模型存在失效风险，关注因子轮动信号，做好风险对冲。',
}

/**
 * 演示模式批量分析
 * @param {Function} onStep - 回调({agentId, step, message})
 */
export async function demoBatchAnalyze(onStep) {
  const agents = ['jun', 'qiao', 'jia', 'speed', 'trend', 'quant']

  // 阶段一：并行初始化所有 Agent
  if (onStep) onStep({ phase: 'init', message: '正在并行初始化 6 个 Agent...' })
  await new Promise(r => setTimeout(r, 800))

  // 阶段二：并行执行所有 Agent
  const promises = agents.map(async (agentId) => {
    for (let i = 1; i <= 5; i++) {
      await new Promise(r => setTimeout(r, 300))
      if (onStep) onStep({ agentId, phase: 'step', step: i })
    }
    return demoAnalyzeAgent(agentId)
  })

  const agentResults = await Promise.all(promises)

  // 阶段三：计算共识
  if (onStep) onStep({ phase: 'consensus', message: '正在聚合共识信号...' })
  await new Promise(r => setTimeout(r, 600))

  const stances = agentResults.map(r => r.structured?.stance || 'neutral')
  const bullCount = stances.filter(s => s === 'bull').length
  const bearCount = stances.filter(s => s === 'bear').length
  const consensusPct = max(10, min(95, 50 + (bullCount - bearCount) * 10 + 15))

  // TOP 机会
  const allRecs = agentResults.flatMap(r =>
    (r.structured?.recommendedStocks || []).map(s => ({
      ...s, agent: r.agent_name,
    }))
  )
  allRecs.sort((a, b) => b.chg_pct - a.chg_pct)

  const badges = ['龙头共识', '多策略共振', '资金认可']
  const consensusOpportunities = allRecs.slice(0, 3).map((rec, i) => ({
    rank: i + 1,
    title: `${rec.name} (${rec.code})`,
    badge: badges[i] || '机会标的',
    badgeKind: i < 2 ? 'primary' : 'muted',
    meta: `${rec.role} · ${rec.reason?.slice(0, 20)}`,
    chg: rec.chg_pct,
    flowLabel: `来源: ${rec.agent}`,
  }))

  if (!consensusOpportunities.length) {
    consensusOpportunities.push(
      { rank: 1, title: '宁德时代 (300750.SZ)', badge: '龙头共识', badgeKind: 'primary', meta: '主线龙头 · 资金持续流入', chg: 5.8, flowLabel: '来源: 钧哥天下无双' },
      { rank: 2, title: '北方华创 (002371.SZ)', badge: '多策略共振', badgeKind: 'primary', meta: '趋势跟随 · 均线多头排列', chg: 4.2, flowLabel: '来源: 乔帮主' },
      { rank: 3, title: '比亚迪 (002594.SZ)', badge: '资金认可', badgeKind: 'muted', meta: '板块轮动 · 底部放量', chg: 3.1, flowLabel: '来源: 量化之翼' },
    )
  }

  if (onStep) onStep({ phase: 'done' })

  return {
    success: true,
    scan_time: new Date().toISOString(),
    consensus: {
      consensusPct,
      bullCount,
      bearCount,
      neutralCount: stances.length - bullCount - bearCount,
      label: bullCount >= 4 ? '乐观看多' : bearCount >= 3 ? '谨慎防御' : '分化震荡',
      avgConfidence: Math.round(agentResults.reduce((s, r) => s + (r.structured?.confidence || 50), 0) / agentResults.length),
    },
    agentResults,
    consensusOpportunities,
    lastUpdated: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
  }
}

function max(a, b) { return Math.max(a, b) }
function min(a, b) { return Math.min(a, b) }

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
