<template>
  <div class="st-page">
    <div class="st-inner">
      <!-- 页头：对齐 stitch 选股策略列表 -->
      <header class="st-hero">
        <div class="st-hero__glow" aria-hidden="true" />
        <div class="st-hero__text">
          <h1 class="st-hero__title">选股策略列表</h1>
          <p class="st-hero__sub">
            基于 AI 与量化筛选的策略入口；卡片数据来自扫描与报告，非收益承诺。
          </p>
        </div>
      </header>

      <div class="st-grid">
        <router-link
          v-for="item in baseCards"
          :key="item.id"
          :to="item.to"
          class="st-card"
        >
          <div class="st-card__main">
            <div class="st-card__row">
              <div class="st-card__left">
                <div class="st-card__tags">
                  <span class="st-tag-cat">{{ item.cat }}</span>
                  <span class="st-tag-pill">{{ item.pill }}</span>
                </div>
                <h2 class="st-card__name">{{ item.title }}</h2>
              </div>
              <div class="st-card__kpi">
                <div class="st-card__kpi-val tabular">{{ item.headline }}</div>
                <div class="st-card__kpi-lbl">{{ item.headlineLbl }}</div>
              </div>
            </div>
            <p class="st-card__desc">{{ item.desc }}</p>
            <div class="st-card__metrics">
              <div class="st-metric">
                <div class="st-metric__lbl">{{ item.m1Lbl }}</div>
                <div class="st-metric__val tabular">{{ item.m1Val }}</div>
              </div>
              <div class="st-metric">
                <div class="st-metric__lbl">{{ item.m2Lbl }}</div>
                <div class="st-metric__val tabular">{{ item.m2Val }}</div>
              </div>
            </div>
          </div>
        </router-link>
      </div>

      <!-- 更多策略：开发中 -->
      <section class="st-more" aria-labelledby="st-more-heading">
        <h3 id="st-more-heading" class="st-more__title">更多策略路演</h3>
        <div class="st-more__panel">
          <p class="st-more__lead">
            更多量化策略、组合回测与实盘路演能力<strong>正在开发中</strong>，当前版本仅开放上述三类入口。
          </p>
          <p class="st-more__muted">
            排期与上新将通过应用更新通知，敬请期待。
          </p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { scan, report } from '@/api/strategy.js'

const stats = ref({ scans: '—', stocks: '—', sectors: '—' })
const latestScan = ref(null)
const reportCount = ref('—')

const baseCards = computed(() => {
  const scans = stats.value.scans
  const stocks = stats.value.stocks
  const sectors = stats.value.sectors
  const lastHit = latestScan.value?.stock_count
  const lastTime = latestScan.value ? formatScanTime(latestScan.value.scan_time) : '—'

  return [
    {
      id: 'agents',
      to: '/strategy/agents',
      cat: 'AI 智能体',
      pill: '游资专家库',
      title: '游资智能体 · 策略智能体',
      desc: '市场监测下的多角色策略库：胜率、收益与状态一览；全场策略总结跳转大模型解读。',
      headline: '6',
      headlineLbl: '策略角色（位）',
      m1Lbl: '扫描次数',
      m1Val: scans,
      m2Lbl: '累计覆盖股票',
      m2Val: stocks,
    },
    {
      id: 'bollinger',
      to: '/strategy/bollinger',
      cat: '量化突破',
      pill: '趋势 / 结构行情',
      title: '布林收缩策略',
      desc: '基于布林带收口检测，提前发现蓄势突破标的；结合扫描结果动态更新命中列表。',
      headline: lastHit != null ? String(lastHit) : '—',
      headlineLbl: '上次命中（只）',
      m1Lbl: '扫描次数',
      m1Val: scans,
      m2Lbl: '累计覆盖股票',
      m2Val: stocks,
    },
    {
      id: 'ticai',
      to: '/ticai',
      cat: 'AI 题材',
      pill: '热点轮动',
      title: '题材挖掘',
      desc: 'AI 驱动的热点题材与板块轮动分析，追踪龙头与情绪周期，入口进入题材中心。',
      headline: sectors !== '—' ? String(sectors) : '—',
      headlineLbl: '监测板块（个）',
      m1Lbl: '扫描次数',
      m1Val: scans,
      m2Lbl: '累计覆盖股票',
      m2Val: stocks,
    },
    {
      id: 'ai',
      to: '/strategy/ai',
      cat: '大模型',
      pill: '全市场',
      title: 'AI 智能策略',
      desc: '腾讯混元等大模型解读扫描结果与市场语境，生成可读报告；非投资建议。',
      headline: reportCount.value !== '—' ? String(reportCount.value) : '—',
      headlineLbl: '分析报告（条）',
      m1Lbl: '扫描次数',
      m1Val: scans,
      m2Lbl: '最近扫描',
      m2Val: lastTime,
    },
    {
      id: 'backtest',
      to: '/strategy/backtest',
      cat: '量化回测',
      pill: '技术指标',
      title: '量化回测',
      desc: '基于 TA-Lib 指标（均线、RSI、布林带、MACD、KDJ、ATR）的历史回测，支持权益曲线、回撤曲线与买卖点标注。',
      headline: '—',
      headlineLbl: '选择股票开始',
      m1Lbl: '回测次数',
      m1Val: '—',
      m2Lbl: '指标库',
      m2Val: 'TA-Lib',
    },
    {
      id: 'factor-prompt',
      to: '/strategy/factor-prompt',
      cat: '因子工程',
      pill: 'DeepSeek',
      title: '自定义因子 Prompt 工程',
      desc: '用自然语言描述因子需求，由 DeepSeek 生成可嵌入因子模板的 Python 逻辑；非量化类请求自动过滤。',
      headline: 'v2.4',
      headlineLbl: '框架版本',
      m1Lbl: '模型',
      m1Val: 'DeepSeek',
      m2Lbl: '引擎',
      m2Val: '因子模板',
    },
  ]
})

async function loadHistory() {
  try {
    const data = await scan.history()
    if (data && data.length > 0) {
      const total = data.length
      const stocks = data.reduce((s, d) => s + (d.stock_count || 0), 0)
      const sectorSet = new Set()
      data.forEach(d => (d.hot_sectors || []).forEach(s => sectorSet.add(s.name || s)))
      stats.value = { scans: String(total), stocks: String(stocks), sectors: String(sectorSet.size) }
      latestScan.value = data[0]
    }
  } catch {
    /* keep defaults */
  }
}

async function loadReportCount() {
  try {
    const reports = await report.list()
    reportCount.value = Array.isArray(reports) ? String(reports.length) : '—'
  } catch {
    reportCount.value = '—'
  }
}

function formatScanTime(timeStr) {
  if (!timeStr) return '—'
  try {
    const d = new Date(timeStr)
    const now = new Date()
    const diffMs = now - d
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return '刚刚'
    if (diffMin < 60) return `${diffMin} 分钟前`
    const diffHr = Math.floor(diffMin / 60)
    if (diffHr < 24) return `${diffHr} 小时前`
    const diffDay = Math.floor(diffHr / 24)
    if (diffDay < 7) return `${diffDay} 天前`
    const mo = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${mo}-${day}`
  } catch {
    return '—'
  }
}

onMounted(() => {
  loadHistory()
  loadReportCount()
})
</script>

<style scoped>
/* Architectural Ledger — 与 DESIGN.md / stitch code 对齐 */
.st-page {
  --st-primary: #003ec7;
  --st-primary-mid: #0052ff;
  /* 策略标签 & 卡片金边 */
  --st-gold: #9a7209;
  --st-gold-mid: #b8860b;
  --st-gold-light: #c9a227;
  --st-gold-bg: rgba(201, 162, 39, 0.14);
  --st-gold-border: rgba(180, 134, 11, 0.55);
  --st-gold-glow: rgba(201, 162, 39, 0.18);
  --st-surface: #f8f9fa;
  --st-low: #f3f4f5;
  --st-high: #e7e8e9;
  --st-white: #ffffff;
  --st-text: #191c1d;
  --st-muted: #434656;
  --st-outline: #737688;
  --st-ghost: rgba(195, 197, 217, 0.15);
  --st-ambient: 0 4px 24px rgba(25, 28, 29, 0.06);

  min-height: 100vh;
  min-height: 100dvh;
  background: var(--st-surface);
  color: var(--st-text);
  padding-top: 0;
  padding-bottom: calc(24px + env(safe-area-inset-bottom, 0) + 72px);
  font-family: 'Inter', var(--font, system-ui, sans-serif);
}

.st-inner {
  max-width: 560px;
  margin: 0 auto;
  padding: 0 20px 20px;
}

.tabular {
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum' 1;
}

/* 页头：安全区顶内边距放在此处，避免顶部出现与背景不一致的「缝隙」 */
.st-hero {
  position: relative;
  overflow: hidden;
  margin: 0 -20px 0;
  padding: calc(14px + env(safe-area-inset-top, 0)) 20px 20px;
  background:
    radial-gradient(ellipse 90% 60% at 105% 0%, rgba(201, 162, 39, 0.22), transparent 55%),
    radial-gradient(ellipse 70% 50% at 5% 0%, rgba(0, 62, 199, 0.14), transparent 52%),
    linear-gradient(170deg, #fffdf5 0%, #fff 40%, rgba(248, 249, 250, 0.95) 100%);
}

.st-hero__glow {
  position: absolute;
  inset: -40% 0 auto 50%;
  height: 160%;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(201, 162, 39, 0.14) 0%, transparent 65%);
  pointer-events: none;
}

.st-hero__text {
  position: relative;
  z-index: 1;
}

.st-hero__title {
  margin: 0;
  font-family: 'Manrope', var(--font, system-ui, sans-serif);
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.1;
  color: var(--st-text);
}

.st-hero__sub {
  margin: 8px 0 0;
  font-size: 15px;
  font-weight: 500;
  line-height: 1.55;
  color: var(--st-muted);
  max-width: 100%;
}

/* 卡片列表 */
.st-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px 0 28px;
}

/* 金色质感卡片：顶金边 + 底部金色阴影，无下边框 */
.st-card {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 22px 22px 20px;
  background: var(--st-white);
  border-radius: 10px;
  box-shadow:
    inset 0 0 0 1px rgba(180, 134, 11, 0.3),
    inset 0 3px 0 0 var(--st-gold-mid),
    inset 0 -4px 0 0 rgba(201, 162, 39, 0.08),
    var(--st-ambient);
  text-decoration: none;
  color: inherit;
  transition: background 0.15s, box-shadow 0.15s;
}
.st-card:active {
  background: #fdfdf5;
  box-shadow:
    inset 0 0 0 1px rgba(180, 134, 11, 0.4),
    inset 0 3px 0 0 var(--st-gold-light),
    inset 0 -4px 0 0 rgba(201, 162, 39, 0.12),
    var(--st-ambient);
}

.st-card__main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.st-card__row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.st-card__left {
  min-width: 0;
  flex: 1;
}

.st-card__tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.st-tag-cat {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--st-gold-mid);
}

.st-tag-pill {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: 3px;
  background: rgba(201, 162, 39, 0.14);
  color: var(--st-gold);
  box-shadow: inset 0 0 0 1px rgba(180, 134, 11, 0.35);
}

.st-card__name {
  margin: 0 0 6px;
  font-family: 'Manrope', var(--font, system-ui, sans-serif);
  font-size: 17px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.25;
  color: var(--st-text);
  transition: color 0.15s;
}
.st-card:hover .st-card__name,
.st-card:active .st-card__name {
  color: var(--st-primary);
}

.st-card__desc {
  margin: 10px 0 0;
  font-size: 15px;
  font-weight: 500;
  line-height: 1.55;
  color: var(--st-muted);
  width: 100%;
}

.st-card__kpi {
  flex: 0 0 auto;
  max-width: 38%;
  text-align: right;
  align-self: flex-start;
}

.st-card__kpi-val {
  font-family: 'Manrope', var(--font, system-ui, sans-serif);
  font-size: 26px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.03em;
  color: var(--st-primary);
}

.st-card__kpi-lbl {
  margin-top: 5px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--st-outline);
  line-height: 1.25;
  margin-left: auto;
  text-align: right;
  white-space: nowrap;
}

.st-card__metrics {
  display: flex;
  gap: 28px;
  margin-top: 14px;
}

.st-metric__lbl {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.03em;
  color: var(--st-outline);
}

.st-metric__val {
  margin-top: 4px;
  font-size: 15px;
  font-weight: 800;
  color: var(--st-text);
}

/* 更多策略 */
.st-more {
  margin-top: 36px;
}

.st-more__title {
  margin: 0 0 12px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--st-text);
}

.st-more__panel {
  padding: 18px 20px;
  background: var(--st-white);
  border-radius: 8px;
  box-shadow: inset 0 0 0 1px var(--st-ghost), var(--st-ambient);
}

.st-more__lead {
  margin: 0 0 8px;
  font-size: 15px;
  font-weight: 500;
  line-height: 1.55;
  color: var(--st-muted);
}

.st-more__lead strong {
  font-weight: 800;
  color: var(--st-primary);
}

.st-more__muted {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.45;
  color: var(--st-outline);
}
</style>
