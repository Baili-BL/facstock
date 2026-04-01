<template>
  <div class="aa-page">
    <!-- 顶栏 -->
    <header class="aa-header">
      <button type="button" class="aa-back" aria-label="返回" @click="goBack">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <div class="aa-header__brand">
        <img
          src="https://lh3.googleusercontent.com/aida-public/AB6AXuD97zD2NIGTCO_1tiXq1wsbA98aL5lltkwfWvGuW5ykcn7zacGqWOfQaC0Cgqq8Y70ssQbZDu4WTh34HYBodcl31NA-stzpx7g9dxTWCMuzM7s7gcIOeZVI8i8nHPZnB0F4J3ToG2bh9x5rvE7Qe3qAnETQRHznWRcVuYltPv923yduEQvww9hwsCd_YcKQjJrZK_VVNT5V0-w_9fQ5GDMZ9eGfWPxUPX4PFFDFtZaCN0EpwpuQSgMG_xOxIR3Btmz_rneBA88VIGp0"
          alt="钧哥天下无双"
          class="aa-header__avatar"
          loading="lazy"
        />
        <div>
          <h1 class="aa-header__title">钧哥天下无双</h1>
          <span class="aa-header__sub">龙头战法 · 布林带收缩</span>
        </div>
      </div>
      <div class="aa-header__right">
        <span
          class="aa-status-badge"
          :class="{
            'aa-status-badge--running': isRunning,
            'aa-status-badge--done': isDone,
          }"
        >
          <span v-if="isRunning" class="aa-status-badge__dot aa-status-badge__dot--spin" />
          <span v-else-if="isDone" class="aa-status-badge__dot" />
          {{ isRunning ? '扫描中' : isDone ? '已完成' : '待启动' }}
        </span>
      </div>
    </header>

    <main class="aa-main">
      <!-- 进度总览 -->
      <section class="aa-progress-card">
        <div class="aa-progress__meta">
          <span class="aa-kicker">扫描进度</span>
          <span class="aa-progress__pct">{{ progressPct }}%</span>
        </div>
        <div class="aa-progress__bar">
          <div
            class="aa-progress__fill"
            :style="{ width: progressPct + '%' }"
            :class="{ 'aa-progress__fill--done': isDone }"
          />
        </div>
        <p class="aa-progress__hint">
          {{ isRunning ? currentStepMsg : isDone ? '扫描完成，以下是结果' : '点击下方按钮启动每日扫描' }}
        </p>
      </section>

      <!-- 步骤日志 -->
      <section class="aa-log-card">
        <div class="aa-log__head">
          <svg class="icon aa-log__ico" aria-hidden="true"><use href="#icon-ai" /></svg>
          <h2 class="aa-log__title">扫描日志</h2>
          <span class="aa-log__count">{{ steps.length }} 步</span>
        </div>
        <div class="aa-log__body" ref="logEl">
          <div
            v-for="(s, i) in steps"
            :key="i"
            class="aa-log-entry"
            :class="{
              'aa-log-entry--done': s.status === 'done',
              'aa-log-entry--active': s.status === 'active',
              'aa-log-entry--error': s.status === 'error',
            }"
          >
            <span class="aa-log-entry__dot" />
            <span class="aa-log-entry__time">{{ s.time }}</span>
            <span class="aa-log-entry__msg">{{ s.message }}</span>
          </div>
          <div v-if="!steps.length" class="aa-log-empty">
            尚未开始扫描，等待启动…
          </div>
        </div>
      </section>

      <!-- 扫描结果（完成后展示） -->
      <template v-if="isDone && scanData">
        <!-- 市场环境 -->
        <section class="aa-market-card">
          <div class="aa-market__head">
            <svg class="icon" aria-hidden="true"><use href="#icon-ai" /></svg>
            <h2 class="aa-market__title">市场环境</h2>
            <span class="aa-market__mode">{{ scanModeLabel }}</span>
          </div>
          <div class="aa-market__indices">
            <div
              v-for="(info, name) in indexData"
              :key="name"
              class="aa-index-item"
            >
              <span class="aa-index-item__name">{{ name }}</span>
              <span
                class="aa-index-item__chg"
                :class="info.change >= 0 ? 'up' : 'down'"
              >
                {{ info.change >= 0 ? '+' : '' }}{{ info.change.toFixed(2) }}%
              </span>
            </div>
          </div>
          <p class="aa-market__condition">
            <span class="aa-condition-tag" :class="marketBullish ? 'bull' : 'bear'">
              {{ marketCondition }}
            </span>
          </p>
        </section>

        <!-- 热点板块 -->
        <section v-if="hotSectors.length" class="aa-sectors-card">
          <div class="aa-sectors__head">
            <svg class="icon" aria-hidden="true"><use href="#icon-ai" /></svg>
            <h2 class="aa-sectors__title">热点板块</h2>
            <span class="aa-sectors__count">{{ hotSectors.length }} 个</span>
          </div>
          <div class="aa-sectors__chips">
            <span
              v-for="s in hotSectors"
              :key="s.name"
              class="aa-sector-chip"
              :class="s.change >= 0 ? 'up' : 'down'"
            >
              {{ s.name }}
              <span class="aa-sector-chip__chg">{{ s.change >= 0 ? '+' : '' }}{{ s.change }}%</span>
            </span>
          </div>
        </section>

        <!-- 评级统计 -->
        <section class="aa-stats-card">
          <div class="aa-stats__head">
            <svg class="icon" aria-hidden="true"><use href="#icon-ai" /></svg>
            <h2 class="aa-stats__title">扫描统计</h2>
          </div>
          <div class="aa-stats__grid">
            <div class="aa-stat-item">
              <span class="aa-stat-item__val">{{ stats.totalCandidates }}</span>
              <span class="aa-stat-item__lbl">候选股票</span>
            </div>
            <div class="aa-stat-item aa-stat-item--s">
              <span class="aa-stat-item__val">{{ stats.gradeS || 0 }}</span>
              <span class="aa-stat-item__lbl">S 级</span>
            </div>
            <div class="aa-stat-item aa-stat-item--a">
              <span class="aa-stat-item__val">{{ stats.gradeA || 0 }}</span>
              <span class="aa-stat-item__lbl">A 级</span>
            </div>
            <div class="aa-stat-item aa-stat-item--b">
              <span class="aa-stat-item__val">{{ stats.gradeB || 0 }}</span>
              <span class="aa-stat-item__lbl">B 级</span>
            </div>
            <div class="aa-stat-item aa-stat-item--leader">
              <span class="aa-stat-item__val">{{ stats.leaders || 0 }}</span>
              <span class="aa-stat-item__lbl">板块中军</span>
            </div>
          </div>
          <div class="aa-stats__elapsed">
            扫描耗时 {{ scanData.elapsedSeconds }}s
          </div>
        </section>

        <!-- 精选推荐 -->
        <section v-if="recommendations.length" class="aa-recs-card">
          <h2 class="aa-recs__title">
            <svg class="icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
            技术选股精选
          </h2>
          <div class="aa-recs__list">
            <div
              v-for="(s, i) in recommendations"
              :key="s.code"
              class="aa-rec-item"
            >
              <div class="aa-rec-item__left">
                <span class="aa-rec-item__rank">{{ i + 1 }}</span>
                <div>
                  <p class="aa-rec-item__name">{{ s.name }}</p>
                  <p class="aa-rec-item__code">{{ s.code }}</p>
                </div>
              </div>
              <div class="aa-rec-item__mid">
                <span
                  class="aa-grade-badge"
                  :class="'grade-' + s.grade"
                >{{ s.grade }}</span>
                <span class="aa-rec-item__sector">{{ s.sector }}</span>
              </div>
              <div class="aa-rec-item__right">
                <div class="aa-rec-item__tags">
                  <span
                    v-for="tag in s.tags.slice(0, 3)"
                    :key="tag"
                    class="aa-tag"
                  >{{ tag }}</span>
                </div>
                <p class="aa-rec-item__reason">{{ s.reason }}</p>
                <div class="aa-rec-item__advice">
                  <span>买：{{ s.buyRange }}</span>
                  <span class="aa-rec-item__stop">止：{{ s.stopLoss }}</span>
                </div>
              </div>
              <span
                class="aa-rec-item__chg"
                :class="s.changePct >= 0 ? 'up' : 'down'"
              >
                {{ s.changePct >= 0 ? '+' : '' }}{{ s.changePct }}%
              </span>
            </div>
          </div>
        </section>

        <!-- AI 增强分析（AgentOutput 格式） -->
        <template v-if="agentResult && agentResult.success">
          <!-- 共识标尺 -->
          <section class="aa-consensus-card">
            <div class="aa-consensus__left">
              <div class="aa-consensus__gauge">
                <svg viewBox="0 0 96 96" class="aa-consensus__svg">
                  <circle cx="48" cy="48" r="40" fill="none" stroke-width="8" stroke="var(--track)" />
                  <circle
                    cx="48" cy="48" r="40"
                    fill="none"
                    stroke-width="8"
                    stroke-linecap="round"
                    :stroke="stanceColor"
                    :stroke-dasharray="gaugeCirc"
                    :stroke-dashoffset="gaugeOffset"
                    transform="rotate(-90 48 48)"
                    class="aa-consensus__arc"
                  />
                  <text x="48" y="44" text-anchor="middle" class="aa-consensus__num">{{ confidence }}</text>
                  <text x="48" y="58" text-anchor="middle" class="aa-consensus__unit">%</text>
                </svg>
              </div>
            </div>
            <div class="aa-consensus__right">
              <div class="aa-consensus__stance-row">
                <span
                  class="aa-stance-tag"
                  :class="'aa-stance-tag--' + (structured?.stance || 'neutral')"
                >
                  {{ stanceLabel }}
                </span>
                <span class="aa-consensus__conf-label">AI 信心 {{ confidence }}%</span>
              </div>
              <p class="aa-consensus__comm">
                {{ structured?.marketCommentary || '' }}
              </p>
              <div class="aa-consensus__advice">
                <strong>策略建议：</strong>{{ structured?.positionAdvice || '' }}
              </div>
              <div v-if="structured?.riskWarning" class="aa-consensus__warning">
                <span class="aa-warn-ico" aria-hidden="true">⚠</span>
                {{ structured.riskWarning }}
              </div>
            </div>
          </section>

          <!-- AI 推荐股票 -->
          <section v-if="aiRecommendedStocks.length" class="aa-recs-card">
            <h2 class="aa-recs__title">
              <svg class="icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
              AI 精选推荐
            </h2>
            <div class="aa-recs__list">
              <div
                v-for="(s, i) in aiRecommendedStocks"
                :key="s.code || i"
                class="aa-rec-item"
              >
                <div class="aa-rec-item__left">
                  <span class="aa-rec-item__rank">{{ i + 1 }}</span>
                  <div>
                    <p class="aa-rec-item__name">{{ s.name }}</p>
                    <p class="aa-rec-item__code">{{ s.code }}</p>
                  </div>
                </div>
                <div class="aa-rec-item__mid">
                  <span
                    class="aa-grade-badge"
                    :class="'grade-' + s.grade"
                  >{{ s.grade }}</span>
                  <span class="aa-rec-item__sector">{{ s.sector }}</span>
                </div>
                <div class="aa-rec-item__right">
                  <div v-if="s.adviseType" class="aa-advise-type">{{ s.adviseType }}</div>
                  <p v-if="s.signal" class="aa-rec-item__reason">{{ s.signal }}</p>
                  <div v-if="s.buyRange || s.stopLoss" class="aa-rec-item__advice">
                    <span v-if="s.buyRange">买：{{ s.buyRange }}</span>
                    <span v-if="s.stopLoss" class="aa-rec-item__stop">止：{{ s.stopLoss }}</span>
                  </div>
                </div>
                <span
                  class="aa-rec-item__chg"
                  :class="(s.changePct || 0) >= 0 ? 'up' : 'down'"
                >
                  {{ (s.changePct || 0) >= 0 ? '+' : '' }}{{ s.changePct || 0 }}%
                </span>
              </div>
            </div>
          </section>

          <!-- 完整 AI 分析报告 -->
          <section class="aa-analysis-card">
            <div class="aa-analysis-card__head">
              <svg class="icon" aria-hidden="true"><use href="#icon-ai" /></svg>
              <h2 class="aa-analysis-card__title">AI 分析报告</h2>
            </div>
            <div class="aa-analysis-card__body">
              <template v-for="(para, i) in analysisParagraphs" :key="i">
                <p v-if="para" class="aa-analysis-para" :class="{ 'aa-analysis-para--section': para.startsWith('【') }">
                  {{ para }}
                </p>
              </template>
            </div>
          </section>
        </template>
      </template>

      <!-- 操作区 -->
      <div class="aa-actions">
        <button
          type="button"
          class="aa-btn-run"
          :class="{ 'aa-btn-run--running': isRunning }"
          :disabled="isRunning"
          @click="runScan"
        >
          <span v-if="isRunning" class="aa-btn-run__spinner" />
          <svg v-else class="icon aa-btn-run__ico" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          {{ isRunning ? '扫描中…' : '启动每日扫描' }}
        </button>
        <button
          v-if="isDone"
          type="button"
          class="aa-btn-reset"
          @click="resetScan"
        >
          重新扫描
        </button>
      </div>

      <!-- Prompt 预览（可展开） -->
      <details class="aa-prompt-panel">
        <summary class="aa-prompt-panel__toggle">
          <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/></svg>
          查看 JunGe 配置
        </summary>
        <div class="aa-prompt-panel__body">
          <div class="aa-prompt-section">
            <h4 class="aa-prompt-label">扫描参数</h4>
            <pre class="aa-prompt-code">热点板块: {{ params.sectors }} 个
AI 增强: {{ params.enhance ? '启用' : '禁用' }}
连续收缩天数阈值: 3 天
布林带极度收缩阈值: 带宽 < 5%
放量阈值: 量比 > 1.2</pre>
          </div>
          <div class="aa-prompt-section">
            <h4 class="aa-prompt-label">策略说明</h4>
            <pre class="aa-prompt-code">钧哥天下无双 - 龙头战法专家
核心理念：布林带极度收缩是主力蓄力的标志，配合放量是关键启动信号。
优先级：政策利好 > 布林带收缩 > 量价配合 > 资金流向（CMF）</pre>
          </div>
        </div>
      </details>

      <p class="aa-footnote">AI 分析结果仅供参考，不构成投资建议。模型基于历史数据与公开信息生成，存在局限性。</p>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  runJungeScan,
} from '@/api/agents.js'

const router = useRouter()

// ── 状态 ────────────────────────────────────────────────────────────────
const steps = ref([])
const isRunning = ref(false)
const isDone = ref(false)
const scanData = ref(null)
const logEl = ref(null)
const params = ref({ sectors: 5, enhance: true })

// ── 计算属性 ────────────────────────────────────────────────────────────────
const agentResult = computed(() => scanData.value?.agentResult)
const structured = computed(() => agentResult.value?.structured || scanData.value?.structured)
const recommendations = computed(() => scanData.value?.recommendations || [])
const hotSectors = computed(() => scanData.value?.hotSectors || [])
const stats = computed(() => scanData.value?.stats || {})
const indexData = computed(() => scanData.value?.market?.indexData || {})
const marketCondition = computed(() => scanData.value?.market?.condition?.status || '未知')
const marketBullish = computed(() => scanData.value?.market?.condition?.bullish || false)
const scanModeLabel = computed(() => {
  const m = scanData.value?.scanMode
  return m === 'hot_sectors' ? '热点板块' : m === 'fallback' ? '全市场降级' : '未知'
})

const confidence = computed(() => structured.value?.confidence ?? 0)
const aiRecommendedStocks = computed(() => structured.value?.recommendedStocks ?? [])

const progressPct = computed(() => {
  if (!isRunning.value && !isDone.value) return 0
  if (isDone.value) return 100
  const maxStep = steps.value.length
  if (!maxStep) return 0
  const active = steps.value.find(s => s.status === 'active')
  if (!active) return Math.round((maxStep / (maxStep + 1)) * 100)
  return Math.round(((active.step - 1) / (maxStep + 1)) * 100)
})

const currentStepMsg = computed(() => {
  const active = steps.value.find(s => s.status === 'active')
  return active?.message || '初始化中...'
})

const stanceLabel = computed(() => {
  const m = { bull: '看多', bear: '看空', neutral: '中性' }
  return m[structured.value?.stance] || '中性'
})

const stanceColor = computed(() => {
  const m = { bull: '#f23645', bear: '#089981', neutral: '#717786' }
  return m[structured.value?.stance] || '#717786'
})

const gaugeR = 40
const gaugeCirc = computed(() => 2 * Math.PI * gaugeR)
const gaugeOffset = computed(() => gaugeCirc.value * (1 - confidence.value / 100))

const analysisParagraphs = computed(() => {
  const text = agentResult.value?.analysis || ''
  return text.split('\n').filter(l => l.trim())
})

// ── 工具函数 ────────────────────────────────────────────────────────────────
function addStep(step, message, status = 'done') {
  const now = new Date()
  const time = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  const existing = steps.value.find(s => s.step === step)
  if (existing) {
    existing.status = status
    existing.message = message
  } else {
    steps.value.push({ step, message, status, time })
  }
  if (status === 'done' && step < 7) {
    addStep(step + 1, _stepMessages[step + 1] || '处理中...', 'active')
  }
  scrollLog()
}

const _stepMessages = {
  1: '正在获取大盘环境...',
  2: '正在获取热点板块...',
  3: '正在扫描板块成分股...',
  4: '正在计算技术指标...',
  5: '正在汇总排序...',
  6: '正在调用 AI 增强分析...',
  7: '扫描完成！',
}

function scrollLog() {
  nextTick(() => {
    if (logEl.value) {
      logEl.value.scrollTop = logEl.value.scrollHeight
    }
  })
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/strategy/agents')
}

// ── 扫描执行 ────────────────────────────────────────────────────────────────
async function runScan() {
  if (isRunning.value) return
  isRunning.value = true
  isDone.value = false
  scanData.value = null
  steps.value = []

  try {
    addStep(1, _stepMessages[1], 'active')
    addStep(2, _stepMessages[2], 'done')
    addStep(3, `正在扫描 ${params.value.sectors} 个热点板块...`, 'active')

    const res = await runJungeScan({ sectors: params.value.sectors, enhance: params.value.enhance })

    addStep(4, '正在计算技术指标...', 'done')
    addStep(5, '正在汇总排序...', 'done')
    addStep(6, '正在生成分析结果...', 'done')

    scanData.value = res.data
    addStep(7, '扫描完成！', 'done')
    isDone.value = true

  } catch (err) {
    console.error('[JunGeTrader] 扫描失败:', err)
    addStep(0, `扫描失败: ${err.message}`, 'error')
  } finally {
    isRunning.value = false
  }
}

function resetScan() {
  steps.value = []
  isRunning.value = false
  isDone.value = false
  scanData.value = null
}
</script>

<style scoped>
/* ── 复用的 AgentAnalysis 样式（确保风格一致） ────────────────────────── */
.aa-page {
  --primary: #4a47d2;
  --primary-mid: #6462ec;
  --on-surface: #1a1c1f;
  --on-var: #414755;
  --surface: #f9f9fe;
  --low: #f3f3f8;
  --high: #e8e8ed;
  --white: #ffffff;
  --up: #f23645;
  --chip-bg: rgba(242, 54, 69, 0.16);
  --chip-on: #7f1d1d;
  --down: #089981;
  --track: #ededf2;
  --line: rgba(193, 198, 215, 0.15);

  min-height: 100vh;
  min-height: 100dvh;
  background: var(--surface);
  color: var(--on-surface);
  padding-bottom: calc(88px + env(safe-area-inset-bottom, 0));
  font-family: 'Inter', var(--font, system-ui, sans-serif);
  -webkit-font-smoothing: antialiased;
}

/* Header */
.aa-header {
  position: sticky;
  top: 0;
  z-index: 40;
  display: grid;
  grid-template-columns: 44px 1fr auto;
  align-items: center;
  gap: 8px;
  padding: calc(12px + env(safe-area-inset-top, 0)) 12px 12px;
  background: rgba(249, 249, 254, 0.88);
  backdrop-filter: blur(16px);
  box-shadow: 0 1px 0 var(--line);
}
.aa-back {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: var(--primary);
}
.aa-back:active { background: rgba(74, 71, 210, 0.08); }
.aa-header__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.aa-header__avatar {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  object-fit: cover;
  flex-shrink: 0;
  background: var(--low);
}
.aa-header__title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.aa-header__sub {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--primary);
}
.aa-header__right { display: flex; align-items: center; }

/* Status badge */
.aa-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  background: var(--low);
  color: var(--on-var);
}
.aa-status-badge--running {
  background: rgba(74, 71, 210, 0.1);
  color: var(--primary);
}
.aa-status-badge--done {
  background: rgba(0, 107, 27, 0.1);
  color: var(--up);
}
.aa-status-badge__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.aa-status-badge__dot--spin {
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Main */
.aa-main {
  max-width: 720px;
  margin: 0 auto;
  padding: 12px 16px 28px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Progress card */
.aa-progress-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 16px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.aa-progress__meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.aa-kicker {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--on-var);
}
.aa-progress__pct {
  font-size: 1.25rem;
  font-weight: 900;
  letter-spacing: -0.03em;
  color: var(--on-surface);
}
.aa-progress__bar {
  height: 6px;
  border-radius: 3px;
  background: var(--track);
  overflow: hidden;
}
.aa-progress__fill {
  height: 100%;
  border-radius: 3px;
  background: var(--primary);
  transition: width 0.3s ease;
}
.aa-progress__fill--done { background: var(--up); }
.aa-progress__hint {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--on-var);
}

/* Log card */
.aa-log-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.aa-log__head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 10px;
}
.aa-log__ico { color: var(--primary); }
.aa-log__title {
  font-size: 13px;
  font-weight: 700;
  flex: 1;
}
.aa-log__count {
  font-size: 11px;
  color: var(--on-var);
  background: var(--low);
  padding: 2px 8px;
  border-radius: 999px;
}
.aa-log__body {
  max-height: 200px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  scrollbar-width: thin;
}
.aa-log__body::-webkit-scrollbar { width: 4px; }
.aa-log__body::-webkit-scrollbar-thumb { background: var(--high); border-radius: 2px; }
.aa-log-empty {
  font-size: 13px;
  color: var(--on-var);
  text-align: center;
  padding: 12px;
}
.aa-log-entry {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12.5px;
  color: var(--on-var);
}
.aa-log-entry__dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--high);
  flex-shrink: 0;
  margin-top: 1px;
}
.aa-log-entry--done .aa-log-entry__dot { background: var(--up); }
.aa-log-entry--active .aa-log-entry__dot { background: var(--primary); animation: pulse 1s ease infinite; }
.aa-log-entry--error .aa-log-entry__dot { background: var(--down); }
.aa-log-entry--error { color: var(--down); }
.aa-log-entry--active { color: var(--primary); font-weight: 600; }
.aa-log-entry__time {
  font-size: 11px;
  color: var(--on-var);
  flex-shrink: 0;
  opacity: 0.7;
}
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

/* Market card */
.aa-market-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.aa-market__head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 10px;
}
.aa-market__title {
  font-size: 13px;
  font-weight: 700;
  flex: 1;
}
.aa-market__mode {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(74, 71, 210, 0.1);
  color: var(--primary);
}
.aa-market__indices {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.aa-index-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6px 12px;
  border-radius: 10px;
  background: var(--low);
  min-width: 80px;
}
.aa-index-item__name {
  font-size: 10px;
  color: var(--on-var);
  font-weight: 600;
}
.aa-index-item__chg {
  font-size: 14px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.aa-index-item__chg.up { color: var(--up); }
.aa-index-item__chg.down { color: var(--down); }
.aa-market__condition {
  margin: 10px 0 0;
  display: flex;
  align-items: center;
}
.aa-condition-tag {
  font-size: 12px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 999px;
}
.aa-condition-tag.bull {
  background: rgba(242, 54, 69, 0.1);
  color: var(--up);
}
.aa-condition-tag.bear {
  background: rgba(8, 153, 129, 0.1);
  color: var(--down);
}

/* Sectors card */
.aa-sectors-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.aa-sectors__head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 10px;
}
.aa-sectors__title {
  font-size: 13px;
  font-weight: 700;
  flex: 1;
}
.aa-sectors__count {
  font-size: 11px;
  color: var(--on-var);
  background: var(--low);
  padding: 2px 8px;
  border-radius: 999px;
}
.aa-sectors__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.aa-sector-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: var(--low);
  color: var(--on-var);
}
.aa-sector-chip.up { background: rgba(242, 54, 69, 0.1); color: var(--up); }
.aa-sector-chip.down { background: rgba(8, 153, 129, 0.1); color: var(--down); }
.aa-sector-chip__chg {
  font-size: 11px;
  opacity: 0.8;
}

/* Stats card */
.aa-stats-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.aa-stats__head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 12px;
}
.aa-stats__title {
  font-size: 13px;
  font-weight: 700;
  flex: 1;
}
.aa-stats__grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}
.aa-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  border-radius: 10px;
  background: var(--low);
}
.aa-stat-item--s { background: rgba(74,71,210,0.15); }
.aa-stat-item--a { background: rgba(100,200,100,0.15); }
.aa-stat-item--b { background: rgba(255,180,0,0.1); }
.aa-stat-item--leader { background: rgba(100,100,255,0.08); }
.aa-stat-item__val {
  font-size: 1.5rem;
  font-weight: 900;
  letter-spacing: -0.04em;
  color: var(--on-surface);
}
.aa-stat-item__lbl {
  font-size: 10px;
  color: var(--on-var);
  margin-top: 2px;
}
.aa-stats__elapsed {
  text-align: right;
  font-size: 11px;
  color: var(--on-var);
  margin-top: 8px;
}

/* Consensus card */
.aa-consensus-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 16px 18px;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.aa-consensus__gauge { width: 96px; height: 96px; }
.aa-consensus__svg { width: 100%; height: 100%; }
.aa-consensus__arc { transition: stroke-dashoffset 0.6s ease; }
.aa-consensus__num {
  font-size: 22px;
  font-weight: 900;
  letter-spacing: -0.03em;
  fill: var(--on-surface);
}
.aa-consensus__unit {
  font-size: 12px;
  fill: var(--on-var);
}
.aa-consensus__stance-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.aa-stance-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.aa-stance-tag--bull { background: rgba(242, 54, 69, 0.12); color: var(--up); }
.aa-stance-tag--bear { background: rgba(8, 153, 129, 0.12); color: var(--down); }
.aa-stance-tag--neutral { background: var(--low); color: var(--on-var); }
.aa-consensus__conf-label {
  font-size: 12px;
  color: var(--on-var);
}
.aa-consensus__comm {
  font-size: 13px;
  color: var(--on-surface);
  line-height: 1.5;
  margin: 0 0 8px;
}
.aa-consensus__advice {
  font-size: 13px;
  color: var(--on-var);
  line-height: 1.4;
}
.aa-consensus__warning {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(242, 54, 69, 0.06);
  font-size: 12px;
  color: #b91c1c;
  line-height: 1.4;
}
.aa-warn-ico { flex-shrink: 0; }

/* Recommendations card */
.aa-recs-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.aa-recs__title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  margin: 0 0 12px;
  color: var(--on-surface);
}
.aa-recs__title .icon { color: #f5a623; }
.aa-recs__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.aa-rec-item {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid var(--line);
}
.aa-rec-item__left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.aa-rec-item__rank {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: var(--primary);
  color: #fff;
  font-size: 11px;
  font-weight: 900;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.aa-rec-item__name {
  font-size: 13px;
  font-weight: 700;
  color: var(--on-surface);
  margin: 0;
}
.aa-rec-item__code {
  font-size: 11px;
  color: var(--on-var);
  margin: 0;
}
.aa-rec-item__mid {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.aa-grade-badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 900;
  background: var(--low);
  color: var(--on-var);
}
.aa-grade-badge.grade-S { background: rgba(74,71,210,0.2); color: var(--primary); }
.aa-grade-badge.grade-A { background: rgba(242, 54, 69, 0.15); color: var(--up); }
.aa-grade-badge.grade-B { background: rgba(255,180,0,0.15); color: #b07000; }
.aa-rec-item__sector {
  font-size: 10px;
  color: var(--on-var);
}
.aa-rec-item__right {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.aa-rec-item__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}
.aa-tag {
  display: inline-block;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 9px;
  font-weight: 600;
  background: var(--low);
  color: var(--on-var);
}
.aa-advise-type {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  background: rgba(74,71,210,0.1);
  color: var(--primary);
  width: fit-content;
}
.aa-rec-item__reason {
  font-size: 11px;
  color: var(--on-var);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 120px;
}
.aa-rec-item__advice {
  display: flex;
  gap: 6px;
  font-size: 10px;
  color: var(--on-var);
}
.aa-rec-item__stop { color: var(--down); }
.aa-rec-item__chg {
  font-size: 14px;
  font-weight: 900;
  letter-spacing: -0.02em;
  white-space: nowrap;
}
.aa-rec-item__chg.up { color: var(--up); }
.aa-rec-item__chg.down { color: var(--down); }

/* Analysis card */
.aa-analysis-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.aa-analysis-card__head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 12px;
}
.aa-analysis-card__title {
  font-size: 13px;
  font-weight: 700;
  margin: 0;
}
.aa-analysis-card__body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.aa-analysis-para {
  font-size: 13px;
  line-height: 1.6;
  color: var(--on-surface);
  margin: 0;
}
.aa-analysis-para--section {
  font-weight: 700;
  color: var(--primary);
}

/* Actions */
.aa-actions {
  display: flex;
  gap: 10px;
}
.aa-btn-run {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px 20px;
  border-radius: 14px;
  border: none;
  background: var(--primary);
  color: #fff;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.01em;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.1s;
}
.aa-btn-run:active:not(:disabled) { transform: scale(0.98); }
.aa-btn-run:disabled { opacity: 0.6; cursor: not-allowed; }
.aa-btn-run--running { background: var(--on-var); }
.aa-btn-run__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
.aa-btn-run__ico { width: 18px; height: 18px; }
.aa-btn-reset {
  padding: 14px 18px;
  border-radius: 14px;
  border: 2px solid var(--high);
  background: transparent;
  color: var(--on-var);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.2s;
}
.aa-btn-reset:active { background: var(--low); }

/* Prompt panel */
.aa-prompt-panel {
  background: var(--white);
  border-radius: 1rem;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.aa-prompt-panel__toggle {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 14px 18px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  list-style: none;
  color: var(--on-var);
}
.aa-prompt-panel__toggle .icon { width: 16px; height: 16px; }
.aa-prompt-panel[open] .aa-prompt-panel__toggle { border-bottom: 1px solid var(--line); }
.aa-prompt-panel__body {
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.aa-prompt-section {}
.aa-prompt-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--on-var);
  margin: 0 0 6px;
}
.aa-prompt-code {
  background: var(--low);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--on-surface);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  line-height: 1.6;
}

/* Footnote */
.aa-footnote {
  font-size: 11px;
  color: var(--on-var);
  text-align: center;
  opacity: 0.7;
  margin: 0;
}
</style>
