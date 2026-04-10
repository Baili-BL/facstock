<template>
  <div class="bollinger-page">
    <header class="bb-header">
      <div class="bb-header__inner">
        <button type="button" class="bb-back" aria-label="返回" @click="$router.push('/strategy')">
          <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
        </button>
        <div class="bb-header__brand">
          <h1 class="bb-header__title">跟着量化基金经理买股票</h1>
        </div>
        <div class="bb-header__tools">
          <button type="button" class="bb-ghost-btn" @click="$router.push('/strategy/bollinger/history')">
            <svg class="icon" viewBox="0 0 24 24"><use href="#icon-history"/></svg>
            <span class="bb-ghost-btn__txt">历史记录</span>
          </button>
        </div>
      </div>
    </header>

    <main class="bb-main">
      <section class="bb-config">
        <div class="bb-config__head">
          <div>
            <h2 class="bb-config__title">扫描配置</h2>
            <p class="bb-config__hint">调整参数以发现技术形态</p>
          </div>
          <button type="button" class="bb-primary-pill" :disabled="scanning" @click="startScan">
            {{ scanning ? '启动中…' : '开始分析' }}
          </button>
        </div>
        <div class="bb-sliders">
          <div class="bb-slider-block">
            <div class="bb-slider-block__row">
              <label class="bb-slider-block__label">板块数量</label>
              <span class="bb-slider-block__val">{{ params.sectors }}</span>
            </div>
            <input
              type="range"
              class="bb-range"
              v-model.number="params.sectors"
              min="1"
              max="12"
              step="1"
              :style="{ '--range-fill': rangeFillSectors }"
            >
            <div class="bb-slider-block__ticks"><span>1</span><span>12</span></div>
          </div>
          <div class="bb-slider-block">
            <div class="bb-slider-block__row">
              <label class="bb-slider-block__label">挤压天数</label>
              <span class="bb-slider-block__val">{{ params.minDays }}</span>
            </div>
            <input
              type="range"
              class="bb-range"
              v-model.number="params.minDays"
              min="0"
              max="20"
              step="1"
              :style="{ '--range-fill': rangeFillMinDays }"
            >
            <div class="bb-slider-block__ticks"><span>0</span><span>20</span></div>
            <p class="bb-slider-block__hint">连续收缩天数下限，越高越严；无结果时可调低。</p>
          </div>
          <div class="bb-slider-block">
            <div class="bb-slider-block__row">
              <label class="bb-slider-block__label">分析周期</label>
              <span class="bb-slider-block__val">{{ params.period }}天</span>
            </div>
            <input
              type="range"
              class="bb-range"
              v-model.number="params.period"
              min="20"
              max="180"
              step="5"
              :style="{ '--range-fill': rangeFillPeriod }"
            >
            <div class="bb-slider-block__ticks"><span>20天</span><span>180天</span></div>
          </div>
          <div class="bb-slider-block">
            <div class="bb-slider-block__row">
              <label class="bb-slider-block__label">窄幅区间</label>
              <span class="bb-slider-block__val">{{ params.bbWidthMax }}%</span>
            </div>
            <input
              type="range"
              class="bb-range"
              v-model.number="params.bbWidthMax"
              min="5"
              max="50"
              step="5"
              :style="{ '--range-fill': rangeFillBbWidth }"
            >
            <div class="bb-slider-block__ticks"><span>5%</span><span>50%</span></div>
            <p class="bb-slider-block__hint">仅展示布林带宽度 ≤ 此值的股票。</p>
          </div>
        </div>
      </section>

      <button v-if="scanning" type="button" class="bb-cancel" @click="cancelScan">取消扫描</button>

      <div class="bb-progress" :class="{ 'bb-progress--on': scanning }">
        <div class="bb-progress__head">
          <span class="bb-progress__dot" :class="{ 'bb-progress__dot--err': scanError }"></span>
          <div>
            <div class="bb-progress__label">{{ scanCancelled ? '正在取消…' : '扫描中…' }}</div>
            <div class="bb-progress__sector">{{ currentSector }}</div>
          </div>
          <span class="bb-progress__pct">{{ progress }}%</span>
        </div>
        <div class="bb-progress__bar"><div class="bb-progress__fill" :style="{ width: progress + '%' }"></div></div>
      </div>

      <section class="bb-results-wrap">
        <div class="bb-results-meta">
          <span class="bb-results-meta__title">
            <svg class="icon bb-check-ic" viewBox="0 0 24 24"><use href="#icon-check"/></svg>
            扫描结果
          </span>
          <span class="bb-results-meta__time">{{ resultsTime || '—' }}</span>
        </div>
        <p v-if="scanning && resultsExist" class="bb-results-live">最近一次已完成 · 本次分析结束后自动更新</p>

        <div v-if="resultsLoading" class="bb-loading"><div class="bb-spinner"></div></div>
        <div v-else-if="resultsError" class="bb-error">{{ resultsError }}</div>
        <template v-else-if="resultsExist">
          <div class="bb-sector-pills">
            <button
              v-for="g in groupedResults"
              :key="g.sectorName"
              type="button"
              class="bb-pill"
              :class="{ 'bb-pill--on': selectedSector === g.sectorName }"
              @click="selectedSector = g.sectorName"
            >
              <span class="bb-pill__name">{{ g.sectorName }}</span>
              <span
                class="bb-pill__chg"
                :class="g.avgChange >= 0 ? 'bb-pill__chg--up' : 'bb-pill__chg--down'"
              >{{ g.avgChange >= 0 ? '+' : '' }}{{ g.avgChange.toFixed(2) }}%</span>
            </button>
          </div>

          <div class="bb-results-block">
            <div class="bb-results-block__head">
              <h2 class="bb-results-block__title">最新扫描结果</h2>
              <div class="bb-seg">
                <button
                  v-for="f in filterOptions"
                  :key="f.key"
                  type="button"
                  class="bb-seg__btn"
                  :class="{ 'bb-seg__btn--on': filterTab === f.key }"
                  @click="filterTab = f.key"
                >{{ f.label }}</button>
              </div>
            </div>

            <div v-if="displayStockList.length === 0" class="bb-empty-list">当前筛选条件下暂无股票</div>
            <div v-else class="bb-stock-list">
              <article
                v-for="s in displayStockList"
              :key="s.code + '-' + (s.sector_name || '')"
              class="bb-stock"
              :class="{ 'bb-stock--leader': truthy(s.is_leader) || Number(s.leader_rank) > 0 }"
                @click="showDetail(s)"
              >
                <button
                  type="button"
                  class="bb-stock__star"
                  :class="{ 'bb-stock__star--on': isInWatchlist(s.code) }"
                  :aria-label="isInWatchlist(s.code) ? '取消自选' : '加自选'"
                  @click.stop="toggleRowStar(s)"
                >
                  <svg class="icon" viewBox="0 0 24 24">
                    <use :href="isInWatchlist(s.code) ? '#icon-star' : '#icon-star-outline'"/>
                  </svg>
                </button>
                <div class="bb-stock__main">
                  <div class="bb-stock__title-row">
                    <span class="bb-stock__name">{{ s.name }}</span>
                    <span class="bb-stock__code">{{ s.code }}</span>
                  </div>
                  <div class="bb-stock__tags">
                    <span v-if="s.grade === 'S'" class="bb-tag bb-tag--s">S级</span>
                    <span v-else-if="s.grade === 'A'" class="bb-tag bb-tag--a">A级</span>
                    <span
                      v-for="tag in stockTagsForCard(s)"
                      :key="tag"
                      class="bb-stock-pill"
                      :class="tagClass(tag)"
                    >{{ tag }}</span>
                  </div>
                </div>
                <div class="bb-stock__stats">
                  <div class="bb-stock__price-block">
                    <div class="bb-stock__price">¥{{ fmtClose(s) }}</div>
                    <div class="bb-stock__pct" :class="fmtPct(s).cls">
                      <span class="bb-stock__pct-arrow" aria-hidden="true">{{ fmtPct(s).arrow }}</span>
                      {{ fmtPct(s).text }}
                    </div>
                  </div>
                  <div class="bb-stock__metrics">
                    <div class="bb-metric">
                      <span class="bb-metric__lbl">量化评分</span>
                      <span class="bb-metric__val">{{ fmtScore(s) }}</span>
                    </div>
                    <div class="bb-metric">
                      <span class="bb-metric__lbl">带宽值</span>
                      <span class="bb-metric__val">{{ fmtBandwidth(s) }}</span>
                    </div>
                    <div class="bb-metric">
                      <span class="bb-metric__lbl">收缩期</span>
                      <span class="bb-metric__val">{{ fmtSqueezeDays(s) }}</span>
                    </div>
                  </div>
                </div>
              </article>
            </div>

            <BollingerAiSummaryPanel
              v-if="currentScanId"
              variant="embed"
              :scan-id="currentScanId"
              :flat-stocks="flatStocks"
            />
          </div>
        </template>
        <div v-else class="bb-empty-page">
          <svg class="icon bb-empty-page__ic" viewBox="0 0 24 24"><use href="#icon-analytics"/></svg>
          暂无扫描结果
        </div>
      </section>
    </main>

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
import { ref, shallowRef, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { scan, watchlist } from '@/api/strategy.js'
import KlineChart from '@/components/KlineChart.vue'
import BollingerAiSummaryPanel from '@/components/BollingerAiSummaryPanel.vue'

const route = useRoute()
const router = useRouter()

// ─── 参数 ───
const params = ref({ sectors: 6, minDays: 3, period: 20, bbWidthMax: 20 })

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
/** 当前展示的扫描记录 id（用于 DeepSeek 小结缓存与「再解读」） */
const currentScanId = ref(null)

const filterTab = ref('all')
const selectedSector = ref('')
const selectedStock = ref(null)
const stockModalVisible = ref(false)
const stockStarred = ref(false)
/** 自选代码集合，与列表星标、详情星标同步 */
const watchlistCodes = shallowRef(new Set())
const filterOptions = [
  { key: 'all', label: '全部' },
  { key: 'S', label: 'S级' },
  { key: 'A', label: 'A级' },
  { key: 'volume', label: '放量' },
  { key: 'vol_price', label: '量价齐升' },
  { key: 'leader', label: '中军' },
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

// 滑杆左侧蓝色填充比例（与 min/max 对齐）
const rangeFillSectors = computed(() => {
  const v = params.value.sectors
  return `${((v - 1) / (12 - 1)) * 100}%`
})
const rangeFillMinDays = computed(() => `${(params.value.minDays / 20) * 100}%`)
const rangeFillPeriod = computed(() => {
  const v = params.value.period
  return `${((v - 20) / (180 - 20)) * 100}%`
})
const rangeFillBbWidth = computed(() => {
  const v = params.value.bbWidthMax
  return `${((v - 5) / (50 - 5)) * 100}%`
})

// 当前选中板块的股票：受 Tab 筛选；板块胶囊切换当前板块
const activeSectorStocks = computed(() => {
  if (!groupedResults.value.length) {
    selectedSector.value = ''
    return []
  }
  if (!selectedSector.value || !groupedResults.value.find(g => g.sectorName === selectedSector.value)) {
    selectedSector.value = groupedResults.value[0].sectorName
  }
  const group = groupedResults.value.find(g => g.sectorName === selectedSector.value)
  if (!group) return []
  let stocks = group.stocks
  if (filterTab.value === 'S') stocks = stocks.filter(s => s.grade === 'S')
  else if (filterTab.value === 'A') stocks = stocks.filter(s => s.grade === 'A')
  else if (filterTab.value === 'volume') {
    stocks = stocks.filter(s => truthy(s.is_volume_up) || truthy(s.is_volume_price_up) ||
      resolveStockTags(s).some(t => String(t).includes('放量')))
  } else if (filterTab.value === 'vol_price') {
    stocks = stocks.filter(s => truthy(s.is_volume_price_up) ||
      resolveStockTags(s).some(t => String(t).includes('量价齐升')))
  } else if (filterTab.value === 'leader') {
    stocks = stocks.filter(s => truthy(s.is_leader) || Number(s.leader_rank) > 0)
  }
  return stocks
})

const displayStockList = computed(() => {
  const stocks = activeSectorStocks.value
  const maxW = params.value.bbWidthMax
  return stocks.filter(s => {
    const w = Number(s.bb_width_pct) || 0
    return w <= maxW
  })
})
// groupedResults：始终基于全量未筛选数据，分组用于板块胶囊，Tab 切换不影响
const groupedResults = computed(() => {
  const map = {}
  for (const s of flatStocks.value) {
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
      const scoreA = (a.bestGrade === 'S' ? 2 : a.bestGrade === 'A' ? 1 : 0)
      const scoreB = (b.bestGrade === 'S' ? 2 : b.bestGrade === 'A' ? 1 : 0)
      if (scoreA !== scoreB) return scoreB - scoreA
      return b.avgScore - a.avgScore
    })
})

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

async function refreshWatchlistCodes() {
  try {
    const list = await watchlist.list()
    const next = new Set()
    for (const row of list || []) {
      const c = row?.code ?? row?.stock_code
      if (c) next.add(String(c))
    }
    watchlistCodes.value = next
  } catch {
    watchlistCodes.value = new Set()
  }
}

function isInWatchlist(code) {
  return Boolean(code && watchlistCodes.value.has(String(code)))
}

async function toggleRowStar(s) {
  const code = s?.code
  if (!code) return
  const name = (s.name && String(s.name).trim()) || String(code)
  try {
    if (isInWatchlist(code)) {
      await watchlist.remove(code)
      showToast('已取消自选', 'success')
    } else {
      await watchlist.add(code, name, s.sector_name)
      showToast('已加入自选', 'success')
    }
    await refreshWatchlistCodes()
    if (selectedStock.value?.code === code) {
      stockStarred.value = isInWatchlist(code)
    }
  } catch (e) {
    showToast(e.message || '操作失败', 'error')
  }
}

function stockTagsForCard(s) {
  return resolveStockTags(s).filter(t => !/^(S|A)级$/.test(String(t)))
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
      bb_width_max: params.value.bbWidthMax,
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
      currentScanId.value = null
      return
    }
    results.value = json.results
    currentScanId.value = json.scan_id ?? null
    resultsTime.value = json.last_update ? '更新于 ' + fmtDate(json.last_update) : ''
    filterTab.value = 'all'
    await refreshWatchlistCodes()
  } catch (e) {
    resultsError.value = e.message || '加载失败'
  } finally {
    resultsLoading.value = false
  }
}

async function viewDetail(id) {
  resultsLoading.value = true
  resultsError.value = ''
  try {
    const data = await scan.detail(id)
    if (!data) {
      showToast('该扫描不存在或暂无结果', 'error')
      return
    }
    results.value = data.results || {}
    currentScanId.value = data.id ?? null
    resultsTime.value = data.scan_time ? '历史扫描 · ' + fmtDate(data.scan_time) : '历史扫描'
    filterTab.value = 'all'
    await refreshWatchlistCodes()
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (e) {
    showToast('加载失败', 'error')
  } finally {
    resultsLoading.value = false
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
  if (truthy(s.cross_above_ma5)) tags.push('上穿M5')
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
  if (x.includes('上穿M5') || x.includes('M5')) return 'pill-ma5'
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
  if (!Number.isFinite(n)) return { text: '--', cls: '', arrow: '' }
  const up = n >= 0
  return {
    text: (up ? '+' : '') + n.toFixed(2) + '%',
    cls: up ? 'up' : 'down',
    arrow: up ? '▲' : '▼',
  }
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
  const { code, name, sector_name } = selectedStock.value
  const displayName = (name && String(name).trim()) || String(code)
  try {
    if (stockStarred.value) {
      await watchlist.remove(code)
      stockStarred.value = false
    } else {
      await watchlist.add(code, displayName, sector_name)
      stockStarred.value = true
    }
    await refreshWatchlistCodes()
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

// ─── 初始化 ───
async function init() {
  const qid = route.query.scan_id
  const openHistoryId =
    qid != null && String(qid).trim() !== '' ? Number(qid) : NaN

  try {
    const statusJson = await scan.status()
    if (statusJson.is_scanning) {
      scanning.value = true
      scanCancelled.value = false
      progress.value = statusJson.progress || 0
      currentSector.value = statusJson.current_sector || ''
      await startPolling()
    } else if (Number.isFinite(openHistoryId)) {
      await viewDetail(openHistoryId)
      router.replace({ path: '/strategy/bollinger', query: {} })
    } else {
      await Promise.all([loadResults(), refreshWatchlistCodes()])
    }
  } catch {
    if (Number.isFinite(openHistoryId)) {
      try {
        await viewDetail(openHistoryId)
      } catch {
        /* 忽略详情加载失败，仍进入主界面 */
      }
      router.replace({ path: '/strategy/bollinger', query: {} })
    } else {
      await Promise.all([loadResults(), refreshWatchlistCodes()])
    }
  }
}

onMounted(init)
onUnmounted(stopPolling)
</script>

<style scoped>
.bollinger-page {
  min-height: 100vh;
  padding-bottom: calc(24px + env(safe-area-inset-bottom));
  font-family: 'Inter', 'Manrope', 'PingFang SC', var(--font), system-ui, sans-serif;
  --bb-primary: #003ec7;
  --bb-cta: #0052ff;
  --bb-surface: #f9f9fe;
  --bb-surface-low: #f3f3f8;
  --bb-track: #e2e2e7;
  --bb-card: #ffffff;
  --bb-on: #1a1c1f;
  --bb-muted: #434656;
  --bb-outline: #737688;
  --bb-up: #059669;
  --bb-down: #dc2626;
  --apple-bg: var(--bb-surface);
  --apple-card: var(--bb-card);
  --apple-text2: var(--bb-on);
  --apple-text3: var(--bb-muted);
  --apple-blue: var(--bb-cta);
  --apple-blue-light: rgba(0, 82, 255, 0.14);
  --apple-red: var(--bb-down);
  --apple-green: var(--bb-up);
  --apple-orange: #ff9800;
  --apple-indigo: var(--bb-cta);
  --apple-gray: var(--bb-muted);
  --apple-gray2: var(--bb-muted);
  --apple-gray3: #8e8e93;
  --apple-gray4: #c3c5d9;
  --apple-gray5: var(--bb-track);
  --apple-gray6: var(--bb-surface-low);
  background: var(--bb-surface);
  color: var(--bb-on);
}

.icon { fill: currentColor; }

/* —— 顶栏 —— */
.bb-header {
  position: sticky;
  top: 0;
  z-index: 50;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(20px) saturate(1.2);
  -webkit-backdrop-filter: blur(20px) saturate(1.2);
  box-shadow: 0 1px 0 rgba(26, 28, 31, 0.06);
}
.bb-header__inner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  padding-top: calc(10px + env(safe-area-inset-top));
  max-width: 1200px;
  margin: 0 auto;
}
.bb-back {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 12px;
  background: var(--bb-surface-low);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--bb-on);
  flex-shrink: 0;
}
.bb-back .icon { width: 20px; height: 20px; fill: currentColor; }
.bb-header__brand {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.bb-header__title {
  margin: 0;
  font-family: 'Manrope', 'PingFang SC', sans-serif;
  font-size: 1.5rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.2;
  text-align: center;
}
.bb-header__tools { flex-shrink: 0; }
.bb-ghost-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  border: none;
  background: transparent;
  color: var(--bb-muted);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  padding: 8px 6px;
  border-radius: 12px;
}
.bb-ghost-btn .icon { width: 20px; height: 20px; fill: currentColor; }
.bb-ghost-btn__txt { display: none; }
@media (min-width: 480px) {
  .bb-ghost-btn__txt { display: inline; }
}

.bb-main {
  padding: 16px;
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* —— 扫描配置 —— */
.bb-config {
  background: var(--bb-card);
  border-radius: 24px;
  padding: 22px 20px 24px;
  box-shadow: 0 8px 24px rgba(26, 28, 31, 0.06);
}
.bb-config__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 24px;
}
.bb-config__title {
  margin: 0;
  font-family: 'Manrope', sans-serif;
  font-size: 1.25rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.bb-config__hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--bb-muted);
  opacity: 0.85;
}
.bb-primary-pill {
  border: none;
  cursor: pointer;
  flex-shrink: 0;
  padding: 10px 22px;
  border-radius: 9999px;
  font-size: 14px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, var(--bb-primary), var(--bb-cta));
  box-shadow: 0 4px 16px rgba(0, 62, 199, 0.25);
  transition: transform 0.15s, opacity 0.15s;
}
.bb-primary-pill:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  box-shadow: none;
}
.bb-primary-pill:active:not(:disabled) { transform: scale(0.98); }

.bb-sliders {
  display: grid;
  gap: 22px;
}
@media (min-width: 768px) {
  .bb-sliders { grid-template-columns: repeat(3, 1fr); gap: 28px; }
}
.bb-slider-block__row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 10px;
}
.bb-slider-block__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--bb-muted);
}
.bb-slider-block__val {
  font-family: 'Manrope', sans-serif;
  font-size: 1.125rem;
  font-weight: 800;
  color: var(--bb-primary);
}
.bb-slider-block__ticks {
  display: flex;
  justify-content: space-between;
  margin-top: 6px;
  font-size: 10px;
  font-weight: 600;
  color: var(--bb-outline);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.bb-slider-block__hint {
  margin: 8px 0 0;
  font-size: 11px;
  line-height: 1.45;
  color: var(--bb-muted);
}
.bb-range-dual-slider {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.bb-range-dual-slider {
  position: relative;
  height: 28px;
}
.bb-range-dual-slider__track {
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 4px;
  background: var(--bb-outline);
  border-radius: 2px;
  transform: translateY(-50%);
}
.bb-range-dual-slider__fill {
  position: absolute;
  top: 0;
  bottom: 0;
  background: var(--bb-primary);
  border-radius: 2px;
}
.bb-range-dual-slider__input {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: transparent;
  pointer-events: none;
  -webkit-appearance: none;
  appearance: none;
  margin: 0;
}
.bb-range-dual-slider__input::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  background: var(--bb-primary);
  border-radius: 50%;
  cursor: pointer;
  pointer-events: auto;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.bb-range-dual-slider__input::-moz-range-thumb {
  width: 16px;
  height: 16px;
  background: var(--bb-primary);
  border-radius: 50%;
  cursor: pointer;
  pointer-events: auto;
  border: none;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.bb-range-dual-slider__input::-webkit-slider-runnable-track {
  height: 4px;
  background: transparent;
}
.bb-range-dual-slider__input::-moz-range-track {
  height: 4px;
  background: transparent;
}

.bb-range {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 24px;
  background: transparent;
  outline: none;
}
.bb-range::-webkit-slider-runnable-track {
  height: 8px;
  border-radius: 9999px;
  background: linear-gradient(
    to right,
    var(--bb-cta) 0%,
    var(--bb-cta) var(--range-fill, 0%),
    var(--bb-track) var(--range-fill, 0%),
    var(--bb-track) 100%
  );
}
.bb-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 22px;
  height: 22px;
  margin-top: -7px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid var(--bb-primary);
  box-shadow: 0 2px 8px rgba(26, 28, 31, 0.12);
  cursor: pointer;
}
.bb-range::-moz-range-track {
  height: 8px;
  border-radius: 9999px;
  background: var(--bb-track);
  border: none;
}
.bb-range::-moz-range-progress {
  height: 8px;
  border-radius: 9999px;
  background: var(--bb-cta);
}
.bb-range::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid var(--bb-primary);
  box-shadow: 0 2px 8px rgba(26, 28, 31, 0.12);
  cursor: pointer;
}

.bb-cancel {
  width: 100%;
  border: none;
  border-radius: 16px;
  padding: 14px;
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  background: var(--bb-down);
  cursor: pointer;
}

.bb-progress {
  display: none;
  background: var(--bb-card);
  border-radius: 24px;
  padding: 18px 20px;
  box-shadow: 0 8px 24px rgba(26, 28, 31, 0.06);
}
.bb-progress--on { display: block; }
.bb-progress__head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.bb-progress__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--bb-cta);
  flex-shrink: 0;
  animation: bb-pulse 1.4s ease-in-out infinite;
}
.bb-progress__dot--err {
  background: var(--bb-down);
  animation: none;
}
@keyframes bb-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
.bb-progress__head > div { flex: 1; min-width: 0; }
.bb-progress__label { font-size: 15px; font-weight: 700; }
.bb-progress__sector { font-size: 13px; color: var(--bb-muted); margin-top: 4px; }
.bb-progress__pct {
  font-size: 13px;
  font-weight: 700;
  color: var(--bb-muted);
}
.bb-progress__bar {
  margin-top: 14px;
  height: 8px;
  border-radius: 9999px;
  background: var(--bb-track);
  overflow: hidden;
}
.bb-progress__fill {
  height: 100%;
  border-radius: 9999px;
  background: linear-gradient(90deg, var(--bb-primary), var(--bb-cta));
  transition: width 0.35s ease;
}

/* —— 扫描结果区 —— */
.bb-results-wrap { display: flex; flex-direction: column; gap: 12px; }
.bb-results-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 2px;
}
.bb-results-meta__title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  color: var(--bb-muted);
}
.bb-check-ic { width: 18px; height: 18px; fill: var(--bb-up); }
.bb-results-meta__time { font-size: 11px; color: var(--bb-outline); }
.bb-results-live {
  margin: 0;
  font-size: 12px;
  color: var(--bb-muted);
  background: var(--bb-surface-low);
  padding: 10px 14px;
  border-radius: 16px;
}
.bb-loading { text-align: center; padding: 48px 20px; }
.bb-spinner {
  width: 32px;
  height: 32px;
  margin: 0 auto;
  border: 3px solid var(--bb-track);
  border-top-color: var(--bb-cta);
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
}
.bb-error {
  text-align: center;
  padding: 32px 16px;
  color: var(--bb-down);
  font-size: 14px;
}
.bb-empty-page {
  text-align: center;
  padding: 40px 16px;
  color: var(--bb-muted);
  font-size: 14px;
}
.bb-empty-page__ic {
  width: 40px;
  height: 40px;
  margin: 0 auto 12px;
  display: block;
  opacity: 0.35;
  fill: var(--bb-outline);
}

.bb-sector-pills {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 6px;
  margin: 0 -4px 14px;
  scrollbar-width: thin;
  scrollbar-color: var(--bb-track) transparent;
}
.bb-sector-pills::-webkit-scrollbar { height: 3px; }
.bb-sector-pills::-webkit-scrollbar-thumb {
  background: var(--bb-track);
  border-radius: 10px;
}
.bb-pill {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border-radius: 9999px;
  border: 1px solid rgba(195, 197, 217, 0.35);
  background: var(--bb-card);
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(26, 28, 31, 0.04);
  transition: background 0.15s, border-color 0.15s;
}
.bb-pill--on {
  background: #0f172a;
  border-color: #0f172a;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.2);
}
.bb-pill__name {
  font-size: 12px;
  font-weight: 800;
  color: var(--bb-muted);
  white-space: nowrap;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bb-pill--on .bb-pill__name { color: #fff; }
.bb-pill__chg { font-size: 12px; font-weight: 800; }
.bb-pill__chg--up { color: #f23645; }
.bb-pill__chg--down { color: #089981; }
.bb-pill--on .bb-pill__chg--up { color: #fb7185; }
.bb-pill--on .bb-pill__chg--down { color: #34d399; }

.bb-results-block { padding-top: 20px; }

.bb-results-block__head {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
@media (min-width: 640px) {
  .bb-results-block__head {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }
}
.bb-results-block__title {
  margin: 0;
  font-family: 'Manrope', sans-serif;
  font-size: 1.25rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.bb-seg {
  display: flex;
  flex-wrap: nowrap;
  gap: 4px;
  padding: 4px;
  border-radius: 18px;
  background: var(--bb-surface-low);
  overflow-x: auto;
  max-width: 100%;
}
.bb-seg__btn {
  flex: 1 0 auto;
  border: none;
  border-radius: 14px;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 700;
  color: var(--bb-muted);
  background: transparent;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s, box-shadow 0.15s;
}
.bb-seg__btn--on {
  background: var(--bb-card);
  color: var(--bb-cta);
  box-shadow: 0 2px 8px rgba(26, 28, 31, 0.08);
}

.bb-empty-list {
  text-align: center;
  padding: 36px 16px;
  font-size: 14px;
  color: var(--bb-muted);
}

.bb-stock-list { display: flex; flex-direction: column; gap: 12px; }

.bb-stock {
  position: relative;
  background: var(--bb-card);
  border-radius: 24px;
  padding: 20px 18px 18px;
  box-shadow: 0 8px 24px rgba(26, 28, 31, 0.06);
  cursor: pointer;
  transition: box-shadow 0.2s, transform 0.15s;
}
.bb-stock:active { transform: scale(0.995); }
.bb-stock:hover { box-shadow: 0 12px 32px rgba(0, 62, 199, 0.08); }
.bb-stock--leader {
  border: 1.5px solid #d4a574;
  box-shadow: 0 8px 24px rgba(180, 120, 40, 0.1), inset 0 0 0 1px rgba(212, 165, 116, 0.12);
}

.bb-stock__star {
  position: absolute;
  top: 18px;
  right: 16px;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 12px;
  background: transparent;
  color: var(--bb-outline);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.bb-stock__star .icon { width: 22px; height: 22px; }
.bb-stock__star--on { color: #f59e0b; }
.bb-stock__star--on .icon { fill: #fbbf24; stroke: none; }

.bb-stock__main { padding-right: 40px; margin-bottom: 16px; }
.bb-stock__title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.bb-stock__name {
  font-family: 'Manrope', sans-serif;
  font-size: 1.25rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.bb-stock__code {
  font-size: 11px;
  font-weight: 700;
  color: var(--bb-outline);
  letter-spacing: 0.04em;
}
.bb-stock__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.bb-tag {
  font-size: 10px;
  font-weight: 800;
  padding: 4px 10px;
  border-radius: 9999px;
}
.bb-tag--s { background: #952200; color: #fff; }
.bb-tag--a { background: #dde1ff; color: #0038b6; }

.bb-stock-pill {
  font-size: 10px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 9999px;
}
.bb-stock-pill.pill-default { background: var(--bb-surface-low); color: var(--bb-on); }
.bb-stock-pill.pill-leader { background: #fff3e0; color: #e65100; }
.bb-stock-pill.pill-grade-s { background: #ffe082; color: #6d4c00; }
.bb-stock-pill.pill-grade-a { background: #e3f2fd; color: #1565c0; }
.bb-stock-pill.pill-cmf { background: #e8f5e9; color: #2e7d32; }
.bb-stock-pill.pill-ind { background: #f3e5f5; color: #7b1fa2; }
.bb-stock-pill.pill-trend { background: #e3f2fd; color: #0277bd; }
.bb-stock-pill.pill-vol { background: #ffebee; color: #c62828; }
.bb-stock-pill.pill-pioneer { background: #fce4ec; color: #ad1457; }
.bb-stock-pill.pill-ma5 { background: #fef3c7; color: #b45309; }

/* 参考稿：左侧价格+涨跌（左对齐）| 竖线 | 右侧三列指标（标签在上、数值在下） */
.bb-stock__stats {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 16px;
  margin-top: 4px;
}
.bb-stock__price-block {
  flex: 0 0 auto;
  text-align: left;
  min-width: 5.5rem;
}
.bb-stock__price {
  font-family: 'Manrope', sans-serif;
  font-size: 1.625rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.1;
  color: var(--bb-on);
}
.bb-stock__pct {
  margin-top: 6px;
  font-size: 14px;
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 4px;
}
.bb-stock__pct-arrow {
  font-size: 11px;
  line-height: 1;
  transform: scale(0.95);
}
.bb-stock__pct.up { color: #16a34a; }
.bb-stock__pct.down { color: var(--bb-down); }

.bb-stock__metrics {
  flex: 1;
  min-width: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px 12px;
  padding-left: 16px;
  border-left: 1px solid #ededf2;
  align-self: stretch;
  align-items: center;
}
.bb-metric {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.bb-metric__lbl {
  display: block;
  font-size: 11px;
  font-weight: 500;
  color: #787b86;
  line-height: 1.2;
}
.bb-metric__val {
  font-size: 15px;
  font-weight: 800;
  color: var(--bb-on);
  line-height: 1.2;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

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
.detail-tags .pill-tag {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 10px;
}
.detail-tags .pill-ma5 { background: #fef3c7; color: #b45309; }

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
