<template>
  <div class="ah-page">
    <header class="ah-top">
      <button type="button" class="ah-top__icon ah-top__icon--back" aria-label="返回" @click="goBack">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <h1 class="ah-top__title">持仓详情</h1>
      <div class="ah-top__actions">
        <button type="button" class="ah-top__icon" aria-label="分享" @click="toast = '分享功能即将开放'">
          <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92s2.92-1.31 2.92-2.92-1.31-2.92-2.92-2.92z"/></svg>
        </button>
        <button type="button" class="ah-top__icon" aria-label="更多" @click="toast = '更多操作即将开放'">
          <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/></svg>
        </button>
      </div>
    </header>

    <main v-if="agent" class="ah-main">
      <!-- loading -->
      <div v-if="h.loading" class="ah-loading">
        <div class="ah-spinner" />
        <span>加载持仓数据…</span>
      </div>

      <!-- error -->
      <div v-else-if="h.error" class="ah-empty">
        <p>数据加载失败：{{ h.error }}</p>
        <button type="button" class="ah-empty__btn" @click="fetchData">重试</button>
      </div>

      <!-- 真实/兜底数据 -->
      <template v-else>
      <!-- 日期 -->
      <nav class="ah-dates" aria-label="选择日期">
        <button
          v-for="d in datePills"
          :key="d.key"
          type="button"
          class="ah-date-pill"
          :class="{ 'ah-date-pill--on': dateKey === d.key }"
          @click="onDatePill(d)"
        >
          {{ d.label }}
          <svg v-if="d.calendar" class="icon icon-sm ah-date-cal" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zM5 8V6h14v2H5z"/>
          </svg>
        </button>
      </nav>

      <!-- 总资产 -->
      <section class="ah-card ah-card--hero">
        <div class="ah-hero__deco" aria-hidden="true">
          <svg class="ah-hero__wallet" viewBox="0 0 24 24" fill="currentColor"><path d="M21 18v1c0 1.1-.9 2-2 2H5c-1.11 0-2-.9-2-2V5c0-1.1.89-2 2-2h14c1.1 0 2 .9 2 2v1h-9c-1.11 0-2 .9-2 2v8c0 1.1.89 2 2 2h9zm-9-2h10V8H12v8zm4-2.5c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"/></svg>
        </div>
        <p class="ah-label">总资产 (CNY)</p>
        <p class="ah-asset tabular">¥{{ h.assets.totalCny }}</p>
        <div class="ah-pnl-grid">
          <div>
            <p class="ah-pnl-lbl">今日盈亏</p>
            <div class="ah-pnl-row">
              <span class="ah-pnl-val tabular" :class="pnlTone(h.assets.todayPnl)">{{ formatSignedMoney(h.assets.todayPnl) }}</span>
              <span class="ah-pct" :class="chipClass(h.assets.todayPct)">{{ formatSignedPct(h.assets.todayPct) }}</span>
            </div>
          </div>
          <div>
            <p class="ah-pnl-lbl">总累计盈亏</p>
            <div class="ah-pnl-row">
              <span class="ah-pnl-val tabular" :class="pnlTone(h.assets.cumPnl)">{{ formatSignedMoney(h.assets.cumPnl) }}</span>
              <span class="ah-pct" :class="chipClass(h.assets.cumPct)">{{ formatSignedPct(h.assets.cumPct) }}</span>
            </div>
          </div>
        </div>
      </section>

      <div class="ah-bento">
        <!-- 7 日收益 -->
        <section class="ah-card ah-chart-card">
          <div class="ah-chart-head">
            <h2 class="ah-h2">7日收益曲线</h2>
            <button type="button" class="ah-link" @click="toast = '详细图表即将接入'">详细图表 &gt;</button>
          </div>
          <div class="ah-bars">
            <div
              v-for="(pct, i) in h.chartBars"
              :key="i"
              class="ah-bar-wrap"
            >
              <div class="ah-bar-track">
                <div
                  class="ah-bar-fill"
                  :style="{ height: pct + '%', opacity: barOpacity(i) }"
                />
              </div>
              <span class="ah-bar-lbl" :class="{ 'ah-bar-lbl--bold': i >= h.chartBars.length - 2 }">{{ h.chartLabels[i] }}</span>
            </div>
          </div>
        </section>

        <!-- 行业分布 -->
        <section class="ah-card ah-sector-card">
          <h2 class="ah-h2 ah-h2--mb">行业分布</h2>
          <div class="ah-sectors">
            <div v-for="(s, i) in h.sectors" :key="s.name" class="ah-sector">
              <div class="ah-sector-head">
                <span>{{ s.name }}</span>
                <span class="tabular">{{ s.pct }}%</span>
              </div>
              <div class="ah-sector-track">
                <div
                  class="ah-sector-bar"
                  :style="{ width: s.pct + '%', opacity: s.opacity }"
                />
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- AI 分析 -->
      <section class="ah-ai">
        <svg class="icon ah-ai__ico" aria-hidden="true"><use href="#icon-ai" /></svg>
        <div>
          <h3 class="ah-ai__title">{{ agent.analysisBrand }} AI 策略分析</h3>
          <p class="ah-ai__body">{{ h.analysisText }}</p>
        </div>
        <button type="button" class="ah-ai__cta" @click="$router.push(`/strategy/agents/${agent.id}/analysis`)" aria-label="查看详细AI分析">
          <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M10 17l5-5-5-5v10z"/></svg>
        </button>
      </section>

      <!-- 持仓表 -->
      <section class="ah-card ah-table-card">
        <div class="ah-table-head">
          <h2 class="ah-h2">当前持仓</h2>
          <button type="button" class="ah-top__icon ah-filter" aria-label="筛选排序" @click="toast = '排序筛选即将开放'">
            <svg class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M10 18h4v-2h-4v2zM3 6v2h18V6H3zm3 7h12v-2H6v2z"/></svg>
          </button>
        </div>
        <div class="ah-table-scroll">
          <table class="ah-table">
            <thead>
              <tr>
                <th>证券名称/代码</th>
                <th class="ah-num">现价</th>
                <th class="ah-num">涨跌幅</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in h.positions" :key="p.code">
                <td>
                  <span class="ah-stock-name">{{ p.name }}</span>
                  <span class="ah-stock-code">{{ p.code }}</span>
                </td>
                <td class="ah-num tabular">{{ p.price }}</td>
                <td class="ah-num">
                  <span class="tabular" :class="p.changePct >= 0 ? 'ah-up' : 'ah-down'">
                    {{ p.changePct >= 0 ? '+' : '' }}{{ p.changePct }}%
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <button type="button" class="ah-view-all" @click="toast = `共 ${h.totalPositionCount} 只，完整列表即将开放`">
          查看全部 {{ h.totalPositionCount }} 只持仓
        </button>
      </section>

      <p class="ah-footnote">
        <template v-if="h.hasRealData">
          数据来源：{{ agent.analysisBrand }} AI 分析 · {{ latestAnalysis?.report_date || '' }}
        </template>
        <template v-else>暂无分析记录，请先运行策略分析获取持仓与建议。</template>
      </p>
      </template>
    </main>

    <div v-else class="ah-empty">
      <p>未找到该智能体</p>
      <button type="button" class="ah-empty__btn" @click="$router.push('/strategy/agents')">返回智能体</button>
    </div>

    <div v-if="toast" class="ah-toast" role="status">{{ toast }}</div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getStrategyAgent } from '@/data/strategyAgents.js'

const route = useRoute()
const router = useRouter()
const toast = ref('')
const dateKey = ref('latest')

// 真实数据
const rawHoldings = ref(null)   // /api/holdings 响应
const latestAnalysis = ref(null) // /api/agents/:id/analysis/latest 响应
const loading = ref(false)
const error = ref(null)

watch(toast, (v) => {
  if (v) setTimeout(() => { toast.value = '' }, 2200)
})

const agent = computed(() => getStrategyAgent(route.params.id))
const agentId = computed(() => route.params.id)

// 持仓数据（来自 holdings API）
const positions = computed(() => {
  if (!rawHoldings.value?.holdings) return []
  return rawHoldings.value.holdings.map(h => ({
    name:    h.stock_name,
    code:    h.stock_code,
    price:   h.current_price || 0,
    changePct: h.profit_loss_pct || 0,
    sector:  h.sector || '',
  }))
})

// 分析结果里的推荐股（快照为空时的兜底，兼容历史记录未写入 holdings_snapshot）
const recommendedAsPositions = computed(() => {
  const ar = latestAnalysis.value?.analysis_result
  if (!ar || typeof ar !== 'object') return []
  let rec = ar.recommendedStocks
  if ((!rec || !rec.length) && ar.structured && Array.isArray(ar.structured.recommendedStocks)) {
    rec = ar.structured.recommendedStocks
  }
  if (!Array.isArray(rec) || !rec.length) return []
  return rec.map((s) => ({
    name: s.name || '',
    code: s.code || '',
    price: s.price ?? 0,
    changePct: Number(s.changePct) || 0,
    sector: s.sector || '',
  }))
})

// 持仓快照：DB 快照 > 实时 holdings > 分析推荐股
const analysisPositions = computed(() => {
  const snap = latestAnalysis.value?.holdings_snapshot
  if (snap && Array.isArray(snap) && snap.length) {
    return snap.map((h) => ({
      name: h.stock_name || h.name || '',
      code: h.stock_code || h.code || '',
      price: h.current_price ?? h.price ?? 0,
      changePct: Number(h.profit_loss_pct ?? h.changePct) || 0,
      sector: h.sector || '',
    }))
  }
  if (positions.value.length) return positions.value
  return recommendedAsPositions.value
})

// 行业分布（从持仓推导）
const sectors = computed(() => {
  const snaps = analysisPositions.value
  if (!snaps.length) return []
  const map = {}
  for (const p of snaps) {
    const sec = p.sector || '其他'
    map[sec] = (map[sec] || 0) + 1
  }
  const total = snaps.length
  const entries = Object.entries(map).sort((a, b) => b[1] - a[1])
  return entries.map(([name, count], i) => ({
    name,
    pct: Math.round((count / total) * 100),
    opacity: 1 - i * 0.15,
  }))
})

// AI 分析文案（来自最新分析记录）
const analysisText = computed(() => {
  const ar = latestAnalysis.value?.analysis_result
  if (!ar) return agent.value?.holdings?.analysisText || ''
  const parts = []
  if (ar.marketCommentary) parts.push(ar.marketCommentary)
  if (ar.positionAdvice)   parts.push(ar.positionAdvice)
  if (ar.riskWarning)      parts.push('⚠ ' + ar.riskWarning)
  return parts.join(' | ') || agent.value?.holdings?.analysisText || ''
})

// 总资产（mock + 真实持仓数据补充）
const assets = computed(() => {
  const posVal = rawHoldings.value?.totalPositionValue || 0
  const pnl    = rawHoldings.value?.totalProfitLoss      || 0
  const mock   = agent.value?.holdings?.assets           || {}
  // 今日盈亏≈持仓盈亏，累计用 mock 的 cumPnl
  return {
    totalCny:  mock.totalCny  || String(posVal.toFixed(2)),
    todayPnl:  String(pnl.toFixed(2)),
    todayPct:  mock.todayPct  || '0',
    cumPnl:    mock.cumPnl    || String(pnl.toFixed(2)),
    cumPct:    mock.cumPct    || '0',
  }
})

// 7日图表：今天用真实持仓盈亏，昨天用最新的历史记录，其余留空
const chartBars = computed(() => {
  const snap = latestAnalysis.value
  if (!snap) {
    return [...agent.value?.holdings?.chartBars || Array(7).fill(30)]
  }
  const pnl = parseFloat(rawHoldings.value?.totalProfitLoss || 0)
  // 今天按盈亏等比映射到基准值，后几天暂无数据填 0
  const base = 50
  const todayBar = Math.min(100, Math.max(5, base + pnl / 200))
  return [40, 55, 45, 75, 60, 90, Math.round(todayBar)]
})

const chartLabels = computed(() => [...agent.value?.holdings?.chartLabels || ['-','-','-','-','-','昨天','今天']])

// 总持仓数（含快照/推荐兜底行数）
const totalPositionCount = computed(() => {
  const n = rawHoldings.value?.totalPositionCount
  if (n != null && n > 0) return n
  const rows = analysisPositions.value
  return rows.length
})

// 统一暴露给模板（必须 .value 解包，否则 h.loading 是 Ref 对象，v-if 永远为真）
const h = computed(() => ({
  assets: assets.value,
  chartBars: chartBars.value,
  chartLabels: chartLabels.value,
  sectors: sectors.value,
  analysisText: analysisText.value,
  positions: analysisPositions.value,
  totalPositionCount: totalPositionCount.value,
  loading: loading.value,
  error: error.value,
  hasRealData: !!latestAnalysis.value,
}))

// 日期药丸：最近分析日期 + 昨天 + 更早
const datePills = computed(() => {
  const rd = latestAnalysis.value?.report_date
  const today = new Date()
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1)
  const fmt = d => `${d.getMonth()+1}/${d.getDate()}`
  const pills = [{ key: 'latest', label: rd ? `最近 ${rd}` : '最近分析' }]
  pills.push({ key: 'yesterday', label: fmt(yesterday) })
  pills.push({ key: 'more', label: '更早', calendar: true })
  return pills
})

function onDatePill(d) {
  if (d.key === 'more') {
    toast.value = '历史日期分析记录即将接入'
    return
  }
  dateKey.value = d.key
}

// 拉取真实数据
async function fetchData() {
  loading.value = true
  error.value   = null
  try {
    const [holdingsRes, analysisRes] = await Promise.all([
      fetch('/api/holdings').then(r => r.json()).catch(() => null),
      fetch(`/api/agents/${agentId.value}/analysis/latest`).then(r => r.json()).catch(() => null),
    ])
    if (holdingsRes?.success)  rawHoldings.value   = holdingsRes.data
    if (analysisRes?.success)   latestAnalysis.value = analysisRes.data
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/strategy/agents')
}

function pnlTone(s) {
  const t = String(s).trim()
  if (t.startsWith('-')) return 'ah-down'
  return 'ah-up'
}

function formatSignedMoney(s) {
  const t = String(s).trim()
  if (t.startsWith('-')) return `¥${t}`
  return `+¥${t}`
}

function formatSignedPct(s) {
  const t = String(s).trim()
  if (t.startsWith('-')) return t + '%'
  if (t.startsWith('+')) return t + '%'
  return '+' + t + '%'
}

function chipClass(s) {
  return String(s).trim().startsWith('-') ? 'ah-pct--down' : 'ah-pct--up'
}

function barOpacity(i) {
  const steps = [0.2, 0.3, 0.25, 0.6, 0.4, 0.8, 1]
  return steps[i] ?? 0.35
}
</script>

<style scoped>
.ah-page {
  --primary: #4a47d2;
  --primary-mid: #6462ec;
  --on-surface: #1a1c1f;
  --on-var: #414755;
  --surface: #f9f9fe;
  --low: #f3f3f8;
  --high: #e8e8ed;
  --highest: #e2e2e7;
  --track: #ededf2;
  --up: #006b1b;
  --up-chip: #70ff76;
  --on-up-chip: #002204;
  --down: #ba1a1a;
  --line: rgba(193, 198, 215, 0.15);

  min-height: 100vh;
  min-height: 100dvh;
  background: var(--surface);
  color: var(--on-surface);
  padding-bottom: calc(88px + env(safe-area-inset-bottom, 0));
  font-family: 'Inter', var(--font, system-ui, sans-serif);
  -webkit-font-smoothing: antialiased;
}

.ah-top {
  position: sticky;
  top: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: calc(12px + env(safe-area-inset-top, 0)) 14px 12px;
  background: var(--surface);
}

.ah-top__title {
  flex: 1;
  margin: 0;
  font-size: 1.35rem;
  font-weight: 600;
  letter-spacing: -0.02em;
  text-align: center;
}

.ah-top__actions {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 88px;
  justify-content: flex-end;
}

.ah-top__icon {
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: var(--on-surface);
  background: transparent;
}
.ah-top__icon--back {
  color: var(--primary);
}
.ah-top__icon:active {
  background: rgba(0, 0, 0, 0.05);
}

.ah-main {
  max-width: 720px;
  margin: 0 auto;
  padding: 8px 16px 28px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.ah-dates {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 6px;
  scrollbar-width: none;
}
.ah-dates::-webkit-scrollbar {
  display: none;
}

.ah-date-pill {
  flex-shrink: 0;
  padding: 8px 18px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  background: var(--low);
  color: var(--on-var);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.ah-date-pill--on {
  background: var(--primary);
  color: #fff;
  box-shadow: 0 2px 8px rgba(74, 71, 210, 0.2);
}
.ah-date-cal {
  opacity: 0.9;
}

.ah-card {
  background: #fff;
  border-radius: 1.25rem;
  box-shadow: 0 8px 32px rgba(26, 28, 31, 0.04);
  outline: 1px solid rgba(193, 198, 215, 0.12);
}

.ah-card--hero {
  position: relative;
  overflow: hidden;
  padding: 24px 22px 22px;
}

.ah-hero__deco {
  position: absolute;
  top: 8px;
  right: 12px;
  opacity: 0.08;
  pointer-events: none;
  color: var(--on-surface);
}
.ah-hero__wallet {
  width: 96px;
  height: 96px;
}

.ah-label {
  margin: 0 0 4px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--on-var);
}

.ah-asset {
  margin: 0;
  font-size: clamp(1.75rem, 7vw, 2.65rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.1;
}

.ah-pnl-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-top: 22px;
  padding-top: 22px;
  border-top: 1px solid var(--line);
}

.ah-pnl-lbl {
  margin: 0 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--on-var);
}

.ah-pnl-row {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
}

.ah-pnl-val {
  font-size: 1.15rem;
  font-weight: 800;
}

.ah-pct {
  font-size: 10px;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 999px;
}
.ah-pct--up {
  background: var(--up-chip);
  color: var(--on-up-chip);
}

.ah-pct--down {
  background: #ffdad6;
  color: #93000a;
}

.ah-up {
  color: var(--up) !important;
}
.ah-down {
  color: var(--down) !important;
}

.ah-bento {
  display: grid;
  gap: 16px;
}

@media (min-width: 640px) {
  .ah-bento {
    grid-template-columns: 7fr 5fr;
    align-items: start;
  }
}

.ah-chart-card {
  padding: 20px 18px 32px;
}

.ah-chart-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 22px;
}

.ah-h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.ah-h2--mb {
  margin-bottom: 18px;
}

.ah-link {
  font-size: 12px;
  font-weight: 700;
  color: var(--primary);
  background: none;
  padding: 4px;
}

.ah-bars {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 6px;
  height: 140px;
  padding: 0 4px;
}

.ah-bar-wrap {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
}

.ah-bar-track {
  flex: 1;
  width: 100%;
  min-height: 80px;
  background: var(--low);
  border-radius: 8px 8px 0 0;
  position: relative;
  display: flex;
  align-items: flex-end;
}

.ah-bar-fill {
  width: 100%;
  border-radius: 8px 8px 0 0;
  background: var(--primary);
  min-height: 4px;
  transition: opacity 0.2s ease;
}

.ah-bar-lbl {
  margin-top: 8px;
  font-size: 10px;
  color: var(--on-var);
  text-align: center;
}
.ah-bar-lbl--bold {
  font-weight: 800;
  color: var(--on-surface);
}

.ah-sector-card {
  padding: 20px 18px;
}

.ah-sectors {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ah-sector-head {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 6px;
}

.ah-sector-track {
  height: 8px;
  background: var(--track);
  border-radius: 999px;
  overflow: hidden;
}

.ah-sector-bar {
  height: 100%;
  border-radius: 999px;
  background: var(--primary);
}

.ah-ai {
  display: flex;
  gap: 12px;
  padding: 18px 18px 18px 16px;
  background: #fff;
  border-radius: 14px;
  border-left: 4px solid var(--primary);
  box-shadow: 0 4px 24px rgba(26, 28, 31, 0.04);
}

.ah-ai__ico {
  flex-shrink: 0;
  color: var(--primary);
  fill: currentColor;
  margin-top: 2px;
}

.ah-ai__cta {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-left: 8px;
  align-self: center;
  cursor: pointer;
  transition: opacity 0.15s ease, transform 0.1s ease;
  padding: 0;
}
.ah-ai__cta:active { opacity: 0.8; transform: scale(0.95); }
.ah-ai__cta .icon { width: 16px; height: 16px; }

.ah-ai__title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 800;
}

.ah-ai__body {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--on-var);
}

.ah-table-card {
  overflow: hidden;
  padding: 0;
}

.ah-table-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 18px;
  background: rgba(243, 243, 248, 0.65);
}

.ah-filter {
  color: var(--on-var) !important;
}

.ah-table-scroll {
  overflow-x: auto;
}

.ah-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.ah-table thead tr {
  background: rgba(243, 243, 248, 0.4);
}

.ah-table th {
  padding: 12px 16px;
  text-align: left;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--on-var);
}

.ah-table td {
  padding: 16px;
  vertical-align: middle;
}

.ah-table tbody tr {
  box-shadow: 0 1px 0 var(--line);
}

.ah-table tbody tr:hover {
  background: rgba(243, 243, 248, 0.5);
}

.ah-num {
  text-align: right;
}

.ah-stock-name {
  display: block;
  font-weight: 800;
  margin-bottom: 4px;
}

.ah-stock-code {
  font-size: 10px;
  font-weight: 600;
  color: var(--on-var);
}

.ah-view-all {
  width: 100%;
  padding: 14px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--primary);
  background: rgba(74, 71, 210, 0.06);
}
.ah-view-all:active {
  background: rgba(74, 71, 210, 0.1);
}

.ah-footnote {
  margin: 4px 0 0;
  font-size: 11px;
  line-height: 1.5;
  color: var(--on-var);
}

.ah-empty {
  padding: 48px 24px;
  text-align: center;
  color: var(--on-var);
}
.ah-empty__btn {
  margin-top: 16px;
  padding: 12px 20px;
  border-radius: 12px;
  font-weight: 700;
  background: linear-gradient(135deg, var(--primary), var(--primary-mid));
  color: #fff;
}

.ah-toast {
  position: fixed;
  left: 50%;
  bottom: calc(100px + env(safe-area-inset-bottom, 0));
  transform: translateX(-50%);
  z-index: 200;
  padding: 10px 18px;
  border-radius: 10px;
  background: rgba(26, 28, 31, 0.88);
  color: #fff;
  font-size: 13px;
  max-width: 90%;
  text-align: center;
  pointer-events: none;
}

.ah-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 24px;
  color: var(--on-var);
  font-size: 13px;
}

.ah-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--low);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: ah-spin 0.8s linear infinite;
}

@keyframes ah-spin {
  to { transform: rotate(360deg); }
}
</style>
