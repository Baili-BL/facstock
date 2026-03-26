<template>
  <div class="bollinger-page">
    <!-- 顶部导航 -->
    <nav class="navbar">
      <div class="nav-back" @click="$router.push('/strategy')">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </div>
      <div class="nav-center">
        <div class="nav-title">
          <svg class="icon" style="fill:var(--apple-indigo);margin-right:6px" viewBox="0 0 24 24"><use href="#icon-strategy"/></svg>
          布林收缩策略
        </div>
        <div class="nav-sub">布林带收缩 · Bollinger Squeeze</div>
      </div>
    </nav>

    <div class="container">
      <!-- 扫描参数 -->
      <div class="param-card">
        <div class="param-card-title">
          <svg class="icon icon-sm" style="fill:var(--apple-orange)"><use href="#icon-tune"/></svg>
          扫描参数
        </div>
        <div class="param-item">
          <div class="param-label">
            <span class="param-name">扫描板块数</span>
            <span class="param-value">{{ params.sectors }}</span>
          </div>
          <input type="range" class="param-slider" v-model.number="params.sectors" min="1" max="20" step="1">
          <div class="param-desc">从热点板块中选取分析的板块数量</div>
        </div>
        <div class="param-item">
          <div class="param-label">
            <span class="param-name">收缩天数</span>
            <span class="param-value">{{ params.minDays }}</span>
          </div>
          <input type="range" class="param-slider" v-model.number="params.minDays" min="1" max="10" step="1">
          <div class="param-desc">布林带收缩持续的最少天数</div>
        </div>
        <div class="param-item">
          <div class="param-label">
            <span class="param-name">分析周期</span>
            <span class="param-value">{{ params.period }}</span>
          </div>
          <input type="range" class="param-slider" v-model.number="params.period" min="10" max="60" step="5">
          <div class="param-desc">布林带计算周期（交易日）</div>
        </div>
      </div>

      <!-- 扫描按钮 -->
      <button class="scan-btn" :disabled="scanning" @click="startScan">
        <svg v-if="!scanning" class="icon" viewBox="0 0 24 24"><use href="#icon-play"/></svg>
        <svg v-else class="icon spinning" viewBox="0 0 24 24"><use href="#icon-refresh"/></svg>
        {{ scanning ? '启动中...' : '开始扫描' }}
      </button>
      <button v-if="scanning" class="cancel-btn" @click="cancelScan">
        <svg class="icon" viewBox="0 0 24 24"><use href="#icon-cancel"/></svg>
        取消扫描
      </button>

      <!-- 扫描进度 -->
      <div class="scan-status-card" :class="{ active: scanning }">
        <div class="scan-status-header">
          <div class="scan-status-dot" :class="{ error: scanError }"></div>
          <div>
            <div class="scan-status-label">{{ scanCancelled ? '正在取消...' : '扫描中...' }}</div>
            <div class="scan-sector">{{ currentSector }}</div>
          </div>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: progress + '%' }"></div>
        </div>
        <div class="progress-text">{{ progress }}%</div>
      </div>

      <!-- 扫描结果 -->
      <div class="results-card" :class="{ active: resultsExist }">
        <div class="results-header">
          <svg class="icon icon-sm" style="fill:var(--apple-green)"><use href="#icon-check"/></svg>
          扫描结果
          <span class="results-time">{{ resultsTime }}</span>
          <span class="results-hint" :class="{ show: scanning && resultsExist }">
            最近一次已完成 · 本次扫描完成后自动更新
          </span>
        </div>
        <div v-if="resultsLoading" class="loading">
          <div class="spinner"></div>
        </div>
        <div v-else-if="resultsError" class="error-msg">{{ resultsError }}</div>
        <div v-else-if="!resultsExist" class="empty">
          <svg class="icon empty-icon" viewBox="0 0 24 24"><use href="#icon-analytics"/></svg>
          暂无扫描结果
        </div>
        <template v-else>
          <!-- 板块 Tab 行 -->
          <div class="sector-tabs-scroll">
            <button
              v-for="g in groupedResults"
              :key="g.sectorName"
              type="button"
              class="sector-tab"
              :class="{ active: selectedSector === g.sectorName }"
              @click="selectedSector = g.sectorName"
            >
              <div class="sector-tab-name">{{ g.sectorName }}</div>
              <div class="sector-tab-change" :class="g.avgChange >= 0 ? 'up' : 'down'">
                {{ g.avgChange >= 0 ? '+' : '' }}{{ g.avgChange.toFixed(2) }}%
              </div>
            </button>
          </div>

          <!-- 股票筛选项 -->
          <div class="results-toolbar">
            <div class="filter-chips">
              <button
                v-for="f in filterOptions"
                :key="f.key"
                type="button"
                class="filter-chip"
                :class="{ active: filterTab === f.key }"
                @click="filterTab = f.key"
              >
                {{ f.label }}
              </button>
            </div>
          </div>

          <!-- 当前选中板块的股票列表 -->
          <div v-if="activeSectorStocks.length === 0" class="empty-inner">当前筛选条件下暂无股票</div>
          <div v-else class="squeeze-list">
            <div
              v-for="s in activeSectorStocks"
              :key="s.code"
              class="squeeze-card"
              :class="cardToneClass(s)"
              @click="showDetail(s)"
            >
              <div class="squeeze-card-top">
                <div class="squeeze-left">
                  <div class="squeeze-name-line">
                    <span class="squeeze-name">{{ s.name }}</span>
                    <span class="squeeze-code">{{ s.code }}</span>
                  </div>
                  <div class="squeeze-sector">{{ s.sector_name }}</div>
                </div>
                <div class="squeeze-price-block">
                  <span class="squeeze-price">{{ fmtClose(s) }}</span>
                  <span class="squeeze-pct-pill" :class="fmtPct(s).cls">{{ fmtPct(s).text }}</span>
                </div>
                <button type="button" class="star-btn" aria-label="自选" @click.stop.prevent>
                  <svg class="icon star-icon" viewBox="0 0 24 24"><use href="#icon-star-outline"/></svg>
                </button>
              </div>
              <div class="metric-grid">
                <div class="metric-cell">
                  <div class="metric-val">
                    <span class="metric-num">{{ fmtScore(s) }}</span>
                    <span v-if="s.grade" class="metric-grade">{{ s.grade }}级</span>
                  </div>
                  <div class="metric-label">评分</div>
                </div>
                <div class="metric-cell">
                  <div class="metric-val"><span class="metric-num">{{ fmtBandwidth(s) }}</span></div>
                  <div class="metric-label">带宽</div>
                </div>
                <div class="metric-cell">
                  <div class="metric-val"><span class="metric-num">{{ fmtSqueezeDays(s) }}</span></div>
                  <div class="metric-label">收缩</div>
                </div>
                <div class="metric-cell">
                  <div class="metric-val"><span class="metric-num">{{ fmtVolumeRatio(s) }}</span></div>
                  <div class="metric-label">量比</div>
                </div>
              </div>
              <div class="squeeze-tags">
                <span
                  v-for="tag in resolveStockTags(s)"
                  :key="tag"
                  class="pill-tag"
                  :class="tagClass(tag)"
                >{{ tag }}</span>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- 历史记录 -->
      <div class="history-section">
        <div class="section-header">
          <div class="section-title">
            <svg class="icon" viewBox="0 0 24 24"><use href="#icon-history"/></svg>
            扫描历史
          </div>
          <button class="refresh-btn" @click="loadHistory">
            <svg class="icon icon-sm" viewBox="0 0 24 24"><use href="#icon-refresh"/></svg>
            刷新
          </button>
        </div>
        <div v-if="historyLoading" class="loading"><div class="spinner"></div></div>
        <div v-else-if="historyError" class="error-msg">{{ historyError }}</div>
        <div v-else-if="history.length === 0" class="empty">
          <svg class="icon empty-icon" viewBox="0 0 24 24"><use href="#icon-history"/></svg>
          暂无扫描历史
        </div>
        <div v-else class="history-list">
          <div v-for="rec in history" :key="rec.id" class="history-card" @click="viewDetail(rec.id)">
            <div class="history-info">
              <div class="history-date">
                <svg class="icon icon-sm" viewBox="0 0 24 24"><use href="#icon-history"/></svg>
                {{ fmtDate(rec.scan_time) }}
              </div>
              <div class="history-meta">
                <span class="history-status" :class="rec.status">{{ statusLabel(rec.status) }}</span>
                <span v-if="rec.sector_count > 0">{{ rec.sector_count }}板块</span>
                <span v-if="rec.stock_count > 0">{{ rec.stock_count }}只</span>
                <span v-if="rec.hot_sectors && rec.hot_sectors.length">
                  {{ rec.hot_sectors.slice(0,2).map(s => s.name).join(', ') }}
                </span>
              </div>
            </div>
            <div class="history-right">
              <button class="delete-btn" @click.stop="deleteScan(rec.id)" title="删除">
                <svg class="icon" viewBox="0 0 24 24"><use href="#icon-delete"/></svg>
              </button>
              <svg class="icon icon-sm" style="fill:var(--apple-gray3)" viewBox="0 0 24 24"><use href="#icon-chevron"/></svg>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 股票详情弹窗 -->
    <div class="detail-modal" :class="{ active: stockModalVisible }" @click.self="closeDetail">
      <div class="detail-panel">
        <div class="detail-header">
          <button class="close-btn" @click="closeDetail">
            <svg class="icon" viewBox="0 0 24 24"><use href="#icon-back"/></svg>
          </button>
          <span class="detail-title">
            <svg class="icon"><use href="#icon-fire"/></svg>
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
              <span class="detail-price">{{ fmtClose(selectedStock) }}</span>
              <span class="detail-pct" :class="fmtPct(selectedStock).cls">{{ fmtPct(selectedStock).text }}</span>
            </div>
            <div class="detail-meta-row">
              <span class="detail-meta-item">{{ selectedStock.code }}</span>
              <span class="detail-meta-item">{{ selectedStock.sector_name }}</span>
            </div>
          </div>

          <!-- K线图：标题在上，Tab+画布在组件内紧贴 -->
          <div class="detail-kline-card">
            <div class="detail-section-label detail-kline-heading">K线走势</div>
            <KlineChart
              v-if="selectedStock?.code"
              :code="selectedStock.code"
            />
          </div>

          <!-- 评分区 -->
          <div class="detail-score-card">
            <div class="detail-score-left">
              <div class="detail-score-label">综合评分</div>
              <div class="detail-score-val">
                <span class="detail-score-num">{{ fmtScore(selectedStock) }}</span>
                <span v-if="selectedStock.grade" class="detail-grade-badge" :class="'grade-' + (selectedStock.grade || '').toLowerCase()">
                  {{ selectedStock.grade }}级
                </span>
              </div>
            </div>
            <div class="detail-metrics-row">
              <div class="detail-metric">
                <span class="dm-val">{{ fmtBandwidth(selectedStock) }}</span>
                <span class="dm-label">带宽</span>
              </div>
              <div class="detail-metric">
                <span class="dm-val">{{ fmtSqueezeDays(selectedStock) }}</span>
                <span class="dm-label">收缩</span>
              </div>
              <div class="detail-metric">
                <span class="dm-val">{{ fmtVolumeRatio(selectedStock) }}</span>
                <span class="dm-label">量比</span>
              </div>
            </div>
          </div>

          <!-- 标签 -->
          <div class="detail-tags-card" v-if="resolveStockTags(selectedStock).length">
            <div class="detail-section-label">特征标签</div>
            <div class="detail-tags">
              <span
                v-for="tag in resolveStockTags(selectedStock)"
                :key="tag"
                class="pill-tag"
                :class="tagClass(tag)"
              >{{ tag }}</span>
            </div>
          </div>

          <!-- 指标摘要 -->
          <div class="detail-indicators-card">
            <div class="detail-section-label">技术指标</div>
            <div class="detail-ind-grid">
              <div class="detail-ind-row">
                <span class="di-key">MACD</span>
                <span class="di-val" :class="truthy(selectedStock.macd_golden) ? 'up' : ''">
                  {{ truthy(selectedStock.macd_golden) ? '金叉' : '--' }}
                </span>
              </div>
              <div class="detail-ind-row">
                <span class="di-key">MA多头</span>
                <span class="di-val" :class="truthy(selectedStock.ma_full_bullish) ? 'up' : truthy(selectedStock.ma_bullish) ? 'mid' : ''">
                  {{ selectedStock.ma_full_bullish ? '多头排列' : selectedStock.ma_bullish ? '短期多头' : '--' }}
                </span>
              </div>
              <div class="detail-ind-row">
                <span class="di-key">资金流</span>
                <span class="di-val" :class="truthy(selectedStock.cmf_bullish) ? 'up' : ''">
                  {{ selectedStock.cmf_strong_bullish ? '强势流入' : selectedStock.cmf_bullish ? '净流入' : '--' }}
                </span>
              </div>
              <div class="detail-ind-row">
                <span class="di-key">RSI</span>
                <span class="di-val" :class="truthy(selectedStock.rsv_recovering) ? 'up' : ''">
                  {{ selectedStock.rsv_recovering ? '超卖回升' : selectedStock.rsv_golden ? 'RSV健康' : '--' }}
                </span>
              </div>
            </div>
          </div>

          <!-- 跳转提示 -->
          <div class="detail-goto-hint" @click="window.location.href = '/ticai?code=' + selectedStock?.code">
            <svg class="icon" viewBox="0 0 24 24"><use href="#icon-analytics"/></svg>
            点击查看完整投研报告
            <svg class="icon" viewBox="0 0 24 24"><use href="#icon-chevron-right"/></svg>
          </div>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div class="toast" :class="[toastType, { show: toastVisible }]">{{ toastMsg }}</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { scan, watchlist } from '@/api/strategy.js'
import KlineChart from '@/components/KlineChart.vue'

// ─── 参数 ───
const params = ref({ sectors: 5, minDays: 3, period: 20 })

// ─── 扫描状态 ───
const scanning = ref(false)
const scanError = ref('')
const scanCancelled = ref(false)
const progress = ref(0)
const currentSector = ref('')
let pollTimer = null

// ─── 结果 ───
const results = ref({})
const resultsLoading = ref(false)
const resultsError = ref('')
const resultsTime = ref('')

const filterTab = ref('all')
const selectedSector = ref('')
const selectedStock = ref(null)
const stockModalVisible = ref(false)
const stockStarred = ref(false)
const filterOptions = [
  { key: 'all', label: '全部' },
  { key: 'S', label: '★ S级' },
  { key: 'A', label: '👍 A级' },
  { key: 'volume', label: '📈 放量' },
  { key: 'money', label: '$ 资金' },
]

const resultsExist = computed(() => Object.keys(results.value).length > 0)
const sortedResults = computed(() => {
  return Object.entries(results.value)
    .sort(([, a], [, b]) => (b.change || 0) - (a.change || 0))
    .reduce((acc, [k, v]) => { acc[k] = v; return acc }, {})
})

const flatStocks = computed(() => {
  const list = []
  for (const [sectorName, data] of Object.entries(sortedResults.value)) {
    for (const s of (data.stocks || [])) {
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

const filteredStocks = computed(() => {
  let arr = flatStocks.value
  if (filterTab.value === 'S') arr = arr.filter(s => s.grade === 'S')
  else if (filterTab.value === 'A') arr = arr.filter(s => s.grade === 'A')
  else if (filterTab.value === 'volume') {
    arr = arr.filter(s => truthy(s.is_volume_up) || truthy(s.is_volume_price_up) ||
      resolveStockTags(s).some(t => String(t).includes('放量')))
  } else if (filterTab.value === 'money') {
    arr = arr.filter(s => truthy(s.cmf_bullish) ||
      resolveStockTags(s).some(t => /资金|流入/.test(String(t))))
  }
  return arr
})

// 当前选中板块的股票（支持筛选）
const activeSectorStocks = computed(() => {
  // 无板块时清空
  if (!groupedResults.value.length) {
    selectedSector.value = ''
    return []
  }
  // 兜底默认选中第一个板块
  if (!selectedSector.value || !groupedResults.value.find(g => g.sectorName === selectedSector.value)) {
    selectedSector.value = groupedResults.value[0].sectorName
  }
  const group = groupedResults.value.find(g => g.sectorName === selectedSector.value)
  let stocks = group.stocks
  if (filterTab.value === 'S') stocks = stocks.filter(s => s.grade === 'S')
  else if (filterTab.value === 'A') stocks = stocks.filter(s => s.grade === 'A')
  else if (filterTab.value === 'volume') {
    stocks = stocks.filter(s => truthy(s.is_volume_up) || truthy(s.is_volume_price_up) ||
      resolveStockTags(s).some(t => String(t).includes('放量')))
  } else if (filterTab.value === 'money') {
    stocks = stocks.filter(s => truthy(s.cmf_bullish) ||
      resolveStockTags(s).some(t => /资金|流入/.test(String(t))))
  }
  return stocks
})
const groupedResults = computed(() => {
  const map = {}
  for (const s of filteredStocks.value) {
    const key = s.sector_name || '其他'
    if (!map[key]) {
      map[key] = { sectorName: key, stocks: [], totalScore: 0, totalChange: 0, count: 0 }
    }
    map[key].stocks.push(s)
    const sc = Number(s.total_score ?? s.score ?? 0)
    const pc = Number(s.pct_change ?? 0)
    if (Number.isFinite(sc)) { map[key].totalScore += sc; map[key].count++ }
    if (Number.isFinite(pc)) map[key].totalChange += pc
  }

  return Object.values(map)
    .map(g => ({
      ...g,
      avgScore: g.count > 0 ? g.totalScore / g.count : 0,
      avgChange: g.stocks.length > 0
        ? g.stocks.reduce((s, st) => s + Number(st.pct_change ?? 0), 0) / g.stocks.length
        : 0,
      bestGrade: (() => {
        const grades = ['S', 'A'].filter(gr => g.stocks.some(s => s.grade === gr))
        return grades[0] || null
      })(),
    }))
    .sort((a, b) => {
      // S级板块优先，其次按均分
      const scoreA = (a.bestGrade === 'S' ? 2 : a.bestGrade === 'A' ? 1 : 0)
      const scoreB = (b.bestGrade === 'S' ? 2 : b.bestGrade === 'A' ? 1 : 0)
      if (scoreA !== scoreB) return scoreB - scoreA
      return b.avgScore - a.avgScore
    })
    return val
})

// ─── 历史 ───
const history = ref([])
const historyLoading = ref(false)
const historyError = ref('')

// ─── Toast ───
const toastMsg = ref('')
const toastType = ref('')
const toastVisible = ref(false)
let toastTimer = null

function showToast(msg, type = '') {
  toastMsg.value = msg
  toastType.value = type
  toastVisible.value = true
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastVisible.value = false }, 2500)
}

// ─── 轮询 ───
async function startPolling() {
  pollTimer = setInterval(pollStatus, 1500)
  await pollStatus()
}

function stopPolling() {
  clearInterval(pollTimer)
  pollTimer = null
}

async function pollStatus() {
  try {
    const json = await scan.status()
    scanError.value = ''
    if (!json.is_scanning && scanning.value) {
      stopPolling()
      scanning.value = false
      await loadResults()
      await loadHistory()
    } else {
      scanning.value = !!json.is_scanning
      progress.value = json.progress || 0
      currentSector.value = json.current_sector || ''
      scanCancelled.value = !!json.cancelled
      if (json.error) scanError.value = json.error
    }
  } catch {}
}

// ─── 扫描 ───
async function startScan() {
  if (scanning.value) return
  scanning.value = true
  scanError.value = ''
  scanCancelled.value = false
  progress.value = 0
  resultsError.value = ''
  try {
    const json = await scan.start({
      sectors: params.value.sectors,
      min_days: params.value.minDays,
      period: params.value.period,
    })
    if (!json.success) {
      showToast(json.error || '启动失败', 'error')
      scanning.value = false
      return
    }
    await startPolling()
  } catch (e) {
    showToast('网络错误: ' + e.message, 'error')
    scanning.value = false
  }
}

async function cancelScan() {
  if (!scanning.value) return
  try {
    await scan.cancel()
    scanCancelled.value = true
    showToast('正在取消...')
  } catch {}
}

// ─── 结果 ───
async function loadResults() {
  resultsLoading.value = true
  resultsError.value = ''
  try {
    const json = await scan.results()
    if (!json.success || !json.results || Object.keys(json.results).length === 0) {
      results.value = {}
      return
    }
    results.value = json.results
    resultsTime.value = json.last_update ? '更新于 ' + fmtDate(json.last_update) : ''
    filterTab.value = 'all'
  } catch (e) {
    resultsError.value = e.message || '加载失败'
  } finally {
    resultsLoading.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  historyError.value = ''
  try {
    const json = await scan.history()
    history.value = (json.data || json || []).slice(0, 20)
  } catch (e) {
    historyError.value = e.message || '加载失败'
  } finally {
    historyLoading.value = false
  }
}

async function viewDetail(id) {
  resultsLoading.value = true
  resultsError.value = ''
  try {
    const json = await scan.detail(id)
    if (!json.success || !json.data) {
      showToast('该扫描暂无结果', 'error')
      return
    }
    const data = json.data
    results.value = data.results || {}
    resultsTime.value = data.scan_time ? '历史扫描 · ' + fmtDate(data.scan_time) : '历史扫描'
    filterTab.value = 'all'
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (e) {
    showToast('加载失败', 'error')
  } finally {
    resultsLoading.value = false
  }
}

async function deleteScan(id) {
  if (!confirm('确定删除这条扫描记录？')) return
  try {
    await scan.delete(id)
    showToast('删除成功', 'success')
    await loadHistory()
  } catch (e) {
    showToast(e.message || '删除失败', 'error')
  }
}

// ─── 标签系统 ───
function truthy(v) {
  return v === true || v === 1 || v === '1' || v === 'true'
}

function buildFallbackTags(s) {
  const tags = []
  const g = s.grade
  if (g === 'S' || g === 'A') tags.push(g + '级')
  if (s.is_leader && s.leader_rank) tags.push('中军#' + s.leader_rank)
  if (truthy(s.cmf_strong_bullish)) tags.push('强势流入')
  else if (truthy(s.cmf_bullish) && truthy(s.cmf_rising)) tags.push('资金流入')
  else if (truthy(s.cmf_bullish)) tags.push('资金净流入')
  if (truthy(s.rsv_recovering)) tags.push('超卖回升')
  else if (truthy(s.rsv_golden)) {
    const r = Number(s.rsv)
    tags.push(Number.isFinite(r) && r >= 65 ? 'RSV强势' : 'RSV健康')
  }
  if (truthy(s.ma_full_bullish)) tags.push('多头排列')
  else if (truthy(s.ma_bullish)) tags.push('短多')
  if (truthy(s.macd_golden) && truthy(s.macd_hist_positive)) tags.push('MACD强势')
  else if (truthy(s.macd_golden)) tags.push('MACD金叉')
  if (truthy(s.is_volume_price_up)) tags.push('量价齐升')
  else if (truthy(s.is_volume_up)) tags.push('放量')
  if (truthy(s.low_volatility)) tags.push('低波蓄势')
  const to = Number(s.turnover)
  if (Number.isFinite(to)) {
    if (to >= 3 && to <= 10) tags.push('人气旺')
    else if (to > 10) tags.push('超人气')
    else if (to >= 1 && to < 3) tags.push('有关注')
  }
  const pc = Number(s.pct_change)
  if (Number.isFinite(pc) && pc >= 5) tags.push('先锋')
  return tags
}

function resolveStockTags(s) {
  let tags = Array.isArray(s.tags) ? s.tags.filter(Boolean) : []
  if (tags.length === 0) tags = buildFallbackTags(s)
  if (tags.length === 0) {
    if (s.squeeze_days != null && s.squeeze_days !== '') tags.push('缩' + s.squeeze_days + '天')
    const bw = Number(s.bb_width_pct)
    if (Number.isFinite(bw)) tags.push('带宽' + bw.toFixed(1) + '%')
  }
  return tags
}

function tagClass(tag) {
  const x = String(tag)
  if (x.startsWith('S级')) return 'pill-grade-s'
  if (x.startsWith('A级')) return 'pill-grade-a'
  if (x.startsWith('中军')) return 'pill-leader'
  if (x.includes('流入') || x.includes('资金')) return 'pill-cmf'
  if (x.includes('MACD') || x.includes('RSV')) return 'pill-ind'
  if (x.includes('多头') || x.includes('短多')) return 'pill-trend'
  if (x.includes('量价') || x.includes('放量')) return 'pill-vol'
  if (x.includes('先锋')) return 'pill-pioneer'
  return 'pill-default'
}

function fmtScore(s) {
  const v = s.total_score ?? s.score ?? s.totalScore
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(1) : '--'
}

function fmtPct(s) {
  const n = Number(s.pct_change)
  if (!Number.isFinite(n)) return { text: '--', cls: '' }
  return { text: (n >= 0 ? '+' : '') + n.toFixed(2) + '%', cls: n >= 0 ? 'up' : 'down' }
}

function fmtSqueezeDays(s) {
  const v = s.squeeze_days
  if (v == null || v === '') return '--'
  return String(v) + '天'
}

function fmtClose(s) {
  const n = Number(s.close)
  return Number.isFinite(n) ? n.toFixed(2) : '--'
}

function fmtBandwidth(s) {
  const n = Number(s.bb_width_pct)
  return Number.isFinite(n) ? n.toFixed(1) + '%' : '--'
}

function fmtVolumeRatio(s) {
  const n = Number(s.volume_ratio ?? s.volumeRatio)
  return Number.isFinite(n) ? n.toFixed(1) : '--'
}

function cardToneClass(s) {
  const g = s.grade
  if (g === 'S') return 'tone-s'
  if (g === 'A') return 'tone-a'
  return 'tone-default'
}

async function showDetail(stock) {
  selectedStock.value = stock
  stockModalVisible.value = true
  document.body.style.overflow = 'hidden'
  // 检查是否已自选
  if (stock?.code) {
    try {
      const { in_watchlist } = await watchlist.check(stock.code)
      stockStarred.value = !!in_watchlist
    } catch {
      stockStarred.value = false
    }
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
    showToast(e.message || '操作失败', 'error')
  }
}

function closeDetail() {
  stockModalVisible.value = false
  document.body.style.overflow = ''
}

function fmtDate(dt) {
  if (!dt) return '--'
  const d = new Date(dt)
  if (isNaN(d)) return String(dt)
  const pad = n => String(n).padStart(2, '0')
  return `${pad(d.getMonth()+1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function statusLabel(s) {
  const map = { completed: '已完成', scanning: '扫描中', error: '出错', cancelled: '已取消' }
  return map[s] || s || '未知'
}

// ─── 初始化 ───
async function init() {
  try {
    const statusJson = await scan.status()
    if (statusJson.is_scanning) {
      scanning.value = true
      scanCancelled.value = false
      progress.value = statusJson.progress || 0
      currentSector.value = statusJson.current_sector || ''
      await startPolling()
    } else {
      await Promise.all([loadResults(), loadHistory()])
    }
  } catch {
    await Promise.all([loadResults(), loadHistory()])
  }
}

onMounted(init)
onUnmounted(stopPolling)
</script>

<style scoped>
.bollinger-page {
  min-height: 100vh;
  /* App.vue 已改用 TV token；本页仍大量引用旧名，在此统一映射 */
  --apple-bg: var(--bg);
  --apple-card: var(--surface);
  --apple-text2: var(--text-2);
  --apple-text3: var(--text-3);
  --apple-blue: var(--brand);
  --apple-blue-light: var(--brand-alpha);
  --apple-red: var(--down);
  --apple-green: var(--up);
  --apple-orange: #ff9800;
  --apple-indigo: var(--brand);
  --apple-gray: var(--text-3);
  --apple-gray2: var(--text-4);
  --apple-gray3: #8e8e93;
  --apple-gray4: var(--divider-hover);
  --apple-gray5: var(--divider);
  --apple-gray6: var(--surface-2);
  background: var(--apple-bg);
}

.navbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(255,255,255,0.78);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  padding: 10px 16px;
  padding-top: calc(10px + env(safe-area-inset-top));
  display: flex; align-items: flex-start; gap: 12px;
}
.nav-back {
  width: 30px; height: 30px; border-radius: 8px;
  background: var(--apple-gray6); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  margin-top: 2px;
}
.nav-back .icon { fill: var(--apple-text2); }
.nav-center { flex: 1; text-align: center; padding-right: 30px; }
.nav-title {
  font-size: 17px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
  letter-spacing: -0.41px;
}
.nav-sub {
  font-size: 11px; color: var(--apple-text3);
  margin-top: 2px; letter-spacing: 0.02em;
}

.container { padding: 16px; }

/* 参数卡片 */
.param-card {
  background: var(--apple-card);
  border-radius: 16px; padding: 18px;
  margin-bottom: 14px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.param-card-title {
  font-size: 13px; font-weight: 600; color: var(--apple-text3);
  letter-spacing: 0.5px; margin-bottom: 16px;
  display: flex; align-items: center; gap: 6px;
}
.param-item { margin-bottom: 20px; }
.param-item:last-child { margin-bottom: 0; }
.param-label { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.param-name { font-size: 15px; font-weight: 500; }
.param-value { font-size: 15px; font-weight: 600; color: var(--apple-blue); }
.param-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 22px;
  background: transparent;
  outline: none;
}
.param-slider::-webkit-slider-runnable-track {
  height: 6px;
  border-radius: 3px;
  background: var(--apple-gray5);
}
.param-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 20px;
  height: 20px;
  margin-top: -7px;
  border-radius: 50%;
  background: var(--apple-blue);
  border: 2px solid var(--apple-card);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
  cursor: pointer;
}
.param-slider::-moz-range-track {
  height: 6px;
  border-radius: 3px;
  background: var(--apple-gray5);
  border: none;
}
.param-slider::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--apple-blue);
  border: 2px solid var(--apple-card);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
  cursor: pointer;
}
.param-desc { font-size: 12px; color: var(--apple-text3); margin-top: 6px; }

/* 按钮 */
.scan-btn {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  width: 100%;
  background: var(--apple-blue);
  color: #fff;
  border: none;
  border-radius: 14px;
  padding: 16px;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.41px;
  cursor: pointer;
  transition: background 0.2s, transform 0.2s, box-shadow 0.2s;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(41, 98, 255, 0.35);
}
.scan-btn:disabled {
  background: var(--apple-gray3);
  color: rgba(255, 255, 255, 0.92);
  box-shadow: none;
  cursor: not-allowed;
  opacity: 0.85;
}
.scan-btn:active:not(:disabled) { transform: scale(0.98); }
.scan-btn .icon { fill: #fff; }
.spinning { animation: spin 0.8s linear infinite; }
.cancel-btn {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  width: 100%; background: var(--apple-red); color: #fff; border: none;
  border-radius: 14px; padding: 14px; font-size: 15px; font-weight: 600;
  cursor: pointer; transition: all 0.2s; margin-bottom: 12px;
}
.cancel-btn .icon { fill: #fff; }

/* 扫描进度 */
.scan-status-card {
  background: var(--apple-card);
  border-radius: 16px; padding: 18px;
  margin-bottom: 14px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
  display: none;
}
.scan-status-card.active { display: block; }
.scan-status-header { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.scan-status-dot {
  width: 10px; height: 10px; border-radius: 50%;
  background: var(--apple-blue);
  animation: pulse 1.5s infinite; flex-shrink: 0;
}
.scan-status-dot.error { background: var(--apple-red); animation: none; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
.scan-status-label { font-size: 15px; font-weight: 600; }
.scan-sector { font-size: 13px; color: var(--apple-text3); margin-top: 4px; }
.progress-bar {
  width: 100%; height: 6px; border-radius: 3px;
  background: var(--apple-gray5); overflow: hidden; margin-top: 10px;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--apple-blue), var(--apple-indigo));
  border-radius: 3px; transition: width 0.3s ease;
}
.progress-text { font-size: 13px; color: var(--apple-text3); margin-top: 6px; text-align: right; }

/* 结果卡片 */
.results-card {
  background: var(--apple-card);
  border-radius: 16px; padding: 18px;
  margin-bottom: 14px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
  display: none;
}
.results-card.active { display: block; }
.results-header {
  font-size: 13px; font-weight: 600; color: var(--apple-text3);
  letter-spacing: 0.5px; margin-bottom: 8px;
  display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.results-time { margin-left: auto; font-size: 12px; font-weight: 400; }
.results-hint {
  width: 100%; font-size: 12px; color: var(--apple-text3);
  background: var(--apple-gray6); padding: 8px 10px; border-radius: 8px;
  display: none; margin: -4px 0 12px;
}
.results-hint.show { display: block; }

/* 视图切换 + 筛选条 */
.results-toolbar {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 14px; flex-wrap: wrap;
}
.filter-chips {
  flex: 1; min-width: 0;
  display: flex; flex-wrap: nowrap; gap: 8px;
  overflow-x: auto; -webkit-overflow-scrolling: touch;
  padding-bottom: 2px;
  scrollbar-width: none;
}
.filter-chips::-webkit-scrollbar { display: none; }
.filter-chip {
  flex-shrink: 0; border: none; cursor: pointer;
  padding: 6px 12px; border-radius: 20px;
  font-size: 13px; font-weight: 500;
  background: var(--apple-gray6); color: var(--apple-text2);
  transition: background 0.15s, color 0.15s;
}
.filter-chip.active {
  background: #FFEBEE; color: var(--apple-red); font-weight: 600;
}
.empty-inner {
  text-align: center; padding: 24px 12px; font-size: 14px; color: var(--apple-text3);
}

/* 收缩结果大卡 */
.squeeze-list { display: flex; flex-direction: column; gap: 12px; }
.squeeze-card {
  border-radius: 14px; padding: 14px 14px 12px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.06);
  cursor: pointer; transition: transform 0.12s, box-shadow 0.12s;
  border: 0.5px solid rgba(0,0,0,0.04);
}
.squeeze-card:active { transform: scale(0.99); }
.squeeze-card.tone-s { background: linear-gradient(180deg, #FFFBF0 0%, #FFF8E7 100%); }
.squeeze-card.tone-a { background: linear-gradient(180deg, #F8FAFC 0%, #F1F5F9 100%); }
.squeeze-card.tone-default { background: var(--apple-card); }

.squeeze-card-top {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 8px; margin-bottom: 12px;
}
.squeeze-left { flex: 1; min-width: 0; }
.squeeze-name-line { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.squeeze-name { font-size: 17px; font-weight: 700; letter-spacing: -0.3px; }
.squeeze-code { font-size: 13px; color: var(--apple-text3); font-weight: 500; }
.squeeze-sector {
  font-size: 11px; color: var(--apple-orange); margin-top: 4px;
  display: inline-block; padding: 2px 8px; border-radius: 6px;
  background: rgba(255,149,0,0.12); font-weight: 600;
}
.squeeze-price-block {
  display: flex; flex-direction: column; align-items: flex-end; gap: 6px;
  flex-shrink: 0;
}
.squeeze-price { font-size: 20px; font-weight: 700; letter-spacing: -0.5px; line-height: 1.1; }
.squeeze-pct-pill {
  font-size: 12px; font-weight: 700; padding: 3px 8px; border-radius: 8px;
  background: var(--apple-gray6);
}
.squeeze-pct-pill.up { background: #FFEBEE; color: var(--apple-red); }
.squeeze-pct-pill.down { background: #E8F5E9; color: var(--apple-green); }
.star-btn {
  width: 36px; height: 36px; border: none; border-radius: 10px;
  background: transparent; color: var(--apple-gray3);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; flex-shrink: 0;
}
.star-btn:active { background: var(--apple-gray6); }
.star-icon { width: 22px; height: 22px; }

/* 四格指标 */
.metric-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;
  margin-bottom: 12px;
}
.metric-cell {
  background: rgba(255,255,255,0.72);
  border-radius: 10px; padding: 8px 4px; text-align: center;
  border: 0.5px solid rgba(0,0,0,0.04);
}
.tone-default .metric-cell { background: var(--apple-gray6); }
.metric-val {
  display: flex; align-items: baseline; justify-content: center; gap: 2px;
  flex-wrap: wrap; min-height: 36px; align-content: center;
}
.metric-num { font-size: 15px; font-weight: 700; letter-spacing: -0.3px; }
.metric-grade { font-size: 11px; font-weight: 700; color: var(--apple-blue); }
.metric-label { font-size: 10px; color: var(--apple-text3); margin-top: 2px; font-weight: 500; }

/* 底部标签 pill */
.squeeze-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.pill-tag {
  font-size: 11px; font-weight: 600; padding: 4px 8px; border-radius: 10px;
}
.pill-default { background: var(--apple-gray6); color: var(--apple-text2); }
.pill-leader { background: #FFF3E0; color: var(--apple-orange); }
.pill-grade-s { background: #FFE082; color: #6D4C00; }
.pill-grade-a { background: #E3F2FD; color: #1565C0; }
.pill-cmf { background: #E8F5E9; color: #2E7D32; }
.pill-ind { background: #F3E5F5; color: #7B1FA2; }
.pill-trend { background: #E3F2FD; color: #0277BD; }
.pill-vol { background: #FFEBEE; color: #C62828; }
.pill-pioneer { background: #FCE4EC; color: #AD1457; }

/* 历史记录 */
.history-section { margin-top: 4px; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.section-title { font-size: 17px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.section-title .icon { fill: var(--apple-gray); }
.refresh-btn {
  border: none; background: none; color: var(--apple-blue); font-size: 13px;
  cursor: pointer; display: flex; align-items: center; gap: 4px;
}
.refresh-btn .icon { fill: var(--apple-blue); }
.history-list { display: flex; flex-direction: column; gap: 10px; }
.history-card {
  background: var(--apple-card); border-radius: 14px; padding: 14px 16px;
  display: flex; align-items: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  cursor: pointer; transition: all 0.2s;
}
.history-card:active { background: var(--apple-gray6); transform: scale(0.98); }
.history-info { flex: 1; min-width: 0; }
.history-date {
  font-size: 15px; font-weight: 600; display: flex; align-items: center; gap: 6px;
}
.history-date .icon { fill: var(--apple-blue); }
.history-meta {
  display: flex; flex-wrap: wrap; gap: 6px;
  font-size: 12px; color: var(--apple-text3); margin-top: 4px;
}
.history-status {
  padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 600;
}
.history-status.completed { background: #E8F5E9; color: var(--apple-green); }
.history-status.scanning { background: var(--apple-blue-light); color: var(--apple-blue); }
.history-status.error { background: #FFEBEE; color: var(--apple-red); }
.history-status.cancelled { background: var(--apple-gray6); color: var(--apple-gray); }
.history-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.delete-btn {
  width: 32px; height: 32px; border-radius: 8px;
  border: none; background: #FFEBEE; color: var(--apple-red);
  display: flex; align-items: center; justify-content: center; cursor: pointer;
  transition: all 0.2s;
}
.delete-btn:active { transform: scale(0.9); background: #FFCDD2; }
.delete-btn .icon { fill: var(--apple-red); width: 16px; height: 16px; }

/* 通用 */
.loading { text-align: center; padding: 60px 20px; color: var(--apple-gray); }
.spinner {
  width: 28px; height: 28px; border: 2.5px solid var(--apple-gray5);
  border-top-color: var(--apple-blue); border-radius: 50%;
  animation: spin 0.7s linear infinite; margin: 0 auto 14px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { text-align: center; padding: 30px 20px; color: var(--apple-red); font-size: 14px; }
.empty {
  text-align: center; padding: 40px 20px; color: var(--apple-gray); font-size: 14px;
}
.empty-icon { font-size: 36px; margin-bottom: 10px; display: block; opacity: 0.4; }

/* 板块 Tab 行 */
.sector-tabs-scroll {
  display: flex; gap: 8px;
  overflow-x: auto; -webkit-overflow-scrolling: touch;
  padding-bottom: 2px; margin-bottom: 12px;
  scrollbar-width: none;
}
.sector-tabs-scroll::-webkit-scrollbar { display: none; }
.sector-tab {
  flex-shrink: 0; border: none; cursor: pointer;
  background: var(--apple-gray6); border-radius: 10px;
  padding: 8px 14px; min-width: 80px; text-align: center;
  transition: all 0.15s;
}
.sector-tab.active { background: #1a1a2e; }
.sector-tab-name { font-size: 13px; font-weight: 700; color: var(--apple-text2); }
.sector-tab.active .sector-tab-name { color: #fff; }
.sector-tab-change { font-size: 11px; font-weight: 600; margin-top: 2px; }
.sector-tab-change.up { color: var(--apple-red); }
.sector-tab-change.down { color: var(--apple-green); }
.sector-tab.active .sector-tab-change.up { color: var(--apple-red); }
.sector-tab.active .sector-tab-change.down { color: #86e6a0; }

/* Toast */
.toast {
  position: fixed; bottom: 100px; left: 50%;
  transform: translateX(-50%);
  background: rgba(0,0,0,0.78); color: #fff; padding: 12px 24px;
  border-radius: 10px; font-size: 14px;
  z-index: 999; opacity: 0; transition: opacity 0.3s; pointer-events: none;
}
.toast.show { opacity: 1; }
.toast.success { background: rgba(52,199,89,0.9); }
.toast.error { background: rgba(255,59,48,0.9); }

/* 股票详情弹窗 */
.detail-modal { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); z-index: 200; }
.detail-modal.active { display: block; }
.detail-panel {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  background: var(--apple-bg);
  animation: slideIn 0.35s cubic-bezier(0.32, 0.72, 0, 1);
  display: flex; flex-direction: column;
  overflow: hidden;
}
@keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
.detail-header {
  background: rgba(255,255,255,0.78); backdrop-filter: saturate(180%) blur(20px);
  padding: 12px 16px; padding-top: calc(12px + env(safe-area-inset-top));
  display: flex; align-items: center; gap: 12px;
  border-bottom: 0.5px solid var(--apple-gray5);
  flex-shrink: 0;
}
.close-btn {
  width: 32px; height: 32px; background: var(--apple-gray6); border-radius: 50%;
  border: none; display: flex; align-items: center; justify-content: center; cursor: pointer;
}
.detail-title {
  flex: 1; font-size: 17px; font-weight: 700; display: flex; align-items: center; gap: 8px;
  letter-spacing: -0.41px;
}
.detail-title .icon { fill: var(--apple-orange); }
.goto-btn {
  display: flex; align-items: center; gap: 4px;
  background: var(--apple-blue); color: #fff; border: none;
  padding: 6px 14px; border-radius: 16px; font-size: 14px; font-weight: 600;
  cursor: pointer;
}
.goto-btn .icon { fill: #fff; }
.detail-star-btn {
  width: 36px; height: 36px; background: var(--apple-gray6); border-radius: 50%;
  border: none; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0;
}
.detail-star-btn .icon { width: 18px; height: 18px; fill: var(--apple-gray2); }
.detail-star-btn.active .icon { fill: #FF9500; }
.detail-content { flex: 1; overflow-y: auto; padding: 16px; }

.detail-price-card {
  background: var(--apple-card); border-radius: 16px; padding: 18px 18px 14px;
  margin-bottom: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.detail-price-main { display: flex; align-items: baseline; gap: 12px; margin-bottom: 8px; }
.detail-price { font-size: 36px; font-weight: 800; letter-spacing: -1px; }
.detail-pct { font-size: 20px; font-weight: 700; }
.detail-pct.up { color: var(--apple-red); }
.detail-pct.down { color: var(--apple-green); }
.detail-meta-row { display: flex; gap: 12px; flex-wrap: wrap; }
.detail-meta-item { font-size: 13px; color: var(--apple-text3); font-weight: 500; }

.detail-kline-card {
  margin-bottom: 12px;
}

.detail-kline-card .detail-kline-heading {
  margin-bottom: 6px;
}

.detail-score-card {
  background: var(--apple-card); border-radius: 16px; padding: 16px 18px;
  margin-bottom: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.04);
  display: flex; align-items: center; gap: 16px;
}
.detail-score-left { flex: 1; }
.detail-score-label { font-size: 12px; color: var(--apple-text3); margin-bottom: 4px; font-weight: 500; }
.detail-score-val { display: flex; align-items: baseline; gap: 8px; }
.detail-score-num { font-size: 28px; font-weight: 800; }
.detail-grade-badge {
  font-size: 12px; font-weight: 800; padding: 2px 8px; border-radius: 8px; color: #fff;
}
.detail-grade-badge.grade-s { background: linear-gradient(135deg, #FF9500, #FF3B30); }
.detail-grade-badge.grade-a { background: var(--apple-blue); }
.detail-grade-badge.grade-b { background: var(--apple-green); }
.detail-grade-badge.grade-c { background: var(--apple-gray); }
.detail-metrics-row { display: flex; gap: 12px; }
.detail-metric { text-align: center; }
.dm-val { font-size: 15px; font-weight: 700; display: block; }
.dm-label { font-size: 10px; color: var(--apple-text3); display: block; margin-top: 2px; }

.detail-tags-card {
  background: var(--apple-card); border-radius: 16px; padding: 14px 18px;
  margin-bottom: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.detail-section-label { font-size: 12px; color: var(--apple-text3); font-weight: 600; margin-bottom: 10px; letter-spacing: 0.5px; }
.detail-tags { display: flex; flex-wrap: wrap; gap: 6px; }

.detail-indicators-card {
  background: var(--apple-card); border-radius: 16px; padding: 14px 18px;
  margin-bottom: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.detail-ind-grid { display: flex; flex-direction: column; }
.detail-ind-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 0; border-bottom: 0.5px solid var(--apple-gray5);
}
.detail-ind-row:last-child { border-bottom: none; }
.di-key { font-size: 14px; color: var(--apple-text2); font-weight: 500; }
.di-val { font-size: 14px; font-weight: 600; }
.di-val.up { color: var(--apple-green); }
.di-val.mid { color: var(--apple-blue); }

.detail-goto-hint {
  background: var(--apple-card); border-radius: 16px; padding: 16px;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  font-size: 15px; font-weight: 600; color: var(--apple-blue);
  cursor: pointer; box-shadow: 0 2px 12px rgba(0,0,0,0.04);
  transition: background 0.15s;
}
.detail-goto-hint:active { background: var(--apple-gray6); }
.detail-goto-hint .icon { fill: var(--apple-blue); }
</style>
