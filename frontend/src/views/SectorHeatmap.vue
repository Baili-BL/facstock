<template>
  <div class="kq-page">
    <!-- 顶部导航 -->
    <header class="kq-bar">
      <button type="button" class="kq-bar__btn" aria-label="返回" @click="router.back()">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
          <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
        </svg>
      </button>
      <h1 class="kq-bar__title">板块热力图</h1>
    </header>

    <main class="kq-main">
      <!-- 页面标题 -->
      <div class="kq-page-hd">
        <h2 class="kq-page-hd__ttl">板块涨跌热力图</h2>
        <p class="kq-page-hd__sub">SECTOR SENTIMENT ANALYZER</p>
      </div>

      <!-- 过滤 Tab -->
      <nav class="kq-filter">
        <button
          v-for="t in filterDefs"
          :key="t.id"
          type="button"
          class="kq-filter__btn"
          :class="{ active: filterKind === t.id }"
          @click="filterKind = t.id"
        >{{ t.label }}</button>
      </nav>

      <!-- 时间框架 -->
      <div class="kq-tf">
        <div class="kq-tf__btns">
          <button
            v-for="tf in tfDefs"
            :key="tf.key"
            type="button"
            class="kq-tf__btn"
            :class="{ active: activeTf === tf.key }"
            @click="activeTf = tf.key"
          >{{ tf.label }}</button>
        </div>
        <!-- 市场广度摘要 -->
        <div v-if="!loading && (breadth.up > 0 || breadth.down > 0)" class="kq-breadth-mini">
          <span class="kq-breadth-mini__up">{{ breadth.up }} 涨</span>
          <div class="kq-breadth-mini__bar">
            <div class="kq-breadth-mini__seg kq-breadth-mini__seg--up" :style="{ width: breadth.upPct + '%' }" />
            <div class="kq-breadth-mini__seg kq-breadth-mini__seg--dn" :style="{ width: breadth.downPct + '%' }" />
          </div>
          <span class="kq-breadth-mini__dn">{{ breadth.down }} 跌</span>
          <span class="kq-breadth-mini__status" :class="breadthStatus.cls">{{ breadthStatus.text }}</span>
        </div>
      </div>

      <!-- 热力图：纯 SVG Treemap -->
      <div v-if="loading" class="kq-loading">
        <div class="kq-spinner" />
        <p>加载板块数据…</p>
      </div>
      <div v-else-if="!layout.length" class="kq-empty">暂无板块数据</div>
      <div v-else class="kq-treemap-wrap" ref="wrapEl">
        <!-- SVG rect 层 -->
        <svg
          class="st-map__svg"
          :width="containerW"
          :height="CHART_H"
          :viewBox="`0 0 ${containerW} ${CHART_H}`"
        >
          <rect
            v-for="(cell, i) in layout"
            :key="i"
            class="st-map__cell"
            :x="cell.x0 + 1"
            :y="cell.y0 + 1"
            :width="Math.max(cell.x1 - cell.x0 - 2, 0)"
            :height="Math.max(cell.y1 - cell.y0 - 2, 0)"
            :fill="fillForChange(cell.change)"
            :rx="2"
            @click="onCellClick(cell)"
          />
        </svg>
        <!-- HTML label 覆盖层 -->
        <div class="st-map__labels" :style="{ width: containerW + 'px', height: CHART_H + 'px' }">
          <div
            v-for="(cell, i) in layout"
            :key="'lbl' + i"
            class="st-map__label"
            :style="labelStyle(cell)"
            @click="onCellClick(cell)"
          >
            <span class="st-map__label-name">{{ cell.name }}</span>
            <span class="st-map__label-chg" :class="cell.change >= 0 ? 'up' : 'dn'">
              {{ cell.change >= 0 ? '+' : '' }}{{ cell.change.toFixed(2) }}%
            </span>
          </div>
        </div>
      </div>

      <!-- 颜色图例 -->
      <div class="kq-legend">
        <div class="kq-legend__item">
          <div class="kq-legend__swatch" style="background: #089981" />
          <span>-3%</span>
        </div>
        <div class="kq-legend__item">
          <div class="kq-legend__swatch" style="background: #d5f5e3" />
          <span>-1%</span>
        </div>
        <div class="kq-legend__item">
          <div class="kq-legend__swatch" style="background: #f2f3f4" />
          <span>平盘</span>
        </div>
        <div class="kq-legend__item">
          <div class="kq-legend__swatch" style="background: #fde8e8" />
          <span>+1%</span>
        </div>
        <div class="kq-legend__item">
          <div class="kq-legend__swatch" style="background: #f23645" />
          <span>+3%</span>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { hierarchy, treemap } from 'd3-hierarchy'
import { market } from '@/api/market.js'

const router = useRouter()
const loading = ref(true)
const filterKind = ref('industry')
const activeTf = ref('1D')
const wrapEl = ref(null)
const containerW = ref(380)
const layout = ref([])
let resizeObserver = null

const CHART_H = 520

const filterDefs = [
  { id: 'industry', label: '行业' },
  { id: 'concept', label: '概念' },
]

const tfDefs = [
  { key: '1D', label: '1日' },
  { key: '1W', label: '1周' },
  { key: '1M', label: '1月' },
  { key: '3M', label: '3月' },
  { key: 'YTD', label: 'YTD' },
]

const industryRaw = ref([])
const conceptRaw  = ref([])

// A股标准配色：红涨绿跌
const UP_DARK   = [242,  54,  69]
const UP_LIGHT = [253, 232, 232]
const DN_LIGHT = [213, 245, 227]
const DN_DARK  = [8,   153, 129]

function mixRgb(light, dark, t) {
  const a = Math.round(light[0] + (dark[0] - light[0]) * t)
  const b = Math.round(light[1] + (dark[1] - light[1]) * t)
  const c = Math.round(light[2] + (dark[2] - light[2]) * t)
  return `rgb(${a}, ${b}, ${c})`
}

function fillForChange(change) {
  const t = Math.min(Math.abs(Number(change) || 0) / 4, 1)
  if (change >= 0) return mixRgb(UP_LIGHT, UP_DARK, t * 0.8 + 0.05)
  return mixRgb(DN_LIGHT, DN_DARK, t * 0.8 + 0.05)
}

function textColor(change) {
  return '#ffffff'
}

function labelStyle(cell) {
  const w = cell.x1 - cell.x0
  const h = cell.y1 - cell.y0
  const fontSize = Math.min(13, Math.max(9, Math.floor(Math.min(w, h) / 4.5)))
  return {
    left:     cell.x0 + 'px',
    top:      cell.y0 + 'px',
    width:    w + 'px',
    height:   h + 'px',
    fontSize: fontSize + 'px',
    color:    textColor(cell.change),
  }
}

function computeLayout(sectors) {
  if (!sectors || !sectors.length) {
    layout.value = []
    return
  }
  const sorted = [...sectors]
    .sort((a, b) => Math.abs(Number(b.change) || 0) - Math.abs(Number(a.change) || 0))
    .slice(0, 80)

  const root = hierarchy({ name: 'root', children: sorted })
    .sum(d => d.change !== undefined ? Math.abs(Number(d.change) || 0.01) : 0)
    .sort((a, b) => (b.value || 0) - (a.value || 0))

  treemap()
    .size([containerW.value, CHART_H])
    .paddingInner(2)
    .paddingOuter(2)
    .round(true)
    (root)

  layout.value = root.leaves().map((d, i) => ({
    x0: Math.round(d.x0),
    y0: Math.round(d.y0),
    x1: Math.round(d.x1),
    y1: Math.round(d.y1),
    name: d.data.name || '',
    change: Number(d.data.change) || 0,
    rank: i + 1,
    total: root.leaves().length,
  }))
}

const breadth = computed(() => {
  const src = filterKind.value === 'industry' ? industryRaw.value : conceptRaw.value
  let up = 0, down = 0, flat = 0
  for (const s of src) {
    const c = Number(s.change) || 0
    if (c > 0) up++
    else if (c < 0) down++
    else flat++
  }
  const tot = up + down + flat || 1
  return {
    up, down, flat,
    upPct:   Math.round((up   / tot) * 100),
    downPct: Math.round((down / tot) * 100),
  }
})

const breadthStatus = computed(() => {
  const p = breadth.value.upPct
  if (p >= 60) return { text: '看多', cls: 'bull' }
  if (p <= 40) return { text: '看空', cls: 'bear' }
  return { text: '中性', cls: 'neu' }
})

function onCellClick(cell) {
  router.push(`/sectors/${encodeURIComponent(cell.name)}`)
}

function updateWidth() {
  if (wrapEl.value) {
    containerW.value = wrapEl.value.clientWidth || 380
    const src = filterKind.value === 'industry' ? industryRaw.value : conceptRaw.value
    computeLayout(src)
  }
}

watch(filterKind, async () => {
  await nextTick()
  const src = filterKind.value === 'industry' ? industryRaw.value : conceptRaw.value
  computeLayout(src)
})

onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect()
})

async function loadData() {
  loading.value = true
  try {
    const [ind, con] = await Promise.all([
      market.sectors(),
      market.sectorsConcept(),
    ])
    industryRaw.value = Array.isArray(ind) ? ind : []
    conceptRaw.value  = Array.isArray(con) ? con : []
  } catch (e) {
    console.error('load heatmap data error', e)
  } finally {
    loading.value = false
    await nextTick()
    updateWidth()
    resizeObserver = new ResizeObserver(() => updateWidth())
    if (wrapEl.value) resizeObserver.observe(wrapEl.value)
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.kq-page {
  --bg:       #f0f2f5;
  --surface:  #ffffff;
  --surface2: #f8f9fa;
  --surface3: #eceff1;
  --gain:    #089981;
  --gain-mid:#27ae60;
  --loss:    #f23645;
  --loss-mid:#e74c3c;
  --primary: #2980b9;
  --text:    #2c3e50;
  --muted:   #7f8c8d;
  --border:  rgba(44,62,80,0.12);

  min-height: 100vh;
  min-height: 100dvh;
  background: var(--bg);
  color: var(--text);
  font-family: Inter, -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

/* 顶部栏 */
.kq-bar {
  position: sticky;
  top: 0;
  z-index: 40;
  display: grid;
  grid-template-columns: 48px 1fr;
  align-items: center;
  min-height: 56px;
  padding: env(safe-area-inset-top, 0) 0 0;
  background: rgba(255,255,255,0.95);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.kq-bar__btn {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--primary);
  cursor: pointer;
}
.kq-bar__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--text);
}

/* 主内容 */
.kq-main {
  padding: 16px 14px 0;
  position: relative;
}

/* 页面标题 */
.kq-page-hd { margin-bottom: 14px; }
.kq-page-hd__ttl {
  font-size: 1.4rem;
  font-weight: 900;
  letter-spacing: -0.03em;
  color: var(--text);
  text-transform: uppercase;
  margin: 0 0 4px;
}
.kq-page-hd__sub {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--muted);
  text-transform: uppercase;
  margin: 0;
}

/* 过滤 Tab */
.kq-filter {
  display: flex;
  gap: 4px;
  background: var(--surface);
  padding: 4px;
  border-radius: 10px;
  margin-bottom: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.kq-filter__btn {
  flex: 1;
  padding: 8px 0;
  border: none;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 700;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  transition: all 0.15s;
}
.kq-filter__btn.active {
  background: var(--primary);
  color: #fff;
  box-shadow: 0 2px 6px rgba(41,128,185,0.35);
}

/* 时间框架 + 市场广度 */
.kq-tf {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  flex-wrap: wrap;
  gap: 8px;
}
.kq-tf__btns {
  display: flex;
  gap: 16px;
}
.kq-tf__btn {
  border: none;
  background: transparent;
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
  cursor: pointer;
  padding: 0 0 4px;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
}
.kq-tf__btn.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
}

/* 市场广度迷你条 */
.kq-breadth-mini {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
}
.kq-breadth-mini__up  { color: #f23645; }
.kq-breadth-mini__dn  { color: #089981; }
.kq-breadth-mini__bar {
  display: flex;
  width: 80px;
  height: 4px;
  border-radius: 2px;
  overflow: hidden;
  background: var(--surface3);
}
.kq-breadth-mini__seg { height: 100%; transition: width 0.3s; }
.kq-breadth-mini__seg--up { background: #f23645; }
.kq-breadth-mini__seg--dn { background: #089981; }
.kq-breadth-mini__status {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 800;
}
.kq-breadth-mini__status.bull { background: #fde8e8; color: #f23645; }
.kq-breadth-mini__status.bear { background: #d5f5e3; color: #089981; }
.kq-breadth-mini__status.neu  { background: var(--surface3); color: var(--muted); }

/* 加载/空 */
.kq-loading,
.kq-empty {
  text-align: center;
  padding: 48px 16px;
  color: var(--muted);
  font-size: 13px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.kq-spinner {
  width: 28px;
  height: 28px;
  border: 2px solid var(--surface3);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: kqspin 0.75s linear infinite;
}
@keyframes kqspin { to { transform: rotate(360deg); } }

/* Treemap */
.kq-treemap-wrap {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
  padding: 2px;
  margin-bottom: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}

.st-map__svg {
  display: block;
}

.st-map__cell {
  cursor: pointer;
  transition: filter 0.1s;
  stroke: rgba(255, 255, 255, 0.7);
  stroke-width: 1;
}
.st-map__cell:hover { filter: brightness(0.92); }

.st-map__labels {
  position: absolute;
  top: 2px;
  left: 2px;
  pointer-events: none;
}

.st-map__label {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
  padding: 4px 4px 2px;
  pointer-events: all;
  cursor: pointer;
  text-align: center;
  overflow: hidden;
  box-sizing: border-box;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.st-map__label-name {
  font-weight: 700;
  line-height: 1.1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.st-map__label-chg {
  font-weight: 800;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}
.st-map__label-chg.up { color: #ffffff !important; }
.st-map__label-chg.dn { color: #ffffff !important; }

/* 图例 */
.kq-legend {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  padding: 10px 0 14px;
  font-size: 10px;
  font-weight: 700;
  color: var(--muted);
}
.kq-legend__item {
  display: flex;
  align-items: center;
  gap: 5px;
}
.kq-legend__swatch {
  width: 12px;
  height: 12px;
  border-radius: 2px;
}
</style>
