<template>
  <div class="watchlist-page">
    <!-- 顶部导航 -->
    <nav class="navbar">
      <div class="nav-title">自选</div>
      <button class="nav-add-btn" @click="showAddModal = true">
        <svg class="icon" viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
        添加
      </button>
    </nav>

    <!-- 内容区 -->
    <div class="container">
      <!-- 加载状态 -->
      <div v-if="loading && stocks.length === 0" class="loading">
        <div class="loading-spinner"></div>
        <div>加载自选列表...</div>
      </div>

      <!-- 错误 -->
      <div v-else-if="error" class="error">
        <div class="error-icon">⚠️</div>
        <div>{{ error }}</div>
        <button class="retry-btn" @click="loadList">重试</button>
      </div>

      <!-- 空状态 -->
      <div v-else-if="stocks.length === 0" class="empty">
        <svg class="icon empty-icon" viewBox="0 0 24 24" style="fill:var(--apple-gray3)">
          <use href="#icon-star-outline"/>
        </svg>
        <div>暂无自选股票</div>
        <div class="empty-hint">点击右上角「添加」将股票加入自选</div>
        <button class="add-first-btn" @click="showAddModal = true">添加自选</button>
      </div>

      <!-- 自选列表 -->
      <div v-else class="stock-list">
        <div
          v-for="stock in stocks"
          :key="stock.code"
          class="stock-item"
          @click="showDetail(stock)"
        >
          <div class="stock-left">
            <div class="stock-name-wrap">
              <span class="stock-name">{{ stock.name }}</span>
              <span class="stock-code">{{ stock.code }}</span>
            </div>
            <span v-if="stock.sector" class="stock-sector">{{ stock.sector }}</span>
          </div>
          <div class="stock-right">
            <div class="stock-price-wrap">
              <span class="stock-price" :class="priceColor(stock)">
                {{ fmtPrice(stock) }}
              </span>
              <span class="stock-change" :class="priceColor(stock)">
                {{ fmtChange(stock) }}
              </span>
            </div>
            <button
              class="unstar-btn"
              :class="{ loading: unstarLoading === stock.code }"
              @click.stop="unstar(stock.code)"
              title="取消自选"
            >
              <svg class="icon" viewBox="0 0 24 24"><use href="#icon-star"/></svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 添加股票弹窗 -->
    <div class="add-modal" :class="{ active: showAddModal }" @click.self="showAddModal = false">
      <div class="add-panel">
        <div class="add-header">
          <span class="add-title">添加自选</span>
          <button class="add-close" @click="showAddModal = false">
            <svg class="icon" viewBox="0 0 24 24"><use href="#icon-cancel"/></svg>
          </button>
        </div>
        <div class="add-body">
          <div class="form-group">
            <label>股票代码</label>
            <input
              v-model="addForm.code"
              type="text"
              placeholder="如 000001"
              maxlength="6"
              @input="addForm.code = addForm.code.replace(/\D/g, '')"
            />
          </div>
          <div class="form-group">
            <label>股票名称</label>
            <input
              v-model="addForm.name"
              type="text"
              placeholder="如 平安银行"
            />
          </div>
          <div class="form-group">
            <label>板块（选填）</label>
            <input
              v-model="addForm.sector"
              type="text"
              placeholder="如 银行"
            />
          </div>
          <button
            class="confirm-btn"
            :disabled="!addForm.code || !addForm.name || adding"
            @click="confirmAdd"
          >
            {{ adding ? '添加中...' : '确认添加' }}
          </button>
          <div v-if="addError" class="add-error">{{ addError }}</div>
        </div>
      </div>
    </div>

    <!-- 股票详情弹窗 -->
    <div class="detail-modal" :class="{ active: detailVisible }" @click.self="closeDetail">
      <div class="detail-panel">
        <div class="detail-header">
          <button class="close-btn" @click="closeDetail">
            <svg class="icon" viewBox="0 0 24 24"><use href="#icon-back"/></svg>
          </button>
          <span class="detail-title">
            <svg class="icon" style="fill:#FF9500"><use href="#icon-star"/></svg>
            {{ detailStock?.name || '' }}
          </span>
          <button
            class="detail-star-btn"
            :class="{ active: inWatchlist }"
            @click="toggleWatchlist"
            :title="inWatchlist ? '取消自选' : '加自选'"
          >
            <svg class="icon" viewBox="0 0 24 24">
              <use :href="inWatchlist ? '#icon-star' : '#icon-star-outline'"/>
            </svg>
          </button>
        </div>
        <div class="detail-content" v-if="detailStock">
          <!-- 行情 -->
          <div class="detail-price-card">
            <div class="detail-price-main">
              <span class="detail-price">¥{{ fmtPrice(detailStock) }}</span>
              <span class="detail-pct" :class="priceColor(detailStock)">{{ fmtChange(detailStock) }}</span>
            </div>
            <div class="detail-meta-row">
              <span class="detail-meta-item">{{ detailStock.code }}</span>
              <span v-if="detailStock.sector" class="detail-meta-item">{{ detailStock.sector }}</span>
              <span v-if="detailStock.add_time" class="detail-meta-item">自选于 {{ detailStock.add_time }}</span>
            </div>
          </div>

          <!-- K线图 -->
          <div class="detail-kline-card">
            <div class="detail-section-label detail-kline-heading">K线走势</div>
            <KlineChart v-if="detailStock.code" :code="detailStock.code" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { watchlist } from '@/api/strategy.js'
import { stock } from '@/api/strategy.js'
import KlineChart from '@/components/KlineChart.vue'

const loading = ref(true)
const error = ref('')
const stocks = ref([])
const unstarLoading = ref(null)

// 添加弹窗
const showAddModal = ref(false)
const addForm = ref({ code: '', name: '', sector: '' })
const adding = ref(false)
const addError = ref('')

// 详情弹窗
const detailVisible = ref(false)
const detailStock = ref(null)
const inWatchlist = ref(true)

async function loadList() {
  loading.value = true
  error.value = ''
  try {
    const data = await watchlist.list()
    const raw = Array.isArray(data) ? data : []
    // 并行获取每只股票实时行情
    const enriched = await Promise.all(
      raw.map(async (s) => {
        try {
          const d = await stock.detail(s.stock_code)
          return {
            ...s,
            code: s.stock_code,
            name: d?.name || s.stock_name,
            close: d?.close,
            pct_change: d?.pct_change,
            sector: s.sector_name || d?.sector_name,
            add_time: s.add_time,
          }
        } catch {
          return {
            ...s,
            code: s.stock_code,
            name: s.stock_name,
            sector: s.sector_name,
            add_time: s.add_time,
          }
        }
      })
    )
    stocks.value = enriched
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function unstar(code) {
  if (unstarLoading.value === code) return
  unstarLoading.value = code
  try {
    await watchlist.remove(code)
    stocks.value = stocks.value.filter((s) => s.code !== code)
    if (detailStock.value?.code === code) closeDetail()
  } catch (e) {
    alert(e.message || '移除失败')
  } finally {
    unstarLoading.value = null
  }
}

async function confirmAdd() {
  const { code, name, sector } = addForm.value
  if (!code || !name) return
  adding.value = true
  addError.value = ''
  try {
    await watchlist.add(code, name, sector)
    showAddModal.value = false
    addForm.value = { code: '', name: '', sector: '' }
    await loadList()
  } catch (e) {
    addError.value = e.message || '添加失败'
  } finally {
    adding.value = false
  }
}

function showDetail(s) {
  detailStock.value = { ...s }
  inWatchlist.value = true
  detailVisible.value = true
  document.body.style.overflow = 'hidden'
}

function closeDetail() {
  detailVisible.value = false
  document.body.style.overflow = ''
}

async function toggleWatchlist() {
  if (!detailStock.value) return
  const code = detailStock.value.code
  const name = detailStock.value.name
  const sector = detailStock.value.sector
  if (inWatchlist.value) {
    try {
      await watchlist.remove(code)
      inWatchlist.value = false
      stocks.value = stocks.value.filter((s) => s.code !== code)
    } catch (e) {
      alert(e.message || '移除失败')
    }
  } else {
    try {
      await watchlist.add(code, name, sector)
      inWatchlist.value = true
      // 避免重复
      if (!stocks.value.find((s) => s.code === code)) {
        stocks.value.unshift({ ...detailStock.value })
      }
    } catch (e) {
      alert(e.message || '添加失败')
    }
  }
}

function priceColor(s) {
  const n = Number(s.pct_change)
  if (!Number.isFinite(n)) return ''
  return n >= 0 ? 'up' : 'down'
}

function fmtPrice(s) {
  const n = Number(s.close)
  return Number.isFinite(n) ? n.toFixed(2) : '--'
}

function fmtChange(s) {
  const n = Number(s.pct_change)
  if (!Number.isFinite(n)) return '--'
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%'
}

onMounted(() => loadList())
</script>

<style scoped>
.watchlist-page { padding-bottom: 0; }

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
.nav-add-btn {
  display: flex; align-items: center; gap: 4px;
  background: var(--apple-blue); color: #fff;
  border: none; padding: 6px 14px; border-radius: 16px;
  font-size: 14px; font-weight: 600; cursor: pointer;
}
.nav-add-btn .icon { fill: #fff; width: 16px; height: 16px; }

.container { padding: 16px 16px 24px; }

.loading { text-align: center; padding: 80px 20px; color: var(--apple-gray); }
.loading-spinner {
  width: 32px; height: 32px;
  border: 3px solid var(--apple-gray5); border-top-color: var(--apple-blue);
  border-radius: 50%; animation: spin 0.7s linear infinite;
  margin: 0 auto 14px;
}
@keyframes spin { to { transform: rotate(360deg); } }

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
.add-first-btn {
  background: var(--apple-blue); color: #fff; border: none;
  padding: 10px 24px; border-radius: 20px; font-size: 15px;
  font-weight: 600; cursor: pointer; margin-top: 20px;
}

.stock-list { display: flex; flex-direction: column; gap: 1px; background: var(--apple-gray5); border-radius: 12px; overflow: hidden; }
.stock-item {
  background: var(--apple-card); padding: 14px 16px;
  display: flex; justify-content: space-between; align-items: center;
  cursor: pointer;
  transition: background 0.15s;
}
.stock-item:active { background: var(--apple-gray6); }

.stock-left { display: flex; flex-direction: column; gap: 4px; }
.stock-name-wrap { display: flex; align-items: baseline; gap: 8px; }
.stock-name { font-size: 16px; font-weight: 700; }
.stock-code { font-size: 12px; color: var(--apple-text3); }
.stock-sector { font-size: 12px; color: var(--apple-text3); }

.stock-right { display: flex; align-items: center; gap: 12px; }
.stock-price-wrap { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }
.stock-price { font-size: 16px; font-weight: 700; }
.stock-change { font-size: 13px; font-weight: 600; }

.unstar-btn {
  width: 32px; height: 32px; border-radius: 50%;
  border: none; background: var(--apple-gray6);
  display: flex; align-items: center; justify-content: center; cursor: pointer;
  flex-shrink: 0; transition: opacity 0.15s;
}
.unstar-btn .icon { width: 16px; height: 16px; fill: #FF9500; }
.unstar-btn.loading { opacity: 0.5; pointer-events: none; }

.up { color: var(--apple-red) !important; }
.down { color: var(--apple-green) !important; }

/* 添加弹窗 */
.add-modal { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); z-index: 200; }
.add-modal.active { display: block; }
.add-panel {
  position: absolute; top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  background: var(--apple-card); border-radius: 16px;
  width: 90%; max-width: 380px;
  animation: fadeIn 0.25s ease;
}
@keyframes fadeIn { from { opacity: 0; transform: translate(-50%, -48%); } to { opacity: 1; transform: translate(-50%, -50%); } }
.add-header {
  padding: 16px 20px; display: flex; align-items: center; justify-content: space-between;
  border-bottom: 0.5px solid var(--apple-gray5);
}
.add-title { font-size: 17px; font-weight: 700; }
.add-close { background: none; border: none; cursor: pointer; padding: 4px; }
.add-close .icon { width: 20px; height: 20px; fill: var(--apple-gray2); }
.add-body { padding: 20px; display: flex; flex-direction: column; gap: 16px; }
.form-group { display: flex; flex-direction: column; gap: 6px; }
.form-group label { font-size: 13px; color: var(--apple-text3); font-weight: 500; }
.form-group input {
  padding: 10px 14px; border: 1px solid var(--apple-gray4);
  border-radius: 10px; font-size: 16px; outline: none;
  transition: border-color 0.2s;
}
.form-group input:focus { border-color: var(--apple-blue); }
.confirm-btn {
  background: var(--apple-blue); color: #fff; border: none;
  padding: 12px; border-radius: 12px; font-size: 16px; font-weight: 600;
  cursor: pointer; transition: opacity 0.15s;
}
.confirm-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.add-error { font-size: 13px; color: var(--apple-red); text-align: center; }

/* 详情弹窗 */
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
.detail-title .icon { fill: #FF9500; }
.detail-star-btn {
  width: 36px; height: 36px; background: var(--apple-gray6); border-radius: 50%;
  border: none; display: flex; align-items: center; justify-content: center; cursor: pointer;
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
.detail-kline-heading { margin-bottom: 6px; }
.detail-section-label { font-size: 12px; color: var(--apple-text3); font-weight: 600; }
</style>
