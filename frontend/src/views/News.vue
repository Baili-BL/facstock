<template>
  <div class="news-page tv-news">
    <!-- 顶栏：TradingView 式极简，标题 + 刷新 -->
    <header class="tv-header">
      <div class="tv-header__title">财经快讯</div>
      <button
        type="button"
        class="tv-header__refresh"
        :class="{ 'tv-header__refresh--spin': loading }"
        aria-label="刷新"
        @click="refresh"
      >
        <svg class="tv-header__refresh-icon" viewBox="0 0 24 24" fill="currentColor">
          <path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
        </svg>
      </button>
    </header>

    <!-- 筛选区：维度拆分，避免时间与来源混在同一行 -->
    <div class="tv-filters">
      <section class="tv-filter-block" aria-labelledby="news-time-label">
        <div id="news-time-label" class="tv-filter-block__label">时间范围</div>
        <div class="tv-pill-row" role="tablist" aria-label="按时间筛选">
          <button
            v-for="tab in timeTabs"
            :key="tab.id"
            type="button"
            class="tv-pill tv-pill--primary"
            :class="{ 'tv-pill--active': timeFilter === tab.id }"
            role="tab"
            :aria-selected="timeFilter === tab.id"
            @click="timeFilter = tab.id"
          >
            {{ tab.label }}
          </button>
        </div>
      </section>

      <section class="tv-filter-block" aria-labelledby="news-source-label">
        <div id="news-source-label" class="tv-filter-block__label">来源</div>
        <div class="tv-pill-row" role="tablist" aria-label="按来源筛选">
          <button
            v-for="tab in sourceTabs"
            :key="'src-' + tab.id"
            type="button"
            class="tv-pill tv-pill--primary"
            :class="{ 'tv-pill--active': sourceFilter === tab.id }"
            role="tab"
            :aria-selected="sourceFilter === tab.id"
            @click="sourceFilter = tab.id"
          >
            {{ tab.label }}
          </button>
        </div>
      </section>

      <section class="tv-filter-block tv-filter-block--sentiment" aria-label="情感筛选">
        <div class="tv-sentiment-row">
          <button
            type="button"
            class="tv-chip"
            :class="{ 'tv-chip--active': sentimentFilter === 'all' }"
            @click="sentimentFilter = 'all'"
          >
            全部
          </button>
          <button
            type="button"
            class="tv-chip tv-chip--bull"
            :class="{ 'tv-chip--active': sentimentFilter === 'positive' }"
            @click="sentimentFilter = sentimentFilter === 'positive' ? 'all' : 'positive'"
          >
            <span class="tv-chip__dot tv-chip__dot--red" />利好
          </button>
          <button
            type="button"
            class="tv-chip tv-chip--bear"
            :class="{ 'tv-chip--active': sentimentFilter === 'negative' }"
            @click="sentimentFilter = sentimentFilter === 'negative' ? 'all' : 'negative'"
          >
            <span class="tv-chip__dot tv-chip__dot--green" />利空
          </button>
          <span class="tv-result-count">{{ filteredNews.length }} 条</span>
        </div>
      </section>
    </div>

    <div class="tv-content">
      <div v-if="loading && newsList.length === 0" class="tv-state">
        <div class="tv-spinner" />
        <p class="tv-state__text">加载中…</p>
      </div>

      <div v-else-if="error" class="tv-state tv-state--error">
        <p class="tv-state__title">抱歉，发生了一个错误</p>
        <p class="tv-state__detail">{{ error }}</p>
        <button type="button" class="tv-btn-reload" @click="refresh">重新载入</button>
      </div>

      <div v-else-if="filteredNews.length === 0" class="tv-state">
        <svg class="tv-state__icon" viewBox="0 0 24 24"><use href="#icon-news"/></svg>
        <p class="tv-state__title">暂无新闻</p>
        <p class="tv-state__hint">请尝试调整筛选或稍后刷新</p>
      </div>

      <div v-else class="tv-list">
        <article
          v-for="(item, idx) in filteredNews"
          :key="idx"
          class="tv-item"
          :class="'tv-item--' + item.sentiment"
          @click="openNews(item)"
        >
          <div class="tv-item__accent" :class="'tv-item__accent--' + item.sentiment" />
          <div class="tv-item__body">
            <div class="tv-item__meta">
              <span class="tv-item__source" :style="{ background: sourceColor(item.source) }">
                {{ item.source || '财经' }}
              </span>
              <time class="tv-item__time">{{ item.timeStr }}</time>
              <span v-if="item.sentiment !== 'neutral'" class="tv-item__tag" :data-sent="item.sentiment">
                {{ item.sentiment === 'positive' ? '利好' : '利空' }}
              </span>
            </div>
            <h3 class="tv-item__title">{{ item.title }}</h3>
            <p v-if="item.content && item.content !== item.title" class="tv-item__summary">{{ item.content }}</p>
          </div>
        </article>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { news } from '@/api/news.js'

const loading = ref(true)
const error = ref('')
const newsList = ref([])

/** 与时间维度独立：全部 | 今日 | 昨日 | 近7日 */
const timeFilter = ref('all')
/** 与来源维度独立：全部 | 财联社 | 新浪 | … */
const sourceFilter = ref('all')
const sentimentFilter = ref('all')

const SOURCE_COLORS = {
  新浪: '#E84D3D',
  同花顺: '#E87714',
  东财: '#3269C6',
  财联社: '#D63523',
  雪球: '#2E7D32',
  金十数据: '#C9A227',
  财经: '#787B86',
  akshare: '#2962FF',
}

const TIME_IDS = ['all', 'today', 'yesterday', 'week']
const TIME_LABELS = { all: '全部', today: '今日', yesterday: '昨日', week: '近7日' }

/** 与 news_fetcher 聚合源一致，固定展示（含财联社），不随当前列表变少 */
const FIXED_SOURCE_ORDER = [
  { id: '财联社', label: '财联社' },
  { id: '同花顺', label: '同花顺' },
  { id: '新浪', label: '新浪' },
  { id: '东财', label: '东财' },
  { id: '雪球', label: '雪球' },
  { id: '金十数据', label: '金十数据' },
]

function shanghaiCutoffs() {
  const now = new Date()
  const sh = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Shanghai' }))
  const todayStart = Math.floor(
    new Date(sh.getFullYear(), sh.getMonth(), sh.getDate()).getTime() / 1000
  )
  return {
    todayStart,
    yesterdayStart: todayStart - 86400,
    weekStart: todayStart - 7 * 86400,
  }
}

const timeTabs = computed(() =>
  TIME_IDS.map((id) => ({ id, label: TIME_LABELS[id] }))
)

const FIXED_SOURCE_IDS = new Set(FIXED_SOURCE_ORDER.map((x) => x.id))

const sourceTabs = computed(() => {
  const tabs = [{ id: 'all', label: '全部' }, ...FIXED_SOURCE_ORDER]
  const seen = new Set(FIXED_SOURCE_IDS)
  for (const item of newsList.value) {
    const src = item.source || ''
    if (src && !seen.has(src)) {
      seen.add(src)
      tabs.push({ id: src, label: src })
    }
  }
  return tabs
})

const filteredNews = computed(() => {
  const { todayStart, yesterdayStart, weekStart } = shanghaiCutoffs()
  return newsList.value.filter((n) => {
    const ts = n._ts || 0
    if (timeFilter.value === 'today' && ts < todayStart) return false
    if (timeFilter.value === 'yesterday' && (ts < yesterdayStart || ts >= todayStart)) return false
    if (timeFilter.value === 'week' && ts < weekStart) return false

    if (sourceFilter.value !== 'all' && (n.source || '') !== sourceFilter.value) return false

    if (sentimentFilter.value !== 'all' && n.sentiment !== sentimentFilter.value) return false
    return true
  })
})

function sourceColor(src) {
  return SOURCE_COLORS[src] || '#787B86'
}

const POSITIVE = [
  '国务院', '发改委', '工信部', '央行', '证监会', '财政部', '政策支持', '扶持',
  '补贴', '减税', '降费', '利好', '突破', '首发', '首创', '领先', '龙头',
  '订单', '中标', '签约', '合作', '战略协议', '业绩预增', '净利润增长',
  '涨价', '提价', '增持', '回购', '举牌', '外资买入', '机构调研',
]
const NEGATIVE = [
  '下跌', '暴跌', '大跌', '跳水', '减持', '清仓', '抛售', '套现',
  '亏损', '下滑', '下降', '业绩变脸', '处罚', '罚款', '违规', '调查', '立案',
  '退市', 'ST', '*ST', '风险警示', '诉讼', '仲裁', '纠纷', '崩盘',
]

function normalizeTs(raw) {
  if (raw == null || raw === '') return Math.floor(Date.now() / 1000)
  const n = Number(raw)
  if (!Number.isNaN(n) && n > 0) {
    if (n > 1e11) return Math.floor(n / 1000)  // 毫秒 → 秒
    if (n > 1e8)  return Math.floor(n)        // 秒（Unix 时间戳）
  }
  // 处理 '2026-03-25 15:43:00' 等字符串格式
  const s = String(raw).trim()
  const d = new Date(s.replace(/-/g, '/'))
  if (!Number.isNaN(d.getTime())) return Math.floor(d.getTime() / 1000)
  return Math.floor(Date.now() / 1000)
}

function parseTimestamp(ts) {
  if (!ts) return null
  const n = Number(ts)
  if (n > 1e11) return new Date(n)         // 毫秒级时间戳
  if (n > 1e6)  return new Date(n * 1000)   // 秒级时间戳（Unix 秒）
  return null
}

function formatTimeStr(ts) {
  const d = parseTimestamp(ts)
  if (!d) return '--'
  const diffMs = Date.now() - d.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin}分钟前`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}小时前`
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Shanghai',
  })
}

function calcSentiment(title) {
  if (!title) return 'neutral'
  const pos = POSITIVE.filter((k) => title.includes(k)).length
  const neg = NEGATIVE.filter((k) => title.includes(k)).length
  if (pos > neg) return 'positive'
  if (neg > pos) return 'negative'
  return 'neutral'
}

/** 与固定来源 Tab 对齐（东财个股新闻常带「东方财富」等） */
function normalizeSourceLabel(src) {
  const s = String(src || '').trim()
  if (!s) return '财经'
  if (s.includes('东方财富')) return '东财'
  return s
}

function enrich(raw) {
  const _ts = normalizeTs(raw.time)
  const source = normalizeSourceLabel(raw.source)
  return {
    ...raw,
    source,
    sentiment: calcSentiment(raw.title || ''),
    timeStr: formatTimeStr(_ts),
    _ts,
  }
}

function openNews(item) {
  if (item.url) window.open(item.url, '_blank')
}

const MEM_TTL = 60 * 1000
const memCache = { data: null, time: 0 }
function fromMem() {
  if (memCache.data && Date.now() - memCache.time < MEM_TTL) return memCache.data
  return null
}
function toMem(d) {
  memCache.data = d
  memCache.time = Date.now()
}

async function fetchNews(force = false) {
  if (!force) {
    const c = fromMem()
    if (c) return c
  }
  const data = await news.list(force)
  toMem(data)
  return data
}

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const raw = await fetchNews(true)
    newsList.value = (Array.isArray(raw) ? raw : []).map(enrich).filter((x) => x && x.title)
  } catch (e) {
    error.value = e.message || '请求超时或网络异常'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await refresh()
})
</script>

<style scoped>
/* TradingView 浅色参考：白底、细分割线、主色 #2962FF */
.tv-news {
  min-height: 100vh;
  background: var(--surface);
  padding-bottom: calc(env(safe-area-inset-bottom) + 8px);
}

.tv-header {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 16px;
  padding-top: calc(10px + env(safe-area-inset-top));
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--divider);
}
.tv-header__title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-1);
  letter-spacing: -0.3px;
}
.tv-header__refresh {
  position: absolute;
  right: 12px;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--text-3);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.tv-header__refresh:active {
  opacity: 0.85;
}
.tv-header__refresh-icon {
  width: 18px;
  height: 18px;
}
.tv-header__refresh--spin .tv-header__refresh-icon {
  animation: tv-spin 0.65s linear infinite;
}
@keyframes tv-spin {
  to {
    transform: rotate(360deg);
  }
}

.tv-filters {
  background: var(--surface);
  border-bottom: 1px solid var(--divider);
  padding-bottom: 10px;
}

.tv-filter-block {
  padding: 10px 16px 0;
}
.tv-filter-block__label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-3);
  margin-bottom: 8px;
}

.tv-pill-row {
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 2px;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}
.tv-pill-row::-webkit-scrollbar {
  display: none;
}

.tv-pill {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: none;
  border-radius: 100px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-1);
  background: var(--surface-2);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.tv-pill--primary.tv-pill--active {
  background: var(--brand);
  color: var(--surface);
}

.tv-filter-block--sentiment {
  padding-top: 12px;
  border-top: 1px solid var(--surface-2);
  margin-top: 6px;
}
.tv-sentiment-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.tv-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-3);
  background: var(--surface);
  border: 1px solid var(--divider);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}
.tv-chip--active {
  border-color: var(--text-1);
  color: var(--text-1);
  background: var(--surface);
}
.tv-chip--bull.tv-chip--active {
  border-color: var(--down);
  color: var(--down);
}
.tv-chip--bear.tv-chip--active {
  border-color: var(--up);
  color: var(--up);
}
.tv-chip__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.tv-chip__dot--red {
  background: var(--down);
}
.tv-chip__dot--green {
  background: var(--up);
}
.tv-result-count {
  margin-left: auto;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-3);
  font-variant-numeric: tabular-nums;
}

.tv-content {
  background: var(--surface);
}

.tv-state {
  text-align: center;
  padding: 72px 24px 48px;
}
.tv-state__title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-1);
  margin-bottom: 8px;
}
.tv-state__text,
.tv-state__hint,
.tv-state__detail {
  font-size: 14px;
  color: var(--text-3);
  line-height: 1.5;
}
.tv-state__detail {
  margin-top: 6px;
  max-width: 280px;
  margin-left: auto;
  margin-right: auto;
}
.tv-state__icon {
  width: 48px;
  height: 48px;
  fill: var(--text-4);
  margin: 0 auto 16px;
  display: block;
}
.tv-state--error .tv-state__title {
  margin-bottom: 4px;
}

.tv-btn-reload {
  margin-top: 20px;
  padding: 12px 32px;
  font-size: 15px;
  font-weight: 600;
  color: var(--surface);
  background: var(--text-1);
  border: none;
  border-radius: 8px;
  cursor: pointer;
}
.tv-btn-reload:active {
  opacity: 0.9;
}

.tv-spinner {
  width: 32px;
  height: 32px;
  margin: 0 auto 12px;
  border: 3px solid var(--divider);
  border-top-color: var(--brand);
  border-radius: 50%;
  animation: tv-spin 0.7s linear infinite;
}

.tv-list {
  border-top: 1px solid var(--divider);
}
.tv-item {
  display: flex;
  border-bottom: 1px solid var(--surface-2);
  cursor: pointer;
}
.tv-item:active {
  background: var(--surface-2);
}
.tv-item__accent {
  width: 3px;
  flex-shrink: 0;
  align-self: stretch;
  background: transparent;
}
.tv-item__accent--positive {
  background: var(--down);
}
.tv-item__accent--negative {
  background: var(--up);
}
.tv-item__body {
  flex: 1;
  min-width: 0;
  padding: 14px 16px 14px 12px;
}
.tv-item__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 6px;
}
.tv-item__source {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  color: var(--surface);
}
.tv-item__time {
  font-size: 12px;
  color: var(--text-3);
}
.tv-item__tag {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
}
.tv-item__tag[data-sent='positive'] {
  background: rgba(242, 54, 69, 0.1);
  color: var(--down);
}
.tv-item__tag[data-sent='negative'] {
  background: rgba(8, 153, 129, 0.1);
  color: var(--up);
}
.tv-item__title {
  font-size: 15px;
  font-weight: 500;
  line-height: 1.45;
  color: var(--text-1);
  word-break: break-word;
}
.tv-item--positive .tv-item__title {
  color: var(--text-1);
}
.tv-item__summary {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.45;
  color: var(--text-3);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
