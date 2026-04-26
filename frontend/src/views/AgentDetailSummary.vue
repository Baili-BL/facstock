/**
 * AgentDetailSummary — 策略详情页（QuantWing Corporate Modern 设计）
 * 路由: /strategy/agents/:id/summary
 * 数据来源: AgentProfile (coreObjective, hardRules, style, tagline, role, etc.)
 */
<template>
  <div class="sdp-page">
    <!-- TopAppBar -->
    <header class="sdp-header">
      <button type="button" class="sdp-header__back" aria-label="返回" @click="goBack">
        <span class="material-symbols-outlined">arrow_back</span>
      </button>
      <h1 class="sdp-header__brand">QuantWing</h1>
      <button type="button" class="sdp-header__share" aria-label="分享" @click="handleShare">
        <span class="material-symbols-outlined">share</span>
      </button>
    </header>

    <main class="sdp-main">
      <!-- 加载中 -->
      <div v-if="isLoading && !agentProfile" class="sdp-loading">
        <div class="sdp-loading__spinner" />
        <p class="sdp-loading__text">正在加载策略详情…</p>
      </div>

      <!-- 策略详情内容 -->
      <template v-else-if="agentProfile">
        <!-- Header Section -->
        <section class="sdp-hero">
          <div class="sdp-hero__title-row">
            <h2 class="sdp-hero__title">{{ agentProfile.name }}</h2>
            <span class="sdp-hero__badge">{{ agentStatus }}</span>
          </div>
          <p class="sdp-hero__subtitle">{{ agentProfile.tagline }}</p>
        </section>

        <!-- Section 1: Core Philosophy -->
        <section class="sdp-section sdp-section--core">
          <div class="sdp-section__deco" />
          <div class="sdp-section__header">
            <span class="material-symbols-outlined sdp-section__icon">psychology</span>
            <h3 class="sdp-section__title">策略核心理念</h3>
          </div>
          <p class="sdp-section__body">{{ agentProfile.coreObjective }}</p>
        </section>

        <!-- Section 2: Methodology Steps -->
        <section class="sdp-section">
          <div class="sdp-section__header">
            <span class="material-symbols-outlined sdp-section__icon">architecture</span>
            <h3 class="sdp-section__title">方法论步骤</h3>
          </div>
          <div class="sdp-steps">
            <!-- 连接线 -->
            <div class="sdp-steps__track" />
            <!-- Steps -->
            <div
              v-for="(step, i) in methodologySteps"
              :key="i"
              class="sdp-step"
              :class="{ 'sdp-step--primary': i === 0 }"
            >
              <div class="sdp-step__dot">{{ i + 1 }}</div>
              <div class="sdp-step__content">
                <h4 class="sdp-step__title">{{ step.title }}</h4>
                <p class="sdp-step__desc">{{ step.desc }}</p>
              </div>
            </div>
          </div>
        </section>

        <!-- Section 3: Hard Rules -->
        <section class="sdp-section">
          <div class="sdp-section__header">
            <span class="material-symbols-outlined sdp-section__icon">gavel</span>
            <h3 class="sdp-section__title">硬规则</h3>
          </div>
          <div class="sdp-rules-grid">
            <div
              v-for="(rule, i) in displayHardRules"
              :key="i"
              class="sdp-rule-item"
            >
              <span class="material-symbols-outlined sdp-rule-item__check">check_circle</span>
              <span class="sdp-rule-item__text">{{ rule }}</span>
            </div>
          </div>
        </section>

        <!-- Section 4: Agent Meta -->
        <section class="sdp-section sdp-section--meta">
          <div class="sdp-section__header">
            <span class="material-symbols-outlined sdp-section__icon">info</span>
            <h3 class="sdp-section__title">策略属性</h3>
          </div>
          <div class="sdp-meta-grid">
            <div class="sdp-meta-item">
              <span class="sdp-meta-item__label">投资风格</span>
              <span class="sdp-meta-item__value">{{ agentProfile.styleCategory || agentProfile.style || '—' }}</span>
            </div>
            <div class="sdp-meta-item">
              <span class="sdp-meta-item__label">持仓风格</span>
              <span class="sdp-meta-item__value">{{ agentProfile.holdingStyle || '—' }}</span>
            </div>
            <div class="sdp-meta-item">
              <span class="sdp-meta-item__label">工具策略</span>
              <span class="sdp-meta-item__value">{{ formatPolicy(agentProfile.toolPolicy) }}</span>
            </div>
            <div class="sdp-meta-item">
              <span class="sdp-meta-item__label">输入维度</span>
              <span class="sdp-meta-item__value">{{ (agentProfile.requiredInputs || []).length }} 个核心输入</span>
            </div>
          </div>

          <!-- 输出焦点 -->
          <div v-if="(agentProfile.outputFocus || []).length" class="sdp-outputs">
            <span class="sdp-outputs__label">关键输出</span>
            <div class="sdp-outputs__chips">
              <span v-for="(focus, i) in agentProfile.outputFocus" :key="i" class="sdp-chip">{{ focus }}</span>
            </div>
          </div>
        </section>

        <!-- Action Buttons -->
        <section class="sdp-actions">
          <button type="button" class="sdp-btn sdp-btn--secondary" @click="goToHoldings">
            <span class="material-symbols-outlined">account_balance_wallet</span>
            <span>查看持仓</span>
          </button>
          <button type="button" class="sdp-btn sdp-btn--primary" @click="goToAnalysis">
            <span class="material-symbols-outlined">query_stats</span>
            <span>查看分析</span>
          </button>
        </section>
      </template>

      <!-- 无数据 -->
      <div v-if="!isLoading && !agentProfile && !fetchError" class="sdp-empty">
        <span class="material-symbols-outlined sdp-empty__ico">info</span>
        <p class="sdp-empty__title">未找到该策略</p>
        <p class="sdp-empty__sub">该智能体暂未配置策略详情</p>
      </div>

      <!-- 错误状态 -->
      <div v-if="fetchError" class="sdp-empty">
        <span class="material-symbols-outlined sdp-empty__ico">error</span>
        <p class="sdp-empty__title">加载失败</p>
        <p class="sdp-empty__sub">{{ fetchError }}</p>
        <button type="button" class="sdp-btn sdp-btn--secondary sdp-btn--sm" @click="loadProfile">重试</button>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchAgentProfile } from '@/api/agents.js'

const route = useRoute()
const router = useRouter()

const basePath = computed(() =>
  route.path.startsWith('/strategy/youzi_agents') ? '/strategy/youzi_agents' : '/strategy/agents'
)

const agentId = computed(() => route.params.id || 'jun')
const agentProfile = ref(null)
const isLoading = ref(true)
const fetchError = ref('')

// 策略状态标签
const agentStatus = computed(() => {
  if (!agentProfile.value) return '待分析'
  const style = (agentProfile.value.styleCategory || agentProfile.value.style || '').toLowerCase()
  if (style.includes('龙头') || style.includes('板')) return '激进型'
  if (style.includes('趋势') || style.includes('波段')) return '稳健型'
  if (style.includes('潜伏') || style.includes('低位')) return '价值型'
  if (style.includes('量化') || style.includes('算法')) return '数据型'
  return '待分析'
})

// 方法论步骤（从 coreObjective 智能推断）
const methodologySteps = computed(() => {
  const objective = agentProfile.value?.coreObjective || ''
  const style = (agentProfile.value?.styleCategory || agentProfile.value?.style || '').toLowerCase()
  const adviseType = agentProfile.value?.adviseType || ''
  const phase = agentProfile.value?.phase || ''

  // 基于风格和类型生成合理的方法论步骤
  if (style.includes('龙头') || adviseType.includes('板')) {
    return [
      { title: '市场情绪感知', desc: '追踪板块联动效应，捕捉龙头股涨停信号与情绪转折点。' },
      { title: '涨停板识别', desc: '识别强势涨停个股，分析封板力度与市场资金流向。' },
      { title: '次日溢价预判', desc: '评估隔日高开概率，制定止盈止损策略。' },
    ]
  }
  if (style.includes('潜伏') || style.includes('低位')) {
    return [
      { title: '估值筛选', desc: '通过基本面数据筛选低估值标的，建立候选池。' },
      { title: '趋势确认', desc: '结合量价关系确认底部启动信号，等待右侧入场点。' },
      { title: '潜伏持仓', desc: '分批建仓，控制成本，耐心等待价值回归。' },
    ]
  }
  if (style.includes('趋势') || style.includes('波段')) {
    return [
      { title: '趋势识别', desc: '通过均线系统与动量指标判断当前趋势方向与强度。' },
      { title: '波段机会捕捉', desc: '识别趋势中的回调与反弹机会，优化入场时机。' },
      { title: '仓位动态管理', desc: '根据趋势强度调整持仓，实现收益最大化。' },
    ]
  }
  if (style.includes('量化') || style.includes('算法')) {
    return [
      { title: '数据清洗与预处理', desc: '剔除异常值，处理缺失数据，确保输入因子质量与连续性。' },
      { title: '多因子合成', desc: '运用 PCA 等降维技术，将动量、价值、波动率等因子进行正交化合成。' },
      { title: '风险模型约束', desc: '基于 Barra 风险模型进行行业与风格中性化，严格控制敞口暴露。' },
    ]
  }
  if (style.includes('轮动') || adviseType.includes('板块')) {
    return [
      { title: '板块轮动追踪', desc: '监控市场板块间的资金流向，识别当前主导热点。' },
      { title: '轮动节奏分析', desc: '分析板块轮动周期，预判下一个潜在热点方向。' },
      { title: '切换决策', desc: '在龙头板块间动态切换，优化持仓结构。' },
    ]
  }
  if (phase === 'phase_1') {
    return [
      { title: '题材分析', desc: '深入解读市场题材，评估题材的持续性与想象空间。' },
      { title: '情绪量化', desc: '通过资金流向与涨停家数等指标量化市场情绪温度。' },
      { title: '题材排序', desc: '对候选题材进行综合评分，优选最强方向。' },
    ]
  }
  // 默认步骤
  return [
    { title: '市场数据分析', desc: '整合量价数据与基本面信息，全面评估市场状态。' },
    { title: '信号生成', desc: '基于策略规则库识别符合条件的交易机会。' },
    { title: '策略输出', desc: '生成包含置信度的操作建议与风险提示。' },
  ]
})

// 硬规则展示（最多4条）
const displayHardRules = computed(() => {
  const rules = agentProfile.value?.hardRules || []
  if (rules.length > 0) return rules.slice(0, 4)
  // 兜底硬规则
  return [
    '单只标的权重占比 ≤ 5%',
    '最大日内回撤触发平仓阈值 3%',
    '避开业绩披露期高波动时间窗口',
    '换手率年化限制 ≤ 500%',
  ]
})

// 加载数据
async function loadProfile() {
  isLoading.value = true
  fetchError.value = ''
  try {
    const data = await fetchAgentProfile(agentId.value)
    agentProfile.value = data
  } catch (e) {
    fetchError.value = e.message || '加载失败，请稍后重试'
  } finally {
    isLoading.value = false
  }
}

// 格式化工具策略
function formatPolicy(policy) {
  const map = {
    shared_context_only: '只读共享事实',
    shared_context_first: '共享事实优先',
    selective_market_tools: '精选行情工具',
    market_board_tools: '涨停板工具',
    data_driven: '数据驱动',
  }
  return map[policy] || policy || '默认策略'
}

// 导航
function goBack() {
  if (window.history.length > 1) router.back()
  else router.push(basePath.value)
}

function goToHoldings() {
  router.push(`${basePath.value}/${agentId.value}`)
}

function goToAnalysis() {
  router.push(`${basePath.value}/${agentId.value}/summary`)
}

function handleShare() {
  if (navigator.share) {
    navigator.share({
      title: `${agentProfile.value?.name || '策略'} - QuantWing`,
      text: agentProfile.value?.tagline || agentProfile.value?.coreObjective || '',
      url: window.location.href,
    }).catch(() => {})
  }
}

onMounted(loadProfile)
</script>

<style scoped>
/* ── Design Tokens (QuantWing) ─────────────────────────────────────────── */
.sdp-page {
  --primary: #002045;
  --primary-container: #1b365c;
  --on-primary-container: #879fcb;
  --on-primary: #ffffff;
  --surface: #f7fafc;
  --surface-dim: #d7dadc;
  --surface-bright: #f7fafc;
  --surface-container-lowest: #ffffff;
  --surface-container-low: #f1f4f6;
  --surface-container: #ebeef0;
  --surface-container-high: #e5e9eb;
  --surface-container-highest: #e0e3e5;
  --on-surface: #181c1e;
  --on-surface-variant: #43474e;
  --primary-fixed: #d6e3ff;
  --secondary-container: #ead9fe;
  --on-secondary-container: #6a5d7c;
  --tertiary: #27006a;
  --tertiary-fixed: #e8ddff;
  --on-tertiary-fixed: #21005e;
  --outline: #74777f;
  --outline-variant: #c4c6cf;

  font-family: 'Manrope', system-ui, sans-serif;
  background: var(--surface);
  color: var(--on-surface);
  min-height: 100vh;
  min-height: 100dvh;
  padding-bottom: calc(40px + env(safe-area-inset-bottom, 0));
}

/* ── Material Symbols ──────────────────────────────────────────────────── */
.material-symbols-outlined {
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  font-size: 20px;
}

/* ── Header ────────────────────────────────────────────────────────────── */
.sdp-header {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: calc(12px + env(safe-area-inset-top, 0)) 16px 12px;
  background: rgba(247, 250, 252, 0.88);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--surface-container-high);
}

.sdp-header__back,
.sdp-header__share {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
  background: transparent;
  transition: background 0.2s;
  flex-shrink: 0;
}

.sdp-header__back:active,
.sdp-header__share:active {
  background: rgba(0, 32, 69, 0.08);
}

.sdp-header__brand {
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 17px;
  letter-spacing: -0.02em;
  color: var(--primary);
  margin: 0;
}

/* ── Main Content ──────────────────────────────────────────────────────── */
.sdp-main {
  max-width: 768px;
  margin: 0 auto;
  padding: 24px 16px 0;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* ── Loading ──────────────────────────────────────────────────────────── */
.sdp-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 60px 0;
}

.sdp-loading__spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--surface-container);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: sdp-spin 0.8s linear infinite;
}

.sdp-loading__text {
  font-size: 14px;
  color: var(--on-surface-variant);
  margin: 0;
}

@keyframes sdp-spin {
  to { transform: rotate(360deg); }
}

/* ── Hero Section ─────────────────────────────────────────────────────── */
.sdp-hero {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sdp-hero__title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.sdp-hero__title {
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 32px;
  line-height: 40px;
  letter-spacing: -0.02em;
  color: var(--primary);
  margin: 0;
}

.sdp-hero__badge {
  display: inline-block;
  padding: 4px 14px;
  border-radius: 999px;
  background: var(--secondary-container);
  color: var(--on-secondary-container);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.sdp-hero__subtitle {
  font-size: 16px;
  line-height: 24px;
  color: var(--on-surface-variant);
  margin: 0;
}

/* ── Section Card ─────────────────────────────────────────────────────── */
.sdp-section {
  background: var(--surface-container-lowest);
  border-radius: 24px;
  padding: 24px;
  box-shadow: 0 8px 30px rgba(26, 54, 93, 0.04);
  border: 1px solid var(--surface-container-high);
  position: relative;
  overflow: hidden;
}

.sdp-section--core {
  background: linear-gradient(135deg, rgba(214, 227, 255, 0.3) 0%, transparent 60%);
}

.sdp-section__deco {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(214, 227, 255, 0.15) 0%, transparent 50%);
  pointer-events: none;
}

.sdp-section__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  position: relative;
  z-index: 1;
}

.sdp-section__icon {
  color: var(--primary);
  font-size: 22px !important;
}

.sdp-section__title {
  font-family: 'Manrope', sans-serif;
  font-weight: 600;
  font-size: 20px;
  line-height: 28px;
  color: var(--primary);
  margin: 0;
}

.sdp-section__body {
  font-size: 16px;
  line-height: 24px;
  color: var(--on-surface-variant);
  margin: 0;
  position: relative;
  z-index: 1;
}

/* ── Steps ────────────────────────────────────────────────────────────── */
.sdp-steps {
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: relative;
  z-index: 1;
}

.sdp-steps__track {
  position: absolute;
  left: 15px;
  top: 24px;
  bottom: 24px;
  width: 2px;
  background: var(--surface-container-high);
  z-index: 0;
}

.sdp-step {
  display: flex;
  gap: 16px;
  position: relative;
  z-index: 1;
}

.sdp-step__dot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--surface-container-highest);
  color: var(--on-surface);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Manrope', sans-serif;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
  border: 4px solid var(--surface-container-lowest);
}

.sdp-step--primary .sdp-step__dot {
  background: var(--primary-container);
  color: var(--on-primary);
  border-color: var(--surface-container-lowest);
}

.sdp-step__content {
  padding-top: 4px;
  flex: 1;
}

.sdp-step__title {
  font-family: 'Manrope', sans-serif;
  font-weight: 600;
  font-size: 14px;
  line-height: 16px;
  color: var(--on-surface);
  margin: 0 0 6px;
}

.sdp-step__desc {
  font-size: 14px;
  line-height: 20px;
  color: var(--on-surface-variant);
  margin: 0;
}

/* ── Hard Rules Grid ──────────────────────────────────────────────────── */
.sdp-rules-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  position: relative;
  z-index: 1;
}

@media (min-width: 480px) {
  .sdp-rules-grid {
    grid-template-columns: 1fr 1fr;
  }
}

.sdp-rule-item {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface);
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid var(--surface-container-high);
}

.sdp-rule-item__check {
  color: var(--primary-container);
  font-size: 18px !important;
  flex-shrink: 0;
}

.sdp-rule-item__text {
  font-size: 14px;
  line-height: 20px;
  color: var(--on-surface);
}

/* ── Meta Grid ────────────────────────────────────────────────────────── */
.sdp-section--meta {
  background: var(--surface-container-lowest);
}

.sdp-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
  position: relative;
  z-index: 1;
}

.sdp-meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sdp-meta-item__label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--on-surface-variant);
}

.sdp-meta-item__value {
  font-size: 14px;
  font-weight: 500;
  color: var(--on-surface);
  line-height: 20px;
}

/* ── Output Chips ─────────────────────────────────────────────────────── */
.sdp-outputs {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid var(--surface-container-high);
  position: relative;
  z-index: 1;
}

.sdp-outputs__label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--on-surface-variant);
}

.sdp-outputs__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sdp-chip {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 999px;
  background: var(--secondary-container);
  color: var(--on-secondary-container);
  font-size: 12px;
  font-weight: 600;
}

/* ── Action Buttons ───────────────────────────────────────────────────── */
.sdp-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  padding: 4px 0 32px;
}

.sdp-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px 20px;
  border-radius: 12px;
  font-family: 'Manrope', sans-serif;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid;
}

.sdp-btn .material-symbols-outlined {
  font-size: 18px !important;
}

.sdp-btn--primary {
  background: var(--primary);
  color: var(--on-primary);
  border-color: var(--primary);
  box-shadow: 0 4px 16px rgba(0, 32, 69, 0.2);
}

.sdp-btn--primary:active {
  background: var(--primary-container);
  border-color: var(--primary-container);
  transform: scale(0.98);
}

.sdp-btn--secondary {
  background: var(--surface-container-lowest);
  color: var(--primary);
  border-color: var(--surface-container-high);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.sdp-btn--secondary:active {
  background: var(--surface-container-low);
  transform: scale(0.98);
}

.sdp-btn--sm {
  padding: 10px 16px;
  font-size: 13px;
  margin-top: 12px;
}

/* ── Empty State ──────────────────────────────────────────────────────── */
.sdp-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
  text-align: center;
}

.sdp-empty__ico {
  font-size: 48px !important;
  color: var(--outline-variant);
}

.sdp-empty__title {
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 18px;
  color: var(--on-surface);
  margin: 0;
}

.sdp-empty__sub {
  font-size: 13px;
  color: var(--on-surface-variant);
  margin: 0;
}
</style>
