/**
 * AgentDetailSummary — AI 智能分析报告页（Editorial Intelligence 设计）
 * 路由: /strategy/agents/:id/summary
 * 数据来源: 今日分析记录（/api/agents/:id/analysis/today） + 历史记录（/api/agents/:id/analysis/history）
 */
<template>
  <div class="ads-page">
    <!-- TopAppBar -->
    <header class="ads-header">
      <button type="button" class="ads-header__back" aria-label="返回" @click="goBack">
        <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <div class="ads-header__brand">
        <div class="ads-header__avatar">{{ agentInitial }}</div>
        <div>
          <h1 class="ads-header__title">{{ agentName }}</h1>
          <span class="ads-header__sub">{{ roleSubtitle }}</span>
        </div>
      </div>
      <div class="ads-header__actions">
        <span v-if="isFromHistory" class="ads-history-badge">
          <svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12"><path d="M13 3a9 9 0 0 0-9 9H1l3.89 3.89.07.14L9 12H6a7 7 0 1 1 2.06 4.94l-1.42 1.42A9 9 0 1 0 13 3zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z"/></svg>
          今日记录
        </span>
        <button type="button" class="ads-header__refresh" :disabled="isRunning" @click="rerunAnalysis">
          <svg v-if="isRunning" class="icon ads-spin" viewBox="0 0 24 24" fill="currentColor"><path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46A7.93 7.93 0 0 0 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74A7.93 7.93 0 0 0 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"/></svg>
          <svg v-else class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
        </button>
      </div>
    </header>

    <main class="ads-main">
      <!-- 加载中 -->
      <div v-if="isLoading && !currentRecord" class="ads-loading">
        <div class="ads-loading__spinner" />
        <p class="ads-loading__text">正在加载分析报告…</p>
      </div>

      <!-- 今日市场智能 Hero -->
      <section v-if="currentRecord || isRunning" class="ads-hero">
        <div class="ads-hero__left">
          <p class="ads-hero__label">今日市场智能</p>

          <!-- 信心指数大数字 -->
          <div class="ads-hero__gauge-row">
            <span class="ads-hero__conf-num" :class="stanceColorClass">{{ confidence }}</span>
            <div class="ads-hero__conf-right">
              <span class="ads-hero__conf-pct">%</span>
              <span class="ads-hero__stance-tag" :class="stanceTagClass">{{ stanceLabel }}</span>
            </div>
          </div>

          <p class="ads-hero__commentary">{{ marketCommentary || '市场分析进行中…' }}</p>

          <!-- AI 策略建议 -->
          <div v-if="positionAdvice" class="ads-hero__advice">
            <svg class="ads-hero__advice-ico" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
            {{ positionAdvice }}
          </div>

          <!-- 风险提示 -->
          <div v-if="riskWarning" class="ads-hero__risk">
            <svg class="ads-hero__risk-ico" viewBox="0 0 24 24" fill="currentColor"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>
            {{ riskWarning }}
          </div>

          <!-- 标签 -->
          <div class="ads-hero__chips">
            <span class="ads-chip ads-chip--primary">{{ confidenceLabel }}</span>
            <span v-if="riskWarning" class="ads-chip ads-chip--risk">注意风险</span>
          </div>
        </div>

        <!-- AI 模型建议卡片 -->
        <div class="ads-hero__right">
          <svg class="ads-hero__right-ico" viewBox="0 0 24 24" fill="currentColor"><path d="M7 2v11h3v9l7-12h-4l4-8z"/></svg>
          <p class="ads-hero__right-title">AI 模型建议</p>
          <p class="ads-hero__right-body">{{ positionAdvice || marketCommentary }}</p>
          <p v-if="reportTime" class="ads-hero__right-time">报告时间：{{ reportTime }}</p>
        </div>
      </section>

      <!-- 核心建议个股 -->
      <section v-if="recommendedStocks.length" class="ads-recs">
        <div class="ads-section-header">
          <h3 class="ads-section-title">核心建议个股</h3>
          <span class="ads-section-meta">实时更新</span>
        </div>
        <div class="ads-recs__list">
          <div
            v-for="(s, i) in recommendedStocks"
            :key="s.code || i"
            class="ads-stock-card"
            role="button"
            tabindex="0"
            @click="goStock(s)"
            @keydown.enter.prevent="goStock(s)"
          >
            <div class="ads-stock-card__left">
              <div class="ads-stock-card__avatar">{{ (s.name || '?')[0] }}</div>
              <div class="ads-stock-card__info">
                <p class="ads-stock-card__name">{{ s.name || '未知' }}</p>
                <p class="ads-stock-card__code">{{ s.displayCode || s.code || '' }}</p>
              </div>
            </div>
            <div class="ads-stock-card__right">
              <div class="ads-stock-card__role" :class="'role-' + roleColor(s.role)">{{ s.role || '关注' }}</div>
              <p class="ads-stock-card__reason">{{ s.reason || '' }}</p>
            </div>
            <svg class="ads-stock-card__arrow" viewBox="0 0 24 24" fill="currentColor"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
          </div>
        </div>
      </section>

      <!-- 分析执行日志 -->
      <section class="ads-log-section">
        <div class="ads-section-header">
          <h3 class="ads-section-title">分析执行日志</h3>
          <span class="ads-section-meta">{{ logSteps.length }} 步</span>
        </div>
        <div class="ads-log-card">
          <div class="ads-log-card__track" />
          <div
            v-for="(s, i) in logSteps"
            :key="i"
            class="ads-log-entry"
            :class="{
              'ads-log-entry--done': s.status === 'done',
              'ads-log-entry--active': s.status === 'active',
              'ads-log-entry--error': s.status === 'error',
            }"
          >
            <div class="ads-log-entry__dot">
              <svg v-if="s.status === 'done'" class="ads-log-entry__check" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
              <span v-else-if="s.status === 'active'" class="ads-log-entry__spin" />
            </div>
            <div class="ads-log-entry__content">
              <p class="ads-log-entry__msg">{{ s.message }}</p>
              <p v-if="s.time" class="ads-log-entry__time">{{ s.time }}</p>
            </div>
          </div>
          <div v-if="!logSteps.length && !isRunning" class="ads-log-empty">
            <p>暂无分析日志</p>
          </div>
          <div v-if="isRunning && !logSteps.length" class="ads-log-empty">
            <p>正在启动分析…</p>
          </div>
        </div>
      </section>

      <!-- 历史表现 -->
      <section v-if="historyRecords.length" class="ads-history">
        <div class="ads-section-header">
          <h3 class="ads-section-title">历史表现分析</h3>
        </div>
        <div class="ads-history-card">
          <!-- 表头 -->
          <div class="ads-history-header">
            <span>分析日期</span>
            <span>立场</span>
            <span>信心</span>
            <span class="text-right">执行</span>
          </div>
          <!-- 列表 -->
          <div
            v-for="rec in historyRecords"
            :key="rec.report_date"
            class="ads-history-row"
            role="button"
            tabindex="0"
            @click="loadHistoryRecord(rec)"
            @keydown.enter.prevent="loadHistoryRecord(rec)"
          >
            <span class="ads-history-row__date">{{ rec.report_date }}</span>
            <span class="ads-history-row__stance" :class="stanceClass(rec.stance)">{{ stanceLabelText(rec.stance) }}</span>
            <span class="ads-history-row__conf" :class="stanceClass(rec.stance)">{{ rec.confidence }}%</span>
            <span class="ads-history-row__action text-right">
              <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
            </span>
          </div>
        </div>
      </section>

      <!-- 无数据 -->
      <div v-if="!isLoading && !currentRecord && !isRunning" class="ads-empty">
        <svg class="ads-empty__ico" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>
        <p class="ads-empty__title">暂无今日分析报告</p>
        <p class="ads-empty__sub">点击下方按钮启动 AI 分析</p>
      </div>
    </main>

    <!-- Footer Actions -->
    <div class="ads-footer">
      <div class="ads-footer__inner">
        <button
          type="button"
          class="ads-btn-primary"
          :disabled="isRunning"
          @click="rerunAnalysis"
        >
          <svg v-if="isRunning" class="ads-btn-primary__spinner" viewBox="0 0 24 24" fill="currentColor"><path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46A7.93 7.93 0 0 0 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74A7.93 7.93 0 0 0 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"/></svg>
          <svg v-else class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          {{ isRunning ? '分析中…' : isFromHistory ? '再次分析' : '启动 AI 分析' }}
        </button>
        <button
          type="button"
          class="ads-btn-secondary"
          :disabled="isRunning"
          @click="goFullReport"
        >
          查看完整报告
          <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchTodayAnalysis, analyzeWithAgent } from '@/api/agents.js'

const route = useRoute()
const router = useRouter()

// ── Agent 信息 ─────────────────────────────────────────────────────────
const agentId = computed(() => route.params.id || 'jun')
const agentName = computed(() => _nameMap[agentId.value] || agentId.value)
const roleSubtitle = computed(() => _roleMap[agentId.value] || '')
const agentInitial = computed(() => {
  const n = (currentRecord.value?.structured?.agentName || agentName.value || '').trim()
  for (const ch of n) {
    if (ch && !/\s/.test(ch)) return ch
  }
  return '?'
})

const _nameMap = {
  jun: '钧哥天下无双', qiao: '乔帮主', jia: '炒股养家',
  speed: '极速先锋', trend: '趋势追随者', quant: '量化之翼',
  deepseek: '深度思考者', beijing: '北京炒家',
}
const _roleMap = {
  jun: '龙头战法', qiao: '板块轮动', jia: '低位潜伏',
  speed: '打板专家', trend: '中线波段', quant: '算法回测',
  deepseek: '深度推理', beijing: '游资打板',
}

// ── 状态 ──────────────────────────────────────────────────────────────
const isLoading = ref(true)
const isRunning = ref(false)
const isFromHistory = ref(false) // 当前展示的是历史记录
const currentRecord = ref(null) // 当前展示的分析结果
const historyRecords = ref([])  // 历史列表
const logSteps = ref([])
const reportTime = ref('')

let abortCtrl = null

// ── 生命周期 ──────────────────────────────────────────────────────────
onBeforeUnmount(() => {
  if (abortCtrl) { abortCtrl.abort(); abortCtrl = null }
  isRunning.value = false
})

onMounted(async () => {
  isLoading.value = true
  try {
    // 加载今日记录
    const today = await fetchTodayAnalysis(agentId.value)
    if (today) {
      loadRecord(today)
    }

    // 加载历史记录（最多5条）
    try {
      const res = await fetch(`/api/agents/${agentId.value}/analysis/history?limit=5`)
      const json = await res.json()
      if (json.success && Array.isArray(json.data)) {
        historyRecords.value = json.data
      }
    } catch (e) {
      console.warn('[AgentDetailSummary] 加载历史失败:', e)
    }
  } catch (e) {
    console.warn('[AgentDetailSummary] 加载失败:', e)
  } finally {
    isLoading.value = false
  }
})

// ── 数据加载 ──────────────────────────────────────────────────────────
function loadRecord(record, fromHistory = false) {
  currentRecord.value = record
  isFromHistory.value = fromHistory
  reportTime.value = record.report_time || record.report_date || ''

  // 从 analysis_result 提取 structured
  const ar = record.analysis_result || {}
  const st = ar.structured || {}

  // 构建分析日志
  const steps = []
  const now = new Date()
  const timeStr = (offset = 0) => {
    const d = new Date(now.getTime() - offset)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }
  steps.push({ message: '数据抓取完成', status: 'done', time: timeStr(600) })
  steps.push({ message: '市场情绪分析', status: 'done', time: timeStr(300) })
  steps.push({ message: '板块轮动评估', status: 'done', time: timeStr(200) })
  steps.push({ message: '持仓信号生成', status: 'done', time: timeStr(100) })
  steps.push({ message: '策略建议输出', status: 'done', time: '' })

  // 如果有 thinking 文本，分段合并后替换默认步骤
  const thinking = ar.thinking || record.thinking_text || ''
  if (thinking) {
    const paras = thinking.split('\n').filter(l => l.trim())
    // 合并连续的非【段落，只保留标题行和合并后的正文
    const merged = []
    let buffer = ''
    for (const p of paras) {
      if (p.trim().startsWith('【')) {
        if (buffer) {
          merged.push(buffer.trim())
          buffer = ''
        }
        merged.push(p.trim())
      } else {
        buffer += (buffer ? ' ' : '') + p.trim()
      }
    }
    if (buffer) merged.push(buffer.trim())

    // 用合并后的内容替换默认步骤
    merged.slice(0, 5).forEach((text, i) => {
      if (steps[i]) {
        steps[i].message = text.slice(0, 80)
      }
    })
  }

  logSteps.value = steps
}

function loadHistoryRecord(rec) {
  loadRecord(rec, true)
}

// ── 计算属性 ──────────────────────────────────────────────────────────
const st = computed(() => {
  const ar = currentRecord.value?.analysis_result || {}
  return ar.structured || currentRecord.value?.structured || {}
})

const confidence = computed(() => st.value?.confidence ?? 0)
const stance = computed(() => st.value?.stance || 'neutral')
const marketCommentary = computed(() => st.value?.marketCommentary || '')
const positionAdvice = computed(() => st.value?.positionAdvice || '')
const riskWarning = computed(() => st.value?.riskWarning || '')

const recommendedStocks = computed(() => {
  const raw = st.value?.recommendedStocks ?? []
  return raw.map(normalizeRecRow).filter(Boolean)
})

const confidenceLabel = computed(() => {
  if (confidence.value >= 75) return '高确定性'
  if (confidence.value >= 55) return '中等确定性'
  return '低确定性'
})

const stanceLabel = computed(() => {
  const m = { bull: '看多情绪', bear: '看空情绪', neutral: '中性立场' }
  return m[stance.value] || '中性立场'
})

const stanceColorClass = computed(() => {
  return { bull: 'ads-conf--bull', bear: 'ads-conf--bear', neutral: 'ads-conf--neutral' }[stance.value] || 'ads-conf--neutral'
})

const stanceTagClass = computed(() => {
  return { bull: 'ads-stance-tag--bull', bear: 'ads-stance-tag--bear', neutral: 'ads-stance-tag--neutral' }[stance.value] || 'ads-stance-tag--neutral'
})

function stanceClass(s) {
  if (!s) return ''
  return s === 'bull' ? 'bull' : s === 'bear' ? 'bear' : 'neutral'
}

function stanceLabelText(s) {
  if (!s) return '中性'
  return s === 'bull' ? '看多' : s === 'bear' ? '看空' : '中性'
}

function roleColor(role) {
  if (!role) return 'default'
  if (role.includes('A级') || role.includes('龙头')) return 'a'
  if (role.includes('B级') || role.includes('关注')) return 'b'
  return 'default'
}

function normalizeRecRow(s) {
  if (!s || typeof s !== 'object') return null
  const code = s.code || s.stock_code || ''
  const displayCode = code.replace('.SH', ' · 上证').replace('.SZ', ' · 深证').replace('.BJ', ' · 北证')
  return {
    name: s.name || s.stock_name || '',
    code,
    displayCode,
    role: s.role || '',
    reason: s.reason || '',
    changePct: s.changePct ?? s.chg_pct ?? 0,
    price: s.price || s.current_price || 0,
    sector: s.sector || '',
    routeCode: code.replace(/\.S[HZ]/, '').replace(/\.BJ/, ''),
  }
}

// ── 分析操作 ──────────────────────────────────────────────────────────
async function rerunAnalysis() {
  if (isRunning.value) return
  isRunning.value = true
  isFromHistory.value = false
  currentRecord.value = null
  logSteps.value = []

  abortCtrl = new AbortController()
  const startTime = Date.now()

  const addStep = (msg, status = 'done') => {
    const elapsed = Math.round((Date.now() - startTime) / 1000)
    logSteps.value.push({ message: msg, status, time: `${elapsed}s` })
  }

  try {
    addStep('正在准备市场数据…', 'active')
    const res = await analyzeWithAgent(agentId.value, abortCtrl)
    currentRecord.value = res
    isFromHistory.value = false
    reportTime.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    addStep('分析完成！', 'done')
  } catch (err) {
    console.error('[AgentDetailSummary] 分析失败:', err)
    addStep(`分析失败: ${err.message}`, 'error')
  } finally {
    isRunning.value = false
    abortCtrl = null
  }
}

// ── 导航 ──────────────────────────────────────────────────────────────
function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/strategy/agents')
}

function goStock(s) {
  if (!s.routeCode) return
  router.push({ name: 'StockDetail', params: { code: s.routeCode } })
}

function goFullReport() {
  router.push(`/strategy/agents/${agentId.value}/analysis`)
}
</script>

<style scoped>
/* ── Design Tokens ─────────────────────────────────────────────────── */
.ads-page {
  --primary: #4648d4;
  --primary-container: #6063ee;
  --surface: #f7f9fb;
  --surface-container-low: #f2f4f6;
  --surface-container: #eceef0;
  --surface-container-lowest: #ffffff;
  --on-surface: #191c1e;
  --on-surface-variant: #464554;
  --on-primary: #ffffff;
  --tertiary-container: #00885d;
  --on-tertiary-fixed: #002113;
  --error: #f23645;
  --error-container: #ffdad6;
  --on-error-container: #93000a;
  --outline-variant: #c7c4d7;
  --bull-color: #f23645;
  --bear-color: #089981;

  font-family: 'Inter', var(--font, system-ui, sans-serif);
  background: var(--surface);
  color: var(--on-surface);
  min-height: 100vh;
  min-height: 100dvh;
  padding-bottom: calc(100px + env(safe-area-inset-bottom, 0));
}

/* ── Header ─────────────────────────────────────────────────────────── */
.ads-header {
  position: sticky;
  top: 0;
  z-index: 50;
  display: grid;
  grid-template-columns: 44px 1fr auto;
  align-items: center;
  gap: 8px;
  padding: calc(12px + env(safe-area-inset-top, 0)) 12px 12px;
  background: rgba(247, 249, 251, 0.88);
  backdrop-filter: blur(16px);
  box-shadow: 0 1px 0 rgba(193, 198, 215, 0.15);
}

.ads-header__back {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: var(--primary);
}
.ads-header__back:active { background: rgba(74, 71, 210, 0.08); }

.ads-header__brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ads-header__avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--primary), var(--primary-container));
  color: var(--on-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 16px;
}

.ads-header__title {
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 16px;
  color: var(--on-surface);
  margin: 0;
}

.ads-header__sub {
  font-size: 11px;
  color: var(--on-surface-variant);
}

.ads-header__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ads-header__refresh {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: var(--on-surface-variant);
}
.ads-header__refresh:active { background: rgba(0,0,0,0.05); }

.ads-history-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 20px;
  background: rgba(70, 72, 212, 0.1);
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
  border: 1px solid rgba(70, 72, 212, 0.2);
}

/* ── Main ────────────────────────────────────────────────────────────── */
.ads-main {
  max-width: 680px;
  margin: 0 auto;
  padding: 24px 16px 0;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* ── Loading ─────────────────────────────────────────────────────────── */
.ads-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 60px 0;
}
.ads-loading__spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--surface-container);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: ads-spin 0.8s linear infinite;
}
.ads-loading__text {
  font-size: 14px;
  color: var(--on-surface-variant);
}
@keyframes ads-spin {
  to { transform: rotate(360deg); }
}
.ads-spin { animation: ads-spin 1s linear infinite; }

/* ── Hero ────────────────────────────────────────────────────────────── */
@media (max-width: 480px) {
  .ads-hero {
    grid-template-columns: 1fr;
    min-height: auto;
  }
  .ads-hero__right {
    width: 100%;
    flex-direction: row;
    align-items: center;
    padding: 16px 20px;
    border-radius: 0;
  }
  .ads-hero__right::before {
    display: none;
  }
  .ads-hero__right-ico { font-size: 20px; }
  .ads-hero__right-body { display: none; }
}

.ads-hero {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0;
  background: var(--surface-container-lowest);
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(70, 72, 212, 0.06);
  min-height: 240px;
  position: relative;
}

.ads-hero__left {
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 1;
  min-width: 0;
}

.ads-hero__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--on-surface-variant);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin: 0;
}

.ads-hero__gauge-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.ads-hero__conf-num {
  font-family: 'Manrope', sans-serif;
  font-weight: 800;
  font-size: 56px;
  line-height: 1;
  letter-spacing: -0.03em;
}
@media (max-width: 400px) {
  .ads-hero__conf-num { font-size: 44px; }
}
.ads-hero__conf-num.ads-conf--bull { color: var(--bull-color); }
.ads-hero__conf-num.ads-conf--bear { color: var(--bear-color); }
.ads-hero__conf-num.ads-conf--neutral { color: var(--on-surface); }

.ads-hero__conf-right {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-bottom: 8px;
}

.ads-hero__conf-pct {
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 22px;
  color: var(--on-surface-variant);
}

.ads-stance-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
}
.ads-stance-tag--bull { background: rgba(242, 54, 69, 0.12); color: var(--bull-color); }
.ads-stance-tag--bear { background: rgba(8, 153, 129, 0.12); color: var(--bear-color); }
.ads-stance-tag--neutral { background: var(--surface-container-low); color: var(--on-surface-variant); }

.ads-hero__commentary {
  font-size: 14px;
  color: var(--on-surface-variant);
  line-height: 1.6;
  max-width: 320px;
  margin: 0;
}

.ads-hero__advice {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--on-surface);
  line-height: 1.5;
}
.ads-hero__advice-ico {
  flex-shrink: 0;
  color: var(--tertiary-container);
  margin-top: 2px;
}

.ads-hero__risk {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
  color: var(--on-error-container);
  background: var(--error-container);
  padding: 8px 10px;
  border-radius: 12px;
  line-height: 1.5;
}
.ads-hero__risk-ico { flex-shrink: 0; margin-top: 1px; }

.ads-hero__chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ads-chip {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
}
.ads-chip--primary { background: rgba(70, 72, 212, 0.1); color: var(--primary); }
.ads-chip--risk { background: var(--error-container); color: var(--on-error-container); }

/* Hero 右侧卡片 */
.ads-hero__right {
  width: 160px;
  padding: 24px 20px;
  background: linear-gradient(160deg, var(--primary), var(--primary-container));
  color: var(--on-primary);
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  position: relative;
  overflow: hidden;
  flex-shrink: 0;
}
.ads-hero__right::before {
  content: '';
  position: absolute;
  right: -30px;
  bottom: -30px;
  width: 100px;
  height: 100px;
  background: rgba(255,255,255,0.08);
  border-radius: 50%;
}
.ads-hero__right-ico {
  font-size: 28px;
  opacity: 0.9;
}
.ads-hero__right-title {
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 15px;
  margin: 0;
}
.ads-hero__right-body {
  font-size: 12px;
  opacity: 0.8;
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ads-hero__right-time {
  font-size: 10px;
  opacity: 0.6;
  margin: 0;
}

/* ── Section Header ──────────────────────────────────────────────────── */
.ads-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.ads-section-title {
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 18px;
  color: var(--on-surface);
  margin: 0;
}
.ads-section-meta {
  font-size: 11px;
  color: var(--on-surface-variant);
  font-weight: 500;
}

/* ── 推荐个股 ────────────────────────────────────────────────────────── */
.ads-recs__list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ads-stock-card {
  background: var(--surface-container-lowest);
  border-radius: 20px;
  padding: 18px 16px;
  display: grid;
  grid-template-columns: 1fr auto 20px;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  transition: box-shadow 0.2s;
  box-shadow: 0 2px 12px rgba(70, 72, 212, 0.05);
}
.ads-stock-card:active { box-shadow: 0 1px 6px rgba(70, 72, 212, 0.08); }

.ads-stock-card__left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ads-stock-card__avatar {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: var(--surface-container-low);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 18px;
  color: var(--primary);
  flex-shrink: 0;
}

.ads-stock-card__info {
  min-width: 80px;
}
.ads-stock-card__name {
  font-weight: 600;
  font-size: 15px;
  color: var(--on-surface);
  margin: 0 0 2px;
  line-height: 1.3;
}
.ads-stock-card__code {
  font-size: 11px;
  color: var(--on-surface-variant);
  margin: 0;
  line-height: 1.3;
}

.ads-stock-card__right {
  text-align: right;
}
.ads-stock-card__role {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  margin-bottom: 4px;
  background: rgba(70, 72, 212, 0.1);
  color: var(--primary);
}
.ads-stock-card__role.role-a { background: rgba(242, 54, 69, 0.1); color: var(--bull-color); }
.ads-stock-card__role.role-b { background: rgba(70, 72, 212, 0.08); color: var(--primary); }
.ads-stock-card__reason {
  font-size: 11px;
  color: var(--on-surface-variant);
  margin: 0;
  max-width: 160px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ads-stock-card__arrow {
  color: var(--outline-variant);
  flex-shrink: 0;
}

/* ── 执行日志 ────────────────────────────────────────────────────────── */
.ads-log-card {
  background: var(--surface-container-lowest);
  border-radius: 20px;
  padding: 24px;
  position: relative;
}

.ads-log-card__track {
  position: absolute;
  left: 29px;
  top: 28px;
  bottom: 28px;
  width: 1px;
  background: var(--outline-variant);
  opacity: 0.3;
}

.ads-log-entry {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding-bottom: 20px;
  position: relative;
}
.ads-log-entry:last-child { padding-bottom: 0; }

.ads-log-entry__dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--surface-container-low);
  border: 2px solid var(--outline-variant);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  z-index: 1;
}
.ads-log-entry--done .ads-log-entry__dot {
  background: var(--tertiary-container);
  border-color: var(--tertiary-container);
}
.ads-log-entry--active .ads-log-entry__dot {
  background: var(--primary);
  border-color: var(--primary);
  animation: ads-pulse 1.5s ease-in-out infinite;
}
.ads-log-entry--error .ads-log-entry__dot {
  background: var(--error-container);
  border-color: var(--error-container);
}

@keyframes ads-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(0.85); }
}

.ads-log-entry__check {
  width: 10px;
  height: 10px;
  color: var(--on-tertiary-fixed);
}
.ads-log-entry__spin {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--on-primary);
  animation: ads-spin 0.8s linear infinite;
}

.ads-log-entry__content {}
.ads-log-entry__msg {
  font-size: 14px;
  font-weight: 500;
  color: var(--on-surface);
  margin: 0 0 2px;
}
.ads-log-entry--error .ads-log-entry__msg { color: var(--on-error-container); }
.ads-log-entry__time {
  font-size: 11px;
  color: var(--on-surface-variant);
  font-variant-numeric: tabular-nums;
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.ads-log-empty {
  text-align: center;
  padding: 20px 0;
}
.ads-log-empty p {
  font-size: 13px;
  color: var(--on-surface-variant);
  margin: 0;
}

/* ── 历史表现 ────────────────────────────────────────────────────────── */
.ads-history-card {
  background: var(--surface-container-lowest);
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(70, 72, 212, 0.05);
}

.ads-history-header {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 40px;
  padding: 12px 20px;
  background: var(--surface-container);
  font-size: 10px;
  font-weight: 700;
  color: var(--on-surface-variant);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.ads-history-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 40px;
  padding: 16px 20px;
  align-items: center;
  cursor: pointer;
  transition: background 0.15s;
}
.ads-history-row:active { background: var(--surface-container-low); }
.ads-history-row + .ads-history-row {
  border-top: 1px solid var(--outline-variant);
  opacity: 0.08;
}

.ads-history-row__date {
  font-size: 14px;
  font-weight: 500;
  color: var(--on-surface);
}
.ads-history-row__stance {
  font-size: 14px;
  font-weight: 700;
}
.ads-history-row__conf {
  font-size: 14px;
  font-weight: 700;
}
.ads-history-row__stance.bull, .ads-history-row__conf.bull { color: var(--bull-color); }
.ads-history-row__stance.bear, .ads-history-row__conf.bear { color: var(--bear-color); }
.ads-history-row__stance.neutral, .ads-history-row__conf.neutral { color: var(--on-surface-variant); }

.ads-history-row__action {
  display: flex;
  justify-content: flex-end;
  color: var(--outline-variant);
}

/* ── 空状态 ─────────────────────────────────────────────────────────── */
.ads-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
}
.ads-empty__ico {
  font-size: 48px;
  color: var(--outline-variant);
}
.ads-empty__title {
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 18px;
  color: var(--on-surface);
  margin: 0;
}
.ads-empty__sub {
  font-size: 13px;
  color: var(--on-surface-variant);
  margin: 0;
}

/* ── Footer ──────────────────────────────────────────────────────────── */
.ads-footer {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 40;
  padding: 12px 16px calc(12px + env(safe-area-inset-bottom, 0));
  background: rgba(247, 249, 251, 0.9);
  backdrop-filter: blur(16px);
}

.ads-footer__inner {
  max-width: 680px;
  margin: 0 auto;
  display: flex;
  gap: 12px;
}

.ads-btn-primary {
  flex: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px 20px;
  background: linear-gradient(160deg, var(--primary), var(--primary-container));
  color: var(--on-primary);
  border: none;
  border-radius: 16px;
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 15px;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(70, 72, 212, 0.25);
  transition: opacity 0.2s, transform 0.15s;
}
.ads-btn-primary:active:not(:disabled) { transform: scale(0.98); opacity: 0.9; }
.ads-btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.ads-btn-primary__spinner {
  width: 18px;
  height: 18px;
  animation: ads-spin 0.8s linear infinite;
}

.ads-btn-secondary {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 16px 16px;
  background: var(--surface-container-lowest);
  color: var(--on-surface-variant);
  border: none;
  border-radius: 16px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  transition: transform 0.15s;
}
.ads-btn-secondary:active:not(:disabled) { transform: scale(0.98); }
.ads-btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
