<template>
  <div class="fp-page">
    <header class="fp-header">
      <button type="button" class="fp-icon-btn" aria-label="返回" @click="$router.push('/strategy')">
        <svg class="fp-svg" viewBox="0 0 24 24" aria-hidden="true"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <h1 class="fp-title">自定义因子 Prompt 工程</h1>
      <div class="fp-header-actions">
        <svg class="fp-psychology" viewBox="0 0 24 24" fill="#0058bc"><path d="M21 10.12h-6.78l2.74-2.82c-2.73-2.7-7.15-2.8-9.88-.1-2.73 2.71-2.73 7.08 0 9.79 2.73 2.71 7.15 2.71 9.88 0C18.32 15.65 19 14.08 19 12.1h2c0 1.98-.88 4.55-2.64 6.29-3.51 3.48-9.21 3.48-12.72 0-3.5-3.47-3.53-9.11-.02-12.58 3.51-3.47 9.14-3.47 12.65 0L21 3v7.12zM12.5 8v4.25l3.5 2.08-.72 1.21L11 13V8h1.5z"/></svg>
        <div class="fp-avatar" aria-hidden="true">α</div>
      </div>
    </header>

    <main class="fp-main">
      <section class="fp-grid-top">
        <div class="fp-card fp-intro">
          <div class="fp-intro-head">
            <div class="fp-spark-wrap">
              <svg class="fp-spark" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.2 4.2L17 7l-3.8 2.1L15 13l-3-2.5L9 13l1.8-3.9L7 7l3.8-.8L12 2zm-6 10l.9 2.5L9 15l-2.2 1.2L8 19l-2-1.7-2 1.7.2-2.8-2.2-1.2 2.5-.5L4 12zm14 2l1.5.3 1.3 1.3-1.8.4-.4 1.8-1.3-1.3-1.8.4.4-1.8-1.8-.4 1.3-1.3 1.5.3.9-1.4z"/></svg>
            </div>
            <h2 class="fp-h2">DeepSeek 集成框架</h2>
          </div>
          <p class="fp-body">
            利用 DeepSeek 的高级推理能力提升您的超额收益研究。该框架提供了必要的结构，以传达复杂的量化要求，确保生成的 Python 逻辑无缝集成到因子引擎生态系统中。
          </p>
        </div>
        <div class="fp-card fp-stepper-card">
          <h3 class="fp-label-up">工作流状态</h3>
          <div class="fp-steps">
            <div class="fp-step-row">
              <div class="fp-step-num" :class="{ active: workflowStep >= 1, done: workflowStep > 1 }">1</div>
              <span class="fp-step-txt" :class="{ strong: workflowStep >= 1 }">生成框架</span>
            </div>
            <div class="fp-step-line" />
            <div class="fp-step-row">
              <div class="fp-step-num" :class="{ active: workflowStep >= 2, pulse: workflowStep === 2 }">2</div>
              <span class="fp-step-txt" :class="{ strong: workflowStep >= 2 }">咨询 DeepSeek</span>
            </div>
            <div class="fp-step-line" />
            <div class="fp-step-row">
              <div class="fp-step-num" :class="{ active: workflowStep >= 3 }">3</div>
              <span class="fp-step-txt" :class="{ strong: workflowStep >= 3 }">注入代码</span>
            </div>
          </div>
        </div>
      </section>

      <section class="fp-section">
        <div class="fp-section-head">
          <h2 class="fp-h2-inline">
            <svg class="fp-inline-ic" viewBox="0 0 24 24"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>
            因子指令输入
          </h2>
          <div class="fp-badge-live">
            <span class="fp-dot" />
            <span>意图识别：开启</span>
          </div>
        </div>
        <div class="fp-panel">
          <div class="fp-input-row">
            <div class="fp-input-wrap">
              <input
                v-model="instruction"
                class="fp-input"
                type="text"
                autocomplete="off"
                placeholder="例如：帮我编写一个5日成交量加权 RSI 因子"
                :disabled="loading"
                @keydown.enter.prevent="onGenerate"
              >
              <span class="fp-mic" aria-hidden="true">
                <svg class="fp-svg-muted" viewBox="0 0 24 24"><path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.91-3c-.49 0-.9.36-.98.85C16.52 14.2 14.47 16 12 16s-4.52-1.8-4.93-4.15c-.08-.49-.49-.85-.98-.85-.61 0-1.09.54-1 1.14.49 3 2.89 5.35 5.91 5.78V20c0 .55.45 1 1 1s1-.45 1-1v-2.08c3.02-.43 5.42-2.78 5.91-5.78.1-.6-.39-1.14-1-1.14z"/></svg>
              </span>
            </div>
            <button type="button" class="fp-btn-primary" :disabled="loading" @click="onGenerate">
              <svg class="fp-bolt" viewBox="0 0 24 24"><path d="M11 21h-1l1-7H7.5c-.58 0-.57-.32-.38-.66.19-.34.05-.08.07-.12C8.48 10.94 10.42 7.54 13 3h1l-1 7h3.5c.49 0 .56.33.47.51l-.07.15C18.44 15.34 16 19 12 21z"/></svg>
              {{ loading ? '生成中…' : '生成因子' }}
            </button>
          </div>
          <p v-if="errorMsg" class="fp-error">{{ errorMsg }}</p>
          <div class="fp-footnote">
            <svg class="fp-info-ic" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>
            <span>系统仅读取专业因子相关指令，非量化研究请求将被自动过滤。</span>
          </div>
        </div>
      </section>

      <section class="fp-section">
        <div class="fp-section-head">
          <h2 class="fp-h2-inline">
            <svg class="fp-inline-ic" viewBox="0 0 24 24"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 14H4V6h16v12zM6 10h12v2H6v-2zm0 4h8v2H6v-2z"/></svg>
            Python 框架
          </h2>
          <span class="fp-ver">v{{ templateVersion }}</span>
        </div>
        <div class="fp-editor">
          <div class="fp-editor-bar">
            <div class="fp-dots">
              <span class="fp-dot-r" /><span class="fp-dot-y" /><span class="fp-dot-g" />
            </div>
            <span class="fp-filename">factor_template.py</span>
            <button type="button" class="fp-copy" aria-label="复制代码" @click="copyCode">
              <svg class="fp-svg-slate" viewBox="0 0 24 24"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>
            </button>
          </div>
          <pre class="fp-pre"><code class="fp-code" v-html="displayedCode"></code></pre>
        </div>
      </section>

      <section class="fp-section fp-last">
        <h2 class="fp-h2-block">
          <svg class="fp-inline-ic" viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/></svg>
          意图识别与状态
        </h2>
        <div class="fp-status-card">
          <div class="fp-status-col">
            <p class="fp-st-label">识别意图</p>
            <div class="fp-st-row">
              <svg class="fp-st-ic" viewBox="0 0 24 24"><path d="M13 3.87L11.1 2.1 5 8.2V20h14V8.2l-6-6zm0 2.43l4.59 4.59H8.41L13 6.3zM7 18v-8h10v8H7z"/></svg>
              <span class="fp-st-val">{{ intentLabel }}</span>
            </div>
          </div>
          <div class="fp-status-col">
            <p class="fp-st-label">连接状态</p>
            <div class="fp-st-row">
              <span class="fp-st-dot" :class="{ ok: apiConnected }" />
              <span class="fp-st-val">{{ apiConnected ? 'DeepSeek API 已连接' : '未配置 API Key' }}</span>
            </div>
          </div>
          <div class="fp-status-col">
            <p class="fp-st-label">当前模型</p>
            <div class="fp-st-row">
              <svg class="fp-st-ic" viewBox="0 0 24 24"><path d="M4 6h16v2H4V6zm0 5h16v2H4v-2zm0 5h10v2H4v-2z"/></svg>
              <span class="fp-st-val">{{ modelDisplay }}</span>
            </div>
          </div>
        </div>
      </section>
    </main>

    <nav class="fp-bottom-nav" aria-label="因子工程导航">
      <router-link to="/strategy" class="fp-nav-item" active-class="">
        <svg class="fp-nav-svg" viewBox="0 0 24 24"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 14H4V6h16v12z"/></svg>
        <span>工作台</span>
      </router-link>
      <div class="fp-nav-item fp-nav-active">
        <svg class="fp-nav-svg" viewBox="0 0 24 24"><path d="M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-1 9H9V9h10v2zm-4 4H9v-2h6v2zm4-8H9V5h10v2z"/></svg>
        <span>提示词</span>
      </div>
      <router-link to="/strategy/backtest" class="fp-nav-item">
        <svg class="fp-nav-svg" viewBox="0 0 24 24"><path d="M3.5 18.49l6-6.01 4 4L22 6.92l-1.41-1.41-7.09 7.97-4-4L2 16.99z"/></svg>
        <span>回测</span>
      </router-link>
      <router-link to="/strategy" class="fp-nav-item">
        <svg class="fp-nav-svg" viewBox="0 0 24 24"><path d="M20 2H4c-1 0-2 .9-2 2v16c0 1.1.9 2 2 2h16c1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 18H4V4h16v16z"/></svg>
        <span>库</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import * as factorApi from '@/api/factor.js'

const instruction = ref('')
// ── Syntax highlighter (no external deps) ──────────────────────────────
function highlightPython(code) {
  const esc = (s) => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
  const lines = code.split('\n')
  return lines.map((line) => {
    let s = esc(line)
    // comments
    s = s.replace(/(#.*)$/, '<span class="sh-comment">$1</span>')
    // strings (single/double/triple, inline only)
    s = s.replace(/('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")/g, '<span class="sh-string">$1</span>')
    // keywords
    s = s.replace(/\b(class|def|return|if|else|elif|for|while|in|not|and|or|import|from|as|try|except|raise|with|pass|break|continue|True|False|None|self)\b/g, '<span class="sh-keyword">$1</span>')
    // builtins / base classes
    s = s.replace(/\b(BaseAlphaFactor|print|len|range|float|int|str|list|dict|tuple|set|np|pd|numpy|pandas)\b/g, '<span class="sh-builtin">$1</span>')
    return s
  }).join('\n')
}
// ──────────────────────────────────────────────────────────────────────

const displayedCode = ref('')
const templateVersion = ref('2.4.1')
const loading = ref(false)
const errorMsg = ref('')
const workflowStep = ref(1)
const apiConnected = ref(false)
const modelDisplay = ref('—')
const lastSuccess = ref(false)

const intentLabel = computed(() => {
  if (!apiConnected.value) return '服务未就绪'
  if (loading.value) return '意图分析中…'
  if (lastSuccess.value) return '因子开发 (Factor Development)'
  return '因子开发 (待机)'
})

async function loadInitial() {
  try {
    const [tpl, st] = await Promise.all([
      factorApi.getFactorTemplate(),
      factorApi.getFactorStatus(),
    ])
    displayedCode.value = tpl.code || ''
    displayedCode.value = highlightPython(displayedCode.value)
    templateVersion.value = tpl.version || templateVersion.value
    apiConnected.value = Boolean(st.connected)
    modelDisplay.value = st.connected ? (st.model_display || st.model_id || 'deepseek-chat') : '—'
  } catch (e) {
    errorMsg.value = e.message || '加载失败'
  }
}

async function onGenerate() {
  errorMsg.value = ''
  const text = instruction.value.trim()
  if (text.length < 4) {
    errorMsg.value = '请输入更具体的因子描述'
    return
  }
  loading.value = true
  workflowStep.value = 2
  lastSuccess.value = false
  try {
    const data = await factorApi.generateFactor(text)
    displayedCode.value = data.code
    displayedCode.value = highlightPython(displayedCode.value)
    templateVersion.value = data.template_version || templateVersion.value
    workflowStep.value = 3
    lastSuccess.value = true
  } catch (e) {
    workflowStep.value = 1
    errorMsg.value = e.message || '生成失败'
    if (e.filtered) {
      /* 保持简短提示 */
    }
  } finally {
    loading.value = false
  }
}

async function copyCode() {
  const t = displayedCode.value
  if (!t) return
  try {
    await navigator.clipboard.writeText(t)
  } catch {
    /* fallback */
    const ta = document.createElement('textarea')
    ta.value = t
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
}

onMounted(() => {
  loadInitial()
})
</script>

<style scoped>
.fp-page {
  --fp-primary: #0058bc;
  --fp-primary-hi: #0070eb;
  --fp-bg: #f7f9fc;
  --fp-surface: #ffffff;
  --fp-surface-low: #f2f4f7;
  --fp-surface-hi: #e0e3e6;
  --fp-text: #191c1e;
  --fp-muted: #414755;
  --fp-outline: #717786;
  --fp-ghost: rgba(193, 198, 215, 0.3);
  --fp-shadow: 0 8px 24px rgba(25, 28, 30, 0.06);
  min-height: 100dvh;
  background: var(--fp-bg);
  color: var(--fp-text);
  font-family: 'Inter', var(--font, system-ui, sans-serif);
  padding-bottom: calc(88px + env(safe-area-inset-bottom, 0));
}

.fp-header {
  position: sticky;
  top: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: calc(12px + env(safe-area-inset-top, 0)) 16px 12px;
  background: var(--fp-bg);
  box-shadow: var(--fp-shadow);
}

.fp-title {
  flex: 1;
  margin: 0;
  font-family: 'Manrope', var(--font, system-ui, sans-serif);
  font-size: 1.05rem;
  font-weight: 800;
  color: var(--fp-primary);
  text-align: center;
  letter-spacing: -0.02em;
}

.fp-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fp-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.fp-icon-btn:active {
  transform: scale(0.96);
}
.fp-gear {
  display: none;
}

.fp-psychology {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
}

.fp-svg {
  width: 22px;
  height: 22px;
  fill: currentColor;
}

.fp-avatar {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  background: linear-gradient(135deg, #86b8ff, #2560a0);
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
}

.fp-main {
  max-width: 560px;
  margin: 0 auto;
  padding: 20px 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.fp-grid-top {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
@media (min-width: 900px) {
  .fp-grid-top {
    flex-direction: row;
    align-items: stretch;
  }
  .fp-intro {
    flex: 2;
  }
  .fp-stepper-card {
    flex: 1;
    min-width: 220px;
  }
}

.fp-card {
  background: var(--fp-surface);
  border-radius: 12px;
  box-shadow: var(--fp-shadow);
  padding: 24px;
}

.fp-stepper-card {
  background: var(--fp-surface-low);
}

.fp-intro-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.fp-spark-wrap {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: #d8e2ff;
  color: var(--fp-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.fp-spark {
  width: 22px;
  height: 22px;
}

.fp-h2 {
  margin: 0;
  font-family: 'Manrope', var(--font, system-ui, sans-serif);
  font-size: 1.125rem;
  font-weight: 700;
}

.fp-body {
  margin: 0;
  font-size: 14px;
  line-height: 1.65;
  color: var(--fp-muted);
}

.fp-label-up {
  margin: 0 0 16px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--fp-outline);
}

.fp-steps {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.fp-step-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.fp-step-num {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 800;
  background: var(--fp-surface-hi);
  color: var(--fp-muted);
  transition: background 0.2s, color 0.2s, box-shadow 0.2s;
}
.fp-step-num.active {
  background: var(--fp-primary);
  color: #fff;
  box-shadow: 0 4px 14px rgba(0, 88, 188, 0.25);
}
.fp-step-num.pulse {
  animation: fp-pulse 1.2s ease-in-out infinite;
}
.fp-step-num.done:not(.active) {
  background: var(--fp-primary-hi);
  color: #fff;
}

@keyframes fp-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.85; transform: scale(0.98); }
}

.fp-step-txt {
  font-size: 14px;
  font-weight: 500;
  color: var(--fp-muted);
}
.fp-step-txt.strong {
  color: var(--fp-primary);
  font-weight: 600;
}

.fp-step-line {
  width: 1px;
  height: 22px;
  margin-left: 15px;
  background: #c1c6d7;
}

.fp-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.fp-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.fp-h2-inline {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'Manrope', var(--font, system-ui, sans-serif);
  font-size: 1.125rem;
  font-weight: 700;
}

.fp-h2-block {
  margin: 0 0 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'Manrope', var(--font, system-ui, sans-serif);
  font-size: 1.125rem;
  font-weight: 700;
}

.fp-inline-ic {
  width: 22px;
  height: 22px;
  fill: var(--fp-primary);
  flex-shrink: 0;
}

.fp-badge-live {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #ecfdf5;
  color: #047857;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.02em;
  border: 1px solid #d1fae5;
}

.fp-dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: #10b981;
  animation: fp-blink 1.5s ease-in-out infinite;
}

@keyframes fp-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

.fp-panel {
  background: var(--fp-surface);
  border-radius: 12px;
  padding: 18px;
  box-shadow: var(--fp-shadow);
  border: 1px solid var(--fp-ghost);
}

.fp-input-row {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
@media (min-width: 640px) {
  .fp-input-row {
    flex-direction: row;
    align-items: stretch;
  }
}

.fp-input-wrap {
  position: relative;
  flex: 1;
}

.fp-input {
  width: 100%;
  height: 52px;
  padding: 0 44px 0 14px;
  border: none;
  border-radius: 12px;
  background: var(--fp-surface-low);
  font-size: 14px;
  color: var(--fp-text);
  outline: none;
  box-shadow: inset 0 0 0 1px transparent;
  transition: box-shadow 0.15s;
}
.fp-input:focus {
  box-shadow: inset 0 0 0 2px rgba(0, 88, 188, 0.2);
}
.fp-input:disabled {
  opacity: 0.7;
}
.fp-input::placeholder {
  color: rgba(113, 119, 134, 0.65);
}

.fp-mic {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  opacity: 0.4;
}

.fp-svg-muted {
  width: 22px;
  height: 22px;
  fill: var(--fp-outline);
}

.fp-btn-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 52px;
  padding: 0 22px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(180deg, var(--fp-primary) 0%, var(--fp-primary-hi) 100%);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 6px 20px rgba(0, 88, 188, 0.28);
  white-space: nowrap;
  -webkit-tap-highlight-color: transparent;
}
.fp-btn-primary:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
.fp-btn-primary:active:not(:disabled) {
  transform: scale(0.98);
}

.fp-bolt {
  width: 20px;
  height: 20px;
  fill: currentColor;
}

.fp-error {
  margin: 10px 0 0;
  font-size: 13px;
  color: #ba1a1a;
}

.fp-footnote {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 14px;
  font-size: 12px;
  font-weight: 500;
  color: var(--fp-outline);
  line-height: 1.45;
}

.fp-info-ic {
  width: 16px;
  height: 16px;
  fill: var(--fp-outline);
  opacity: 0.75;
  flex-shrink: 0;
  margin-top: 2px;
}

.fp-ver {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--fp-surface-hi);
  color: var(--fp-muted);
}

.fp-editor {
  border-radius: 12px;
  overflow: hidden;
  background: #1e293b;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.2);
}

.fp-editor-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #334155;
}

.fp-dots {
  display: flex;
  align-items: center;
  gap: 6px;
}
.fp-dot-r,
.fp-dot-y,
.fp-dot-g {
  width: 10px;
  height: 10px;
  border-radius: 999px;
}
.fp-dot-r {
  background: #ff5f56;
}
.fp-dot-y {
  background: #ffbd2e;
}
.fp-dot-g {
  background: #27c93f;
}

.fp-filename {
  margin-left: 10px;
  flex: 1;
  font-family: ui-monospace, monospace;
  font-size: 11px;
  color: #94a3b8;
}

.fp-copy {
  background: none;
  border: none;
  padding: 6px;
  cursor: pointer;
  border-radius: 8px;
  color: #94a3b8;
}
.fp-copy:active {
  color: #fff;
}

.fp-svg-slate {
  width: 18px;
  height: 18px;
  fill: currentColor;
}

.fp-pre {
  margin: 0;
  padding: 18px 16px 22px;
  overflow-x: auto;
  max-height: min(52vh, 420px);
  overflow-y: auto;
}

.fp-code .sh-keyword  { color: #f472b6; }
.fp-code .sh-string   { color: #fbbf24; }
.fp-code .sh-comment  { color: #64748b; font-style: italic; }
.fp-code .sh-builtin  { color: #60a5fa; }
.fp-code .sh-def      { color: #34d399; }

.fp-status-card {
  background: var(--fp-surface);
  border-radius: 12px;
  padding: 20px;
  box-shadow: var(--fp-shadow);
  border: 1px solid var(--fp-ghost);
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
}
@media (min-width: 640px) {
  .fp-status-card {
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }
}

.fp-st-label {
  margin: 0 0 6px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--fp-outline);
}

.fp-st-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fp-st-ic {
  width: 20px;
  height: 20px;
  fill: var(--fp-primary);
  flex-shrink: 0;
}

.fp-st-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #cbd5e1;
  flex-shrink: 0;
}
.fp-st-dot.ok {
  background: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.25);
  animation: fp-blink 2s ease-in-out infinite;
}

.fp-st-val {
  font-size: 14px;
  font-weight: 700;
  color: var(--fp-text);
  line-height: 1.3;
}

.fp-last {
  margin-bottom: 8px;
}

.fp-bottom-nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 50;
  display: flex;
  justify-content: space-around;
  align-items: center;
  padding: 8px 8px calc(10px + env(safe-area-inset-bottom, 0));
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-radius: 16px 16px 0 0;
  box-shadow: 0 -4px 24px rgba(25, 28, 30, 0.06);
}

.fp-nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  border-radius: 12px;
  text-decoration: none;
  color: #64748b;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  -webkit-tap-highlight-color: transparent;
}
.fp-nav-item:active {
  transform: scale(0.96);
}

.fp-nav-active {
  background: #eff6ff;
  color: var(--fp-primary);
  font-weight: 800;
}

.fp-nav-svg {
  width: 22px;
  height: 22px;
  fill: currentColor;
}
</style>
