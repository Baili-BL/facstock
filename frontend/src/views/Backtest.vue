<template>
  <div class="bt-page">
    <!-- 页头 -->
    <header class="bt-header">
      <div class="bt-header__inner">
        <button type="button" class="bt-back" aria-label="返回" @click="$router.push('/strategy')">
          <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
        </button>
        <div class="bt-header__brand">
          <h1 class="bt-header__title">量化回测</h1>
        </div>
      </div>
    </header>

    <main class="bt-main">
      <!-- 配置面板 -->
      <section class="bt-config">
        <h2 class="bt-section-title">回测配置</h2>

        <div class="bt-form">
          <!-- 股票代码 -->
          <div class="bt-field">
            <label class="bt-field__label">股票代码</label>
            <div class="bt-code-row">
              <input
                v-model="stockCode"
                class="bt-input"
                placeholder="600519"
                maxlength="6"
                @keydown.enter="runBacktest"
              >
              <button type="button" class="bt-btn bt-btn--ghost" @click="showStockSearch = true">
                搜索
              </button>
            </div>
            <div v-if="stockName" class="bt-field__hint">{{ stockName }}</div>
          </div>

          <!-- 策略模板 -->
          <div class="bt-field">
            <label class="bt-field__label">策略模板</label>
            <select v-model="templateId" class="bt-select" @change="onTemplateChange">
              <option v-for="t in catalog" :key="t.id" :value="t.id">{{ t.name }}</option>
            </select>
            <div class="bt-field__hint">{{ activeTemplate?.description }}</div>
          </div>

          <!-- 动态参数 -->
          <div v-if="activeTemplate?.params?.length" class="bt-params">
            <div v-for="p in activeTemplate.params" :key="p.id" class="bt-field">
              <label class="bt-field__label">{{ p.name }}</label>
              <div class="bt-param-row">
                <input
                  v-model.number="params[p.id]"
                  class="bt-input bt-input--sm"
                  :type="p.type === 'float' ? 'number' : 'number'"
                  :min="p.min" :max="p.max" :step="p.type === 'float' ? 0.1 : 1"
                >
                <span class="bt-param-range">
                  {{ p.min }}~{{ p.max }}
                </span>
              </div>
            </div>
          </div>

          <!-- 时间范围 -->
          <div class="bt-field">
            <label class="bt-field__label">回测时间范围</label>
            <div class="bt-range-btns">
              <button
                v-for="r in rangeOptions"
                :key="r.label"
                type="button"
                class="bt-range-btn"
                :class="{ 'bt-range-btn--active': selectedRange === r.value }"
                @click="setRange(r.value)"
              >{{ r.label }}</button>
            </div>
            <div class="bt-date-row">
              <input v-model="startDate" type="date" class="bt-input bt-input--date">
              <span class="bt-date-sep">~</span>
              <input v-model="endDate" type="date" class="bt-input bt-input--date">
            </div>
          </div>

          <!-- 初始资金 -->
          <div class="bt-field">
            <label class="bt-field__label">初始资金（元）</label>
            <input v-model.number="initialCash" type="number" class="bt-input bt-input--sm" min="10000" step="10000">
          </div>

          <!-- 执行按钮 -->
          <button
            type="button"
            class="bt-btn bt-btn--primary bt-run-btn"
            :disabled="running || !stockCode || stockCode.length !== 6"
            @click="runBacktest"
          >
            <span v-if="running" class="bt-spinner"></span>
            {{ running ? '回测中…' : '开始回测' }}
          </button>
        </div>

        <!-- 错误提示 -->
        <div v-if="errorMsg" class="bt-error">
          <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
          {{ errorMsg }}
        </div>
      </section>

      <!-- 回测结果 -->
      <section v-if="result" class="bt-result">

        <h2 class="bt-section-title">回测结果</h2>

        <!-- KPI 统计 -->
        <div class="bt-kpi-grid">
          <div class="bt-kpi-card" :class="kpiClass(result.totalReturnPct)">
            <div class="bt-kpi-card__val">{{ signPct(result.totalReturnPct) }}%</div>
            <div class="bt-kpi-card__lbl">总收益率</div>
          </div>
          <div class="bt-kpi-card">
            <div class="bt-kpi-card__val">{{ result.annualReturnPct?.toFixed(1) }}%</div>
            <div class="bt-kpi-card__lbl">年化收益率</div>
          </div>
          <div class="bt-kpi-card" :class="kpiClass(-result.maxDrawdownPct)">
            <div class="bt-kpi-card__val">-{{ result.maxDrawdownPct?.toFixed(2) }}%</div>
            <div class="bt-kpi-card__lbl">最大回撤</div>
          </div>
          <div class="bt-kpi-card">
            <div class="bt-kpi-card__val">{{ result.sharpeRatio?.toFixed(2) }}</div>
            <div class="bt-kpi-card__lbl">夏普比率</div>
          </div>
          <div class="bt-kpi-card">
            <div class="bt-kpi-card__val">{{ result.winRatePct?.toFixed(1) }}%</div>
            <div class="bt-kpi-card__lbl">胜率</div>
          </div>
          <div class="bt-kpi-card">
            <div class="bt-kpi-card__val">{{ result.tradeCount }}</div>
            <div class="bt-kpi-card__lbl">交易次数</div>
          </div>
          <div class="bt-kpi-card">
            <div class="bt-kpi-card__val">{{ result.profitLossRatio?.toFixed(2) }}</div>
            <div class="bt-kpi-card__lbl">盈亏比</div>
          </div>
          <div class="bt-kpi-card">
            <div class="bt-kpi-card__val">{{ result.initialCash?.toLocaleString() }}</div>
            <div class="bt-kpi-card__lbl">初始资金</div>
          </div>
        </div>

        <!-- 权益曲线 + 回撤曲线 -->
        <div class="bt-charts-row">
          <div class="bt-chart-card">
            <div class="bt-chart-card__title">权益曲线</div>
            <div ref="equityChartRef" class="bt-chart-canvas"></div>
          </div>
          <div class="bt-chart-card">
            <div class="bt-chart-card__title">回撤曲线</div>
            <div ref="drawdownChartRef" class="bt-chart-canvas"></div>
          </div>
        </div>

        <!-- K 线 + 买卖点 -->
        <div class="bt-chart-card bt-chart-card--wide">
          <div class="bt-chart-card__title">
            K 线图（含买卖点标注）
            <span class="bt-chart-legend">
              <span class="bt-legend-buy">▲ 买入</span>
              <span class="bt-legend-sell">▼ 卖出</span>
            </span>
          </div>
          <div ref="klineChartRef" class="bt-chart-canvas bt-chart-canvas--tall"></div>
        </div>

        <!-- 交易记录 -->
        <details v-if="result.trades?.length" class="bt-trades">
          <summary class="bt-trades__summary">
            交易记录（{{ result.trades.length }} 笔）
          </summary>
          <table class="bt-trades-table">
            <thead>
              <tr>
                <th>买入日期</th>
                <th>买入价</th>
                <th>卖出日期</th>
                <th>卖出价</th>
                <th>收益率</th>
                <th>持仓天数</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(t, i) in result.trades" :key="i" :class="t.pnlAbs >= 0 ? 'bt-trade--win' : 'bt-trade--loss'">
                <td>{{ t.buyDate }}</td>
                <td>{{ t.buyPrice?.toFixed(2) }}</td>
                <td>{{ t.sellDate }}</td>
                <td>{{ t.sellPrice?.toFixed(2) }}</td>
                <td :class="t.pnlPct >= 0 ? 'bt-win' : 'bt-loss'">
                  {{ t.pnlPct >= 0 ? '+' : '' }}{{ t.pnlPct?.toFixed(2) }}%
                </td>
                <td>{{ t.holdDays }} 天</td>
              </tr>
            </tbody>
          </table>
        </details>
      </section>
    </main>

    <!-- 股票搜索弹窗 -->
    <Teleport to="body">
      <div v-if="showStockSearch" class="bt-modal-overlay" @click.self="showStockSearch = false">
        <div class="bt-modal">
          <div class="bt-modal__header">
            <h3>搜索股票</h3>
            <button class="bt-modal__close" @click="showStockSearch = false">✕</button>
          </div>
          <div class="bt-modal__body">
            <input
              v-model="searchKeyword"
              class="bt-input"
              placeholder="输入股票代码或名称"
              @input="doSearch"
            >
            <div v-if="searchResults.length" class="bt-search-results">
              <button
                v-for="s in searchResults"
                :key="s.code"
                type="button"
                class="bt-search-item"
                @click="selectStock(s)"
              >
                <span class="bt-search-item__code">{{ s.code }}</span>
                <span class="bt-search-item__name">{{ s.name }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { backtestCatalog, backtestRun } from '@/api/backtest.js'
import { stocks } from '@/api/strategy.js'
import { createChart, createSeriesMarkers } from 'lightweight-charts'

// ── 状态 ──────────────────────────────────────────────────────────────────
const stockCode = ref('')
const stockName = ref('')
const templateId = ref('ma_cross')
const params = ref({})
const startDate = ref('')
const endDate = ref('')
const selectedRange = ref('3m')
const initialCash = ref(100000)
const running = ref(false)
const errorMsg = ref('')
const result = ref(null)

const catalog = ref([])

// 搜索
const showStockSearch = ref(false)
const searchKeyword = ref('')
const searchResults = ref([])
let searchTimer = null

// 图表 refs
const equityChartRef = ref(null)
const drawdownChartRef = ref(null)
const klineChartRef = ref(null)
let equityChart = null
let drawdownChart = null
let klineChart = null
let klineSeries = null
let klineVolumeSeries = null
let buySeries = null
let sellSeries = null

// ── 常量 ──────────────────────────────────────────────────────────────────
const rangeOptions = [
  { label: '近1月', value: '1m', days: 22 },
  { label: '近3月', value: '3m', days: 65 },
  { label: '近半年', value: '6m', days: 130 },
  { label: '近1年', value: '1y', days: 252 },
  { label: '近3年', value: '3y', days: 756 },
  { label: '自定义', value: 'custom', days: 0 },
]

// ── 计算属性 ────────────────────────────────────────────────────────────────
const activeTemplate = computed(() =>
  catalog.value.find(t => t.id === templateId.value)
)

// ── 生命周期 ────────────────────────────────────────────────────────────────
onMounted(async () => {
  try {
    const data = await backtestCatalog()
    catalog.value = data
    if (catalog.value.length) {
      onTemplateChange()
    }
  } catch (e) {
    console.error('catalog load failed', e)
  }

  // 设置默认结束日期 = 今天
  const today = new Date()
  endDate.value = fmtDate(today)
  setRange('3m')
})

onBeforeUnmount(() => {
  destroyCharts()
})

// ── 方法 ──────────────────────────────────────────────────────────────────
function onTemplateChange() {
  const t = activeTemplate.value
  if (!t) return
  const defaults = {}
  for (const p of (t.params || [])) {
    defaults[p.id] = p.default
  }
  params.value = defaults
}

function setRange(value) {
  selectedRange.value = value
  if (value === 'custom') return
  const opt = rangeOptions.find(r => r.value === value)
  if (!opt || !opt.days) return

  const today = new Date()
  endDate.value = fmtDate(today)
  const start = new Date(today)
  start.setDate(start.getDate() - opt.days)
  startDate.value = fmtDate(start)
}

async function runBacktest() {
  if (!stockCode.value || stockCode.value.length !== 6) {
    errorMsg.value = '请输入有效的 6 位股票代码'
    return
  }
  errorMsg.value = ''
  running.value = true
  result.value = null
  destroyCharts()

  try {
    const data = await backtestRun({
      stock_code: stockCode.value,
      template_id: templateId.value,
      params: params.value,
      start_date: startDate.value || undefined,
      end_date: endDate.value || undefined,
      initial_cash: initialCash.value,
      commission_pct: 0.001,
    })
    result.value = data
    if (!data || data.error) {
      errorMsg.value = data?.error || '回测失败'
      result.value = null
    }
  } catch (e) {
    errorMsg.value = e?.message || String(e)
  } finally {
    running.value = false
  }
}

async function doSearch() {
  clearTimeout(searchTimer)
  if (searchKeyword.value.length < 1) {
    searchResults.value = []
    return
  }
  searchTimer = setTimeout(async () => {
    try {
      const { list } = await stocks.search(searchKeyword.value, 10)
      searchResults.value = (list || []).map(s => ({
        code: s.code || s.stock_code,
        name: s.name || s.stock_name,
      }))
    } catch {
      searchResults.value = []
    }
  }, 300)
}

function selectStock(s) {
  stockCode.value = s.code
  stockName.value = s.name
  showStockSearch.value = false
  searchKeyword.value = ''
  searchResults.value = []
}

function fmtDate(d) {
  return d.toISOString().slice(0, 10)
}

function kpiClass(v) {
  if (v === undefined || v === null) return ''
  return v >= 0 ? 'bt-kpi-card--up' : 'bt-kpi-card--down'
}

function signPct(v) {
  if (v === undefined || v === null) return '0'
  return v >= 0 ? `+${v.toFixed(2)}` : v.toFixed(2)
}

// ── 图表渲染 ───────────────────────────────────────────────────────────────
async function renderCharts() {
  if (!result.value) return

  await nextTick()

  // 分阶段等待 paint：setTimeout(0) 让出主线程确保浏览器完成 layout
  await new Promise(r => setTimeout(r, 0))
  // 再等一个 RAF 确保两次 paint cycle
  await new Promise(r => requestAnimationFrame(r))

  console.log('[debug] clientWidth:', equityChartRef.value?.clientWidth, 'offsetWidth:', equityChartRef.value?.offsetWidth)
  console.log('[debug] equity len:', result.value.equity?.length, 'sample:', result.value.equity?.slice(0,3))
  console.log('[debug] times len:', result.value.candles?.times?.length, 'sample:', result.value.candles?.times?.slice(0,3))

  if (equityChartRef.value) renderEquityChart()
  if (drawdownChartRef.value) renderDrawdownChart()
  if (klineChartRef.value) renderKlineChart()
}

function destroyCharts() {
  equityChart?.remove()
  drawdownChart?.remove()
  klineChart?.remove()
  equityChart = null
  drawdownChart = null
  klineChart = null
}

function _getChartWidth(el) {
  // 优先 clientWidth，若仍为 0 则尝试 offsetWidth 或父容器宽度兜底
  return el.clientWidth || el.offsetWidth || (el.parentElement?.clientWidth - 24) || 344
}

function renderEquityChart() {
  const el = equityChartRef.value
  el.innerHTML = ''
  const w = _getChartWidth(el)
  equityChart = createChart(el, { width: w, height: 180, layout: { textColor: '#666' } })
  const s = equityChart.addLineSeries({
    color: '#2196f3',
    lineWidth: 2,
    crosshairMode: 1,
  })
  const times = result.value.candles.times.map(t => t)
  const equity = result.value.equity || []
  s.setData(times.map((t, i) => ({ time: tsToLw(t), value: equity[i] ?? 0 })))
  equityChart.timeScale().fitContent()
  const ro = new ResizeObserver(() => {
    if (equityChart) equityChart.applyOptions({ width: _getChartWidth(el) })
  })
  ro.observe(el)
}

function renderDrawdownChart() {
  const el = drawdownChartRef.value
  el.innerHTML = ''
  const w = _getChartWidth(el)
  drawdownChart = createChart(el, { width: w, height: 180, layout: { textColor: '#666' } })
  const s = drawdownChart.addLineSeries({
    color: '#ef5350',
    lineWidth: 1,
    crosshairMode: 1,
  })
  const times = result.value.candles.times
  const dd = result.value.drawdownPct || []
  s.setData(times.map((t, i) => ({ time: tsToLw(t), value: -(dd[i] ?? 0) })))
  drawdownChart.timeScale().fitContent()
  const ro = new ResizeObserver(() => {
    if (drawdownChart) drawdownChart.applyOptions({ width: _getChartWidth(el) })
  })
  ro.observe(el)
}

function renderKlineChart() {
  const el = klineChartRef.value
  el.innerHTML = ''
  const w = _getChartWidth(el)
  klineChart = createChart(el, { width: w, height: 400, layout: { textColor: '#666' } })
  klineChart.applyOptions({ width: w })

  klineSeries = klineChart.addCandlestickSeries({
    upColor: '#ef5350',
    downColor: '#26a69a',
    borderUpColor: '#ef5350',
    borderDownColor: '#26a69a',
    wickUpColor: '#ef5350',
    wickDownColor: '#26a69a',
  })

  klineVolumeSeries = klineChart.addHistogramSeries({
    color: '#26a69a',
    priceFormat: { type: 'volume' },
    priceScaleId: '',
  })

  const c = result.value.candles
  const candleData = c.times.map((t, i) => ({
    time: tsToLw(t),
    open: c.opens[i],
    high: c.highs[i],
    low: c.lows[i],
    close: c.closes[i],
  }))
  const volData = c.times.map((t, i) => ({
    time: tsToLw(t),
    value: c.volumes[i] ?? 0,
    color: (c.closes[i] >= c.opens[i]) ? '#ef535040' : '#26a69a40',
  }))
  klineSeries.setData(candleData)
  klineVolumeSeries.setData(volData)

  // 买卖点（lightweight-charts v5 用 createSeriesMarkers）
  const allMarkers = [
    ...(result.value.markers?.buy || []).map(m => ({
      time: tsToLw(m.time),
      position: 'belowBar',
      color: '#f59f00',
      shape: 'arrowUp',
      text: '买入',
    })),
    ...(result.value.markers?.sell || []).map(m => ({
      time: tsToLw(m.time),
      position: 'aboveBar',
      color: '#9c27b0',
      shape: 'arrowDown',
      text: '卖出',
    })),
  ].sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0))
  if (allMarkers.length > 0) {
    createSeriesMarkers(klineSeries, allMarkers)
  }

  klineChart.timeScale().fitContent()

  // resize 监听
  const ro = new ResizeObserver(() => {
    if (klineChart) klineChart.applyOptions({ width: _getChartWidth(el) })
  })
  ro.observe(el)
}

function tsToLw(ts) {
  if (!ts) return ''
  const d = new Date(Number(ts) * 1000)
  const y = d.getUTCFullYear()
  const m = String(d.getUTCMonth() + 1).padStart(2, '0')
  const day = String(d.getUTCDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

// ── 监听结果变化 → 重新渲染图表 ───────────────────────────────────────────
watch(result, async (val) => {
  if (val) {
    await nextTick()
    renderCharts()
  }
})
</script>

<style scoped>
/* ── 基础布局 ──────────────────────────────────────────────────────────────── */
.bt-page { min-height: 100dvh; background: #f5f5f7; font-family: system-ui, -apple-system, sans-serif; }
.bt-header { background: #fff; border-bottom: 1px solid rgba(0,0,0,.08); position: sticky; top: 0; z-index: 50; }
.bt-header__inner { display: flex; align-items: center; height: 48px; padding: 0 8px; }
.bt-back { border: none; background: transparent; padding: 10px; cursor: pointer; border-radius: 10px; }
.bt-header__brand { flex: 1; padding: 0 4px; }
.bt-header__title { font-size: 17px; font-weight: 600; color: #1c1c1e; margin: 0; }

.bt-main { padding: 12px 12px 32px; max-width: 760px; margin: 0 auto; }
.bt-section-title { font-size: 15px; font-weight: 600; color: #1c1c1e; margin: 0 0 10px; }

/* ── 配置面板 ──────────────────────────────────────────────────────────────── */
.bt-config { background: #fff; border-radius: 16px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }
.bt-form { display: flex; flex-direction: column; gap: 14px; }

.bt-field { display: flex; flex-direction: column; gap: 4px; }
.bt-field__label { font-size: 13px; font-weight: 500; color: #3c3c43; }
.bt-field__hint { font-size: 11px; color: #8e8e93; }

.bt-input {
  border: 1px solid #d1d1d6; border-radius: 10px; padding: 8px 12px; font-size: 15px;
  outline: none; transition: border-color .15s; background: #fff; color: #1c1c1e; width: 100%;
  box-sizing: border-box;
}
.bt-input:focus { border-color: #007aff; }
.bt-input--sm { width: 120px; }
.bt-input--date { flex: 1; }

.bt-select {
  border: 1px solid #d1d1d6; border-radius: 10px; padding: 8px 12px; font-size: 15px;
  outline: none; background: #fff; color: #1c1c1e; width: 100%; cursor: pointer;
}

.bt-btn {
  border: none; border-radius: 10px; padding: 10px 16px; font-size: 15px; font-weight: 600;
  cursor: pointer; transition: opacity .15s; display: inline-flex; align-items: center; justify-content: center; gap: 6px;
}
.bt-btn--primary { background: #007aff; color: #fff; }
.bt-btn--primary:disabled { opacity: .5; cursor: not-allowed; }
.bt-btn--ghost { background: #f2f2f7; color: #007aff; font-weight: 500; padding: 6px 12px; font-size: 13px; }
.bt-run-btn { width: 100%; }

.bt-code-row { display: flex; gap: 8px; }
.bt-code-row .bt-input { flex: 1; }

.bt-params { background: #f9f9fb; border-radius: 10px; padding: 10px 12px; display: flex; flex-direction: column; gap: 10px; }
.bt-param-row { display: flex; align-items: center; gap: 8px; }
.bt-param-range { font-size: 11px; color: #8e8e93; }

.bt-range-btns { display: flex; flex-wrap: wrap; gap: 6px; }
.bt-range-btn {
  border: 1px solid #d1d1d6; border-radius: 20px; padding: 4px 12px; font-size: 12px;
  background: #fff; cursor: pointer; transition: all .15s; color: #3c3c43;
}
.bt-range-btn--active { background: #007aff; color: #fff; border-color: #007aff; }
.bt-date-row { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
.bt-date-sep { color: #8e8e93; font-size: 13px; }

.bt-error {
  display: flex; align-items: center; gap: 6px; padding: 10px 12px; border-radius: 10px;
  background: #fff0f0; color: #d32f2f; font-size: 13px; margin-top: 4px;
}

/* ── 结果区域 ──────────────────────────────────────────────────────────────── */
.bt-result { display: flex; flex-direction: column; gap: 12px; }
.bt-result > .bt-section-title { margin-top: 4px; }

.bt-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
@media (max-width: 480px) { .bt-kpi-grid { grid-template-columns: repeat(2, 1fr); } }
.bt-kpi-card {
  background: #fff; border-radius: 12px; padding: 12px 8px; text-align: center;
  box-shadow: 0 1px 4px rgba(0,0,0,.06);
}
.bt-kpi-card--up .bt-kpi-card__val { color: #ef5350; }
.bt-kpi-card--down .bt-kpi-card__val { color: #26a69a; }
.bt-kpi-card__val { font-size: 18px; font-weight: 700; color: #1c1c1e; font-variant-numeric: tabular-nums; }
.bt-kpi-card__lbl { font-size: 10px; color: #8e8e93; margin-top: 2px; }

.bt-charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
@media (max-width: 480px) { .bt-charts-row { grid-template-columns: 1fr; } }
.bt-chart-card {
  background: #fff; border-radius: 12px; padding: 12px;
  box-shadow: 0 1px 4px rgba(0,0,0,.06); display: flex; flex-direction: column; gap: 6px;
}
.bt-chart-card--wide { grid-column: 1 / -1; }
.bt-chart-card__title { font-size: 13px; font-weight: 600; color: #1c1c1e; }
.bt-chart-canvas { border-radius: 8px; overflow: hidden; min-height: 180px; width: 100%; }
.bt-chart-canvas--tall { min-height: 400px; }
.bt-chart-legend { float: right; font-size: 11px; color: #8e8e93; }
.bt-legend-buy { color: #f59f00; margin-right: 8px; }
.bt-legend-sell { color: #9c27b0; }

/* ── 交易记录 ──────────────────────────────────────────────────────────────── */
.bt-trades { background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.06); }
.bt-trades__summary {
  padding: 12px 16px; font-size: 14px; font-weight: 600; color: #1c1c1e; cursor: pointer;
  list-style: none; user-select: none;
}
.bt-trades-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.bt-trades-table th { padding: 6px 10px; text-align: left; color: #8e8e93; font-weight: 500; border-bottom: 1px solid #f0f0f0; }
.bt-trades-table td { padding: 8px 10px; color: #1c1c1e; border-bottom: 1px solid #f8f8f8; }
.bt-trade--win td { background: #fff8f8; }
.bt-trade--loss td { background: #f0fff8; }
.bt-win { color: #ef5350; font-weight: 600; }
.bt-loss { color: #26a69a; font-weight: 600; }

/* ── 股票搜索弹窗 ──────────────────────────────────────────────────────────── */
.bt-modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.4); z-index: 200;
  display: flex; align-items: center; justify-content: center; padding: 20px;
}
.bt-modal { background: #fff; border-radius: 16px; width: 100%; max-width: 400px; overflow: hidden; }
.bt-modal__header { display: flex; align-items: center; padding: 14px 16px; border-bottom: 1px solid #f0f0f0; }
.bt-modal__header h3 { flex: 1; font-size: 16px; font-weight: 600; margin: 0; }
.bt-modal__close { border: none; background: transparent; font-size: 18px; cursor: pointer; padding: 4px 8px; }
.bt-modal__body { padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
.bt-search-results { display: flex; flex-direction: column; gap: 2px; max-height: 280px; overflow-y: auto; }
.bt-search-item {
  display: flex; align-items: center; gap: 10px; padding: 10px 12px;
  border: none; background: #f5f5f7; border-radius: 10px; cursor: pointer; text-align: left;
  transition: background .1s;
}
.bt-search-item:hover { background: #e8e8ef; }
.bt-search-item__code { font-size: 13px; font-weight: 600; color: #007aff; min-width: 60px; }
.bt-search-item__name { font-size: 13px; color: #3c3c43; }

/* ── Spinner ───────────────────────────────────────────────────────────────── */
.bt-spinner {
  display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(255,255,255,.3);
  border-top-color: #fff; border-radius: 50%; animation: bt-spin .6s linear infinite;
}
@keyframes bt-spin { to { transform: rotate(360deg); } }
</style>
