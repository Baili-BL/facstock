<template>
  <div class="ticai-page">
    <!-- 顶部导航 -->
    <nav class="navbar">
      <div class="nav-icon" @click="$router.push('/strategy')">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </div>
      <div class="nav-icon" @click="$router.push('/strategy')">
        <svg class="icon" viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
      </div>
      <div class="nav-title">题材挖掘</div>
      <button type="button" class="nav-refresh" @click="refreshForce" :disabled="loading" :class="{ spinning: loading }">
        <svg class="icon" viewBox="0 0 24 24"><path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
      </button>
    </nav>

    <!-- 题材概览条 -->
    <div class="hot-header">
      <svg class="hot-header__fire"><use href="#icon-fire"/></svg>
      <span class="hot-header__title">题材挖掘</span>
      <span class="hot-header__count tabular">{{ themes.length }}个</span>
      <button type="button" class="btn-primary btn-primary--grad" @click="refreshForce" :disabled="loading">
        {{ loading ? '加载中' : '刷新' }}
      </button>
    </div>

    <div class="container">
      <!-- 加载 -->
      <div v-if="loading && themes.length === 0" class="state">
        <div class="spinner" />
        <p>加载热点题材中...</p>
      </div>

      <!-- 错误 -->
      <div v-else-if="error" class="state state--err">
        <div class="state__icon">⚠️</div>
        <p>{{ error }}</p>
        <button type="button" class="btn-primary btn-primary--grad" @click="refreshForce">重试</button>
      </div>

      <!-- 空 -->
      <div v-else-if="themes.length === 0" class="state">
        <div class="state__icon">📊</div>
        <p>暂无热点题材</p>
      </div>

      <!-- 题材卡片列表 -->
      <div v-else class="theme-list">
        <div v-for="theme in themes" :key="theme.name" class="theme-card">

          <!-- 卡片头部 -->
          <div class="theme-head">
            <div class="theme-head__left">
              <div class="theme-head__name">
                <svg class="theme-head__fire"><use href="#icon-fire"/></svg>
                {{ theme.name }}
              </div>
              <div class="theme-head__badges">
                <span
                  v-if="theme.emotion?.stage"
                  class="badge badge-emotion"
                  :style="{ color: theme.emotion.color }"
                >{{ theme.emotion.stage }}</span>
                <span
                  v-for="t in (theme.quality?.tags || [])"
                  :key="t.name"
                  class="badge badge-quality"
                  :style="{ color: t.color }"
                >{{ t.name }}</span>
              </div>
            </div>
            <div class="theme-head__change tabular" :class="themeChangeDir(theme)">
              {{ themeChangeText(theme) }}
            </div>
          </div>

          <!-- 题材统计条 -->
          <div class="theme-stats">
            <span class="stat">热度 <em class="tabular">{{ Math.round(theme.hot_score || 0) }}</em></span>
            <span class="stat stat--up">涨 <em class="tabular">{{ theme.info?.up_count || 0 }}</em></span>
            <span class="stat stat--down">跌 <em class="tabular">{{ theme.info?.down_count || 0 }}</em></span>
          </div>

          <!-- 成分股表格 -->
          <div class="stock-table">
            <div class="stock-table__head">
              <span>股票</span>
              <span class="tar">涨跌幅</span>
            </div>
            <div
              v-for="(stock, idx) in (theme.stocks || [])"
              :key="stock.code"
              class="stock-row"
              @click="showStockDetail(stock, theme.name)"
            >
              <div class="stock-row__main">
                <div class="stock-row__rank">
                  <span class="rank-num" :class="'rank-' + Math.min(idx + 1, 5)">{{ idx + 1 }}</span>
                  <span v-if="stock.role" class="role-tag" :class="'role-' + stock.role">{{ stock.role }}</span>
                </div>
                <div class="stock-row__info">
                  <div class="stock-row__nm">{{ stock.name }}<span class="stock-row__cd tabular">{{ stock.code }}</span></div>
                </div>
              </div>
              <div class="stock-row__right">
                <div class="stock-row__chg tabular" :class="stockDir(stock)">
                  {{ stockChangeText(stock) }}
                </div>
                <div v-if="stock.price" class="stock-row__price tabular">¥{{ stock.price }}</div>
                <div v-if="stock.score" class="stock-row__score">{{ stock.score }}分</div>
              </div>
              <!-- 特征标签单独一行，贴在 stock-row 底部 -->
              <div v-if="hasFeatureTags(stock)" class="stock-row__feat">
                <span v-if="stock.is_first_limit || stock.is_limit_up" class="feat-tag feat-tag--red">首板</span>
                <span v-if="stock.is_weak_to_strong" class="feat-tag feat-tag--blue">弱转强</span>
                <span v-if="stock.volume_level === '地量'" class="feat-tag feat-tag--gray">地量</span>
              </div>
            </div>
            <div v-if="!theme.stocks?.length" class="stock-empty">暂无成分股数据</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 股票详情弹窗 -->
    <div class="detail-modal" :class="{ active: stockModalVisible }" @click.self="closeDetail">
      <div class="detail-panel">
        <div class="detail-header">
          <button type="button" class="detail-icon-btn" @click="closeDetail">
            <svg viewBox="0 0 24 24" width="22" height="22"><path fill="currentColor" d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
          </button>
          <span class="detail-title">
            <svg class="detail-title__fire"><use href="#icon-fire"/></svg>
            {{ selectedStock?.name || '' }}
          </span>
          <button type="button" class="detail-star-btn" :class="{ on: stockStarred }" :title="stockStarred ? '取消自选' : '加自选'" @click="toggleStockStar">
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path :fill="stockStarred ? 'var(--brand)' : 'none'" :stroke="stockStarred ? 'var(--brand)' : 'currentColor'" stroke-width="1.5" d="M12 17.3l5.2 3.1-1.4-5.9L20 9.8l-6-.5L12 3.7 9.9 9.3l-6 .5 4.2 4.7-1.4 5.9 5.3-3.1z"/>
            </svg>
          </button>
        </div>

        <div v-if="selectedStock" class="detail-scroll">
          <!-- 价格卡片 -->
          <div class="detail-price-card">
            <div class="detail-price-row">
              <span class="detail-px tabular">{{ selectedStock.price ? '¥' + Number(selectedStock.price).toFixed(2) : '--' }}</span>
              <span class="detail-pct tabular" :class="stockDir(selectedStock)">{{ stockChangeText(selectedStock) }}</span>
            </div>
            <div class="detail-tags-row">
              <span class="detail-tag">{{ selectedStock.code }}</span>
              <span v-if="selectedThemeName" class="detail-tag">{{ selectedThemeName }}</span>
            </div>
          </div>

          <!-- K线 -->
          <div class="detail-kline-card">
            <div class="detail-label">K线走势</div>
            <KlineChart v-if="selectedStock?.code" :code="selectedStock.code" />
          </div>

          <!-- 评分 -->
          <div v-if="selectedStock.score" class="detail-score-card">
            <div class="detail-score-row">
              <div>
                <div class="detail-label">题材评分</div>
                <div class="detail-score-num tabular">{{ selectedStock.score }}分</div>
              </div>
              <span v-if="selectedStock.role" class="detail-grade-badge">{{ selectedStock.role }}</span>
            </div>
          </div>

          <!-- 特征标签 -->
          <div v-if="getStockTags(selectedStock).length" class="detail-tags-card">
            <div class="detail-label">特征标签</div>
            <div class="detail-pills">
              <span v-for="tag in getStockTags(selectedStock)" :key="tag" class="pill-tag">{{ tag }}</span>
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

async function refresh({ force = false } = {}) {
  if (inFlight) return
  inFlight = true
  if (force || themes.value.length === 0) loading.value = true
  error.value = ''
  try {
    const result = await ticai.all({ force, refreshFirst: force })
    themes.value = Object.entries(result.data || {}).map(([name, info]) => ({ name, ...info }))
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
    inFlight = false
  }
}

function refreshForce() { return refresh({ force: true }) }

function themeChangeDir(theme) {
  return (theme.info?.change_pct || 0) >= 0 ? 'up' : 'down'
}
function themeChangeText(theme) {
  const n = theme.info?.change_pct || 0
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%'
}

function stockDir(stock) {
  return (stock.change_pct_num ?? 0) >= 0 ? 'up' : 'down'
}
function stockChangeText(stock) {
  if (stock.change_pct) return stock.change_pct
  const n = stock.change_pct_num ?? 0
  return (n >= 0 ? '+' : '') + Number(n).toFixed(2) + '%'
}

function hasFeatureTags(s) {
  if (!s) return false
  return !!(s.is_first_limit || s.is_limit_up || s.is_weak_to_strong || s.volume_level === '地量')
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
  try {
    const { in_watchlist } = await watchlist.check(stock.code)
    stockStarred.value = !!in_watchlist
  } catch { stockStarred.value = false }
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
  } catch (e) { error.value = e.message || '操作失败' }
}

function closeDetail() {
  stockModalVisible.value = false
  document.body.style.overflow = ''
}

function startAutoRefresh() {
  refreshTimer = setInterval(() => refresh({ force: false }), 60000)
}

onMounted(() => { refresh(); startAutoRefresh() })
onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer) })
</script>

<style scoped>
/*
 * 题材挖掘 — Architectural Ledger 风格（参考 Watchlist.vue）
 * 涨跌语义：正向/涨 #006d41，负向/跌 #a00024
 */
.ticai-page {
  min-height: 100vh;
  background: var(--bg);
  color: var(--text-1);
  font-family: 'Inter', var(--font);
}

/* ── 顶部导航 ── */
.navbar {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: calc(48px + env(safe-area-inset-top, 0));
  padding: 0 12px;
  padding-top: env(safe-area-inset-top, 0);
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 1px 0 var(--divider);
}
.nav-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  cursor: pointer;
  flex-shrink: 0;
}
.nav-icon .icon { fill: var(--text-2); }
.nav-title {
  flex: 1;
  font-family: 'Manrope', var(--font);
  font-size: 17px;
  font-weight: 800;
  letter-spacing: -0.02em;
  text-align: center;
  color: var(--brand);
}
.nav-refresh {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: none;
  border: none;
  cursor: pointer;
  flex-shrink: 0;
}
.nav-refresh .icon { fill: var(--text-2); }
.spinning .icon { animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── 题材概览条 ── */
.hot-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  background: var(--surface);
  border-bottom: 1px solid var(--divider);
}
.hot-header__fire {
  width: 18px;
  height: 18px;
  fill: var(--brand);
  flex-shrink: 0;
}
.hot-header__title {
  font-family: 'Manrope', var(--font);
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--brand);
}
.hot-header__count {
  font-size: 13px;
  color: var(--text-3);
}
.btn-primary {
  margin-left: auto;
  padding: 7px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 700;
  border: none;
  cursor: pointer;
  background: var(--surface-2);
  color: var(--text-2);
}
.btn-primary--grad {
  background: linear-gradient(135deg, var(--brand) 0%, #1a56d4 100%);
  color: #fff;
  box-shadow: 0 2px 12px rgba(41, 98, 255, 0.28);
}
.btn-primary:disabled { opacity: 0.55; cursor: not-allowed; }

/* ── 内容区 ── */
.container { padding: 12px 14px 32px; }

.state {
  text-align: center;
  padding: 72px 20px 48px;
  color: var(--text-3);
  font-size: 14px;
}
.state--err { color: var(--down); }
.state__icon { font-size: 48px; margin-bottom: 14px; }
.state p { margin-bottom: 14px; }
.spinner {
  width: 28px;
  height: 28px;
  border: 2.5px solid var(--divider);
  border-top-color: var(--brand);
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
  margin: 0 auto 12px;
}

/* ── 题材列表 ── */
.theme-list { display: flex; flex-direction: column; gap: 12px; }

.theme-card {
  background: var(--surface);
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}

/* 题材头部 */
.theme-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 14px 10px;
  background: linear-gradient(165deg, rgba(41, 98, 255, 0.08) 0%, #fff 55%);
}
.theme-head__left { flex: 1; min-width: 0; }
.theme-head__name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: 'Manrope', var(--font);
  font-size: 16px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--text-1);
  margin-bottom: 6px;
}
.theme-head__fire { width: 16px; height: 16px; fill: var(--brand); flex-shrink: 0; }
.theme-head__badges { display: flex; flex-wrap: wrap; gap: 5px; }
.badge {
  font-size: 10px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
}
.badge-emotion { background: rgba(41, 98, 255, 0.1); }
.badge-quality { background: rgba(107, 79, 163, 0.12); }
.theme-head__change {
  font-size: 16px;
  font-weight: 800;
  flex-shrink: 0;
}

/* 题材统计条 */
.theme-stats {
  display: flex;
  gap: 16px;
  padding: 8px 14px;
  font-size: 12px;
  color: var(--text-3);
  background: var(--surface-2);
  border-top: 1px solid var(--divider);
  border-bottom: 1px solid var(--divider);
}
.stat { font-weight: 600; }
.stat em { font-style: normal; }
.stat--up { color: #006d41; font-weight: 800; }
.stat--down { color: #a00024; font-weight: 800; }

/* ── 成分股表格（仿 Watchlist 风格）── */
.stock-table { }
.stock-table__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 7px 14px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-3);
  border-bottom: 1px solid var(--divider);
}
.tar { text-align: right; }

.stock-row {
  padding: 11px 14px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  cursor: pointer;
  transition: background 0.1s ease;
  border-bottom: 1px solid var(--divider);
}
.stock-row:last-of-type { border-bottom: none; }
.stock-row:active { background: var(--surface-2); }

.stock-row__main {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  width: 100%;
}
.stock-row__rank {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  flex-shrink: 0;
  padding-top: 1px;
}
.rank-num {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 800;
  color: #fff;
  flex-shrink: 0;
}
.rank-1 { background: var(--brand); }
.rank-2 { background: #1e56c9; }
.rank-3 { background: #4a6fa5; }
.rank-4, .rank-5 { background: #8e9299; }

.role-tag {
  font-size: 9px;
  font-weight: 800;
  padding: 3px 6px;
  border-radius: 3px;
  letter-spacing: 0.02em;
  flex-shrink: 0;
}
.role-龙头 { background: #a00024; color: #fff; }
.role-中军 { background: var(--brand); color: #fff; }
.role-低吸, .role-跟风 { background: var(--text-2); color: #fff; }

.stock-row__info { flex: 1; min-width: 0; }
.stock-row__nm {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-1);
  line-height: 1.3;
}
.stock-row__cd {
  display: inline-block;
  margin-left: 6px;
  font-size: 11px;
  color: var(--text-3);
  font-weight: 400;
}

.stock-row__right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
  padding-top: 1px;
}
.stock-row__chg {
  font-size: 14px;
  font-weight: 800;
}
.stock-row__price {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-1);
}
.stock-row__score {
  font-size: 10px;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 4px;
  background: #a00024;
  color: #fff;
}

/* 特征标签单独一行 */
.stock-row__feat {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding-left: 29px;
}
.feat-tag {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 4px;
}
.feat-tag--red { background: rgba(160, 0, 36, 0.1); color: #a00024; }
.feat-tag--blue { background: rgba(41, 98, 255, 0.1); color: var(--brand); }
.feat-tag--gray { background: var(--surface-2); color: var(--text-3); }

.stock-empty {
  padding: 22px 14px;
  text-align: center;
  font-size: 13px;
  color: var(--text-3);
  border-top: 1px solid var(--divider);
}

/* 涨跌通用 */
.up { color: #006d41 !important; }
.down { color: #a00024 !important; }
em { font-style: normal; }

/* ── 详情弹窗 ── */
.detail-modal {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(25, 28, 29, 0.42);
  z-index: 200;
}
.detail-modal.active { display: block; }
.detail-panel {
  position: absolute;
  inset: 0;
  background: var(--bg);
  animation: slideIn 0.3s cubic-bezier(0.32, 0.72, 0, 1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
@keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }

.detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 12px;
  padding-top: calc(12px + env(safe-area-inset-top, 0));
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 1px 0 var(--divider);
  flex-shrink: 0;
}
.detail-icon-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: var(--surface-2);
  border: none;
  cursor: pointer;
  flex-shrink: 0;
}
.detail-icon-btn svg { fill: var(--text-2); }
.detail-title {
  flex: 1;
  font-family: 'Manrope', var(--font);
  font-size: 17px;
  font-weight: 800;
  letter-spacing: -0.02em;
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--text-1);
  min-width: 0;
}
.detail-title__fire { width: 18px; height: 18px; fill: var(--brand); flex-shrink: 0; }
.detail-star-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: var(--surface-2);
  border: none;
  cursor: pointer;
  flex-shrink: 0;
}
.detail-star-btn svg { fill: none; stroke: var(--text-4); stroke-width: 1.5; }
.detail-star-btn.on svg { fill: var(--brand); stroke: var(--brand); }

.detail-scroll { flex: 1; overflow-y: auto; padding: 14px; }

.detail-card {
  background: var(--surface);
  border-radius: 10px;
  padding: 16px 16px 14px;
  margin-bottom: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  outline: 1px solid rgba(115, 118, 136, 0.15);
  outline-offset: -1px;
}
.detail-price-row { display: flex; align-items: baseline; gap: 12px; margin-bottom: 8px; flex-wrap: wrap; }
.detail-px {
  font-size: 34px;
  font-weight: 800;
  color: var(--text-1);
}
.detail-pct { font-size: 18px; font-weight: 800; }
.detail-tags-row { display: flex; gap: 8px; flex-wrap: wrap; }
.detail-tag {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-2);
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--surface-2);
}

.detail-kline-card { margin-bottom: 10px; }
.detail-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-3);
  margin-bottom: 8px;
}

.detail-score-card {
  background: var(--surface);
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  outline: 1px solid rgba(115, 118, 136, 0.15);
  outline-offset: -1px;
}
.detail-score-row { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; }
.detail-score-num {
  font-family: 'Manrope', var(--font);
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--text-1);
  margin-top: 4px;
}
.detail-grade-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
  background: var(--brand);
  color: #fff;
}

.detail-tags-card {
  background: var(--surface);
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  outline: 1px solid rgba(115, 118, 136, 0.15);
  outline-offset: -1px;
}
.detail-pills { display: flex; flex-wrap: wrap; gap: 6px; }
.pill-tag {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 6px;
  background: var(--surface-2);
  color: var(--text-2);
}
</style>
