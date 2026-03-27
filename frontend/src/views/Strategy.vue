<template>
  <div class="st-page">
    <div class="st-inner">
      <!-- 页头：对齐 stitch 选股策略列表 -->
      <header class="st-hero">
        <div class="st-hero__text">
          <h1 class="st-hero__title">选股策略列表</h1>
          <p class="st-hero__sub">
            基于 AI 与量化筛选的 FacSstock 策略入口；卡片数据来自扫描与报告，非收益承诺。
          </p>
        </div>
        <button type="button" class="st-sort" @click="sortReversed = !sortReversed">
          智能排序
        </button>
      </header>

      <div class="st-grid">
        <router-link
          v-for="item in orderedCards"
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
                <p class="st-card__desc">{{ item.desc }}</p>
              </div>
              <div class="st-card__kpi">
                <div class="st-card__kpi-val tabular">{{ item.headline }}</div>
                <div class="st-card__kpi-lbl">{{ item.headlineLbl }}</div>
              </div>
            </div>
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
          <div class="st-card__spark" aria-hidden="true">
            <svg
              class="st-spark-svg"
              viewBox="0 0 400 56"
              preserveAspectRatio="none"
            >
              <!-- 单段平滑曲线：无 T 链式、无 non-scaling-stroke，横向拉伸时仍为一条连续线 -->
              <path
                :d="item.sparkPath"
                fill="none"
                :stroke="item.sparkStroke"
                stroke-width="2.75"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
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

/** 单段三次贝塞尔，整条路径一笔连续 */
const SPARK_BOLLINGER_D = 'M0 46 C140 36 280 14 400 4'
const SPARK_TICAI_D = 'M0 40 C110 44 250 22 400 6'
const SPARK_AI_D = 'M0 44 C130 20 270 30 400 12'

const sortReversed = ref(false)
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
      id: 'bollinger',
      to: '/strategy/bollinger',
      cat: '量化突破',
      pill: '趋势 / 结构行情',
      title: '布林收缩策略',
      desc: '基于布林带收口检测，提前发现蓄势突破标的；结合扫描结果动态更新命中列表。',
      headline: lastHit != null ? String(lastHit) : '—',
      headlineLbl: '最近一次命中（只）',
      m1Lbl: '扫描次数',
      m1Val: scans,
      m2Lbl: '累计覆盖股票',
      m2Val: stocks,
      sparkPath: SPARK_BOLLINGER_D,
      sparkStroke: 'var(--st-secondary)',
    },
    {
      id: 'ticai',
      to: '/ticai',
      cat: 'AI 题材',
      pill: '热点轮动',
      title: '题材挖掘',
      desc: 'AI 驱动的热点题材与板块轮动分析，追踪龙头与情绪周期，入口进入题材中心。',
      headline: sectors !== '—' ? String(sectors) : '—',
      headlineLbl: '历史监测板块（个）',
      m1Lbl: '扫描次数',
      m1Val: scans,
      m2Lbl: '累计覆盖股票',
      m2Val: stocks,
      sparkPath: SPARK_TICAI_D,
      sparkStroke: 'var(--st-secondary)',
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
      sparkPath: SPARK_AI_D,
      sparkStroke: 'var(--st-secondary)',
    },
  ]
})

const orderedCards = computed(() => {
  const list = baseCards.value
  return sortReversed.value ? [...list].reverse() : list
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
  --st-secondary: #006d41;
  --st-tertiary: #a00024;
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
  padding-top: calc(12px + env(safe-area-inset-top, 0));
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

/* 页头 */
.st-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 28px;
}

.st-hero__title {
  margin: 0;
  font-family: 'Manrope', var(--font, system-ui, sans-serif);
  font-size: 2.125rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.12;
  color: var(--st-text);
}

.st-hero__sub {
  margin: 8px 0 0;
  font-size: 1.125rem;
  font-weight: 500;
  line-height: 1.55;
  color: var(--st-muted);
  max-width: 22rem;
}

.st-sort {
  flex-shrink: 0;
  align-self: flex-end;
  padding: 10px 14px;
  font-family: inherit;
  font-size: 0.875rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--st-text);
  background: var(--st-high);
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s;
}
.st-sort:active {
  background: #d9dadb;
}

/* 卡片列表 */
.st-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.st-card {
  display: flex;
  flex-direction: column;
  min-height: 200px;
  padding: 24px 22px 18px;
  background: var(--st-white);
  border-radius: 10px;
  box-shadow:
    inset 0 0 0 1px var(--st-ghost),
    inset 0 0 0 2px var(--st-gold-border),
    inset 0 -3px 0 0 var(--st-gold-glow),
    var(--st-ambient);
  text-decoration: none;
  color: inherit;
  transition: background 0.15s, box-shadow 0.15s;
}
.st-card:active {
  background: var(--st-low);
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
  margin-bottom: 6px;
}

.st-tag-cat {
  font-size: 0.8125rem;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--st-gold-mid);
}

.st-tag-pill {
  font-size: 0.8125rem;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 3px;
  background: var(--st-gold-bg);
  color: var(--st-gold);
  box-shadow: inset 0 0 0 1px var(--st-gold-border);
}

.st-card__name {
  margin: 0 0 7px;
  font-family: 'Manrope', var(--font, system-ui, sans-serif);
  font-size: 1.5rem;
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
  margin: 0;
  font-size: 1.0625rem;
  font-weight: 500;
  line-height: 1.55;
  color: var(--st-muted);
  max-width: 100%;
}

.st-card__kpi {
  text-align: right;
  flex-shrink: 0;
}

.st-card__kpi-val {
  font-family: 'Manrope', var(--font, system-ui, sans-serif);
  font-size: 1.9375rem;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.03em;
  color: var(--st-primary);
}

.st-card__kpi-lbl {
  margin-top: 6px;
  font-size: 0.8125rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: var(--st-outline);
  line-height: 1.35;
  max-width: 7rem;
  margin-left: auto;
  text-align: right;
}

.st-card__metrics {
  display: flex;
  gap: 24px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--st-low);
}

.st-metric__lbl {
  font-size: 0.8125rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  color: var(--st-outline);
}

.st-metric__val {
  margin-top: 4px;
  font-size: 1.125rem;
  font-weight: 800;
  color: var(--st-text);
}

.st-card__spark {
  margin-top: 16px;
  height: 48px;
  width: 100%;
  overflow: visible;
}

.st-spark-svg {
  display: block;
  width: 100%;
  height: 100%;
  overflow: visible;
}

/* 更多策略 */
.st-more {
  margin-top: 36px;
}

.st-more__title {
  margin: 0 0 12px;
  font-size: 1rem;
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
  font-size: 1.0625rem;
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
  font-size: 1rem;
  font-weight: 500;
  line-height: 1.45;
  color: var(--st-outline);
}
</style>
