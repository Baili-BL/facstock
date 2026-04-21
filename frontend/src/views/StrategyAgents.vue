<template>
  <div class="agents-page">
    <header class="agents-top">
      <button type="button" class="agents-top__back" aria-label="返回" @click="$router.push('/strategy')">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>

      <div class="agents-top__brand">
        <div class="agents-top__avatar" aria-hidden="true">
          <span class="agents-top__avatar-inner">游</span>
        </div>
        <h1 class="agents-top__title">游资智能体</h1>
      </div>

    </header>

    <main class="agents-main">
      <!-- ——— 游资智能体专家库 ——— -->
      <div class="agents-section-head">
        <div>
          <p class="agents-kicker">市场监测 · MARKET SURVEILLANCE</p>
          <h2 class="agents-h2">游资策略专家库</h2>
        </div>
        <span class="agents-pill">实时更新</span>
      </div>

      <!-- AI 全场总结 -->
      <router-link to="/strategy/ai/macro-summary" class="agents-hero">
        <div class="agents-hero__top">
          <div class="agents-hero__left">
            <div class="agents-hero__icon-wrap">
              <svg class="agents-hero__brain icon icon-xl" aria-hidden="true">
                <use href="#icon-ai" />
              </svg>
            </div>
            <div>
              <h3 class="agents-hero__title">AI 全场策略总结</h3>
              <p class="agents-hero__desc">汇总钧哥、乔帮主等 6 位顶尖智能体的共识意见</p>
            </div>
          </div>
          <div class="agents-hero__right">
            <span class="agents-hero__badge">核心大脑</span>
            <span class="agents-hero__arrow" aria-hidden="true">›</span>
          </div>
        </div>
        <div class="agents-hero__foot">
          <div class="agents-hero__faces">
            <img
              v-for="(u, i) in heroAvatars"
              :key="i"
              :src="u"
              alt=""
              class="agents-hero__face"
              loading="lazy"
            />
            <span class="agents-hero__more">+3</span>
          </div>
          <div class="agents-hero__consensus">
            策略共识度: <span class="agents-hero__pct">{{ consensusPct }}%</span>
          </div>
        </div>
      </router-link>

      <!-- 智能体卡片 -->
      <div class="agents-grid">
        <article
          v-for="(a, idx) in visibleAgents"
          :key="a.id"
          class="agent-card"
        >
          <div class="agent-card__head">
            <div class="agent-card__who">
              <div class="agent-card__img-wrap">
                <span class="agent-card__img agent-card__img--text" :aria-label="a.name">{{ agentCardInitial(a) }}</span>
                <span
                  class="agent-card__dot"
                  :class="{
                    'agent-card__dot--on': a.status === 'scanning' || a.status === 'active',
                    'agent-card__dot--off': a.status === 'offline',
                  }"
                />
              </div>
              <div>
                <h3 class="agent-card__name">{{ a.name }}</h3>
                <span class="agent-card__style">{{ a.style }}</span>
              </div>
            </div>
            <div
              class="agent-card__status"
              :class="{
                'agent-card__status--live': a.status === 'scanning' || a.status === 'active',
                'agent-card__status--off': a.status === 'offline',
              }"
            >
              <span class="agent-card__status-dot" />
              {{ statusLabel(a.status) }}
            </div>
          </div>
          <div class="agent-card__metrics">
            <div class="agent-metric">
              <p class="agent-metric__lbl">胜率</p>
              <p class="agent-metric__val tabular">{{ a.winRate }}%</p>
            </div>
            <div
              class="agent-metric agent-metric--accent"
              :class="{ 'agent-metric--neg': a.returnPct < 0 }"
            >
              <p class="agent-metric__lbl">收益率</p>
              <p class="agent-metric__val tabular" :class="a.returnPct >= 0 ? 'up' : 'down'">
                {{ a.returnPct >= 0 ? '+' : '' }}{{ a.returnPct }}%
              </p>
            </div>
          </div>
          <button
            type="button"
            class="agent-card__btn"
            :class="{ 'agent-card__btn--primary': idx === 0 }"
            @click="goToHoldings(a)"
          >
            查看持仓详情
          </button>
          <button
            type="button"
            class="agent-card__btn agent-card__btn--ai"
            @click="goToAnalysis(a)"
          >
            <svg class="icon icon-sm" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a9 9 0 0 1 9 9c0 3.12-1.6 5.87-4.03 7.54L17 17H7l.03-1.46C4.6 16.87 3 14.12 3 11a9 9 0 0 1 9-9zm0 2a7 7 0 1 0 0 14A7 7 0 0 0 12 4zm0 4a3 3 0 1 1 0 6 3 3 0 0 1 0-6zm0 2a1 1 0 0 1 1 1v4l3.29 3.29a1 1 0 0 1-1.41 1.42L12 15.41l-3.29 3.3a1 1 0 1 1-1.42-1.42L11 14V11a1 1 0 0 1 1-1z"/></svg>
            AI 分析
          </button>
        </article>
      </div>

      <!-- 感知洞察 -->
      <section class="agents-insight" aria-labelledby="insight-h">
        <div class="agents-insight__head">
          <span class="agents-insight__spark" aria-hidden="true">✦</span>
          <h3 id="insight-h" class="agents-insight__title">感知洞察</h3>
        </div>
        <p class="agents-insight__body" v-html="insightHtml" />
      </section>

      <p class="agents-disclaimer">
        AI 分析结果仅供参考，不构成投资建议。
      </p>
    </main>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { STRATEGY_AGENTS } from '@/data/strategyAgents.js'

const router = useRouter()

const consensusPct = ref(89)

// 从后端拉取各 Agent 真实胜率/收益率，覆盖静态数据
const agentPerf = ref({})

async function fetchAgentPerformance() {
  const ids = STRATEGY_AGENTS.map(a => a.id)
  await Promise.allSettled(ids.map(async (id) => {
    try {
      const res = await fetch(`/api/agents/${id}/performance`).then(r => r.json())
      if (res.success && res.data) agentPerf.value[id] = res.data
    } catch {}
  }))
}

onMounted(fetchAgentPerformance)

/** 历史记录（与 stitch code.html 对齐） */
const historyRecords = ref([
  {
    id: 'h1',
    date: '2026-10-24',
    title: '周度策略共识',
    sentiment: 'bullish',
    pctLabel: '75% 看多',
    summary:
      '重点关注区域贸易协议后的能源与中东基建项目。共识度高，预期公用事业板块将具有高流动性。',
    avatarChars: ['钧', '乔', '林', '王', '张', '李'],
    linkedLabel: '6 个智能体活跃',
    accentBorder: false,
  },
  {
    id: 'h2',
    date: '2026-10-21',
    title: '宏观同步快讯',
    sentiment: 'neutral',
    pctLabel: '48% 中性',
    summary: '建议持币观望。G7 国家利率波动导致成长股短期震荡。',
    avatarChars: ['钧', '乔', '林', '王', '张', '李'],
    linkedLabel: '6 个智能体活跃',
    accentBorder: true,
  },
  {
    id: 'h3',
    date: '2026-10-18',
    title: '收益率优化建议',
    sentiment: 'bearish',
    pctLabel: '15% 看空',
    summary: '主要半导体 ETF 出现离场信号。高收益债市场流动性紧缩建议转向避险策略。',
    avatarChars: ['钧', '乔', '林', '王', '张', '李'],
    linkedLabel: '6 个智能体活跃',
    accentBorder: false,
  },
])

function sentimentIcon(s) {
  if (s === 'bullish') return '↗'
  if (s === 'bearish') return '↘'
  return '—'
}

const heroAvatars = [
  'https://lh3.googleusercontent.com/aida-public/AB6AXuD97zD2NIGTCO_1tiXq1wsbA98aL5lltkwfWvGuW5ykcn7zacGqWOfQaC0Cgqq8Y70ssQbZDu4WTh34HYBodcl31NA-stzpx7g9dxTWCMuzM7s7gcIOeZVI8i8nHPZnB0F4J3ToG2bh9x5rvE7Qe3qAnETQRHznWRcVuYltPv923yduEQvww9hwsCd_YcKQjJrZK_VVNT5V0-w_9fQ5GDMZ9eGfWPxUPX4PFFDFtZaCN0EpwpuQSgMG_xOxIR3Btmz_rneBA88VIGp0',
  'https://lh3.googleusercontent.com/aida-public/AB6AXuAkvzyqjBc8b9-yrIA6kgiCLQcivIp4wH7WIrTQUKwzMfdOzv2XtxUV1wNrNrhfqeTLIsfBuwrA3EAr241oN4kTt-lHWYMl71AITtxC7_wt8A4nW5MoITPdKsNLCU-voyo3kk-xnCUKV3_3FlxK00PYxoASCqVuhe9VcRsOmbddONa0gr6gZFUpH1G88RrCpk-PROMttjpPhO7TZ0ni-GVtLFYsVapWVFGzL1FCMkpV35eb1k3IDjJCoTwR7-_RArQ6FiGkkFrFe9QP',
  'https://lh3.googleusercontent.com/aida-public/AB6AXuCGHKOsrw9P6UWNPtwRIbhOcdxdNbEN4ox5tJN9WMKrpuIDRMSGn8J3pzyTvreLu-7teIzU07GZxcA73Tcn15zCifb-gTMNKucYIvJRRtfnD8_yb5Lkp135iwwUdn2cR7vLp37g7uccbUfYOzGdXVQo5_HBrYIZiv5TgKFSeJ8t5-j0uQAu7VZkOuNLsDBQv8zcpObbrHC3y2ydOpBCzine4Ex3E-LQvcjIDCbWGcOWcetrGAmcOSofOp6KqiV9C8SjYZZV4crcvnKb',
]

const agents = STRATEGY_AGENTS

const visibleAgents = computed(() =>
  agents
    .filter((a) => a.status !== 'offline')
    .map((a) => {
      const perf = agentPerf.value[a.id]
      if (!perf) return a
      return {
        ...a,
        winRate: perf.analysisCount > 0 ? perf.winRate : a.winRate,
        returnPct: perf.analysisCount > 0 ? perf.returnPct : a.returnPct,
      }
    })
)

const insightHtml =
  '当前市场情绪处于<span class="agents-insight__quote">「极度亢奋」</span>阶段，建议重点关注 <strong>钧哥天下无双</strong> 的龙头标的选择，并在高位配合 <strong>量化之翼</strong> 的回撤预警。'

function statusLabel(s) {
  if (s === 'scanning') return '扫描中'
  if (s === 'active') return '活跃'
  return '离线'
}

function goToHoldings(a) {
  router.push(`/strategy/agents/${a.id}`)
}

function goToAnalysis(a) {
  router.push(`/strategy/agents/${a.id}/analysis`)
}

function agentCardInitial(a) {
  const s = String(a?.analysisBrand || a?.name || '?').trim()
  return s[0] || '?'
}
</script>

<style scoped>
/* DESIGN.md — Architectural Ledger tokens */
.agents-page {
  --primary: #4a47d2;
  --primary-mid: #6462ec;
  --on-surface: #1a1c1f;
  --on-surface-variant: #414755;
  --surface: #f9f9fe;
  --surface-low: #f3f3f8;
  --surface-high: #e8e8ed;
  --surface-highest: #e2e2e7;
  --outline-variant: rgba(193, 198, 215, 0.15);
  --tertiary: #089981;
  --tertiary-fixed: #f23645;
  --on-tertiary-fixed: #ffffff;
  --error: #f23645;
  --error-container: #ffdad6;
  --on-error-container: #93000a;
  --outline-soft: #717786;

  min-height: 100vh;
  min-height: 100dvh;
  background: var(--surface);
  color: var(--on-surface);
  padding-bottom: calc(88px + env(safe-area-inset-bottom, 0));
  font-family: 'Inter', var(--font, system-ui, sans-serif);
  -webkit-font-smoothing: antialiased;
}

.agents-top {
  position: sticky;
  top: 0;
  z-index: 40;
  display: grid;
  grid-template-columns: 44px 1fr auto;
  align-items: center;
  gap: 4px;
  padding: calc(12px + env(safe-area-inset-top, 0)) 10px 12px;
  background: var(--surface-low);
  box-shadow: 0 1px 0 var(--outline-variant);
}


.agents-top__back {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: var(--on-surface);
  opacity: 0.85;
}
.agents-top__back:active {
  background: rgba(0, 0, 0, 0.05);
}

.agents-top__brand {
  grid-column: 2;
  justify-self: center;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.agents-top__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e2dfff, #c2c1ff);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.agents-top__avatar-inner {
  font-size: 15px;
  font-weight: 800;
  color: var(--primary);
}

.agents-top__title {
  margin: 0;
  font-size: 17px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.agents-main {
  max-width: 720px;
  margin: 0 auto;
  padding: 20px 18px 32px;
}

.agents-section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 22px;
}

.agents-kicker {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--primary);
  margin: 0 0 6px;
}

.agents-h2 {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  line-height: 1.2;
}

.agents-pill {
  flex-shrink: 0;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: var(--on-surface-variant);
  background: var(--surface-high);
}

/* Hero gradient — Glass & Gradient rule */
.agents-hero {
  display: block;
  text-decoration: none;
  color: inherit;
  margin-bottom: 26px;
  padding: 22px 20px;
  border-radius: 18px;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-mid) 100%);
  box-shadow: 0 12px 40px rgba(74, 71, 210, 0.22);
  position: relative;
  overflow: hidden;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.agents-hero::after {
  content: '';
  position: absolute;
  inset: -50%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.18) 0%, transparent 65%);
  pointer-events: none;
}
.agents-hero:active {
  transform: scale(0.99);
}

.agents-hero__top {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.agents-hero__left {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  min-width: 0;
}

.agents-hero__icon-wrap {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.28);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.agents-hero__brain {
  color: #fff;
  fill: currentColor;
}

.agents-hero__title {
  margin: 0 0 6px;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #fff;
}

.agents-hero__desc {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.82);
  max-width: 220px;
}

.agents-hero__right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  flex-shrink: 0;
}

.agents-hero__badge {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.22);
  color: #fff;
}

.agents-hero__arrow {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.55);
}

.agents-hero__foot {
  position: relative;
  z-index: 1;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.agents-hero__faces {
  display: flex;
  align-items: center;
}
.agents-hero__face {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid var(--primary);
  margin-left: -8px;
}
.agents-hero__face:first-child {
  margin-left: 0;
}

.agents-hero__more {
  width: 32px;
  height: 32px;
  margin-left: -8px;
  border-radius: 50%;
  border: 2px solid var(--primary-mid);
  background: var(--primary-mid);
  color: #fff;
  font-size: 10px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
}

.agents-hero__consensus {
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  white-space: nowrap;
}
.agents-hero__pct {
  color: var(--tertiary-fixed);
}

/* Grid */
.agents-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
}

@media (min-width: 640px) {
  .agents-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.agent-card {
  padding: 18px 18px 16px;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 -4px 32px rgba(26, 28, 31, 0.04);
  outline: 1px solid rgba(193, 198, 215, 0.12);
  transition: box-shadow 0.2s ease;
}
.agent-card:hover {
  box-shadow: 0 8px 36px rgba(26, 28, 31, 0.08);
}

.agent-card__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 4px;
}

.agent-card__who {
  display: flex;
  gap: 14px;
  min-width: 0;
}

.agent-card__img-wrap {
  position: relative;
  flex-shrink: 0;
}
.agent-card__img {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  object-fit: cover;
}
.agent-card__img--text {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 800;
  color: #fff;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-mid) 100%);
  letter-spacing: -0.02em;
  user-select: none;
}

.agent-card__dot {
  position: absolute;
  right: -2px;
  bottom: -2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid #fff;
}
.agent-card__dot--on {
  background: var(--tertiary-fixed);
}
.agent-card__dot--off {
  background: #c1c6d7;
}

.agent-card__name {
  margin: 0 0 4px;
  font-size: 16px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.agent-card__style {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--primary);
}

.agent-card__status {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 800;
}
.agent-card__status--live {
  background: rgba(112, 255, 118, 0.18);
  color: var(--tertiary);
}
.agent-card__status--off {
  background: var(--surface-high);
  color: #717786;
}

.agent-card__status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.agent-card__metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 18px;
}

.agent-metric {
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--surface-low);
}
.agent-metric--accent {
  border-left: 2px solid var(--tertiary);
}
.agent-metric--neg {
  border-left-color: var(--error);
}

.agent-metric__lbl {
  margin: 0 0 4px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: #5f5e60;
}

.agent-metric__val {
  margin: 0;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.agent-card__btn {
  width: 100%;
  margin-top: 14px;
  padding: 12px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 700;
  background: var(--surface-highest);
  color: var(--on-surface);
  cursor: pointer;
  transition: background 0.15s ease, transform 0.1s ease;
}
.agent-card__btn:active {
  transform: scale(0.98);
}
.agent-card__btn--primary {
  background: linear-gradient(135deg, var(--primary), var(--primary-mid));
  color: #fff;
}

.agent-card__btn--ai {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  font-size: 13px;
  font-weight: 700;
  margin-top: 8px;
  background: rgba(74, 71, 210, 0.08);
  color: var(--primary);
  padding: 10px;
}

.up {
  color: var(--tertiary) !important;
}
.down {
  color: var(--error) !important;
}

/* Insight — left accent per DESIGN.md */
.agents-insight {
  margin-top: 32px;
  padding: 20px 20px 20px 18px;
  background: #fff;
  border-radius: 0 14px 14px 0;
  border-left: 4px solid var(--primary);
  box-shadow: 0 4px 24px rgba(26, 28, 31, 0.04);
}

.agents-insight__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.agents-insight__spark {
  color: var(--primary);
  font-size: 16px;
  line-height: 1;
}

.agents-insight__title {
  margin: 0;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--primary);
}

.agents-insight__body {
  margin: 0;
  font-size: 14px;
  line-height: 1.65;
  color: var(--on-surface);
}

.agents-insight__body :deep(strong) {
  font-weight: 800;
}

.agents-insight__quote {
  font-style: normal;
  color: var(--on-surface-variant);
}

.agents-disclaimer {
  margin: 24px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--on-surface-variant);
}

/* Modal */
.agents-modal {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(26, 28, 31, 0.45);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 16px;
  padding-bottom: calc(16px + env(safe-area-inset-bottom, 0));
}

@media (min-width: 480px) {
  .agents-modal {
    align-items: center;
  }
}

.agents-modal__panel {
  width: 100%;
  max-width: 400px;
  padding: 22px;
  background: #fff;
  border-radius: 18px;
  box-shadow: 0 24px 64px rgba(26, 28, 31, 0.18);
}

.agents-modal__title {
  margin: 0 0 6px;
  font-size: 18px;
  font-weight: 800;
}

.agents-modal__sub {
  margin: 0 0 14px;
  font-size: 13px;
  color: var(--on-surface-variant);
}

.agents-modal__text {
  margin: 0 0 18px;
  font-size: 14px;
  line-height: 1.55;
  color: var(--on-surface);
}

.agents-modal__actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.agents-modal__ghost {
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 600;
  color: var(--on-surface-variant);
}

.agents-modal__primary {
  padding: 10px 18px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--primary), var(--primary-mid));
  color: #fff;
  text-decoration: none;
  display: inline-block;
}
</style>
