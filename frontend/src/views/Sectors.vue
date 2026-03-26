<template>
  <div class="sec-page">
    <!-- 每日宏观视角（蓝底横幅） -->
    <section class="sec-macro" v-if="macroData">
      <div class="sec-macro__lbl">MACRO INSIGHT</div>
      <h2 class="sec-macro__ttl">每日宏观视角</h2>
      <p class="sec-macro__body">{{ macroData.summary_text }}</p>
      <div class="sec-macro__tags">
        <span v-for="(t, i) in macroTags" :key="i" class="sec-macro__tag" :class="t.cls">{{ t.text }}</span>
      </div>
    </section>
    <section v-else-if="macroLoading" class="sec-macro sec-macro--skel">
      <div class="sk sk--40" /><div class="sk sk--55" />
      <div class="sk sk--100" /><div class="sk sk--80" />
    </section>

    <!-- 板块涨跌分布 -->
    <section class="hm-card sec-dist">
      <div class="sec-dist__hd">
        <h3 class="hm-macro__title">板块涨跌分布 <span class="hm-macro__en">SECTOR BREADTH</span></h3>
      </div>
      <div class="sec-dist__legend">
        <span class="sec-dist__dot sec-dist__dot--up" />上涨 {{ breadth.up }}
        <span class="sec-dist__dot sec-dist__dot--flat ml" />平盘 {{ breadth.flat }}
        <span class="sec-dist__dot sec-dist__dot--down ml" />下跌 {{ breadth.down }}
      </div>
      <div class="hm-sentiment__bar" role="img" :aria-label="`上涨${breadth.upPct}%`">
        <div class="hm-sentiment__seg is-up" :style="{ width: breadth.upPct + '%' }" />
        <div class="hm-sentiment__seg is-flat" :style="{ width: breadth.flatPct + '%' }" />
        <div class="hm-sentiment__seg is-down" :style="{ width: breadth.downPct + '%' }" />
      </div>
    </section>

    <!-- 热门板块：行业 / 概念 Tab + 列表 -->
    <section class="hm-card sec-hot">
      <div class="sec-hot__hd">
        <span class="sec-hot__ttl">热门板块</span>
        <span class="sec-hot__en">HOT SECTORS</span>
      </div>
      <div class="sec-hot-pills" role="tablist">
        <button
          type="button"
          class="sec-hot-pill"
          :class="{ 'sec-hot-pill--on': hotKind === 'industry' }"
          role="tab"
          @click="hotKind = 'industry'"
        >行业</button>
        <button
          type="button"
          class="sec-hot-pill"
          :class="{ 'sec-hot-pill--on': hotKind === 'concept' }"
          role="tab"
          @click="hotKind = 'concept'"
        >概念</button>
      </div>
      <div class="sec-hot-thead">
        <span>板块名称</span>
        <span class="ta-r">涨跌幅 %</span>
        <span class="ta-r">热度</span>
      </div>
      <div v-if="loadingHot" class="skeleton-chip-row" aria-busy="true">
        <div v-for="i in 6" :key="i" class="sk" style="height:40px;border-radius:6px" />
      </div>
      <div v-else>
        <div
          v-for="s in hotRows"
          :key="s.name"
          class="sec-hot-row"
        >
          <span class="sec-hot-name">{{ s.name }}</span>
          <span class="ta-r sec-pct tabular-nums" :class="pctClass(s.change)">{{ formatPct(s.change) }}%</span>
          <span class="ta-r sec-heat tabular-nums">{{ heatVal(s) }}</span>
        </div>
        <div v-if="!hotRows.length" class="sec-empty">暂无数据</div>
      </div>
    </section>

    <!-- 板块主力净流入（亿）柱状图 -->
    <section class="hm-card sec-flow">
      <div class="sec-flow__hd">
        <span class="sec-hot__ttl">板块主力净流入(亿)</span>
        <button type="button" class="sec-flow__more" @click="scrollToSectorTable">更多 ›</button>
      </div>
      <div class="sec-flow-pills" role="tablist">
        <button
          v-for="t in fundFlowTabs"
          :key="t.id"
          type="button"
          class="sec-flow-pill"
          :class="{ 'sec-flow-pill--on': fundFlowKind === t.id }"
          role="tab"
          @click="fundFlowKind = t.id"
        >{{ t.label }}</button>
      </div>
      <div v-if="loadingFlow" class="sec-flow-skel" aria-busy="true">
        <div v-for="i in 6" :key="i" class="sec-flow-skel__col">
          <div class="sk sk-flow" />
        </div>
      </div>
      <div v-else class="sec-flow-chart">
        <div
          v-for="(item, idx) in fundFlowList"
          :key="item.name + '-' + idx"
          class="sec-flow-col"
        >
          <span
            class="sec-flow-val tabular-nums"
            :class="netYiClass(item.net_yi)"
          >{{ formatNetYi(item.net_yi) }}</span>
          <div class="sec-flow-bar-wrap">
            <div
              class="sec-flow-bar"
              :class="netYiClass(item.net_yi)"
              :style="{ height: barHeightPct(item) + '%' }"
            />
          </div>
          <span class="sec-flow-name">{{ item.name }}</span>
        </div>
        <div v-if="!fundFlowList.length" class="sec-empty sec-empty--flow">暂无资金流数据</div>
      </div>
    </section>

    <!-- 分类 Tab -->
    <div class="sec-tabs-wrap">
      <div class="hm-rank-tabs" role="tablist">
        <button
          v-for="f in statFilters"
          :key="f.value"
          type="button"
          class="hm-rank-tab"
          :class="{ active: statFilter === f.value }"
          role="tab"
          @click="statFilter = f.value"
        >{{ f.label }}</button>
      </div>
    </div>

    <!-- 板块明细表 -->
    <section ref="secTableEl" class="hm-card sec-table">
      <div class="sec-table__hd">
        <span class="hm-macro__title">板块明细 <span class="hm-macro__en">SECTOR LIST</span></span>
      </div>
      <div class="sec-thead">
        <span>板块名称</span>
        <span class="ta-r">今日涨跌 %</span>
        <span class="ta-r">领涨个股</span>
      </div>
      <div v-if="statLoading" class="sec-empty">加载中…</div>
      <template v-else>
        <div
          v-for="row in displayedRows"
          :key="row.name + statSortKey"
          class="sec-tr"
        >
          <span class="sec-td-name">{{ row.name }}</span>
          <span class="sec-td-pct ta-r tabular-nums" :class="pctClass(row.change)">{{ formatPct(row.change) }}%</span>
          <span class="sec-td-lead ta-r">
            <template v-if="row.leader">
              <span class="sec-lead-n">{{ row.leader }}</span>
              <span class="tabular-nums" :class="pctClass(row.leader_change)">{{ formatPct(row.leader_change) }}%</span>
            </template>
            <span v-else class="sec-muted">—</span>
          </span>
        </div>
        <div v-if="!displayedRows.length && !statLoading" class="sec-empty">暂无数据</div>
        <button
          v-if="hasMoreRows"
          type="button"
          class="sec-load-more"
          @click="loadMore"
        >加载更多板块 (LOAD MORE)</button>
      </template>
    </section>

    <footer class="sec-foot">
      <p>数据仅供参考，不构成投资建议。</p>
      <p class="sec-foot-muted">SECTOR DATA · {{ new Date().getFullYear() }}</p>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { market, macroSummary } from '../api/market.js'

const industryList = ref([])
const conceptList = ref([])
const statLoading = ref(false)
const loadingHot = ref(false)
const loadingFlow = ref(false)
const hotKind = ref('industry')
const fundFlowKind = ref('industry')
const fundFlowList = ref([])
const secTableEl = ref(null)

const fundFlowTabs = [
  { id: 'industry', label: '行业' },
  { id: 'concept', label: '概念' },
  { id: 'region', label: '地域' },
]

const statFilter = ref('all')
const statSortKey = ref('change')
const statSortDir = ref('desc')
const displayCount = ref(20)

const statFilters = [
  { label: '全部', value: 'all' },
  { label: '行业', value: 'industry' },
  { label: '概念', value: 'concept' },
  { label: '风格', value: 'style' },
  { label: '地区', value: 'region' },
]

// ── 宏观数据 ────────────────────────────────────────────────
const macroRaw = ref(null)
const macroLoading = ref(false)

const macroData = computed(() => macroRaw.value)

const macroTags = computed(() => {
  const m = macroRaw.value
  if (!m) return []
  const tags = []
  const score = Number(m.sentiment_score)
  if (Number.isFinite(score)) {
    if (score >= 58) tags.push({ text: '看多 Bullish', cls: 'sec-tag--bull' })
    else if (score <= 42) tags.push({ text: '谨慎 Bearish', cls: 'sec-tag--bear' })
    else tags.push({ text: '中性 Neutral', cls: 'sec-tag--neu' })
  }
  const b = m.breadth
  if (b && Number(b.up_pct) >= 52) tags.push({ text: '涨家占优', cls: 'sec-tag--vol' })
  else if (b && Number(b.down_pct) >= 52) tags.push({ text: '跌家偏多', cls: 'sec-tag--bear' })
  if (!tags.length) tags.push({ text: '市场观察', cls: 'sec-tag--neu' })
  return tags.slice(0, 3)
})

// ── 合并板块池 ──────────────────────────────────────────────
const mergedSectors = computed(() => {
  const m = new Map()
  for (const s of industryList.value) { if (s && s.name) m.set(s.name, s) }
  for (const s of conceptList.value)  { if (s && s.name && !m.has(s.name)) m.set(s.name, s) }
  return [...m.values()]
})

// ── 涨跌分布 ───────────────────────────────────────────────
const breadth = computed(() => {
  let up = 0, down = 0, flat = 0
  for (const s of mergedSectors.value) {
    const c = Number(s.change)
    if (!Number.isFinite(c)) continue
    if (c > 0) up++; else if (c < 0) down++; else flat++
  }
  const tot = up + down + flat || 1
  const u = Math.floor((100 * up) / tot)
  const f = Math.floor((100 * flat) / tot)
  const d = 100 - u - f
  return { up, down, flat, upPct: u, flatPct: f, downPct: d < 0 ? 0 : d }
})

// ── 热门列表（行业 / 概念 Tab）──────────────────────────────
const hotRows = computed(() => {
  const src = hotKind.value === 'concept' ? conceptList.value : industryList.value
  return [...src]
    .filter(s => Number.isFinite(Number(s.change)))
    .sort((a, b) => Math.abs(Number(b.change)) - Math.abs(Number(a.change)))
    .slice(0, 6)
})

const fundFlowMaxAbs = computed(() => {
  const list = fundFlowList.value
  if (!list.length) return 1
  return Math.max(...list.map(x => Math.abs(Number(x.net_yi) || 0)), 1e-9)
})

function barHeightPct(item) {
  const v = Math.abs(Number(item.net_yi) || 0)
  return Math.min(100, (v / fundFlowMaxAbs.value) * 100)
}

function formatNetYi(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return '--'
  const sign = n > 0 ? '+' : ''
  return sign + n.toFixed(2)
}

function netYiClass(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return ''
  if (n > 0) return 'is-up'
  if (n < 0) return 'is-down'
  return 'is-flat'
}

function scrollToSectorTable() {
  secTableEl.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
}

function heatVal(s) {
  const raw = s.heat_display
  if (raw != null && String(raw).trim() !== '') {
    const n = parseFloat(String(raw).replace(/[^\d.-]/g, ''))
    if (Number.isFinite(n)) return n.toFixed(1)
  }
  const c = Math.abs(Number(s.change) || 0)
  return Math.min(99, Math.round(50 + c * 12)).toFixed(1)
}

// ── 板块明细列表 ───────────────────────────────────────────
const statBaseList = computed(() => {
  if (statFilter.value === 'industry') return industryList.value
  if (statFilter.value === 'concept')  return conceptList.value
  if (statFilter.value === 'style' || statFilter.value === 'region') return []
  const seen = new Set(), out = []
  for (const s of industryList.value) { if (s && s.name && !seen.has(s.name)) { seen.add(s.name); out.push(s) } }
  for (const s of conceptList.value)  { if (s && s.name && !seen.has(s.name)) { seen.add(s.name); out.push(s) } }
  return out
})

const statSortedList = computed(() => {
  const list = [...statBaseList.value]
  const key = statSortKey.value
  const dir = statSortDir.value === 'asc' ? 1 : -1
  list.sort((a, b) => {
    const va = a[key], vb = b[key]
    if (key === 'name') return dir * String(va).localeCompare(String(vb), 'zh-CN')
    const na = Number(va), nb = Number(vb)
    if (!Number.isFinite(na) && !Number.isFinite(nb)) return 0
    if (!Number.isFinite(na)) return 1
    if (!Number.isFinite(nb)) return -1
    return dir * (na - nb)
  })
  return list
})

const displayedRows  = computed(() => statSortedList.value.slice(0, displayCount.value))
const hasMoreRows    = computed(() => statSortedList.value.length > displayCount.value)

function loadMore() { displayCount.value += 20 }

// ── 工具函数 ───────────────────────────────────────────────
function formatPct(v) {
  if (v == null || v === '' || Number.isNaN(Number(v))) return '--'
  const n = Number(v)
  return (n >= 0 ? '+' : '') + n.toFixed(2)
}

function pctClass(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return ''
  if (n > 0) return 'is-up'
  if (n < 0) return 'is-down'
  return 'is-flat'
}

// ── 数据加载 ───────────────────────────────────────────────
async function loadMacro() {
  macroLoading.value = true
  try { macroRaw.value = await macroSummary() } catch { macroRaw.value = null }
  finally { macroLoading.value = false }
}

async function loadData() {
  statLoading.value = true
  loadingHot.value  = true
  try {
    const [ind, con] = await Promise.all([market.sectors(), market.sectorsConcept()])
    industryList.value = Array.isArray(ind) ? ind : []
    conceptList.value  = Array.isArray(con) ? con : []
  } catch (e) { console.error(e) }
  finally { statLoading.value = false; loadingHot.value = false }
}

async function loadFundFlow() {
  loadingFlow.value = true
  try {
    const data = await market.sectorMainFundFlow(fundFlowKind.value)
    fundFlowList.value = Array.isArray(data) ? data : []
  } catch (e) {
    console.error(e)
    fundFlowList.value = []
  } finally {
    loadingFlow.value = false
  }
}

watch(fundFlowKind, () => { loadFundFlow() })

onMounted(() => {
  loadData()
  loadMacro()
  loadFundFlow()
})
</script>

<style scoped>
/* ── 复用首页变量体系 + 字体层级 ─────────────────────────────── */
.sec-page {
  --hm-primary:      #003ec7;
  --hm-primary-mid:  #0052ff;
  --hm-up:           #a50021;
  --hm-down:         #006d41;
  --hm-surface:      #f8f9fa;
  --hm-low:          #f3f4f5;
  --hm-high:         #e7e8e9;
  --hm-white:        #ffffff;
  --hm-text:         #191c1d;
  --hm-muted:        #434656;
  --hm-outline:      #737688;
  --hm-ghost:        rgba(195, 197, 217, 0.15);
  --hm-ambient:      0 4px 24px rgba(25, 28, 29, 0.06);

  min-height: 100vh;
  min-height: 100dvh;
  background: var(--hm-surface);
  color: var(--hm-text);
  padding: 10px 16px calc(env(safe-area-inset-bottom) + 80px);
  font-family: 'Inter', var(--font);
}

/* 复用首页 .hm-card */
.hm-card {
  background: var(--hm-white);
  border-radius: 8px;
  box-shadow: inset 0 0 0 1px var(--hm-ghost), var(--hm-ambient);
  overflow: hidden;
}

/* 复用首页标题系 */
.hm-macro__title {
  margin: 0;
  font-family: 'Manrope', var(--font);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--hm-primary);
}
.hm-macro__en {
  font-weight: 800;
  opacity: 0.85;
  font-size: 9px;
  letter-spacing: 0.04em;
  color: var(--hm-outline);
}

/* 共用涨跌色 */
.is-up   { color: var(--hm-up)   !important; }
.is-down { color: var(--hm-down) !important; }
.is-flat { color: var(--hm-outline); }
.tabular-nums { font-variant-numeric: tabular-nums; }

/* 复用首页 .hm-sentiment__bar */
.hm-sentiment__bar {
  display: flex;
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
  background: var(--hm-high);
}
.hm-sentiment__seg {
  height: 100%;
  min-width: 0;
  transition: width 0.25s ease;
}
.hm-sentiment__seg.is-up   { background: var(--hm-up); }
.hm-sentiment__seg.is-flat { background: #c3c5d9; }
.hm-sentiment__seg.is-down { background: var(--hm-down); }

/* 复用首页 .hm-rank-tabs */
.hm-rank-tabs {
  display: flex;
  gap: 16px;
  overflow-x: auto;
  padding: 0;
  border-bottom: 1px solid var(--hm-ghost);
  scrollbar-width: none;
}
.hm-rank-tabs::-webkit-scrollbar { display: none; }
.hm-rank-tab {
  flex: 0 0 auto;
  padding: 8px 0 10px;
  font-size: 12px;
  font-weight: 800;
  color: var(--hm-muted);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  cursor: pointer;
  font-family: inherit;
}
.hm-rank-tab.active {
  color: var(--hm-primary);
  border-bottom-color: var(--hm-primary);
}

/* ── 宏观蓝卡（与首页宏观呼应的深蓝底） ─────────────────────── */
.sec-macro {
  position: relative;
  overflow: hidden;
  border-radius: 8px;
  padding: 16px 14px 14px;
  margin-bottom: 12px;
  background: linear-gradient(135deg, #1e3a8a 0%, #172554 50%, #0f172a 100%);
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08), 0 10px 25px -5px rgba(15,23,42,0.35);
}
.sec-macro__lbl {
  display: inline-block;
  margin-bottom: 8px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.9);
  background: rgba(255,255,255,0.12);
  border: 1px solid rgba(255,255,255,0.2);
}
.sec-macro__ttl {
  margin: 0 0 8px;
  font-family: 'Manrope', 'Inter', sans-serif;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #fff;
}
.sec-macro__body {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.55;
  color: rgba(255,255,255,0.88);
  font-weight: 500;
}
.sec-macro__tags { display: flex; flex-wrap: wrap; gap: 8px; }
.sec-macro__tag {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 9999px;
  font-size: 10px;
  font-weight: 700;
}
.sec-tag--bull { background: rgba(34,197,94,0.25); color: #bbf7d0; border: 1px solid rgba(34,197,94,0.35); }
.sec-tag--bear { background: rgba(248,113,113,0.2); color: #fecaca; border: 1px solid rgba(248,113,113,0.35); }
.sec-tag--neu  { background: rgba(255,255,255,0.12); color: rgba(255,255,255,0.9); border: 1px solid rgba(255,255,255,0.2); }
.sec-tag--vol  { background: rgba(59,130,246,0.25); color: #bfdbfe; border: 1px solid rgba(59,130,246,0.35); }

.sec-macro--skel .sk {
  height: 11px;
  border-radius: 5px;
  background: rgba(255,255,255,0.12);
  margin-bottom: 9px;
}
.sk--40  { width: 40%; }
.sk--55  { width: 55%; height: 20px; }
.sk--100 { width: 100%; }
.sk--80  { width: 80%; }

/* ── 分布条 ───────────────────────────────────────────────── */
.sec-dist {
  padding: 14px 14px 12px;
  margin-bottom: 12px;
}
.sec-dist__hd { margin-bottom: 10px; }
.sec-dist__legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 0;
  margin-bottom: 10px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.02em;
  color: var(--hm-muted);
}
.sec-dist__dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-right: 5px;
  vertical-align: middle;
}
.sec-dist__dot--up   { background: var(--hm-up); }
.sec-dist__dot--flat { background: #c3c5d9; }
.sec-dist__dot--down { background: var(--hm-down); }
.ml { margin-left: 14px; }

/* ── 热门列表 ─────────────────────────────────────────────── */
.sec-hot {
  padding: 12px 0 0;
  margin-bottom: 12px;
}
.sec-hot__hd {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 0 14px 10px;
}
.sec-hot__ttl {
  font-family: 'Manrope', var(--font);
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--hm-text);
}
.sec-hot__en {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--hm-outline);
}

.sec-hot-pills {
  display: flex;
  gap: 8px;
  padding: 0 14px 10px;
}
.sec-hot-pill {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  border: 1px solid var(--hm-ghost);
  background: var(--hm-white);
  color: var(--hm-muted);
  cursor: pointer;
  font-family: inherit;
}
.sec-hot-pill--on {
  background: rgba(165, 0, 33, 0.1);
  border-color: rgba(165, 0, 33, 0.35);
  color: var(--hm-up);
}

.sec-flow {
  margin-bottom: 12px;
}
.sec-flow__hd {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px 8px;
}
.sec-flow__more {
  font-size: 12px;
  font-weight: 700;
  color: var(--hm-outline);
  background: none;
  border: none;
  cursor: pointer;
  font-family: inherit;
}
.sec-flow-pills {
  display: flex;
  gap: 8px;
  padding: 0 14px 10px;
  flex-wrap: wrap;
}
.sec-flow-pill {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  border: 1px solid var(--hm-ghost);
  background: var(--hm-white);
  color: var(--hm-muted);
  cursor: pointer;
  font-family: inherit;
}
.sec-flow-pill--on {
  background: rgba(165, 0, 33, 0.1);
  border-color: rgba(165, 0, 33, 0.35);
  color: var(--hm-up);
}

.sec-flow-chart {
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  gap: 4px;
  padding: 4px 14px 14px;
  min-height: 168px;
  position: relative;
}
.sec-flow-col {
  flex: 1;
  min-width: 0;
  max-width: 18%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.sec-flow-val {
  font-size: 10px;
  font-weight: 800;
  line-height: 1.2;
  text-align: center;
}
.sec-flow-bar-wrap {
  flex: 1;
  width: 100%;
  min-height: 92px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  align-items: stretch;
}
.sec-flow-bar {
  width: 100%;
  min-height: 3px;
  border-radius: 4px 4px 0 0;
  transition: height 0.3s ease;
}
.sec-flow-bar.is-up { background: var(--hm-up); }
.sec-flow-bar.is-down { background: var(--hm-down); }
.sec-flow-bar.is-flat { background: var(--hm-outline); }
.sec-flow-name {
  font-size: 9px;
  font-weight: 600;
  color: var(--hm-muted);
  text-align: center;
  line-height: 1.25;
  max-width: 100%;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.sec-flow-skel {
  display: flex;
  justify-content: space-between;
  gap: 6px;
  padding: 12px 14px 20px;
  min-height: 140px;
}
.sec-flow-skel__col {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}
.sk-flow {
  height: 72px;
  border-radius: 6px;
  width: 100%;
}

.sec-empty--flow {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.sec-hot-thead {
  display: grid;
  grid-template-columns: 1fr 72px 56px;
  gap: 6px;
  padding: 7px 14px;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--hm-outline);
  background: var(--hm-low);
}
.sec-hot-row {
  display: grid;
  grid-template-columns: 1fr 72px 56px;
  gap: 6px;
  align-items: center;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 800;
  box-shadow: 0 1px 0 var(--hm-ghost);
  background: var(--hm-white);
  transition: background 0.12s;
}
.sec-hot-row:active { background: var(--hm-low); }
.sec-hot-name {
  font-family: 'Manrope', var(--font);
  font-weight: 800;
  color: var(--hm-text);
}
.sec-pct { font-size: 13px; }
.sec-heat { font-size: 11px; font-weight: 700; color: var(--hm-muted); }

/* ── Tab 包装 ─────────────────────────────────────────────── */
.sec-tabs-wrap { margin-bottom: 10px; }

/* ── 板块明细表 ───────────────────────────────────────────── */
.sec-table {
  padding: 12px 0 0;
  margin-bottom: 10px;
}
.sec-table__hd {
  padding: 0 14px 10px;
}
.sec-thead {
  display: grid;
  grid-template-columns: 1fr 88px 1fr;
  gap: 6px;
  padding: 7px 14px;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--hm-outline);
  background: var(--hm-low);
}
.ta-r { text-align: right; }

.sec-tr {
  display: grid;
  grid-template-columns: 1fr 88px 1fr;
  gap: 6px;
  align-items: center;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 800;
  box-shadow: 0 1px 0 var(--hm-ghost);
  background: var(--hm-white);
  transition: background 0.12s;
}
.sec-tr:last-of-type { border-bottom: none; }
.sec-tr:active { background: var(--hm-low); }

.sec-td-name {
  font-family: 'Manrope', var(--font);
  font-weight: 800;
  color: var(--hm-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sec-td-pct { font-size: 13px; }
.sec-td-lead {
  font-size: 11px;
  line-height: 1.4;
  text-align: right;
}
.sec-lead-n { color: var(--hm-muted); margin-right: 4px; }
.sec-muted { color: var(--hm-outline); }

.sec-empty {
  padding: 20px;
  text-align: center;
  font-size: 13px;
  color: var(--hm-outline);
}

.sec-load-more {
  display: block;
  width: 100%;
  padding: 14px;
  border: none;
  background: transparent;
  font-size: 12px;
  font-weight: 700;
  color: var(--hm-primary);
  cursor: pointer;
  font-family: inherit;
}

/* ── Footer ───────────────────────────────────────────────── */
.sec-foot {
  text-align: center;
  padding: 16px 8px 8px;
  font-size: 11px;
  color: var(--hm-outline);
}
.sec-foot-muted { margin: 4px 0 0; }

/* skeleton 共用 */
.skeleton-chip-row { display: flex; flex-wrap: wrap; gap: 8px; padding: 12px 14px; }
.sk {
  height: 56px;
  border-radius: 12px;
  background: linear-gradient(90deg, var(--hm-low) 0%, var(--hm-high) 50%, var(--hm-low) 100%);
  background-size: 200% 100%;
  animation: sk-shine 1.1s ease-in-out infinite;
}
@keyframes sk-shine {
  0%   { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}
</style>
