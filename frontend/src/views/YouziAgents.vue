<template>
  <div class="yza-page">
    <!-- TopAppBar -->
    <header class="yza-topbar">
      <div class="yza-topbar__inner">
        <div class="yza-topbar__left">
          <button class="yza-topbar__back" aria-label="返回策略" @click="$router.push('/strategy')">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M15.41 7.41 14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>
          </button>
        </div>
        <h1 class="yza-topbar__title">策略全景</h1>
        <button class="yza-topbar__filter" aria-label="筛选">
          <span class="material-symbols-outlined">filter_list</span>
        </button>
      </div>
    </header>

    <!-- Main Content -->
    <main class="yza-main">

      <!-- Loading -->
      <div v-if="loading && !agentCards.length" class="yza-loading">
        <div class="yza-spinner" />
        <p>正在加载…</p>
      </div>

      <!-- Error -->
      <div v-else-if="errorMsg" class="yza-error">
        <p>{{ errorMsg }}</p>
        <button class="yza-retry-btn" type="button" @click="loadAgents">重试</button>
      </div>

      <template v-else>
        <!-- Hero Section -->
        <section class="yza-hero">
          <div class="yza-hero__glow yza-hero__glow--1" aria-hidden="true" />
          <div class="yza-hero__glow yza-hero__glow--2" aria-hidden="true" />
          <div class="yza-hero__content">
            <div class="yza-hero__badge">
              <span class="material-symbols-outlined">auto_awesome</span>
              <span>Premium System</span>
            </div>
            <h2 class="yza-hero__title">游资智能体架构</h2>
            <h3 class="yza-hero__subtitle">基于顶级游资思维深度构建的智能交易生态</h3>
            <p class="yza-hero__desc">
              聚合全网游资战法，实现从情绪感知到自动执行的闭环。每一位智能体都是战法精髓的数字生命。
            </p>
          </div>
          <div class="yza-hero__cta">
            <button class="yza-cta-btn" type="button" @click="$router.push('/strategy/youzi_agents/intro')">
              <span>了解更多</span>
              <span class="material-symbols-outlined">arrow_forward</span>
            </button>
          </div>
        </section>

        <!-- Feishu Push Management -->
        <article class="yza-feishu-card">
          <div class="yza-feishu-card__icon">
            <span class="material-symbols-outlined">notifications_active</span>
          </div>
          <div class="yza-feishu-card__body">
            <h2 class="yza-feishu-card__title">飞书推送管理</h2>
            <p class="yza-feishu-card__desc">实时掌握策略异动，全天候极速推送</p>
          </div>
          <button class="yza-feishu-card__btn" type="button" @click="$router.push('/strategy/youzi_agents/feishu')">
            配置管理
          </button>
        </article>

        <!-- Agent Cards -->
        <article
          v-for="agent in agentCards"
          :key="agent.id"
          class="yza-card"
        >
          <div class="yza-card__header">
            <h2 class="yza-card__name">{{ agent.name }}</h2>
            <div class="yza-card__tags">
              <span
                v-for="(tag, idx) in agent.displayTags"
                :key="tag"
                class="yza-tag"
                :class="idx % 2 === 0 ? 'yza-tag--primary' : 'yza-tag--tertiary'"
              >{{ tag }}</span>
            </div>
            <p class="yza-card__desc">{{ agent.description }}</p>
          </div>

          <div class="yza-card__metrics">
            <div class="yza-card__metric">
              <span class="yza-card__metric-label">胜率</span>
              <span class="yza-card__metric-val">{{ agent.winRate }}</span>
            </div>
            <div class="yza-card__metric yza-card__metric--right">
              <span class="yza-card__metric-label">累计收益</span>
              <span class="yza-card__metric-val" :class="agent.returnPctRaw >= 0 ? 'yza-card__metric-val--profit' : 'yza-card__metric-val--loss'">{{ agent.returnPct }}</span>
            </div>
            <div class="yza-card__metric">
              <span class="yza-card__metric-label">夏普比率</span>
              <span class="yza-card__metric-val">{{ agent.sharpe }}</span>
            </div>
            <div class="yza-card__metric yza-card__metric--right">
              <span class="yza-card__metric-label">最大回撤</span>
              <span class="yza-card__metric-val yza-card__metric-val--loss">{{ agent.maxDrawdown }}</span>
            </div>
          </div>

          <div class="yza-card__actions">
            <button class="yza-action-btn yza-action-btn--primary" type="button" @click="$router.push(`/strategy/youzi_agents/${agent.id}`)">
              <span class="material-symbols-outlined">account_balance_wallet</span>
              <span>查看持仓</span>
            </button>
            <button class="yza-action-btn yza-action-btn--secondary" type="button" @click="$router.push(`/strategy/youzi_agents/${agent.id}/analysis`)">
              <span class="material-symbols-outlined">insights</span>
              <span>查看分析</span>
            </button>
            <a class="yza-card__link" href="#" @click.prevent="$router.push(`/strategy/youzi_agents/${agent.id}/summary`)">
              <span>策略详情</span>
              <span class="material-symbols-outlined">chevron_right</span>
            </a>
          </div>
        </article>
      </template>

    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { fetchAgentArchitecture } from '@/api/agents.js'

const architecture = ref(null)
const agentPerf = ref({})
const loading = ref(false)
const errorMsg = ref('')

async function fetchAgentPerformance(ids) {
  if (!ids.length) return
  const nextPerf = {}
  await Promise.allSettled(
    ids.map(async (id) => {
      try {
        const res = await fetch(`/api/agents/${id}/performance`).then((r) => r.json())
        if (res.success && res.data) nextPerf[id] = res.data
      } catch {}
    })
  )
  agentPerf.value = nextPerf
}

async function loadAgents() {
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await fetchAgentArchitecture()
    architecture.value = data
    await fetchAgentPerformance((data?.personaAgents || []).map((a) => a.id))
  } catch (error) {
    errorMsg.value = error?.message || '无法加载游资智能体数据'
  } finally {
    loading.value = false
  }
}

// Static data for agents not yet in backend
const STATIC_AGENTS = {
  chenxiaoqun: {
    id: 'chenxiaoqun',
    name: '陈小群',
    tagline: '新生代游资典范，以情绪合力龙头战法为核心，专做主线龙头，擅长高位接力、分歧转一致和反核博弈',
    displayTags: ['情绪合力龙头', '高位接力', '反核博弈', '新生代游资代表'],
    winRate: '75.2%',
    returnPct: '+85.4%',
    returnPctRaw: 85.4,
    sharpe: '3.10',
    maxDrawdown: '-5.2%',
  },
  zhaolaoge: {
    id: 'zhaolaoge',
    name: '赵老哥',
    tagline: '主要手法为板上买，以首板和二板接力为主，精于捕捉主升浪，坚持"不创新高不做、不回踩不重仓"的铁律',
    displayTags: ['主升浪战法', '八年一万倍', '板上买', '新生代敢死队'],
    winRate: '45.8%',
    returnPct: '+315.6%',
    returnPctRaw: 315.6,
    sharpe: '1.45',
    maxDrawdown: '-35.6%',
  },
  zhangmengzhu: {
    id: 'zhangmengzhu',
    name: '章盟主',
    tagline: '从5万做到百亿体量的老牌游资，江湖人称"游资教父"，深耕A股30年。核心模式为涨停开路后缩量回踩20日线确认，专攻高确定性主升浪',
    displayTags: ['涨停开路+缩量回踩', '百亿体量', '游资教父', '主升浪专家'],
    winRate: '62.4%',
    returnPct: '+120.8%',
    returnPctRaw: 120.8,
    sharpe: '2.15',
    maxDrawdown: '-15.4%',
  },
  xiaoyueyu: {
    id: 'xiaoyueyu',
    name: '小鳄鱼',
    tagline: '90后新生代游资领军人物，以二板接力为核心战法，操盘手法灵活多样，市场好时追龙头、弱势时空仓或低吸，从万元起步四年过亿，风控意识极强',
    displayTags: ['二板接力', '超短狙击', '择时控仓', '九零后游资标杆'],
    winRate: '58.9%',
    returnPct: '+185.3%',
    returnPctRaw: 185.3,
    sharpe: '1.75',
    maxDrawdown: '-25.8%',
  },
}

const PHASE_MAP = {
  phase_1: '题材挖掘',
  phase_2: '信号生成',
  phase_3: '风控聚合',
}

const agentCards = computed(() => {
  // Build cards from API data
  const apiPersonas = architecture.value?.personaAgents || []
  const apiCards = apiPersonas.map((agent) => {
    const perf = agentPerf.value[agent.id] || {}
    const analysisCount = Number(perf.analysisCount || 0)
    const winRate = analysisCount > 0 ? Number(perf.winRate || 0) : 0
    const returnPctRaw = analysisCount > 0 ? Number(perf.returnPct || 0) : 0
    const maxDrawdown = analysisCount > 0 ? perf.maxDrawdown : null
    const sharpe = analysisCount > 0 && perf.sharpeRatio ? Number(perf.sharpeRatio) : null

    const winRateDisplay = analysisCount > 0 ? winRate.toFixed(1) + '%' : '—'
    const returnPctDisplay = analysisCount > 0
      ? (returnPctRaw >= 0 ? '+' : '') + returnPctRaw.toFixed(1) + '%'
      : '—'
    const maxDrawdownDisplay = maxDrawdown ? maxDrawdown + '%' : '—'
    const sharpeDisplay = sharpe != null ? sharpe.toFixed(2) : '—'

    const phaseTag = PHASE_MAP[agent.phase] || ''
    const styleTag = agent.styleCategory || agent.holdingStyle || ''
    const tagline = agent.tagline || agent.coreObjective || ''

    // Pick 2 display tags from available data
    const displayTags = [phaseTag, styleTag].filter(Boolean)

    return {
      id: agent.id,
      name: agent.name,
      description: tagline,
      displayTags,
      winRate: winRateDisplay,
      returnPct: returnPctDisplay,
      returnPctRaw,
      maxDrawdown: maxDrawdownDisplay,
      sharpe: sharpeDisplay,
    }
  })

  // Merge static agents (those not already in API response)
  const apiIds = new Set(apiCards.map((c) => c.id))
  const staticCards = Object.values(STATIC_AGENTS).filter((a) => !apiIds.has(a.id))

  return [...apiCards, ...staticCards]
})

onMounted(() => { loadAgents() })
</script>

<style scoped>
/* ── Page ───────────────────────────────────────────── */
.yza-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: #f7f9fb;
  padding-bottom: 40px;
}

/* ── TopAppBar ──────────────────────────────────────── */
.yza-topbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 50;
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(113, 119, 134, 0.18);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
}

.yza-topbar__inner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  max-width: 1440px;
  margin: 0 auto;
  padding: 16px 24px;
}

.yza-topbar__left { display: flex; align-items: center; width: 40px; }

.yza-topbar__back {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: transparent;
  color: #191c1e;
  border: none;
  cursor: pointer;
  transition: background 0.15s;
  flex-shrink: 0;
}

.yza-topbar__back:hover { background: rgba(25, 28, 30, 0.08); }
.yza-topbar__back svg { width: 20px; height: 20px; }

.yza-topbar__title {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: #191c1e;
  margin: 0;
  text-align: center;
  flex: 1;
}

.yza-topbar__filter {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: transparent;
  color: #0058bc;
  border: none;
  cursor: pointer;
  transition: background 0.2s;
}

.yza-topbar__filter:hover { background: rgba(0, 88, 188, 0.08); }
.yza-topbar__filter .material-symbols-outlined { font-size: 22px; }

/* ── Main ───────────────────────────────────────────── */
.yza-main {
  padding-top: 88px;
  padding-bottom: 100px;
  padding-left: 16px;
  padding-right: 16px;
  max-width: 1440px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* ── Loading ────────────────────────────────────────── */
.yza-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 80px 0;
  color: #888;
  font-size: 14px;
}

.yza-spinner {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 2px solid #e6e8ea;
  border-top-color: #0058bc;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ── Error ──────────────────────────────────────────── */
.yza-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 0;
  color: #ba1a1a;
  font-size: 14px;
}

.yza-retry-btn {
  padding: 8px 20px;
  border-radius: 999px;
  background: #0058bc;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  transition: background 0.2s;
}

.yza-retry-btn:hover { background: #004494; }

/* ── Hero ───────────────────────────────────────────── */
.yza-hero {
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 40%, #eff6ff 100%);
  border-radius: 24px;
  padding: 32px;
  box-shadow: 0 10px 40px -10px rgba(0, 0, 0, 0.05);
  border: 1px solid rgba(113, 119, 134, 0.12);
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.yza-hero__glow {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}

.yza-hero__glow--1 {
  width: 256px;
  height: 256px;
  top: -64px;
  right: -64px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.1), transparent 70%);
}

.yza-hero__glow--2 {
  width: 256px;
  height: 256px;
  bottom: -64px;
  left: -64px;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.1), transparent 70%);
}

.yza-hero__content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.yza-hero__badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  background: #191c1e;
  color: #f7f9fb;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  width: max-content;
}

.yza-hero__badge .material-symbols-outlined { font-size: 14px; }

.yza-hero__title {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  color: #191c1e;
  margin: 0;
}

.yza-hero__subtitle {
  font-size: 18px;
  font-weight: 500;
  color: #0058bc;
  margin: 0;
  line-height: 1.4;
}

.yza-hero__desc {
  font-size: 16px;
  line-height: 1.6;
  color: #414755;
  margin: 0;
  max-width: 640px;
}

.yza-hero__cta { position: relative; z-index: 1; }

.yza-cta-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 16px 24px;
  background: #191c1e;
  color: #f7f9fb;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.05em;
  border: none;
  cursor: pointer;
  transition: background 0.2s, transform 0.2s;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
}

.yza-cta-btn:hover { background: #2d3133; transform: translateY(-1px); }
.yza-cta-btn:active { transform: scale(0.97); }
.yza-cta-btn .material-symbols-outlined { font-size: 18px; }

/* ── Feishu Card ─────────────────────────────────────── */
.yza-feishu-card {
  background: #eceef0;
  border-radius: 24px;
  padding: 20px;
  box-shadow: none;
  border: 1px solid #c1c6d7;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.yza-feishu-card__icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #ffffff;
  color: #0058bc;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.yza-feishu-card__icon .material-symbols-outlined { font-size: 24px; }

.yza-feishu-card__body { flex: 1; min-width: 0; }

.yza-feishu-card__title {
  font-size: 18px;
  font-weight: 700;
  color: #191c1e;
  margin: 0 0 4px;
  line-height: 1.3;
}

.yza-feishu-card__desc {
  font-size: 13px;
  color: #414755;
  margin: 0;
  line-height: 1.4;
}

.yza-feishu-card__btn {
  flex-shrink: 0;
  padding: 10px 20px;
  background: #191c1e;
  color: #f7f9fb;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.02em;
  border: none;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}

.yza-feishu-card__btn:hover { background: #2d3133; }

/* ── Agent Card ──────────────────────────────────────── */
.yza-card {
  background: #ffffff;
  border-radius: 24px;
  padding: 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
  border: 1px solid #c1c6d7;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.yza-card__header {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.yza-card__name {
  font-size: 28px;
  font-weight: 700;
  color: #191c1e;
  margin: 0;
  letter-spacing: -0.01em;
}

.yza-card__tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.yza-tag {
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.03em;
}

.yza-tag--primary {
  background: rgba(0, 112, 235, 0.1);
  color: #0058bc;
}

.yza-tag--tertiary {
  background: rgba(70, 72, 212, 0.1);
  color: #4648d4;
}

.yza-card__desc {
  font-size: 14px;
  color: #414755;
  line-height: 1.5;
  margin: 0;
}

/* Metrics 2x2 grid */
.yza-card__metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  background: #f2f4f6;
  border-radius: 12px;
  padding: 16px;
}

.yza-card__metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.yza-card__metric--right { align-items: flex-end; }

.yza-card__metric-label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: #717786;
}

.yza-card__metric-val {
  font-size: 24px;
  font-weight: 600;
  color: #191c1e;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.yza-card__metric-val--profit { color: #e11d48; }
.yza-card__metric-val--loss { color: #16a34a; }

/* Actions */
.yza-card__actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.yza-action-btn {
  width: 100%;
  padding: 16px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.05em;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.yza-action-btn .material-symbols-outlined { font-size: 18px; }

.yza-action-btn--primary {
  background: #191c1e;
  color: #f2f4f6;
}

.yza-action-btn--primary:hover { background: #2d3133; }

.yza-action-btn--secondary {
  background: transparent;
  color: #191c1e;
  border: 1px solid #c1c6d7;
}

.yza-action-btn--secondary:hover { background: #f2f4f6; }

.yza-card__link {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 4px;
  font-size: 14px;
  color: #414755;
  text-decoration: none;
  cursor: pointer;
  transition: color 0.2s;
}

.yza-card__link:hover { color: #191c1e; }
.yza-card__link .material-symbols-outlined { font-size: 18px; }

/* ── Responsive ─────────────────────────────────────── */
@media (min-width: 768px) {
  .yza-main {
    padding-left: 32px;
    padding-right: 32px;
  }

  .yza-hero__title { font-size: 40px; }
  .yza-card__name { font-size: 32px; }
  .yza-card__metrics { gap: 24px; }
}

@media (max-width: 480px) {
  .yza-topbar__inner { padding: 12px 16px; }

  .yza-main {
    padding-top: 76px;
    padding-left: 12px;
    padding-right: 12px;
    gap: 16px;
  }

  .yza-hero { padding: 24px; gap: 16px; }
  .yza-hero__title { font-size: 26px; }
  .yza-hero__subtitle { font-size: 16px; }

  .yza-feishu-card {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
    padding: 16px;
  }

  .yza-feishu-card__btn { width: 100%; text-align: center; }

  .yza-card { padding: 20px; gap: 20px; }
  .yza-card__name { font-size: 24px; }
  .yza-card__metric-val { font-size: 20px; }
}
</style>
