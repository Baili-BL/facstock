<template>
  <div class="bbale-page">
    <!-- TopAppBar -->
    <header class="bbale-topbar">
      <button type="button" class="bbale-icon-btn" aria-label="返回" @click="$router.push('/strategy/bollinger/history')">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <h2 class="bbale-nav-title">告警管理</h2>
      <button type="button" class="bbale-icon-btn bbale-icon-btn--accent" aria-label="新建告警" @click="$router.push('/strategy/bollinger/alert/new')">
        <svg class="icon" viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
      </button>
    </header>

    <main class="bbale-main">
      <!-- Page Title -->
      <header class="bbale-head">
        <div>
          <h1 class="bbale-h1">告警规则</h1>
          <p class="bbale-desc">管理布林带收缩突破策略的飞书推送规则。</p>
        </div>
      </header>

      <!-- Search -->
      <div class="bbale-search-wrap">
        <svg class="icon bbale-search-ic" viewBox="0 0 24 24"><use href="#icon-search"/></svg>
        <input v-model.trim="searchQuery" type="search" class="bbale-search" placeholder="搜索规则名称..." autocomplete="off">
      </div>

      <!-- Loading -->
      <div v-if="loading" class="bbale-state bbale-state--load"><div class="bbale-spinner" /></div>

      <!-- Error -->
      <div v-else-if="error" class="bbale-state bbale-state--err">{{ error }}</div>

      <!-- Empty -->
      <div v-else-if="filteredList.length === 0" class="bbale-state bbale-state--empty">
        <svg class="icon bbale-empty-ic" viewBox="0 0 24 24"><use href="#icon-history"/></svg>
        <p>{{ searchQuery ? '无匹配规则' : '暂无告警规则' }}</p>
        <button type="button" class="bbale-empty-cta" @click="$router.push('/strategy/bollinger/alert/new')">新建告警</button>
      </div>

      <!-- Rule Cards -->
      <div v-else class="bbale-list">
        <article
          v-for="rule in filteredList"
          :key="rule.id"
          class="bbale-card"
          :class="{ 'bbale-card--disabled': !rule.enabled }"
          @click="goEdit(rule.id)"
        >
          <div class="bbale-card__header">
            <div class="bbale-card__icon" :class="rule.enabled ? 'bbale-card__icon--active' : 'bbale-card__icon--inactive'">
              <svg class="icon" viewBox="0 0 24 24"><use href="#icon-bell"/></svg>
            </div>
            <div class="bbale-card__meta">
              <p class="bbale-card__name">{{ rule.rule_name }}</p>
              <p class="bbale-card__updated">
                {{ rule.linked_scan_time ? '关联扫描 ' + fmtDate(rule.linked_scan_time) : '无关联扫描' }}
              </p>
            </div>
            <div class="bbale-card__badge" :class="rule.enabled ? 'bbale-card__badge--on' : 'bbale-card__badge--off'">
              {{ rule.enabled ? '已启用' : '已停用' }}
            </div>
          </div>

          <div class="bbale-card__body">
            <div class="bbale-card__grid">
              <div class="bbale-card__cell">
                <p class="bbale-k">指标</p>
                <p class="bbale-v2">{{ metricLabel(rule.metric) }}</p>
              </div>
              <div class="bbale-card__cell">
                <p class="bbale-k">条件</p>
                <p class="bbale-v2">{{ condLabel(rule.cond_op) }} {{ rule.threshold || '—' }}</p>
              </div>
              <div class="bbale-card__cell">
                <p class="bbale-k">频率</p>
                <p class="bbale-v2">{{ freqLabel(rule.frequency) }}</p>
              </div>
            </div>
          </div>

          <div class="bbale-card__footer">
            <button type="button" class="bbale-link bbale-link--danger" @click.stop="onDelete(rule.id)">删除</button>
          </div>
        </article>
      </div>

      <!-- Bento stats -->
      <div v-if="!loading && !error" class="bbale-bento">
        <div class="bbale-bento__stat">
          <span class="bbale-bento__num">{{ activeCount }}</span>
          <span class="bbale-bento__lbl">已启用规则</span>
        </div>
        <div class="bbale-bento__stat">
          <span class="bbale-bento__num">{{ totalCount }}</span>
          <span class="bbale-bento__lbl">规则总数</span>
        </div>
      </div>
    </main>

    <!-- FAB: New -->
    <button type="button" class="bbale-fab" aria-label="新建告警" @click="$router.push('/strategy/bollinger/alert/new')">
      <svg class="icon" viewBox="0 0 24 24"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
    </button>

    <div v-if="toastVisible" class="bbale-toast" :class="'bbale-toast--' + toastType">{{ toastMsg }}</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { alertRule } from '@/api/strategy.js'

const router = useRouter()

const rawList = ref([])
const loading = ref(true)
const error = ref('')
const searchQuery = ref('')

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

const METRIC_MAP = {
  bb_width_pct: '布林带收缩值',
  pct_change: '涨跌幅',
  volume_ratio: '量比',
  total_score: '综合评分',
  squeeze_days: '收缩天数',
}
const COND_MAP = {
  gt: '>',
  lt: '<',
  cross_above: '上穿',
  cross_below: '下破',
}
const FREQ_MAP = {
  once: '仅一次',
  daily: '每天一次',
  weekly: '每周一次',
}

function metricLabel(m) { return METRIC_MAP[m] || m || '—' }
function condLabel(c) { return COND_MAP[c] || c || '—' }
function freqLabel(f) { return FREQ_MAP[f] || f || '—' }

const filteredList = computed(() => {
  if (!searchQuery.value) return rawList.value
  const q = searchQuery.value.toLowerCase()
  return rawList.value.filter(r => r.rule_name.toLowerCase().includes(q))
})

const totalCount = computed(() => rawList.value.length)
const activeCount = computed(() => rawList.value.filter(r => r.enabled).length)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await alertRule.list()
    rawList.value = Array.isArray(data) ? data : []
  } catch (e) {
    error.value = e.message || '加载失败'
    rawList.value = []
  } finally {
    loading.value = false
  }
}

function goEdit(id) {
  router.push({ path: `/strategy/bollinger/alert/${id}` })
}

async function onDelete(id) {
  if (!confirm('确定删除该告警规则？')) return
  try {
    await alertRule.delete(id)
    showToast('删除成功', 'ok')
    await load()
  } catch (e) {
    showToast(e.message || '删除失败', 'err')
  }
}

onMounted(load)
</script>

<style scoped>
.bbale-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: #f9f9fe;
  color: #1a1c1f;
  font-family: 'Inter', 'Manrope', 'PingFang SC', system-ui, sans-serif;
  padding-bottom: calc(120px + env(safe-area-inset-bottom, 0px));
}

.bbale-topbar {
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
.bbale-icon-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #1a1c1f;
  transition: background 0.15s, transform 0.12s;
  justify-self: start;
}
.bbale-icon-btn:active { transform: scale(0.96); }
.bbale-icon-btn--accent { background: #003ec7; color: #fff; }
.bbale-icon-btn--accent:active { background: #0052ff; }
.bbale-nav-title {
  margin: 0;
  text-align: center;
  font-family: 'Manrope', 'PingFang SC', sans-serif;
  font-weight: 800;
  font-size: 17px;
  letter-spacing: -0.02em;
  color: #1a1c1f;
}

.bbale-main {
  max-width: 1024px;
  margin: 0 auto;
  padding: 20px 16px 32px;
}
.bbale-head {
  margin-bottom: 24px;
}
.bbale-h1 {
  font-family: 'Manrope', 'PingFang SC', sans-serif;
  font-weight: 800;
  font-size: clamp(1.75rem, 5vw, 2.25rem);
  letter-spacing: -0.03em;
  line-height: 1.15;
}
.bbale-desc {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.55;
  color: #434656;
}

.bbale-search-wrap {
  position: relative;
  margin-bottom: 28px;
}
.bbale-search-ic {
  position: absolute;
  left: 18px;
  top: 50%;
  transform: translateY(-50%);
  width: 20px;
  height: 20px;
  fill: #737688;
  pointer-events: none;
}
.bbale-search {
  width: 100%;
  padding: 16px 20px 16px 52px;
  border: none;
  border-radius: 1rem;
  font-size: 14px;
  background: #f3f3f8;
  color: #1a1c1f;
  transition: background 0.15s, box-shadow 0.15s;
  box-sizing: border-box;
  outline: none;
}
.bbale-search:focus {
  background: #ffffff;
  box-shadow: 0 0 0 2px #003ec7;
}
.bbale-search::placeholder { color: #737688; }

.bbale-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 64px 0;
  text-align: center;
  color: #434656;
  font-size: 14px;
}
.bbale-state--err { color: #ba1a1a; }
.bbale-empty-ic { width: 48px; height: 48px; fill: #c3c5d9; }
.bbale-empty-cta {
  margin-top: 8px;
  padding: 10px 28px;
  border-radius: 9999px;
  background: #003ec7;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: background 0.15s, transform 0.12s;
}
.bbale-empty-cta:active { transform: scale(0.97); background: #0052ff; }

.bbale-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #ededf2;
  border-top-color: #003ec7;
  border-radius: 50%;
  animation: bbale-spin 0.75s linear infinite;
}
@keyframes bbale-spin { to { transform: rotate(360deg); } }

.bbale-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 24px;
}
.bbale-card {
  background: #ffffff;
  border-radius: 2rem;
  padding: 20px 24px;
  box-shadow: 0 8px 24px rgba(26, 28, 31, 0.06);
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.12s;
}
.bbale-card:active { transform: scale(0.99); box-shadow: 0 4px 12px rgba(26, 28, 31, 0.08); }
.bbale-card--disabled { opacity: 0.6; }

.bbale-card__header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
}
.bbale-card__icon {
  width: 44px;
  height: 44px;
  border-radius: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.bbale-card__icon--active { background: #dde1ff; }
.bbale-card__icon--inactive { background: #f3f3f8; }
.bbale-card__icon--active .icon { fill: #003ec7; }
.bbale-card__icon .icon { width: 22px; height: 22px; fill: #737688; }

.bbale-card__meta { flex: 1; min-width: 0; }
.bbale-card__name {
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 15px;
  color: #1a1c1f;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bbale-card__updated {
  font-size: 12px;
  color: #737688;
  margin-top: 2px;
}

.bbale-card__badge {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 9999px;
  flex-shrink: 0;
}
.bbale-card__badge--on { background: #dfe3ff; color: #003ec7; }
.bbale-card__badge--off { background: #f3f3f8; color: #737688; }

.bbale-card__body { margin-bottom: 12px; }
.bbale-card__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  padding: 14px;
  background: #f3f3f8;
  border-radius: 1.5rem;
}
.bbale-card__cell { text-align: center; }
.bbale-k {
  font-size: 11px;
  font-weight: 600;
  color: #737688;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}
.bbale-v2 {
  font-size: 13px;
  font-weight: 600;
  color: #1a1c1f;
}

.bbale-card__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 8px;
}
.bbale-link {
  font-size: 13px;
  font-weight: 600;
  padding: 6px 16px;
  border-radius: 9999px;
  border: none;
  cursor: pointer;
  transition: background 0.15s, transform 0.12s;
}
.bbale-link:active { transform: scale(0.96); }
.bbale-link--danger { background: #ffdad6; color: #93000a; }
.bbale-link--danger:hover { background: #ffb4a1; }

.bbale-bento {
  display: flex;
  gap: 16px;
  margin-top: 8px;
}
.bbale-bento__stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 20px;
  background: #ffffff;
  border-radius: 2rem;
  box-shadow: 0 8px 24px rgba(26, 28, 31, 0.06);
}
.bbale-bento__num {
  font-family: 'Manrope', sans-serif;
  font-size: 2rem;
  font-weight: 800;
  color: #003ec7;
  letter-spacing: -0.03em;
}
.bbale-bento__lbl {
  font-size: 12px;
  color: #737688;
  font-weight: 500;
}

.bbale-fab {
  position: fixed;
  bottom: calc(80px + env(safe-area-inset-bottom, 0px));
  right: 20px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: #003ec7;
  color: #fff;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(0, 62, 199, 0.4);
  transition: background 0.15s, transform 0.12s, box-shadow 0.15s;
  z-index: 40;
}
.bbale-fab .icon { width: 28px; height: 28px; fill: currentColor; }
.bbale-fab:active { transform: scale(0.94); background: #0052ff; }

.bbale-toast {
  position: fixed;
  bottom: 100px;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 24px;
  border-radius: 9999px;
  font-size: 14px;
  font-weight: 600;
  background: #1a1c1f;
  color: #fff;
  box-shadow: 0 8px 24px rgba(26, 28, 31, 0.2);
  z-index: 100;
  white-space: nowrap;
}
.bbale-toast--ok { background: #003b1f; }
.bbale-toast--err { background: #ba1a1a; }
</style>
