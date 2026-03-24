<template>
  <div>
    <nav class="navbar">
      <div class="nav-back" onclick="history.back()">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </div>
      <div class="nav-title">
        <svg class="icon" style="fill:var(--apple-indigo);margin-right:6px" viewBox="0 0 24 24"><use href="#icon-strategy"/></svg>
        历史报表
      </div>
    </nav>

    <div class="container">
      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        <div>加载中...</div>
      </div>
      <div v-else-if="error" class="error">{{ error }}</div>
      <div v-else-if="reports.length === 0" class="empty">暂无历史报表</div>
      <div v-else class="report-list">
        <div v-for="r in reports" :key="r.report_date" class="report-card" @click="showDetail(r.report_date)">
          <div class="report-info">
            <span class="report-date">
              <svg class="icon icon-sm"><use href="#icon-calendar"/></svg>
              {{ r.report_date }}
            </span>
            <div class="report-meta">
              <span class="report-meta-item">
                <svg class="icon icon-sm"><use href="#icon-category"/></svg>
                {{ r.themes_count }} 个题材
              </span>
              <span class="report-meta-item">
                <svg class="icon icon-sm"><use href="#icon-stock"/></svg>
                {{ r.stocks_count }} 只股票
              </span>
            </div>
          </div>
          <span class="report-arrow">
            <svg class="icon"><use href="#icon-chevron-right"/></svg>
          </span>
        </div>
      </div>
    </div>

    <!-- 详情弹窗 -->
    <div class="detail-modal" :class="{ active: detailModal }" @click.self="closeDetail">
      <div class="detail-panel">
        <div class="detail-header">
          <button class="close-btn" @click="closeDetail">
            <svg class="icon" viewBox="0 0 24 24"><use href="#icon-back"/></svg>
          </button>
          <span class="detail-title">
            <svg class="icon"><use href="#icon-calendar"/></svg>
            {{ selectedDate }}
          </span>
        </div>
        <div class="detail-content">
          <div v-if="detailLoading" class="loading">
            <div class="spinner"></div>
          </div>
          <div v-else-if="detailError" class="error">{{ detailError }}</div>
          <div v-else>
            <div v-for="(stocks, themeName) in detailData" :key="themeName" class="theme-card">
              <div class="theme-header">
                <span class="theme-name">
                  <svg class="icon icon-sm"><use href="#icon-fire"/></svg>
                  {{ themeName }}
                </span>
              </div>
              <div class="stock-list">
                <template v-if="stocks && stocks.length">
                  <div v-for="(s, idx) in stocks" :key="s.stock_code" class="stock-item">
                    <div class="stock-left">
                      <span class="stock-rank" :class="idx === 0 ? 'rank-1' : idx === 1 ? 'rank-2' : idx === 2 ? 'rank-3' : 'rank-other'">{{ idx + 1 }}</span>
                      <div class="stock-name-wrap">
                        <span class="stock-name">{{ s.stock_name }}</span>
                        <span class="stock-code">{{ s.stock_code }}</span>
                      </div>
                      <span v-if="s.is_buyable === false || s.is_buyable === 0" class="stock-unbuyable">
                        <svg class="icon icon-sm"><use href="#icon-warning"/></svg>
                        {{ s.unbuyable_reason || '无法买入' }}
                      </span>
                    </div>
                    <span class="stock-change" :class="(s.change_pct || 0) >= 0 ? 'up' : 'down'">
                      {{ (s.change_pct || 0) >= 0 ? '+' : '' }}{{ (s.change_pct || 0).toFixed(2) }}%
                    </span>
                  </div>
                </template>
                <div v-else class="empty-stock">暂无股票</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ticai } from '@/api/ticai.js'

const loading = ref(true)
const error = ref('')
const reports = ref([])

const detailModal = ref(false)
const selectedDate = ref('')
const detailLoading = ref(false)
const detailError = ref('')
const detailData = ref({})

async function loadReports() {
  try {
    reports.value = await ticai.reports()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function showDetail(date) {
  selectedDate.value = date
  detailModal.value = true
  detailLoading.value = true
  detailError.value = ''
  detailData.value = {}
  try {
    const data = await ticai.report(date)
    detailData.value = data.themes || {}
  } catch (e) {
    detailError.value = e.message
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  detailModal.value = false
}

onMounted(() => loadReports())
</script>

<style scoped>
.navbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(255,255,255,0.78);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  padding: 12px 16px;
  padding-top: calc(12px + env(safe-area-inset-top));
  display: flex; align-items: center; gap: 12px;
}
.nav-back {
  width: 30px; height: 30px; border-radius: 8px;
  background: var(--apple-gray6); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.nav-back .icon { fill: var(--apple-text2); }
.nav-title { font-size: 17px; font-weight: 600; display: flex; align-items: center; gap: 6px; letter-spacing: -0.41px; flex: 1; justify-content: center; padding-right: 30px; }
.nav-title .icon { fill: var(--apple-blue); }
.container { padding: 16px; }
.loading { text-align: center; padding: 80px 20px; color: var(--apple-gray); }
.spinner { width: 28px; height: 28px; border: 2.5px solid var(--apple-gray5); border-top-color: var(--apple-blue); border-radius: 50%; animation: spin 0.7s linear infinite; margin: 0 auto 14px; }
@keyframes spin { to { transform: rotate(360deg); } }
.error { text-align: center; padding: 60px 20px; color: var(--apple-red); }
.empty { text-align: center; padding: 80px 20px; color: var(--apple-gray); }
.report-list { display: flex; flex-direction: column; gap: 12px; }
.report-card {
  background: var(--apple-card); border-radius: 16px; padding: 16px 18px;
  display: flex; justify-content: space-between; align-items: center;
  cursor: pointer; transition: all 0.2s;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.report-card:active { background: var(--apple-gray6); transform: scale(0.98); }
.report-info { display: flex; flex-direction: column; gap: 6px; }
.report-date { font-size: 17px; font-weight: 600; color: var(--apple-text); display: flex; align-items: center; gap: 8px; letter-spacing: -0.41px; }
.report-date .icon { fill: var(--apple-blue); }
.report-meta { display: flex; gap: 14px; font-size: 13px; color: var(--apple-text3); }
.report-meta-item { display: flex; align-items: center; gap: 4px; }
.report-meta-item .icon { fill: var(--apple-gray); }
.report-arrow { color: var(--apple-gray3); }
.detail-modal { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); z-index: 200; }
.detail-modal.active { display: block; }
.detail-panel { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: var(--apple-bg); animation: slideIn 0.35s cubic-bezier(0.32, 0.72, 0, 1); display: flex; flex-direction: column; }
@keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
.detail-header { background: rgba(255,255,255,0.78); backdrop-filter: saturate(180%) blur(20px); padding: 12px 16px; padding-top: calc(12px + env(safe-area-inset-top)); display: flex; align-items: center; gap: 12px; }
.close-btn { width: 32px; height: 32px; background: var(--apple-gray6); border-radius: 50%; border: none; display: flex; align-items: center; justify-content: center; cursor: pointer; color: var(--apple-text2); }
.detail-title { flex: 1; font-size: 17px; font-weight: 600; display: flex; align-items: center; gap: 8px; letter-spacing: -0.41px; }
.detail-title .icon { fill: var(--apple-blue); }
.detail-content { flex: 1; overflow-y: auto; padding: 16px; }
.theme-card { background: var(--apple-card); border-radius: 16px; overflow: hidden; margin-bottom: 14px; box-shadow: 0 2px 12px rgba(0,0,0,0.04); }
.theme-header { padding: 16px 18px; border-bottom: 0.5px solid var(--apple-gray5); display: flex; justify-content: space-between; align-items: center; }
.theme-name { font-size: 16px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.theme-name .icon { fill: var(--apple-orange); }
.stock-list { padding: 0; }
.stock-item { padding: 14px 18px; border-bottom: 0.5px solid var(--apple-gray5); display: flex; justify-content: space-between; align-items: center; }
.stock-item:last-child { border-bottom: none; }
.stock-left { display: flex; align-items: center; gap: 12px; }
.stock-rank { width: 22px; height: 22px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; color: #fff; flex-shrink: 0; }
.rank-1 { background: var(--apple-red); }
.rank-2 { background: var(--apple-orange); }
.rank-3 { background: var(--apple-purple); }
.rank-other { background: var(--apple-gray); }
.stock-name-wrap { display: flex; flex-direction: column; gap: 2px; }
.stock-name { font-size: 15px; font-weight: 600; letter-spacing: -0.24px; }
.stock-code { font-size: 12px; color: var(--apple-text3); }
.stock-unbuyable { display: flex; align-items: center; gap: 4px; font-size: 11px; color: var(--apple-orange); background: #FFF3E0; padding: 3px 8px; border-radius: 8px; font-weight: 600; }
.stock-unbuyable .icon { fill: var(--apple-orange); }
.stock-change { font-size: 16px; font-weight: 700; letter-spacing: -0.24px; }
.up { color: var(--apple-red) !important; }
.down { color: var(--apple-green) !important; }
.empty-stock { text-align: center; padding: 28px; color: var(--apple-gray); font-size: 14px; }
</style>

