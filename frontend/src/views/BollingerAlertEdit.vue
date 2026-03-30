<template>
  <div class="bae-page">
    <!-- TopAppBar -->
    <header class="bae-topbar">
      <button type="button" class="bae-icon-btn" aria-label="返回" @click="goBack">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <h2 class="bae-nav-title">告警设置</h2>
      <div class="bae-topbar__right">
        <span v-if="form.enabled" class="bae-status-badge">已启用</span>
        <button type="button" class="bae-icon-btn" aria-label="更多" @click="showMore = !showMore">
          <svg class="icon" viewBox="0 0 24 24"><path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/></svg>
        </button>
      </div>
    </header>

    <!-- More dropdown -->
    <div v-if="showMore && isEdit" class="bae-more-menu">
      <button type="button" class="bae-more-item bae-more-item--danger" @click="onDelete">
        <svg class="icon" viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/></svg>
        删除规则
      </button>
    </div>

    <main class="bae-main">

      <!-- Strategy Header (Bento) -->
      <section class="bae-bento-grid">
        <div class="bae-card bae-card--white">
          <p class="bae-card__eyebrow">策略名称</p>
          <input
            v-model="form.rule_name"
            type="text"
            class="bae-name-input"
            placeholder="输入规则名称..."
            maxlength="200"
          >
          <div class="bae-live-tag">
            <span class="bae-live-dot" />
            <span>实时监控中</span>
          </div>
        </div>
        <div class="bae-card bae-card--blue-tint">
          <div class="bae-flex-center">
            <div class="bae-lark-icon">
              <svg class="icon" viewBox="0 0 24 24" style="font-size:22px;fill:currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
            </div>
            <div>
              <p class="bae-card__eyebrow bae-card__eyebrow--blue">飞书告警设置</p>
              <p class="bae-card__sub">Lark Webhook Integration</p>
            </div>
          </div>
        </div>
      </section>

      <!-- Webhook Configuration -->
      <section class="bae-card bae-card--white">
        <label class="bae-label">Webhook 地址</label>
        <div class="bae-webhook-row">
          <input
            v-model="form.webhook_url"
            type="url"
            class="bae-input bae-input--full"
            placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
          >
          <button
            type="button"
            class="bae-btn bae-btn--outline"
            :disabled="testing || !form.webhook_url"
            @click="testWebhook"
          >
            {{ testing ? '测试中…' : '测试连接' }}
          </button>
        </div>
        <p v-if="testResult === true" class="bae-hint bae-hint--ok">
          <svg class="icon" viewBox="0 0 24 24" style="width:16px;height:16px;fill:#003b1f"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
          连接成功
        </p>
        <p v-else-if="testResult === false" class="bae-hint bae-hint--err">
          <svg class="icon" viewBox="0 0 24 24" style="width:16px;height:16px;fill:#93000a"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
          连接失败，请检查 Webhook 地址
        </p>
      </section>

      <!-- Trigger Conditions -->
      <section class="bae-card bae-card--white">
        <h3 class="bae-section-title">
          <svg class="icon" viewBox="0 0 24 24"><path d="M3 17v2h6v-2H3zM3 5v2h10V5H3zm10 16v-2h8v-2h-8v-2h-2v6h2zM7 9v2H3v2h4v2h2V9H7zm14 4v-2H11v2h10zm-6-4h2V7h4V5h-4V3h-2v6z" fill="currentColor"/></svg>
          触发条件设置
        </h3>
        <div class="bae-condition-grid">
          <div class="bae-cell">
            <label class="bae-cell-label">指标</label>
            <div class="bae-select-wrap">
              <select v-model="form.metric" class="bae-select">
                <option value="bb_width_pct">布林带收缩值</option>
                <option value="pct_change">涨跌幅</option>
                <option value="volume_ratio">量比</option>
                <option value="total_score">综合评分</option>
                <option value="squeeze_days">收缩天数</option>
              </select>
              <svg class="icon bae-select-arrow" viewBox="0 0 24 24"><path d="M7 10l5 5 5-5z" fill="currentColor"/></svg>
            </div>
          </div>
          <div class="bae-cell">
            <label class="bae-cell-label">触发条件</label>
            <div class="bae-select-wrap">
              <select v-model="form.cond_op" class="bae-select">
                <option value="gt">大于</option>
                <option value="lt">小于</option>
                <option value="cross_above">上穿</option>
                <option value="cross_below">下破</option>
              </select>
              <svg class="icon bae-select-arrow" viewBox="0 0 24 24"><path d="M7 10l5 5 5-5z" fill="currentColor"/></svg>
            </div>
          </div>
          <div class="bae-cell">
            <label class="bae-cell-label">阈值</label>
            <input
              v-model="form.threshold"
              type="text"
              class="bae-input"
              placeholder="14.5"
              maxlength="64"
            >
          </div>
        </div>
      </section>

      <!-- Alert Frequency -->
      <section class="bae-card bae-card--white">
        <h3 class="bae-section-title">
          <svg class="icon" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="currentColor"/></svg>
          告警频率
        </h3>
        <div class="bae-freq-grid">
          <button
            v-for="opt in FREQ_OPTS"
            :key="opt.value"
            type="button"
            class="bae-freq-btn"
            :class="{ 'bae-freq-btn--active': form.frequency === opt.value }"
            @click="form.frequency = opt.value"
          >
            <svg v-if="form.frequency === opt.value" class="icon bae-freq-check" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="currentColor"/></svg>
            {{ opt.label }}
          </button>
        </div>
      </section>

      <!-- Message Preview Card -->
      <section class="bae-preview-section">
        <p class="bae-preview-label">告警消息预览</p>
        <div class="bae-preview-card">
          <div class="bae-preview-icon">
            <svg class="icon" viewBox="0 0 24 24" style="fill:#fff"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/></svg>
          </div>
          <div class="bae-preview-body">
            <div class="bae-preview-head">
              <span class="bae-preview-title">布林带告警</span>
              <span class="bae-preview-time">刚刚</span>
            </div>
            <p class="bae-preview-text">
              {{ previewText }}
            </p>
          </div>
        </div>
      </section>

      <!-- Footer Actions -->
      <div class="bae-footer">
        <button
          type="button"
          class="bae-save-btn"
          :disabled="saving || !form.rule_name"
          @click="onSave"
        >
          {{ saving ? '保存中…' : isEdit ? '保存变更' : '保存并启用' }}
        </button>
        <button v-if="isEdit" type="button" class="bae-toggle-btn" @click="toggleEnabled">
          {{ form.enabled ? '停用规则' : '启用规则' }}
        </button>
      </div>

    </main>

    <!-- Toast -->
    <div v-if="toastVisible" class="bae-toast" :class="'bae-toast--' + toastType">{{ toastMsg }}</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { alertRule, scan } from '@/api/strategy.js'

const router = useRouter()
const route = useRoute()

const isEdit = computed(() => route.params.id && route.params.id !== 'new')

const form = ref({
  rule_name: '布林带收缩突破',
  webhook_url: '',
  metric: 'bb_width_pct',
  cond_op: 'gt',
  threshold: '',
  frequency: 'once',
  enabled: true,
  scan_id: null,
})

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const testResult = ref(null)   // null | true | false
const showMore = ref(false)
const scanList = ref([])

const toastMsg = ref('')
const toastType = ref('')
const toastVisible = ref(false)
let toastTimer = null

const FREQ_OPTS = [
  { value: 'once', label: '仅一次' },
  { value: 'daily', label: '每天一次' },
  { value: 'weekly', label: '每周一次' },
]

const METRIC_LABEL = {
  bb_width_pct: '布林带收缩值',
  pct_change: '涨跌幅',
  volume_ratio: '量比',
  total_score: '综合评分',
  squeeze_days: '收缩天数',
}

const COND_LABEL = {
  gt: '大于',
  lt: '小于',
  cross_above: '上穿',
  cross_below: '下破',
}

const previewText = computed(() => {
  const metric = METRIC_LABEL[form.value.metric] || form.value.metric
  const cond = COND_LABEL[form.value.cond_op] || form.value.cond_op
  const threshold = form.value.threshold || '?'
  return `符合条件股票 触发 ${metric} ${cond} ${threshold}`
})

function showToast(msg, type = '') {
  toastMsg.value = msg
  toastType.value = type
  toastVisible.value = true
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastVisible.value = false }, 2500)
}

function goBack() {
  router.push('/strategy/bollinger/alerts')
}

async function testWebhook() {
  if (!form.value.webhook_url) return
  testing.value = true
  testResult.value = null
  try {
    const res = await fetch('/api/feishu/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ webhook_url: form.value.webhook_url }),
    })
    const json = await res.json()
    testResult.value = json.success === true
    if (!json.success) showToast(json.error || '连接失败', 'err')
  } catch {
    testResult.value = false
    showToast('网络错误', 'err')
  } finally {
    testing.value = false
  }
}

async function onSave() {
  if (!form.value.rule_name) {
    showToast('请输入规则名称', 'err')
    return
  }
  saving.value = true
  try {
    const payload = { ...form.value }
    if (isEdit.value) {
      await alertRule.update(parseInt(route.params.id), payload)
      showToast('保存成功', 'ok')
    } else {
      const res = await alertRule.create(payload)
      showToast('创建成功', 'ok')
      setTimeout(() => router.push(`/strategy/bollinger/alert/${res.id}`), 800)
    }
    setTimeout(() => router.push('/strategy/bollinger/alerts'), 1200)
  } catch (e) {
    showToast(e.message || '保存失败', 'err')
  } finally {
    saving.value = false
  }
}

async function toggleEnabled() {
  form.value.enabled = !form.value.enabled
  await onSave()
}

async function onDelete() {
  if (!confirm('确定删除该告警规则？')) return
  try {
    await alertRule.delete(parseInt(route.params.id))
    showToast('删除成功', 'ok')
    setTimeout(() => router.push('/strategy/bollinger/alerts'), 600)
  } catch (e) {
    showToast(e.message || '删除失败', 'err')
  }
}

async function loadRule() {
  if (!isEdit.value) return
  loading.value = true
  try {
    const data = await alertRule.get(parseInt(route.params.id))
    if (data) {
      form.value.rule_name = data.rule_name || '布林带收缩突破'
      form.value.webhook_url = data.webhook_url || ''
      form.value.metric = data.metric || 'bb_width_pct'
      form.value.cond_op = data.cond_op || 'gt'
      form.value.threshold = data.threshold || ''
      form.value.frequency = data.frequency || 'once'
      form.value.enabled = Boolean(data.enabled)
      form.value.scan_id = data.scan_id || null
    }
  } catch (e) {
    showToast('加载失败', 'err')
  } finally {
    loading.value = false
  }
}

onMounted(loadRule)
</script>

<style scoped>
.bae-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: #f9f9fe;
  color: #1a1c1f;
  font-family: 'Inter', 'Manrope', 'PingFang SC', system-ui, sans-serif;
  padding-bottom: 32px;
}

/* ── TopAppBar ── */
.bae-topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 56px;
  padding: 8px 12px;
  padding-top: calc(8px + env(safe-area-inset-top, 0px));
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 1px 0 rgba(26, 28, 31, 0.06);
}
.bae-icon-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #1a1c1f;
  transition: background 0.15s, transform 0.12s;
  flex-shrink: 0;
}
.bae-icon-btn:active { transform: scale(0.96); }
.bae-icon-btn .icon { width: 24px; height: 24px; fill: currentColor; }
.bae-nav-title {
  margin: 0;
  text-align: center;
  font-family: 'Manrope', 'PingFang SC', sans-serif;
  font-weight: 800;
  font-size: 17px;
  letter-spacing: -0.02em;
  color: #1a1c1f;
  flex: 1;
}
.bae-topbar__right {
  display: flex;
  align-items: center;
  gap: 6px;
}
.bae-status-badge {
  font-size: 12px;
  font-weight: 700;
  color: #003ec7;
  background: #dde1ff;
  padding: 3px 10px;
  border-radius: 9999px;
}

/* ── More menu ── */
.bae-more-menu {
  position: fixed;
  top: 64px;
  right: 16px;
  z-index: 60;
  background: #ffffff;
  border-radius: 1.5rem;
  box-shadow: 0 8px 24px rgba(26, 28, 31, 0.14);
  padding: 8px;
  min-width: 160px;
}
.bae-more-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 1rem;
  border: none;
  background: none;
  font-size: 14px;
  font-weight: 600;
  color: #1a1c1f;
  cursor: pointer;
  transition: background 0.12s;
  text-align: left;
}
.bae-more-item:active { background: #f3f3f8; }
.bae-more-item--danger { color: #ba1a1a; }
.bae-more-item--danger:active { background: #ffdad6; }
.bae-more-item .icon { width: 20px; height: 20px; fill: currentColor; }

/* ── Main ── */
.bae-main {
  max-width: 1024px;
  margin: 0 auto;
  padding: 20px 16px 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ── Cards ── */
.bae-card {
  border-radius: 2rem;
  padding: 20px 24px;
}
.bae-card--white {
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(26, 28, 31, 0.06);
}
.bae-card--blue-tint {
  background: rgba(0, 82, 255, 0.06);
  border: 1px solid rgba(0, 82, 255, 0.1);
  display: flex;
  align-items: center;
}
.bae-flex-center { display: flex; align-items: center; gap: 14px; }
.bae-lark-icon {
  width: 44px;
  height: 44px;
  border-radius: 1rem;
  background: #003ec7;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.bae-card__eyebrow {
  font-size: 11px;
  font-weight: 700;
  color: #737688;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 6px;
}
.bae-card__eyebrow--blue { color: #003ec7; margin-bottom: 0; }
.bae-card__sub {
  font-size: 12px;
  color: #434656;
  margin-top: 2px;
}

/* ── Bento Grid ── */
.bae-bento-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}
@media (min-width: 600px) {
  .bae-bento-grid { grid-template-columns: 1fr 1fr; }
}

/* ── Name Input ── */
.bae-name-input {
  width: 100%;
  border: none;
  outline: none;
  font-family: 'Manrope', 'PingFang SC', sans-serif;
  font-size: 1.25rem;
  font-weight: 800;
  color: #1a1c1f;
  background: transparent;
  letter-spacing: -0.02em;
  padding: 0;
  margin-bottom: 12px;
  box-sizing: border-box;
}
.bae-name-input::placeholder { color: #c3c5d9; font-weight: 600; }
.bae-live-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #434656;
}
.bae-live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22c55e;
  animation: bae-pulse 2s ease-in-out infinite;
}
@keyframes bae-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(0.85); }
}

/* ── Webhook ── */
.bae-label {
  display: block;
  font-size: 14px;
  font-weight: 700;
  color: #1a1c1f;
  margin-bottom: 10px;
}
.bae-webhook-row {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.bae-input {
  padding: 14px 20px;
  border: none;
  border-radius: 9999px;
  font-size: 14px;
  background: #f3f3f8;
  color: #1a1c1f;
  transition: background 0.15s, box-shadow 0.15s;
  outline: none;
  width: 100%;
  box-sizing: border-box;
}
.bae-input:focus {
  background: #ffffff;
  box-shadow: 0 0 0 2px #003ec7;
}
.bae-input::placeholder { color: #c3c5d9; }
.bae-input--full { flex: 1; min-width: 0; }
.bae-btn {
  padding: 14px 24px;
  border-radius: 9999px;
  font-size: 14px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: background 0.15s, transform 0.12s;
  white-space: nowrap;
}
.bae-btn:active { transform: scale(0.96); }
.bae-btn--outline {
  background: #f3f3f8;
  color: #1a1c1f;
}
.bae-btn--outline:hover { background: #ededf2; }
.bae-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.bae-btn:disabled:active { transform: none; }
.bae-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  margin-top: 10px;
}
.bae-hint--ok { color: #003b1f; }
.bae-hint--err { color: #93000a; }

/* ── Section Title ── */
.bae-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 700;
  color: #434656;
  margin-bottom: 16px;
}
.bae-section-title .icon {
  width: 20px;
  height: 20px;
  fill: #737688;
}

/* ── Condition Grid ── */
.bae-condition-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
@media (max-width: 480px) {
  .bae-condition-grid { grid-template-columns: 1fr; gap: 16px; }
}
.bae-cell { display: flex; flex-direction: column; gap: 8px; }
.bae-cell-label {
  font-size: 11px;
  font-weight: 700;
  color: #737688;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding-left: 4px;
}
.bae-select-wrap {
  position: relative;
  display: flex;
  align-items: center;
}
.bae-select {
  width: 100%;
  appearance: none;
  padding: 14px 40px 14px 18px;
  border: none;
  border-radius: 9999px;
  font-size: 14px;
  background: #f3f3f8;
  color: #1a1c1f;
  outline: none;
  cursor: pointer;
  transition: background 0.15s, box-shadow 0.15s;
  box-sizing: border-box;
}
.bae-select:focus {
  background: #ffffff;
  box-shadow: 0 0 0 2px #003ec7;
}
.bae-select-arrow {
  position: absolute;
  right: 14px;
  width: 20px;
  height: 20px;
  fill: #737688;
  pointer-events: none;
}
.bae-input { flex: 1; }

/* ── Frequency ── */
.bae-freq-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
@media (max-width: 480px) {
  .bae-freq-grid { grid-template-columns: 1fr; }
}
.bae-freq-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 14px 12px;
  border-radius: 9999px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, transform 0.12s, box-shadow 0.15s;
  background: #f3f3f8;
  color: #434656;
}
.bae-freq-btn:active { transform: scale(0.96); }
.bae-freq-btn--active {
  background: #003ec7;
  color: #ffffff;
  box-shadow: 0 6px 20px rgba(0, 62, 199, 0.35);
}
.bae-freq-check { width: 18px; height: 18px; fill: #ffffff; }

/* ── Preview ── */
.bae-preview-section { padding: 0 4px; }
.bae-preview-label {
  font-size: 11px;
  font-weight: 700;
  color: #737688;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 10px;
}
.bae-preview-card {
  display: flex;
  gap: 14px;
  background: #ffffff;
  border-radius: 2rem;
  padding: 18px 20px;
  box-shadow: 0 8px 24px rgba(26, 28, 31, 0.1);
  max-width: 420px;
}
.bae-preview-icon {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #003ec7;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.bae-preview-icon .icon { width: 24px; height: 24px; }
.bae-preview-body { flex: 1; min-width: 0; }
.bae-preview-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.bae-preview-title {
  font-size: 14px;
  font-weight: 700;
  color: #1a1c1f;
  font-family: 'Manrope', 'PingFang SC', sans-serif;
}
.bae-preview-time {
  font-size: 11px;
  color: #737688;
}
.bae-preview-text {
  font-size: 13px;
  color: #434656;
  line-height: 1.5;
}

/* ── Footer ── */
.bae-footer {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 4px;
}
.bae-save-btn {
  width: 100%;
  padding: 18px;
  border-radius: 9999px;
  border: none;
  background: #003ec7;
  color: #ffffff;
  font-family: 'Manrope', 'PingFang SC', sans-serif;
  font-size: 16px;
  font-weight: 800;
  cursor: pointer;
  transition: background 0.15s, transform 0.12s, box-shadow 0.15s;
  box-shadow: 0 8px 24px rgba(0, 62, 199, 0.3);
  letter-spacing: -0.01em;
}
.bae-save-btn:active:not(:disabled) { transform: scale(0.98); }
.bae-save-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.bae-toggle-btn {
  width: 100%;
  padding: 14px;
  border-radius: 9999px;
  border: none;
  background: #f3f3f8;
  color: #434656;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, transform 0.12s;
}
.bae-toggle-btn:active { transform: scale(0.98); }

/* ── Toast ── */
.bae-toast {
  position: fixed;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  padding: 12px 28px;
  border-radius: 9999px;
  font-size: 14px;
  font-weight: 600;
  background: #1a1c1f;
  color: #fff;
  box-shadow: 0 8px 24px rgba(26, 28, 31, 0.25);
  z-index: 100;
  white-space: nowrap;
}
.bae-toast--ok { background: #003b1f; }
.bae-toast--err { background: #ba1a1a; }
</style>
