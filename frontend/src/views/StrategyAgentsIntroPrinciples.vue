<template>
  <div class="principles-page">
    <!-- Header -->
    <header class="principles-top">
      <button type="button" class="principles-top__back" aria-label="返回" @click="$router.push(introBase)">
        <svg viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <div class="principles-top__brand">
        <div class="principles-top__avatar">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9v1zm3-19C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7z"/></svg>
        </div>
        <div>
          <p class="principles-top__eyebrow">SYSTEM PRINCIPLES</p>
          <h1 class="principles-top__title">设计原则</h1>
        </div>
      </div>
    </header>

    <!-- Loading -->
    <div v-if="loading" class="principles-loading">
      <div class="principles-spinner" />
      <p>正在加载…</p>
    </div>

    <!-- Error -->
    <div v-else-if="errorMsg" class="principles-error">
      <strong>加载失败：</strong>{{ errorMsg }}
    </div>

    <!-- Content -->
    <main v-else-if="architecture" class="principles-main">

      <!-- Hero -->
      <section class="principles-hero">
        <div class="principles-hero__mesh" />
        <div class="principles-hero__content">
          <p class="principles-hero__kicker">DESIGN PHILOSOPHY</p>
          <h2 class="principles-hero__title">游资智能体架构台设计原则</h2>
          <p class="principles-hero__subtitle">v{{ architecture.version || '2.0' }}</p>
          <p class="principles-hero__desc">
            这些原则定义了游资智能体架构台的设计哲学，是整套系统从分层结构到人格打法的底层依据。
            每一项原则都对应着对传统 AI 选股工具的反思与超越。
          </p>
        </div>
        <div class="principles-hero__count">
          <span class="principles-hero__count-num">{{ architecture.principles?.length || 0 }}</span>
          <span class="principles-hero__count-label">项设计原则</span>
        </div>
      </section>

      <!-- Principles Grid -->
      <section class="principles-section">
        <div class="principles-grid">
          <article
            v-for="(principle, index) in architecture.principles || []"
            :key="index"
            class="principle-card"
            :style="{ '--card-index': index }"
          >
            <div class="principle-card__num">{{ String(index + 1).padStart(2, '0') }}</div>
            <div class="principle-card__body">
              <p class="principle-card__text">{{ principle }}</p>
            </div>
          </article>
        </div>
      </section>

      <!-- Footer -->
      <div class="principles-footer">
        <button type="button" class="principles-footer__back" @click="$router.push(introBase)">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
          返回系统介绍
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
const introBase = computed(() =>
  route.path.startsWith('/strategy/youzi_agents') ? '/strategy/youzi_agents/intro' : '/strategy/agents/intro'
)

const architecture = ref(null)
const loading = ref(false)
const errorMsg = ref('')

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

onMounted(() => { loadArchitecture() })
</script>

<style scoped>
/* ── Page ───────────────────────────────────────────── */
.principles-page {
  min-height: 100vh;
  min-height: 100dvh;
  background:
    radial-gradient(circle at top right, rgba(198, 151, 52, 0.16), transparent 32%),
    linear-gradient(180deg, #FBFAF5 0%, #F2EFE7 36%, #ECE8DE 100%);
  color: #152033;
  padding-bottom: 48px;
}

/* ── Header ─────────────────────────────────────────── */
.principles-top {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  backdrop-filter: blur(18px);
  background: rgba(248, 244, 234, 0.84);
  border-bottom: 1px solid rgba(84, 68, 38, 0.08);
}

.principles-top__back {
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

.principles-top__back:hover { background: rgba(255, 255, 255, 0.92); }
.principles-top__back svg { width: 20px; height: 20px; color: #C8973A; }

.principles-top__brand {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.principles-top__avatar {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #0C172C, #1a2d4f);
  color: #C8973A;
  box-shadow: 0 16px 36px rgba(12, 23, 44, 0.18);
  flex-shrink: 0;
}

.principles-top__avatar svg { width: 22px; height: 22px; }

.principles-top__eyebrow {
  font-size: 10px;
  letter-spacing: 0.18em;
  color: #C8973A;
  text-transform: uppercase;
  margin: 0;
}

.principles-top__title {
  font-size: 20px;
  line-height: 1.1;
  font-weight: 800;
  letter-spacing: -0.03em;
  margin: 0;
  color: #0C172C;
}

/* ── Loading / Error ───────────────────────────────── */
.principles-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px;
  color: #68778c;
  font-size: 14px;
}

.principles-spinner {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid rgba(198, 151, 52, 0.14);
  border-top-color: #C8973A;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.principles-error {
  margin: 20px 18px;
  padding: 18px 20px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid rgba(21, 32, 51, 0.08);
  color: #b42318;
}

/* ── Main ───────────────────────────────────────────── */
.principles-main {
  width: min(900px, calc(100% - 32px));
  margin: 0 auto;
  padding: 28px 0 0;
}

/* ── Hero ───────────────────────────────────────────── */
.principles-hero {
  position: relative;
  overflow: hidden;
  border-radius: 28px;
  padding: 32px;
  background:
    linear-gradient(135deg, rgba(22, 27, 60, 0.98) 0%, rgba(35, 42, 100, 0.96) 58%, rgba(198, 151, 52, 0.92) 100%);
  color: #fff;
  box-shadow: 0 32px 72px rgba(22, 27, 60, 0.2);
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.principles-hero__mesh {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 18% 18%, rgba(198, 151, 52, 0.25), transparent 24%),
    radial-gradient(circle at 82% 26%, rgba(244, 239, 226, 0.08), transparent 28%),
    linear-gradient(120deg, transparent 0%, rgba(255, 255, 255, 0.04) 45%, transparent 100%);
  pointer-events: none;
}

.principles-hero__content {
  position: relative;
  z-index: 1;
  flex: 1;
}

.principles-hero__kicker {
  color: #C8973A;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin: 0;
}

.principles-hero__title {
  margin: 8px 0 4px;
  font-size: clamp(22px, 4vw, 36px);
  line-height: 1.1;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: #fff;
}

.principles-hero__subtitle {
  font-size: 14px;
  color: rgba(244, 239, 226, 0.6);
  margin: 0 0 12px;
}

.principles-hero__desc {
  max-width: 600px;
  font-size: 15px;
  line-height: 1.8;
  color: rgba(244, 239, 226, 0.82);
  margin: 0;
}

.principles-hero__count {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(244, 239, 226, 0.08);
  flex-shrink: 0;
  text-align: center;
}

.principles-hero__count-num {
  font-size: 48px;
  font-weight: 800;
  letter-spacing: -0.06em;
  color: #C8973A;
  line-height: 1;
}

.principles-hero__count-label {
  font-size: 13px;
  color: rgba(244, 239, 226, 0.7);
  margin-top: 6px;
}

/* ── Section ───────────────────────────────────────── */
.principles-section {
  margin-top: 28px;
}

/* ── Grid ──────────────────────────────────────────── */
.principles-grid {
  display: grid;
  gap: 14px;
}

.principle-card {
  display: flex;
  gap: 18px;
  padding: 22px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(21, 32, 51, 0.08);
  box-shadow: 0 12px 32px rgba(21, 32, 51, 0.06);
  transition: all 0.2s;
  align-items: center;
}

.principle-card:hover {
  box-shadow: 0 16px 40px rgba(198, 151, 52, 0.1);
  border-color: rgba(198, 151, 52, 0.2);
  transform: translateY(-1px);
}

.principle-card__num {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(135deg, #0C172C, #1a2d4f);
  color: #C8973A;
  font-size: 16px;
  font-weight: 800;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.principle-card__body {
  flex: 1;
}

.principle-card__text {
  font-size: 16px;
  line-height: 1.8;
  color: #0C172C;
  margin: 0;
}

/* ── Footer ────────────────────────────────────────── */
.principles-footer {
  margin-top: 32px;
  display: flex;
  justify-content: center;
}

.principles-footer__back {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  border-radius: 999px;
  border: 1.5px solid rgba(198, 151, 52, 0.2);
  background: #fff;
  color: #C8973A;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.principles-footer__back svg { width: 18px; height: 18px; }

.principles-footer__back:hover {
  border-color: #C8973A;
  color: #9e7630;
}

/* ── Responsive ─────────────────────────────────────── */
@media (max-width: 767px) {
  .principles-main {
    width: min(100%, calc(100% - 20px));
    padding-top: 18px;
  }

  .principles-top {
    padding: 14px 12px;
  }

  .principles-hero {
    flex-direction: column;
    padding: 22px 18px;
    border-radius: 24px;
  }

  .principles-hero__count {
    align-self: flex-start;
    flex-direction: row;
    gap: 8px;
    padding: 14px 18px;
  }

  .principles-hero__count-num {
    font-size: 32px;
  }

  .principles-grid {
    gap: 10px;
  }

  .principle-card {
    flex-direction: column;
    gap: 14px;
    padding: 18px;
    border-radius: 18px;
  }
}
</style>
