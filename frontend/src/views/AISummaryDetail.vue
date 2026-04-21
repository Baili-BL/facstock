<template>
  <div class="asd-page">
    <header class="asd-header">
      <button type="button" class="asd-back" aria-label="返回" @click="goBack">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <div class="asd-brand">
        <img
          class="asd-brand__avatar"
          src="https://lh3.googleusercontent.com/aida-public/AB6AXuCAWb4Xek1sXSS5gBqrPoX0yLnV6mCxOimlTOphZierWjTFMvRicNXIngdIz7Bv6csFGSVex0u_UDyjK7Hs_Mm0sfo31UGyniJML2R-mxZbxXksuN8o87L120ABTZxguEV0hEsOMhZmxRn94xtgo1gvR_UIwarmX6E0q--yFF0_gRP5EjgGHm5LsVw6mYBxsTICiOD6H6CeVP147lF2sNAk9g9HrcONLFkurV2vPZpZclLl-AGxWieQqMBUtxLsM8M9I_2kCi5vi65A"
          alt=""
          loading="lazy"
        />
        <h1 class="asd-brand__title">游资智能体</h1>
      </div>
      <button type="button" class="asd-icon" aria-label="搜索" @click="$router.push('/')">
        <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
      </button>
    </header>

    <main class="asd-main">
      <div class="asd-headline">
        <div>
          <p class="asd-kicker">AI 策略总结</p>
          <h2 class="asd-title">智能共识策略概览</h2>
        </div>
        <div class="asd-headline__actions">
          <!-- 模式切换 -->
          <div class="asd-mode-toggle">
            <button
              type="button"
              class="asd-mode-btn"
              :class="{ 'asd-mode-btn--active': analysisMode === 'parallel' }"
              @click="setMode('parallel')"
            >
              并行模式
            </button>
            <button
              type="button"
              class="asd-mode-btn"
              :class="{ 'asd-mode-btn--active': analysisMode === 'hierarchical' }"
              @click="setMode('hierarchical')"
            >
              <span class="asd-mode-btn__icon">🎯</span>
              层次化
            </button>
          </div>
          <div v-if="loading" class="asd-sync asd-sync--loading">
            <span class="asd-sync__dot asd-sync__dot--spin" aria-hidden="true" />
            <span>{{ currentStepMessage }}</span>
          </div>
          <div v-else class="asd-sync">
            <span class="asd-sync__dot" aria-hidden="true" />
            <span>实时数据已同步</span>
          </div>
          <button type="button" class="asd-btn-primary" @click="$router.push('/strategy/macro')">
            更新研报
          </button>
        </div>
        <div v-if="errorMsg" class="asd-error">{{ errorMsg }}</div>
      </div>

      <!-- 主控分析卡片（仅层次化模式显示） -->
      <div v-if="analysisMode === 'hierarchical' && masterData" class="asd-master-card">
        <div class="asd-master-card__header">
          <svg class="icon asd-master-card__icon" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
          </svg>
          <h3 class="asd-master-card__title">市场首席策略官分析</h3>
          <span class="asd-master-card__phase">{{ masterData.marketPhase || '分析中' }}</span>
        </div>
        <div class="asd-master-card__body">
          <div class="asd-master-item">
            <span class="asd-master-item__label">市场核心意图</span>
            <span class="asd-master-item__value">{{ masterData.marketCoreIntent || '分析中...' }}</span>
          </div>
          <div class="asd-master-item">
            <span class="asd-master-item__label">主线题材</span>
            <span class="asd-master-item__value asd-master-item__value--highlight">{{ masterData.keyTheme || '暂无明显主线' }}</span>
          </div>
          <div class="asd-master-item">
            <span class="asd-master-item__label">风险偏好</span>
            <span class="asd-master-item__badge" :class="'badge--' + riskAppetiteClass">{{ masterData.riskAppetite || '中' }}</span>
          </div>
          <div v-if="masterData.agentPriority?.length" class="asd-master-item asd-master-item--priority">
            <span class="asd-master-item__label">智能体优先级</span>
            <div class="asd-master-priority">
              <span
                v-for="(agentId, idx) in masterData.agentPriority.slice(0, 5)"
                :key="agentId"
                class="asd-master-priority__tag"
                :class="{ 'asd-master-priority__tag--high': idx === 0 }"
              >
                {{ getAgentName(agentId) }}
              </span>
            </div>
          </div>
          <div v-if="masterData.coordinationNotes" class="asd-master-item asd-master-item--notes">
            <span class="asd-master-item__label">操作建议</span>
            <span class="asd-master-item__value">{{ masterData.coordinationNotes }}</span>
          </div>
        </div>
      </div>

      <!-- 执行日志（仅层次化模式显示） -->
      <div v-if="analysisMode === 'hierarchical' && executionLog.length" class="asd-log-card">
        <div class="asd-log-card__header">
          <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/></svg>
          <h3 class="asd-log-card__title">执行日志</h3>
          <span class="asd-log-card__count">{{ executionLog.length }} 条</span>
        </div>
        <div class="asd-log-card__body">
          <div
            v-for="(log, idx) in executionLog.slice(-8)"
            :key="idx"
            class="asd-log-entry"
            :class="'asd-log-entry--' + log.status"
          >
            <span class="asd-log-entry__phase">[{{ formatPhase(log.phase) }}]</span>
            <span class="asd-log-entry__agent">{{ log.agent_id }}</span>
            <span class="asd-log-entry__status">{{ formatStatus(log.status) }}</span>
            <span class="asd-log-entry__msg">{{ log.message }}</span>
          </div>
        </div>
      </div>

      <div class="asd-grid">
        <!-- 左：共识 + 洞察 -->
        <div class="asd-col asd-col--left">
          <section class="asd-card asd-gauge-card">
            <h3 class="asd-card-label">市场情绪共识</h3>
            <div class="asd-gauge-wrap">
              <div class="asd-gauge">
                <svg class="asd-gauge__svg" viewBox="0 0 192 192" aria-hidden="true">
                  <defs>
                    <linearGradient :id="gradId" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stop-color="#4a47d2" />
                      <stop offset="100%" stop-color="#fb7185" />
                    </linearGradient>
                  </defs>
                  <circle class="asd-gauge__track" cx="96" cy="96" r="88" fill="none" stroke-width="12" />
                  <circle
                    class="asd-gauge__prog"
                    cx="96"
                    cy="96"
                    r="88"
                    fill="none"
                    stroke-width="12"
                    stroke-linecap="round"
                    :stroke="`url(#${gradId})`"
                    :stroke-dasharray="gaugeCirc"
                    :stroke-dashoffset="gaugeOffset"
                    transform="rotate(-90 96 96)"
                  />
                </svg>
                <div class="asd-gauge__center">
                  <span class="asd-gauge__num tabular">{{ consensusPct }}</span>
                  <span class="asd-gauge__pct">%</span>
                </div>
              </div>
              <div class="asd-gauge__foot">
                <div class="asd-bull-pill">
                  <span class="asd-bull-pill__ico" aria-hidden="true">↗</span>
                  {{ sentimentLabel }}
                </div>
                <p class="asd-gauge__sub">综合 {{ agentCount }} 名核心智能体观点</p>
              </div>
            </div>
            <div class="asd-gauge__glow" aria-hidden="true" />
          </section>

          <!-- 综合建议（仅层次化模式显示） -->
          <section v-if="analysisMode === 'hierarchical' && synthesis" class="asd-card asd-insight">
            <div class="asd-insight__head">
              <svg class="icon asd-insight__ico" aria-hidden="true"><use href="#icon-ai" /></svg>
              <h3 class="asd-insight__title">综合建议</h3>
            </div>
            <p class="asd-insight__body asd-synthesis">{{ synthesis }}</p>
          </section>

          <!-- 洞察（并行模式使用旧的） -->
          <section v-else class="asd-card asd-insight">
            <div class="asd-insight__head">
              <svg class="icon asd-insight__ico" aria-hidden="true"><use href="#icon-ai" /></svg>
              <h3 class="asd-insight__title">核心深度洞察</h3>
            </div>
            <div v-if="loading" class="asd-insight__body asd-skeleton" />
            <p v-else class="asd-insight__body">{{ deepInsight }}</p>
          </section>
        </div>

        <!-- 右：头寸 + TOP3 -->
        <div class="asd-col asd-col--right">
          <section>
            <div class="asd-section-h">
              <h3 class="asd-section-h__title">主力智能体头寸</h3>
              <span class="asd-section-h__link">实时追踪</span>
            </div>
            <div class="asd-agents">
              <div
                v-for="a in stanceAgents"
                :key="a.name"
                class="asd-agent"
                :class="{ 'asd-agent--bear': a.stance === 'bear' }"
              >
                <div class="asd-agent__row1">
                  <div class="asd-agent__who">
                    <div class="asd-agent__av">
                      <img :src="a.avatar" :alt="a.name" loading="lazy" />
                    </div>
                    <div>
                      <p class="asd-agent__name">{{ a.name }}</p>
                      <p class="asd-agent__role">{{ a.role }}</p>
                    </div>
                  </div>
                  <span class="asd-agent__arrow" :class="'tone-' + a.stance" aria-hidden="true">
                    {{ a.stance === 'bull' ? '↑' : a.stance === 'bear' ? '↓' : '—' }}
                  </span>
                </div>
                <div class="asd-agent__row2">
                  <span class="asd-tag" :class="'asd-tag--' + a.stance">{{ a.tagLabel }}</span>
                  <span class="asd-conf">信心指数 {{ a.confidence }}%</span>
                </div>
              </div>
            </div>
          </section>

          <section class="asd-card asd-top3">
            <div class="asd-top3__head">
              <div class="asd-top3__head-l">
                <svg class="icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/></svg>
                <h3 class="asd-top3__title">核心投资机会 (TOP 3)</h3>
              </div>
              <span class="asd-top3__time">最后更新: {{ lastUpdated }}</span>
            </div>
            <div class="asd-top3__list">
              <button
                v-for="op in opportunities"
                :key="op.rank"
                type="button"
                class="asd-opp"
              >
                <div class="asd-opp__left">
                  <span class="asd-opp__rank">{{ op.rank }}</span>
                  <div>
                    <div class="asd-opp__title-row">
                      <span class="asd-opp__name">{{ op.title }}</span>
                      <span class="asd-opp__badge" :class="'bdg-' + op.badgeKind">{{ op.badge }}</span>
                    </div>
                    <p class="asd-opp__meta">{{ op.meta }}</p>
                  </div>
                </div>
                <div class="asd-opp__right">
                  <p class="asd-opp__chg tabular" :class="op.chg >= 0 ? 'up' : 'down'">
                    {{ op.chg >= 0 ? '+' : '' }}{{ op.chg }}%
                  </p>
                  <p class="asd-opp__flow">
                    <span class="asd-opp__flow-ico" aria-hidden="true">⌇</span>
                    {{ op.flowLabel }}
                  </p>
                </div>
              </button>
            </div>
          </section>
        </div>
      </div>

      <p class="asd-note">AI 分析结果仅供参考，不构成投资建议。</p>

      <!-- 骨架屏覆盖层（首次加载时） -->
      <div v-if="loading" class="asd-loading-overlay" aria-label="正在加载">
        <div class="asd-spinner" />
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { batchAnalyzeAgents } from '@/api/agents.js'
import { stanceMeta } from '@/api/agents.js'

const router = useRouter()
const gradId = 'asd-gauge-grad-' + Math.random().toString(36).slice(2, 9)

// ─── 状态 ────────────────────────────────────────────────────────────────
const loading = ref(true)
const errorMsg = ref('')
const apiData = ref(null)
const analysisMode = ref('hierarchical') // 'parallel' | 'hierarchical'
const executionLog = ref([])

// ─── Agent 名称映射 ─────────────────────────────────────────────────────
const _nameMap = {
  jun: '钧哥天下无双', qiao: '乔帮主', jia: '炒股养家',
  speed: '极速先锋', trend: '趋势追随者', quant: '量化之翼',
  deepseek: '深度思考者', beijing: '北京炒家', master: '市场首席策略官',
}

function getAgentName(agentId) {
  return _nameMap[agentId] || agentId
}

// ─── API 数据 ────────────────────────────────────────────────────────────
onMounted(async () => {
  await fetchData()
})

async function fetchData() {
  loading.value = true
  errorMsg.value = ''
  executionLog.value = []
  try {
    const data = await batchAnalyzeAgents({ mode: analysisMode.value })
    apiData.value = data
    // 保存执行日志
    if (data.execution_log) {
      executionLog.value = data.execution_log
    }
  } catch (e) {
    errorMsg.value = e.message || '加载失败，请重试'
  } finally {
    loading.value = false
  }
}

async function setMode(mode) {
  if (mode === analysisMode.value) return
  analysisMode.value = mode
  await fetchData()
}

// ─── 当前步骤消息 ───────────────────────────────────────────────────────
const currentStepMessage = computed(() => {
  const log = executionLog.value
  if (!log.length) return 'AI 分析中…'
  const last = log[log.length - 1]
  if (last.status === 'RUNNING' || last.status === 'running') {
    return `${getAgentName(last.agent_id)} ${last.message}`
  }
  return 'AI 分析中…'
})

// ─── 主控分析数据 ────────────────────────────────────────────────────────
const masterData = computed(() => apiData.value?.master || null)

// ─── 综合建议 ────────────────────────────────────────────────────────────
const synthesis = computed(() => apiData.value?.synthesis || '')

// ─── 共识 ────────────────────────────────────────────────────────────────
const consensusPct = computed(() => apiData.value?.consensus?.consensusPct ?? 75)
const agentCount = computed(() => apiData.value?.agentResults?.length ?? 6)
const lastUpdated = computed(() => apiData.value?.lastUpdated ?? '')

const gaugeR = 88
const gaugeCirc = 2 * Math.PI * gaugeR
const gaugeOffset = computed(() => gaugeCirc * (1 - consensusPct.value / 100))

// ─── 风险偏好样式 ────────────────────────────────────────────────────────
const riskAppetiteClass = computed(() => {
  const appetite = masterData.value?.riskAppetite || '中'
  const map = { '高': 'high', '中': 'medium', '低': 'low' }
  return map[appetite] || 'medium'
})

// ─── 情感标签 ───────────────────────────────────────────────────────────
const sentimentLabel = computed(() => {
  const pct = consensusPct.value
  if (pct >= 70) return '乐观看多'
  if (pct >= 55) return '偏乐观'
  if (pct >= 45) return '中性'
  if (pct >= 30) return '偏谨慎'
  return '谨慎防御'
})

// ─── 格式化工具 ──────────────────────────────────────────────────────────
function formatPhase(phase) {
  const map = {
    'master': '主控',
    'phase_1': '阶段一',
    'phase_2': '阶段二',
    'phase_3': '阶段三',
    'aggregation': '聚合',
    'init': '初始化',
    'system': '系统',
  }
  return map[phase] || phase
}

function formatStatus(status) {
  const map = {
    'COMPLETED': '✅',
    'completed': '✅',
    'RUNNING': '⏳',
    'running': '⏳',
    'FAILED': '❌',
    'failed': '❌',
    'START': '🚀',
    'SKIPPED': '⏭',
  }
  return map[status] || '•'
}

// ─── Agent 头像映射（与 HTML 一致）───────────────────────────────────────
const AVATARS = {
  jun:    'https://lh3.googleusercontent.com/aida-public/AB6AXuCInasWv9TA_vo972ng4g8Lgb_bQ4E1cu98XzjALQmj8yMGhNJSnwVYhexJop8gwbZN6eRXUZyKG26O6k8JZZETgqF6HtUdGPRj9BRji9prMyH0BWc4ajlgrH_DjeCOHUWTnIqXHnvSlA4JSZZE060X8fGfCwYeKrj2rRAyyzVY8UtL6KGDrRGUoeuPtbGBzn_Y8zJvfUaz1N_8MySMe_ssRpxzetyoEtSNJKvZG-szOhuTDPby1R8c_70pSReCbjyz0lrDPbWitlC_',
  qiao:   'https://lh3.googleusercontent.com/aida-public/AB6AXuBbTjBU5m7nu-qgUNvUvX_0HISDFUIaEqSqBqNCa5EaldH9DCAwciFceGOMChghk6Ub_Xx70mUe_x9Gcuin402k_pHzdPQTJmwfg8QKv-j4t8A3D4J8Vh2DFXSy9n6lN014wvx8RpXXmXYwbiUP1pJjSzg5UsxixvMO914IhF2mAVmtDWYt5BpYklOfHfOqzZqZO_mfJIVB3mbDtQHdahZuG5EQehM_jW6H1xGaCFsmsSwRY9kS9u9TiIHoDguRCw4ZVvkS3OlJhUCa',
  jia:    'https://lh3.googleusercontent.com/aida-public/AB6AXuD29hsbiQEvz7_nZE6X3aYJOQLxZPPRwuM24_Nuv3MwjLioX07l-YIGg2ySy1huFUCPp9JnUUkxJkXkTsbv8gRrtaw4O6cpUgTaSYAuibSnvSkv4_F8EljMld-RhwTAcgAqlNLOcYEOPHm9N0-zO9rHVeqV-K6CpMYd-EkyD3UxRpAkFYlBxdOMYkgSK1-essCbdgd5rEY-RWnejsCa9nJaAkQbqN1vXnZU_k3OPzdUDFW7TYVi5YvprAkevbvRoARpOMD94KH1cKyV',
  speed:  'https://lh3.googleusercontent.com/aida-public/AB6AXuDNtFfv2wwow28ZIYXj21sQUMes_Cdf7vQhU3XpTZjYUIgqFwC8v1HwM3szL75BQkNgfIkxLzkDq49OgfwHzHQGGglJk3JefuW78gSCKbBwASVfloyHrTVOllcxGMHKntJOekIHZqq1gtTw2749B3654J5tn9mEdm3UcinnA7si9_wM2lLeYvSnTYTNeXttkcjKvh4x457rnnSJsr9ga0kcLv7_MaZFEKsJ4i3ykzLdN9iDfh2johon281TYHArUU-xPyvu3us6wOap',
  trend:  'https://lh3.googleusercontent.com/aida-public/AB6AXuA5kCrXH_prczoiwrFXf7_CnDgPrex4uO0Ra5kSRNlZ4R3xKgE4RrQ-l3eSx92_C9Tz7Qzxx3jgLixNLP1z9iVFOJw3R7yF9zRJhC1gTDP0iKJZtiVHYbT8YXf8IhiapRURsZgZqWrdXMRyVzg2XLcyPIAZvcl0Qja7bimQr6T9bQL5TUPqy0QHhYx1K73cdo-KJMwNpD8vU6NuUU8Ux2ygOwhJpdtYLNb6wjdHs9HWwi8uOmIUijDeSlaq-jLCtNDpi9grcCV7SGZC',
  quant:  'https://lh3.googleusercontent.com/aida-public/AB6AXuA_Zh5VZPRr36YAjHM2_mwc9qyvwpqHJidM8GdKTUFql2DeeuoBfZ2tSLenUEp3yeBKkBSEsOH87oU4yDkcuJvRVcNad5kTMZd1lfCZ0D7MziS_tZPF8zKdOnLycSCZxO7rX1jml-Bg7yvaRSHmpd6exQU0V-hMe-peXCflT_TpQ987Vc4eM8MK2OB4KawZFxH38unZm7f2Xn-ihkHuQHDZ39NX5pp-_UMnr_bN-twnt5AR6pqXZe786G6h4mrNZWnEurXcS4Pa3fHh',
}

// 角色副标题映射
const ROLE_MAP = {
  jun:      '龙头战法',
  qiao:     '板块轮动',
  jia:      '低位潜伏',
  speed:    '打板专家',
  trend:    '中线波段',
  quant:    '算法回测',
  deepseek: '深度推理',
  beijing:  '游资打板',
}

// ─── 主力智能体头寸 ──────────────────────────────────────────────────────
const stanceAgents = computed(() => {
  const results = apiData.value?.agentResults ?? []
  return results.map(r => {
    const s = r.structured || {}
    const id = r.agent_id || s.agentId || ''
    return {
      name:     r.agent_name || s.agentName || getAgentName(id),
      role:     ROLE_MAP[id] || s.agentName || '',
      stance:   s.stance || 'neutral',
      tagLabel: (stanceMeta(s.stance || 'neutral')).tagLabel,
      confidence: s.confidence ?? 50,
      avatar:   AVATARS[id] || AVATARS.jun,
    }
  })
})

// ─── TOP 3 机会 ──────────────────────────────────────────────────────────
const opportunities = computed(() => apiData.value?.consensusOpportunities ?? [])

// ─── 深度洞察 ────────────────────────────────────────────────────────────
const deepInsight = computed(() => {
  const results = apiData.value?.agentResults ?? []
  if (!results.length) return ''
  const bullish = results.filter(r => (r.structured?.stance) === 'bull').length
  const bearish = results.filter(r => (r.structured?.stance) === 'bear').length
  if (bullish >= 4) return '多数智能体对科技板块持防御态势，资金正明显向能源与高股息蓝筹板块轮动。当前市场分歧点在于消费复苏的斜率，但整体仓位建议保持在 70% 左右，利用回调布局政策对冲板块。'
  if (bearish >= 2) return '部分智能体对短期市场持谨慎态度，建议控制仓位防御为主，等待市场情绪企稳后再布局。'
  return '各智能体观点分化，建议保持中性仓位，关注轮动节奏，做好止盈止损。'
})

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/strategy/agents')
}
</script>

<style scoped>
.asd-page {
  --primary: #4a47d2;
  --primary-mid: #6462ec;
  --on-surface: #1a1c1f;
  --on-var: #414755;
  --surface: #f9f9fe;
  --low: #f3f3f8;
  --high: #e8e8ed;
  --white: #ffffff;
  --up: #f23645;
  --up-bright: #fb7185;
  --chip-bg: rgba(242, 54, 69, 0.16);
  --chip-on: #7f1d1d;
  --down: #089981;
  --err-bg: #ffdad6;
  --err-on: #93000a;
  --neutral-bg: #e2dfe1;
  --neutral-on: #636264;
  --track: #ededf2;

  min-height: 100vh;
  min-height: 100dvh;
  background: var(--surface);
  color: var(--on-surface);
  padding-bottom: calc(88px + env(safe-area-inset-bottom, 0));
  font-family: 'Inter', var(--font, system-ui, sans-serif);
  -webkit-font-smoothing: antialiased;
}

.asd-header {
  position: sticky;
  top: 0;
  z-index: 40;
  display: grid;
  grid-template-columns: 44px 1fr 44px;
  align-items: center;
  gap: 8px;
  padding: calc(10px + env(safe-area-inset-top, 0)) 12px 12px;
  background: rgba(249, 249, 254, 0.88);
  backdrop-filter: blur(16px);
  box-shadow: 0 24px 64px rgba(26, 28, 31, 0.04);
}

.asd-back {
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: var(--primary);
}
.asd-back:active {
  background: rgba(74, 71, 210, 0.08);
}

.asd-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: center;
  min-width: 0;
}

.asd-brand__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  background: var(--primary-mid);
}

.asd-brand__title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.asd-icon {
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: var(--on-var);
  justify-self: end;
}
.asd-icon:active {
  background: rgba(0, 0, 0, 0.05);
}

.asd-main {
  max-width: 1100px;
  margin: 0 auto;
  padding: 16px 16px 28px;
}

.asd-headline {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 28px;
}

@media (min-width: 720px) {
  .asd-headline {
    flex-direction: row;
    align-items: flex-end;
    justify-content: space-between;
  }
}

.asd-kicker {
  margin: 0 0 6px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--primary);
}

.asd-title {
  margin: 0;
  font-size: clamp(1.65rem, 4vw, 2.25rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.15;
}

.asd-headline__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.asd-sync {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 12px;
  background: var(--low);
  font-size: 13px;
  font-weight: 600;
  color: var(--on-var);
}

.asd-sync__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--up-bright);
  animation: asd-pulse 1.8s ease-in-out infinite;
}

@keyframes asd-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.45;
  }
}

.asd-btn-primary {
  padding: 10px 20px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 700;
  color: #fff;
  background: var(--primary);
  box-shadow: 0 8px 24px rgba(74, 71, 210, 0.22);
}
.asd-btn-primary:active {
  opacity: 0.92;
  transform: scale(0.98);
}

.asd-grid {
  display: grid;
  gap: 24px;
}

@media (min-width: 1024px) {
  .asd-grid {
    grid-template-columns: 1fr 2fr;
    align-items: start;
  }
}

.asd-col {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.asd-card {
  background: var(--white);
  border-radius: 1.75rem;
  box-shadow: 0 24px 64px rgba(26, 28, 31, 0.04);
  outline: 1px solid rgba(193, 198, 215, 0.1);
}

.asd-card-label {
  margin: 0 0 18px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(65, 71, 85, 0.65);
}

.asd-gauge-card {
  position: relative;
  overflow: hidden;
  padding: 26px 22px 28px;
}

.asd-gauge-wrap {
  position: relative;
  z-index: 1;
}

.asd-gauge {
  position: relative;
  width: min(192px, 70vw);
  height: min(192px, 70vw);
  margin: 0 auto;
}

.asd-gauge__svg {
  width: 100%;
  height: 100%;
}

.asd-gauge__track {
  stroke: var(--track);
}

.asd-gauge__prog {
  transition: stroke-dashoffset 1s ease-out;
}

.asd-gauge__center {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
}

.asd-gauge__num {
  font-size: 2.75rem;
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1;
}

.asd-gauge__pct {
  font-size: 1.15rem;
  font-weight: 600;
  color: rgba(65, 71, 85, 0.55);
  align-self: flex-end;
  margin-bottom: 8px;
}

.asd-gauge__foot {
  text-align: center;
  margin-top: 22px;
}

.asd-bull-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 999px;
  background: var(--chip-bg);
  color: var(--chip-on);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.asd-bull-pill__ico {
  font-size: 13px;
  font-weight: 900;
}

.asd-gauge__sub {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--on-var);
}

.asd-gauge__glow {
  position: absolute;
  right: -32px;
  bottom: -32px;
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: rgba(74, 71, 210, 0.06);
  filter: blur(28px);
  pointer-events: none;
}

.asd-insight {
  padding: 24px 22px;
  border-left: 4px solid var(--primary);
}

.asd-insight__head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.asd-insight__ico {
  color: var(--primary);
  fill: currentColor;
}

.asd-insight__title {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
}

.asd-insight__body {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  font-weight: 500;
  color: var(--on-var);
}

.asd-section-h {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  padding: 0 4px;
}

.asd-section-h__title {
  margin: 0;
  font-size: 17px;
  font-weight: 800;
}

.asd-section-h__link {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--primary);
}

.asd-agents {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

@media (min-width: 520px) {
  .asd-agents {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 900px) {
  .asd-agents {
    grid-template-columns: repeat(3, 1fr);
  }
}

.asd-agent {
  padding: 18px 16px;
  border-radius: 1rem;
  background: var(--low);
  transition: background 0.2s ease, box-shadow 0.2s ease;
}
.asd-agent:hover {
  background: var(--white);
  box-shadow: 0 12px 40px rgba(26, 28, 31, 0.08);
}

.asd-agent--bear {
  border-left: 4px solid var(--down);
}

.asd-agent__row1 {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.asd-agent__who {
  display: flex;
  gap: 10px;
  min-width: 0;
}

.asd-agent__av {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  overflow: hidden;
  background: var(--high);
  flex-shrink: 0;
}
.asd-agent__av img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.asd-agent__name {
  margin: 0 0 2px;
  font-size: 14px;
  font-weight: 800;
}

.asd-agent__role {
  margin: 0;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: rgba(65, 71, 85, 0.55);
}

.asd-agent__arrow {
  font-size: 18px;
  font-weight: 900;
  line-height: 1;
}
.asd-agent__arrow.tone-bull {
  color: var(--up-bright);
}
.asd-agent__arrow.tone-bear {
  color: var(--down);
}
.asd-agent__arrow.tone-neutral {
  color: #717786;
}

.asd-agent__row2 {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.asd-tag {
  font-size: 11px;
  font-weight: 800;
  padding: 4px 10px;
  border-radius: 999px;
}
.asd-tag--bull {
  background: var(--chip-bg);
  color: var(--chip-on);
}
.asd-tag--bear {
  background: var(--err-bg);
  color: var(--err-on);
}
.asd-tag--neutral {
  background: var(--neutral-bg);
  color: var(--neutral-on);
}

.asd-conf {
  font-size: 10px;
  font-weight: 600;
  color: var(--on-var);
}

.asd-top3 {
  overflow: hidden;
}

.asd-top3__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--track);
}

.asd-top3__head-l {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.asd-top3__head-l .icon {
  color: var(--primary);
  flex-shrink: 0;
}

.asd-top3__title {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
}

.asd-top3__time {
  font-size: 10px;
  font-weight: 800;
  color: rgba(65, 71, 85, 0.45);
  flex-shrink: 0;
}

.asd-top3__list {
  display: flex;
  flex-direction: column;
}

.asd-opp {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 18px 20px;
  text-align: left;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--track);
  cursor: pointer;
  transition: background 0.15s ease;
}
.asd-opp:last-child {
  border-bottom: none;
}
.asd-opp:hover,
.asd-opp:active {
  background: var(--low);
}

.asd-opp__left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.asd-opp__rank {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--low);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 800;
  color: var(--primary);
  flex-shrink: 0;
}

.asd-opp__title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.asd-opp__name {
  font-size: 16px;
  font-weight: 800;
}

.asd-opp__badge {
  font-size: 10px;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
.bdg-primary {
  background: rgba(74, 71, 210, 0.1);
  color: var(--primary);
}
.bdg-muted {
  background: var(--neutral-bg);
  color: #474649;
}

.asd-opp__meta {
  margin: 0;
  font-size: 12px;
  color: var(--on-var);
}

.asd-opp__right {
  text-align: right;
  flex-shrink: 0;
}

.asd-opp__chg {
  margin: 0 0 4px;
  font-size: 17px;
  font-weight: 800;
}

.asd-opp__chg.up {
  color: var(--up);
}
.asd-opp__chg.down {
  color: var(--down);
}

.asd-opp__flow {
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  font-size: 10px;
  font-weight: 700;
  color: rgba(65, 71, 85, 0.55);
}

.asd-opp__flow-ico {
  opacity: 0.7;
}

.asd-note {
  margin-top: 28px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--on-var);
}

/* ── 加载状态 ──────────────────────────────────────────────── */
.asd-sync--loading .asd-sync__dot {
  animation: asd-pulse 1s ease-in-out infinite;
}

.asd-skeleton {
  height: 52px;
  background: linear-gradient(90deg, var(--low) 25%, var(--high) 50%, var(--low) 75%);
  background-size: 200% 100%;
  animation: asd-shimmer 1.4s ease infinite;
  border-radius: 8px;
}

@keyframes asd-shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.asd-loading-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(249, 249, 254, 0.7);
  backdrop-filter: blur(8px);
}

.asd-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--low);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: asd-spin 0.8s linear infinite;
}

@keyframes asd-spin {
  to { transform: rotate(360deg); }
}

.asd-error {
  margin-top: 8px;
  padding: 8px 14px;
  border-radius: 8px;
  background: rgba(186, 26, 26, 0.08);
  color: var(--down);
  font-size: 12px;
}

/* ── 模式切换 ──────────────────────────────────────────────── */
.asd-mode-toggle {
  display: flex;
  background: var(--low);
  border-radius: 10px;
  padding: 3px;
  gap: 2px;
}

.asd-mode-btn {
  padding: 6px 12px;
  border-radius: 8px;
  border: none;
  background: transparent;
  font-size: 12px;
  font-weight: 600;
  color: var(--on-var);
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  gap: 4px;
}

.asd-mode-btn--active {
  background: var(--white);
  color: var(--primary);
  box-shadow: 0 2px 8px rgba(74, 71, 210, 0.15);
}

.asd-mode-btn__icon {
  font-size: 14px;
}

/* ── 主控分析卡片 ──────────────────────────────────────────────── */
.asd-master-card {
  background: var(--white);
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(26, 28, 31, 0.04);
  outline: 1px solid rgba(193, 198, 215, 0.12);
  overflow: hidden;
}

.asd-master-card__header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 18px;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-mid) 100%);
  color: #fff;
}

.asd-master-card__icon {
  width: 24px;
  height: 24px;
  fill: currentColor;
}

.asd-master-card__title {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
  flex: 1;
}

.asd-master-card__phase {
  font-size: 11px;
  font-weight: 700;
  padding: 4px 10px;
  background: rgba(255,255,255,0.2);
  border-radius: 999px;
}

.asd-master-card__body {
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.asd-master-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.asd-master-item__label {
  font-size: 11px;
  font-weight: 700;
  color: var(--on-var);
  min-width: 72px;
  flex-shrink: 0;
}

.asd-master-item__value {
  font-size: 13px;
  color: var(--on-surface);
  line-height: 1.5;
}

.asd-master-item__value--highlight {
  color: var(--primary);
  font-weight: 700;
}

.asd-master-item__badge {
  font-size: 12px;
  font-weight: 800;
  padding: 3px 10px;
  border-radius: 999px;
}

.badge--high {
  background: rgba(242, 54, 69, 0.1);
  color: #f23645;
}

.badge--medium {
  background: rgba(74, 71, 210, 0.1);
  color: var(--primary);
}

.badge--low {
  background: rgba(8, 153, 129, 0.1);
  color: #089981;
}

.asd-master-item--priority {
  flex-direction: column;
  gap: 8px;
}

.asd-master-priority {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.asd-master-priority__tag {
  font-size: 11px;
  font-weight: 700;
  padding: 4px 10px;
  background: var(--low);
  border-radius: 6px;
  color: var(--on-var);
}

.asd-master-priority__tag--high {
  background: rgba(74, 71, 210, 0.12);
  color: var(--primary);
}

.asd-master-item--notes {
  flex-direction: column;
  gap: 6px;
  padding-top: 12px;
  border-top: 1px solid var(--track);
}

/* ── 执行日志卡片 ──────────────────────────────────────────────── */
.asd-log-card {
  background: var(--white);
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(26, 28, 31, 0.04);
  outline: 1px solid rgba(193, 198, 215, 0.12);
  overflow: hidden;
}

.asd-log-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--track);
}

.asd-log-card__header .icon {
  width: 18px;
  height: 18px;
  color: var(--primary);
  fill: currentColor;
}

.asd-log-card__title {
  margin: 0;
  font-size: 14px;
  font-weight: 800;
  flex: 1;
}

.asd-log-card__count {
  font-size: 11px;
  font-weight: 700;
  color: var(--on-var);
  background: var(--low);
  padding: 3px 8px;
  border-radius: 999px;
}

.asd-log-card__body {
  padding: 12px 18px;
  max-height: 200px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.asd-log-entry {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 12px;
  line-height: 1.5;
}

.asd-log-entry__phase {
  font-size: 10px;
  font-weight: 700;
  color: var(--primary);
  background: rgba(74, 71, 210, 0.08);
  padding: 2px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.asd-log-entry__agent {
  font-weight: 700;
  color: var(--on-surface);
  min-width: 60px;
}

.asd-log-entry__status {
  font-size: 12px;
  flex-shrink: 0;
}

.asd-log-entry__msg {
  color: var(--on-var);
  flex: 1;
}

.asd-log-entry--COMPLETED .asd-log-entry__status { color: #089981; }
.asd-log-entry--RUNNING .asd-log-entry__status { color: var(--primary); }
.asd-log-entry--FAILED .asd-log-entry__status { color: #f23645; }

/* ── 综合建议 ──────────────────────────────────────────────── */
.asd-synthesis {
  white-space: pre-wrap;
  font-size: 12px;
  line-height: 1.8;
}
</style>
