<template>
  <div class="aa-page">
    <!-- 顶栏 -->
    <header class="aa-header">
      <button type="button" class="aa-back" aria-label="返回" @click="goBack">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <div class="aa-header__brand">
        <img :src="agentAvatar" :alt="agentName" class="aa-header__avatar" loading="lazy" />
        <div>
          <h1 class="aa-header__title">{{ agentName }}</h1>
          <span class="aa-header__sub">{{ roleSubtitle }}</span>
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
          {{ isRunning ? '分析中' : isDone ? '已完成' : '待分析' }}
        </span>
      </div>
    </header>

    <!-- 后端失败时静默走了演示数据，必须显眼提示，避免误以为是大模型真结果 -->
    <div
      v-if="isDemoResult && isDone"
      class="aa-demo-banner"
      role="status"
    >
      <span class="aa-demo-banner__ico" aria-hidden="true">ⓘ</span>
      <div class="aa-demo-banner__text">
        <strong>当前为演示数据</strong>（后端接口未成功返回）。真实分析通常需数十秒，且依赖后端与
        <code>HUNYUAN_API_KEY</code>。请打开浏览器控制台查看报错，或确认 Flask 已在 5002 端口运行。
      </div>
    </div>

    <main class="aa-main">
      <!-- 进度总览 -->
      <section class="aa-progress-card">
        <div class="aa-progress__meta">
          <span class="aa-kicker">分析进度</span>
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
          {{ isRunning ? currentStepMsg : isDone ? '分析完成，以下是结果' : '点击下方按钮启动 AI 分析' }}
        </p>
      </section>

      <!-- 步骤日志 -->
      <section class="aa-log-card">
        <div class="aa-log__head">
          <svg class="icon aa-log__ico" aria-hidden="true"><use href="#icon-ai" /></svg>
          <h2 class="aa-log__title">分析日志</h2>
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
            尚未开始分析，等待启动…
          </div>
        </div>
      </section>

      <!-- 分析结果（完成后展示） -->
      <template v-if="isDone && result">
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
              <span class="aa-consensus__conf-label">信心指数 {{ confidence }}%</span>
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

        <!-- 推荐股票 -->
        <section v-if="recommendedStocks.length" class="aa-recs-card">
          <h2 class="aa-recs__title">
            <svg class="icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
            推荐关注
          </h2>
          <div class="aa-recs__list">
            <div
              v-for="(s, i) in recommendedStocks"
              :key="i"
              class="aa-rec-item"
            >
              <div class="aa-rec-item__left">
                <span class="aa-rec-item__rank">{{ i + 1 }}</span>
                <div>
                  <p class="aa-rec-item__name">{{ s.name }}</p>
                  <p class="aa-rec-item__code">{{ s.code }}</p>
                </div>
              </div>
              <div class="aa-rec-item__right">
                <span
                  class="aa-rec-item__role"
                  :class="'role-' + roleColor(s.role)"
                >{{ s.role }}</span>
                <p class="aa-rec-item__reason">{{ s.reason }}</p>
              </div>
              <span
                class="aa-rec-item__chg"
                :class="s.chg_pct >= 0 ? 'up' : 'down'"
              >
                {{ s.chg_pct >= 0 ? '+' : '' }}{{ s.chg_pct }}%
              </span>
            </div>
          </div>
        </section>

        <!-- 完整分析文本 -->
        <section class="aa-analysis-card">
          <div class="aa-analysis-card__head">
            <svg class="icon" aria-hidden="true"><use href="#icon-ai" /></svg>
            <h2 class="aa-analysis-card__title">完整分析报告</h2>
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

      <!-- 操作区 -->
      <div class="aa-actions">
        <button
          type="button"
          class="aa-btn-run"
          :class="{ 'aa-btn-run--running': isRunning }"
          :disabled="isRunning"
          @click="runAnalysis"
        >
          <span v-if="isRunning" class="aa-btn-run__spinner" />
          <svg v-else class="icon aa-btn-run__ico" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          {{ isRunning ? '分析中…' : '启动 AI 分析' }}
        </button>
        <button
          v-if="isDone"
          type="button"
          class="aa-btn-reset"
          @click="resetAnalysis"
        >
          重新分析
        </button>
      </div>

      <!-- Prompt 预览（可展开） -->
      <details class="aa-prompt-panel">
        <summary class="aa-prompt-panel__toggle">
          <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/></svg>
          查看 Prompt 模板
        </summary>
        <div class="aa-prompt-panel__body">
          <div class="aa-prompt-section">
            <h4 class="aa-prompt-label">System Prompt</h4>
            <pre class="aa-prompt-code">{{ systemPromptPreview }}</pre>
          </div>
          <div class="aa-prompt-section">
            <h4 class="aa-prompt-label">User Prompt（已渲染数据）</h4>
            <pre class="aa-prompt-code">{{ userPromptPreview }}</pre>
          </div>
        </div>
      </details>

      <p class="aa-footnote">AI 分析结果仅供参考，不构成投资建议。模型基于历史数据与公开信息生成，存在局限性。</p>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  demoAnalyzeAgent,
  analyzeWithAgent,
  batchAnalyzeAgents,
} from '@/api/agents.js'

const route = useRoute()
const router = useRouter()

const agentId = computed(() => route.params.id || 'jun')
const agentName = computed(() => _nameMap[agentId.value] || agentId.value)
const roleSubtitle = computed(() => _roleMap[agentId.value] || '')
const agentAvatar = computed(() => _avatarMap[agentId.value] || '')

const _nameMap = {
  jun: '钧哥天下无双', qiao: '乔帮主', jia: '炒股养家',
  speed: '极速先锋', trend: '趋势追随者', quant: '量化之翼',
  deepseek: '深度思考者',
}
const _roleMap = {
  jun: '龙头战法', qiao: '板块轮动', jia: '低位潜伏',
  speed: '打板专家', trend: '中线波段', quant: '算法回测',
  deepseek: '深度推理',
}
const _avatarMap = {
  jun: 'https://lh3.googleusercontent.com/aida-public/AB6AXuD97zD2NIGTCO_1tiXq1wsbA98aL5lltkwfWvGuW5ykcn7zacGqWOfQaC0Cgqq8Y70ssQbZDu4WTh34HYBodcl31NA-stzpx7g9dxTWCMuzM7s7gcIOeZVI8i8nHPZnB0F4J3ToG2bh9x5rvE7Qe3qAnETQRHznWRcVuYltPv923yduEQvww9hwsCd_YcKQjJrZK_VVNT5V0-w_9fQ5GDMZ9eGfWPxUPX4PFFDFtZaCN0EpwpuQSgMG_xOxIR3Btmz_rneBA88VIGp0',
  qiao: 'https://lh3.googleusercontent.com/aida-public/AB6AXuAkvzyqjBc8b9-yrIA6kgiCLQcivIp4wH7WIrTQUKwzMfdOzv2XtxUV1wNrNrhfqeTLIsfBuwrA3EAr241oN4kTt-lHWYMl71AITtxC7_wt8A4nW5MoITPdKsNLCU-voyo3kk-xnCUKV3_3FlxK00PYxoASCqVuhe9VcRsOmbddONa0gr6gZFUpH1G88RrCpk-PROMttjpPhO7TZ0ni-GVtLFYsVapWVFGzL1FCMkpV35eb1k3IDjJCoTwR7-_RArQ6FiGkkFrFe9QP',
  jia: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCGHKOsrw9P6UWNPtwRIbhOcdxdNbEN4ox5tJN9WMKrpuIDRMSGn8J3pzyTvreLu-7teIzU07GZxcA73Tcn15zCifb-gTMNKucYIvJRRtfnD8_yb5Lkp135iwwUdn2cR7vLp37g7uccbUfYOzGdXVQo5_HBrYIZiv5TgKFSeJ8t5-j0uQAu7VZkOuNLsDBQv8zcpObbrHC3y2ydOpBCzine4Ex3E-LQvcjIDCbWGcOWcetrGAmcOSofOp6KqiV9C8SjYZZV4crcvnKb',
  speed: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBI1vgeMlusdYkzuj2NE-ZGv7Qn0PwPB9a_8WTgd0SGuQgcffIKV3DMdqPmLrjo_tJOUEbWfFAaM7etkCiK-DL0Kapz57lZHDU_E2NrtrhRLiyYhFUv4Wjod5RP80FRuRoaI6Imm8MC3xR_Fk4UVdMODD4y766SLxZpwZ6wfesd3pjueWfMgRetsFTOBrdDiR9sO0SmJ3UVyPu0w3xeOx2YfAI8VEUP5yhV5egxcDv0BQBPOWmUPY1n6ED5gCwKVlSooRXybPuYgEVS',
  trend: 'https://lh3.googleusercontent.com/aida-public/AB6AXuC7iUecTzgh3H2Vfw_JF5So-Z65G9cEHtjtOH7DEpIkIAvZVHQD6hDEjwcthbiSx752DTPKTOWEo95r0Q7cwv2gz0FSSYH1TddIwzZy58u2sHd2jjQgjqv4Rz16eJOIaRUgO5y0uI_DjjZt935pLPrGECMwP4rGV9rg_9voHG4bA8bi_3seWorRDwsmUj7vNh2_FiyvN963Et2sHDidpmRnG2hntpi1oHnFFbScS5u_oIfAFIvKdj0DG6C7bTHJToK3ya0bUw5Mal3y',
  quant: 'https://lh3.googleusercontent.com/aida-public/AB6AXuDGooDuo4HpiasBYDo6fvclBIFA-Gh4cz1OC5oVGRLDNxZJjYYx0j2REaQm6JDUHsEoUPFF1_w4cMBqT8qOZnTA6PHhdNfLvwxOrGe-V954yPvS_z1wJsPCEe5FQCb4-3dB2HiQjFwqveRFT0dOijk0eU_XX-RYIzJuzvzF9Y3eI343MalIdAFvOwUJH0NAGG3PxoqVPtKwHoNZRpT4MKFN-TGzRm55gHx_47AYleZV04gHMAVos0Y2tUQazlvkUpk9IyoyupmByD_e',
  deepseek: 'https://api.dicebear.com/7.x/bottts-neutral/svg?seed=deepseek&backgroundColor=b6e3f4',
}

// ── 状态 ────────────────────────────────────────────────────────────────
const steps = ref([])
const isRunning = ref(false)
const isDone = ref(false)
const result = ref(null)
const logEl = ref(null)
/** true = 本次结果是前端 demoAnalyzeAgent，非后端真实返回 */
const isDemoResult = ref(false)

// ── 计算属性 ────────────────────────────────────────────────────────────────
const structured = computed(() => result.value?.structured)
const confidence = computed(() => structured.value?.confidence ?? 0)
const recommendedStocks = computed(() => structured.value?.recommendedStocks ?? [])

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
  const text = result.value?.analysis || ''
  return text.split('\n').filter(l => l.trim())
})

const systemPromptPreview = computed(() => {
  return `你是一位专业的A股短线交易策略分析师，代号「${agentName.value}」，使用${roleSubtitle.value}风格。
你拥有丰富的题材炒作、龙头战法、板块轮动实战经验，熟悉游资操盘手法与量化指标。
请始终以专业、严谨、客观的态度输出分析，禁止提供具体买卖价格建议。`
})

const userPromptPreview = computed(() => {
  const m = {
    'jun': '请根据以下今日市场数据，从龙头视角给出你的策略分析...',
    'qiao': '请根据以下今日市场数据，分析板块轮动节奏与配置方向...',
    'jia': '请根据以下市场数据，从价值与安全边际角度给出分析...',
    'speed': '请根据以下市场数据，分析打板机会与风险...',
    'trend': '请根据以下市场数据，分析中期趋势方向与波段机会...',
    'quant': '请根据以下市场数据，给出量化视角的分析...',
    'deepseek': '请从宏观+行业+个股三维深度推理，结合扫描数据给出分析...',
  }
  return m[agentId.value] || '正在加载 Prompt...'
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
  // 自动激活下一步
  if (status === 'done' && step < 6) {
    addStep(step + 1, _stepMessages[step + 1] || '处理中...', 'active')
  }
  scrollLog()
}

const _stepMessages = {
  1: '正在准备市场数据...',
  2: '正在加载 Agent Prompt 模板...',
  3: '正在调用 AI 模型分析...',
  4: '正在解析结构化分析结果...',
  5: '正在生成分析报告...',
  6: '分析完成！',
}

function scrollLog() {
  nextTick(() => {
    if (logEl.value) {
      logEl.value.scrollTop = logEl.value.scrollHeight
    }
  })
}

function roleColor(role) {
  if (!role) return 'neutral'
  if (role.includes('龙头') || role.includes('中军')) return 'primary'
  if (role.includes('跟风') || role.includes('补涨')) return 'muted'
  return 'neutral'
}

// ── 分析执行 ────────────────────────────────────────────────────────────────
async function runAnalysis() {
  if (isRunning.value) return
  isRunning.value = true
  isDone.value = false
  result.value = null
  steps.value = []
  isDemoResult.value = false

  try {
    // 初始化步骤
    addStep(1, _stepMessages[1], 'active')

    // 调用分析（优先后端，失败则降级演示）
    let res
    try {
      addStep(2, _stepMessages[2], 'done')
      addStep(3, `正在调用 AI 模型分析「${agentName.value}」...`, 'active')
      res = await analyzeWithAgent(agentId.value)
      isDemoResult.value = false
    } catch (e) {
      console.warn('[AgentAnalysis] 后端调用失败，降级到演示模式:', e)
      isDemoResult.value = true
      // 降级到演示模式（固定文案 + 约 3s 动画，易被误认为真 AI）
      res = await demoAnalyzeAgent(agentId.value, (stepInfo) => {
        if (stepInfo.step) addStep(stepInfo.step, stepInfo.message, 'done')
      })
    }

    addStep(4, '正在解析结构化分析结果...', 'done')
    addStep(5, '正在生成分析报告...', 'done')
    result.value = res
    addStep(6, '分析完成！', 'done')
    isDone.value = true
  } catch (err) {
    console.error('[AgentAnalysis] 分析失败:', err)
    addStep(0, `分析失败: ${err.message}`, 'error')
  } finally {
    isRunning.value = false
  }
}

function resetAnalysis() {
  steps.value = []
  isRunning.value = false
  isDone.value = false
  result.value = null
  isDemoResult.value = false
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/strategy/agents')
}
</script>

<style scoped>
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

/* 演示数据提示条（后端失败时） */
.aa-demo-banner {
  margin: 0 12px 10px;
  padding: 10px 12px;
  display: flex;
  gap: 10px;
  align-items: flex-start;
  border-radius: 12px;
  background: #fff8e6;
  border: 1px solid #f0c96b;
  color: #5c4a00;
  font-size: 13px;
  line-height: 1.45;
}
.aa-demo-banner__ico {
  flex-shrink: 0;
  font-weight: 700;
  font-size: 16px;
  line-height: 1.2;
}
.aa-demo-banner__text strong {
  display: block;
  margin-bottom: 4px;
}
.aa-demo-banner__text code {
  font-size: 11px;
  padding: 1px 4px;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 4px;
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

.aa-header__right {
  display: flex;
  align-items: center;
}

.aa-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  background: var(--low);
  color: var(--on-var);
  white-space: nowrap;
}
.aa-status-badge--running {
  background: rgba(74, 71, 210, 0.12);
  color: var(--primary);
}
.aa-status-badge--done {
  background: rgba(0, 107, 27, 0.1);
  color: var(--up);
}

.aa-status-badge__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}
.aa-status-badge__dot--spin {
  animation: spin-dot 1s linear infinite;
}
@keyframes spin-dot {
  to { transform: rotate(360deg); }
}

/* Main */
.aa-main {
  max-width: 720px;
  margin: 0 auto;
  padding: 20px 16px 32px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Progress */
.aa-progress-card {
  padding: 20px 18px;
  background: var(--white);
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(26, 28, 31, 0.04);
  outline: 1px solid rgba(193, 198, 215, 0.12);
}

.aa-progress__meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.aa-kicker {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--on-var);
}

.aa-progress__pct {
  font-size: 14px;
  font-weight: 800;
  color: var(--primary);
}

.aa-progress__bar {
  height: 8px;
  background: var(--track);
  border-radius: 999px;
  overflow: hidden;
  margin-bottom: 10px;
}

.aa-progress__fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--primary), var(--primary-mid));
  transition: width 0.5s ease;
  min-width: 4px;
}
.aa-progress__fill--done {
  background: linear-gradient(90deg, #f23645, #fb7185);
}

.aa-progress__hint {
  margin: 0;
  font-size: 13px;
  color: var(--on-var);
}

/* Log */
.aa-log-card {
  padding: 20px 18px;
  background: var(--white);
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(26, 28, 31, 0.04);
  outline: 1px solid rgba(193, 198, 215, 0.12);
}

.aa-log__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.aa-log__ico {
  color: var(--primary);
  fill: currentColor;
  flex-shrink: 0;
}

.aa-log__title {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
  flex: 1;
}

.aa-log__count {
  font-size: 11px;
  font-weight: 800;
  color: var(--on-var);
  background: var(--low);
  padding: 3px 8px;
  border-radius: 999px;
}

.aa-log__body {
  max-height: 280px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-right: 4px;
  scrollbar-width: thin;
}

.aa-log-entry {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13px;
  color: var(--on-var);
  opacity: 0.6;
}
.aa-log-entry--done { opacity: 1; }
.aa-log-entry--active { opacity: 1; font-weight: 600; color: var(--primary); }
.aa-log-entry--error { opacity: 1; color: var(--down); }

.aa-log-entry__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--on-var);
  flex-shrink: 0;
  margin-top: 3px;
}
.aa-log-entry--done .aa-log-entry__dot { background: var(--up); }
.aa-log-entry--active .aa-log-entry__dot {
  background: var(--primary);
  animation: pulse-dot 1.2s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.5); opacity: 0.5; }
}
.aa-log-entry--error .aa-log-entry__dot { background: var(--down); }

.aa-log-entry__time {
  font-size: 11px;
  color: rgba(65, 71, 85, 0.5);
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.aa-log-entry__msg { flex: 1; }

.aa-log-empty {
  font-size: 13px;
  color: var(--on-var);
  opacity: 0.5;
  text-align: center;
  padding: 20px 0;
}

/* Consensus */
.aa-consensus-card {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 20px;
  padding: 22px;
  background: var(--white);
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(26, 28, 31, 0.04);
  outline: 1px solid rgba(193, 198, 215, 0.12);
}
@media (max-width: 400px) {
  .aa-consensus-card { grid-template-columns: 1fr; }
}

.aa-consensus__left { display: flex; align-items: center; }
.aa-consensus__gauge { width: 96px; height: 96px; }
.aa-consensus__svg { width: 100%; height: 100%; }
.aa-consensus__arc { transition: stroke-dashoffset 1s ease; }
.aa-consensus__num {
  font-size: 20px;
  font-weight: 800;
  fill: var(--on-surface);
  font-variant-numeric: tabular-nums;
}
.aa-consensus__unit {
  font-size: 10px;
  font-weight: 600;
  fill: var(--on-var);
}

.aa-consensus__stance-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.aa-stance-tag {
  font-size: 12px;
  font-weight: 800;
  padding: 4px 12px;
  border-radius: 999px;
}
.aa-stance-tag--bull {
  background: var(--chip-bg);
  color: var(--chip-on);
}
.aa-stance-tag--bear {
  background: rgba(8, 153, 129, 0.14);
  color: #047857;
}
.aa-stance-tag--neutral {
  background: var(--high);
  color: var(--on-var);
}

.aa-consensus__conf-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--on-var);
}

.aa-consensus__comm {
  margin: 0 0 10px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--on-surface);
}

.aa-consensus__advice {
  font-size: 13px;
  line-height: 1.6;
  color: var(--on-var);
  margin-bottom: 8px;
}
.aa-consensus__advice strong { font-weight: 800; color: var(--on-surface); }

.aa-consensus__warning {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 12px;
  color: #93000a;
  background: rgba(186, 26, 26, 0.06);
  padding: 8px 10px;
  border-radius: 8px;
  line-height: 1.5;
}
.aa-warn-ico { flex-shrink: 0; font-size: 14px; }

/* Recommendations */
.aa-recs-card {
  padding: 22px 20px;
  background: var(--white);
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(26, 28, 31, 0.04);
  outline: 1px solid rgba(193, 198, 215, 0.12);
}

.aa-recs__title {
  margin: 0 0 18px;
  font-size: 16px;
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--primary);
}

.aa-recs__list { display: flex; flex-direction: column; gap: 12px; }

.aa-rec-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  background: var(--low);
  border-radius: 12px;
  flex-wrap: wrap;
}

.aa-rec-item__left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 0 0 auto;
}

.aa-rec-item__rank {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.aa-rec-item__name {
  margin: 0;
  font-size: 14px;
  font-weight: 800;
  white-space: nowrap;
}
.aa-rec-item__code {
  margin: 0;
  font-size: 10px;
  color: var(--on-var);
  font-variant-numeric: tabular-nums;
}

.aa-rec-item__right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.aa-rec-item__role {
  font-size: 10px;
  font-weight: 800;
  padding: 2px 8px;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  width: fit-content;
}
.role-primary { background: rgba(74, 71, 210, 0.12); color: var(--primary); }
.role-muted { background: var(--high); color: var(--on-var); }
.role-neutral { background: var(--low); color: var(--on-var); }

.aa-rec-item__reason {
  margin: 0;
  font-size: 11px;
  color: var(--on-var);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.aa-rec-item__chg {
  font-size: 15px;
  font-weight: 800;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.aa-rec-item__chg.up { color: var(--up); }
.aa-rec-item__chg.down { color: var(--down); }

/* Analysis Card */
.aa-analysis-card {
  padding: 22px 20px;
  background: var(--white);
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(26, 28, 31, 0.04);
  outline: 1px solid rgba(193, 198, 215, 0.12);
}

.aa-analysis-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  color: var(--primary);
}
.aa-analysis-card__head .icon { fill: currentColor; }

.aa-analysis-card__title {
  margin: 0;
  font-size: 16px;
  font-weight: 800;
}

.aa-analysis-card__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.aa-analysis-para {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--on-var);
}
.aa-analysis-para--section {
  font-weight: 700;
  color: var(--primary);
  margin-top: 4px;
}

/* Actions */
.aa-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.aa-btn-run {
  flex: 1;
  min-width: 200px;
  padding: 16px 24px;
  border-radius: 14px;
  font-size: 16px;
  font-weight: 800;
  color: #fff;
  background: linear-gradient(135deg, var(--primary), var(--primary-mid));
  box-shadow: 0 8px 32px rgba(74, 71, 210, 0.3);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
  transition: opacity 0.15s ease, transform 0.1s ease;
}
.aa-btn-run:active { transform: scale(0.98); opacity: 0.9; }
.aa-btn-run:disabled { opacity: 0.7; cursor: not-allowed; }
.aa-btn-run--running {
  background: linear-gradient(135deg, #717786, #9ca3af);
  box-shadow: none;
}

.aa-btn-run__ico { font-size: 18px; }

.aa-btn-run__spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.aa-btn-reset {
  padding: 16px 20px;
  border-radius: 14px;
  font-size: 14px;
  font-weight: 700;
  background: var(--low);
  color: var(--on-var);
  cursor: pointer;
  flex-shrink: 0;
}
.aa-btn-reset:active { opacity: 0.8; }

/* Prompt Panel */
.aa-prompt-panel {
  background: var(--white);
  border-radius: 14px;
  outline: 1px solid rgba(193, 198, 215, 0.12);
  overflow: hidden;
}

.aa-prompt-panel__toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 18px;
  font-size: 13px;
  font-weight: 700;
  color: var(--on-var);
  cursor: pointer;
  user-select: none;
  list-style: none;
}
.aa-prompt-panel__toggle .icon { fill: currentColor; }
.aa-prompt-panel__toggle::-webkit-details-marker { display: none; }

.aa-prompt-panel__body {
  padding: 0 18px 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.aa-prompt-section {}

.aa-prompt-label {
  margin: 0 0 8px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--primary);
}

.aa-prompt-code {
  margin: 0;
  padding: 12px 14px;
  background: var(--low);
  border-radius: 10px;
  font-size: 11px;
  line-height: 1.6;
  color: var(--on-var);
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 160px;
  overflow-y: auto;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
}

/* Footnote */
.aa-footnote {
  margin: 4px 0 0;
  font-size: 11px;
  line-height: 1.5;
  color: var(--on-var);
}
</style>
