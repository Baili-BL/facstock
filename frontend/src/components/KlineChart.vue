<template>
  <div class="kline-wrap">
    <!-- 图例 -->
    <div v-show="status === 'ready'" class="kline-legend">
      <span class="legend-item"><span class="legend-dot legend-dot--rise"></span>K线</span>
      <span class="legend-item"><span class="legend-dot legend-dot--ma5"></span>MA5</span>
      <span class="legend-item"><span class="legend-dot legend-dot--ma10"></span>MA10</span>
      <span class="legend-item"><span class="legend-dot legend-dot--ma20"></span>MA20</span>
    </div>
    <div class="kline-panel">
      <div class="kline-plot" @mouseleave="hideTooltip">
        <!-- Indicator selector -->
        <div class="kline-ind-row">
          <button
            v-for="opt in INDICATOR_OPTIONS"
            :key="opt.key"
            type="button"
            class="kline-ind-btn"
            :class="{ active: activeTab === opt.key }"
            :disabled="tabBusy || status !== 'ready'"
            @click="pickIndicator(opt.key)"
          >{{ opt.label }}</button>
        </div>
        <div v-if="status === 'loading'" class="kline-loading">
          <span class="kline-dot"></span>
          <span>{{ loading ? '加载K线...' : '渲染图表...' }}</span>
        </div>
        <div v-else-if="status === 'error'" class="kline-err">{{ errorMsg }}</div>
        <div v-show="status === 'ready'" ref="chartEl" class="kline-canvas"></div>
        <div
          v-show="tooltip.show && status === 'ready'"
          class="kline-tooltip"
          :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
        >
          <div class="kline-tooltip-rows">
            <div class="kline-tooltip-line">
              <span class="kline-tooltip-label">开=</span><span :class="['kline-tooltip-num', tooltip.up ? 'is-up' : 'is-down']">{{ tooltip.open }}</span>
            </div>
            <div class="kline-tooltip-line">
              <span class="kline-tooltip-label">高=</span><span :class="['kline-tooltip-num', tooltip.up ? 'is-up' : 'is-down']">{{ tooltip.high }}</span>
            </div>
            <div class="kline-tooltip-line">
              <span class="kline-tooltip-label">低=</span><span :class="['kline-tooltip-num', tooltip.up ? 'is-up' : 'is-down']">{{ tooltip.low }}</span>
            </div>
            <div class="kline-tooltip-line">
              <span class="kline-tooltip-label">收=</span><span :class="['kline-tooltip-num', tooltip.up ? 'is-up' : 'is-down']">{{ tooltip.close }}</span>
            </div>
            <div class="kline-tooltip-line">
              <span class="kline-tooltip-label">涨=</span><span :class="['kline-tooltip-num', tooltip.up ? 'is-up' : 'is-down']">{{ tooltip.pct }}</span>
            </div>
          </div>
          <div class="kline-tooltip-date">{{ tooltip.dateStr }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { createChart, CandlestickSeries, LineSeries, HistogramSeries } from 'lightweight-charts'
import { stock } from '@/api/strategy.js'

const props = defineProps({
  code:     { type: String, required: true },
  interval: { type: String, default: 'daily' },
})

const INDICATOR_OPTIONS = [
  { key: 'volume', label: '成交量' },
  { key: 'cmf', label: 'CMF' },
  { key: 'ma', label: '均线' },
  { key: 'bandwidth', label: '布林带' },
]

const activeTab     = ref('volume')
const tabBusy = ref(false)

const chartEl = ref(null)
const status  = ref('loading')
const errorMsg = ref('')
const loading = ref(false)

let rawData = null
let chart   = null
let ro      = null
let crosshairHandler = null

const tooltip = ref({
  show: false,
  x: 0,
  y: 0,
  open: '',
  high: '',
  low: '',
  close: '',
  pct: '',
  dateStr: '',
  up: true,
})

const TOOLTIP_W = 128
const TOOLTIP_H = 138

const CH = 248

const C = {
  up:    '#f23645',
  down:  '#089981',
  /* 布林带：灰系虚线，与下方均线（橙/蓝/紫）明显区分 */
  bbU:   'rgba(100, 116, 139, 0.55)',
  bbM:   'rgba(71, 85, 105, 0.88)',
  bbL:   'rgba(100, 116, 139, 0.55)',
  volU:  'rgba(242, 54, 69, 0.72)',
  volD:  'rgba(8, 153, 129, 0.72)',
  cmfP:  'rgba(242, 54, 69, 0.85)',
  cmfN:  'rgba(8, 153, 129, 0.85)',
  bwMain: 'rgba(156,136,255,0.95)',
  bwMa5:  'rgba(255,193,7,0.90)',
  bwMa10: 'rgba(33,150,243,0.90)',
  sigU:  '#f23645',
  sigD:  '#089981',
  ma5:   '#E65100',
  ma10:  '#1565C0',
  ma20:  '#6A1B9A',
}

// ── helpers ────────────────────────────────
function zipByDates(dates, values) {
  if (!dates?.length || !values?.length) return []
  const n = Math.min(dates.length, values.length)
  const out = []
  for (let i = 0; i < n; i++) {
    const v = values[i]
    if (v === null || v === undefined || Number.isNaN(Number(v))) continue
    out.push({ time: dates[i], value: Number(v) })
  }
  return out
}

function candleByTime(candles) {
  const m = {}
  for (const c of candles || []) {
    if (c?.time != null) m[c.time] = c
  }
  return m
}

function fmtPx(v) {
  if (v == null || Number.isNaN(Number(v))) return '--'
  return Number(v).toFixed(2)
}

/** 友好日期格式：2026-03-21 */
function formatTooltipDate(time) {
  if (time == null) return ''
  if (typeof time === 'string') {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(time)
    if (m) {
      return `${m[1]}-${m[2]}-${m[3]}`
    }
    return time
  }
  if (typeof time === 'number') {
    const dt = new Date(time * 1000)
    const y = dt.getUTCFullYear()
    const mo = String(dt.getUTCMonth() + 1).padStart(2, '0')
    const d = String(dt.getUTCDate()).padStart(2, '0')
    return `${y}-${mo}-${d}`
  }
  if (typeof time === 'object' && time && 'year' in time) {
    const y = time.year
    const mo = String(time.month).padStart(2, '0')
    const d = String(time.day).padStart(2, '0')
    return `${y}-${mo}-${d}`
  }
  return ''
}

function hideTooltip() {
  tooltip.value.show = false
}

function destroyChartOnly() {
  ro?.disconnect()
  ro = null
  if (chart && crosshairHandler) {
    try {
      chart.unsubscribeCrosshairMove(crosshairHandler)
    } catch {}
    crosshairHandler = null
  }
  if (chart) {
    chart.remove()
    chart = null
  }
  hideTooltip()
}

function clearAll() {
  destroyChartOnly()
  rawData = null
  status.value = 'loading'
}

// ── 核心：重建整图（每次 Tab 切换或首次加载）──
function buildChart(data, tab) {
  if (!chartEl.value || !data) return
  destroyChartOnly()

  const W = chartEl.value.clientWidth || 340

  chart = createChart(chartEl.value, {
    width: W,
    height: CH,
    layout: {
      background: { color: '#ffffff' },
      textColor: 'rgba(0,0,0,0.45)',
      fontSize: 11,
    },
    grid: {
      vertLines: { color: 'rgba(0,0,0,0.06)' },
      horzLines: { color: 'rgba(0,0,0,0.06)' },
    },
    crosshair: {
      mode: 1,
      vertLine: { color: 'rgba(0,0,0,0.12)', width: 1, style: 2, labelBackgroundColor: '#1c1c1e' },
      horzLine: { color: 'rgba(0,0,0,0.12)', width: 1, style: 2, labelBackgroundColor: '#1c1c1e' },
    },
    rightPriceScale: {
      borderColor: 'rgba(0,0,0,0.08)',
      scaleMargins: { top: 0.03, bottom: 0.30 },
    },
    timeScale: {
      borderColor: 'rgba(0,0,0,0.08)',
      timeVisible: false,
      secondsVisible: false,
      barSpacing: 6,
      tickMarkMaxCharacterLength: 10,
    },
    localization: {
      dateFormat: 'yyyy-MM-dd',
    },
    handleScroll: { mouseWheel: true, pressedMouseMove: true },
    handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
  })

  // ── 副图（必须先 addSeries，再 applyOptions 改轴属性）──
  if (tab === 'volume') {
    const s = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'sub',
    })
    chart.priceScale('sub').applyOptions({
      scaleMargins: { top: 0.70, bottom: 0.02 },
      borderVisible: false,
    })
    if (data.volumes?.length) {
      s.setData(data.volumes.map(v => ({
        time: v.time,
        value: Number(v.value) || 0,
        color: v.color === '#ef5350' ? C.volU : C.volD,
      })))
    }
  }

  if (tab === 'cmf') {
    const s = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'price', precision: 3, minMove: 0.001 },
      priceScaleId: 'sub',
    })
    chart.priceScale('sub').applyOptions({
      scaleMargins: { top: 0.70, bottom: 0.02 },
      borderVisible: false,
    })
    if (data.cmf?.length && data.dates?.length) {
      const n = Math.min(data.cmf.length, data.dates.length)
      const pts = []
      for (let i = 0; i < n; i++) {
        const v = data.cmf[i]
        if (v === null || v === undefined) continue
        pts.push({ time: data.dates[i], value: Number(v), color: v >= 0 ? C.cmfP : C.cmfN })
      }
      if (pts.length) s.setData(pts)
    }
  }

  if (tab === 'ma') {
    chart.priceScale('sub').applyOptions({
      scaleMargins: { top: 0.70, bottom: 0.02 },
      borderVisible: false,
    })
    const subMa5 = chart.addSeries(LineSeries, {
      color: C.ma5,
      lineWidth: 1.5,
      priceScaleId: 'sub',
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: false,
    })
    const subMa5Pts = zipByDates(data.dates, data.ma5)
    if (subMa5Pts.length) subMa5.setData(subMa5Pts)

    const subMa10 = chart.addSeries(LineSeries, {
      color: C.ma10,
      lineWidth: 1.5,
      priceScaleId: 'sub',
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })
    const subMa10Pts = zipByDates(data.dates, data.ma10)
    if (subMa10Pts.length) subMa10.setData(subMa10Pts)

    const subMa20 = chart.addSeries(LineSeries, {
      color: C.ma20,
      lineWidth: 1.5,
      priceScaleId: 'sub',
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })
    const subMa20Pts = zipByDates(data.dates, data.ma20)
    if (subMa20Pts.length) subMa20.setData(subMa20Pts)
  }

  if (tab === 'bandwidth') {
    const bw = chart.addSeries(LineSeries, {
      color: C.bwMain,
      lineWidth: 1.5,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
      priceScaleId: 'sub',
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: false,
    })
    chart.priceScale('sub').applyOptions({
      scaleMargins: { top: 0.70, bottom: 0.02 },
      borderVisible: false,
    })
    const bwPts = zipByDates(data.dates, data.bb_width)
    if (bwPts.length) bw.setData(bwPts)

    const ma5 = chart.addSeries(LineSeries, {
      color: C.bwMa5,
      lineWidth: 1,
      lineStyle: 2,
      priceScaleId: 'sub',
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })
    const ma5Pts = zipByDates(data.dates, data.width_ma5)
    if (ma5Pts.length) ma5.setData(ma5Pts)

    const ma10 = chart.addSeries(LineSeries, {
      color: C.bwMa10,
      lineWidth: 1,
      lineStyle: 2,
      priceScaleId: 'sub',
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    })
    const ma10Pts = zipByDates(data.dates, data.width_ma10)
    if (ma10Pts.length) ma10.setData(ma10Pts)
  }

  // ── 布林带 ─────────────────────────────────
  const bbUpper = chart.addSeries(LineSeries, {
    color: C.bbU,
    lineWidth: 1,
    lineStyle: 2,
    priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
  })
  const bbMid = chart.addSeries(LineSeries, {
    color: C.bbM,
    lineWidth: 1,
    lineStyle: 0,
    priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
  })
  const bbLower = chart.addSeries(LineSeries, {
    color: C.bbL,
    lineWidth: 1,
    lineStyle: 2,
    priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
  })
  if (data.bb_upper?.length)   bbUpper.setData(data.bb_upper.map(v => ({ time: v.time, value: Number(v.value) })))
  if (data.bb_middle?.length)  bbMid.setData(data.bb_middle.map(v => ({ time: v.time, value: Number(v.value) })))
  if (data.bb_lower?.length)   bbLower.setData(data.bb_lower.map(v => ({ time: v.time, value: Number(v.value) })))

  // ── 均线 MA5 / MA10 / MA20 ──────────────────────
  const ma5Series = chart.addSeries(LineSeries, {
    color: C.ma5, lineWidth: 2,
    priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
  })
  const ma5Pts = zipByDates(data.dates, data.ma5)
  if (ma5Pts.length) ma5Series.setData(ma5Pts)

  const ma10Series = chart.addSeries(LineSeries, {
    color: C.ma10, lineWidth: 2,
    priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
  })
  const ma10Pts = zipByDates(data.dates, data.ma10)
  if (ma10Pts.length) ma10Series.setData(ma10Pts)

  const ma20Series = chart.addSeries(LineSeries, {
    color: C.ma20, lineWidth: 2,
    priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
  })
  const ma20Pts = zipByDates(data.dates, data.ma20)
  if (ma20Pts.length) ma20Series.setData(ma20Pts)

  // ── 蜡烛图 ─────────────────────────────────
  const candleSeries = chart.addSeries(CandlestickSeries, {
    upColor: C.up, downColor: C.down,
    borderUpColor: C.up, borderDownColor: C.down,
    wickUpColor: C.up, wickDownColor: C.down,
  })
  if (data.candles?.length) candleSeries.setData(data.candles)

  // ── 十字光标 OHLC 浮层（涨红跌绿）──────────────
  crosshairHandler = (param) => {
    if (!chartEl.value || param.point === undefined || param.time === undefined) {
      hideTooltip()
      return
    }
    const bar = param.seriesData.get(candleSeries)
    if (!bar || bar.open === undefined) {
      hideTooltip()
      return
    }
    const o = Number(bar.open)
    const h = Number(bar.high)
    const l = Number(bar.low)
    const c = Number(bar.close)
    const up = c >= o
    const pct = o > 0 ? ((c - o) / o * 100) : null
    const pctStr = pct !== null ? (pct >= 0 ? '+' + pct.toFixed(2) + '%' : pct.toFixed(2) + '%') : '--'

    const pw = chartEl.value.clientWidth
    const ph = chartEl.value.clientHeight
    const pad = 10
    let x = param.point.x + pad
    let y = param.point.y + pad
    if (x + TOOLTIP_W > pw) x = param.point.x - TOOLTIP_W - pad
    if (y + TOOLTIP_H > ph) y = param.point.y - TOOLTIP_H - pad
    x = Math.max(6, Math.min(x, pw - TOOLTIP_W - 6))
    y = Math.max(6, Math.min(y, ph - TOOLTIP_H - 6))

    tooltip.value = {
      show: true,
      x,
      y,
      open: fmtPx(o),
      high: fmtPx(h),
      low: fmtPx(l),
      close: fmtPx(c),
      pct: pctStr,
      dateStr: formatTooltipDate(param.time),
      up,
    }
  }
  chart.subscribeCrosshairMove(crosshairHandler)

  // ── 量能信号标记 ─────────────────────────────
  addSignalMarkers(chart, data, candleSeries)

  chart.timeScale().fitContent()
  status.value = 'ready'

  ro = new ResizeObserver(entries => {
    if (!chart) return
    const w = entries[0]?.contentRect.width
    if (w > 0) chart.resize(w, CH)
  })
  ro.observe(chartEl.value)
}

// ── 量能信号：打在对应 K 线 low 下方 0.3% 处 ────
function addSignalMarkers(chart, data, candleSeries) {
  if (!data.dates?.length || !data.candles?.length) return
  const byT = candleByTime(data.candles)
  const dates = data.dates

  const upKeys   = ['vp_vol_break_up', 'vp_main_buy_signal', 'vp_cost_break']
  const downKeys = ['vp_vol_break_down']

  upKeys.forEach(key => {
    const arr = data[key]
    if (!arr?.length) return
    const s = chart.addSeries(LineSeries, {
      color: C.sigU, lineWidth: 2, lineStyle: 2,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
    })
    const pts = []
    for (let i = 0; i < Math.min(arr.length, dates.length); i++) {
      if (!arr[i]) continue
      const c = byT[dates[i]]
      if (c?.low != null) pts.push({ time: dates[i], value: Number(c.low) * 0.997 })
    }
    if (pts.length) s.setData(pts)
  })

  downKeys.forEach(key => {
    const arr = data[key]
    if (!arr?.length) return
    const s = chart.addSeries(LineSeries, {
      color: C.sigD, lineWidth: 2, lineStyle: 2,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
    })
    const pts = []
    for (let i = 0; i < Math.min(arr.length, dates.length); i++) {
      if (!arr[i]) continue
      const c = byT[dates[i]]
      if (c?.low != null) pts.push({ time: dates[i], value: Number(c.low) * 0.997 })
    }
    if (pts.length) s.setData(pts)
  })
}

async function pickIndicator(tab) {
  await switchTab(tab)
}

// ── 副图指标切换 ────────────────────────────────
async function switchTab(tab) {
  if (tab === activeTab.value || !rawData || tabBusy.value) return
  tabBusy.value = true
  activeTab.value = tab
  await nextTick()
  try {
    buildChart(rawData, tab)
  } finally {
    tabBusy.value = false
  }
}

// ── 数据加载 ────────────────────────────────
async function loadKline() {
  if (!props.code) return
  errorMsg.value = ''
  status.value   = 'loading'
  loading.value  = true
  tabBusy.value  = true
  try {
    const raw = await stock.detail(props.code, 'daily')
    if (!raw || !raw.candles?.length) {
      errorMsg.value = '暂无K线数据'
      status.value   = 'error'
      return
    }
    rawData = raw
    await nextTick()
    buildChart(rawData, activeTab.value)
  } catch (e) {
    errorMsg.value = '加载失败: ' + (e?.message || '未知错误')
    status.value   = 'error'
  } finally {
    loading.value = false
    tabBusy.value = false
  }
}

watch(() => props.code, () => {
  activeTab.value = 'volume'
  loadKline()
})

onMounted(() => {
  loadKline()
})
onUnmounted(() => {
  clearAll()
})
</script>

<style scoped>
/* 白底卡片，与参考图一致 */
.kline-wrap {
  background: #ffffff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.04), 0 2px 12px rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(0, 0, 0, 0.06);
}

/* 图例 */
.kline-legend {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 14px 6px;
  font-size: 11px;
  color: rgba(0, 0, 0, 0.5);
  flex-shrink: 0;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.legend-dot--rise { background: #f23645; }
.legend-dot--ma5 { background: #e65100; }
.legend-dot--ma10 { background: #1565c0; }
.legend-dot--ma20 { background: #6a1b9a; }

.kline-panel {
  display: flex;
  flex-direction: column;
  background: #ffffff;
}

/* Indicator selector row (inside kline-plot) */
.kline-ind-row {
  display: flex;
  flex-direction: row;
  gap: 4px;
  padding: 2px 10px 6px;
  flex-shrink: 0;
}

.kline-ind-btn {
  all: initial;
  font-family: -apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, Ubuntu, sans-serif;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  padding: 5px 12px;
  border-radius: 8px;
  color: rgba(19, 23, 34, 0.45);
  background-color: transparent;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease;
  -webkit-tap-highlight-color: transparent;
}
.kline-ind-btn:not(:disabled):hover {
  background-color: rgba(240, 243, 250, 1);
  color: rgba(19, 23, 34, 0.75);
}
.kline-ind-btn.active {
  background-color: rgba(41, 98, 255, 0.1);
  color: #2962ff;
}
.kline-ind-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.kline-plot {
  position: relative;
  height: 248px;
  min-height: 248px;
  flex: 1;
  background: #ffffff;
}

.kline-canvas {
  width: 100%;
  height: 100%;
  min-height: 248px;
  background: #ffffff;
}

.kline-loading,
.kline-err {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: rgba(0, 0, 0, 0.45);
  font-size: 13px;
  z-index: 1;
  background: #ffffff;
}

.kline-err {
  color: var(--apple-red);
}

.kline-dot {
  width: 6px;
  height: 6px;
  background: var(--apple-blue);
  border-radius: 50%;
  animation: kpulse 1.2s ease-in-out infinite;
}

@keyframes kpulse {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50%       { opacity: 1;    transform: scale(1.2); }
}

/* 十字光标 OHLC 浮层 */
.kline-tooltip {
  position: absolute;
  z-index: 20;
  min-width: 118px;
  padding: 10px 12px 8px;
  background: #3d3d41;
  border-radius: 8px;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.2);
  pointer-events: none;
  font-size: 12px;
  line-height: 1.45;
}

.kline-tooltip-line {
  display: flex;
  align-items: baseline;
  gap: 0;
  white-space: nowrap;
}

.kline-tooltip-label {
  color: rgba(255, 255, 255, 0.92);
}

.kline-tooltip-num.is-up {
  color: #f23645;
  font-weight: 600;
}

.kline-tooltip-num.is-down {
  color: #089981;
  font-weight: 600;
}

.kline-tooltip-date {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  font-size: 11px;
  color: rgba(255, 255, 255, 0.55);
}
</style>
