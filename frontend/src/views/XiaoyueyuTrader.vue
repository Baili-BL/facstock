<template>
  <div class="xy-page">
    <!-- 顶栏 -->
    <header class="xy-header">
      <button type="button" class="xy-back" aria-label="返回" @click="goBack">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <div class="xy-header__brand">
        <img
          src="https://pic.imgdb.cn/item/5f7b3c6e160a81a4a535c2a1.jpg"
          alt="小鳄鱼"
          class="xy-header__avatar"
          loading="lazy"
        />
        <div>
          <h1 class="xy-header__title">小鳄鱼</h1>
          <span class="xy-header__sub">龙头战法 · 超短狙击</span>
        </div>
      </div>
      <div class="xy-header__right">
        <span
          class="xy-status-badge"
          :class="{
            'xy-status-badge--running': isRunning,
            'xy-status-badge--done': isDone,
          }"
        >
          <span v-if="isRunning" class="xy-status-badge__dot xy-status-badge__dot--spin" />
          <span v-else-if="isDone" class="xy-status-badge__dot" />
          {{ isRunning ? '扫描中' : isDone ? '已完成' : '待启动' }}
        </span>
      </div>
    </header>

    <main class="xy-main">
      <!-- 进度总览 -->
      <section class="xy-progress-card">
        <div class="xy-progress__meta">
          <span class="xy-kicker">扫描进度</span>
          <span class="xy-progress__pct">{{ progressPct }}%</span>
        </div>
        <div class="xy-progress__bar">
          <div
            class="xy-progress__fill"
            :style="{ width: progressPct + '%' }"
            :class="{ 'xy-progress__fill--done': isDone }"
          />
        </div>
        <p class="xy-progress__hint">
          {{ isRunning ? currentStepMsg : isDone ? '扫描完成，以下是结果' : '点击下方按钮启动每日扫描' }}
        </p>
      </section>

      <!-- 步骤日志 -->
      <section class="xy-log-card">
        <div class="xy-log__head">
          <svg class="icon xy-log__ico" aria-hidden="true"><use href="#icon-ai" /></svg>
          <h2 class="xy-log__title">扫描日志</h2>
          <span class="xy-log__count">{{ steps.length }} 步</span>
        </div>
        <div class="xy-log__body" ref="logEl">
          <div
            v-for="(s, i) in steps"
            :key="i"
            class="xy-log-entry"
            :class="{
              'xy-log-entry--done': s.status === 'done',
              'xy-log-entry--active': s.status === 'active',
              'xy-log-entry--error': s.status === 'error',
            }"
          >
            <span class="xy-log-entry__dot" />
            <span class="xy-log-entry__time">{{ s.time }}</span>
            <span class="xy-log-entry__msg">{{ s.message }}</span>
          </div>
          <div v-if="!steps.length" class="xy-log-empty">
            尚未开始扫描，等待启动…
          </div>
        </div>
      </section>

      <!-- 扫描结果（完成后展示） -->
      <template v-if="isDone && scanData">
        <!-- 情绪周期 -->
        <section class="xy-emotion-card">
          <div class="xy-emotion__head">
            <svg class="icon" aria-hidden="true"><use href="#icon-ai" /></svg>
            <h2 class="xy-emotion__title">情绪周期</h2>
            <span class="xy-emotion__phase" :class="'phase-' + emotionPhase">
              {{ emotionName }}
            </span>
          </div>
          <div class="xy-emotion__content">
            <div class="xy-emotion__gauge">
              <div class="xy-emotion__gauge-ring" :class="'phase-' + emotionPhase">
                <span class="xy-emotion__gauge-score">{{ emotionScore }}</span>
              </div>
            </div>
            <div class="xy-emotion__info">
              <div class="xy-emotion__item">
                <span class="xy-emotion__label">周期阶段</span>
                <span class="xy-emotion__value">{{ emotionName }}（{{ emotionDesc }}）</span>
              </div>
              <div class="xy-emotion__item">
                <span class="xy-emotion__label">仓位建议</span>
                <span class="xy-emotion__value" :class="'position-' + emotionPosition">
                  {{ emotionPosition }}
                </span>
              </div>
              <div class="xy-emotion__item">
                <span class="xy-emotion__label">涨停数量</span>
                <span class="xy-emotion__value">{{ limitUpCount }} 只</span>
              </div>
            </div>
          </div>
        </section>

        <!-- 市场指数 -->
        <section class="xy-market-card">
          <div class="xy-market__head">
            <svg class="icon" aria-hidden="true"><use href="#icon-ai" /></svg>
            <h2 class="xy-market__title">大盘指数</h2>
          </div>
          <div class="xy-market__indices">
            <div
              v-for="(info, name) in indexData"
              :key="name"
              class="xy-index-item"
            >
              <span class="xy-index-item__name">{{ name }}</span>
              <span
                class="xy-index-item__chg"
                :class="info.change >= 0 ? 'up' : 'down'"
              >
                {{ info.change >= 0 ? '+' : '' }}{{ info.change.toFixed(2) }}%
              </span>
            </div>
          </div>
        </section>

        <!-- 热点板块 -->
        <section v-if="hotSectors.length" class="xy-sectors-card">
          <div class="xy-sectors__head">
            <svg class="icon" aria-hidden="true"><use href="#icon-ai" /></svg>
            <h2 class="xy-sectors__title">热点板块</h2>
            <span class="xy-sectors__count">{{ hotSectors.length }} 个</span>
          </div>
          <div class="xy-sectors__chips">
            <span
              v-for="s in hotSectors"
              :key="s.name"
              class="xy-sector-chip"
              :class="s.change >= 0 ? 'up' : 'down'"
            >
              {{ s.name }}
              <span class="xy-sector-chip__chg">{{ s.change >= 0 ? '+' : '' }}{{ s.change }}%</span>
            </span>
          </div>
        </section>

        <!-- 龙头统计 -->
        <section class="xy-stats-card">
          <div class="xy-stats__head">
            <svg class="icon" aria-hidden="true"><use href="#icon-ai" /></svg>
            <h2 class="xy-stats__title">龙头扫描</h2>
          </div>
          <div class="xy-stats__grid">
            <div class="xy-stat-item">
              <span class="xy-stat-item__val">{{ stats.totalCandidates }}</span>
              <span class="xy-stat-item__lbl">候选股票</span>
            </div>
            <div class="xy-stat-item xy-stat-item--leader">
              <span class="xy-stat-item__val">{{ stats.leaders || 0 }}</span>
              <span class="xy-stat-item__lbl">连板龙头</span>
            </div>
            <div class="xy-stat-item xy-stat-item--c2">
              <span class="xy-stat-item__val">{{ stats.continuity2 || 0 }}</span>
              <span class="xy-stat-item__lbl">二连板</span>
            </div>
            <div class="xy-stat-item xy-stat-item--c3">
              <span class="xy-stat-item__val">{{ stats.continuity3 || 0 }}</span>
              <span class="xy-stat-item__lbl">三连板+</span>
            </div>
            <div class="xy-stat-item xy-stat-item--c4">
              <span class="xy-stat-item__val">{{ stats.continuity4plus || 0 }}</span>
              <span class="xy-stat-item__lbl">四连板+</span>
            </div>
          </div>
          <div class="xy-stats__elapsed">
            扫描耗时 {{ scanData.elapsedSeconds }}s
          </div>
        </section>

        <!-- 精选龙头 -->
        <section v-if="recommendations.length" class="xy-recs-card">
          <h2 class="xy-recs__title">
            <svg class="icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
            精选龙头
          </h2>
          <div class="xy-recs__list">
            <div
              v-for="(s, i) in recommendations"
              :key="s.code"
              class="xy-rec-item"
            >
              <div class="xy-rec-item__left">
                <span class="xy-rec-item__rank">{{ i + 1 }}</span>
                <div>
                  <p class="xy-rec-item__name">{{ s.name }}</p>
                  <p class="xy-rec-item__code">{{ s.code }}</p>
                </div>
              </div>
              <div class="xy-rec-item__mid">
                <span
                  class="xy-continuity-badge"
                  :class="'continuity-' + Math.min(s.continuity, 4)"
                >
                  {{ s.continuity }}板
                </span>
                <span class="xy-rec-item__sector">{{ s.sectorName || s.tags?.[0] }}</span>
              </div>
              <div class="xy-rec-item__right">
                <div class="xy-rec-item__buy-type">{{ s.buyType }}</div>
                <div class="xy-rec-item__range">
                  <span>买：{{ s.buyRange }}</span>
                  <span class="xy-rec-item__stop">止：{{ s.stopLoss }}</span>
                </div>
              </div>
              <span
                class="xy-rec-item__chg"
                :class="s.changePct >= 0 ? 'up' : 'down'"
              >
                {{ s.changePct >= 0 ? '+' : '' }}{{ s.changePct }}%
              </span>
            </div>
          </div>
        </section>

        <!-- AI 增强分析 -->
        <template v-if="agentResult && agentResult.success">
          <!-- 共识标尺 -->
          <section class="xy-consensus-card">
            <div class="xy-consensus__left">
              <div class="xy-consensus__gauge">
                <svg viewBox="0 0 96 96" class="xy-consensus__svg">
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
                    class="xy-consensus__arc"
                  />
                  <text x="48" y="44" text-anchor="middle" class="xy-consensus__num">{{ confidence }}</text>
                  <text x="48" y="58" text-anchor="middle" class="xy-consensus__unit">%</text>
                </svg>
              </div>
            </div>
            <div class="xy-consensus__right">
              <div class="xy-consensus__stance-row">
                <span
                  class="xy-stance-tag"
                  :class="'xy-stance-tag--' + (structured?.stance || 'neutral')"
                >
                  {{ stanceLabel }}
                </span>
                <span class="xy-consensus__conf-label">AI 信心 {{ confidence }}%</span>
              </div>
              <p class="xy-consensus__comm">
                {{ structured?.marketCommentary || '' }}
              </p>
              <div class="xy-consensus__advice">
                <strong>策略建议：</strong>{{ structured?.positionAdvice || '' }}
              </div>
              <div v-if="structured?.riskWarning" class="xy-consensus__warning">
                <span class="xy-warn-ico" aria-hidden="true">⚠</span>
                {{ structured.riskWarning }}
              </div>
            </div>
          </section>

          <!-- AI 推荐龙头 -->
          <section v-if="aiRecommendedStocks.length" class="xy-recs-card">
            <h2 class="xy-recs__title">
              <svg class="icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
              AI 精选龙头
            </h2>
            <div class="xy-recs__list">
              <div
                v-for="(s, i) in aiRecommendedStocks"
                :key="s.code || i"
                class="xy-rec-item"
              >
                <div class="xy-rec-item__left">
                  <span class="xy-rec-item__rank">{{ i + 1 }}</span>
                  <div>
                    <p class="xy-rec-item__name">{{ s.name }}</p>
                    <p class="xy-rec-item__code">{{ s.code }}</p>
                  </div>
                </div>
                <div class="xy-rec-item__mid">
                  <span
                    class="xy-continuity-badge"
                    :class="'continuity-' + Math.min(s.continuity || 1, 4)"
                  >
                    {{ s.continuity || 1 }}板
                  </span>
                  <span class="xy-rec-item__sector">{{ s.sector || '' }}</span>
                </div>
                <div class="xy-rec-item__right">
                  <div v-if="s.adviseType" class="xy-rec-item__buy-type">{{ s.adviseType }}</div>
                  <p v-if="s.signal" class="xy-rec-item__reason">{{ s.signal }}</p>
                  <div v-if="s.buyRange || s.stopLoss" class="xy-rec-item__range">
                    <span v-if="s.buyRange">买：{{ s.buyRange }}</span>
                    <span v-if="s.stopLoss" class="xy-rec-item__stop">止：{{ s.stopLoss }}</span>
                  </div>
                </div>
                <span
                  class="xy-rec-item__chg"
                  :class="(s.changePct || 0) >= 0 ? 'up' : 'down'"
                >
                  {{ (s.changePct || 0) >= 0 ? '+' : '' }}{{ s.changePct || 0 }}%
                </span>
              </div>
            </div>
          </section>

          <!-- 完整 AI 分析报告 -->
          <section class="xy-analysis-card">
            <div class="xy-analysis-card__head">
              <svg class="icon" aria-hidden="true"><use href="#icon-ai" /></svg>
              <h2 class="xy-analysis-card__title">AI 分析报告</h2>
            </div>
            <div class="xy-analysis-card__body">
              <template v-for="(para, i) in analysisParagraphs" :key="i">
                <p v-if="para" class="xy-analysis-para" :class="{ 'xy-analysis-para--section': para.startsWith('【') }">
                  {{ para }}
                </p>
              </template>
            </div>
          </section>
        </template>
      </template>

      <!-- 操作区 -->
      <div class="xy-actions">
        <button
          type="button"
          class="xy-btn-run"
          :class="{ 'xy-btn-run--running': isRunning }"
          :disabled="isRunning"
          @click="runScan"
        >
          <span v-if="isRunning" class="xy-btn-run__spinner" />
          <svg v-else class="icon xy-btn-run__ico" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          {{ isRunning ? '扫描中…' : '启动每日扫描' }}
        </button>
        <button
          v-if="isDone"
          type="button"
          class="xy-btn-reset"
          @click="resetScan"
        >
          重新扫描
        </button>
      </div>

      <!-- Prompt 预览 -->
      <details class="xy-prompt-panel">
        <summary class="xy-prompt-panel__toggle">
          <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/></svg>
          查看小鳄鱼配置
        </summary>
        <div class="xy-prompt-panel__body">
          <div class="xy-prompt-section">
            <h4 class="xy-prompt-label">策略说明</h4>
            <pre class="xy-prompt-code">小鳄鱼战法 - 龙头战法·超短狙击
核心思想：只做最强龙头，市场只需要一个龙头

选股标准：
- 必须是市场核心题材
- 必须有连板高度（2板→3板→4板）
- 必须资金强（封单大、回封能力强）

买点策略：
- 打板（涨停板上买）
- 分歧转一致（回封点）
- 换手板（筹码充分交换）

卖点策略：
- 龙头断板，立刻卖出
- 情绪退潮，高位股集体炸板
- 加速后兑现，连续加速涨停

情绪周期：
- 只在发酵期和高潮期重仓
- 退潮期必须空仓</pre>
          </div>
        </div>
      </details>

      <p class="xy-footnote">AI 分析结果仅供参考，不构成投资建议。超短线交易风险极高，请严格止损。</p>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  runXiaoyueyuScan,
} from '@/api/agents.js'

const router = useRouter()

// ── 状态 ────────────────────────────────────────────────────────────────
const steps = ref([])
const isRunning = ref(false)
const isDone = ref(false)
const scanData = ref(null)
const logEl = ref(null)
const params = ref({ enhance: true })

// ── 计算属性 ────────────────────────────────────────────────────────────────
const agentResult = computed(() => scanData.value?.agentResult)
const structured = computed(() => agentResult.value?.structured || scanData.value?.structured)
const recommendations = computed(() => scanData.value?.recommendations || [])
const hotSectors = computed(() => scanData.value?.hotSectors || [])
const stats = computed(() => scanData.value?.stats || {})
const indexData = computed(() => scanData.value?.market?.indexData || {})
const limitUpCount = computed(() => scanData.value?.market?.limitUpCount || 0)
const emotion = computed(() => scanData.value?.emotion || {})

const emotionPhase = computed(() => emotion.value?.phase || 'startup')
const emotionName = computed(() => emotion.value?.name || '未知')
const emotionDesc = computed(() => emotion.value?.description || '')
const emotionScore = computed(() => emotion.value?.score || 0)
const emotionPosition = computed(() => emotion.value?.positionAdvice || '轻仓')

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
  if (status === 'done' && step < 6) {
    addStep(step + 1, _stepMessages[step + 1] || '处理中...', 'active')
  }
  scrollLog()
}

const _stepMessages = {
  1: '正在获取大盘环境...',
  2: '正在分析情绪周期...',
  3: '正在获取热点板块...',
  4: '正在扫描涨停龙头...',
  5: '正在调用 AI 增强分析...',
  6: '扫描完成！',
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
  else router.push('/strategy/youzi_agents')
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
    addStep(3, _stepMessages[3], 'active')

    const res = await runXiaoyueyuScan({ enhance: params.value.enhance })

    addStep(4, '正在扫描涨停龙头...', 'done')
    addStep(5, '正在生成分析结果...', 'done')

    scanData.value = res.data
    addStep(6, '扫描完成！', 'done')
    isDone.value = true

  } catch (err) {
    console.error('[XiaoyueyuTrader] 扫描失败:', err)
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
/* ── 小鳄鱼主题色 ─────────────────────────────────────────────────────────── */
.xy-page {
  --primary: #e85d04;
  --primary-mid: #f48c06;
  --on-surface: #1a1c1f;
  --on-var: #414755;
  --surface: #fffbf5;
  --low: #fff7ed;
  --high: #fed7aa;
  --white: #ffffff;
  --up: #e85d04;
  --down: #059669;
  --track: #fed7aa;
  --line: rgba(232, 93, 4, 0.1);

  min-height: 100vh;
  min-height: 100dvh;
  background: var(--surface);
  color: var(--on-surface);
  padding-bottom: calc(88px + env(safe-area-inset-bottom, 0));
  font-family: 'Inter', var(--font, system-ui, sans-serif);
  -webkit-font-smoothing: antialiased;
}

/* Header */
.xy-header {
  position: sticky;
  top: 0;
  z-index: 40;
  display: grid;
  grid-template-columns: 44px 1fr auto;
  align-items: center;
  gap: 8px;
  padding: calc(12px + env(safe-area-inset-top, 0)) 12px 12px;
  background: rgba(255, 251, 245, 0.88);
  backdrop-filter: blur(16px);
  box-shadow: 0 1px 0 var(--line);
}
.xy-back {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: var(--primary);
}
.xy-back:active { background: rgba(232, 93, 4, 0.08); }
.xy-header__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.xy-header__avatar {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  object-fit: cover;
  flex-shrink: 0;
  background: var(--low);
}
.xy-header__title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.xy-header__sub {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--primary);
}
.xy-header__right { display: flex; align-items: center; }

/* Status badge */
.xy-status-badge {
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
.xy-status-badge--running {
  background: rgba(232, 93, 4, 0.1);
  color: var(--primary);
}
.xy-status-badge--done {
  background: rgba(5, 150, 105, 0.1);
  color: var(--down);
}
.xy-status-badge__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.xy-status-badge__dot--spin {
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Main */
.xy-main {
  max-width: 720px;
  margin: 0 auto;
  padding: 12px 16px 28px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Progress card */
.xy-progress-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 16px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.xy-progress__meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.xy-kicker {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--on-var);
}
.xy-progress__pct {
  font-size: 1.25rem;
  font-weight: 900;
  letter-spacing: -0.03em;
  color: var(--on-surface);
}
.xy-progress__bar {
  height: 6px;
  border-radius: 3px;
  background: var(--track);
  overflow: hidden;
}
.xy-progress__fill {
  height: 100%;
  border-radius: 3px;
  background: var(--primary);
  transition: width 0.3s ease;
}
.xy-progress__fill--done { background: var(--down); }
.xy-progress__hint {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--on-var);
}

/* Log card */
.xy-log-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.xy-log__head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 10px;
}
.xy-log__ico { color: var(--primary); }
.xy-log__title {
  font-size: 13px;
  font-weight: 700;
  flex: 1;
}
.xy-log__count {
  font-size: 11px;
  color: var(--on-var);
  background: var(--low);
  padding: 2px 8px;
  border-radius: 999px;
}
.xy-log__body {
  max-height: 200px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  scrollbar-width: thin;
}
.xy-log__body::-webkit-scrollbar { width: 4px; }
.xy-log__body::-webkit-scrollbar-thumb { background: var(--high); border-radius: 2px; }
.xy-log-empty {
  font-size: 13px;
  color: var(--on-var);
  text-align: center;
  padding: 12px;
}
.xy-log-entry {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12.5px;
  color: var(--on-var);
}
.xy-log-entry__dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--high);
  flex-shrink: 0;
  margin-top: 1px;
}
.xy-log-entry--done .xy-log-entry__dot { background: var(--down); }
.xy-log-entry--active .xy-log-entry__dot { background: var(--primary); animation: pulse 1s ease infinite; }
.xy-log-entry--error .xy-log-entry__dot { background: var(--down); }
.xy-log-entry--error { color: var(--down); }
.xy-log-entry--active { color: var(--primary); font-weight: 600; }
.xy-log-entry__time {
  font-size: 11px;
  color: var(--on-var);
  flex-shrink: 0;
  opacity: 0.7;
}
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

/* Emotion card */
.xy-emotion-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.xy-emotion__head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 12px;
}
.xy-emotion__title {
  font-size: 13px;
  font-weight: 700;
  flex: 1;
}
.xy-emotion__phase {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 3px 10px;
  border-radius: 999px;
}
.xy-emotion__phase.phase-climax { background: rgba(232, 93, 4, 0.15); color: var(--primary); }
.xy-emotion__phase.phase-fermentation { background: rgba(245, 140, 6, 0.15); color: #b45309; }
.xy-emotion__phase.phase-startup { background: rgba(5, 150, 105, 0.1); color: var(--down); }
.xy-emotion__phase.phase-recession { background: rgba(220, 38, 38, 0.1); color: #dc2626; }
.xy-emotion__content {
  display: flex;
  align-items: center;
  gap: 16px;
}
.xy-emotion__gauge {
  flex-shrink: 0;
}
.xy-emotion__gauge-ring {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 4px solid var(--primary);
}
.xy-emotion__gauge-ring.phase-climax { border-color: var(--primary); }
.xy-emotion__gauge-ring.phase-fermentation { border-color: #f48c06; }
.xy-emotion__gauge-ring.phase-startup { border-color: var(--down); }
.xy-emotion__gauge-ring.phase-recession { border-color: #dc2626; }
.xy-emotion__gauge-score {
  font-size: 1.5rem;
  font-weight: 900;
  color: var(--on-surface);
}
.xy-emotion__info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.xy-emotion__item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.xy-emotion__label {
  font-size: 12px;
  color: var(--on-var);
}
.xy-emotion__value {
  font-size: 13px;
  font-weight: 600;
  color: var(--on-surface);
}
.xy-emotion__value.position-重仓 { color: var(--primary); }
.xy-emotion__value.position-轻仓 { color: #f48c06; }
.xy-emotion__value.position-空仓 { color: #dc2626; }

/* Market card */
.xy-market-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.xy-market__head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 10px;
}
.xy-market__title {
  font-size: 13px;
  font-weight: 700;
  flex: 1;
}
.xy-market__indices {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.xy-index-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6px 12px;
  border-radius: 10px;
  background: var(--low);
  min-width: 80px;
}
.xy-index-item__name {
  font-size: 10px;
  color: var(--on-var);
  font-weight: 600;
}
.xy-index-item__chg {
  font-size: 14px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.xy-index-item__chg.up { color: var(--up); }
.xy-index-item__chg.down { color: var(--down); }

/* Sectors card */
.xy-sectors-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.xy-sectors__head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 10px;
}
.xy-sectors__title {
  font-size: 13px;
  font-weight: 700;
  flex: 1;
}
.xy-sectors__count {
  font-size: 11px;
  color: var(--on-var);
  background: var(--low);
  padding: 2px 8px;
  border-radius: 999px;
}
.xy-sectors__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.xy-sector-chip {
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
.xy-sector-chip.up { background: rgba(232, 93, 4, 0.1); color: var(--up); }
.xy-sector-chip.down { background: rgba(5, 150, 105, 0.1); color: var(--down); }
.xy-sector-chip__chg {
  font-size: 11px;
  opacity: 0.8;
}

/* Stats card */
.xy-stats-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.xy-stats__head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 12px;
}
.xy-stats__title {
  font-size: 13px;
  font-weight: 700;
  flex: 1;
}
.xy-stats__grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}
.xy-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  border-radius: 10px;
  background: var(--low);
}
.xy-stat-item--leader { background: rgba(232, 93, 4, 0.15); }
.xy-stat-item--c2 { background: rgba(245, 140, 6, 0.15); }
.xy-stat-item--c3 { background: rgba(180, 83, 9, 0.15); }
.xy-stat-item--c4 { background: rgba(220, 38, 38, 0.15); }
.xy-stat-item__val {
  font-size: 1.5rem;
  font-weight: 900;
  letter-spacing: -0.04em;
  color: var(--on-surface);
}
.xy-stat-item__lbl {
  font-size: 10px;
  color: var(--on-var);
  margin-top: 2px;
}
.xy-stats__elapsed {
  text-align: right;
  font-size: 11px;
  color: var(--on-var);
  margin-top: 8px;
}

/* Consensus card */
.xy-consensus-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 16px 18px;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.xy-consensus__gauge { width: 96px; height: 96px; }
.xy-consensus__svg { width: 100%; height: 100%; }
.xy-consensus__arc { transition: stroke-dashoffset 0.6s ease; }
.xy-consensus__num {
  font-size: 22px;
  font-weight: 900;
  letter-spacing: -0.03em;
  fill: var(--on-surface);
}
.xy-consensus__unit {
  font-size: 12px;
  fill: var(--on-var);
}
.xy-consensus__stance-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.xy-stance-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.xy-stance-tag--bull { background: rgba(232, 93, 4, 0.12); color: var(--up); }
.xy-stance-tag--bear { background: rgba(5, 150, 105, 0.12); color: var(--down); }
.xy-stance-tag--neutral { background: var(--low); color: var(--on-var); }
.xy-consensus__conf-label {
  font-size: 12px;
  color: var(--on-var);
}
.xy-consensus__comm {
  font-size: 13px;
  color: var(--on-surface);
  line-height: 1.5;
  margin: 0 0 8px;
}
.xy-consensus__advice {
  font-size: 13px;
  color: var(--on-var);
  line-height: 1.4;
}
.xy-consensus__warning {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(220, 38, 38, 0.06);
  font-size: 12px;
  color: #b91c1c;
  line-height: 1.4;
}
.xy-warn-ico { flex-shrink: 0; }

/* Recommendations card */
.xy-recs-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.xy-recs__title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  margin: 0 0 12px;
  color: var(--on-surface);
}
.xy-recs__title .icon { color: #f59e0b; }
.xy-recs__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.xy-rec-item {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid var(--line);
}
.xy-rec-item__left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.xy-rec-item__rank {
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
.xy-rec-item__name {
  font-size: 13px;
  font-weight: 700;
  color: var(--on-surface);
  margin: 0;
}
.xy-rec-item__code {
  font-size: 11px;
  color: var(--on-var);
  margin: 0;
}
.xy-rec-item__mid {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.xy-continuity-badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 900;
  background: var(--low);
  color: var(--on-var);
}
.xy-continuity-badge.continuity-2 { background: rgba(245, 140, 6, 0.2); color: #b45309; }
.xy-continuity-badge.continuity-3 { background: rgba(232, 93, 4, 0.2); color: var(--primary); }
.xy-continuity-badge.continuity-4 { background: rgba(220, 38, 38, 0.2); color: #dc2626; }
.xy-rec-item__sector {
  font-size: 10px;
  color: var(--on-var);
}
.xy-rec-item__right {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.xy-rec-item__buy-type {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  background: rgba(232, 93, 4, 0.1);
  color: var(--primary);
  width: fit-content;
}
.xy-rec-item__range {
  display: flex;
  gap: 6px;
  font-size: 10px;
  color: var(--on-var);
}
.xy-rec-item__stop { color: var(--down); }
.xy-rec-item__reason {
  font-size: 11px;
  color: var(--on-var);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 120px;
}
.xy-rec-item__chg {
  font-size: 14px;
  font-weight: 900;
  letter-spacing: -0.02em;
  white-space: nowrap;
}
.xy-rec-item__chg.up { color: var(--up); }
.xy-rec-item__chg.down { color: var(--down); }

/* Analysis card */
.xy-analysis-card {
  background: var(--white);
  border-radius: 1.1rem;
  padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.xy-analysis-card__head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 12px;
}
.xy-analysis-card__title {
  font-size: 13px;
  font-weight: 700;
  margin: 0;
}
.xy-analysis-card__body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.xy-analysis-para {
  font-size: 13px;
  line-height: 1.6;
  color: var(--on-surface);
  margin: 0;
}
.xy-analysis-para--section {
  font-weight: 700;
  color: var(--primary);
}

/* Actions */
.xy-actions {
  display: flex;
  gap: 10px;
}
.xy-btn-run {
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
.xy-btn-run:active:not(:disabled) { transform: scale(0.98); }
.xy-btn-run:disabled { opacity: 0.6; cursor: not-allowed; }
.xy-btn-run--running { background: var(--on-var); }
.xy-btn-run__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
.xy-btn-run__ico { width: 18px; height: 18px; }
.xy-btn-reset {
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
.xy-btn-reset:active { background: var(--low); }

/* Prompt panel */
.xy-prompt-panel {
  background: var(--white);
  border-radius: 1rem;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.xy-prompt-panel__toggle {
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
.xy-prompt-panel__toggle .icon { width: 16px; height: 16px; }
.xy-prompt-panel[open] .xy-prompt-panel__toggle { border-bottom: 1px solid var(--line); }
.xy-prompt-panel__body {
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.xy-prompt-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--on-var);
  margin: 0 0 6px;
}
.xy-prompt-code {
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
.xy-footnote {
  font-size: 11px;
  color: var(--on-var);
  text-align: center;
  opacity: 0.7;
  margin: 0;
}
</style>
