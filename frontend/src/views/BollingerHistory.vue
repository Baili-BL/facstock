<template>
  <div class="bbh-page">
    <!-- 顶栏：玻璃拟态，对齐设计稿 -->
    <nav class="bbh-topbar">
      <button type="button" class="bbh-icon-btn" aria-label="返回" @click="$router.push('/strategy/bollinger')">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <h2 class="bbh-nav-title">历史记录</h2>
      <div class="bbh-topbar__spacer" aria-hidden="true" />
    </nav>

    <main class="bbh-main">
      <header class="bbh-head">
        <div>
          <h1 class="bbh-h1">历史记录</h1>
          <p class="bbh-desc">
            查看并审计基于布林带收缩策略（Bollinger Squeeze Strategy）及热点行业参数的自动市场扫描记录。
          </p>
        </div>
        <button
          type="button"
          class="bbh-filter-btn"
          :class="{ 'bbh-filter-btn--on': filterModalActive }"
          title="时间筛选"
          aria-label="打开时间筛选"
          @click="openFilterModal"
        >
          <svg class="icon" viewBox="0 0 24 24"><use href="#icon-calendar"/></svg>
          <span v-if="filterModalActive" class="bbh-filter-dot" aria-hidden="true" />
        </button>
      </header>

      <div class="bbh-search-wrap">
        <svg class="icon bbh-search-ic" viewBox="0 0 24 24"><use href="#icon-search"/></svg>
        <input
          v-model.trim="searchQuery"
          type="search"
          class="bbh-search"
          placeholder="搜索行业或参数..."
          autocomplete="off"
        >
      </div>

      <div v-if="loading" class="bbh-state bbh-state--load"><div class="bbh-spinner" /></div>
      <div v-else-if="error" class="bbh-state bbh-state--err">{{ error }}</div>
      <div v-else-if="filteredList.length === 0" class="bbh-state bbh-state--empty">
        <svg class="icon bbh-empty-ic" viewBox="0 0 24 24"><use href="#icon-history"/></svg>
        暂无匹配记录
      </div>
      <div v-else class="bbh-list">
        <article
          v-for="rec in filteredList"
          :key="rec.id"
          class="bbh-card"
        >
          <div class="bbh-card__lead">
            <div
              class="bbh-card__icon"
              :class="rec.status === 'scanning' ? 'bbh-card__icon--pulse' : 'bbh-card__icon--done'"
            >
              <svg v-if="rec.status === 'scanning'" class="icon" viewBox="0 0 24 24"><use href="#icon-analytics"/></svg>
              <svg v-else class="icon" viewBox="0 0 24 24"><use href="#icon-history"/></svg>
            </div>
            <div class="bbh-card__time">
              <p class="bbh-k">扫描时间</p>
              <p class="bbh-v">{{ fmtDate(rec.scan_time) }}</p>
            </div>
          </div>
          <div class="bbh-card__body">
            <div class="bbh-card__grid">
              <div>
                <p class="bbh-k">目标板块</p>
                <p class="bbh-v2">{{ targetSectorText(rec) }}</p>
              </div>
              <div>
                <p class="bbh-k">扫描参数</p>
                <p class="bbh-v2">{{ paramLine(rec) }}</p>
              </div>
            </div>
            <div class="bbh-card__actions">
              <button
                v-if="rec.status === 'completed'"
                type="button"
                class="bbh-link bbh-link--primary"
                @click="goDetail(rec.id)"
              >查看详情</button>
              <button type="button" class="bbh-link bbh-link--danger" @click="onDelete(rec.id)">删除</button>
            </div>
          </div>
        </article>
      </div>

      <!-- 摘要区：本周统计 + 活动警报占位 -->
      <div class="bbh-bento">
        <div class="bbh-bento__perf">
          <div>
            <h3 class="bbh-bento__h">本周表现</h3>
            <p class="bbh-bento__p">
              本周您已成功执行 <strong>{{ weekCompletedCount }}</strong> 次已完成扫描。单次耗时随板块与成分股规模变化，系统未汇总平均耗时。
            </p>
          </div>
          <div class="bbh-bars" aria-hidden="true">
            <span /><span /><span /><span /><span />
          </div>
        </div>
        <div class="bbh-bento__alert">
          <span class="bbh-bento__num">—</span>
          <span class="bbh-bento__lbl">活动警报</span>
          <button type="button" class="bbh-bento__link" @click="onManageAlerts">管理警报</button>
        </div>
      </div>
    </main>

    <!-- 新建扫描：进入主扫描页 -->
    <button type="button" class="bbh-fab" aria-label="新建扫描" @click="$router.push('/strategy/bollinger')">
      <svg class="icon" viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
    </button>

    <div v-if="toastVisible" class="bbh-toast" :class="'bbh-toast--' + toastType">{{ toastMsg }}</div>

    <!-- 时间筛选弹窗 -->
    <div
      v-if="filterModalVisible"
      class="bbh-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="bbh-filter-title"
      @click.self="closeFilterModal"
    >
      <div class="bbh-modal__panel" @click.stop>
        <div class="bbh-modal__head">
          <h3 id="bbh-filter-title" class="bbh-modal__title">筛选条件</h3>
          <button type="button" class="bbh-modal__close" aria-label="关闭" @click="closeFilterModal">
            <svg class="icon" viewBox="0 0 24 24"><use href="#icon-cancel"/></svg>
          </button>
        </div>
        <div class="bbh-modal__body">
          <p class="bbh-modal__sec-label">扫描时间</p>
          <div class="bbh-modal__dates">
            <label class="bbh-date-field">
              <span class="bbh-date-field__lbl">开始日期</span>
              <input v-model="draftDateFrom" type="date" class="bbh-date-input">
            </label>
            <label class="bbh-date-field">
              <span class="bbh-date-field__lbl">结束日期</span>
              <input v-model="draftDateTo" type="date" class="bbh-date-input">
            </label>
          </div>
          <p class="bbh-modal__hint">开始、结束可只填一侧或都填；均留空则不按日期筛选。</p>

          <p class="bbh-modal__sec-label bbh-modal__sec-label--mt">时间快捷</p>
          <div class="bbh-time-card-grid" role="group" aria-label="时间快捷">
            <button
              v-for="item in visibleTimeShortcuts"
              :key="item.id"
              type="button"
              class="bbh-time-card"
              @click="applyTimeShortcut(item.id)"
            >{{ item.label }}</button>
          </div>
          <button
            v-if="hasMoreTimeShortcuts"
            type="button"
            class="bbh-load-more"
            @click="expandTimeShortcuts"
          >加载更多</button>
        </div>
        <div class="bbh-modal__foot">
          <button type="button" class="bbh-modal__btn bbh-modal__btn--ghost" @click="resetFilterDraft">重置</button>
          <button type="button" class="bbh-modal__btn bbh-modal__btn--primary" @click="applyFilterModal">确定</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { scan } from '@/api/strategy.js'

const router = useRouter()

const rawList = ref([])
const loading = ref(true)
const error = ref('')
const searchQuery = ref('')

/** 已生效的日期筛选 */
const dateFrom = ref('')
const dateTo = ref('')

/** 弹窗内草稿 */
const filterModalVisible = ref(false)
const draftDateFrom = ref('')
const draftDateTo = ref('')

/** 时间快捷：默认展示条数，超出则「加载更多」 */
const TIME_SHORTCUT_PAGE = 5
const TIME_SHORTCUT_PRESETS = [
  { id: 'today', label: '今天' },
  { id: 'yesterday', label: '昨天' },
  { id: 'last7', label: '近 7 天' },
  { id: 'last30', label: '近 30 天' },
  { id: 'thisWeek', label: '本周' },
  { id: 'lastWeek', label: '上周' },
  { id: 'thisMonth', label: '本月' },
  { id: 'lastMonth', label: '上月' },
  { id: 'thisQuarter', label: '本季度' },
  { id: 'lastQuarter', label: '上季度' },
  { id: 'thisYear', label: '今年' },
  { id: 'lastYear', label: '去年' },
]
const showAllTimeShortcuts = ref(false)

const visibleTimeShortcuts = computed(() => {
  const all = TIME_SHORTCUT_PRESETS
  if (showAllTimeShortcuts.value || all.length <= TIME_SHORTCUT_PAGE) return all
  return all.slice(0, TIME_SHORTCUT_PAGE)
})

const hasMoreTimeShortcuts = computed(
  () =>
    TIME_SHORTCUT_PRESETS.length > TIME_SHORTCUT_PAGE &&
    !showAllTimeShortcuts.value
)

const filterModalActive = computed(() => Boolean(dateFrom.value || dateTo.value))

const toastMsg = ref('')
const toastType = ref('')
const toastVisible = ref(false)
let toastTimer = null

function showToast(msg, type = '') {
  toastMsg.value = msg
  toastType.value = type
  toastVisible.value = true
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastVisible.value = false }, 2200)
}

function fmtDate(dt) {
  if (!dt) return '—'
  const d = new Date(dt)
  if (Number.isNaN(d.getTime())) return String(dt)
  const pad = n => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function statusLabel(s) {
  const map = { completed: '已完成', scanning: '扫描中', error: '失败', cancelled: '已取消' }
  return map[s] || s || '未知'
}

function paramLine(rec) {
  const p = rec.params || {}
  const sectors = p.sectors ?? p.top_sectors
  const minDays = p.min_days
  const period = p.period
  const parts = []
  if (sectors != null) parts.push(`板块数 ${sectors}`)
  if (minDays != null) parts.push(`挤压≥${minDays}天`)
  if (period != null) parts.push(`周期${period}天`)
  return parts.length ? parts.join(' · ') : '默认参数'
}

function targetSectorText(rec) {
  const hs = rec.hot_sectors
  if (hs && hs.length) return hs.map(s => s.name || s).filter(Boolean).join(', ')
  if (rec.sector_count) return `共 ${rec.sector_count} 个板块（扫描完成后展示名称）`
  return '—'
}

function recSearchBlob(rec) {
  return [
    targetSectorText(rec),
    paramLine(rec),
    statusLabel(rec.status),
    fmtDate(rec.scan_time),
    String(rec.stock_count || ''),
  ].join(' ').toLowerCase()
}

function recordScanDate(rec) {
  if (!rec.scan_time) return null
  const d = new Date(rec.scan_time)
  return Number.isNaN(d.getTime()) ? null : d
}

/** 按本地日历日，闭区间 [from, to]；任一端留空则不限制该侧 */
function inSelectedDateRange(d, fromStr, toStr) {
  if (!fromStr && !toStr) return true
  if (!d) return false
  if (fromStr) {
    const [y, m, day] = fromStr.split('-').map(Number)
    const start = new Date(y, m - 1, day, 0, 0, 0, 0)
    if (d < start) return false
  }
  if (toStr) {
    const [y, m, day] = toStr.split('-').map(Number)
    const end = new Date(y, m - 1, day, 23, 59, 59, 999)
    if (d > end) return false
  }
  return true
}

function expandTimeShortcuts() {
  showAllTimeShortcuts.value = true
}

function openFilterModal() {
  draftDateFrom.value = dateFrom.value
  draftDateTo.value = dateTo.value
  showAllTimeShortcuts.value = false
  filterModalVisible.value = true
}

function closeFilterModal() {
  filterModalVisible.value = false
}

function pad2(n) {
  return String(n).padStart(2, '0')
}

function fmtYMD(d) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

/** 本周一（本地），不含时间分量 */
function startOfMonday(d) {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7))
  return x
}

/** 时间快捷卡片：写入草稿开始/结束日期 */
function applyTimeShortcut(id) {
  const today = new Date()
  const set = (from, to) => {
    draftDateFrom.value = from
    draftDateTo.value = to
  }

  switch (id) {
    case 'today':
      set(fmtYMD(today), fmtYMD(today))
      break
    case 'yesterday': {
      const y = new Date(today)
      y.setDate(y.getDate() - 1)
      const f = fmtYMD(y)
      set(f, f)
      break
    }
    case 'last7': {
      const s = new Date(today)
      s.setDate(s.getDate() - 6)
      set(fmtYMD(s), fmtYMD(today))
      break
    }
    case 'last30': {
      const s = new Date(today)
      s.setDate(s.getDate() - 29)
      set(fmtYMD(s), fmtYMD(today))
      break
    }
    case 'thisWeek': {
      const s = startOfMonday(today)
      set(fmtYMD(s), fmtYMD(today))
      break
    }
    case 'lastWeek': {
      const thisMon = startOfMonday(today)
      const lastMon = new Date(thisMon)
      lastMon.setDate(lastMon.getDate() - 7)
      const lastSun = new Date(thisMon)
      lastSun.setDate(lastSun.getDate() - 1)
      set(fmtYMD(lastMon), fmtYMD(lastSun))
      break
    }
    case 'thisMonth': {
      const s = new Date(today.getFullYear(), today.getMonth(), 1)
      set(fmtYMD(s), fmtYMD(today))
      break
    }
    case 'lastMonth': {
      const lastPrev = new Date(today.getFullYear(), today.getMonth(), 0)
      const firstPrev = new Date(lastPrev.getFullYear(), lastPrev.getMonth(), 1)
      set(fmtYMD(firstPrev), fmtYMD(lastPrev))
      break
    }
    case 'thisQuarter': {
      const q0 = Math.floor(today.getMonth() / 3) * 3
      const s = new Date(today.getFullYear(), q0, 1)
      set(fmtYMD(s), fmtYMD(today))
      break
    }
    case 'lastQuarter': {
      let y = today.getFullYear()
      let q = Math.floor(today.getMonth() / 3)
      if (q === 0) {
        y -= 1
        q = 3
      } else {
        q -= 1
      }
      const sm = q * 3
      const s = new Date(y, sm, 1)
      const e = new Date(y, sm + 3, 0)
      set(fmtYMD(s), fmtYMD(e))
      break
    }
    case 'thisYear': {
      const s = new Date(today.getFullYear(), 0, 1)
      set(fmtYMD(s), fmtYMD(today))
      break
    }
    case 'lastYear': {
      const y = today.getFullYear() - 1
      const s = new Date(y, 0, 1)
      const e = new Date(y, 11, 31)
      set(fmtYMD(s), fmtYMD(e))
      break
    }
    default:
      break
  }
}

function applyFilterModal() {
  const a = draftDateFrom.value
  const b = draftDateTo.value
  if (a && b && a > b) {
    showToast('开始日期不能晚于结束日期', 'err')
    return
  }
  dateFrom.value = a
  dateTo.value = b
  filterModalVisible.value = false
}

function resetFilterDraft() {
  draftDateFrom.value = ''
  draftDateTo.value = ''
  dateFrom.value = ''
  dateTo.value = ''
  showAllTimeShortcuts.value = false
  filterModalVisible.value = false
  showToast('已清空筛选', 'ok')
}

const filteredList = computed(() => {
  let list = rawList.value
  if (dateFrom.value || dateTo.value) {
    list = list.filter(r =>
      inSelectedDateRange(recordScanDate(r), dateFrom.value, dateTo.value)
    )
  }
  const q = searchQuery.value.toLowerCase()
  if (!q) return list
  return list.filter(r => recSearchBlob(r).includes(q))
})

/** 本周（周一至周日）内完成的扫描次数 */
const weekCompletedCount = computed(() => {
  const now = new Date()
  const monday = new Date(now)
  const wd = monday.getDay()
  const offset = wd === 0 ? -6 : 1 - wd
  monday.setDate(monday.getDate() + offset)
  monday.setHours(0, 0, 0, 0)
  const nextMon = new Date(monday)
  nextMon.setDate(nextMon.getDate() + 7)
  return rawList.value.filter(r => {
    if (r.status !== 'completed') return false
    const t = new Date(r.scan_time)
    return !Number.isNaN(t.getTime()) && t >= monday && t < nextMon
  }).length
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await scan.history(100)
    rawList.value = Array.isArray(data) ? data : []
  } catch (e) {
    error.value = e.message || '加载失败'
    rawList.value = []
  } finally {
    loading.value = false
  }
}

function goDetail(id) {
  router.push({ path: `/strategy/bollinger/scan/${id}` })
}

async function onDelete(id) {
  if (!confirm('确定删除这条扫描记录？')) return
  try {
    await scan.delete(id)
    showToast('删除成功', 'ok')
    await load()
  } catch (e) {
    showToast(e.message || '删除失败', 'err')
  }
}

function onManageAlerts() {
  router.push('/strategy/bollinger/alerts')
}

onMounted(load)
</script>

<style scoped>
.bbh-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: #f9f9fe;
  color: #1a1c1f;
  font-family: 'Inter', 'Manrope', 'PingFang SC', var(--font), system-ui, sans-serif;
  padding-bottom: calc(120px + env(safe-area-inset-bottom, 0px));
}

.bbh-topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  display: grid;
  grid-template-columns: 40px 1fr 40px;
  align-items: center;
  min-height: 56px;
  padding: 8px 12px;
  padding-top: calc(8px + env(safe-area-inset-top, 0px));
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 1px 0 rgba(26, 28, 31, 0.06);
}
.bbh-icon-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #1a1c1f;
  justify-self: start;
}
.bbh-icon-btn:active { transform: scale(0.96); }
.bbh-nav-title {
  margin: 0;
  text-align: center;
  font-family: 'Manrope', 'PingFang SC', sans-serif;
  font-weight: 800;
  font-size: 17px;
  letter-spacing: -0.02em;
  color: #1a1c1f;
}
.bbh-topbar__spacer { width: 40px; justify-self: end; }

.bbh-main {
  max-width: 1024px;
  margin: 0 auto;
  padding: 20px 16px 32px;
}

.bbh-head {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 24px;
}
@media (min-width: 768px) {
  .bbh-head {
    flex-direction: row;
    align-items: flex-end;
    justify-content: space-between;
  }
}
.bbh-h1 {
  font-family: 'Manrope', 'PingFang SC', sans-serif;
  font-weight: 800;
  font-size: clamp(1.75rem, 5vw, 2.25rem);
  letter-spacing: -0.03em;
  line-height: 1.15;
}
.bbh-desc {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.55;
  color: #434656;
  max-width: 36rem;
}
.bbh-filter-btn {
  position: relative;
  align-self: flex-start;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f3f3f8;
  color: #1a1c1f;
  transition: background 0.15s, transform 0.12s;
}
.bbh-filter-btn .icon { width: 24px; height: 24px; fill: currentColor; }
.bbh-filter-btn:active { transform: scale(0.96); }
.bbh-filter-btn--on,
.bbh-filter-btn:hover { background: #ededf2; }
.bbh-filter-dot {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #0052ff;
  border: 2px solid #f3f3f8;
}
.bbh-filter-btn--on .bbh-filter-dot { border-color: #ededf2; }

.bbh-search-wrap {
  position: relative;
  margin-bottom: 28px;
}
.bbh-search-ic {
  position: absolute;
  left: 18px;
  top: 50%;
  transform: translateY(-50%);
  width: 20px;
  height: 20px;
  fill: #737688;
  pointer-events: none;
}
.bbh-search {
  width: 100%;
  padding: 16px 20px 16px 52px;
  border: none;
  border-radius: 1rem;
  font-size: 14px;
  background: #f3f3f8;
  color: #1a1c1f;
  transition: background 0.2s, box-shadow 0.2s;
}
.bbh-search::placeholder { color: #737688; }
.bbh-search:focus {
  outline: none;
  background: #fff;
  box-shadow: 0 0 0 2px rgba(0, 62, 199, 0.15);
}

.bbh-list {
  display: flex;
  flex-direction: column;
  gap: 22px;
}
.bbh-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 22px;
  background: #fff;
  border-radius: 1rem;
  box-shadow: 0 8px 24px rgba(26, 28, 31, 0.06);
  transition: transform 0.15s;
}
@media (min-width: 768px) {
  .bbh-card {
    flex-direction: row;
    align-items: flex-start;
    gap: 22px;
  }
}
.bbh-card:active { transform: scale(0.995); }

.bbh-card__lead {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-shrink: 0;
}
.bbh-card__time {
  flex: 1;
  min-width: 0;
}
.bbh-card__time .bbh-k { margin-bottom: 4px; }
.bbh-card__time .bbh-v { margin: 0; }

.bbh-card__body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-width: 0;
}
@media (min-width: 768px) {
  .bbh-card__body {
    flex-direction: row;
    align-items: center;
    gap: 22px;
  }
}

.bbh-card__icon {
  flex-shrink: 0;
  width: 56px;
  height: 56px;
  border-radius: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
}
.bbh-card__icon .icon { width: 28px; height: 28px; }
.bbh-card__icon--done {
  background: #ededf2;
  color: #434656;
}
.bbh-card__icon--pulse {
  background: #dde1ff;
  color: #003ec7;
}
.bbh-card__icon--pulse .icon {
  animation: bbh-pulse 1.4s ease-in-out infinite;
}
@keyframes bbh-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.75; transform: scale(1.05); }
}

.bbh-card__grid {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 18px;
  grid-template-columns: 1fr;
}
@media (min-width: 768px) {
  .bbh-card__grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
  }
}
.bbh-k {
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #737688;
  margin-bottom: 4px;
}
.bbh-v {
  font-family: 'Manrope', sans-serif;
  font-weight: 800;
  font-size: 16px;
  color: #1a1c1f;
}
.bbh-v2 {
  font-size: 14px;
  font-weight: 600;
  color: #434656;
  line-height: 1.45;
}

.bbh-card__actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-start;
  flex-shrink: 0;
}
@media (min-width: 768px) {
  .bbh-card__actions {
    align-self: center;
    min-width: 88px;
  }
}
.bbh-link {
  padding: 4px 8px;
  font-size: 14px;
  font-weight: 700;
  background: none;
  border: none;
  cursor: pointer;
}
.bbh-link--primary { color: #0052ff; text-decoration: none; }
.bbh-link--primary:hover { text-decoration: underline; }
.bbh-link--danger { color: #f23645; }
.bbh-link--danger:hover { text-decoration: underline; }

.bbh-bento {
  display: grid;
  gap: 20px;
  margin-top: 28px;
  padding-top: 8px;
  grid-template-columns: 1fr;
}
@media (min-width: 768px) {
  .bbh-bento { grid-template-columns: 2fr 1fr; }
}
.bbh-bento__perf {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 28px;
  border-radius: 1rem;
  background: linear-gradient(135deg, #003ec7 0%, #0052ff 100%);
  color: #fff;
  box-shadow: 0 12px 32px rgba(0, 62, 199, 0.25);
}
.bbh-bento__h {
  font-family: 'Manrope', sans-serif;
  font-weight: 800;
  font-size: 22px;
  margin-bottom: 8px;
}
.bbh-bento__p {
  font-size: 13px;
  line-height: 1.5;
  color: rgba(223, 227, 255, 0.95);
  max-width: 280px;
}
.bbh-bento__p strong { color: #fff; font-weight: 800; }
.bbh-bars {
  display: none;
  align-items: flex-end;
  gap: 6px;
  height: 64px;
}
@media (min-width: 640px) {
  .bbh-bars { display: flex; }
}
.bbh-bars span {
  width: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.25);
}
.bbh-bars span:nth-child(1) { height: 40%; }
.bbh-bars span:nth-child(2) { height: 60%; }
.bbh-bars span:nth-child(3) { height: 85%; }
.bbh-bars span:nth-child(4) { height: 50%; }
.bbh-bars span:nth-child(5) { height: 95%; background: rgba(255, 255, 255, 0.95); }

.bbh-bento__alert {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 28px;
  border-radius: 1rem;
  background: #ededf2;
}
.bbh-bento__num {
  font-family: 'Manrope', sans-serif;
  font-weight: 800;
  font-size: 2rem;
  color: #1a1c1f;
  margin-bottom: 4px;
}
.bbh-bento__lbl {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #737688;
}
.bbh-bento__link {
  margin-top: 14px;
  font-size: 12px;
  font-weight: 700;
  color: #0052ff;
  background: none;
  border: none;
  cursor: pointer;
  text-decoration: underline;
}

.bbh-state {
  text-align: center;
  padding: 48px 20px;
  color: #434656;
  font-size: 14px;
}
.bbh-state--err { color: #f23645; }
.bbh-empty-ic {
  width: 40px;
  height: 40px;
  margin: 0 auto 12px;
  display: block;
  opacity: 0.35;
  fill: #737688;
}
.bbh-spinner {
  width: 32px;
  height: 32px;
  margin: 0 auto;
  border: 2px solid #e2e2e7;
  border-top-color: #0052ff;
  border-radius: 50%;
  animation: bbh-spin 0.7s linear infinite;
}
@keyframes bbh-spin { to { transform: rotate(360deg); } }

.bbh-fab {
  position: fixed;
  right: 22px;
  bottom: calc(28px + env(safe-area-inset-bottom, 0px));
  z-index: 40;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #003ec7;
  color: #fff;
  box-shadow: 0 8px 24px rgba(0, 62, 199, 0.35);
  cursor: pointer;
  transition: transform 0.15s;
}
.bbh-fab .icon { width: 26px; height: 26px; fill: currentColor; }
.bbh-fab:active { transform: scale(0.95); }

.bbh-toast {
  position: fixed;
  left: 50%;
  bottom: calc(100px + env(safe-area-inset-bottom, 0px));
  transform: translateX(-50%);
  z-index: 60;
  padding: 10px 18px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  background: rgba(26, 28, 31, 0.88);
  color: #fff;
  pointer-events: none;
}
.bbh-toast--ok { background: rgba(5, 150, 105, 0.92); }
.bbh-toast--err { background: rgba(186, 26, 26, 0.92); }

/* 筛选弹窗 */
.bbh-modal {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(26, 28, 31, 0.45);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 0 12px;
  padding-bottom: max(12px, env(safe-area-inset-bottom, 0px));
}
@media (min-width: 640px) {
  .bbh-modal {
    align-items: center;
    padding: 24px;
  }
}
.bbh-modal__panel {
  width: 100%;
  max-width: 420px;
  max-height: min(88vh, 640px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #f9f9fe;
  border-radius: 1.25rem 1.25rem 0 0;
  box-shadow: 0 -8px 32px rgba(26, 28, 31, 0.12);
}
@media (min-width: 640px) {
  .bbh-modal__panel {
    border-radius: 1.25rem;
    box-shadow: 0 8px 32px rgba(26, 28, 31, 0.12);
  }
}
.bbh-modal__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px 12px;
  flex-shrink: 0;
}
.bbh-modal__title {
  margin: 0;
  font-family: 'Manrope', 'PingFang SC', sans-serif;
  font-size: 1.125rem;
  font-weight: 800;
  color: #1a1c1f;
}
.bbh-modal__close {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ededf2;
  color: #434656;
  cursor: pointer;
}
.bbh-modal__close .icon { width: 22px; height: 22px; fill: currentColor; }
.bbh-modal__close:active { transform: scale(0.96); }

.bbh-modal__body {
  padding: 0 20px 16px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}
.bbh-modal__sec-label {
  margin: 0 0 10px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #737688;
}
.bbh-modal__sec-label--mt { margin-top: 20px; }
.bbh-modal__dates {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
@media (min-width: 480px) {
  .bbh-modal__dates {
    flex-direction: row;
    align-items: flex-end;
    gap: 12px;
  }
}
.bbh-date-field {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.bbh-date-field__lbl {
  font-size: 13px;
  font-weight: 600;
  color: #434656;
}
.bbh-date-input {
  width: 100%;
  padding: 12px 14px;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  font-family: inherit;
  background: #fff;
  color: #1a1c1f;
  box-shadow: 0 0 0 1px rgba(195, 197, 217, 0.35);
}
.bbh-date-input:focus {
  outline: none;
  box-shadow: 0 0 0 2px rgba(0, 82, 255, 0.35);
}
.bbh-modal__hint {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: #787b86;
}

.bbh-time-card-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-top: 4px;
}
@media (min-width: 400px) {
  .bbh-time-card-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
.bbh-time-card {
  padding: 14px 12px;
  border: none;
  border-radius: 14px;
  font-size: 14px;
  font-weight: 700;
  font-family: inherit;
  cursor: pointer;
  text-align: center;
  background: #fff;
  color: #1a1c1f;
  box-shadow: 0 0 0 1px rgba(195, 197, 217, 0.45);
  transition: background 0.15s, box-shadow 0.15s, transform 0.12s;
}
.bbh-time-card:active {
  transform: scale(0.98);
}
.bbh-time-card:hover {
  box-shadow: 0 0 0 2px rgba(0, 82, 255, 0.25);
  background: rgba(0, 82, 255, 0.04);
}

.bbh-load-more {
  display: block;
  width: 100%;
  margin-top: 12px;
  padding: 12px 16px;
  border: none;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 700;
  font-family: inherit;
  cursor: pointer;
  color: #0052ff;
  background: rgba(0, 82, 255, 0.08);
  transition: background 0.15s;
}
.bbh-load-more:active {
  transform: scale(0.99);
}
.bbh-load-more:hover {
  background: rgba(0, 82, 255, 0.14);
}

.bbh-modal__foot {
  display: flex;
  gap: 12px;
  padding: 16px 20px 20px;
  flex-shrink: 0;
  border-top: 1px solid rgba(226, 226, 231, 0.8);
  background: #fff;
  border-radius: 0 0 1.25rem 1.25rem;
}
.bbh-modal__btn {
  flex: 1;
  padding: 14px 16px;
  border-radius: 999px;
  font-size: 15px;
  font-weight: 700;
  border: none;
  cursor: pointer;
  font-family: inherit;
}
.bbh-modal__btn--ghost {
  background: #ededf2;
  color: #434656;
}
.bbh-modal__btn--primary {
  background: linear-gradient(135deg, #003ec7, #0052ff);
  color: #fff;
}
.bbh-modal__btn:active { transform: scale(0.98); }
</style>
