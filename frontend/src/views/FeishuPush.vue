<template>
  <div class="push-page">
    <!-- TopAppBar -->
    <header class="push-topbar">
      <button type="button" class="topbar-btn" @click="$router.push(`${feishuBase}/feishu`)">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
      </button>
      <h1 class="topbar-title">飞书推送管理</h1>
      <div class="topbar-toggle">
        <span class="topbar-toggle__label">ON</span>
        <button
          type="button"
          class="topbar-toggle__btn"
          :class="cfg.enabled ? 'topbar-toggle__btn--on' : 'topbar-toggle__btn--off'"
          :disabled="saving"
          @click="toggleEnabled"
        >
          <span class="topbar-toggle__knob" />
        </button>
      </div>
    </header>

    <main class="push-main">
      <!-- Section 1: Status -->
      <section class="push-card">
        <div class="push-card__head">
          <h2 class="push-card__title">调度状态</h2>
          <div class="push-card__right">
            <button type="button" class="push-card__link" @click="$router.push(`${feishuBase}/feishu/history`)">
              推送记录
              <svg viewBox="0 0 24 24" fill="currentColor" class="push-card__chevron"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
            </button>
            <div class="push-status-badge" :class="data?.running ? 'push-status-badge--running' : 'push-status-badge--stopped'">
              <span class="push-status-badge__dot" />
              <span>{{ data?.running ? 'Running' : 'Stopped' }}</span>
            </div>
          </div>
        </div>
        <div class="push-status-body">
          <div class="push-status-row">
            <p class="push-status-row__label">ACTIVE AGENTS</p>
            <p class="push-status-row__value">{{ (cfg.agentIds || []).join(', ') || '—' }}</p>
          </div>
          <div class="push-status-row push-status-row--border">
            <p class="push-status-row__label">NEXT PUSH</p>
            <div v-if="data?.nextSlot" class="push-status-row__next">
              <svg viewBox="0 0 24 24" fill="currentColor" class="push-status-row__clock"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>
              {{ data.nextSlot.slotLabel }} {{ data.nextSlot.scheduledAt }}
            </div>
            <span v-else class="push-status-row__value">—</span>
          </div>
        </div>
      </section>

      <!-- Section 2: Webhook -->
      <section class="push-card">
        <h2 class="push-card__title">Webhook URL</h2>
        <div class="push-webhook">
          <div class="push-webhook__input-wrap">
            <input
              v-model="cfg.webhookUrl"
              type="url"
              class="push-webhook__input"
              placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
              :disabled="saving"
              @blur="onWebhookBlur"
            />
            <button type="button" class="push-webhook__copy" @click="copyWebhook">
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>
            </button>
          </div>
          <button
            type="button"
            class="push-btn push-btn--secondary"
            :disabled="!cfg.webhookUrl || testLoading"
            @click="testWebhook"
          >
            <svg viewBox="0 0 24 24" fill="currentColor" class="push-btn__icon"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
            {{ testLoading ? '测试中…' : 'Test Connection' }}
          </button>
          <p v-if="testResult !== null" class="push-webhook__hint" :class="testResult ? 'push-webhook__hint--ok' : 'push-webhook__hint--err'">
            {{ testResult ? '✓ 测试消息发送成功，请检查飞书群' : '✗ 测试发送失败，请检查 Webhook 地址' }}
          </p>
        </div>
      </section>

      <!-- Section 3: Agents -->
      <section class="push-card">
        <div class="push-card__head">
          <h2 class="push-card__title">推送 Agent</h2>
          <span class="push-card__badge">{{ cfg.agentIds?.length || 0 }}/{{ availableAgents.length }} SELECTED</span>
        </div>
        <div class="push-agent-chips">
          <button
            v-for="ag in availableAgents"
            :key="ag.id"
            type="button"
            class="push-agent-chip"
            :class="{ 'push-agent-chip--active': (cfg.agentIds || []).includes(ag.id) }"
            :disabled="saving"
            @click="toggleAgent(ag.id)"
          >
            <svg v-if="(cfg.agentIds || []).includes(ag.id)" viewBox="0 0 24 24" fill="currentColor" class="push-agent-chip__check"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
            {{ ag.name }}
          </button>
        </div>
      </section>

      <!-- Section 4: Config Params -->
      <section class="push-card">
        <h2 class="push-card__title">Configuration Parameters</h2>
        <div class="push-params">
          <div class="push-param-row">
            <div class="push-param-row__left">
              <p class="push-param-row__name">每 Agent 推荐股</p>
              <p class="push-param-row__label">STOCKS PER AGENT</p>
            </div>
            <div class="push-stepper">
              <button type="button" class="push-stepper__btn" :disabled="cfg.topStocksPerAgent <= 1 || saving" @click="cfg.topStocksPerAgent = Math.max(1, cfg.topStocksPerAgent - 1)">
                <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 13H5v-2h14v2z"/></svg>
              </button>
              <span class="push-stepper__val">{{ cfg.topStocksPerAgent }}</span>
              <button type="button" class="push-stepper__btn" :disabled="cfg.topStocksPerAgent >= 10 || saving" @click="cfg.topStocksPerAgent = Math.min(10, cfg.topStocksPerAgent + 1)">
                <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
              </button>
            </div>
          </div>
          <div class="push-param-row">
            <div class="push-param-row__left">
              <p class="push-param-row__name">共识股上限</p>
              <p class="push-param-row__label">CONSENSUS LIMIT</p>
            </div>
            <div class="push-stepper">
              <button type="button" class="push-stepper__btn" :disabled="cfg.consensusTopN <= 1 || saving" @click="cfg.consensusTopN = Math.max(1, cfg.consensusTopN - 1)">
                <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 13H5v-2h14v2z"/></svg>
              </button>
              <span class="push-stepper__val">{{ cfg.consensusTopN }}</span>
              <button type="button" class="push-stepper__btn" :disabled="cfg.consensusTopN >= 20 || saving" @click="cfg.consensusTopN = Math.min(20, cfg.consensusTopN + 1)">
                <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
              </button>
            </div>
          </div>
          <div class="push-param-row">
            <div class="push-param-row__left">
              <p class="push-param-row__name">并发数</p>
              <p class="push-param-row__label">CONCURRENCY</p>
            </div>
            <div class="push-stepper">
              <button type="button" class="push-stepper__btn" :disabled="cfg.analysisMaxWorkers <= 1 || saving" @click="cfg.analysisMaxWorkers = Math.max(1, cfg.analysisMaxWorkers - 1)">
                <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 13H5v-2h14v2z"/></svg>
              </button>
              <span class="push-stepper__val">{{ cfg.analysisMaxWorkers }}</span>
              <button type="button" class="push-stepper__btn" :disabled="cfg.analysisMaxWorkers >= 8 || saving" @click="cfg.analysisMaxWorkers = Math.min(8, cfg.analysisMaxWorkers + 1)">
                <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Section 5: Time Slots -->
      <section class="push-card push-card--last">
        <h2 class="push-card__title">定时推送时段</h2>
        <div class="push-slots">
          <div
            v-for="slot in slots"
            :key="slot.key"
            class="push-slot-item"
            :class="slot.enabled ? 'push-slot-item--active' : 'push-slot-item--inactive'"
            @click="slot.enabled = !slot.enabled"
          >
            <div class="push-slot-item__check" :class="slot.enabled ? 'push-slot-item__check--on' : 'push-slot-item__check--off'">
              <svg v-if="slot.enabled" viewBox="0 0 24 24" fill="currentColor" class="push-slot-item__check-icon"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
            </div>
            <div class="push-slot-item__content">
              <span class="push-slot-item__time">{{ slot.time }}</span>
              <span class="push-slot-item__label">{{ slot.label }}</span>
            </div>
            <span v-if="slot.enabled" class="push-slot-item__dot" />
          </div>
        </div>
      </section>

      <!-- Error -->
      <div v-if="errorMsg" class="push-error">{{ errorMsg }}</div>
    </main>

    <!-- Bottom Action Bar -->
    <div class="push-bottombar">
      <button
        type="button"
        class="push-bottombar__btn push-bottombar__btn--secondary"
        :disabled="triggering || loading"
        @click="triggerNow"
      >
        <svg v-if="triggering" viewBox="0 0 24 24" fill="currentColor" class="push-spinner-icon"><path d="M12 6v3l4-4-4-4v3c-4.42 0-8 3.58-8 8 0 1.57.46 3.03 1.24 4.26L6.7 14.8c-.45-.83-.7-1.79-.7-2.8 0-3.31 2.69-6 6-6zm6.76 1.74L17.3 9.2c.44.84.7 1.79.7 2.8 0 3.31-2.69 6-6 6v-3l-4 4 4 4v-3c4.42 0 8-3.58 8-8 0-1.57-.46-3.03-1.24-4.26z"/></svg>
        {{ triggering ? '推送中…' : '立即推送一次' }}
      </button>
      <button
        type="button"
        class="push-bottombar__btn push-bottombar__btn--primary"
        :disabled="saving || loading"
        @click="saveConfig"
      >
        <svg v-if="saving" viewBox="0 0 24 24" fill="currentColor" class="push-spinner-icon"><path d="M12 6v3l4-4-4-4v3c-4.42 0-8 3.58-8 8 0 1.57.46 3.03 1.24 4.26L6.7 14.8c-.45-.83-.7-1.79-.7-2.8 0-3.31 2.69-6 6-6zm6.76 1.74L17.3 9.2c.44.84.7 1.79.7 2.8 0 3.31-2.69 6-6 6v-3l-4 4 4 4v-3c4.42 0 8-3.58 8-8 0-1.57-.46-3.03-1.24-4.26z"/></svg>
        {{ saving ? '保存中…' : '保存配置' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { fetchPushStatus, savePushConfig, triggerPush, testFeishuWebhook } from '@/api/agents.js'

const route = useRoute()

const feishuBase = computed(() =>
  route.path.startsWith('/strategy/youzi_agents') ? '/strategy/youzi_agents' : '/strategy/agents'
)

const loading = ref(false)
const saving = ref(false)
const triggering = ref(false)
const testLoading = ref(false)
const testResult = ref(null)
const errorMsg = ref('')

const data = ref(null)

const cfg = reactive({
  enabled: true,
  webhookUrl: '',
  agentIds: [],
  topStocksPerAgent: 3,
  consensusTopN: 5,
  analysisMaxWorkers: 2,
})

const slots = ref([])

const availableAgents = [
  { id: 'beijing',  name: '北京炒家' },
  { id: 'qiao',     name: '乔帮主' },
  { id: 'jia',      name: '炒股养家' },
  { id: 'jun',      name: '钧哥天下无双' },
  { id: 'speed',    name: '极速先锋' },
  { id: 'trend',    name: '趋势追随者' },
  { id: 'quant',    name: '量化之翼' },
  { id: 'deepseek', name: '深度思考者' },
]

async function loadStatus() {
  loading.value = true
  errorMsg.value = ''
  try {
    const d = await fetchPushStatus()
    data.value = d
    cfg.enabled = d.enabled ?? true
    cfg.webhookUrl = d.webhook_url || ''
    cfg.agentIds = d.agent_ids || []
    cfg.topStocksPerAgent = d.top_stocks_per_agent ?? 3
    cfg.consensusTopN = d.consensus_top_n ?? 5
    cfg.analysisMaxWorkers = d.analysis_max_workers ?? 2
    slots.value = (d.slots || []).map(s => ({ ...s }))
  } catch (e) {
    errorMsg.value = '加载失败：' + (e.message || '未知错误')
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  saving.value = true
  errorMsg.value = ''
  testResult.value = null
  try {
    const payload = {
      enabled: cfg.enabled,
      webhook_url: cfg.webhookUrl,
      agent_ids: cfg.agentIds,
      top_stocks_per_agent: cfg.topStocksPerAgent,
      consensus_top_n: cfg.consensusTopN,
      analysis_max_workers: cfg.analysisMaxWorkers,
      slot_updates: slots.value.map(s => ({
        key: s.key,
        enabled: s.enabled,
        label: s.label,
        time: s.time,
      })),
    }
    console.log('[saveConfig] payload:', JSON.stringify(payload, null, 2))
    // Optimistic update — apply locally first so UI responds immediately
    const savedSlots = slots.value.map(s => ({ ...s }))
    const savedCfg = {
      enabled: cfg.enabled,
      webhookUrl: cfg.webhookUrl,
      agentIds: [...cfg.agentIds],
      topStocksPerAgent: cfg.topStocksPerAgent,
      consensusTopN: cfg.consensusTopN,
      analysisMaxWorkers: cfg.analysisMaxWorkers,
    }
    const result = await savePushConfig(payload)
    console.log('[saveConfig] result:', result)
    // Apply server response
    cfg.enabled = result.enabled ?? cfg.enabled
    cfg.webhookUrl = result.webhook_url || cfg.webhookUrl
    cfg.agentIds = result.agent_ids || cfg.agentIds
    cfg.topStocksPerAgent = result.top_stocks_per_agent ?? cfg.topStocksPerAgent
    cfg.consensusTopN = result.consensus_top_n ?? cfg.consensusTopN
    cfg.analysisMaxWorkers = result.analysis_max_workers ?? cfg.analysisMaxWorkers
    if (result.slots) {
      slots.value = result.slots.map(s => ({ ...s }))
    }
  } catch (e) {
    console.error('[saveConfig] error:', e)
    errorMsg.value = '保存失败：' + (e.message || String(e))
  } finally {
    saving.value = false
  }
}

function toggleEnabled() {
  cfg.enabled = !cfg.enabled
  saveConfig()
}

function toggleAgent(id) {
  const idx = cfg.agentIds.indexOf(id)
  if (idx === -1) {
    cfg.agentIds.push(id)
  } else {
    cfg.agentIds.splice(idx, 1)
  }
}

async function triggerNow() {
  triggering.value = true
  errorMsg.value = ''
  try {
    await triggerPush({ webhook_url: cfg.webhookUrl || undefined })
  } catch (e) {
    errorMsg.value = '推送失败：' + (e.message || '未知错误')
  } finally {
    triggering.value = false
  }
}

async function testWebhook() {
  testLoading.value = true
  testResult.value = null
  errorMsg.value = ''
  try {
    const res = await testFeishuWebhook(cfg.webhookUrl)
    testResult.value = res.success
    if (!res.success) errorMsg.value = res.message || '测试失败'
  } catch (e) {
    testResult.value = false
    errorMsg.value = e.message || '测试失败'
  } finally {
    testLoading.value = false
  }
}

function copyWebhook() {
  if (!cfg.webhookUrl) return
  navigator.clipboard.writeText(cfg.webhookUrl).catch(() => {})
}

function onWebhookBlur() {
  testResult.value = null
}

onMounted(async () => {
  await loadStatus()
})
</script>

<style scoped>
.push-page {
  min-height: 100dvh;
  background: #f7f9fb;
  color: #191c1e;
  font-family: 'Manrope', -apple-system, BlinkMacSystemFont, sans-serif;
  padding-bottom: 100px;
}

/* ── TopAppBar ── */
.push-topbar {
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
  font-size: 17px;
  font-weight: 700;
  color: #191c1e;
  letter-spacing: -0.02em;
}

.topbar-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
}

.topbar-toggle__label {
  font-size: 12px;
  font-weight: 700;
  color: #74777f;
  letter-spacing: 0.05em;
}

.topbar-toggle__btn {
  width: 48px;
  height: 28px;
  border-radius: 14px;
  border: none;
  cursor: pointer;
  position: relative;
  transition: background 0.2s;
  padding: 2px;
}

.topbar-toggle__btn--on  { background: #002045; }
.topbar-toggle__btn--off { background: #d8dadc; }
.topbar-toggle__btn:disabled { opacity: 0.5; cursor: not-allowed; }

.topbar-toggle__knob {
  display: block;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
  transition: transform 0.2s;
  position: absolute;
  top: 2px;
  right: 2px;
}

.topbar-toggle__btn--on .topbar-toggle__knob  { transform: translateX(-20px); }
.topbar-toggle__btn--off .topbar-toggle__knob { transform: translateX(0); }

/* ── Main ── */
.push-main {
  padding: 80px 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── Card ── */
.push-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border: 1px solid #eceef0;
}

.push-card--last {
  margin-bottom: 0;
}

.push-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 12px;
}

.push-card__title {
  font-size: 20px;
  font-weight: 600;
  color: #191c1e;
  letter-spacing: -0.01em;
  line-height: 1.4;
}

.push-card__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.push-card__link {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  font-weight: 700;
  color: #74777f;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  transition: color 0.15s;
}

.push-card__link:hover { color: #002045; }
.push-card__chevron { width: 16px; height: 16px; }

/* ── Status badge ── */
.push-status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.push-status-badge--running {
  background: rgba(0, 110, 47, 0.1);
  color: #006e2f;
}
.push-status-badge--stopped {
  background: #f2f4f6;
  color: #74777f;
}

.push-status-badge__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.push-status-badge--running .push-status-badge__dot { background: #006e2f; }
.push-status-badge--stopped .push-status-badge__dot { background: #74777f; }

/* ── Status body ── */
.push-status-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.push-status-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.push-status-row--border {
  padding-top: 12px;
  border-top: 1px solid #e0e3e5;
}

.push-status-row__label {
  font-size: 12px;
  font-weight: 700;
  color: #74777f;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.push-status-row__value {
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 13px;
  color: #43474e;
  word-break: break-all;
}

.push-status-row__next {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 13px;
  color: #1a365d;
  background: rgba(214, 227, 255, 0.4);
  padding: 6px 10px;
  border-radius: 8px;
}

.push-status-row__clock {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

/* ── Webhook ── */
.push-webhook {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.push-webhook__input-wrap {
  position: relative;
}

.push-webhook__input {
  width: 100%;
  padding: 12px 44px 12px 12px;
  border: 1px solid #c4c6cf;
  border-radius: 8px;
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 13px;
  color: #191c1e;
  background: #f7f9fb;
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}

.push-webhook__input:focus { border-color: #002045; }
.push-webhook__input:disabled { opacity: 0.5; }

.push-webhook__copy {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  cursor: pointer;
  color: #74777f;
  padding: 4px;
  display: grid;
  place-items: center;
  transition: color 0.15s;
}

.push-webhook__copy:hover { color: #002045; }
.push-webhook__copy svg { width: 18px; height: 18px; }

.push-webhook__hint {
  font-size: 13px;
  margin: 0;
}
.push-webhook__hint--ok  { color: #006e2f; }
.push-webhook__hint--err { color: #ba1a1a; }

/* ── Buttons ── */
.push-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 10px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  border: 1px solid #e0e3e5;
  background: #ffffff;
  color: #191c1e;
}

.push-btn:hover:not(:disabled) { background: #f2f4f6; }
.push-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.push-btn__icon { width: 18px; height: 18px; }

/* ── Agent Chips ── */
.push-agent-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.push-agent-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1.5px solid #c4c6cf;
  background: #ffffff;
  font-size: 14px;
  font-weight: 500;
  color: #43474e;
  cursor: pointer;
  transition: all 0.15s;
}

.push-agent-chip:hover:not(:disabled) { border-color: #002045; }
.push-agent-chip--active {
  background: #d6e3ff;
  border-color: #d6e3ff;
  color: #001b3c;
}
.push-agent-chip:disabled { opacity: 0.5; cursor: not-allowed; }
.push-agent-chip__check { width: 14px; height: 14px; flex-shrink: 0; }

/* ── Params ── */
.push-params {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.push-param-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  background: #f7f9fb;
  border-radius: 8px;
  border: 1px solid #e0e3e5;
}

.push-param-row__left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.push-param-row__name {
  font-size: 14px;
  font-weight: 500;
  color: #191c1e;
}

.push-param-row__label {
  font-size: 12px;
  font-weight: 700;
  color: #74777f;
  letter-spacing: 0.05em;
}

/* ── Stepper ── */
.push-stepper {
  display: flex;
  align-items: center;
  gap: 4px;
  background: #ffffff;
  border: 1px solid #c4c6cf;
  border-radius: 8px;
  padding: 4px;
}

.push-stepper__btn {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: grid;
  place-items: center;
  color: #74777f;
  transition: all 0.15s;
}

.push-stepper__btn:hover:not(:disabled) { color: #002045; background: #f2f4f6; }
.push-stepper__btn:disabled { opacity: 0.3; cursor: not-allowed; }
.push-stepper__btn svg { width: 18px; height: 18px; }

.push-stepper__val {
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: #191c1e;
  min-width: 24px;
  text-align: center;
}

/* ── Slots ── */
.push-slots {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.push-slot-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
  border: 1.5px solid transparent;
}

.push-slot-item--active {
  background: rgba(214, 227, 255, 0.25);
  border-color: #d6e3ff;
}

.push-slot-item--inactive {
  background: #f7f9fb;
  border-color: #e0e3e5;
}

.push-slot-item__check {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  transition: all 0.15s;
  border: 2px solid transparent;
}

.push-slot-item__check--on {
  background: #002045;
  border-color: #002045;
}

.push-slot-item__check--off {
  background: #ffffff;
  border-color: #c4c6cf;
}

.push-slot-item__check-icon {
  width: 14px;
  height: 14px;
  color: #ffffff;
}

.push-slot-item__content {
  flex: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.push-slot-item__time {
  font-size: 16px;
  font-weight: 500;
  color: #191c1e;
}

.push-slot-item__label {
  font-size: 14px;
}

.push-slot-item--active .push-slot-item__label { color: #1a365d; }
.push-slot-item--inactive .push-slot-item__label { color: #74777f; }

.push-slot-item__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #006e2f;
  flex-shrink: 0;
}

/* ── Error ── */
.push-error {
  padding: 12px 14px;
  background: #ffdad6;
  border: 1px solid #ba1a1a;
  border-radius: 10px;
  color: #93000a;
  font-size: 14px;
}

/* ── History Panel ── */
.push-history-panel {
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #eceef0;
  overflow: hidden;
}

.push-history-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #eceef0;
}

.push-history-panel__title {
  font-size: 16px;
  font-weight: 600;
  color: #191c1e;
}

.push-history-panel__close {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: #f2f4f6;
  cursor: pointer;
  display: grid;
  place-items: center;
  color: #74777f;
  transition: background 0.15s;
}

.push-history-panel__close:hover { background: #e0e3e5; }
.push-history-panel__close svg { width: 18px; height: 18px; }

.push-history-panel__loading,
.push-history-panel__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 32px;
  color: #74777f;
  font-size: 14px;
}

.push-history-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-height: 420px;
  overflow-y: auto;
  padding: 0 16px 16px;
}

.push-history-group-label {
  font-size: 12px;
  font-weight: 700;
  color: #74777f;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 12px 0 8px;
}

.push-history-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── Record Card ── */
.push-record-card {
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

.push-record-card:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08);
}

.push-record-card--ok {
  border-color: #eceef0;
}

.push-record-card--err {
  border-color: #ffdad6;
  background: #fffbfb;
}

.push-record-card__err-bar {
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: #ba1a1a;
  border-radius: 12px 0 0 12px;
}

.push-record-card__left {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.push-record-card__slot {
  font-size: 16px;
  font-weight: 600;
  color: #191c1e;
  line-height: 1.3;
  margin: 0;
}

.push-record-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}

.push-record-card__meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.push-record-card__meta-icon {
  width: 15px;
  height: 15px;
  color: #74777f;
  flex-shrink: 0;
}

.push-record-card__mono {
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 13px;
  color: #43474e;
}

.push-record-card__text {
  font-size: 14px;
  color: #43474e;
}

.push-record-card__err-msg {
  font-size: 12px;
  color: #ba1a1a;
  background: #ffdad6;
  padding: 3px 8px;
  border-radius: 6px;
  width: fit-content;
}

.push-record-card__right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}

.push-record-card__status-icon {
  width: 22px;
  height: 22px;
}

.push-record-card__status-icon--ok { color: #006e2f; }
.push-record-card__status-icon--err { color: #ba1a1a; }

.push-record-card__status-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-align: right;
  white-space: nowrap;
}

.push-record-card__status-label--ok { color: #006e2f; }
.push-record-card__status-label--err { color: #ba1a1a; }

/* ── Bottom Bar ── */
.push-bottombar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 50;
  display: flex;
  gap: 12px;
  padding: 16px;
  background: #ffffff;
  border-top: 1px solid #eceef0;
  box-shadow: 0 -8px 16px rgba(0, 0, 0, 0.05);
}

.push-bottombar__btn {
  flex: 1;
  height: 52px;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: none;
}

.push-bottombar__btn:disabled { opacity: 0.5; cursor: not-allowed; }

.push-bottombar__btn--secondary {
  background: #ffffff;
  border: 1.5px solid #c4c6cf;
  color: #191c1e;
}

.push-bottombar__btn--secondary:hover:not(:disabled) { border-color: #002045; }

.push-bottombar__btn--primary {
  background: #002045;
  color: #ffffff;
  box-shadow: 0 4px 12px rgba(0, 32, 69, 0.2);
}

.push-bottombar__btn--primary:hover:not(:disabled) { opacity: 0.9; }

.push-spinner-icon {
  width: 18px;
  height: 18px;
  animation: spin 0.8s linear infinite;
}

.push-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(116, 119, 127, 0.2);
  border-top-color: #74777f;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Transitions ── */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.25s ease;
}
.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ── Card badge ── */
.push-card__badge {
  font-size: 12px;
  font-weight: 700;
  color: #74777f;
  background: #eceef0;
  padding: 4px 8px;
  border-radius: 6px;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

/* ── Responsive ── */
@media (min-width: 768px) {
  .push-main {
    max-width: 640px;
    margin: 0 auto;
  }
  .push-bottombar {
    max-width: 640px;
    left: 50%;
    transform: translateX(-50%);
  }
  .push-topbar {
    max-width: 640px;
    left: 50%;
    transform: translateX(-50%);
  }
}
</style>
