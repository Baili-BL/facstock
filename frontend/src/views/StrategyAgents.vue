<template>
  <div class="agents-page">
    <!-- 顶栏：活跃=金融智能；全部=历史总结回顾 -->
    <header class="agents-top" :data-mode="tab">
      <button type="button" class="agents-top__back" aria-label="返回" @click="$router.push('/strategy')">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>

      <div v-if="tab === 'active'" class="agents-top__brand">
        <div class="agents-top__avatar" aria-hidden="true">
          <span class="agents-top__avatar-inner">金</span>
        </div>
        <h1 class="agents-top__title">金融智能</h1>
      </div>
      <h1 v-else class="agents-top__title agents-top__title--history">历史总结回顾</h1>

      <div v-if="tab === 'active'" class="agents-top__right">
        <button type="button" class="agents-top__iconbtn" aria-label="搜索" @click="$router.push('/')">
          <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
        </button>
      </div>
      <div v-else class="agents-top__right agents-top__right--pair">
        <button type="button" class="agents-top__iconbtn" aria-label="搜索" @click="$router.push('/')">
          <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
        </button>
        <button type="button" class="agents-top__iconbtn" aria-label="日历" @click="calendarHint = true">
          <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zM5 8V6h14v2H5z"/></svg>
        </button>
      </div>
    </header>

    <main class="agents-main">
      <!-- Tab -->
      <div class="agents-tabs">
        <button
          type="button"
          class="agents-tab"
          :class="{ 'agents-tab--on': tab === 'active' }"
          @click="tab = 'active'"
        >
          活跃智能体
        </button>
        <button
          type="button"
          class="agents-tab"
          :class="{ 'agents-tab--on': tab === 'all' }"
          @click="tab = 'all'"
        >
          全部智能体
        </button>
      </div>

      <!-- ——— 活跃智能体：原专家库 ——— -->
      <template v-if="tab === 'active'">
      <!-- 区块标题 -->
      <div class="agents-section-head">
        <div>
          <p class="agents-kicker">市场监测 · MARKET SURVEILLANCE</p>
          <h2 class="agents-h2">游资策略专家库</h2>
        </div>
        <span class="agents-pill">实时更新</span>
      </div>

      <!-- AI 全场总结 -->
      <router-link to="/strategy/ai/summary" class="agents-hero">
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
                <img :src="a.avatar" :alt="a.name" class="agent-card__img" loading="lazy" />
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
        以上为产品演示与策略角色设定，非实盘收益承诺；持仓与信号功能将陆续接入。
      </p>
      </template>

      <!-- ——— 全部智能体：历史总结回顾详情 ——— -->
      <section v-else class="hist" aria-label="历史总结回顾">
        <div class="hist-hero">
          <div class="hist-perf">
            <span class="hist-perf__label">绩效洞察</span>
            <h2 class="hist-perf__stat">
              季度智能预测胜率: <span class="tabular">{{ perfWinRate }}%</span>
            </h2>
            <p class="hist-perf__desc">
              在过去的 {{ perfAnalysisCount }} 场分析中，AI 智能体在能源和科技板块的调仓与市场转折点保持了高度一致。
            </p>
            <div class="hist-perf__chips">
              <span class="hist-chip hist-chip--bull">看多趋势已确立</span>
              <span class="hist-chip hist-chip--muted">{{ perfUpdated }}</span>
            </div>
          </div>
          <div class="hist-banner">
            <img
              class="hist-banner__img"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuA0q0qGWm0478yH9XVTg8J6vpt694AOh9V8F_7bTJRt4REhz7aCpckyhV0PVpPynwsmzesIxd59i8m1Zo5NmDIiHrozdqg7vII42ByibC8GsNB8GHFv22WzUFwY7I8PBbLzxF5ogWvzuL3O4pcVtNbbkYPbUJf0Pm0unc7oGkiLrqehD4N0aMojdKdKVt9DylYdN4i7-YFq4f0AcY-qqOElQPGFqdNMHejrD17Ts-QvAK8uXNNRIr8lSxHNUa5nCCnWBBECTBFemGd1"
              alt=""
              loading="lazy"
            />
            <div class="hist-banner__grad" />
            <p class="hist-banner__text">AI 策略矩阵：十月扩张计划</p>
          </div>
        </div>

        <div class="hist-toolbar">
          <h3 class="hist-toolbar__title">历史总结记录</h3>
          <div class="hist-toolbar__btns">
            <button type="button" class="hist-filter-btn" :class="{ 'is-on': sortOrder === 'latest' }" @click="sortOrder = 'latest'">
              排序：最新
            </button>
            <button type="button" class="hist-filter-btn" :class="{ 'is-on': sentimentFilter === 'bull' }" @click="toggleSentimentFilter('bull')">
              筛选：看多
            </button>
          </div>
        </div>

        <div class="hist-grid">
          <article
            v-for="rec in filteredHistory"
            :key="rec.id"
            class="hist-card"
            :class="{
              'hist-card--accent': rec.accentBorder,
            }"
          >
            <div class="hist-card__top">
              <div>
                <span class="hist-card__date">{{ rec.date }}</span>
                <h4 class="hist-card__name">{{ rec.title }}</h4>
              </div>
              <div class="hist-sent" :class="'hist-sent--' + rec.sentiment">
                <span class="hist-sent__ico" aria-hidden="true">{{ sentimentIcon(rec.sentiment) }}</span>
                <span>{{ rec.pctLabel }}</span>
              </div>
            </div>
            <p class="hist-card__summary">{{ rec.summary }}</p>
            <div class="hist-card__sectors">
              <div class="hist-sectors">
                <span
                  v-for="(ch, i) in rec.avatarChars"
                  :key="i"
                  class="hist-sector-dot"
                  :class="'tone-' + (i % 4)"
                >{{ ch }}</span>
              </div>
              <span class="hist-card__linktxt">{{ rec.linkedLabel }}</span>
            </div>
            <button type="button" class="hist-card__cta" @click="$router.push('/strategy/ai')">
              查看完整报告
              <span class="hist-card__cta-arrow" aria-hidden="true">→</span>
            </button>
          </article>
        </div>

        <div class="hist-ai-cta">
          <div class="hist-ai-cta__icon" aria-hidden="true">
            <svg class="icon icon-xl"><use href="#icon-ai" /></svg>
          </div>
          <div class="hist-ai-cta__text">
            <h4 class="hist-ai-cta__title">识别到 AI 分析模式</h4>
            <p class="hist-ai-cta__desc">
              当前历史数据显示，「钧哥」与「林叔」的情绪在重大市场突破前有 92% 的相关性。是否需要进行深度历史同步分析？
            </p>
          </div>
          <button type="button" class="hist-ai-cta__btn" @click="$router.push('/strategy/ai')">
            生成深度回顾报告
          </button>
        </div>

        <p class="agents-disclaimer hist-disclaimer">
          历史总结为演示数据，非投资建议；正式版本将对接扫描与 AI 报告时间线。
        </p>
      </section>
    </main>

    <!-- 日历占位提示 -->
    <div v-if="calendarHint" class="agents-modal" @click.self="calendarHint = false">
      <div class="agents-modal__panel">
        <h4 class="agents-modal__title">按日期筛选</h4>
        <p class="agents-modal__text">日历筛选将在接入真实报告数据后开放，当前可查看下方历史记录列表。</p>
        <div class="agents-modal__actions">
          <button type="button" class="agents-modal__primary" @click="calendarHint = false">知道了</button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { STRATEGY_AGENTS } from '@/data/strategyAgents.js'

const router = useRouter()

/** 演示数据：与产品设计稿一致，后续可接 API */
const tab = ref('active')
const calendarHint = ref(false)

const consensusPct = ref(89)

/** 历史总结页 — 绩效区 */
const perfWinRate = ref('84.2')
const perfAnalysisCount = ref(42)
const perfUpdated = ref('2分钟前更新')

const sortOrder = ref('latest')
const sentimentFilter = ref(null) // null | 'bull'

function toggleSentimentFilter(v) {
  sentimentFilter.value = sentimentFilter.value === v ? null : v
}

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

const filteredHistory = computed(() => {
  let list = [...historyRecords.value]
  if (sentimentFilter.value === 'bull') {
    list = list.filter((r) => r.sentiment === 'bullish')
  }
  if (sortOrder.value === 'latest') {
    list.sort((a, b) => (a.date < b.date ? 1 : -1))
  }
  return list
})

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

const visibleAgents = computed(() => agents.filter((a) => a.status !== 'offline'))

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
  --tertiary: #006b1b;
  --tertiary-fixed: #70ff76;
  --on-tertiary-fixed: #002204;
  --error: #ba1a1a;
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

.agents-top__title--history {
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  text-align: center;
  justify-self: center;
  grid-column: 2;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agents-top[data-mode='all'] .agents-top__brand {
  display: none;
}

.agents-top__right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  grid-column: 3;
}

.agents-top__right--pair {
  gap: 0;
}

.agents-top__iconbtn {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: var(--on-surface);
  background: transparent;
}
.agents-top[data-mode='active'] .agents-top__iconbtn {
  color: var(--primary);
}
.agents-top__iconbtn:active {
  background: rgba(0, 0, 0, 0.06);
}

.agents-main {
  max-width: 720px;
  margin: 0 auto;
  padding: 20px 18px 32px;
}

.agents-tabs {
  display: flex;
  gap: 28px;
  margin-bottom: 28px;
  border-bottom: 1px solid var(--outline-variant);
}

.agents-tab {
  padding: 0 0 14px;
  margin-bottom: -1px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: #5f5e60;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
}
.agents-tab--on {
  color: var(--primary);
  border-bottom-color: var(--primary);
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

/* —— 历史总结回顾（全部智能体） —— */
.hist {
  padding-top: 4px;
}

.hist-hero {
  display: grid;
  gap: 16px;
  margin-bottom: 28px;
}

@media (min-width: 720px) {
  .hist-hero {
    grid-template-columns: 1fr 1fr;
    align-items: stretch;
  }
}

.hist-perf {
  padding: 22px 20px;
  border-radius: 14px;
  background: var(--surface-low);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 200px;
}

.hist-perf__label {
  display: block;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--outline-soft);
  margin-bottom: 8px;
}

.hist-perf__stat {
  margin: 0 0 12px;
  font-size: clamp(1.35rem, 4.5vw, 2.4rem);
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.15;
  color: var(--on-surface);
}

.hist-perf__desc {
  margin: 0;
  font-size: 14px;
  line-height: 1.55;
  color: var(--on-surface-variant);
  max-width: 28em;
}

.hist-perf__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
}

.hist-chip {
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.hist-chip--bull {
  background: var(--tertiary-fixed);
  color: var(--on-tertiary-fixed);
}

.hist-chip--muted {
  background: var(--surface-highest);
  color: var(--on-surface-variant);
  font-weight: 700;
}

.hist-banner {
  position: relative;
  border-radius: 14px;
  overflow: hidden;
  min-height: 180px;
  background: var(--surface-high);
}

@media (min-width: 720px) {
  .hist-banner {
    min-height: 100%;
  }
}

.hist-banner__img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: grayscale(0.35);
  opacity: 0.85;
}

.hist-banner__grad {
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, rgba(74, 71, 210, 0.45), transparent 55%);
  pointer-events: none;
}

.hist-banner__text {
  position: absolute;
  left: 18px;
  right: 18px;
  bottom: 18px;
  margin: 0;
  font-size: 17px;
  font-weight: 800;
  line-height: 1.3;
  color: #fff;
  text-shadow: 0 2px 12px rgba(0, 0, 0, 0.35);
  z-index: 1;
}

.hist-toolbar {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 20px;
}

@media (min-width: 520px) {
  .hist-toolbar {
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
  }
}

.hist-toolbar__title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  letter-spacing: -0.01em;
}

.hist-toolbar__btns {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hist-filter-btn {
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 700;
  color: var(--on-surface);
  background: var(--surface-highest);
  transition: background 0.15s ease;
}
.hist-filter-btn.is-on {
  background: rgba(74, 71, 210, 0.12);
  color: var(--primary);
}
.hist-filter-btn:active {
  opacity: 0.9;
}

.hist-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
}

@media (min-width: 640px) {
  .hist-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 960px) {
  .hist-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

.hist-card {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 22px 20px;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 4px 32px rgba(26, 28, 31, 0.04);
  outline: 1px solid rgba(193, 198, 215, 0.15);
  transition: box-shadow 0.2s ease;
}

.hist-card--accent {
  border-left: 4px solid var(--primary);
  outline: none;
  box-shadow: 0 4px 32px rgba(26, 28, 31, 0.06);
}

.hist-card:hover {
  box-shadow: 0 8px 40px rgba(26, 28, 31, 0.08);
}

.hist-card__top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}

.hist-card__date {
  display: block;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--outline-soft);
  margin-bottom: 6px;
}

.hist-card__name {
  margin: 0;
  font-size: 17px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.hist-card__summary {
  margin: 0 0 18px;
  font-size: 14px;
  line-height: 1.55;
  color: var(--on-surface-variant);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.hist-sent {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.hist-sent--bullish {
  background: var(--tertiary-fixed);
  color: var(--on-tertiary-fixed);
}

.hist-sent--neutral {
  background: var(--surface-high);
  color: var(--on-surface-variant);
}

.hist-sent--bearish {
  background: var(--error-container);
  color: var(--on-error-container);
}

.hist-sent__ico {
  font-size: 12px;
  line-height: 1;
}

.hist-card__sectors {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}

.hist-sectors {
  display: flex;
  align-items: center;
}

.hist-sector-dot {
  width: 30px;
  height: 30px;
  margin-left: -7px;
  border-radius: 50%;
  border: 2px solid #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 800;
  color: #fff;
  flex-shrink: 0;
}
.hist-sector-dot:first-child {
  margin-left: 0;
}
.hist-sector-dot.tone-0 {
  background: var(--primary-mid);
}
.hist-sector-dot.tone-1 {
  background: #94a3b8;
}
.hist-sector-dot.tone-2 {
  background: var(--primary);
}
.hist-sector-dot.tone-3 {
  background: #1e293b;
}

.hist-card__linktxt {
  font-size: 10px;
  font-weight: 800;
  color: var(--outline-soft);
}

.hist-card__cta {
  width: 100%;
  padding: 14px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.02em;
  background: var(--surface-highest);
  color: var(--on-surface);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: background 0.2s ease, color 0.2s ease;
}
.hist-card:hover .hist-card__cta {
  background: linear-gradient(135deg, var(--primary), var(--primary-mid));
  color: #fff;
}
.hist-card__cta-arrow {
  font-size: 15px;
  opacity: 0.9;
}

.hist-ai-cta {
  margin-top: 36px;
  padding: 22px 20px;
  background: #fff;
  border-radius: 14px;
  border-left: 4px solid var(--primary);
  box-shadow: 0 4px 32px rgba(26, 28, 31, 0.04);
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: stretch;
}

@media (min-width: 640px) {
  .hist-ai-cta {
    flex-direction: row;
    align-items: center;
    gap: 22px;
  }
}

.hist-ai-cta__icon {
  flex-shrink: 0;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: rgba(74, 71, 210, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
}

.hist-ai-cta__text {
  flex: 1;
  min-width: 0;
}

.hist-ai-cta__title {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 800;
}

.hist-ai-cta__desc {
  margin: 0;
  font-size: 14px;
  line-height: 1.55;
  color: var(--on-surface-variant);
}

.hist-ai-cta__btn {
  flex-shrink: 0;
  padding: 14px 20px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 800;
  color: #fff;
  background: linear-gradient(135deg, var(--primary), var(--primary-mid));
  box-shadow: 0 8px 24px rgba(74, 71, 210, 0.25);
  text-align: center;
  white-space: nowrap;
}
.hist-ai-cta__btn:active {
  transform: scale(0.98);
}

.hist-disclaimer {
  margin-top: 28px;
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
