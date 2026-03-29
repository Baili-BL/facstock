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
              </div>
              <button type="button" class="bsd-card__link" @click="goMainStrategy">
                在完整分析中查看
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

const stockTotal = computed(() => flatStocks.value.length)

const sectorCount = computed(() => {
  const d = detail.value
  if (!d?.results) return 0
  return Object.keys(d.results).length
})

const visibleStocks = computed(() => flatStocks.value.slice(0, visibleCount.value))

const canLoadMore = computed(() => visibleCount.value < flatStocks.value.length)

const summaryText = computed(() => buildSummary(detail.value, flatStocks.value))

watch(scanId, () => {
  visibleCount.value = PAGE
  loadDetail()
})

function loadMore() {
  visibleCount.value += PAGE
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/strategy/bollinger/history')
}

function goMainStrategy() {
  const id = scanId.value
  if (id == null) return
  router.push({ path: '/strategy/bollinger', query: { scan_id: String(id) } })
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
  t += ' 以下为该次扫描中的个股列表，可在「完整分析」中结合 K 线与标签进一步研判。'
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
</style>
