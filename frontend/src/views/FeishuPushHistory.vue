<template>
  <div class="history-page">
    <!-- TopAppBar -->
    <header class="history-topbar">
      <button type="button" class="topbar-btn" @click="$router.push(`${feishuBase}/feishu`)">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
      </button>
      <h1 class="topbar-title">推送记录</h1>
      <div class="topbar-spacer" />
    </header>

    <main class="history-main">
      <!-- Search Bar -->
      <div class="history-search">
        <div class="history-search__icon">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
        </div>
        <input
          v-model="search"
          class="history-search__input"
          placeholder="搜索推送历史..."
          type="text"
        />
      </div>

      <!-- Records List -->
      <div class="history-content">
        <div v-if="loading" class="history-empty">
          <div class="history-spinner" />
          <span>加载中…</span>
        </div>
        <div v-else-if="filteredGroups.length === 0" class="history-empty">
          <svg viewBox="0 0 24 24" fill="currentColor" class="history-empty__icon"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
          <span>{{ search ? '未找到匹配的推送记录' : '暂无推送记录' }}</span>
        </div>
        <div v-else class="history-groups">
          <template v-for="(group, gi) in filteredGroups" :key="gi">
            <p class="history-group-label">{{ group.label }}</p>
            <div class="history-cards">
              <div
                v-for="h in group.items"
                :key="h.id || h.generatedAt"
                class="history-card"
                :class="h.sent ? 'history-card--ok' : 'history-card--err'"
              >
                <!-- Error left accent bar -->
                <div v-if="!h.sent" class="history-card__err-bar" />

                <!-- Left: slot + meta -->
                <div class="history-card__left">
                  <h3 class="history-card__slot">{{ h.slotLabel || '手动推送' }}</h3>
                  <div class="history-card__meta">
                    <div class="history-card__meta-item">
                      <svg viewBox="0 0 24 24" fill="currentColor" class="history-card__meta-icon"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>
                      <span class="history-card__mono">{{ formatTime(h.generatedAt) }}</span>
                    </div>
                    <div class="history-card__meta-item">
                      <svg viewBox="0 0 24 24" fill="currentColor" class="history-card__meta-icon"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
                      <span class="history-card__text">{{ h.successCount }}/{{ h.agentCount }} 成功</span>
                    </div>
                  </div>
                  <div v-if="h.errorText" class="history-card__err-msg">{{ h.errorText }}</div>
                </div>

                <!-- Right: status -->
                <div class="history-card__right">
                  <svg v-if="h.sent" viewBox="0 0 24 24" fill="currentColor" class="history-card__status-icon history-card__status-icon--ok"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                  <svg v-else viewBox="0 0 24 24" fill="currentColor" class="history-card__status-icon history-card__status-icon--err"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
                  <span v-if="h.sent" class="history-card__status-label history-card__status-label--ok">推送成功</span>
                  <span v-else class="history-card__status-label history-card__status-label--err">{{ h.errorText || '推送失败' }}</span>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { fetchPushHistory } from '@/api/agents.js'

const route = useRoute()
const feishuBase = computed(() =>
  route.path.startsWith('/strategy/youzi_agents') ? '/strategy/youzi_agents' : '/strategy/agents'
)

const loading = ref(true)
const search = ref('')
const records = ref([])

// 取最近5条真实推送，排除 dry_run
const realRecords = computed(() => {
  return (records.value || []).filter(h => !h.dryRun).slice(0, 5)
})

// 按今天/昨天分组
const grouped = computed(() => {
  const today = []
  const yesterday = []

  for (const h of realRecords.value) {
    const d = _getDate(ts => h.generatedAt)
    if (d === 'today') today.push(h)
    else yesterday.push(h)
  }

  const groups = []
  if (today.length) groups.push({ label: '今天', items: today })
  if (yesterday.length) groups.push({ label: '昨天', items: yesterday })
  return groups
})

// 搜索过滤
const filteredGroups = computed(() => {
  if (!search.value.trim()) return grouped.value
  const q = search.value.trim().toLowerCase()
  return grouped.value
    .map(g => ({
      label: g.label,
      items: g.items.filter(h =>
        (h.slotLabel || '').toLowerCase().includes(q) ||
        (h.errorText || '').toLowerCase().includes(q)
      ),
    }))
    .filter(g => g.items.length > 0)
})

function _getDate(fn) {
  const ts = fn()
  if (!ts) return null
  try {
    const d = new Date(ts)
    const now = new Date()
    if (d.toDateString() === now.toDateString()) return 'today'
    const yd = new Date(now)
    yd.setDate(yd.getDate() - 1)
    if (d.toDateString() === yd.toDateString()) return 'yesterday'
    return null
  } catch {
    return null
  }
}

function formatTime(ts) {
  if (!ts) return '—'
  try {
    return new Date(ts).toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return ts
  }
}

async function loadRecords() {
  loading.value = true
  try {
    records.value = await fetchPushHistory(50)
  } catch {
    records.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadRecords()
})
</script>

<style scoped>
.history-page {
  min-height: 100dvh;
  background: #f7f9fb;
  color: #191c1e;
  font-family: 'Manrope', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── TopAppBar ── */
.history-topbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  height: 64px;
  background: #ffffff;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.topbar-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: transparent;
  border: none;
  cursor: pointer;
  color: #43474e;
  transition: background 0.15s;
}

.topbar-btn:hover { background: #f2f4f6; }
.topbar-btn svg { width: 22px; height: 22px; }

.topbar-title {
  font-size: 20px;
  font-weight: 700;
  color: #191c1e;
  letter-spacing: -0.01em;
}

.topbar-spacer { width: 40px; }

/* ── Main ── */
.history-main {
  padding: 80px 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ── Search ── */
.history-search {
  position: relative;
  width: 100%;
}

.history-search__icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: #74777f;
  display: grid;
  place-items: center;
}

.history-search__icon svg { width: 20px; height: 20px; }

.history-search__input {
  width: 100%;
  padding: 11px 14px 11px 44px;
  border: 1px solid #c4c6cf;
  border-radius: 999px;
  background: #ffffff;
  font-family: 'Manrope', -apple-system, sans-serif;
  font-size: 14px;
  color: #191c1e;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
  box-sizing: border-box;
}

.history-search__input::placeholder { color: #74777f; }
.history-search__input:focus {
  border-color: #002045;
  box-shadow: 0 0 0 3px rgba(0, 32, 69, 0.08);
}

/* ── Content ── */
.history-content {}

/* ── Empty ── */
.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 64px 0;
  color: #74777f;
  font-size: 14px;
}

.history-empty__icon {
  width: 48px;
  height: 48px;
  opacity: 0.3;
}

.history-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(116, 119, 127, 0.2);
  border-top-color: #74777f;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* ── Groups ── */
.history-groups {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.history-group-label {
  font-size: 12px;
  font-weight: 700;
  color: #74777f;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 12px 0 8px;
  margin: 0;
}

.history-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── Record Card ── */
.history-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border: 1px solid #eceef0;
  transition: box-shadow 0.2s;
  position: relative;
  overflow: hidden;
}

.history-card:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
}

.history-card--ok { border-color: #eceef0; }
.history-card--err {
  border-color: #ffdad6;
  background: #fffbfb;
}

.history-card__err-bar {
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: #ba1a1a;
  border-radius: 12px 0 0 12px;
}

.history-card__left {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.history-card__slot {
  font-size: 16px;
  font-weight: 600;
  color: #191c1e;
  line-height: 1.3;
  margin: 0;
}

.history-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}

.history-card__meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.history-card__meta-icon {
  width: 15px;
  height: 15px;
  color: #74777f;
  flex-shrink: 0;
}

.history-card__mono {
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 13px;
  color: #43474e;
}

.history-card__text {
  font-size: 14px;
  color: #43474e;
}

.history-card__err-msg {
  font-size: 12px;
  color: #ba1a1a;
  background: #ffdad6;
  padding: 3px 8px;
  border-radius: 6px;
  width: fit-content;
}

.history-card__right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}

.history-card__status-icon {
  width: 22px;
  height: 22px;
}

.history-card__status-icon--ok { color: #006e2f; }
.history-card__status-icon--err { color: #ba1a1a; }

.history-card__status-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-align: right;
  white-space: nowrap;
}

.history-card__status-label--ok { color: #006e2f; }
.history-card__status-label--err { color: #ba1a1a; }

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Responsive ── */
@media (min-width: 768px) {
  .history-main {
    max-width: 640px;
    margin: 0 auto;
  }
  .history-topbar {
    max-width: 640px;
    left: 50%;
    transform: translateX(-50%);
  }
}
</style>
