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
        <div v-if="!loading && breadth.up > 0 || breadth.down > 0" class="kq-breadth-mini">
          <span class="kq-breadth-mini__up">{{ breadth.up }} 涨</span>
          <div class="kq-breadth-mini__bar">
            <div class="kq-breadth-mini__seg kq-breadth-mini__seg--up" :style="{ width: breadth.upPct + '%' }" />
            <div class="kq-breadth-mini__seg kq-breadth-mini__seg--dn" :style="{ width: breadth.downPct + '%' }" />
          </div>
          <span class="kq-breadth-mini__dn">{{ breadth.down }} 跌</span>
          <span class="kq-breadth-mini__status" :class="breadthStatus.cls">{{ breadthStatus.text }}</span>
        </div>
      </div>

      <!-- 热力图：Treemap -->
      <div v-if="loading" class="kq-loading">
        <div class="kq-spinner" />
        <p>加载板块数据…</p>
      </div>
      <div v-else-if="!treemapNodes.length" class="kq-empty">暂无板块数据</div>
      <div v-else class="kq-treemap-wrap">
        <svg
          class="kq-treemap"
          :viewBox="`0 0 ${VW} ${VH}`"
          preserveAspectRatio="xMidYMid meet"
        >
          <g v-for="(node, idx) in treemapNodes" :key="node.id">
            <!-- 区块背景 -->
            <rect
              class="kq-cell"
              :x="node.x + 1"
              :y="node.y + 1"
              :width="Math.max(0, node.w - 2)"
              :height="Math.max(0, node.h - 2)"
              :fill="node.bg"
              rx="3"
              @mouseenter="showTooltip($event, node)"
              @mousemove="moveTooltip($event)"
              @mouseleave="hideTooltip"
              @click="onCellClick(node)"
            />
            <!-- 区块标签 -->
            <text
              v-if="node.showName"
              class="kq-cell-name"
              :x="node.x + node.w / 2"
              :y="node.y + node.h / 2 - (node.showPct ? node.fn * 0.45 : 0)"
              text-anchor="middle"
              dominant-baseline="middle"
              :fill="node.tc"
              :font-size="node.fn"
              font-weight="900"
            >{{ node.label }}</text>
            <!-- 涨跌幅 -->
            <text
              v-if="node.showPct"
              class="kq-cell-pct"
              :x="node.x + node.w / 2"
              :y="node.y + node.h / 2 + (node.showName ? node.fn * 0.55 : 0)"
              text-anchor="middle"
              dominant-baseline="middle"
              :fill="node.tc"
              :font-size="node.fp"
              font-weight="900"
            >{{ node.pctStr }}</text>
          </g>
        </svg>
      </div>

      <!-- Tooltip -->
      <div
        v-if="tooltip.visible"
        class="kq-tooltip"
        :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
      >
        <div class="kq-tooltip__name">{{ tooltip.name }}</div>
        <div class="kq-tooltip__pct" :style="{ color: tooltip.pctColor }">
          {{ tooltip.pctStr }}
        </div>
        <div class="kq-tooltip__rank">
          <span class="kq-tooltip__rank-lbl">排名</span>
          <span class="kq-tooltip__rank-val">{{ tooltip.rank }} / {{ tooltip.total }}</span>
        </div>
      </div>

      <!-- 颜色图例 -->
      <div class="kq-legend">
        <div class="kq-legend__item">
          <div class="kq-legend__swatch kq-legend__swatch--deep-loss" />
          <span>-3%</span>
        </div>
        <div class="kq-legend__item">
          <div class="kq-legend__swatch kq-legend__swatch--loss" />
          <span>0%</span>
        </div>
        <div class="kq-legend__item">
          <div class="kq-legend__swatch kq-legend__swatch--flat" />
          <span>平盘</span>
        </div>
        <div class="kq-legend__item">
          <div class="kq-legend__swatch kq-legend__swatch--gain" />
          <span>0%</span>
        </div>
        <div class="kq-legend__item">
          <div class="kq-legend__swatch kq-legend__swatch--deep-gain" />
          <span>+3%</span>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { market } from '@/api/market.js'

const router = useRouter()
const loading = ref(true)
const filterKind = ref('industry')
const activeTf = ref('1D')

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

const VW = 380
const VH = 520

// 红涨绿跌配色
function sectorBg(change) {
  const c = Number(change) || 0
  const abs = Math.abs(c)
  if (c > 0) {
    if (abs >= 3.0) return '#c0392b'
    if (abs >= 2.0) return '#e74c3c'
    if (abs >= 1.0) return '#ec7063'
    if (abs >= 0.5) return '#f5b7b1'
    return '#fadbd8'
  }
  if (c < 0) {
    if (abs >= 3.0) return '#1e8449'
    if (abs >= 2.0) return '#27ae60'
    if (abs >= 1.0) return '#52be80'
    if (abs >= 0.5) return '#82e0aa'
    return '#d5f5e3'
  }
  return '#f2f3f4'
}

function sectorTextColor(change) {
  const c = Number(change) || 0
  const abs = Math.abs(c)
  if (abs >= 0.5) return '#ffffff'
  return '#5d6d7e'
}

function pctColor(change) {
  return sectorTextColor(change)
}

function pctStr(change) {
  const c = Number(change) || 0
  return `${c > 0 ? '+' : ''}${c.toFixed(2)}%`
}

function ellipsis(name, max) {
  if (!name) return ''
  return name.length > max ? name.slice(0, max - 1) + '…' : name
}

// Squarified Treemap
function squarify(nodes, x, y, w, h) {
  if (!nodes.length) return []
  const total = nodes.reduce((s, n) => s + n.weight, 0) || 1
  const result = []
  const isVertical = h >= w
  const short = Math.min(w, h)

  function layout(row, remaining, cx, cy, cw, ch) {
    if (!remaining.length) {
      placeRow(row, cx, cy, cw, ch, result, isVertical)
      return
    }
    const row2 = [...row, remaining[0]]
    const worst1 = worstRatio(row, short, total)
    const worst2 = worstRatio(row2, short, total)
    if (!row.length || worst2 <= worst1) {
      layout(row2, remaining.slice(1), cx, cy, cw, ch)
    } else {
      placeRow(row, cx, cy, cw, ch, result, isVertical)
      const s = row.reduce((a, n) => a + n.weight, 0)
      const area = cw * ch
      const rowLen = (s / total) * area / short
      if (isVertical) {
        layout([], remaining, cx + rowLen, cy, cw - rowLen, ch)
      } else {
        layout([], remaining, cx, cy + rowLen, cw, ch - rowLen)
      }
    }
  }

  layout([], [...nodes], x, y, w, h)
  return result
}

function worstRatio(row, short, total) {
  if (!row.length) return Infinity
  const s = row.reduce((a, n) => a + n.weight, 0)
  const area = short * short * 100
  let worst = 0
  for (const n of row) {
    const nArea = (n.weight / s) * area * short
    const r = Math.max(area / nArea, nArea / area)
    if (r > worst) worst = r
  }
  return worst
}

function placeRow(row, x, y, w, h, result, isVertical) {
  if (!row.length) return
  const s = row.reduce((a, n) => a + n.weight, 0)
  const totalW = isVertical ? w : h
  let pos = isVertical ? x : y
  for (const n of row) {
    const frac = n.weight / s
    const cellSize = frac * totalW
    result.push({
      ...n,
      x: isVertical ? pos : x,
      y: isVertical ? y : pos,
      w: isVertical ? cellSize : w,
      h: isVertical ? h : cellSize,
    })
    pos += cellSize
  }
}

// 构建 Treemap 数据（最多100个）
const treemapNodes = computed(() => {
  const src = filterKind.value === 'industry' ? industryRaw.value : conceptRaw.value
  if (!src.length) return []

  // 取前100，按涨跌幅绝对值排序
  const sorted = [...src]
    .sort((a, b) => Math.abs(Number(b.change) || 0) - Math.abs(Number(a.change) || 0))
    .slice(0, 100)

  const total = sorted.length

  // 前10名特殊布局（双列大区块）
  const megaItems = sorted.slice(0, Math.min(4, total))
  // 11-30名中等区块
  const largeItems = sorted.slice(4, Math.min(16, total))
  // 其余小区块用 Treemap
  const smallItems = sorted.slice(Math.min(16, total))

  const nodes = []
  const GAP = 2

  // MEGA 层：前4个，双列
  const megaW = Math.floor((VW - GAP * 3) / 2)
  const megaH = Math.floor(VH * 0.30)
  megaItems.forEach((s, i) => {
    const col = i % 2
    const row = Math.floor(i / 2)
    const ch = Number(s.change) || 0
    nodes.push({
      id: s.name,
      name: s.name,
      change: ch,
      weight: Math.max(Math.abs(ch), 0.5),
      x: col * (megaW + GAP),
      y: row * (megaH + GAP),
      w: megaW,
      h: megaH,
      bg: sectorBg(ch),
      tc: sectorTextColor(ch),
      pctStr: pctStr(ch),
      pctColor: pctColor(ch),
      label: s.name,
      showName: true,
      showPct: true,
      fn: 13,
      fp: 12,
      rank: sorted.indexOf(s) + 1,
      total,
    })
  })

  // LARGE 层：11-30名，4列
  const largeTop = megaH * 2 + GAP * 2
  const largeBotH = Math.floor(VH * 0.22)
  const largeColW = Math.floor((VW - GAP * 5) / 4)
  largeItems.forEach((s, i) => {
    const col = i % 4
    const row = Math.floor(i / 4)
    const ch = Number(s.change) || 0
    nodes.push({
      id: s.name + '_l',
      name: s.name,
      change: ch,
      weight: Math.max(Math.abs(ch), 0.3),
      x: col * (largeColW + GAP),
      y: largeTop + row * (largeBotH + GAP),
      w: largeColW,
      h: largeBotH,
      bg: sectorBg(ch),
      tc: sectorTextColor(ch),
      pctStr: pctStr(ch),
      pctColor: pctColor(ch),
      label: s.name,
      showName: true,
      showPct: true,
      fn: 10,
      fp: 10,
      rank: sorted.indexOf(s) + 1,
      total,
    })
  })

  // SMALL 层：其余，用 Treemap 填充
  const smallTop = largeTop + Math.ceil(largeItems.length / 4) * (largeBotH + GAP)
  const smallH = VH - smallTop - GAP
  if (smallItems.length > 0) {
    const otherData = smallItems.map(s => ({
      weight: Math.max(Math.abs(Number(s.change) || 0), 0.05),
      data: s,
    }))
    const otherRects = squarify(otherData, 0, smallTop, VW, smallH)
    otherRects.forEach(r => {
      const ch = Number(r.data.change) || 0
      const area = r.w * r.h
      const showPct = area >= 500 && r.w >= 26 && r.h >= 16
      const showName = area >= 700 && r.w >= 36
      nodes.push({
        id: r.data.name + '_s',
        name: r.data.name,
        change: ch,
        x: r.x,
        y: r.y,
        w: r.w,
        h: r.h,
        bg: sectorBg(ch),
        tc: sectorTextColor(ch),
        pctStr: pctStr(ch),
        pctColor: pctColor(ch),
        label: showName ? ellipsis(r.data.name, Math.floor(r.w / 8)) : '',
        showPct,
        showName,
        fn: area < 800 ? 8 : 9,
        fp: area < 800 ? 8 : 9,
        rank: sorted.indexOf(r.data) + 1,
        total,
      })
    })
  }

  return nodes
})

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

// Tooltip
const tooltip = ref({
  visible: false, x: 0, y: 0,
  name: '', pctStr: '', pctColor: '#c0392b',
  rank: 0, total: 0,
})

function showTooltip(e, node) {
  tooltip.value = {
    visible: true,
    x: e.clientX + 14,
    y: e.clientY - 40,
    name: node.name,
    pctStr: node.pctStr,
    pctColor: node.pctColor,
    rank: node.rank,
    total: node.total,
  }
}

function moveTooltip(e) {
  tooltip.value.x = e.clientX + 14
  tooltip.value.y = e.clientY - 40
}

function hideTooltip() {
  tooltip.value.visible = false
}

function onCellClick(node) {
  router.push(`/sectors/${encodeURIComponent(node.name)}`)
}

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
  --gain:    #1e8449;
  --gain-mid:#27ae60;
  --loss:    #c0392b;
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
  padding-bottom: calc(env(safe-area-inset-bottom) + 32px);
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
.kq-breadth-mini__up  { color: var(--loss-mid); }
.kq-breadth-mini__dn  { color: var(--gain-mid); }
.kq-breadth-mini__bar {
  display: flex;
  width: 80px;
  height: 4px;
  border-radius: 2px;
  overflow: hidden;
  background: var(--surface3);
}
.kq-breadth-mini__seg { height: 100%; transition: width 0.3s; }
.kq-breadth-mini__seg--up { background: var(--loss-mid); }
.kq-breadth-mini__seg--dn { background: var(--gain-mid); }
.kq-breadth-mini__status {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 800;
}
.kq-breadth-mini__status.bull { background: #d5f5e3; color: var(--gain); }
.kq-breadth-mini__status.bear { background: #fadbd8; color: var(--loss); }
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
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
  padding: 2px;
  margin-bottom: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}
.kq-treemap {
  width: 100%;
  height: auto;
  display: block;
}
.kq-cell {
  cursor: pointer;
  transition: filter 0.15s;
}
.kq-cell:hover {
  filter: brightness(0.92);
}
.kq-cell-name {
  font-weight: 900;
  letter-spacing: -0.02em;
  pointer-events: none;
  user-select: none;
}
.kq-cell-pct {
  font-weight: 900;
  letter-spacing: -0.02em;
  pointer-events: none;
  user-select: none;
  font-variant-numeric: tabular-nums;
}

/* Tooltip */
.kq-tooltip {
  position: fixed;
  z-index: 1000;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 14px;
  min-width: 130px;
  pointer-events: none;
  box-shadow: 0 4px 20px rgba(0,0,0,0.12);
}
.kq-tooltip__name {
  font-size: 12px;
  font-weight: 800;
  color: var(--text);
  margin-bottom: 4px;
}
.kq-tooltip__pct {
  font-size: 17px;
  font-weight: 900;
  letter-spacing: -0.03em;
  margin-bottom: 6px;
  font-variant-numeric: tabular-nums;
}
.kq-tooltip__rank {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: var(--muted);
}
.kq-tooltip__rank-val {
  font-weight: 800;
  color: var(--text);
}

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
.kq-legend__swatch--deep-gain { background: #c0392b; }
.kq-legend__swatch--gain      { background: #ec7063; }
.kq-legend__swatch--flat      { background: var(--surface3); }
.kq-legend__swatch--loss      { background: #82e0aa; }
.kq-legend__swatch--deep-loss { background: #1e8449; }
</style>
