<template>
  <div class="bsd-page">
    <header class="bsd-header">
      <button type="button" class="bsd-back" aria-label="返回" @click="goBack">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <h1 class="bsd-title">布林带收缩策略</h1>
      <button type="button" class="bsd-head-link" @click="$router.push('/strategy/bollinger/history')">历史</button>
    </header>

    <main class="bsd-main">
      <div v-if="loading" class="bsd-state"><div class="bsd-spin" /></div>
      <div v-else-if="loadError" class="bsd-state bsd-state--err">{{ loadError }}</div>
      <template v-else-if="detail">
        <!-- 区域 1：扫描历史文案 + 元信息 -->
        <section class="bsd-hero">
          <p class="bsd-hero__eyebrow">布林带收缩策略 · 单次扫描档案</p>
          <p class="bsd-hero__lead">
            以下为本轮扫描的归档快照，便于对照当时的热点板块、参数设置与命中标的，快速回顾市场结构。
          </p>
          <div class="bsd-hero__time-block">
            <p class="bsd-hero__k">扫描时间</p>
            <p class="bsd-hero__time">{{ fmtScanTime(detail.scan_time) }}</p>
          </div>
          <ul class="bsd-hero__facts">
            <li><span class="bsd-fact-k">扫描参数</span>{{ paramLine(detail) }}</li>
            <li><span class="bsd-fact-k">覆盖范围</span>{{ sectorCount }} 个板块 · {{ stockTotal }} 只股票</li>
            <li v-if="detail.status"><span class="bsd-fact-k">状态</span>{{ statusText(detail.status) }}</li>
          </ul>
        </section>

        <!-- 区域 2：DeepSeek 模型小结（与主策略页共用组件，服务端持久化缓存） -->
        <BollingerAiSummaryPanel
          v-if="scanId"
          :scan-id="scanId"
          :flat-stocks="flatStocks"
          :fallback-summary="summaryText"
        />

        <!-- 区域 3：成分卡片 + 加载更多 -->
        <section class="bsd-list-sec">
          <h2 class="bsd-sec-title">成分与表现</h2>
          <p v-if="stockTotal === 0" class="bsd-empty">该扫描暂无成分数据，可能扫描未完成或结果未写入。</p>
          <template v-else>
            <div v-if="sectorTabs.length" class="bsd-sector-tabs" role="tablist" aria-label="按板块筛选">
              <button
                type="button"
                role="tab"
                class="bsd-sector-tab"
                :class="{ 'bsd-sector-tab--on': activeSector === '' }"
                :aria-selected="activeSector === ''"
                @click="setSectorTab('')"
              >
                全部<span class="bsd-sector-tab__n">{{ stockTotal }}</span>
              </button>
              <button
                v-for="t in sectorTabs"
                :key="t.key"
                type="button"
                role="tab"
                class="bsd-sector-tab"
                :class="{ 'bsd-sector-tab--on': activeSector === t.key }"
                :aria-selected="activeSector === t.key"
                @click="setSectorTab(t.key)"
              >
                {{ t.key }}<span class="bsd-sector-tab__n">{{ t.count }}</span>
              </button>
            </div>

            <article
              v-for="(s, idx) in visibleStocks"
              :key="s.code + '-' + (s.sector_name || '') + '-' + idx"
              class="bsd-card"
            >
              <div class="bsd-card__head">
                <span class="bsd-card__name">{{ s.name || '—' }}</span>
                <span class="bsd-card__code">{{ s.code }}</span>
              </div>
              <div class="bsd-card__rows">
                <div class="bsd-card__row">
                  <span class="bsd-card__k">所属板块</span>
                  <span class="bsd-card__v">{{ s.sector_name || '—' }}</span>
                </div>
                <div class="bsd-card__row">
                  <span class="bsd-card__k">涨跌幅</span>
                  <span class="bsd-card__v" :class="pctClass(s)">{{ fmtPct(s) }}</span>
                </div>
                <div class="bsd-card__row">
                  <span class="bsd-card__k">评分 / 等级</span>
                  <span class="bsd-card__v">{{ fmtScore(s) }}<template v-if="s.grade"> · {{ s.grade }} 级</template></span>
                </div>
                <div class="bsd-card__row">
                  <span class="bsd-card__k">收缩 / 带宽</span>
                  <span class="bsd-card__v">{{ fmtSq(s) }} · {{ fmtBw(s) }}</span>
                </div>
                <div v-if="stockTagsLine(s)" class="bsd-card__row bsd-card__row--tags">
                  <span class="bsd-card__k">标签</span>
                  <span class="bsd-card__v bsd-card__tags">{{ stockTagsLine(s) }}</span>
                </div>
              </div>
              <button
                type="button"
                class="bsd-card__link"
                :disabled="stockAiLoading && stockAiTargetCode === s.code"
                @click="runStockAi(s)"
              >
                {{ stockAiLoading && stockAiTargetCode === s.code ? 'DeepSeek 分析中…' : 'DeepSeek 分析此股' }}
              </button>
            </article>

            <button
              v-if="canLoadMore"
              type="button"
              class="bsd-load-more"
              @click="loadMore"
            >加载更多</button>
          </template>
        </section>
      </template>
    </main>

    <!-- 单股 DeepSeek 分析 -->
    <div
      v-if="stockAiOpen"
      class="bsd-ai-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="bsd-ai-title"
      @click.self="closeStockAi"
    >
      <div class="bsd-ai-panel">
        <div class="bsd-ai-panel__head">
          <h2 id="bsd-ai-title" class="bsd-ai-panel__title">
            DeepSeek 单股解读
            <span v-if="stockAiStock" class="bsd-ai-panel__sub">{{ stockAiStock.name }} {{ stockAiStock.code }}</span>
          </h2>
          <button type="button" class="bsd-ai-close" aria-label="关闭" @click="closeStockAi">×</button>
        </div>
        <div class="bsd-ai-panel__body">
          <div v-if="stockAiLoading" class="bsd-ai-state">
            <div class="bsd-spin" />
            <p>正在结合本次扫描的收缩指标与标签推理…</p>
          </div>
          <div v-else-if="stockAiError" class="bsd-ai-state bsd-ai-state--err">{{ stockAiError }}</div>
          <template v-else-if="stockAiDisplay">
            <p v-if="stockAiDisplay.summary" class="bsd-ai-summary">{{ stockAiDisplay.summary }}</p>
            <p v-if="stockAiDisplay.risk_note" class="bsd-ai-risk">{{ stockAiDisplay.risk_note }}</p>
            <details v-if="stockAiDisplay.cot_steps?.length" class="bsd-ai-cot">
              <summary>查看推理过程（Chain-of-Thought）</summary>
              <div class="bsd-ai-cot__steps">
                <div v-for="(step, i) in stockAiDisplay.cot_steps" :key="i" class="bsd-ai-step">
                  <p class="bsd-ai-step__t">{{ step.title }}</p>
                  <p class="bsd-ai-step__c">{{ step.content }}</p>
                </div>
              </div>
            </details>
            <p class="bsd-ai-foot">由 DeepSeek 生成 · 仅供参考 · 不构成投资建议</p>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { scan } from '@/api/strategy.js'
import BollingerAiSummaryPanel from '@/components/BollingerAiSummaryPanel.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const loadError = ref('')
const detail = ref(null)

const PAGE = 5
const visibleCount = ref(PAGE)
/** 板块筛选：空字符串 = 全部 */
const activeSector = ref('')

const scanId = computed(() => {
  const id = route.params.id
  const n = Number(id)
  return Number.isFinite(n) ? n : null
})

const flatStocks = computed(() => {
  const d = detail.value
  if (!d?.results) return []
  const list = []
  for (const [sectorName, block] of Object.entries(d.results)) {
    const stocks = block?.stocks || []
    for (const s of stocks) {
      list.push({ ...s, sector_name: sectorName })
    }
  }
  list.sort((a, b) => {
    const sa = Number(a.total_score ?? a.score ?? 0)
    const sb = Number(b.total_score ?? b.score ?? 0)
    return sb - sa
  })
  return list
})

const sectorTabs = computed(() => {
  const d = detail.value
  if (!d?.results) return []
  return Object.entries(d.results)
    .map(([key, block]) => ({
      key,
      count: (block?.stocks || []).length,
      change: Number(block?.change || 0),
    }))
    .filter(t => t.count > 0)
    .sort((a, b) => Math.abs(b.change) - Math.abs(a.change))
})

const filteredStocks = computed(() => {
  if (!activeSector.value) return flatStocks.value
  return flatStocks.value.filter(s => s.sector_name === activeSector.value)
})

const stockTotal = computed(() => flatStocks.value.length)

const sectorCount = computed(() => {
  const d = detail.value
  if (!d?.results) return 0
  return Object.keys(d.results).length
})

const visibleStocks = computed(() => filteredStocks.value.slice(0, visibleCount.value))

const canLoadMore = computed(() => visibleCount.value < filteredStocks.value.length)

const stockAiOpen = ref(false)
const stockAiLoading = ref(false)
const stockAiError = ref('')
const stockAiStock = ref(null)
const stockAiData = ref(null)
const stockAiTargetCode = ref('')

/** 模型偶发把合法 JSON 整段写进 summary，前端再解析一层，避免整屏 raw JSON */
function normalizeStockAiData(raw) {
  if (!raw || typeof raw !== 'object') return null
  const sum = raw.summary
  if (typeof sum !== 'string') return raw
  const t = sum.trim()
  if (!t.startsWith('{')) return raw
  try {
    const inner = JSON.parse(t)
    if (!inner || typeof inner !== 'object') return raw
    const steps = inner.cot_steps
    const hasCot = Array.isArray(steps) && steps.length > 0
    const innerSum = inner.summary
    const hasSum = typeof innerSum === 'string' && innerSum.trim().length > 0
    const hasRisk = typeof inner.risk_note === 'string' && inner.risk_note.trim().length > 0
    if (hasCot || hasSum || hasRisk) {
      return {
        ...raw,
        cot_steps: hasCot ? steps : (raw.cot_steps || []),
        summary: hasSum ? innerSum.trim() : '',
        risk_note: hasRisk ? inner.risk_note.trim() : (raw.risk_note || ''),
      }
    }
  } catch {
    /* ignore */
  }
  return raw
}

const stockAiDisplay = computed(() => normalizeStockAiData(stockAiData.value))

const summaryText = computed(() => buildSummary(detail.value, flatStocks.value))

watch(scanId, () => {
  visibleCount.value = PAGE
  activeSector.value = ''
  loadDetail()
})

function setSectorTab(key) {
  activeSector.value = key
  visibleCount.value = PAGE
}

function loadMore() {
  visibleCount.value += PAGE
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/strategy/bollinger/history')
}

function stockTagsLine(s) {
  const tags = s?.tags
  if (!Array.isArray(tags) || !tags.length) return ''
  return tags.map(t => String(t)).filter(Boolean).join(' · ')
}

async function runStockAi(s) {
  const id = scanId.value
  if (id == null || !s?.code) return
  stockAiTargetCode.value = String(s.code)
  stockAiStock.value = s
  stockAiOpen.value = true
  stockAiLoading.value = true
  stockAiError.value = ''
  stockAiData.value = null
  try {
    stockAiData.value = await scan.stockAiAnalysis(id, s.code)
  } catch (e) {
    stockAiError.value = e.message || '分析失败'
  } finally {
    stockAiLoading.value = false
    stockAiTargetCode.value = ''
  }
}

function closeStockAi() {
  stockAiOpen.value = false
  stockAiStock.value = null
  stockAiData.value = null
  stockAiError.value = ''
}

function fmtScanTime(t) {
  if (!t) return '—'
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return String(t)
  const p = n => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function paramLine(rec) {
  const p = rec?.params || {}
  const sectors = p.sectors ?? p.top_sectors
  const minDays = p.min_days
  const period = p.period
  const parts = []
  if (sectors != null) parts.push(`板块数 ${sectors}`)
  if (minDays != null) parts.push(`挤压≥${minDays}天`)
  if (period != null) parts.push(`周期${period}天`)
  return parts.length ? parts.join(' · ') : '默认参数'
}

function statusText(s) {
  const m = { completed: '已完成', scanning: '扫描中', error: '失败', cancelled: '已取消' }
  return m[s] || s || '—'
}

function fmtPct(s) {
  const v = Number(s?.pct_change)
  if (!Number.isFinite(v)) return '—'
  const sign = v > 0 ? '+' : ''
  return `${sign}${v.toFixed(2)}%`
}

function pctClass(s) {
  const v = Number(s?.pct_change)
  if (!Number.isFinite(v)) return ''
  if (v > 0) return 'bsd-up'
  if (v < 0) return 'bsd-down'
  return ''
}

function fmtScore(s) {
  const v = Number(s?.total_score ?? s?.score)
  return Number.isFinite(v) ? v.toFixed(1) : '—'
}

function fmtSq(s) {
  const v = s?.squeeze_days
  if (v == null || v === '') return '—'
  return `收缩 ${v} 天`
}

function fmtBw(s) {
  const v = s?.bandwidth_pct ?? s?.bandwidth
  if (v == null || v === '') return '带宽 —'
  const n = Number(v)
  return Number.isFinite(n) ? `带宽 ${n.toFixed(1)}%` : `带宽 ${v}`
}

function buildSummary(d, stocks) {
  if (!d) return ''
  if (!stocks.length) {
    return '本次扫描未写入成分股结果，或该次任务未产生有效标的。若刚完成扫描，可稍后在历史记录中刷新后再试。'
  }
  const sGr = stocks.filter(x => x.grade === 'S').length
  const aGr = stocks.filter(x => x.grade === 'A').length
  const sq = stocks
    .map(x => Number(x.squeeze_days))
    .filter(Number.isFinite)
  const avgSq = sq.length ? (sq.reduce((a, b) => a + b, 0) / sq.length).toFixed(1) : null

  const sectors = d.results ? Object.entries(d.results) : []
  const top = [...sectors]
    .sort((a, b) => Math.abs(Number(b[1]?.change || 0)) - Math.abs(Number(a[1]?.change || 0)))
    .slice(0, 3)
    .map(([name, b]) => `${name}（${Number(b?.change || 0) >= 0 ? '+' : ''}${Number(b?.change || 0).toFixed(2)}%）`)
    .join('、')

  let t = `本次共纳入 ${stocks.length} 只标的；其中 S 级 ${sGr} 只、A 级 ${aGr} 只。`
  if (avgSq) t += ` 样本平均连续收缩约 ${avgSq} 个交易日，有利于观察布林带收窄后的变盘可能。`
  if (top) t += ` 板块层面，涨幅领先的前几位包括：${top}。`
  t += ' 以下为该次扫描中的个股列表，可按板块筛选，并可用「DeepSeek 分析此股」结合当次收缩指标与标签解读。'
  return t
}

async function loadDetail() {
  const id = scanId.value
  if (id == null) {
    loadError.value = '无效的记录编号'
    loading.value = false
    return
  }
  loading.value = true
  loadError.value = ''
  try {
    const data = await scan.detail(id)
    if (!data || data.id == null) {
      loadError.value = '记录不存在'
      detail.value = null
      return
    }
    detail.value = data
  } catch (e) {
    loadError.value = e.message || '加载失败'
    detail.value = null
  } finally {
    loading.value = false
  }
}

onMounted(loadDetail)
</script>

<style scoped>
.bsd-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: #f9f9fe;
  color: #1a1c1f;
  font-family: 'Inter', 'Manrope', 'PingFang SC', var(--font), system-ui, sans-serif;
  padding-bottom: calc(28px + env(safe-area-inset-bottom, 0px));
}

.bsd-header {
  display: grid;
  grid-template-columns: 44px 1fr 44px;
  align-items: center;
  padding: 10px 12px;
  padding-top: calc(10px + env(safe-area-inset-top, 0px));
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(16px);
  position: sticky;
  top: 0;
  z-index: 20;
  box-shadow: 0 1px 0 rgba(26, 28, 31, 0.06);
}
.bsd-back {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 12px;
  background: #f3f3f8;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.bsd-back .icon { width: 20px; height: 20px; fill: currentColor; }
.bsd-title {
  margin: 0;
  text-align: center;
  font-size: 1.125rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.bsd-head-link {
  justify-self: end;
  padding: 8px 4px;
  border: none;
  background: none;
  font-size: 14px;
  font-weight: 700;
  color: #0052ff;
  cursor: pointer;
}

.bsd-main {
  max-width: 720px;
  margin: 0 auto;
  padding: 20px 16px 32px;
}

.bsd-state {
  text-align: center;
  padding: 48px 20px;
  color: #434656;
}
.bsd-state--err { color: #f23645; }
.bsd-spin {
  width: 32px;
  height: 32px;
  margin: 0 auto;
  border: 2px solid #e2e2e7;
  border-top-color: #0052ff;
  border-radius: 50%;
  animation: bsd-spin 0.7s linear infinite;
}
@keyframes bsd-spin { to { transform: rotate(360deg); } }

/* 区域 1 */
.bsd-hero {
  background: #fff;
  border-radius: 20px;
  padding: 22px 20px;
  box-shadow: 0 8px 24px rgba(26, 28, 31, 0.06);
  margin-bottom: 20px;
}
.bsd-hero__eyebrow {
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #737688;
  margin: 0 0 8px;
}
.bsd-hero__lead {
  margin: 0 0 20px;
  font-size: 15px;
  line-height: 1.6;
  color: #434656;
}
.bsd-hero__time-block {
  text-align: center;
  padding: 16px 12px;
  margin-bottom: 18px;
  background: #f3f3f8;
  border-radius: 16px;
}
.bsd-hero__k {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #737688;
}
.bsd-hero__time {
  margin: 0;
  font-family: 'Manrope', sans-serif;
  font-size: 1.5rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #1a1c1f;
}
.bsd-hero__facts {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 14px;
  line-height: 1.5;
  color: #434656;
}
.bsd-fact-k {
  display: block;
  font-size: 11px;
  font-weight: 800;
  color: #737688;
  margin-bottom: 2px;
}

/* 区域 3 */
.bsd-list-sec .bsd-sec-title {
  margin: 0 0 14px;
  font-size: 1.05rem;
  font-weight: 800;
  color: #1a1c1f;
}

.bsd-sector-tabs {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 4px;
  margin-bottom: 16px;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.bsd-sector-tabs::-webkit-scrollbar { display: none; }
.bsd-sector-tab {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: none;
  border-radius: 9999px;
  font-size: 13px;
  font-weight: 700;
  font-family: inherit;
  cursor: pointer;
  background: #eef0f5;
  color: #434656;
  transition: background 0.15s, color 0.15s;
  max-width: 200px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bsd-sector-tab--on {
  background: linear-gradient(135deg, #003ec7, #0052ff);
  color: #fff;
}
.bsd-sector-tab__n {
  font-size: 11px;
  font-weight: 800;
  opacity: 0.85;
  padding: 2px 6px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.08);
}
.bsd-sector-tab--on .bsd-sector-tab__n {
  background: rgba(255, 255, 255, 0.22);
}

.bsd-empty {
  text-align: center;
  padding: 28px 16px;
  color: #787b86;
  font-size: 14px;
}

.bsd-card {
  background: #fff;
  border-radius: 18px;
  padding: 20px 18px;
  margin-bottom: 14px;
  box-shadow: 0 8px 24px rgba(26, 28, 31, 0.06);
}
.bsd-card__head {
  text-align: center;
  margin-bottom: 14px;
}
.bsd-card__name {
  display: block;
  font-family: 'Manrope', sans-serif;
  font-size: 1.25rem;
  font-weight: 800;
  color: #1a1c1f;
}
.bsd-card__code {
  display: block;
  margin-top: 4px;
  font-size: 13px;
  font-weight: 600;
  color: #787b86;
}
.bsd-card__rows {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
}
.bsd-card__row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  font-size: 14px;
}
.bsd-card__k {
  flex-shrink: 0;
  color: #737688;
  font-weight: 600;
}
.bsd-card__v {
  text-align: right;
  color: #1a1c1f;
  font-weight: 600;
}
.bsd-card__row--tags .bsd-card__v {
  text-align: right;
  font-size: 12px;
  line-height: 1.45;
  font-weight: 500;
  color: #5c5f6e;
}
.bsd-card__tags { white-space: normal; word-break: break-all; }
.bsd-up { color: #059669 !important; }
.bsd-down { color: #dc2626 !important; }

.bsd-card__link {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 700;
  font-family: inherit;
  cursor: pointer;
  color: #fff;
  background: linear-gradient(135deg, #003ec7, #0052ff);
}
.bsd-card__link:active { transform: scale(0.99); }
.bsd-card__link:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.bsd-load-more {
  display: block;
  width: 100%;
  margin-top: 6px;
  padding: 14px;
  border: none;
  border-radius: 14px;
  font-size: 15px;
  font-weight: 700;
  font-family: inherit;
  cursor: pointer;
  color: #0052ff;
  background: rgba(0, 82, 255, 0.1);
}
.bsd-load-more:active { transform: scale(0.99); }

/* 单股 DeepSeek 弹层 */
.bsd-ai-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(26, 28, 31, 0.45);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: env(safe-area-inset-top, 0) 0 0;
}
@media (min-width: 520px) {
  .bsd-ai-overlay {
    align-items: center;
    padding: 24px;
  }
}
.bsd-ai-panel {
  width: 100%;
  max-width: 520px;
  max-height: min(88vh, 720px);
  background: #fff;
  border-radius: 20px 20px 0 0;
  box-shadow: 0 -8px 40px rgba(26, 28, 31, 0.12);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
@media (min-width: 520px) {
  .bsd-ai-panel {
    border-radius: 20px;
  }
}
.bsd-ai-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 18px 12px;
  border-bottom: 1px solid #ededf2;
}
.bsd-ai-panel__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 800;
  color: #1a1c1f;
  line-height: 1.35;
}
.bsd-ai-panel__sub {
  display: block;
  margin-top: 4px;
  font-size: 13px;
  font-weight: 600;
  color: #737688;
}
.bsd-ai-close {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 12px;
  background: #f3f3f8;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  color: #434656;
}
.bsd-ai-panel__body {
  padding: 16px 18px 22px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}
.bsd-ai-state {
  text-align: center;
  padding: 32px 12px;
  color: #434656;
  font-size: 14px;
}
.bsd-ai-state--err { color: #dc2626; }
.bsd-ai-summary {
  margin: 0 0 12px;
  font-size: 15px;
  line-height: 1.65;
  color: #1a1c1f;
}
.bsd-ai-risk {
  margin: 0 0 16px;
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.55;
  color: #7c2d12;
  background: #fff7ed;
  border-radius: 12px;
}
.bsd-ai-cot {
  margin-bottom: 14px;
  border-radius: 14px;
  background: #f3f3f8;
  padding: 12px 14px;
  font-size: 13px;
}
.bsd-ai-cot summary {
  cursor: pointer;
  font-weight: 700;
  color: #003ec7;
}
.bsd-ai-cot__steps {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.bsd-ai-step__t {
  margin: 0 0 4px;
  font-weight: 800;
  font-size: 12px;
  color: #737688;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.bsd-ai-step__c {
  margin: 0;
  line-height: 1.55;
  color: #434656;
  white-space: pre-wrap;
}
.bsd-ai-foot {
  margin: 0;
  font-size: 11px;
  color: #9ca3af;
  text-align: center;
}
</style>
