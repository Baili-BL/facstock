<template>
  <div class="news-page">
    <!-- 顶部导航 -->
    <nav class="navbar">
      <div class="nav-title">财经快讯</div>
      <button class="refresh-btn" @click="refresh" :class="{ spinning: loading }">
        <svg class="icon" viewBox="0 0 24 24"><use href="#icon-refresh"/></svg>
      </button>
    </nav>

    <!-- 平台 Tab 栏 -->
    <div class="platform-tabs">
      <div
        v-for="tab in tabs"
        :key="tab.id"
        class="platform-tab"
        :class="{ active: activeTab === tab.id }"
        @click="switchTab(tab.id)"
      >
        <span class="tab-dot" :style="{ background: tab.color }" v-if="tab.id !== 'all'"></span>
        {{ tab.label }}
        <span class="tab-count">{{ tab.count }}</span>
      </div>
    </div>

    <div class="container">
      <!-- 加载中 -->
      <div v-if="loading && newsList.length === 0" class="loading">
        <div class="spinner"></div>
        <div>加载新闻中...</div>
      </div>

      <!-- 错误 -->
      <div v-else-if="error" class="error">
        <div class="error-icon">⚠️</div>
        <div>{{ error }}</div>
        <button class="retry-btn" @click="refresh">重试</button>
      </div>

      <!-- 空状态 -->
      <div v-else-if="displayNews.length === 0" class="empty">
        <svg class="icon empty-icon" style="fill:var(--apple-gray3)"><use href="#icon-news"/></svg>
        <div>暂无新闻</div>
        <div class="empty-hint">下拉刷新获取最新资讯</div>
      </div>

      <!-- 按日期分组 -->
      <div v-else class="news-groups">
        <div v-for="group in groupedNews" :key="group.date" class="news-group">
          <div class="date-label" :class="group.dateClass">{{ group.dateLabel }}</div>
          <div class="news-list">
            <a
              v-for="(item, idx) in group.items"
              :key="idx"
              class="news-item"
              :class="'sentiment-' + item.sentiment"
              :href="item.url || '#'"
              target="_blank"
              rel="noopener"
            >
              <div class="news-meta">
                <span class="news-source" :style="{ background: item.sourceColor }">
                  {{ item.source }}
                </span>
                <span class="news-time">{{ item.timeStr }}</span>
              </div>
              <div class="news-title">{{ item.title }}</div>
              <div class="news-content" v-if="item.content && item.content !== item.title">
                {{ item.content }}
              </div>
            </a>
          </div>
        </div>
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
const activeTab = ref('all')

// 3天截止时间戳（秒）
const THREE_DAYS_AGO = Math.floor(Date.now() / 1000) - 3 * 24 * 60 * 60

const SOURCE_COLORS = {
  '新浪': '#E84D3D',
  '同花顺': '#E87714',
  '东财': '#3269C6',
  '财联社': '#D63523',
  '雪球': '#2E7D32',
}

const PLATFORM_META = [
  { id: 'all',     label: '全部',   color: '#888' },
  { id: '新浪',   label: '新浪',   color: SOURCE_COLORS['新浪'] },
  { id: '同花顺', label: '同花顺', color: SOURCE_COLORS['同花顺'] },
  { id: '东财',   label: '东财',   color: SOURCE_COLORS['东财'] },
  { id: '财联社', label: '财联社', color: SOURCE_COLORS['财联社'] },
  { id: '雪球',   label: '雪球',   color: SOURCE_COLORS['雪球'] },
]

// Tab列表（含各平台计数）
const tabs = computed(() => {
  const counts = { all: filteredNews.value.length }
  for (const item of filteredNews.value) {
    const src = item.source || ''
    counts[src] = (counts[src] || 0) + 1
  }
  return PLATFORM_META.map(t => ({ ...t, count: counts[t.id] || 0 }))
})

// 平台过滤后的新闻
const filteredNews = computed(() => {
  if (activeTab.value === 'all') return newsList.value
  return newsList.value.filter(n => (n.source || '') === activeTab.value)
})

// 展示用新闻（含排序）
const displayNews = computed(() =>
  [...filteredNews.value].sort((a, b) => (b._ts || 0) - (a._ts || 0))
)

function switchTab(id) {
  activeTab.value = id
}

// 情绪关键词
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

function parseTimestamp(ts) {
  if (!ts) return null
  const n = Number(ts)
  if (n > 1e12) return new Date(n)
  if (n > 1e9)  return new Date(n * 1000)
  if (n > 1e6)  return new Date(n * 1000)
  if (n > 1e3)  return new Date(n * 1000)
  return null
}

function formatTimeStr(ts) {
  const d = parseTimestamp(ts)
  if (!d) return '--'
  const now = new Date()
  const diffMs = now - d
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin}分钟前`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}小时前`
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    timeZone: 'Asia/Shanghai'
  })
}

function calcSentiment(title) {
  if (!title) return 'neutral'
  const pos = POSITIVE.filter(k => title.includes(k)).length
  const neg = NEGATIVE.filter(k => title.includes(k)).length
  if (pos > neg) return 'positive'
  if (neg > pos) return 'negative'
  return 'neutral'
}

function dateLabel(dateStr) {
  const today     = new Date().toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' })
  const yesterday = new Date(Date.now() - 86400000).toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' })
  const dayBefore = new Date(Date.now() - 2 * 86400000).toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' })
  if (dateStr === today)     return '今日'
  if (dateStr === yesterday) return '昨日'
  if (dateStr === dayBefore)  return '前日'
  return dateStr
}

function enrich(raw) {
  const ts = Number(raw.time)
  if (ts > 1 && ts < THREE_DAYS_AGO) return null
  return {
    ...raw,
    sentiment: calcSentiment(raw.title || ''),
    timeStr: formatTimeStr(raw.time),
    sourceColor: SOURCE_COLORS[raw.source] || '#888',
    _ts: ts,
  }
}

const groupedNews = computed(() => {
  const groups = {}
  for (const item of displayNews.value) {
    const d = parseTimestamp(item.time)
    if (!d) continue
    const key = d.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' })
    if (!groups[key]) groups[key] = []
    groups[key].push(item)
  }
  return Object.keys(groups)
    .sort((a, b) => new Date(b) - new Date(a))
    .slice(0, 3)
    .map(date => ({
      date,
      dateLabel: dateLabel(date),
      dateClass: dateLabel(date) === '今日' ? 'today'
               : dateLabel(date) === '昨日' ? 'yesterday' : '',
      items: groups[date],
    }))
})

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const raw = await news.list()
    newsList.value = (Array.isArray(raw) ? raw : []).map(enrich).filter(Boolean)
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => refresh())
</script>

<style scoped>
.news-page { padding-bottom: 0; }

.navbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(255,255,255,0.98);
  backdrop-filter: saturate(180%) blur(20px);
  padding: 10px 16px;
  padding-top: calc(10px + env(safe-area-inset-top));
  display: flex; align-items: center;
  border-bottom: 0.5px solid var(--apple-gray5);
}
.nav-title { font-size: 17px; font-weight: 700; flex: 1; text-align: center; }

.refresh-btn {
  width: 36px; height: 36px; border-radius: 50%;
  background: var(--apple-gray6); border: none;
  display: flex; align-items: center; justify-content: center; cursor: pointer;
}
.refresh-btn .icon { width: 18px; height: 18px; fill: var(--apple-gray2); }
.refresh-btn.spinning .icon { animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 平台 Tab 栏 */
.platform-tabs {
  display: flex; gap: 4px; padding: 10px 16px 0;
  overflow-x: auto; scrollbar-width: none; -webkit-overflow-scrolling: touch;
}
.platform-tabs::-webkit-scrollbar { display: none; }

.platform-tab {
  flex-shrink: 0; display: flex; align-items: center; gap: 5px;
  padding: 7px 14px; border-radius: 20px; font-size: 14px; font-weight: 600;
  color: var(--apple-text3); background: var(--apple-gray6);
  cursor: pointer; white-space: nowrap; user-select: none;
  transition: all 0.2s;
}
.platform-tab.active {
  color: #fff; background: var(--apple-text1);
}
.platform-tab:not(.active):active { background: var(--apple-gray5); }

.tab-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
}
.platform-tab.active .tab-dot { background: #fff !important; }

.tab-count {
  font-size: 11px; font-weight: 400; opacity: 0.7;
}

.container { padding: 12px 16px 24px; }

.loading { text-align: center; padding: 80px 20px; color: var(--apple-gray); }
.spinner {
  width: 32px; height: 32px;
  border: 3px solid var(--apple-gray5); border-top-color: var(--apple-blue);
  border-radius: 50%; animation: spin 0.7s linear infinite;
  margin: 0 auto 14px;
}

.error { text-align: center; padding: 60px 20px; }
.error-icon { font-size: 48px; margin-bottom: 16px; }
.retry-btn {
  background: var(--apple-blue); color: #fff; border: none;
  padding: 10px 24px; border-radius: 20px; font-size: 15px;
  font-weight: 600; cursor: pointer; margin-top: 16px;
}

.empty { text-align: center; padding: 60px 20px; color: var(--apple-gray); }
.empty-icon { width: 48px; height: 48px; margin: 0 auto 16px; display: block; }
.empty-hint { font-size: 14px; margin-top: 8px; color: var(--apple-gray2); }

.news-groups { display: flex; flex-direction: column; gap: 20px; }

.news-group { display: flex; flex-direction: column; }

.date-label {
  font-size: 13px; font-weight: 700;
  padding: 6px 0 8px; margin-bottom: 4px;
  border-bottom: 1.5px solid var(--apple-gray5);
}
.date-label.today { color: var(--apple-red); border-color: var(--apple-red); }
.date-label.yesterday { color: var(--apple-orange); }

.news-list { display: flex; flex-direction: column; }

.news-item {
  display: flex; flex-direction: column; gap: 5px;
  padding: 12px 0;
  border-bottom: 0.5px solid var(--apple-gray6);
  text-decoration: none; color: inherit;
  cursor: pointer; transition: background 0.15s;
}
.news-item:last-child { border-bottom: none; }
.news-item:active {
  background: var(--apple-gray6); border-radius: 8px;
  padding-left: 6px; padding-right: 6px; margin: 0 -6px;
}

.news-meta { display: flex; align-items: center; gap: 8px; }
.news-source {
  font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 8px; color: #fff;
}
.news-time { font-size: 12px; color: var(--apple-text3); }

.news-title {
  font-size: 15px; line-height: 1.5; word-break: break-all;
}
.sentiment-positive .news-title { color: var(--apple-red); }
.sentiment-negative .news-title { color: var(--apple-green); }
.sentiment-neutral .news-title   { color: var(--apple-text1); }

.news-content {
  font-size: 13px; line-height: 1.5; color: var(--apple-text3);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
