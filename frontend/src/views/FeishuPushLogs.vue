<template>
  <div class="logs-page">
    <!-- TopAppBar -->
    <header class="logs-topbar">
      <button type="button" class="topbar-btn" @click="$router.push(feishuBase)">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
      </button>
      <h1 class="topbar-title">飞书推送配置变更记录</h1>
      <div class="topbar-actions">
        <button type="button" class="topbar-action-btn" title="新增配置" @click="$router.push(`${feishuBase}/feishu/edit`)">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
        </button>
      </div>
    </header>

    <main class="logs-main">
      <!-- Grouped Log List -->
      <div v-if="loading" class="logs-empty">
        <div class="logs-spinner" />
        <span>加载中…</span>
      </div>

      <template v-else>
        <!-- Empty State -->
        <div v-if="!configLogs.length" class="logs-empty">
          <svg viewBox="0 0 24 24" fill="currentColor" class="logs-empty__icon"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>
          <span>暂无配置变更记录</span>
        </div>

        <!-- Grouped by date -->
        <section v-for="group in groupedLogs" :key="group.dateKey" class="logs-section">
          <div class="logs-section__head">
            <h2 class="logs-section__label">{{ group.label }}</h2>
            <span class="logs-section__date">{{ group.fullDate }}</span>
          </div>

          <div class="logs-section__cards">
            <div
              v-for="log in group.items"
              :key="log.id"
              class="log-card"
            >
              <!-- Header: time + title + status -->
              <div class="log-card__head">
                <div class="log-card__time-wrap">
                  <span class="log-card__time">{{ formatTime(log.changedAt) }}</span>
                  <span class="log-card__divider" />
                  <span class="log-card__title">{{ logTitle(log) }}</span>
                </div>
                <span class="log-card__status-badge">成功</span>
              </div>

              <!-- Detail lines -->
              <div class="log-card__details">
                <template v-for="(line, idx) in buildDetailLines(log)" :key="idx">
                  <div class="log-detail-line">
                    <svg viewBox="0 0 24 24" fill="currentColor" class="log-detail-line__icon" :class="line.iconClass">
                      <!-- link → webhook -->
                      <path v-if="line.icon === 'link'" d="M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z"/>
                      <!-- add_circle → agent add -->
                      <path v-if="line.icon === 'add_circle'" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 11h-4v4h-2v-4H7v-2h4V7h2v4h4v2z"/>
                      <!-- remove_circle → agent remove -->
                      <path v-if="line.icon === 'remove_circle'" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 11H7v-2h10v2z"/>
                      <!-- bolt → param/concurrency -->
                      <path v-if="line.icon === 'bolt'" d="M7 2v11h3v9l7-12h-4l4-8z"/>
                      <!-- schedule → slot -->
                      <path v-if="line.icon === 'schedule'" d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/>
                      <!-- toggle_on/toggle_off → enable/disable -->
                      <path v-if="line.icon === 'toggle_on'" d="M17 7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h10c2.76 0 5-2.24 5-5s-2.24-5-5-5zm0 8H7c-1.66 0-3-1.34-3-3s1.34-3 3-3h10c1.66 0 3 1.34 3 3s-1.34 3-3 3z"/>
                    </svg>
                    <span class="log-detail-line__text" v-html="line.text" />
                  </div>
                </template>
              </div>

              <!-- Action Buttons -->
              <div class="log-card__actions">
                <button
                  type="button"
                  class="log-action log-action--view"
                  @click="$router.push(`${feishuBase}/feishu/edit`)"
                >
                  查看
                </button>
                <button
                  type="button"
                  class="log-action log-action--edit"
                  @click="$router.push(`${feishuBase}/feishu/edit`)"
                >
                  <svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>
                  编辑
                </button>
                <button
                  type="button"
                  class="log-action log-action--delete"
                  @click="deleteLog(log.id)"
                >
                  <svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
                  删除
                </button>
              </div>
            </div>
          </div>
        </section>
      </template>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchPushConfigLogs, deletePushConfigLog } from '@/api/agents.js'

const route = useRoute()
const router = useRouter()

// 动态返回父级路径，支持 /strategy/agents 和 /strategy/youzi_agents 两条入口
const feishuBase = computed(() =>
  route.path.startsWith('/strategy/youzi_agents') ? '/strategy/youzi_agents' : '/strategy/agents'
)

const loading = ref(true)
const configLogs = ref([])

// ── Group by date ──────────────────────────────────────────────────────────
const groupedLogs = computed(() => {
  const groups = {}
  for (const log of configLogs.value) {
    const d = new Date(log.changedAt)
    const now = new Date()
    const todayStr = now.toDateString()
    const yd = new Date(now)
    yd.setDate(yd.getDate() - 1)
    const yesterdayStr = yd.toDateString()
    const dateStr = d.toDateString()

    let label, fullDate
    if (dateStr === todayStr) {
      label = '今天'
      fullDate = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日`
    } else if (dateStr === yesterdayStr) {
      label = '昨天'
      fullDate = `${yd.getFullYear()}年${yd.getMonth() + 1}月${yd.getDate()}日`
    } else {
      label = `${d.getMonth() + 1}月${d.getDate()}日`
      fullDate = `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
    }

    if (!groups[dateStr]) {
      groups[dateStr] = { label, fullDate, dateKey: dateStr, items: [] }
    }
    groups[dateStr].items.push(log)
  }
  return Object.values(groups)
})

// ── Helpers ─────────────────────────────────────────────────────────────────
function logTitle(log) {
  const map = {
    webhook_update: 'Webhook 配置更新',
    agent_add: '推送 Agent 调整',
    agent_remove: '推送 Agent 调整',
    slot_update: '定时推送计划更新',
    param_update: '并发限制调整',
    enable_toggle: '推送开关切换',
  }
  return map[log.changeType] || '配置变更'
}

function buildDetailLines(log) {
  const d = log.details || {}
  const lines = []

  switch (log.changeType) {
    case 'webhook_update':
      lines.push({
        icon: 'link',
        iconClass: 'log-icon--primary',
        text: `Webhook 地址已更新：由旧地址指向 <code>${(d.new || '').slice(0, 40)}${(d.new || '').length > 40 ? '...' : ''}</code>`,
      })
      break

    case 'agent_add':
      lines.push({
        icon: 'add_circle',
        iconClass: 'log-icon--primary',
        text: `新增了推送角色：<strong>${d.agent_name || ''}</strong>`,
      })
      break

    case 'agent_remove':
      lines.push({
        icon: 'remove_circle',
        iconClass: 'log-icon--error',
        text: `移除了推送角色：<strong>${d.agent_name || ''}</strong>`,
      })
      break

    case 'slot_update':
      lines.push({
        icon: 'schedule',
        iconClass: 'log-icon--primary',
        text: `更新了定时推送时段，新增了 <strong>"${d.new_label || ''}"</strong>`,
      })
      break

    case 'param_update': {
      const paramNames = {
        analysis_max_workers: '并发数',
        consensus_top_n: '共识股上限',
        top_stocks_per_agent: '每Agent推荐股',
      }
      const name = paramNames[d.param] || d.param || ''
      if (d.param === 'analysis_max_workers') {
        lines.push({
          icon: 'bolt',
          iconClass: 'log-icon--primary',
          text: `修改了并发数，从 <strong>${d.old}</strong> 提高到 <strong>${d.new}</strong>`,
        })
      } else {
        lines.push({
          icon: 'bolt',
          iconClass: 'log-icon--primary',
          text: `修改了 ${name}，从 <strong>${d.old}</strong> 调整为 <strong>${d.new}</strong>`,
        })
      }
      break
    }

    case 'enable_toggle':
      lines.push({
        icon: 'toggle_on',
        iconClass: 'log-icon--primary',
        text: `推送开关已${d.new ? '启用' : '停用'}`,
      })
      break
  }

  return lines
}

function formatTime(ts) {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
  } catch {
    return ts
  }
}

// ── Actions ────────────────────────────────────────────────────────────────
async function loadLogs() {
  loading.value = true
  try {
    configLogs.value = await fetchPushConfigLogs(100)
  } catch {
    configLogs.value = []
  } finally {
    loading.value = false
  }
}

async function deleteLog(logId) {
  try {
    await deletePushConfigLog(logId)
    configLogs.value = configLogs.value.filter(l => l.id !== logId)
  } catch {
    // ignore
  }
}

onMounted(() => {
  loadLogs()
})
</script>

<style scoped>
.logs-page {
  min-height: 100dvh;
  background: #f7f9fb;
  color: #191c1e;
  font-family: 'Manrope', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── TopAppBar ── */
.logs-topbar {
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
  color: #002045;
  transition: background 0.15s;
}

.topbar-btn:hover { background: #f2f4f6; }
.topbar-btn svg { width: 22px; height: 22px; }

.topbar-title {
  font-size: 17px;
  font-weight: 700;
  color: #002045;
  letter-spacing: -0.01em;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.topbar-action-btn {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: grid;
  place-items: center;
  color: #002045;
  transition: background 0.15s;
}

.topbar-action-btn:hover { background: #f2f4f6; }
.topbar-action-btn svg { width: 22px; height: 22px; }

/* ── Main ── */
.logs-main {
  padding: 80px 16px 32px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* ── Section ── */
.logs-section {}

.logs-section__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px 12px;
}

.logs-section__label {
  font-size: 12px;
  font-weight: 700;
  color: #74777f;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin: 0;
}

.logs-section__date {
  font-size: 12px;
  color: #74777f;
  font-weight: 500;
}

.logs-section__cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── Log Card ── */
.log-card {
  background: #ffffff;
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border: 1px solid #ffffff;
  position: relative;
  overflow: hidden;
}

.log-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 8px;
}

.log-card__time-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.log-card__time {
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 13px;
  font-weight: 500;
  color: #002045;
  background: #d6e3ff;
  padding: 2px 8px;
  border-radius: 8px;
  flex-shrink: 0;
  white-space: nowrap;
}

.log-card__divider {
  width: 1px;
  height: 16px;
  background: #c4c6cf;
  flex-shrink: 0;
}

.log-card__title {
  font-size: 14px;
  font-weight: 600;
  color: #191c1e;
  line-height: 1.3;
}

.log-card__status-badge {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(0, 110, 47, 0.12);
  color: #006e2f;
  flex-shrink: 0;
}

/* ── Detail Lines ── */
.log-card__details {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.log-detail-line {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.log-detail-line__icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  margin-top: 1px;
}

.log-icon--primary { color: #002045; }
.log-icon--error { color: #ba1a1a; }

.log-detail-line__text {
  font-size: 14px;
  color: #43474e;
  line-height: 1.5;
}

.log-detail-line__text :deep(strong) {
  font-weight: 600;
  color: #191c1e;
}

.log-detail-line__text :deep(code) {
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 13px;
  background: #f2f4f6;
  color: #002045;
  padding: 1px 4px;
  border-radius: 4px;
}

/* ── Action Buttons ── */
.log-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #f7f9fb;
}

.log-action {
  flex: 1;
  min-width: 0;
  padding: 8px 4px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  transition: all 0.15s;
}

.log-action svg { width: 16px; height: 16px; }

.log-action--view {
  background: #002045;
  color: #ffffff;
}

.log-action--view:hover { opacity: 0.9; }

.log-action--edit {
  background: #ffffff;
  color: #002045;
  border: 1px solid #c4c6cf;
}

.log-action--edit:hover { background: #f2f4f6; }

.log-action--delete {
  background: #ffdad6;
  color: #ba1a1a;
  border: 1px solid #ffdad6;
}

.log-action--delete:hover { opacity: 0.85; }

/* ── Empty ── */
.logs-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 64px 0;
  color: #74777f;
  font-size: 14px;
}

.logs-empty__icon {
  width: 48px;
  height: 48px;
  opacity: 0.3;
}

.logs-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(116, 119, 127, 0.2);
  border-top-color: #74777f;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Responsive ── */
@media (min-width: 768px) {
  .logs-main {
    max-width: 640px;
    margin: 0 auto;
  }
  .logs-topbar {
    max-width: 640px;
    left: 50%;
    transform: translateX(-50%);
  }
}
</style>
