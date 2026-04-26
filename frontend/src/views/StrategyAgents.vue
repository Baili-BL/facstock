<template>
  <div class="landing-page">
    <!-- Header -->
    <header class="lp-header">
      <button type="button" class="lp-back" aria-label="返回" @click="$router.push('/strategy')">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M15.41 7.41 14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>
      </button>
      <div class="lp-header__brand">
        <div class="lp-header__logo">策</div>
        <div>
          <p class="lp-header__eyebrow">FACSTOCK</p>
          <h1 class="lp-header__title">游资智能体架构台</h1>
        </div>
      </div>
    </header>

    <main class="lp-main">

      <!-- Loading -->
      <div v-if="loading && !architecture" class="lp-loading">
        <div class="lp-spinner" />
        <p>正在加载…</p>
      </div>

      <template v-if="architecture">
        <!-- Hero -->
        <section class="lp-hero">
          <div class="lp-hero__deco" aria-hidden="true">
            <div class="lp-hero__circle lp-hero__circle--1" />
            <div class="lp-hero__circle lp-hero__circle--2" />
          </div>
          <div class="lp-hero__content">
            <p class="lp-hero__kicker">不是角色列表，而是一套完整协同系统</p>
            <h2 class="lp-hero__title">共享事实层 + 主控协调层<br>方法论人格层 + 验证聚合层</h2>
          </div>
        </section>

        <!-- Entry Cards (horizontal scroll) -->
        <div class="lp-entries-scroll">
          <router-link to="/strategy/agents/intro" class="lp-entry-card">
            <div class="lp-entry-card__icon">
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>
            </div>
            <div class="lp-entry-card__body">
              <h3 class="lp-entry-card__title">游资智能体架构台是什么？</h3>
              <p class="lp-entry-card__desc">不是角色列表，而是一套完整的多智能体协同选股系统。了解它的分层设计、运行机制与人格打法。</p>
            </div>
            <div class="lp-entry-card__action">
              <span>系统介绍</span>
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
            </div>
          </router-link>

          <router-link to="/strategy/agents" class="lp-entry-card">
            <div class="lp-entry-card__icon">
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5s-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>
            </div>
            <div class="lp-entry-card__body">
              <h3 class="lp-entry-card__title">方法论人格库</h3>
              <p class="lp-entry-card__desc">查看所有游资人格 Agent，包括连板猎手、龙头信仰、首板先锋等策略打法。</p>
            </div>
            <div class="lp-entry-card__action">
              <span>进入查看</span>
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
            </div>
          </router-link>

          <router-link to="/strategy/agents/feishu" class="lp-entry-card">
            <div class="lp-entry-card__icon">
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>
            </div>
            <div class="lp-entry-card__body">
              <h3 class="lp-entry-card__title">飞书变更记录</h3>
              <p class="lp-entry-card__desc">查看飞书推送的配置变更历史记录，支持新增、编辑、查看推送管理配置。</p>
            </div>
            <div class="lp-entry-card__action">
              <span>查看记录</span>
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
            </div>
          </router-link>
        </div>

        <!-- Stats Row -->
        <div class="lp-stats">
          <div class="lp-stat">
            <span class="lp-stat__num">{{ (architecture.personaAgents || []).length || architecture.layers?.length || 0 }}</span>
            <span class="lp-stat__label">人格 Agent</span>
          </div>
          <div class="lp-stat">
            <span class="lp-stat__num">{{ architecture.sharedContext?.inputs?.length || 0 }}</span>
            <span class="lp-stat__label">共享事实输入</span>
          </div>
          <div class="lp-stat">
            <span class="lp-stat__num">{{ architecture.layers?.length || 0 }}</span>
            <span class="lp-stat__label">系统层级</span>
          </div>
          <div class="lp-stat">
            <span class="lp-stat__num">{{ architecture.runtimeModes?.length || 0 }}</span>
            <span class="lp-stat__label">运行模式</span>
          </div>
        </div>

        <!-- Persona Grid -->
        <section class="lp-personas" id="persona-library">
          <div class="lp-section-head">
            <p class="lp-section-head__kicker">PERSONA LAYER</p>
            <h2 class="lp-section-head__title">方法论人格库</h2>
          </div>
          <div class="lp-persona-grid">
            <article
              v-for="agent in personaCards"
              :key="agent.id"
              class="lp-persona-card"
            >
              <div class="lp-persona-card__top">
                <div class="lp-persona-card__avatar">{{ agent.name[0] }}</div>
                <div class="lp-persona-card__info">
                  <div class="lp-persona-card__tags">
                    <span class="lp-tag">{{ formatPhase(agent.phase) }}</span>
                    <span class="lp-tag">{{ agent.holdingStyle }}</span>
                  </div>
                  <h3 class="lp-persona-card__name">{{ agent.name }}</h3>
                  <p class="lp-persona-card__style">{{ agent.styleCategory }}</p>
                </div>
              </div>

              <div class="lp-persona-card__metrics">
                <div class="lp-metric">
                  <span class="lp-metric__label">胜率</span>
                  <span class="lp-metric__val">{{ agent.analysisCount > 0 ? agent.winRate + '%' : '—' }}</span>
                </div>
                <div class="lp-metric">
                  <span class="lp-metric__label">累计收益</span>
                  <span class="lp-metric__val" :class="agent.analysisCount > 0 ? (agent.returnPct >= 0 ? 'is-up' : 'is-down') : ''">
                    {{ agent.analysisCount > 0 ? (agent.returnPct >= 0 ? '+' : '') + agent.returnPct + '%' : '—' }}
                  </span>
                </div>
                <div class="lp-metric">
                  <span class="lp-metric__label">夏普率</span>
                  <span class="lp-metric__val">{{ agent.analysisCount > 0 ? (agent.sharpeRatio || '—') : '—' }}</span>
                </div>
                <div class="lp-metric">
                  <span class="lp-metric__label">最大回撤</span>
                  <span class="lp-metric__val is-down">{{ agent.analysisCount > 0 && agent.maxDrawdown ? agent.maxDrawdown + '%' : '—' }}</span>
                </div>
              </div>

              <p class="lp-persona-card__objective">{{ agent.coreObjective }}</p>

              <div class="lp-persona-card__btns">
                <button type="button" class="lp-btn lp-btn--primary" @click="goToAnalysis(agent)">
                  查看分析
                  <svg viewBox="0 0 24 24"><path fill="currentColor" d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
                </button>
                <button type="button" class="lp-btn lp-btn--secondary" @click="goToHoldings(agent)">
                  查看持仓
                  <svg viewBox="0 0 24 24"><path fill="currentColor" d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
                </button>
              </div>
            </article>
          </div>
        </section>

        <p class="lp-footnote">
          数据生成时间：{{ formatGeneratedAt(architecture.generatedAt) }}。
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

async function fetchAgentPerformance(ids) {
  if (!ids.length) return
  const nextPerf = {}
  await Promise.allSettled(ids.map(async (id) => {
    try {
      const res = await fetch(`/api/agents/${id}/performance`).then((r) => r.json())
      if (res.success && res.data) nextPerf[id] = res.data
    } catch {}
  }))
  agentPerf.value = nextPerf
}

async function loadArchitecture() {
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await fetchAgentArchitecture()
    architecture.value = data
    await fetchAgentPerformance((data?.personaAgents || []).map((a) => a.id))
  } catch (error) {
    errorMsg.value = error?.message || '无法加载策略系统架构'
  } finally {
    loading.value = false
  }
}

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

function goToHoldings(agent) { router.push(`/strategy/agents/${agent.id}`) }
function goToDetail(agent) { router.push(`/strategy/agents/${agent.id}/summary`) }
function goToAnalysis(agent) { router.push(`/strategy/agents/${agent.id}/analysis`) }

function formatPhase(phase) {
  const map = { phase_1: '题材挖掘', phase_2: '信号生成', phase_3: '风控聚合' }
  return map[phase] || phase || ''
}

function formatGeneratedAt(value) {
  if (!value) return '未知'
  try {
    return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return value }
}

onMounted(() => { loadArchitecture() })
</script>

<style scoped>
/* ── Page ───────────────────────────────────────────── */
.landing-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: #ffffff;
  padding-bottom: 40px;
}

/* ── Header ─────────────────────────────────────────── */
.lp-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 18px;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.lp-back {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #f5f5f5;
  border: none;
  cursor: pointer;
  transition: background 0.15s;
  flex-shrink: 0;
}

.lp-back:hover { background: #eee; }
.lp-back svg { width: 20px; height: 20px; color: #333; }

.lp-header__brand {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
}

.lp-header__logo {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: linear-gradient(135deg, #0C172C, #1a2d4f);
  color: #C8973A;
  font-size: 16px;
  font-weight: 800;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.lp-header__eyebrow {
  font-size: 10px;
  letter-spacing: 0.14em;
  color: #888;
  text-transform: uppercase;
  margin: 0;
}

.lp-header__title {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin: 0;
  color: #0C172C;
}

/* ── Main ───────────────────────────────────────────── */
.lp-main {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px 18px 0;
}

/* ── Loading ────────────────────────────────────────── */
.lp-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 0;
  color: #888;
  font-size: 14px;
}

.lp-spinner {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid #eee;
  border-top-color: #C8973A;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Hero ───────────────────────────────────────────── */
.lp-hero {
  position: relative;
  overflow: hidden;
  border-radius: 20px;
  padding: 32px 28px;
  background: linear-gradient(135deg, #0C172C 0%, #152238 60%, #1a2d4f 100%);
  color: #fff;
  margin-bottom: 20px;
}

.lp-hero__deco {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.lp-hero__circle {
  position: absolute;
  border-radius: 50%;
}

.lp-hero__circle--1 {
  width: 220px;
  height: 220px;
  top: -80px;
  right: -60px;
  background: radial-gradient(circle, rgba(200, 151, 58, 0.2), transparent 70%);
}

.lp-hero__circle--2 {
  width: 160px;
  height: 160px;
  bottom: -50px;
  left: 20px;
  background: radial-gradient(circle, rgba(200, 151, 58, 0.12), transparent 70%);
}

.lp-hero__content {
  position: relative;
  z-index: 1;
}

.lp-hero__kicker {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: #C8973A;
  margin: 0 0 10px;
  text-transform: uppercase;
}

.lp-hero__title {
  margin: 0;
  font-size: 22px;
  line-height: 1.35;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #fff;
}

/* ── Entry Cards (horizontal scroll) ────────────────── */
.lp-entries-scroll {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 4px;
  margin-bottom: 20px;
  scrollbar-width: none;
}

.lp-entries-scroll::-webkit-scrollbar { display: none; }

.lp-entry-card {
  flex: 0 0 300px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border-radius: 16px;
  background: #fafafa;
  border: 1px solid rgba(0, 0, 0, 0.06);
  text-decoration: none;
  color: inherit;
  cursor: pointer;
  transition: box-shadow 0.15s, border-color 0.15s;
}

.lp-entry-card:hover {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  border-color: rgba(200, 151, 58, 0.3);
}

.lp-entry-card__icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, #0C172C, #152238);
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.lp-entry-card__icon svg { width: 20px; height: 20px; color: #C8973A; }

.lp-entry-card__body { flex: 1; }

.lp-entry-card__title {
  font-size: 14px;
  font-weight: 700;
  color: #0C172C;
  margin: 0 0 4px;
}

.lp-entry-card__desc {
  font-size: 12px;
  color: #666;
  line-height: 1.5;
  margin: 0;
}

.lp-entry-card__action {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 700;
  color: #C8973A;
}

.lp-entry-card__action svg { width: 14px; height: 14px; }

/* ── Stats ──────────────────────────────────────────── */
.lp-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 28px;
}

.lp-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 14px 8px;
  border-radius: 12px;
  background: #fafafa;
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.lp-stat__num {
  font-size: 22px;
  font-weight: 800;
  color: #0C172C;
  letter-spacing: -0.04em;
}

.lp-stat__label {
  font-size: 11px;
  color: #888;
  margin-top: 4px;
  text-align: center;
}

/* ── Section Head ───────────────────────────────────── */
.lp-section-head { margin-bottom: 16px; }

.lp-section-head__kicker {
  font-size: 11px;
  letter-spacing: 0.14em;
  color: #C8973A;
  font-weight: 700;
  text-transform: uppercase;
  margin: 0 0 4px;
}

.lp-section-head__title {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #0C172C;
  margin: 0;
}

/* ── Persona Grid ───────────────────────────────────── */
.lp-persona-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}

.lp-persona-card {
  border-radius: 16px;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.07);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: box-shadow 0.15s;
}

.lp-persona-card:hover {
  box-shadow: 0 6px 24px rgba(200, 151, 58, 0.12);
  border-color: rgba(200, 151, 58, 0.25);
}

.lp-persona-card__top {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.lp-persona-card__avatar {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, #0C172C, #1a2d4f);
  color: #C8973A;
  font-size: 18px;
  font-weight: 800;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.lp-persona-card__info { flex: 1; min-width: 0; }

.lp-persona-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 4px;
}

.lp-tag {
  border-radius: 999px;
  padding: 2px 7px;
  background: rgba(200, 151, 58, 0.1);
  color: #C8973A;
  font-size: 10px;
  font-weight: 700;
  border: 1px solid rgba(200, 151, 58, 0.2);
}

.lp-persona-card__name {
  font-size: 15px;
  font-weight: 800;
  color: #0C172C;
  margin: 0 0 2px;
  letter-spacing: -0.01em;
}

.lp-persona-card__style {
  font-size: 11px;
  color: #888;
  margin: 0;
}

/* Metrics 2x2 */
.lp-persona-card__metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 10px;
  overflow: hidden;
}

.lp-metric {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 6px;
  background: #fafafa;
  gap: 2px;
}

.lp-metric__label {
  font-size: 10px;
  color: #888;
  font-weight: 600;
}

.lp-metric__val {
  font-size: 13px;
  font-weight: 800;
  color: #0C172C;
  font-variant-numeric: tabular-nums;
}

.lp-metric__val.is-up { color: #16a34a; }
.lp-metric__val.is-down { color: #dc2626; }

.lp-persona-card__objective {
  font-size: 12px;
  color: #555;
  line-height: 1.55;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.lp-persona-card__btns {
  display: flex;
  gap: 8px;
  margin-top: auto;
}

.lp-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;
  border: none;
}

.lp-btn svg { width: 14px; height: 14px; transition: transform 0.15s; }
.lp-btn:hover svg { transform: translateX(2px); }

.lp-btn--primary {
  background: #0C172C;
  color: #C8973A;
}

.lp-btn--primary:hover {
  background: #152238;
}

.lp-btn--secondary {
  background: transparent;
  color: #666;
  border: 1px solid rgba(0, 0, 0, 0.12);
}

.lp-btn--secondary:hover {
  background: #f5f5f5;
  color: #0C172C;
}

/* ── Footnote ───────────────────────────────────────── */
.lp-footnote {
  text-align: center;
  font-size: 12px;
  color: #aaa;
  margin-top: 24px;
  padding-bottom: 20px;
}

/* ── Responsive ─────────────────────────────────────── */
@media (max-width: 600px) {
  .lp-stats {
    grid-template-columns: repeat(2, 1fr);
  }

  .lp-hero__title {
    font-size: 18px;
  }

  .lp-persona-grid {
    grid-template-columns: 1fr;
  }

  .lp-entries-scroll {
    flex-direction: column;
    overflow-x: visible;
  }

  .lp-entry-card {
    flex: 0 0 auto;
  }
}
</style>
