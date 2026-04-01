<template>
  <div class="stk">
    <header class="stk-bar">
      <button type="button" class="stk-bar__btn" aria-label="返回" @click="router.back()">
        <svg viewBox="0 0 24 24" width="22" height="22"><path fill="currentColor" d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
      </button>
      <h1 class="stk-bar__title">{{ stockRow?.name || '股票详情' }}</h1>
      <button
        type="button"
        class="stk-bar__star"
        :class="{ on: inWatchlist }"
        :title="inWatchlist ? '取消自选' : '加自选'"
        @click="toggleWatchlist"
      >
        <svg viewBox="0 0 24 24" width="20" height="20">
          <path
            :fill="inWatchlist ? 'var(--stk-primary)' : 'none'"
            :stroke="inWatchlist ? 'var(--stk-primary)' : 'currentColor'"
            stroke-width="1.5"
            d="M12 17.3l5.2 3.1-1.4-5.9L20 9.8l-6-.5L12 3.7 9.9 9.3l-6 .5 4.2 4.7-1.4 5.9 5.3-3.1z"
          />
        </svg>
      </button>
    </header>

    <main class="stk-main">
      <div v-if="loadErr" class="stk-err">{{ loadErr }}</div>
      <div v-else-if="loading" class="stk-loading">
        <div class="stk-spin" />
        <p>加载行情…</p>
      </div>
      <template v-else-if="stockRow">
        <div ref="detailsRootRef" class="stk-details">
          <button
            type="button"
            class="stk-details__trigger"
            :aria-expanded="detailsOpen"
            @click="detailsOpen = !detailsOpen"
          >
            <span class="stk-details__trigger-label">股票详情</span>
            <span class="stk-details__trigger-mid tabular">{{ fmtPrice(stockRow) }}</span>
            <span class="stk-details__trigger-mid tabular" :class="tvDir(stockRow)">{{ fmtDeltaLine(stockRow) }}</span>
            <span class="stk-details__chev" :class="{ 'is-open': detailsOpen }" aria-hidden="true" />
          </button>
          <div v-show="detailsOpen" class="stk-details__panel">
            <div class="stk-price">
              <div class="stk-price__row">
                <span class="stk-price__px tabular">{{ fmtPrice(stockRow) }}</span>
                <span class="stk-price__chg tabular" :class="tvDir(stockRow)">{{ fmtDeltaLine(stockRow) }}</span>
              </div>
              <div class="stk-price__meta">
                <span class="stk-tag">{{ stockRow.code }}</span>
                <span v-if="stockRow.sector" class="stk-tag">{{ stockRow.sector }}</span>
              </div>
            </div>

            <div v-if="quoteBlk" class="stk-stats">
              <div class="stk-stats__row">
                <div class="stk-stat"><span class="stk-stat__l">今开</span><span class="stk-stat__v">{{ fmtVal(quoteBlk.open) }}</span></div>
                <div class="stk-stat"><span class="stk-stat__l">最高</span><span class="stk-stat__v">{{ fmtVal(quoteBlk.high) }}</span></div>
                <div class="stk-stat"><span class="stk-stat__l">最低</span><span class="stk-stat__v">{{ fmtVal(quoteBlk.low) }}</span></div>
              </div>
              <div class="stk-stats__row">
                <div class="stk-stat"><span class="stk-stat__l">成交量</span><span class="stk-stat__v">{{ fmtAmt(quoteBlk.volume) }}</span></div>
                <div class="stk-stat"><span class="stk-stat__l">成交额</span><span class="stk-stat__v">{{ fmtAmt(quoteBlk.amount) }}</span></div>
                <div class="stk-stat"><span class="stk-stat__l">换手率</span><span class="stk-stat__v">{{ fmtPct(quoteBlk.turnover) }}</span></div>
              </div>
              <div class="stk-stats__row">
                <div class="stk-stat"><span class="stk-stat__l">量比</span><span class="stk-stat__v">{{ fmtVal(quoteBlk.qtyRatio) }}</span></div>
                <div class="stk-stat"><span class="stk-stat__l">总市值</span><span class="stk-stat__v">{{ fmtCap(quoteBlk.mktCap) }}</span></div>
                <div class="stk-stat"><span class="stk-stat__l">市盈率</span><span class="stk-stat__v">{{ fmtVal(quoteBlk.pe) }}</span></div>
              </div>
            </div>
          </div>
        </div>

        <div class="stk-chart">
          <KlineChart v-if="stockRow.code" :code="stockRow.code" />
        </div>

        <div class="stk-more">
          <p class="stk-more__title">更多股票详情</p>
          <a
            class="stk-more__entry"
            :href="tvChartHref"
          >
            <span class="stk-more__entry-text">TradingView 专业图表</span>
            <span class="stk-more__entry-arr" aria-hidden="true">›</span>
          </a>
        </div>
      </template>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { stock, watchlist } from '@/api/strategy.js'
import KlineChart from '@/components/KlineChart.vue'
import { tvSymbolFromChinaCode6 } from '@/utils/tvSymbol.js'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const loadErr = ref('')
const stockRow = ref(null)
const quoteBlk = ref(null)
const inWatchlist = ref(false)
const detailsOpen = ref(false)
const detailsRootRef = ref(null)

function onDocClickDetails(e) {
  const el = detailsRootRef.value
  if (!el || !detailsOpen.value) return
  if (!el.contains(e.target)) detailsOpen.value = false
}

onMounted(() => {
  document.addEventListener('click', onDocClickDetails)
})
onUnmounted(() => {
  document.removeEventListener('click', onDocClickDetails)
})

const codeNorm = computed(() => {
  const c = String(route.params.code || '').trim()
  return /^\d{6}$/.test(c) ? c : ''
})

/** TradingView H5：同窗口打开（更像 App 内页），行情走同源 /tv_udf */
const tvChartHref = computed(() => {
  const c = codeNorm.value
  if (!c) return '#'
  const q = new URLSearchParams({
    symbol: tvSymbolFromChinaCode6(c),
    locale: 'zh',
    return: route.fullPath || `/stock/${c}`,
  })
  const nm = (stockRow.value?.name || '').trim()
  if (nm) q.set('name', nm)
  const path = `/charting_library/mobile_white.html?${q.toString()}`
  if (typeof window !== 'undefined') {
    return new URL(path, window.location.origin).href
  }
  return path
})

function tvDir(s) {
  const n = Number(s?.pct_change)
  if (!Number.isFinite(n)) return ''
  return n >= 0 ? 'is-up' : 'is-down'
}

function fmtPrice(s) {
  const n = Number(s?.close)
  return Number.isFinite(n) ? n.toFixed(2) : '--'
}

function fmtDeltaLine(s) {
  const pct = Number(s.pct_change)
  if (Number.isFinite(s.change_amt) && s.change_amt !== null) {
    const sd = s.change_amt >= 0 ? '+' : ''
    const sp = pct >= 0 ? '+' : ''
    return `${sd}${Number(s.change_amt).toFixed(2)} ${sp}${pct.toFixed(2)}%`
  }
  const close = Number(s.close)
  if (!Number.isFinite(pct) || !Number.isFinite(close)) return '--'
  const prev = close / (1 + pct / 100)
  const delta = close - prev
  const sd = delta >= 0 ? '+' : ''
  const sp = pct >= 0 ? '+' : ''
  return `${sd}${delta.toFixed(2)} ${sp}${pct.toFixed(2)}%`
}

function fmtVal(v) {
  if (v == null || v === '-' || Number.isNaN(Number(v))) return '--'
  return Number(v).toFixed(2)
}

function fmtPct(v) {
  if (v == null || Number.isNaN(Number(v))) return '--'
  const n = Number(v)
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%'
}

function fmtAmt(v) {
  if (v == null || Number.isNaN(Number(v))) return '--'
  const n = Number(v)
  const abs = Math.abs(n)
  if (abs >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return (n / 1e4).toFixed(0) + '万'
  return n.toFixed(0)
}

function fmtCap(v) {
  if (v == null || Number.isNaN(Number(v))) return '--'
  const n = Number(v)
  if (n >= 1e12) return (n / 1e12).toFixed(2) + '万亿'
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(0) + '万'
  return String(n)
}

function mapQuoteToRows(q) {
  if (!q || typeof q !== 'object') return
  const row = {
    code: q.code,
    name: q.name || '—',
    close: q.close,
    pct_change: q.pct_change,
    change_amt: q.change != null ? q.change : q.change_amt,
    sector: q.sector || '',
  }
  const blk = {
    open: q.open,
    high: q.high,
    low: q.low,
    volume: q.volume,
    amount: q.amount,
    turnover: q.turnover,
    qtyRatio: q.qty_ratio != null ? q.qty_ratio : q.qtyRatio,
    amplitude: q.amplitude,
    pe: q.pe,
    pb: q.pb,
    mktCap: q.mkt_cap != null ? q.mkt_cap : q.mktCap,
    floatMktCap: q.float_mkt_cap != null ? q.float_mkt_cap : q.floatMktCap,
  }
  return { row, blk }
}

async function refresh() {
  const code = codeNorm.value
  if (!code) {
    loadErr.value = '无效的股票代码'
    loading.value = false
    stockRow.value = null
    quoteBlk.value = null
    return
  }
  loading.value = true
  loadErr.value = ''
  try {
    try {
      const ok = await watchlist.check(code)
      inWatchlist.value = Boolean(ok?.in_watchlist)
    } catch {
      inWatchlist.value = false
    }

    const raw = await stock.quote(code)
    const q = raw && typeof raw === 'object' && raw.success !== undefined
      ? { ...raw }
      : raw
    if (q && typeof q === 'object') delete q.success

    if (!q || (q.name == null || q.name === '') && (q.close == null || q.close === undefined)) {
      throw new Error('暂无行情数据')
    }
    const mapped = mapQuoteToRows(q)
    if (!mapped.row.code) mapped.row.code = code
    stockRow.value = mapped.row
    quoteBlk.value = mapped.blk
  } catch (e) {
    loadErr.value = e?.message || '加载失败'
    stockRow.value = null
    quoteBlk.value = null
  } finally {
    loading.value = false
  }
}

async function toggleWatchlist() {
  if (!stockRow.value) return
  const code = stockRow.value.code
  const name = stockRow.value.name
  const sector = stockRow.value.sector
  try {
    if (inWatchlist.value) {
      await watchlist.remove(code)
      inWatchlist.value = false
    } else {
      await watchlist.add(code, name, sector)
      inWatchlist.value = true
    }
  } catch (e) {
    alert(e?.message || '操作失败')
  }
}

watch(codeNorm, () => {
  refresh()
}, { immediate: true })
</script>

<style scoped>
.stk {
  --stk-primary: #003ec7;
  --stk-primary-mid: #0052ff;
  --stk-rise: #f23645;
  --stk-fall: #089981;
  --stk-surface: #f8f9fa;
  --stk-on-surface: #191c1d;
  --stk-on-variant: #434656;
  --stk-outline: #737688;

  min-height: 100vh;
  min-height: 100dvh;
  background: var(--stk-surface);
  color: var(--stk-on-surface);
  padding-bottom: calc(env(safe-area-inset-bottom) + 72px);
  font-family: Inter, var(--font, system-ui), sans-serif;
}
.tabular {
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum' 1;
}

.stk-bar {
  position: sticky;
  top: 0;
  z-index: 40;
  display: grid;
  grid-template-columns: 44px 1fr 44px;
  align-items: center;
  min-height: calc(48px + env(safe-area-inset-top, 0));
  padding: env(safe-area-inset-top, 0) 8px 0;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(16px);
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.06);
}
.stk-bar__btn,
.stk-bar__star {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--stk-on-surface);
  cursor: pointer;
}
.stk-bar__btn:active,
.stk-bar__star:active {
  background: rgba(0, 0, 0, 0.05);
}
.stk-bar__title {
  margin: 0;
  text-align: center;
  font-size: 1rem;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.stk-bar__star.on {
  color: var(--stk-primary-mid);
}

.stk-main {
  padding: 16px 14px 24px;
  max-width: 560px;
  margin: 0 auto;
}
.stk-loading,
.stk-err {
  text-align: center;
  padding: 48px 16px;
  color: var(--stk-on-variant);
  font-size: 14px;
}
.stk-err {
  color: #ba1a1a;
}
.stk-spin {
  width: 28px;
  height: 28px;
  border: 2px solid #e7e8e9;
  border-top-color: var(--stk-primary);
  border-radius: 50%;
  animation: stk-spin 0.75s linear infinite;
  margin: 0 auto 12px;
}
@keyframes stk-spin {
  to {
    transform: rotate(360deg);
  }
}

.stk-details {
  margin-bottom: 16px;
}
.stk-details__trigger {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 12px 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  font: inherit;
  color: var(--stk-on-surface);
  cursor: pointer;
  text-align: left;
  -webkit-tap-highlight-color: transparent;
}
.stk-details__trigger:active {
  background: #fafafa;
}
.stk-details__trigger-label {
  font-size: 14px;
  font-weight: 700;
  color: var(--stk-on-surface);
  margin-right: auto;
}
.stk-details__trigger-mid {
  font-size: 14px;
  font-weight: 700;
}
.stk-details__trigger-mid.is-up {
  color: var(--stk-rise);
}
.stk-details__trigger-mid.is-down {
  color: var(--stk-fall);
}
.stk-details__chev {
  width: 10px;
  height: 10px;
  margin-left: 4px;
  border-right: 2px solid var(--stk-outline);
  border-bottom: 2px solid var(--stk-outline);
  transform: rotate(45deg);
  transition: transform 0.2s ease;
  flex-shrink: 0;
}
.stk-details__chev.is-open {
  transform: rotate(-135deg);
  margin-top: 4px;
}
.stk-details__panel {
  margin-top: 10px;
  padding-top: 4px;
}
.stk-details__panel .stk-price {
  margin-bottom: 14px;
}
.stk-details__panel .stk-stats {
  margin-bottom: 0;
}

.stk-price {
  margin-bottom: 18px;
}
.stk-price__row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
}
.stk-price__px {
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.stk-price__chg {
  font-size: 1.125rem;
  font-weight: 700;
}
.stk-price__chg.is-up {
  color: var(--stk-rise);
}
.stk-price__chg.is-down {
  color: var(--stk-fall);
}
.stk-price__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.stk-tag {
  font-size: 13px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 8px;
  background: #fff;
  color: var(--stk-on-variant);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.stk-stats {
  background: #fff;
  border-radius: 16px;
  padding: 4px 0;
  margin-bottom: 20px;
  box-shadow: 0 4px 20px rgba(25, 28, 29, 0.05);
}
.stk-stats__row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}
.stk-stats__row:last-child {
  border-bottom: none;
}
.stk-stat {
  padding: 12px 10px;
  text-align: center;
  border-right: 1px solid rgba(0, 0, 0, 0.05);
}
.stk-stat:last-child {
  border-right: none;
}
.stk-stat__l {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--stk-outline);
  margin-bottom: 4px;
}
.stk-stat__v {
  font-size: 14px;
  font-weight: 700;
}

.stk-chart {
  border-radius: 16px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 4px 20px rgba(25, 28, 29, 0.05);
}
.stk-chart :deep(.kline-wrap) {
  min-height: 280px;
}

.stk-more {
  margin-top: 20px;
}
.stk-more__title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 700;
  color: var(--stk-on-variant);
  letter-spacing: -0.02em;
}
.stk-more__entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  text-decoration: none;
  color: var(--stk-on-surface);
  font-size: 15px;
  font-weight: 600;
  -webkit-tap-highlight-color: transparent;
  transition: background 0.15s ease, border-color 0.15s ease;
}
.stk-more__entry:active {
  background: #fafafa;
}
.stk-more__entry-text {
  flex: 1;
}
.stk-more__entry-arr {
  font-size: 22px;
  font-weight: 300;
  color: var(--stk-outline);
  line-height: 1;
}
</style>
