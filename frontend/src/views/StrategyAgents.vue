<template>
  <div class="agents-arch-page">
    <header class="agents-arch-top">
      <button type="button" class="agents-arch-top__back" aria-label="返回" @click="$router.push('/strategy')">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <div class="agents-arch-top__brand">
        <div class="agents-arch-top__avatar">策</div>
        <div>
          <p class="agents-arch-top__eyebrow">STRATEGY SYSTEM</p>
          <h1 class="agents-arch-top__title">游资智能体架构台</h1>
        </div>
      </div>
      <button type="button" class="agents-arch-top__refresh" :disabled="loading" @click="loadArchitecture">
        <span v-if="loading" class="agents-arch-top__spinner" />
        <svg v-else class="icon" viewBox="0 0 24 24" fill="currentColor"><path d="M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
      </button>
    </header>

    <main class="agents-arch-main">
      <section class="agents-hero">
        <div class="agents-hero__mesh" />
        <div class="agents-hero__copy">
          <p class="agents-hero__kicker">不是角色列表，而是完整协同系统</p>
          <h2 class="agents-hero__title">共享事实层 + 主控协调层 + 方法论人格层 + 验证聚合层</h2>
          <p class="agents-hero__desc">
            现在的策略智能体页会直接展示系统分层、运行模式、共享事实协议和各人格打法，让我们能从“架构是否专业”而不是“Prompt 写得像不像”来评估这套系统。
          </p>
          <div class="agents-hero__actions">
            <router-link to="/strategy/ai/macro-summary" class="agents-hero__btn agents-hero__btn--primary">
              查看全场共识
            </router-link>
            <button type="button" class="agents-hero__btn" @click="scrollToPersonas">
              查看人格库
            </button>
          </div>
        </div>

        <div class="agents-hero__stats">
          <article v-for="stat in heroStats" :key="stat.label" class="hero-stat">
            <p class="hero-stat__label">{{ stat.label }}</p>
            <p class="hero-stat__value tabular">{{ stat.value }}</p>
            <p class="hero-stat__hint">{{ stat.hint }}</p>
          </article>
        </div>
      </section>

      <section v-if="errorMsg" class="agents-error">
        <strong>架构数据加载失败：</strong>{{ errorMsg }}
      </section>

      <section v-if="loading && !architecture" class="agents-loading">
        <div class="agents-loading__spinner" />
        <p>正在加载策略系统架构…</p>
      </section>

      <template v-else-if="architecture">
        <section class="agents-section">
          <div class="agents-section__head">
            <div>
              <p class="agents-section__kicker">SYSTEM PRINCIPLES</p>
              <h2 class="agents-section__title">设计原则</h2>
            </div>
            <span class="agents-section__badge">v{{ architecture.version || '2.0' }}</span>
          </div>
          <div class="principle-grid">
            <article v-for="(principle, index) in architecture.principles || []" :key="principle" class="principle-card">
              <span class="principle-card__index">{{ index + 1 }}</span>
              <p class="principle-card__text">{{ principle }}</p>
            </article>
          </div>
        </section>

        <section class="agents-section">
          <div class="agents-section__head">
            <div>
              <p class="agents-section__kicker">ARCHITECTURE STACK</p>
              <h2 class="agents-section__title">系统分层</h2>
            </div>
            <span class="agents-section__badge">{{ layers.length }} 层</span>
          </div>
          <div class="layer-stack">
            <article
              v-for="layer in layers"
              :key="layer.id"
              class="layer-card"
              :class="'layer-card--' + layer.tone"
            >
              <div class="layer-card__top">
                <div>
                  <p class="layer-card__eyebrow">{{ layer.title }}</p>
                  <h3 class="layer-card__title">{{ layer.description }}</h3>
                </div>
                <span class="layer-card__pill">
                  {{ (layer.agents && layer.agents.length) || (layer.modules && layer.modules.length) || 0 }} 个模块
                </span>
              </div>
              <div class="layer-card__groups">
                <div class="layer-card__group">
                  <p class="layer-card__label">核心模块</p>
                  <div class="layer-card__chips">
                    <span v-for="module in layer.modules || []" :key="module" class="layer-chip">{{ module }}</span>
                  </div>
                </div>
                <div v-if="layer.agents?.length" class="layer-card__group">
                  <p class="layer-card__label">关联 Agent</p>
                  <div class="layer-card__chips">
                    <span v-for="agent in layer.agents" :key="agent.id" class="layer-chip layer-chip--agent">
                      {{ agent.name }}
                    </span>
                  </div>
                </div>
                <div class="layer-card__group">
                  <p class="layer-card__label">产出</p>
                  <div class="layer-card__chips">
                    <span v-for="output in layer.outputs || []" :key="output" class="layer-chip layer-chip--output">{{ output }}</span>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section class="agents-section">
          <div class="agents-section__head">
            <div>
              <p class="agents-section__kicker">SHARED CONTEXT CONTRACT</p>
              <h2 class="agents-section__title">共享事实协议</h2>
            </div>
            <span class="agents-section__badge">{{ sharedContext.inputs.length }} 个输入</span>
          </div>
          <div class="context-grid">
            <article class="context-card">
              <p class="context-card__eyebrow">{{ sharedContext.name }}</p>
              <h3 class="context-card__title">{{ sharedContext.description }}</h3>
              <div class="context-card__list">
                <div v-for="input in sharedContext.inputs" :key="input.id" class="context-card__item">
                  <p class="context-card__item-title">{{ input.label }}</p>
                  <p class="context-card__item-desc">{{ input.description }}</p>
                </div>
              </div>
            </article>

            <article class="context-card">
              <p class="context-card__eyebrow">系统硬约束</p>
              <h3 class="context-card__title">人格不是数据源</h3>
              <ul class="context-rule-list">
                <li v-for="rule in sharedContext.rules" :key="rule">{{ rule }}</li>
              </ul>
              <div class="context-card__foot">
                <span v-for="output in sharedContext.outputs" :key="output" class="context-output">{{ output }}</span>
              </div>
            </article>
          </div>
        </section>

        <section class="agents-section">
          <div class="agents-section__head">
            <div>
              <p class="agents-section__kicker">EXECUTION FLOW</p>
              <h2 class="agents-section__title">执行链路</h2>
            </div>
            <span class="agents-section__badge">{{ executionFlow.length }} 步</span>
          </div>
          <div class="flow-grid">
            <article v-for="(step, index) in executionFlow" :key="step.id" class="flow-card">
              <div class="flow-card__index">{{ index + 1 }}</div>
              <div>
                <h3 class="flow-card__title">{{ step.title }}</h3>
                <p class="flow-card__detail">{{ step.detail }}</p>
              </div>
            </article>
          </div>
        </section>

        <section class="agents-section">
          <div class="agents-section__head">
            <div>
              <p class="agents-section__kicker">RUNTIME MODES</p>
              <h2 class="agents-section__title">运行模式</h2>
            </div>
            <span class="agents-section__badge">{{ runtimeModes.length }} 种</span>
          </div>
          <div class="mode-grid">
            <article v-for="mode in runtimeModes" :key="mode.id" class="mode-card">
              <p class="mode-card__id">{{ mode.id }}</p>
              <h3 class="mode-card__title">{{ mode.title }}</h3>
              <p class="mode-card__desc">{{ mode.description }}</p>
            </article>
          </div>
        </section>

        <section class="agents-section" id="persona-library">
          <div class="agents-section__head">
            <div>
              <p class="agents-section__kicker">PERSONA LAYER</p>
              <h2 class="agents-section__title">方法论人格库</h2>
            </div>
            <span class="agents-section__badge">{{ personaCards.length }} 位人格</span>
          </div>

          <article v-if="coordinatorCard" class="coordinator-card">
            <div class="coordinator-card__top">
              <div>
                <p class="coordinator-card__eyebrow">COORDINATOR</p>
                <h3 class="coordinator-card__title">{{ coordinatorCard.name }}</h3>
              </div>
              <span class="coordinator-card__pill">{{ formatPolicy(coordinatorCard.toolPolicy) }}</span>
            </div>
            <p class="coordinator-card__desc">{{ coordinatorCard.coreObjective }}</p>
            <div class="coordinator-card__meta">
              <span class="coordinator-meta">{{ coordinatorCard.styleCategory }}</span>
              <span class="coordinator-meta">{{ coordinatorCard.holdingStyle }}</span>
              <span class="coordinator-meta">{{ coordinatorCard.requiredInputs.length }} 个核心输入</span>
            </div>
            <div class="coordinator-card__rules">
              <div>
                <p class="coordinator-card__label">硬规则</p>
                <ul class="coordinator-card__list">
                  <li v-for="rule in coordinatorCard.hardRules" :key="rule">{{ rule }}</li>
                </ul>
              </div>
              <div>
                <p class="coordinator-card__label">关键输出</p>
                <div class="coordinator-card__chips">
                  <span v-for="field in coordinatorCard.outputFocus" :key="field">{{ field }}</span>
                </div>
              </div>
            </div>
          </article>

          <div class="persona-grid">
            <article v-for="agent in personaCards" :key="agent.id" class="persona-card">
              <div class="persona-card__head">
                <div class="persona-card__who">
                  <div class="persona-card__avatar">{{ agent.name[0] }}</div>
                  <div>
                    <h3 class="persona-card__name">{{ agent.name }}</h3>
                    <p class="persona-card__style">{{ agent.styleCategory }}</p>
                  </div>
                </div>
                <div class="persona-card__perf">
                  <p class="persona-card__perf-label">胜率 / 收益</p>
                  <p class="persona-card__perf-value tabular">
                    <template v-if="agent.analysisCount > 0">
                      {{ agent.winRate }}% / {{ agent.returnPct >= 0 ? '+' : '' }}{{ agent.returnPct }}%
                    </template>
                    <template v-else>待积累</template>
                  </p>
                </div>
              </div>

              <div class="persona-card__meta">
                <span class="persona-meta">{{ formatPhase(agent.phase) }}</span>
                <span class="persona-meta">{{ agent.holdingStyle }}</span>
                <span class="persona-meta">{{ formatPolicy(agent.toolPolicy) }}</span>
              </div>

              <p class="persona-card__objective">{{ agent.coreObjective }}</p>

              <div class="persona-card__block">
                <p class="persona-card__label">依赖输入</p>
                <div class="persona-card__chips">
                  <span v-for="input in agent.requiredInputs.slice(0, 4)" :key="input">{{ input }}</span>
                </div>
              </div>

              <div class="persona-card__block">
                <p class="persona-card__label">方法论步骤</p>
                <ol class="persona-card__steps">
                  <li v-for="step in agent.reasoningSteps.slice(0, 3)" :key="step.title">
                    <strong>{{ step.title }}</strong>{{ step.description ? `：${step.description}` : '' }}
                  </li>
                </ol>
              </div>

              <div class="persona-card__block">
                <p class="persona-card__label">硬规则</p>
                <ul class="persona-card__rules">
                  <li v-for="rule in agent.hardRules.slice(0, 3)" :key="rule">{{ rule }}</li>
                </ul>
              </div>

              <div class="persona-card__foot">
                <button type="button" class="persona-card__btn persona-card__btn--ghost" @click="goToHoldings(agent)">
                  查看持仓
                </button>
                <button type="button" class="persona-card__btn persona-card__btn--primary" @click="goToAnalysis(agent)">
                  查看分析
                </button>
              </div>
            </article>
          </div>
        </section>

        <p class="agents-footnote">
          数据生成时间：{{ formatGeneratedAt(architecture.generatedAt) }}。当前页面展示的是“系统如何协同工作”，不是收益承诺。
        </p>
      </template>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchAgentArchitecture } from '@/api/agents.js'

const router = useRouter()

const architecture = ref(null)
const loading = ref(false)
const errorMsg = ref('')
const agentPerf = ref({})

const sharedContext = computed(() => architecture.value?.sharedContext || { inputs: [], rules: [], outputs: [] })
const layers = computed(() => architecture.value?.layers || [])
const executionFlow = computed(() => architecture.value?.executionFlow || [])
const runtimeModes = computed(() => architecture.value?.runtimeModes || [])
const coordinatorCard = computed(() => (architecture.value?.coordinatorAgents || [])[0] || null)

const personaCards = computed(() => {
  const personas = architecture.value?.personaAgents || []
  return personas.map((agent) => {
    const perf = agentPerf.value[agent.id] || {}
    const analysisCount = Number(perf.analysisCount || 0)
    return {
      ...agent,
      analysisCount,
      winRate: analysisCount > 0 ? Number(perf.winRate || 0) : 0,
      returnPct: analysisCount > 0 ? Number(perf.returnPct || 0) : 0,
    }
  })
})

const heroStats = computed(() => [
  {
    label: '人格 Agent',
    value: personaCards.value.length || '—',
    hint: '策略打法层',
  },
  {
    label: '共享事实输入',
    value: sharedContext.value.inputs.length || '—',
    hint: '统一 MarketContextPacket',
  },
  {
    label: '系统层级',
    value: layers.value.length || '—',
    hint: '从事实到聚合',
  },
  {
    label: '运行模式',
    value: runtimeModes.value.length || '—',
    hint: '单体 / 批量 / 层次化',
  },
])

async function fetchAgentPerformance(ids) {
  if (!ids.length) return
  const nextPerf = {}
  await Promise.allSettled(ids.map(async (id) => {
    try {
      const res = await fetch(`/api/agents/${id}/performance`).then((r) => r.json())
      if (res.success && res.data) nextPerf[id] = res.data
    } catch {
      // 忽略绩效接口失败，页面仍然渲染架构信息
    }
  }))
  agentPerf.value = nextPerf
}

async function loadArchitecture() {
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await fetchAgentArchitecture()
    architecture.value = data
    await fetchAgentPerformance((data?.personaAgents || []).map((agent) => agent.id))
  } catch (error) {
    errorMsg.value = error?.message || '无法加载策略系统架构'
  } finally {
    loading.value = false
  }
}

function goToHoldings(agent) {
  router.push(`/strategy/agents/${agent.id}`)
}

function goToAnalysis(agent) {
  router.push(`/strategy/agents/${agent.id}/analysis`)
}

function scrollToPersonas() {
  const target = document.getElementById('persona-library')
  if (!target) return
  target.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function formatPhase(phase) {
  const map = {
    master: '主控阶段',
    phase_1: '题材分析阶段',
    phase_2: '技术执行阶段',
    phase_3: '综合判断阶段',
  }
  return map[phase] || '策略人格层'
}

function formatPolicy(policy) {
  const map = {
    shared_context_only: '只读共享事实',
    shared_context_first: '共享事实优先',
    selective_market_tools: '精选行情工具',
    market_board_tools: '涨停板工具',
    data_driven: '数据驱动',
  }
  return map[policy] || policy || '默认策略'
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

onMounted(loadArchitecture)
</script>

<style scoped>
.agents-arch-page {
  min-height: 100vh;
  min-height: 100dvh;
  background:
    radial-gradient(circle at top right, rgba(198, 151, 52, 0.16), transparent 32%),
    linear-gradient(180deg, #fbfaf5 0%, #f2efe7 36%, #ece8de 100%);
  color: #152033;
  padding-bottom: calc(24px + env(safe-area-inset-bottom, 0px));
}

.agents-arch-top {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
  backdrop-filter: blur(18px);
  background: rgba(248, 244, 234, 0.84);
  border-bottom: 1px solid rgba(84, 68, 38, 0.08);
}

.agents-arch-top__back,
.agents-arch-top__refresh {
  width: 40px;
  height: 40px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(84, 68, 38, 0.08);
  box-shadow: 0 8px 24px rgba(21, 32, 51, 0.06);
}

.agents-arch-top__brand {
  min-width: 0;
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
}

.agents-arch-top__avatar {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #0f1b2f, #1f3659);
  color: #f7d78c;
  font-size: 18px;
  font-weight: 800;
  box-shadow: 0 16px 36px rgba(15, 27, 47, 0.18);
}

.agents-arch-top__eyebrow {
  font-size: 10px;
  letter-spacing: 0.18em;
  color: #856732;
  text-transform: uppercase;
}

.agents-arch-top__title {
  font-size: 20px;
  line-height: 1.1;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.agents-arch-top__spinner,
.agents-loading__spinner {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid rgba(21, 32, 51, 0.14);
  border-top-color: #8b6a22;
  animation: agents-spin 0.8s linear infinite;
}

@keyframes agents-spin {
  to {
    transform: rotate(360deg);
  }
}

.agents-arch-main {
  width: min(1160px, calc(100% - 32px));
  margin: 0 auto;
  padding: 28px 0 48px;
}

.agents-hero {
  position: relative;
  overflow: hidden;
  display: grid;
  gap: 20px;
  padding: 28px;
  border-radius: 28px;
  background:
    linear-gradient(135deg, rgba(12, 23, 42, 0.98) 0%, rgba(28, 49, 84, 0.96) 58%, rgba(63, 45, 14, 0.92) 100%);
  color: #f4efe2;
  box-shadow: 0 32px 72px rgba(10, 18, 31, 0.2);
}

.agents-hero__mesh {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 18% 18%, rgba(247, 215, 140, 0.16), transparent 24%),
    radial-gradient(circle at 82% 26%, rgba(124, 173, 255, 0.2), transparent 28%),
    linear-gradient(120deg, transparent 0%, rgba(255, 255, 255, 0.04) 45%, transparent 100%);
  pointer-events: none;
}

.agents-hero__copy,
.agents-hero__stats {
  position: relative;
  z-index: 1;
}

.agents-hero__kicker {
  color: #f0c973;
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.agents-hero__title {
  margin-top: 8px;
  font-size: clamp(28px, 4vw, 42px);
  line-height: 1.02;
  font-weight: 800;
  letter-spacing: -0.05em;
}

.agents-hero__desc {
  max-width: 760px;
  margin-top: 14px;
  color: rgba(244, 239, 226, 0.8);
  font-size: 15px;
  line-height: 1.75;
}

.agents-hero__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 22px;
}

.agents-hero__btn {
  border-radius: 999px;
  padding: 12px 18px;
  border: 1px solid rgba(244, 239, 226, 0.18);
  color: #f4efe2;
  background: rgba(255, 255, 255, 0.06);
  font-size: 14px;
  font-weight: 600;
}

.agents-hero__btn--primary {
  background: linear-gradient(135deg, #f4c96f, #c9972d);
  border-color: transparent;
  color: #1a2235;
}

.agents-hero__stats {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
}

.hero-stat {
  padding: 16px 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(244, 239, 226, 0.08);
}

.hero-stat__label {
  font-size: 12px;
  color: rgba(244, 239, 226, 0.68);
}

.hero-stat__value {
  margin-top: 6px;
  font-size: 30px;
  line-height: 1;
  font-weight: 800;
}

.hero-stat__hint {
  margin-top: 8px;
  color: rgba(244, 239, 226, 0.72);
  font-size: 12px;
}

.agents-error,
.agents-loading {
  margin-top: 20px;
  padding: 18px 20px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid rgba(21, 32, 51, 0.08);
}

.agents-error {
  color: #b42318;
}

.agents-loading {
  display: flex;
  align-items: center;
  gap: 12px;
}

.agents-section {
  margin-top: 26px;
}

.agents-section__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.agents-section__kicker {
  color: #8b6a22;
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.agents-section__title {
  margin-top: 4px;
  font-size: 28px;
  line-height: 1.1;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: #17243a;
}

.agents-section__badge {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(183, 138, 34, 0.12);
  color: #7d5e1f;
  font-size: 12px;
  font-weight: 700;
}

.principle-grid,
.flow-grid,
.mode-grid,
.persona-grid,
.context-grid {
  display: grid;
  gap: 14px;
}

.principle-grid {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.principle-card,
.context-card,
.mode-card,
.flow-card,
.coordinator-card,
.persona-card,
.layer-card {
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(21, 32, 51, 0.08);
  box-shadow: 0 18px 40px rgba(21, 32, 51, 0.06);
}

.principle-card {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 18px;
}

.principle-card__index {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #16335b, #315688);
  color: #f7d78c;
  font-weight: 800;
  flex-shrink: 0;
}

.principle-card__text {
  font-size: 14px;
  line-height: 1.75;
  color: #304057;
}

.layer-stack {
  display: grid;
  gap: 14px;
}

.layer-card {
  padding: 18px 18px 16px;
}

.layer-card__top {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

.layer-card__eyebrow {
  color: #7d5e1f;
  font-size: 12px;
  font-weight: 700;
}

.layer-card__title {
  margin-top: 6px;
  font-size: 16px;
  line-height: 1.55;
  font-weight: 700;
  color: #17243a;
}

.layer-card__pill {
  align-self: flex-start;
  border-radius: 999px;
  padding: 8px 10px;
  font-size: 12px;
  font-weight: 700;
  background: rgba(21, 32, 51, 0.06);
  color: #47566d;
}

.layer-card__groups {
  display: grid;
  gap: 14px;
  margin-top: 16px;
}

.layer-card__label,
.persona-card__label,
.coordinator-card__label {
  font-size: 12px;
  color: #7b8797;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.layer-card__chips,
.coordinator-card__chips,
.persona-card__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.layer-chip,
.coordinator-card__chips span,
.persona-card__chips span,
.context-output,
.persona-meta,
.coordinator-meta {
  border-radius: 999px;
  padding: 7px 11px;
  font-size: 12px;
  font-weight: 600;
}

.layer-chip {
  background: #f2f4f7;
  color: #304057;
}

.layer-chip--agent {
  background: rgba(183, 138, 34, 0.14);
  color: #815f15;
}

.layer-chip--output {
  background: rgba(21, 32, 51, 0.08);
  color: #4f607a;
}

.layer-card--facts {
  border-left: 6px solid #3662a0;
}

.layer-card--coordinator {
  border-left: 6px solid #8b6a22;
}

.layer-card--persona {
  border-left: 6px solid #156f66;
}

.layer-card--guard {
  border-left: 6px solid #c85c2d;
}

.layer-card--aggregate {
  border-left: 6px solid #5f4bd1;
}

.layer-card--runtime {
  border-left: 6px solid #2f3e57;
}

.context-grid {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.context-card {
  padding: 20px;
}

.context-card__eyebrow {
  color: #8b6a22;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.context-card__title {
  margin-top: 10px;
  font-size: 18px;
  line-height: 1.55;
  color: #17243a;
}

.context-card__list {
  display: grid;
  gap: 14px;
  margin-top: 16px;
}

.context-card__item-title {
  font-size: 14px;
  font-weight: 700;
  color: #23314b;
}

.context-card__item-desc {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.75;
  color: #5a6a7f;
}

.context-rule-list {
  margin-top: 16px;
  padding-left: 18px;
  color: #36465d;
  line-height: 1.8;
}

.context-card__foot {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
}

.context-output,
.persona-meta,
.coordinator-meta {
  background: rgba(21, 32, 51, 0.06);
  color: #304057;
}

.flow-grid {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.flow-card {
  display: flex;
  gap: 14px;
  padding: 18px;
}

.flow-card__index {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  background: linear-gradient(135deg, #f1c66f, #ca932c);
  color: #17243a;
  font-weight: 800;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.flow-card__title {
  font-size: 16px;
  font-weight: 700;
  color: #17243a;
}

.flow-card__detail,
.mode-card__desc,
.persona-card__objective,
.coordinator-card__desc {
  margin-top: 6px;
  font-size: 14px;
  line-height: 1.75;
  color: #5a6a7f;
}

.mode-grid {
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
}

.mode-card {
  padding: 18px;
}

.mode-card__id {
  color: #8b6a22;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}

.mode-card__title {
  margin-top: 8px;
  font-size: 18px;
  color: #17243a;
}

.coordinator-card {
  padding: 22px;
  background: linear-gradient(135deg, rgba(17, 29, 49, 0.96), rgba(45, 54, 70, 0.94));
  color: #f1ecdf;
}

.coordinator-card__top {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.coordinator-card__eyebrow {
  color: #f2cc78;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.coordinator-card__title {
  margin-top: 6px;
  font-size: 24px;
  line-height: 1.05;
  font-weight: 800;
}

.coordinator-card__pill {
  align-self: flex-start;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(242, 204, 120, 0.12);
  color: #f6d892;
  font-size: 12px;
  font-weight: 700;
}

.coordinator-card__meta,
.persona-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.coordinator-card__rules {
  display: grid;
  gap: 18px;
  margin-top: 18px;
}

.coordinator-card__list {
  margin-top: 8px;
  padding-left: 18px;
  line-height: 1.8;
  color: rgba(241, 236, 223, 0.86);
}

.coordinator-card__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.coordinator-card__chips span {
  background: rgba(255, 255, 255, 0.08);
  color: #f1ecdf;
}

.persona-grid {
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  margin-top: 16px;
}

.persona-card {
  padding: 18px;
}

.persona-card__head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

.persona-card__who {
  display: flex;
  align-items: center;
  gap: 12px;
}

.persona-card__avatar {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #183456, #2f5b8b);
  color: #f7d78c;
  font-size: 18px;
  font-weight: 800;
  box-shadow: 0 14px 30px rgba(22, 51, 91, 0.18);
}

.persona-card__name {
  font-size: 20px;
  line-height: 1.1;
  color: #17243a;
}

.persona-card__style {
  margin-top: 4px;
  font-size: 13px;
  color: #7a8797;
}

.persona-card__perf {
  text-align: right;
}

.persona-card__perf-label {
  font-size: 11px;
  color: #7a8797;
}

.persona-card__perf-value {
  margin-top: 5px;
  font-size: 15px;
  font-weight: 700;
  color: #22314b;
}

.persona-card__block {
  margin-top: 14px;
}

.persona-card__steps,
.persona-card__rules {
  margin-top: 8px;
  padding-left: 18px;
  color: #304057;
  line-height: 1.75;
}

.persona-card__foot {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}

.persona-card__btn {
  flex: 1;
  border-radius: 14px;
  padding: 12px 14px;
  font-size: 14px;
  font-weight: 700;
  border: 1px solid rgba(21, 32, 51, 0.08);
  background: #fff;
  color: #24334c;
}

.persona-card__btn--primary {
  background: linear-gradient(135deg, #172943, #27476f);
  border-color: transparent;
  color: #f4efe2;
}

.agents-footnote {
  margin-top: 24px;
  text-align: center;
  color: #68778c;
  font-size: 13px;
}

@media (max-width: 767px) {
  .agents-arch-main {
    width: min(100%, calc(100% - 20px));
    padding-top: 18px;
  }

  .agents-arch-top {
    padding: 14px 12px;
  }

  .agents-hero {
    padding: 22px 18px;
    border-radius: 24px;
  }

  .agents-section__title {
    font-size: 24px;
  }

  .persona-card__head,
  .coordinator-card__top {
    flex-direction: column;
  }

  .persona-card__perf {
    text-align: left;
  }
}
</style>
