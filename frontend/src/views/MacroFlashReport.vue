/**
 * MacroFlashReport — 宏观同步快讯（Editorial Intelligence 设计）
 * 路由: /strategy/macro
 * 数据来源: /api/macro/flash-report
 */
<template>
  <div class="mfr-page">
    <!-- TopAppBar -->
    <header class="mfr-header">
      <button type="button" class="mfr-header__back" aria-label="返回" @click="$router.push('/strategy')">
        <svg class="mfr-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <div class="mfr-header__brand">
        <div class="mfr-header__logo">
          <svg class="mfr-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M7 2v11h3v9l7-12h-4l4-8z"/></svg>
        </div>
        <div>
          <h1 class="mfr-header__title">Editorial Intelligence</h1>
          <span class="mfr-header__sub">宏观同步快讯</span>
        </div>
      </div>
      <div class="mfr-header__actions">
        <button type="button" class="mfr-header__icon-btn" :disabled="isRefreshing" @click="refresh">
          <svg class="mfr-icon" :class="{ 'mfr-spin': isRefreshing }" viewBox="0 0 24 24" fill="currentColor"><path d="M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
        </button>
      </div>
    </header>

    <main class="mfr-main">
      <!-- Loading skeleton -->
      <div v-if="isLoading" class="mfr-loading">
        <div class="mfr-loading__spinner" />
        <p class="mfr-loading__text">正在加载宏观数据…</p>
      </div>

      <template v-else-if="data">
        <!-- Header Section -->
        <section class="mfr-page-header">
          <div class="mfr-page-header__left">
            <span class="mfr-flash-badge">
              <span class="mfr-flash-dot" />
              Flash Update
            </span>
            <h2 class="mfr-page-header__title">{{ data.title }}</h2>
            <p class="mfr-page-header__desc">{{ data.subtitle }}</p>
          </div>
          <div class="mfr-sync-status">
            <span class="mfr-sync-dot" />
            <span class="mfr-sync-text">{{ data.syncStatus }}</span>
          </div>
        </section>

        <!-- Global & Domestic: Bento Grid -->
        <div class="mfr-bento">
          <!-- International Outlook -->
          <div class="mfr-card mfr-card--intl">
            <div class="mfr-card__deco" />
            <div class="mfr-card__body">
              <div class="mfr-card__section-title">
                <svg class="mfr-icon mfr-icon--sm" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
                <span>国际动态</span>
              </div>
              <div class="mfr-intl-grid">
                <div v-for="item in data.international" :key="item.label" class="mfr-intl-cell">
                  <p class="mfr-intl-cell__label">{{ item.label }}</p>
                  <div class="mfr-intl-cell__row">
                    <span class="mfr-intl-cell__val">{{ item.value }}</span>
                    <span class="mfr-intl-cell__chg" :class="chgClass(item.change)">{{ item.change }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Domestic Outlook -->
          <div class="mfr-card mfr-card--domestic">
            <div class="mfr-card__body">
              <div class="mfr-card__section-title mfr-card__section-title--light">
                <svg class="mfr-icon mfr-icon--sm" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z"/></svg>
                <span>国内宏观</span>
              </div>
              <div class="mfr-domestic-items">
                <div v-for="item in data.domestic" :key="item.label" class="mfr-domestic-item">
                  <div class="mfr-domestic-item__head">
                    <span class="mfr-domestic-item__label">{{ item.label }}</span>
                    <span class="mfr-domestic-item__val">{{ item.value }}</span>
                  </div>
                  <div class="mfr-domestic-item__bar">
                    <div class="mfr-domestic-item__fill" :style="{ width: item.pct + '%' }" />
                  </div>
                </div>
                <p class="mfr-domestic-quote">"{{ data.domesticQuote }}"</p>
              </div>
            </div>
          </div>
        </div>

        <!-- International Major Events -->
        <section class="mfr-section">
          <div class="mfr-section__head">
            <h3 class="mfr-section__title">
              <svg class="mfr-icon mfr-icon--sm" viewBox="0 0 24 24" fill="currentColor"><path d="M18 11v2h4v-2h-4zm-2 6.61c.96.71 2.21 1.65 3.2 2.39.4-.53.8-1.07 1.2-1.6-.99-.74-2.24-1.68-3.2-2.4-.4.54-.8 1.08-1.2 1.61zM20.4 5.6c-.4-.53-.8-1.07-1.2-1.6-.99.74-2.24 1.68-3.2 2.4.4.53.8 1.07 1.2 1.6.96-.72 2.21-1.65 3.2-2.4zM4 9c-1.1 0-2 .9-2 2v2c0 1.1.9 2 2 2h1v4h2v-4h1l5 3V6L8 9H4zm11.5 3c0-1.33-.58-2.53-1.5-3.35v6.69c.92-.81 1.5-2.01 1.5-3.34z"/></svg>
              国际大事件
            </h3>
            <span class="mfr-section__meta">实时突发更新</span>
          </div>
          <div class="mfr-events-list">
            <div
              v-for="(evt, i) in data.events"
              :key="i"
              class="mfr-event-item"
            >
              <div class="mfr-event-item__head">
                <h4 class="mfr-event-item__title">{{ evt.title }}</h4>
                <span class="mfr-event-item__time">{{ evt.time }}</span>
              </div>
              <p class="mfr-event-item__body">{{ evt.desc }}</p>
              <div class="mfr-event-item__tags">
                <span
                  v-for="(tag, j) in evt.tags"
                  :key="j"
                  class="mfr-tag"
                  :class="tag.cls"
                >
                  <span class="mfr-tag__dot" />
                  {{ tag.text }}
                </span>
              </div>
            </div>
          </div>
        </section>

        <!-- Expert Agent Evaluation -->
        <section class="mfr-section">
          <div class="mfr-section__head">
            <h3 class="mfr-section__title">
              <svg class="mfr-icon mfr-icon--sm" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zM7 17h10v-2H7v2zm3-6c.55 0 1-.45 1-1s-.45-1-1-1-1 .45-1 1 .45 1 1 1zm4 0c.55 0 1-.45 1-1s-.45-1-1-1-1 .45-1 1 .45 1 1 1zm-4 2h4v-1H10v1z"/></svg>
              专家智能体评估
            </h3>
            <span class="mfr-section__meta">基于 {{ data.agentModelCount }} 个模型深度研判</span>
          </div>
          <div class="mfr-agents-grid">
            <div
              v-for="(agent, i) in data.agents"
              :key="i"
              class="mfr-agent-card"
            >
              <div class="mfr-agent-card__head">
                <div class="mfr-agent-card__avatar" :class="'mfr-agent-card__avatar--' + agent.colorKey">
                  <span v-if="agent.avatarIcon" class="mfr-agent-card__icon material-symbols-outlined">{{ agent.avatarIcon }}</span>
                  <span v-else>{{ agent.avatarText }}</span>
                </div>
                <div class="mfr-agent-card__info">
                  <p class="mfr-agent-card__name">{{ agent.name }}</p>
                  <p class="mfr-agent-card__sub">{{ agent.sub }}</p>
                </div>
                <div class="mfr-agent-card__stance" :class="'mfr-agent-card__stance--' + agent.stanceKey">
                  {{ agent.stance }}
                </div>
              </div>
              <p class="mfr-agent-card__comment">{{ agent.comment }}</p>
            </div>
          </div>
        </section>

        <!-- Sector Forecasts & Consensus -->
        <section class="mfr-section">
          <h3 class="mfr-section__title">
            <svg class="mfr-icon mfr-icon--sm" viewBox="0 0 24 24" fill="currentColor"><path d="M11 2v20c-5.07-.5-9-4.79-9-10s3.93-9.5 9-10zm2.03 0v8.99H22c-.47-4.74-4.24-8.52-8.97-8.99zm0 11.01V22c4.74-.47 8.5-4.25 8.97-8.99h-8.97z"/></svg>
            板块预测与共识
          </h3>
          <div class="mfr-sectors-grid">
            <div
              v-for="(sector, i) in data.sectors"
              :key="i"
              class="mfr-sector-card"
            >
              <div class="mfr-sector-card__img-wrap">
                <img class="mfr-sector-card__img" :src="sector.img" :alt="sector.name" loading="lazy" />
              </div>
              <div class="mfr-sector-card__body">
                <div class="mfr-sector-card__title-row">
                  <h4 class="mfr-sector-card__name">{{ sector.name }}</h4>
                  <svg v-if="sector.trend === 'up'" class="mfr-icon mfr-icon--trend" viewBox="0 0 24 24" fill="currentColor"><path d="M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z"/></svg>
                  <svg v-else class="mfr-icon mfr-icon--trend-down" viewBox="0 0 24 24" fill="currentColor"><path d="M16 18l2.29-2.29-4.88-4.88-4 4L2 7.41 3.41 6l6 6 4-4 6.3 6.29L22 12v6z"/></svg>
                </div>
                <p class="mfr-sector-card__desc">{{ sector.desc }}</p>
                <div class="mfr-sector-card__chips">
                  <span v-for="(chip, j) in sector.chips" :key="j" class="mfr-sector-chip">{{ chip }}</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- System Synthesis -->
        <section class="mfr-synthesis">
          <div class="mfr-synthesis__deco">
            <span class="material-symbols-outlined mfr-synthesis__deco-icon">auto_awesome</span>
          </div>
          <div class="mfr-synthesis__body">
            <div class="mfr-synthesis__head">
              <div class="mfr-synthesis__head-icon">
                <svg class="mfr-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>
              </div>
              <h3 class="mfr-synthesis__title">综合建议</h3>
            </div>
            <div class="mfr-synthesis__cols">
              <div class="mfr-synthesis__col">
                <p class="mfr-synthesis__col-label">核心结论</p>
                <p class="mfr-synthesis__core">{{ data.synthesis.core }}</p>
              </div>
              <div class="mfr-synthesis__col">
                <p class="mfr-synthesis__col-label">操作指引</p>
                <ul class="mfr-synthesis__list">
                  <li v-for="(item, i) in data.synthesis.actions" :key="i" class="mfr-synthesis__list-item">
                    <span class="mfr-synthesis__list-dot" />
                    {{ item }}
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>
      </template>

      <!-- Error / Empty state -->
      <div v-if="!isLoading && !data && !error" class="mfr-empty">
        <svg class="mfr-icon mfr-empty__ico" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>
        <p class="mfr-empty__title">暂无宏观数据</p>
        <p class="mfr-empty__sub">请检查网络连接后重试</p>
      </div>

      <div v-if="error" class="mfr-error">
        <p>{{ error }}</p>
        <button class="mfr-btn-text" @click="refresh">重试</button>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { macroFlashReport } from '@/api/market.js'

const isLoading = ref(true)
const isRefreshing = ref(false)
const error = ref('')
const rawData = ref(null)

async function load() {
  try {
    const result = await macroFlashReport()
    rawData.value = result
    error.value = ''
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    isLoading.value = false
    isRefreshing.value = false
  }
}

async function refresh() {
  if (isRefreshing.value) return
  isRefreshing.value = true
  await load()
}

onMounted(load)

const data = computed(() => rawData.value)

function chgClass(change) {
  if (!change) return 'mfr-chg--flat'
  if (change.startsWith('+') || change.includes('↑')) return 'mfr-chg--up'
  if (change.startsWith('-')) return 'mfr-chg--down'
  return 'mfr-chg--flat'
}
</script>

<style scoped>
/* ── Design Tokens ─────────────────────────────────────────────── */
.mfr-page {
  --primary: #4648d4;
  --primary-container: #6063ee;
  --surface: #f7f9fb;
  --surface-container-low: #f2f4f6;
  --surface-container: #eceef0;
  --surface-container-high: #e0e3e5;
  --surface-container-lowest: #ffffff;
  --on-surface: #191c1e;
  --on-surface-variant: #464554;
  --on-primary: #ffffff;
  --tertiary: #006c49;
  --tertiary-container: #00885d;
  --on-tertiary-fixed: #002113;
  --error: #ba1a1a;
  --error-container: #ffdad6;
  --on-error-container: #93000a;
  --outline-variant: #c7c4d7;
  --secondary: #505f76;
  --secondary-container: #d0e1fb;
  --on-secondary-fixed: #0b1c30;

  font-family: 'Inter', system-ui, sans-serif;
  background: var(--surface);
  color: var(--on-surface);
  min-height: 100vh;
  min-height: 100dvh;
  padding-bottom: env(safe-area-inset-bottom, 0);
}

/* ── Header ─────────────────────────────────────────────────────── */
.mfr-header {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: calc(12px + env(safe-area-inset-top, 0)) 16px 12px;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  box-shadow: 0 1px 0 rgba(193, 198, 215, 0.12);
}

.mfr-header__back {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s;
}
.mfr-header__back:active { background: rgba(70, 72, 212, 0.08); }
.mfr-header__back .mfr-icon { fill: var(--primary); }

.mfr-header__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.mfr-header__logo {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--primary), var(--primary-container));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--on-primary);
  flex-shrink: 0;
}

.mfr-header__title {
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 15px;
  color: var(--on-surface);
  margin: 0;
  line-height: 1.2;
}

.mfr-header__sub {
  font-size: 11px;
  color: var(--on-surface-variant);
  display: block;
  line-height: 1.2;
}

.mfr-header__actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.mfr-header__icon-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--on-surface-variant);
  cursor: pointer;
  transition: background 0.15s;
}
.mfr-header__icon-btn:active { background: rgba(0,0,0,0.05); }
.mfr-header__icon-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.mfr-header__icon-btn .mfr-icon { fill: var(--on-surface-variant); }

/* ── Main ───────────────────────────────────────────────────────── */
.mfr-main {
  max-width: 720px;
  margin: 0 auto;
  padding: 0 16px 32px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* ── Icons ──────────────────────────────────────────────────────── */
.mfr-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}
.mfr-icon--sm {
  width: 16px;
  height: 16px;
}
.mfr-icon--trend { fill: var(--tertiary-container); }
.mfr-icon--trend-down { fill: var(--error); }

.mfr-spin {
  animation: mfr-rotate 1s linear infinite;
}
@keyframes mfr-rotate {
  to { transform: rotate(360deg); }
}

/* ── Loading ───────────────────────────────────────────────────── */
.mfr-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 80px 0;
}
.mfr-loading__spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--surface-container);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: mfr-rotate 0.8s linear infinite;
}
.mfr-loading__text {
  font-size: 14px;
  color: var(--on-surface-variant);
  margin: 0;
}

/* ── Page Header ───────────────────────────────────────────────── */
.mfr-page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  padding-top: 24px;
}

.mfr-page-header__left { flex: 1; min-width: 0; }

.mfr-flash-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(70, 72, 212, 0.1);
  color: var(--primary);
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.mfr-flash-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary);
  animation: mfr-pulse 1.8s ease-in-out infinite;
}
@keyframes mfr-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.75); }
}

.mfr-page-header__title {
  font-family: 'Manrope', sans-serif;
  font-weight: 800;
  font-size: 26px;
  letter-spacing: -0.02em;
  color: var(--on-surface);
  margin: 0 0 4px;
  line-height: 1.2;
}

.mfr-page-header__desc {
  font-size: 13px;
  color: var(--on-surface-variant);
  margin: 0;
  line-height: 1.5;
}

.mfr-sync-status {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--surface-container-lowest);
  padding: 8px 14px;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(70, 72, 212, 0.06);
  flex-shrink: 0;
}

.mfr-sync-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--tertiary-container);
  animation: mfr-pulse 1.8s ease-in-out infinite;
}

.mfr-sync-text {
  font-size: 11px;
  font-weight: 600;
  color: var(--on-surface-variant);
  white-space: nowrap;
}

/* ── Bento Grid ─────────────────────────────────────────────────── */
.mfr-bento {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media (max-width: 520px) {
  .mfr-bento { grid-template-columns: 1fr; }
}

/* ── Cards ──────────────────────────────────────────────────────── */
.mfr-card {
  background: var(--surface-container-lowest);
  border-radius: 20px;
  padding: 20px;
  position: relative;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(70, 72, 212, 0.06);
}

.mfr-card--intl .mfr-card__deco {
  position: absolute;
  top: -24px;
  right: -24px;
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: rgba(70, 72, 212, 0.06);
  transition: transform 0.3s;
}
.mfr-card--intl:hover .mfr-card__deco { transform: scale(1.15); }

.mfr-card--domestic {
  background: linear-gradient(145deg, var(--primary), var(--primary-container));
  box-shadow: 0 8px 24px rgba(70, 72, 212, 0.15);
}

.mfr-card__body { position: relative; z-index: 1; }

.mfr-card__section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 16px;
  color: var(--on-surface);
  margin-bottom: 16px;
}
.mfr-card__section-title .mfr-icon { fill: var(--primary); }
.mfr-card__section-title--light { color: var(--on-primary); }
.mfr-card__section-title--light .mfr-icon { fill: var(--on-primary); }

/* International grid */
.mfr-intl-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.mfr-intl-cell {
  background: var(--surface-container-low);
  border-radius: 12px;
  padding: 12px;
}

.mfr-intl-cell__label {
  font-size: 11px;
  color: var(--on-surface-variant);
  font-weight: 500;
  margin: 0 0 6px;
}

.mfr-intl-cell__row {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.mfr-intl-cell__val {
  font-family: 'Manrope', sans-serif;
  font-weight: 800;
  font-size: 18px;
  color: var(--on-surface);
  line-height: 1;
}

.mfr-intl-cell__chg {
  font-size: 11px;
  font-weight: 700;
}
.mfr-chg--up { color: var(--error); }
.mfr-chg--down { color: var(--tertiary-container); }
.mfr-chg--flat { color: var(--on-surface-variant); }

/* Domestic */
.mfr-domestic-items { display: flex; flex-direction: column; gap: 14px; }

.mfr-domestic-item__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.mfr-domestic-item__label {
  font-size: 13px;
  color: rgba(255,255,255,0.75);
}
.mfr-domestic-item__val {
  font-family: 'Manrope', sans-serif;
  font-weight: 800;
  font-size: 16px;
  color: var(--on-primary);
}

.mfr-domestic-item__bar {
  width: 100%;
  height: 4px;
  background: rgba(255,255,255,0.2);
  border-radius: 99px;
  overflow: hidden;
}
.mfr-domestic-item__fill {
  height: 100%;
  background: var(--on-primary);
  border-radius: 99px;
  transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
}

.mfr-domestic-quote {
  font-size: 11px;
  color: rgba(255,255,255,0.6);
  line-height: 1.6;
  font-style: italic;
  margin: 8px 0 0;
  border-top: 1px solid rgba(255,255,255,0.1);
  padding-top: 12px;
}

/* ── Section ───────────────────────────────────────────────────── */
.mfr-section { display: flex; flex-direction: column; gap: 16px; }

.mfr-section__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.mfr-section__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 18px;
  color: var(--on-surface);
  margin: 0;
}
.mfr-section__title .mfr-icon { fill: var(--primary); }

.mfr-section__meta {
  font-size: 11px;
  color: var(--on-surface-variant);
  font-weight: 500;
}

/* ── Events ─────────────────────────────────────────────────────── */
.mfr-events-list {
  background: var(--surface-container-lowest);
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(70, 72, 212, 0.04);
}

.mfr-event-item {
  padding: 18px 20px;
  transition: background 0.15s;
  cursor: pointer;
}
.mfr-event-item:hover { background: var(--surface-container-low); }
.mfr-event-item + .mfr-event-item {
  border-top: 1px solid transparent;
}

.mfr-event-item__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 6px;
}

.mfr-event-item__title {
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 14px;
  color: var(--on-surface);
  margin: 0;
  line-height: 1.4;
}

.mfr-event-item__time {
  font-size: 10px;
  color: var(--on-surface-variant);
  background: var(--surface-container-high);
  padding: 2px 8px;
  border-radius: 8px;
  white-space: nowrap;
  flex-shrink: 0;
  margin-top: 2px;
}

.mfr-event-item__body {
  font-size: 12px;
  color: var(--on-surface-variant);
  line-height: 1.6;
  margin: 0 0 10px;
}

.mfr-event-item__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.mfr-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 8px;
}
.mfr-tag__dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
}
.mfr-tag--bearish {
  background: rgba(242, 54, 69, 0.1);
  color: var(--error);
}
.mfr-tag--bearish .mfr-tag__dot { background: var(--error); }
.mfr-tag--bullish {
  background: rgba(0, 136, 93, 0.1);
  color: var(--tertiary-container);
}
.mfr-tag--bullish .mfr-tag__dot { background: var(--tertiary-container); }
.mfr-tag--neutral {
  background: var(--secondary-container);
  color: var(--secondary);
}
.mfr-tag--neutral .mfr-tag__dot { background: var(--secondary); }

/* ── Agent Cards ───────────────────────────────────────────────── */
.mfr-agents-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}
@media (max-width: 520px) {
  .mfr-agents-grid { grid-template-columns: 1fr; }
}

.mfr-agent-card {
  background: var(--surface-container-low);
  border-radius: 16px;
  padding: 16px;
  border: 1.5px solid transparent;
  transition: border-color 0.25s, box-shadow 0.25s;
}
.mfr-agent-card:hover {
  border-color: rgba(70, 72, 212, 0.18);
  box-shadow: 0 4px 16px rgba(70, 72, 212, 0.08);
}

.mfr-agent-card__head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.mfr-agent-card__avatar {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 15px;
  flex-shrink: 0;
}
.mfr-agent-card__avatar--primary { background: rgba(70, 72, 212, 0.15); color: var(--primary); }
.mfr-agent-card__avatar--secondary { background: var(--secondary-container); color: var(--secondary); }
.mfr-agent-card__avatar--error { background: var(--error-container); color: var(--error); }
.mfr-agent-card__avatar--tertiary { background: rgba(0, 136, 93, 0.12); color: var(--tertiary-container); }
.mfr-agent-card__avatar .mfr-agent-card__icon {
  font-size: 18px;
  width: 18px;
  height: 18px;
}

.mfr-agent-card__info { flex: 1; min-width: 0; }
.mfr-agent-card__name {
  font-weight: 700;
  font-size: 13px;
  color: var(--on-surface);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mfr-agent-card__sub {
  font-size: 10px;
  color: var(--on-surface-variant);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mfr-agent-card__stance {
  font-size: 10px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 8px;
  white-space: nowrap;
}
.mfr-agent-card__stance--bullish { background: rgba(0, 136, 93, 0.12); color: var(--tertiary-container); }
.mfr-agent-card__stance--bearish { background: var(--error-container); color: var(--on-error-container); }
.mfr-agent-card__stance--neutral { background: var(--surface-container-high); color: var(--on-surface-variant); }

.mfr-agent-card__comment {
  font-size: 11px;
  color: var(--on-surface-variant);
  line-height: 1.6;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── Sector Cards ──────────────────────────────────────────────── */
.mfr-sectors-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}
@media (max-width: 520px) {
  .mfr-sectors-grid { grid-template-columns: 1fr; }
}

.mfr-sector-card {
  background: var(--surface-container-lowest);
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  box-shadow: 0 2px 12px rgba(70, 72, 212, 0.05);
}

.mfr-sector-card__img-wrap {
  width: 80px;
  flex-shrink: 0;
  overflow: hidden;
}
.mfr-sector-card__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.mfr-sector-card__body {
  padding: 14px;
  flex: 1;
  min-width: 0;
}

.mfr-sector-card__title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 6px;
}
.mfr-sector-card__name {
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 14px;
  color: var(--on-surface);
  margin: 0;
  line-height: 1.3;
}

.mfr-sector-card__desc {
  font-size: 11px;
  color: var(--on-surface-variant);
  line-height: 1.5;
  margin: 0 0 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mfr-sector-card__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.mfr-sector-chip {
  font-size: 10px;
  background: var(--surface-container-low);
  color: var(--on-surface-variant);
  padding: 2px 6px;
  border-radius: 6px;
  font-weight: 500;
}

/* ── Synthesis ──────────────────────────────────────────────────── */
.mfr-synthesis {
  background: rgba(70, 72, 212, 0.06);
  border-radius: 20px;
  padding: 28px;
  position: relative;
  overflow: hidden;
}

.mfr-synthesis__deco {
  position: absolute;
  bottom: -20px;
  right: -10px;
  opacity: 0.06;
}
.mfr-synthesis__deco-icon {
  font-size: 160px;
  color: var(--primary);
  font-variation-settings: 'FILL' 0;
}

.mfr-synthesis__body { position: relative; z-index: 1; }

.mfr-synthesis__head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.mfr-synthesis__head-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--on-primary);
}
.mfr-synthesis__head-icon .mfr-icon { fill: var(--on-primary); width: 22px; height: 22px; }

.mfr-synthesis__title {
  font-family: 'Manrope', sans-serif;
  font-weight: 800;
  font-size: 20px;
  color: var(--on-surface);
  margin: 0;
}

.mfr-synthesis__cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}
@media (max-width: 520px) {
  .mfr-synthesis__cols { grid-template-columns: 1fr; gap: 20px; }
}

.mfr-synthesis__col-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--primary);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin: 0 0 10px;
}

.mfr-synthesis__core {
  font-size: 14px;
  font-weight: 500;
  color: var(--on-surface);
  line-height: 1.7;
  margin: 0;
}

.mfr-synthesis__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mfr-synthesis__list-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 13px;
  color: var(--on-surface);
  line-height: 1.5;
}

.mfr-synthesis__list-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary);
  flex-shrink: 0;
  margin-top: 6px;
}

/* ── Empty / Error ─────────────────────────────────────────────── */
.mfr-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 80px 0;
}
.mfr-empty__ico { width: 48px; height: 48px; color: var(--outline-variant); }
.mfr-empty__title {
  font-family: 'Manrope', sans-serif;
  font-weight: 700;
  font-size: 18px;
  color: var(--on-surface);
  margin: 0;
}
.mfr-empty__sub {
  font-size: 13px;
  color: var(--on-surface-variant);
  margin: 0;
}

.mfr-error {
  text-align: center;
  padding: 40px 0;
  color: var(--on-error-container);
  background: var(--error-container);
  border-radius: 16px;
  padding: 20px;
}

.mfr-btn-text {
  background: none;
  border: none;
  color: var(--primary);
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  margin-top: 8px;
  text-decoration: underline;
}
</style>
