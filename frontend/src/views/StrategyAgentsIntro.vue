<template>
  <div class="intro-page">
    <!-- Header -->
    <header class="intro-top">
      <button type="button" class="intro-top__back" aria-label="返回" @click="$router.push(basePath)">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <div class="intro-top__brand">
        <div class="intro-top__avatar">策</div>
        <div>
          <p class="intro-top__eyebrow">SYSTEM OVERVIEW</p>
          <h1 class="intro-top__title">游资智能体架构台</h1>
        </div>
      </div>
    </header>

    <!-- Loading -->
    <div v-if="loading" class="intro-loading">
      <div class="intro-spinner" />
      <p>正在加载系统介绍…</p>
    </div>

    <!-- Error -->
    <div v-else-if="errorMsg" class="intro-error">
      <strong>加载失败：</strong>{{ errorMsg }}
    </div>

    <!-- Content -->
    <main v-else-if="architecture" class="intro-main">

      <!-- Hero Banner -->
      <section class="intro-hero">
        <div class="intro-hero__mesh" />
        <div class="intro-hero__content">
          <p class="intro-hero__kicker">SYSTEM OVERVIEW</p>
          <h2 class="intro-hero__title">游资智能体架构台</h2>
          <p class="intro-hero__subtitle">不是角色列表，而是一套完整的多智能体协同选股系统</p>
          <p class="intro-hero__desc">
            游资智能体架构台是一套将「游资炒家思维」工程化的多智能体系统。与传统 AI 选股工具不同，它不依赖单一 Prompt，而是将选股过程拆解为多个专业化模块，各司其职、层层递进，最终输出可解释、可追溯的选股决策。
          </p>
        </div>
        <div class="intro-hero__stats">
          <article v-for="stat in heroStats" :key="stat.label" class="intro-hero-stat">
            <p class="intro-hero-stat__value">{{ stat.value }}</p>
            <p class="intro-hero-stat__label">{{ stat.label }}</p>
            <p class="intro-hero-stat__hint">{{ stat.hint }}</p>
          </article>
        </div>
      </section>

      <!-- Four Layer Architecture -->
      <section class="intro-section">
        <div class="intro-section__head">
          <p class="intro-section__kicker">ARCHITECTURE STACK</p>
          <h2 class="intro-section__title">四层系统架构</h2>
          <p class="intro-section__subtitle">从数据事实到人格决策，逐层构建选股能力</p>
        </div>
        <div class="intro-layer-stack">
          <article
            v-for="layer in layers"
            :key="layer.id"
            class="intro-layer-card"
            :class="'intro-layer-card--' + layer.tone"
          >
            <div class="intro-layer-card__top">
              <div>
                <p class="intro-layer-card__eyebrow">{{ layer.title }}</p>
                <h3 class="intro-layer-card__desc">{{ layer.description }}</h3>
              </div>
              <span class="intro-layer-card__pill">
                {{ (layer.agents && layer.agents.length) || (layer.modules && layer.modules.length) || 0 }} 个模块
              </span>
            </div>
            <div class="intro-layer-card__groups">
              <div class="intro-layer-card__group">
                <p class="intro-layer-card__label">核心模块</p>
                <div class="intro-layer-card__chips">
                  <span v-for="module in layer.modules || []" :key="module" class="intro-chip">{{ module }}</span>
                </div>
              </div>
              <div v-if="layer.agents?.length" class="intro-layer-card__group">
                <p class="intro-layer-card__label">关联 Agent</p>
                <div class="intro-layer-card__chips">
                  <span v-for="agent in layer.agents" :key="agent.id" class="intro-chip intro-chip--agent">{{ agent.name }}</span>
                </div>
              </div>
              <div class="intro-layer-card__group">
                <p class="intro-layer-card__label">产出</p>
                <div class="intro-layer-card__chips">
                  <span v-for="output in layer.outputs || []" :key="output" class="intro-chip intro-chip--output">{{ output }}</span>
                </div>
              </div>
            </div>
          </article>
        </div>
      </section>

      <!-- Shared Context Protocol -->
      <section class="intro-section">
        <div class="intro-section__head">
          <p class="intro-section__kicker">SHARED CONTEXT CONTRACT</p>
          <h2 class="intro-section__title">共享事实协议</h2>
          <p class="intro-section__subtitle">所有 Agent 共享同一套市场事实，消除信息不对称</p>
        </div>
        <div class="intro-context-grid">
          <article class="intro-context-card">
            <p class="intro-context-card__eyebrow">{{ sharedContext.name }}</p>
            <h3 class="intro-context-card__title">{{ sharedContext.description }}</h3>
            <div class="intro-context-card__list">
              <div v-for="input in sharedContext.inputs" :key="input.id" class="intro-context-card__item">
                <p class="intro-context-card__item-title">{{ input.label }}</p>
                <p class="intro-context-card__item-desc">{{ input.description }}</p>
              </div>
            </div>
          </article>
          <article class="intro-context-card intro-context-card--dark">
            <p class="intro-context-card__eyebrow intro-context-card__eyebrow--purple">系统硬约束</p>
            <h3 class="intro-context-card__title">人格不是数据源</h3>
            <ul class="intro-context-rule-list">
              <li v-for="rule in sharedContext.rules" :key="rule">{{ rule }}</li>
            </ul>
            <div class="intro-context-card__foot">
              <span v-for="output in sharedContext.outputs" :key="output" class="intro-context-output">{{ output }}</span>
            </div>
          </article>
        </div>
      </section>

      <!-- Execution Flow -->
      <section class="intro-section">
        <div class="intro-section__head">
          <p class="intro-section__kicker">EXECUTION FLOW</p>
          <h2 class="intro-section__title">完整执行链路</h2>
          <p class="intro-section__subtitle">从数据采集到结果聚合的端到端流程</p>
        </div>
        <div class="intro-flow-grid">
          <article v-for="(step, index) in executionFlow" :key="step.id" class="intro-flow-card">
            <div class="intro-flow-card__index">{{ index + 1 }}</div>
            <div>
              <h3 class="intro-flow-card__title">{{ step.title }}</h3>
              <p class="intro-flow-card__detail">{{ step.detail }}</p>
            </div>
          </article>
        </div>
      </section>

      <!-- Runtime Modes -->
      <section class="intro-section">
        <div class="intro-section__head">
          <p class="intro-section__kicker">RUNTIME MODES</p>
          <h2 class="intro-section__title">三种运行模式</h2>
          <p class="intro-section__subtitle">灵活应对不同分析场景</p>
        </div>
        <div class="intro-mode-grid">
          <article v-for="mode in runtimeModes" :key="mode.id" class="intro-mode-card">
            <p class="intro-mode-card__id">{{ mode.id }}</p>
            <h3 class="intro-mode-card__title">{{ mode.title }}</h3>
            <p class="intro-mode-card__desc">{{ mode.description }}</p>
          </article>
        </div>
      </section>

      <!-- Learn More Card -->
      <section class="intro-section">
        <div class="intro-section__head">
          <p class="intro-section__kicker">DEEPER LOOK</p>
          <h2 class="intro-section__title">深入了解</h2>
        </div>
        <router-link to="/strategy/agents/intro/principles" class="intro-learn-card">
          <div class="intro-learn-card__left">
            <div class="intro-learn-card__icon">
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9v1zm3-19C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7z"/></svg>
            </div>
            <div>
              <h3 class="intro-learn-card__title">设计原则 v{{ architecture.version || '2.0' }}</h3>
              <p class="intro-learn-card__desc">了解游资智能体架构台背后的设计哲学与核心原则</p>
            </div>
          </div>
          <div class="intro-learn-card__action">
            <span>了解更多</span>
            <svg class="intro-learn-card__arrow" viewBox="0 0 24 24" fill="currentColor"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
          </div>
        </router-link>
      </section>

      <!-- Footer -->
      <div class="intro-footer">
        <p class="intro-footer__text">数据生成时间：{{ formatGeneratedAt(architecture.generatedAt) }}</p>
        <button type="button" class="intro-footer__back" @click="$router.push(basePath)">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
          返回游资智能体架构台
        </button>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { fetchAgentArchitecture } from '@/api/agents.js'

const route = useRoute()

const basePath = computed(() =>
  route.path.startsWith('/strategy/youzi_agents') ? '/strategy/youzi_agents' : '/strategy/agents'
)

const architecture = ref(null)
const loading = ref(false)
const errorMsg = ref('')

const sharedContext = computed(() => architecture.value?.sharedContext || { inputs: [], rules: [], outputs: [] })
const layers = computed(() => architecture.value?.layers || [])
const executionFlow = computed(() => architecture.value?.executionFlow || [])
const runtimeModes = computed(() => architecture.value?.runtimeModes || [])

const heroStats = computed(() => [
  { label: '人格 Agent', value: (architecture.value?.personaAgents || []).length || '—', hint: '策略打法层' },
  { label: '共享事实输入', value: sharedContext.value.inputs.length || '—', hint: '统一 MarketContextPacket' },
  { label: '系统层级', value: layers.value.length || '—', hint: '从事实到聚合' },
  { label: '运行模式', value: runtimeModes.value.length || '—', hint: '单体 / 批量 / 层次化' },
])

async function loadArchitecture() {
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await fetchAgentArchitecture()
    architecture.value = data
  } catch (error) {
    errorMsg.value = error?.message || '无法加载策略系统架构'
  } finally {
    loading.value = false
  }
}

function formatGeneratedAt(value) {
  if (!value) return '未知'
  try {
    return new Date(value).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return value
  }
}

onMounted(() => { loadArchitecture() })
</script>

<style scoped>
/* ── Page ───────────────────────────────────────────── */
.intro-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: #FAF7F2;
  color: #152033;
  padding-bottom: 48px;
}

/* ── Header ─────────────────────────────────────────── */
.intro-top {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  backdrop-filter: blur(18px);
  background: rgba(250, 247, 242, 0.84);
  border-bottom: 1px solid rgba(84, 68, 38, 0.08);
}

.intro-top__back {
  width: 40px;
  height: 40px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(84, 68, 38, 0.08);
  box-shadow: 0 8px 24px rgba(21, 32, 51, 0.06);
  cursor: pointer;
  transition: background 0.15s;
  flex-shrink: 0;
}

.intro-top__back:hover { background: rgba(255, 255, 255, 0.92); }

.intro-top__brand {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.intro-top__avatar {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #0C172C, #1a2d4f);
  color: #C8973A;
  font-size: 18px;
  font-weight: 800;
  box-shadow: 0 16px 36px rgba(12, 23, 44, 0.18);
  flex-shrink: 0;
}

.intro-top__eyebrow {
  font-size: 10px;
  letter-spacing: 0.18em;
  color: #888;
  text-transform: uppercase;
  margin: 0;
}

.intro-top__title {
  font-size: 20px;
  line-height: 1.1;
  font-weight: 800;
  letter-spacing: -0.03em;
  margin: 0;
  color: #0C172C;
}

/* ── Loading / Error ───────────────────────────────── */
.intro-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px;
  color: #68778c;
  font-size: 14px;
}

.intro-spinner {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid rgba(70, 72, 212, 0.14);
  border-top-color: #4648D4;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.intro-error {
  margin: 20px 18px;
  padding: 18px 20px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid rgba(21, 32, 51, 0.08);
  color: #b42318;
}

/* ── Main Content ──────────────────────────────────── */
.intro-main {
  width: min(1000px, calc(100% - 32px));
  margin: 0 auto;
  padding: 28px 0 0;
}

/* ── Hero ───────────────────────────────────────────── */
.intro-hero {
  position: relative;
  overflow: hidden;
  border-radius: 28px;
  padding: 32px;
  background:
    linear-gradient(135deg, rgba(22, 27, 60, 0.98) 0%, rgba(35, 42, 100, 0.96) 58%, rgba(70, 72, 212, 0.92) 100%);
  color: #f4efe2;
  box-shadow: 0 32px 72px rgba(22, 27, 60, 0.2);
}

.intro-hero__mesh {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 18% 18%, rgba(100, 99, 238, 0.25), transparent 24%),
    radial-gradient(circle at 82% 26%, rgba(124, 173, 255, 0.2), transparent 28%),
    linear-gradient(120deg, transparent 0%, rgba(255, 255, 255, 0.04) 45%, transparent 100%);
  pointer-events: none;
}

.intro-hero__content {
  position: relative;
  z-index: 1;
}

.intro-hero__kicker {
  color: #a09df5;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin: 0;
}

.intro-hero__title {
  margin: 8px 0 4px;
  font-size: clamp(28px, 5vw, 44px);
  line-height: 1.02;
  font-weight: 800;
  letter-spacing: -0.05em;
}

.intro-hero__subtitle {
  font-size: 16px;
  color: rgba(244, 239, 226, 0.8);
  margin: 0 0 16px;
}

.intro-hero__desc {
  max-width: 800px;
  font-size: 15px;
  line-height: 1.8;
  color: rgba(244, 239, 226, 0.82);
  margin: 0;
}

.intro-hero__stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-top: 24px;
  position: relative;
  z-index: 1;
}

.intro-hero-stat {
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(244, 239, 226, 0.08);
  text-align: center;
}

.intro-hero-stat__value {
  font-size: 28px;
  font-weight: 800;
  margin: 0;
  letter-spacing: -0.04em;
}

.intro-hero-stat__label {
  font-size: 11px;
  color: rgba(244, 239, 226, 0.68);
  margin: 5px 0 3px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
}

.intro-hero-stat__hint {
  font-size: 11px;
  color: rgba(244, 239, 226, 0.6);
  margin: 0;
}

/* ── Section ───────────────────────────────────────── */
.intro-section {
  margin-top: 28px;
}

.intro-section__head {
  margin-bottom: 16px;
}

.intro-section__kicker {
  color: #4648D4;
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin: 0;
}

.intro-section__title {
  margin: 6px 0 4px;
  font-size: 28px;
  line-height: 1.1;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: #0C172C;
}

.intro-section__subtitle {
  font-size: 14px;
  color: #68778c;
  margin: 0;
}

/* ── Layer Stack ────────────────────────────────────── */
.intro-layer-stack {
  display: grid;
  gap: 14px;
}

.intro-layer-card {
  padding: 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(70, 72, 212, 0.08);
  box-shadow: 0 12px 32px rgba(70, 72, 212, 0.06);
}

.intro-layer-card__top {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

.intro-layer-card__eyebrow {
  color: #4648D4;
  font-size: 12px;
  font-weight: 700;
  margin: 0;
}

.intro-layer-card__desc {
  margin: 6px 0 0;
  font-size: 16px;
  line-height: 1.5;
  font-weight: 700;
  color: #0C172C;
}

.intro-layer-card__pill {
  align-self: flex-start;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 700;
  background: rgba(70, 72, 212, 0.08);
  color: #4648D4;
  white-space: nowrap;
}

.intro-layer-card__groups {
  display: grid;
  gap: 14px;
  margin-top: 16px;
}

.intro-layer-card__group { }

.intro-layer-card__label {
  font-size: 11px;
  color: #7b8797;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin: 0 0 8px;
}

.intro-layer-card__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.intro-chip,
.intro-context-output {
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 12px;
  font-weight: 600;
  background: #f2f4f7;
  color: #304057;
}

.intro-chip--agent {
  background: rgba(70, 72, 212, 0.12);
  color: #4648D4;
}

.intro-chip--output {
  background: rgba(12, 23, 44, 0.08);
  color: #4f607a;
}

.intro-layer-card--facts      { border-left: 5px solid #3662a0; }
.intro-layer-card--coordinator { border-left: 5px solid #4648D4; }
.intro-layer-card--persona    { border-left: 5px solid #156f66; }
.intro-layer-card--guard      { border-left: 5px solid #c85c2d; }
.intro-layer-card--aggregate  { border-left: 5px solid #5f4bd1; }
.intro-layer-card--runtime    { border-left: 5px solid #2f3e57; }

/* ── Context ────────────────────────────────────────── */
.intro-context-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
}

.intro-context-card {
  padding: 20px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(70, 72, 212, 0.08);
  box-shadow: 0 12px 32px rgba(70, 72, 212, 0.06);
}

.intro-context-card--dark {
  background: linear-gradient(135deg, rgba(22, 27, 60, 0.96), rgba(45, 54, 100, 0.94));
  color: #f1ecdf;
}

.intro-context-card__eyebrow {
  color: #4648D4;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  margin: 0;
}

.intro-context-card__eyebrow--purple { color: #a09df5; }

.intro-context-card__title {
  margin: 10px 0 14px;
  font-size: 18px;
  line-height: 1.5;
  color: #0C172C;
}

.intro-context-card--dark .intro-context-card__title { color: #f1ecdf; }

.intro-context-card__list {
  display: grid;
  gap: 14px;
}

.intro-context-card__item-title {
  font-size: 14px;
  font-weight: 700;
  color: #0C172C;
  margin: 0;
}

.intro-context-card--dark .intro-context-card__item-title { color: #f1ecdf; }

.intro-context-card__item-desc {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.75;
  color: #5a6a7f;
}

.intro-context-card--dark .intro-context-card__item-desc { color: rgba(241, 236, 223, 0.8); }

.intro-context-rule-list {
  margin: 16px 0 0;
  padding-left: 18px;
  line-height: 1.9;
  color: rgba(241, 236, 223, 0.88);
}

.intro-context-card__foot {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
}

.intro-context-output {
  background: rgba(255, 255, 255, 0.08);
  color: #f1ecdf;
}

/* ── Flow ───────────────────────────────────────────── */
.intro-flow-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.intro-flow-card {
  display: flex;
  gap: 14px;
  padding: 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(12, 23, 44, 0.08);
  box-shadow: 0 12px 32px rgba(12, 23, 44, 0.06);
  position: relative;
}

.intro-flow-card__index {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: linear-gradient(135deg, #4648D4, #6063ee);
  color: #ffffff;
  font-weight: 800;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.intro-flow-card__title {
  font-size: 16px;
  font-weight: 700;
  color: #0C172C;
  margin: 0;
}

.intro-flow-card__detail {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.75;
  color: #5a6a7f;
}

/* ── Modes ──────────────────────────────────────────── */
.intro-mode-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}

.intro-mode-card {
  padding: 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(70, 72, 212, 0.08);
  box-shadow: 0 12px 32px rgba(70, 72, 212, 0.06);
}

.intro-mode-card__id {
  color: #4648D4;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  margin: 0;
}

.intro-mode-card__title {
  margin: 8px 0 6px;
  font-size: 18px;
  color: #0C172C;
}

.intro-mode-card__desc {
  font-size: 14px;
  line-height: 1.75;
  color: #5a6a7f;
  margin: 0;
}

/* ── Learn More Card ───────────────────────────────── */
.intro-learn-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 22px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(70, 72, 212, 0.1);
  box-shadow: 0 8px 28px rgba(70, 72, 212, 0.06);
  cursor: pointer;
  transition: all 0.2s;
  text-decoration: none;
}

.intro-learn-card:hover {
  box-shadow: 0 12px 36px rgba(70, 72, 212, 0.1);
  border-color: rgba(70, 72, 212, 0.25);
  transform: translateY(-1px);
}

.intro-learn-card__left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.intro-learn-card__icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(135deg, #4648D4, #6063ee);
  display: grid;
  place-items: center;
  flex-shrink: 0;
  box-shadow: 0 8px 20px rgba(70, 72, 212, 0.2);
}

.intro-learn-card__icon svg {
  width: 22px;
  height: 22px;
  color: #ffffff;
}

.intro-learn-card__title {
  font-size: 17px;
  font-weight: 800;
  color: #0C172C;
  margin: 0;
  letter-spacing: -0.02em;
}

.intro-learn-card__desc {
  margin: 5px 0 0;
  font-size: 13px;
  color: #68778c;
  line-height: 1.65;
}

.intro-learn-card__action {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 7px 14px;
  border-radius: 6px;
  background: #4648D4;
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
  cursor: pointer;
  transition: background 0.15s;
}

.intro-learn-card__arrow {
  width: 16px;
  height: 16px;
  transition: transform 0.15s ease;
}

.intro-learn-card__action:hover {
  background: #3638c6;
}

.intro-learn-card__action:hover .intro-learn-card__arrow {
  transform: translateX(2px);
}

/* ── Footer ────────────────────────────────────────── */
.intro-footer {
  margin-top: 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 24px 0 0;
  border-top: 1px solid rgba(70, 72, 212, 0.08);
}

.intro-footer__text {
  color: #94a3b8;
  font-size: 13px;
  margin: 0;
}

.intro-footer__back {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  border-radius: 999px;
  border: 1.5px solid rgba(70, 72, 212, 0.2);
  background: #fff;
  color: #4648D4;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  text-decoration: none;
}

.intro-footer__back svg { width: 18px; height: 18px; }

.intro-footer__back:hover {
  border-color: #4648D4;
  color: #3638c6;
}

/* ── Responsive ─────────────────────────────────────── */
@media (max-width: 767px) {
  .intro-main {
    width: min(100%, calc(100% - 20px));
    padding-top: 18px;
  }

  .intro-top {
    padding: 14px 12px;
  }

  .intro-hero {
    padding: 22px 18px;
    border-radius: 24px;
  }

  .intro-hero__stats {
    grid-template-columns: repeat(2, 1fr);
  }

  .intro-section__title {
    font-size: 24px;
  }

  .intro-layer-card__top {
    flex-direction: column;
  }

  .intro-layer-card__groups {
    grid-template-columns: 1fr;
  }

  .intro-learn-card {
    flex-direction: column;
    align-items: flex-start;
  }
  .intro-learn-card__action {
    align-self: flex-end;
  }
}
</style>
