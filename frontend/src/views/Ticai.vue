<template>
  <div class="ticai-page">
    <!-- 顶部导航 -->
    <nav class="navbar">
      <div class="nav-back" @click="$router.push('/strategy')">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </div>
      <div class="nav-close" @click="$router.push('/strategy')">
        <svg class="icon" viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
      </div>
      <div class="nav-title">题材挖掘</div>
      <div class="nav-more" @click="refreshForce" :class="{ spinning: loading }">
        <svg class="icon" viewBox="0 0 24 24"><path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2z"/></svg>
      </div>
    </nav>

    <!-- 次标题：火焰 + 题材挖掘 -->
    <div class="sub-header">
      <svg class="icon icon-fire" style="fill:#FF3B30"><use href="#icon-fire"/></svg>
      <span class="sub-title">题材挖掘</span>
    </div>

    <!-- 今日热点 + 数量 + 刷新 -->
    <div class="hot-section-header">
      <span class="hot-title">今日热点</span>
      <span class="hot-count">{{ themes.length }}个</span>
      <button class="refresh-btn red" @click="refreshForce" :disabled="loading">
        {{ loading ? '加载中' : '刷新' }}
      </button>
    </div>

    <div class="container">
      <!-- 加载状态 -->
      <div v-if="loading && themes.length === 0" class="loading">
        <div class="spinner"></div>
        <div>加载热点题材中...</div>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="error" class="error">
        <div class="error-icon">⚠️</div>
        <div>{{ error }}</div>
        <button class="retry-btn" @click="refreshForce">重试</button>
      </div>

      <!-- 空状态 -->
      <div v-else-if="themes.length === 0" class="empty">
        <div class="empty-icon">📊</div>
        <div>暂无热点题材</div>
      </div>

      <!-- 题材卡片列表 -->
      <div v-else class="theme-list">
        <div v-for="theme in themes" :key="theme.name" class="theme-card">
          <!-- 卡片头部：火焰+题材名，徽章，涨跌幅 -->
          <div class="theme-header">
            <div class="theme-info">
              <span class="theme-name">
                <svg class="icon" style="fill:var(--apple-orange)"><use href="#icon-fire"/></svg>
                {{ theme.name }}
              </span>
              <div class="theme-badges">
                <span v-if="theme.emotion?.stage" class="badge badge-emotion" :style="{ color: theme.emotion.color }">
                  {{ theme.emotion.stage }}
                </span>
                <span v-for="t in (theme.quality?.tags || [])" :key="t.name" class="badge badge-quality" :style="{ color: t.color }">
                  {{ t.name }}
                </span>
              </div>
            </div>
            <div class="theme-change" :class="(theme.info?.change_pct || 0) >= 0 ? 'up' : 'down'">
              {{ (theme.info?.change_pct || 0) >= 0 ? '+' : '' }}{{ (theme.info?.change_pct || 0).toFixed(2) }}%
            </div>
          </div>

          <!-- 统计行：热度、涨、跌 -->
          <div class="theme-stats">
            <span class="stat-item">热度 {{ Math.round(theme.hot_score || 0) }}</span>
            <span class="stat-item">涨 {{ theme.info?.up_count || 0 }}</span>
            <span class="stat-item">跌 {{ theme.info?.down_count || 0 }}</span>
          </div>

          <!-- 成分股列表 -->
          <div class="stock-list">
            <div v-if="theme.stocks && theme.stocks.length > 0">
              <div
                v-for="(stock, idx) in theme.stocks"
                :key="stock.code"
                class="stock-item"
                @click="showStockDetail(stock, theme.name)"
              >
                <div class="stock-left">
                  <span class="stock-rank" :class="'rank-' + (idx + 1)">{{ idx + 1 }}</span>
                  <span v-if="stock.role" class="stock-role" :class="'role-' + stock.role">{{ stock.role }}</span>
                  <div class="stock-name-wrap">
                    <span class="stock-name">{{ stock.name }}</span>
                    <span class="stock-code">{{ stock.code }}</span>
                  </div>
                  <div class="stock-tags">
                    <span v-if="stock.is_first_limit || stock.is_limit_up" class="stock-tag">首板</span>
                    <span v-if="stock.is_weak_to_strong" class="stock-tag">弱转强</span>
                    <span v-if="stock.volume_level === '地量'" class="stock-tag">地量</span>
                  </div>
                </div>
                <div class="stock-right">
                  <span class="stock-change" :class="(stock.change_pct_num ?? 0) >= 0 ? 'up' : 'down'">
                    {{ formatStockChange(stock) }}
                  </span>
                  <span v-if="stock.price" class="stock-price">¥{{ String(stock.price) }}</span>
                  <span v-if="stock.score" class="stock-score">{{ stock.score }}分</span>
                </div>
              </div>
            </div>
            <div v-else class="no-stocks">暂无成分股数据</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 股票详情弹窗（与布林带类似） -->
    <div class="detail-modal" :class="{ active: stockModalVisible }" @click.self="closeDetail">
      <div class="detail-panel">
        <div class="detail-header">
          <button class="close-btn" @click="closeDetail">
            <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
          </button>
          <span class="detail-title">
            <svg class="icon" style="fill:var(--apple-orange)"><use href="#icon-fire"/></svg>
            {{ selectedStock?.name || '' }}
          </span>
          <button
            class="detail-star-btn"
            :class="{ active: stockStarred }"
            @click="toggleStockStar"
            :title="stockStarred ? '取消自选' : '加自选'"
          >
            <svg class="icon" viewBox="0 0 24 24">
              <use :href="stockStarred ? '#icon-star' : '#icon-star-outline'"/>
            </svg>
          </button>
        </div>
        <div class="detail-content" v-if="selectedStock">
          <!-- 基础行情 -->
          <div class="detail-price-card">
            <div class="detail-price-main">
              <span class="detail-price">¥{{ fmtPrice(selectedStock) }}</span>
              <span class="detail-pct" :class="fmtPct(selectedStock).cls">{{ fmtPct(selectedStock).text }}</span>
            </div>
            <div class="detail-meta-row">
              <span class="detail-meta-item">{{ selectedStock.code }}</span>
              <span v-if="selectedThemeName" class="detail-meta-item">{{ selectedThemeName }}</span>
            </div>
          </div>

          <!-- K线图 -->
          <div class="detail-kline-card">
            <div class="detail-section-label detail-kline-heading">K线走势</div>
            <KlineChart v-if="selectedStock?.code" :code="selectedStock.code" />
          </div>

          <!-- 评分 -->
          <div v-if="selectedStock.score" class="detail-score-card">
            <div class="detail-score-left">
              <div class="detail-score-label">题材评分</div>
              <div class="detail-score-val">
                <span class="detail-score-num">{{ selectedStock.score }}分</span>
                <span v-if="selectedStock.role" class="detail-grade-badge grade-role">{{ selectedStock.role }}</span>
              </div>
            </div>
          </div>

          <!-- 特征标签 -->
          <div class="detail-tags-card" v-if="getStockTags(selectedStock).length">
            <div class="detail-section-label">特征标签</div>
            <div class="detail-tags">
              <span
                v-for="tag in getStockTags(selectedStock)"
                :key="tag"
                class="pill-tag pill-default"
              >{{ tag }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ticai } from '@/api/ticai.js'
import { watchlist } from '@/api/strategy.js'
import KlineChart from '@/components/KlineChart.vue'

const loading = ref(true)
const error = ref('')
const themes = ref([])
const selectedStock = ref(null)
const selectedThemeName = ref('')
const stockModalVisible = ref(false)
const stockStarred = ref(false)
let refreshTimer = null
let inFlight = false

/** force=false：TTL 内且同日缓存命中则不请求；force=true：始终请求（刷新/重试） */
async function refresh({ force = false } = {}) {
  if (inFlight) return
  inFlight = true
  const showFullLoading = force || themes.value.length === 0
  if (showFullLoading) loading.value = true
  error.value = ''
  try {
    const result = await ticai.all({ force })
    themes.value = Object.entries(result.data || {}).map(([name, info]) => ({ name, ...info }))
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
    inFlight = false
  }
}

function refreshForce() {
  return refresh({ force: true })
}

function formatStockChange(stock) {
  const num = stock.change_pct_num ?? 0
  const str = stock.change_pct
  if (str) return str
  return (num >= 0 ? '+' : '') + Number(num).toFixed(2) + '%'
}

function fmtPrice(s) {
  const p = s.price
  if (p == null || p === '') return '--'
  const n = Number(p)
  return Number.isFinite(n) ? n.toFixed(2) : String(p)
}

function fmtPct(s) {
  const n = Number(s.change_pct_num)
  if (Number.isFinite(n)) {
    return { text: (n >= 0 ? '+' : '') + n.toFixed(2) + '%', cls: n >= 0 ? 'up' : 'down' }
  }
  const str = String(s.change_pct || '')
  const isUp = str.startsWith('+') || (!str.startsWith('-') && str !== '--')
  return { text: str || '--', cls: isUp ? 'up' : 'down' }
}

function getStockTags(s) {
  const tags = []
  if (s.role) tags.push(s.role)
  if (s.is_first_limit || s.is_limit_up) tags.push('首板')
  if (s.is_weak_to_strong) tags.push('弱转强')
  if (s.volume_level === '地量') tags.push('地量')
  return tags
}

async function showStockDetail(stock, themeName) {
  if (!stock?.code) return
  selectedStock.value = stock
  selectedThemeName.value = themeName || ''
  stockModalVisible.value = true
  document.body.style.overflow = 'hidden'
  // 检查是否已自选
  try {
    const { in_watchlist } = await watchlist.check(stock.code)
    stockStarred.value = !!in_watchlist
  } catch {
    stockStarred.value = false
  }
}

async function toggleStockStar() {
  if (!selectedStock.value?.code) return
  const { code, name } = selectedStock.value
  try {
    if (stockStarred.value) {
      await watchlist.remove(code)
      stockStarred.value = false
    } else {
      await watchlist.add(code, name)
      stockStarred.value = true
    }
  } catch (e) {
    error.value = e.message || '操作失败'
  }
}

function closeDetail() {
  stockModalVisible.value = false
  document.body.style.overflow = ''
}

function startAutoRefresh() {
  refreshTimer = setInterval(() => refresh({ force: false }), 60000)
}

onMounted(() => {
  refresh()
  startAutoRefresh()
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.ticai-page { padding-bottom: 0; }

.navbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(255,255,255,0.98);
  backdrop-filter: saturate(180%) blur(20px);
  padding: 10px 16px;
  padding-top: calc(10px + env(safe-area-inset-top));
  display: flex; align-items: center; gap: 12px;
}
.nav-back, .nav-close {
  width: 30px; height: 30px; border-radius: 8px;
  background: var(--apple-gray6); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.nav-back .icon, .nav-close .icon { fill: var(--apple-text2); }
.nav-title { font-size: 17px; font-weight: 600; flex: 1; text-align: center; }
.nav-more {
  width: 30px; height: 30px; border-radius: 8px;
  background: var(--apple-gray6); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.nav-more .icon { fill: var(--apple-text2); }
.spinning { opacity: 0.6; }

.sub-header {
  padding: 10px 16px 8px;
  display: flex; align-items: center; gap: 8px;
  border-bottom: 0.5px solid var(--apple-gray5);
}
.sub-header .icon-fire { width: 20px; height: 20px; }
.sub-title { font-size: 15px; font-weight: 600; color: #FF3B30; }

.hot-section-header {
  padding: 12px 16px;
  display: flex; align-items: center; gap: 12px;
}
.hot-title { font-size: 16px; font-weight: 600; }
.hot-count { font-size: 14px; color: var(--apple-text3); }
.refresh-btn { margin-left: auto; padding: 6px 14px; border-radius: 16px; font-size: 14px; font-weight: 600; cursor: pointer; border: none; background: var(--apple-gray6); color: var(--apple-text2); }
.refresh-btn.red { background: #FF3B30; color: #fff; }
.refresh-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.container { padding: 0 16px 24px; }

.loading { text-align: center; padding: 80px 20px; color: var(--apple-gray); }
.spinner { width: 32px; height: 32px; border: 3px solid var(--apple-gray5); border-top-color: var(--apple-blue); border-radius: 50%; animation: spin 0.7s linear infinite; margin: 0 auto 14px; }
@keyframes spin { to { transform: rotate(360deg); } }

.error { text-align: center; padding: 60px 20px; }
.error-icon { font-size: 48px; margin-bottom: 16px; }
.retry-btn { background: var(--apple-blue); color: #fff; border: none; padding: 10px 24px; border-radius: 20px; font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 16px; }

.empty { text-align: center; padding: 80px 20px; color: var(--apple-gray); }
.empty-icon { font-size: 48px; margin-bottom: 16px; }

.theme-list { display: flex; flex-direction: column; gap: 14px; }

.theme-card {
  background: var(--apple-card);
  border-radius: 16px; overflow: hidden;
  box-shadow: 0 2px 12px rgba(0,0,0,0.05);
}

.theme-header {
  padding: 14px 16px;
  display: flex; justify-content: space-between; align-items: flex-start;
  border-bottom: 0.5px solid var(--apple-gray5);
}
.theme-info { flex: 1; }
.theme-name { font-size: 16px; font-weight: 700; display: flex; align-items: center; gap: 6px; }
.theme-badges { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 6px; }
.badge-emotion { background: #FFF3E0; }
.badge-quality { background: #E3F2FD; }
.theme-change { font-size: 18px; font-weight: 700; flex-shrink: 0; }

.theme-stats {
  padding: 8px 16px; display: flex; gap: 16px;
  font-size: 13px; color: var(--apple-text3);
  border-bottom: 0.5px solid var(--apple-gray5);
}
.stat-item { font-weight: 500; }

.stock-list { padding: 0; }
.stock-item {
  padding: 12px 16px;
  border-bottom: 0.5px solid var(--apple-gray5);
  display: flex; justify-content: space-between; align-items: center;
  cursor: pointer;
  transition: background 0.15s;
}
.stock-item:last-child { border-bottom: none; }
.stock-item:active { background: var(--apple-gray6); }

.stock-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.stock-rank {
  width: 22px; height: 22px; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; color: #fff; flex-shrink: 0;
}
.rank-1 { background: var(--apple-red); }
.rank-2 { background: var(--apple-orange); }
.rank-3 { background: var(--apple-purple); }
.rank-4, .rank-5 { background: var(--apple-gray); }

.stock-role { font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; flex-shrink: 0; }
.role-龙头 { background: #FF3B30; color: #fff; }
.role-中军 { background: #007AFF; color: #fff; }
.role-低吸, .role-跟风 { background: var(--apple-gray); color: #fff; }

.stock-name-wrap { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.stock-name { font-size: 15px; font-weight: 600; }
.stock-code { font-size: 12px; color: var(--apple-text3); }

.stock-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.stock-tag { font-size: 10px; color: var(--apple-text3); padding: 2px 6px; border-radius: 4px; background: var(--apple-gray6); }

.stock-right { text-align: right; display: flex; flex-direction: column; align-items: flex-end; gap: 2px; flex-shrink: 0; }
.stock-change { font-size: 15px; font-weight: 700; }
.stock-price { font-size: 12px; color: var(--apple-text3); }
.stock-score { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 8px; background: rgba(255,59,48,0.12); color: var(--apple-red); }

.no-stocks { padding: 24px; text-align: center; color: var(--apple-gray); font-size: 14px; }

.up { color: var(--apple-red) !important; }
.down { color: var(--apple-green) !important; }

/* 股票详情弹窗（与布林带一致） */
.detail-modal { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); z-index: 200; }
.detail-modal.active { display: block; }
.detail-panel {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  background: var(--apple-bg);
  animation: slideIn 0.35s cubic-bezier(0.32, 0.72, 0, 1);
  display: flex; flex-direction: column; overflow: hidden;
}
@keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
.detail-header {
  background: rgba(255,255,255,0.78); backdrop-filter: saturate(180%) blur(20px);
  padding: 12px 16px; padding-top: calc(12px + env(safe-area-inset-top));
  display: flex; align-items: center; gap: 12px;
  border-bottom: 0.5px solid var(--apple-gray5); flex-shrink: 0;
}
.close-btn {
  width: 32px; height: 32px; background: var(--apple-gray6); border-radius: 50%;
  border: none; display: flex; align-items: center; justify-content: center; cursor: pointer;
}
.detail-title { flex: 1; font-size: 17px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
.detail-title .icon { fill: var(--apple-orange); }
.detail-star-btn {
  width: 36px; height: 36px; background: var(--apple-gray6); border-radius: 50%;
  border: none; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0;
}
.detail-star-btn .icon { width: 18px; height: 18px; fill: var(--apple-gray2); }
.detail-star-btn.active .icon { fill: #FF9500; }
.detail-content { flex: 1; overflow-y: auto; padding: 16px; }

.detail-price-card {
  background: var(--apple-card); border-radius: 16px; padding: 18px;
  margin-bottom: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.detail-price-main { display: flex; align-items: baseline; gap: 12px; margin-bottom: 8px; }
.detail-price { font-size: 36px; font-weight: 800; }
.detail-pct { font-size: 20px; font-weight: 700; }
.detail-meta-row { display: flex; gap: 12px; flex-wrap: wrap; }
.detail-meta-item { font-size: 13px; color: var(--apple-text3); }

.detail-kline-card { margin-bottom: 12px; }
.detail-kline-heading { margin-bottom: 6px; font-size: 12px; color: var(--apple-text3); font-weight: 600; }

.detail-score-card {
  background: var(--apple-card); border-radius: 16px; padding: 16px 18px;
  margin-bottom: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.detail-score-left { flex: 1; }
.detail-score-label { font-size: 12px; color: var(--apple-text3); margin-bottom: 4px; }
.detail-score-val { display: flex; align-items: baseline; gap: 8px; }
.detail-score-num { font-size: 28px; font-weight: 800; }
.detail-grade-badge { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 8px; }
.detail-grade-badge.grade-role { background: var(--apple-blue); color: #fff; }

.detail-tags-card {
  background: var(--apple-card); border-radius: 16px; padding: 14px 18px;
  margin-bottom: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.detail-section-label { font-size: 12px; color: var(--apple-text3); font-weight: 600; margin-bottom: 10px; }
.detail-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.pill-tag { font-size: 12px; padding: 4px 10px; border-radius: 8px; background: var(--apple-gray6); color: var(--apple-text2); }
</style>
