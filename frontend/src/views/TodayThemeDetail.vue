<template>
  <div class="ttd-page">
    <header class="ttd-header">
      <button type="button" class="ttd-header__back" aria-label="返回" @click="$router.push('/')">
        <svg viewBox="0 0 24 24" fill="currentColor" class="ttd-icon"><path d="M15.41 7.41 14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>
      </button>
      <div class="ttd-header__meta">
        <h1 class="ttd-header__title">今日炒什么</h1>
        <p class="ttd-header__sub">最近 5 个交易日题材热榜</p>
      </div>
      <button type="button" class="ttd-header__refresh" :disabled="loading" @click="load(true)">
        刷新
      </button>
    </header>

    <main class="ttd-main">
      <section class="ttd-card ttd-summary">
        <div class="ttd-summary__hd">
          <svg viewBox="0 0 24 24" fill="currentColor" class="ttd-icon"><path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.1 0-2 .9-2 2v13c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 15H5V10h14v9z"/></svg>
          <span>{{ selectedDay?.date || '--' }}</span>
        </div>
        <p class="ttd-summary__text">{{ selectedSummary }}</p>
      </section>

      <section class="ttd-tabs" v-if="days.length">
        <button
          v-for="day in days"
          :key="day.date"
          type="button"
          class="ttd-tab"
          :class="{ 'ttd-tab--active': selectedDate === day.date }"
          @click="selectedDate = day.date"
        >
          {{ day.date.slice(5) }}
        </button>
      </section>

      <section v-if="loading" class="ttd-loading">
        <div v-for="i in 4" :key="i" class="ttd-skel" />
      </section>

      <section v-else-if="selectedThemes.length" class="ttd-list">
        <article
          v-for="item in selectedThemes"
          :key="`${selectedDate}-${item.rank}-${item.name}`"
          class="ttd-item"
        >
          <div class="ttd-item__rank" :class="rankClass(item.rank)">{{ item.rank }}</div>
          <div class="ttd-item__main">
            <div class="ttd-item__top">
              <div class="ttd-item__title-wrap">
                <h3 class="ttd-item__name">{{ item.name }}</h3>
              </div>
              <div class="ttd-item__metric">
                <span class="ttd-item__pct" :class="item.change >= 0 ? 'is-up' : 'is-down'">
                  {{ formatPct(item.change) }}
                </span>
                <span class="ttd-item__heat">{{ formatHeat(item.heat_value) }}热度值</span>
              </div>
            </div>

            <div class="ttd-item__chips">
              <span class="ttd-chip ttd-chip--limit">涨停家数 {{ item.limit_up_count }}</span>
              <span v-if="item.leader_name" class="ttd-chip ttd-chip--leader">
                {{ item.leader_name }} {{ formatPct(item.leader_change) }}
              </span>
            </div>

            <div class="ttd-item__bottom">
              <p class="ttd-item__summary">{{ item.summary || '当日题材热度集中，关注龙头与板块联动。' }}</p>
              <a
                v-if="item.detail_url"
                class="ttd-item__link"
                :href="item.detail_url"
                target="_blank"
                rel="noreferrer"
              >
                详情
              </a>
            </div>
          </div>
        </article>
      </section>

      <section v-else class="ttd-empty">
        <p class="ttd-empty__title">这一天暂无题材榜数据</p>
        <p class="ttd-empty__sub">可以切换其它交易日，或点击刷新重新拉取。</p>
      </section>

      <section v-if="error" class="ttd-error">
        <p>{{ error }}</p>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { todayThemeHistory } from '@/api/market.js'

const loading = ref(true)
const error = ref('')
const payload = ref(null)
const selectedDate = ref('')

const days = computed(() => Array.isArray(payload.value?.days) ? payload.value.days : [])
const selectedDay = computed(() => {
  if (!days.value.length) return null
  return days.value.find(day => day.date === selectedDate.value) || days.value[0]
})
const selectedThemes = computed(() => Array.isArray(selectedDay.value?.themes) ? selectedDay.value.themes : [])
const selectedSummary = computed(() => {
  const top = selectedThemes.value[0]
  if (top?.summary) return top.summary
  return '聚焦最近交易日最强题材方向，观察龙头表现与板块联动。'
})

async function load(force = false) {
  loading.value = true
  error.value = ''
  try {
    const data = await todayThemeHistory(5, force)
    payload.value = data
    if (!selectedDate.value && Array.isArray(data?.days) && data.days.length) {
      selectedDate.value = data.days[0].date
    }
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => load(false))

function formatPct(v) {
  const n = Number(v || 0)
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

function formatHeat(v) {
  const n = Number(v || 0)
  return `${n.toFixed(1)}万`
}

function rankClass(rank) {
  if (rank === 1) return 'is-top1'
  if (rank === 2) return 'is-top2'
  if (rank === 3) return 'is-top3'
  return 'is-normal'
}
</script>

<style scoped>
.ttd-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: #f7f8fa;
  color: #101318;
}

.ttd-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: calc(12px + env(safe-area-inset-top, 0)) 16px 12px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(14px);
  box-shadow: 0 1px 0 rgba(17, 24, 39, 0.06);
}

.ttd-header__back,
.ttd-header__refresh {
  border: none;
  background: transparent;
  color: #2962ff;
  font-weight: 700;
}

.ttd-header__back {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.ttd-header__meta {
  flex: 1;
  min-width: 0;
}

.ttd-header__title {
  margin: 0;
  font-size: 20px;
  font-weight: 800;
}

.ttd-header__sub {
  margin: 2px 0 0;
  font-size: 12px;
  color: #6b7280;
}

.ttd-main {
  padding: 14px 16px calc(24px + env(safe-area-inset-bottom, 0));
}

.ttd-card {
  background: #fff;
  border-radius: 20px;
  padding: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}

.ttd-summary {
  margin-bottom: 14px;
}

.ttd-summary__hd {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
  color: #4b5563;
  margin-bottom: 10px;
}

.ttd-summary__text {
  margin: 0;
  line-height: 1.6;
  font-size: 14px;
}

.ttd-tabs {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 6px;
  margin-bottom: 12px;
}

.ttd-tab {
  flex: 0 0 auto;
  border: 1px solid #dbe2ea;
  background: #fff;
  color: #6b7280;
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 700;
}

.ttd-tab--active {
  color: #2962ff;
  border-color: rgba(41, 98, 255, 0.3);
  background: rgba(41, 98, 255, 0.08);
}

.ttd-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ttd-item {
  display: flex;
  gap: 14px;
  padding: 16px;
  border-radius: 20px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
}

.ttd-item__rank {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  color: #fff;
  flex-shrink: 0;
}

.ttd-item__rank.is-top1 { background: #ff3154; }
.ttd-item__rank.is-top2 { background: #ff7a1a; }
.ttd-item__rank.is-top3 { background: #ffb020; }
.ttd-item__rank.is-normal { background: #c4c7cf; }

.ttd-item__main {
  flex: 1;
  min-width: 0;
}

.ttd-item__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.ttd-item__name {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  line-height: 1.25;
}

.ttd-item__metric {
  text-align: right;
  flex-shrink: 0;
}

.ttd-item__pct {
  display: block;
  font-size: 18px;
  font-weight: 800;
  line-height: 1.1;
}

.ttd-item__pct.is-up { color: #f23645; }
.ttd-item__pct.is-down { color: #089981; }

.ttd-item__heat {
  display: block;
  margin-top: 6px;
  color: #6b7280;
  font-size: 12px;
  font-weight: 700;
}

.ttd-item__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.ttd-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 8px;
  border: 1px solid rgba(15, 23, 42, 0.12);
  background: #fff;
  font-size: 12px;
  font-weight: 700;
}

.ttd-chip--limit {
  color: #f23645;
  border-color: rgba(242, 54, 69, 0.35);
}

.ttd-chip--leader {
  color: #4b5563;
}

.ttd-item__bottom {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-top: 10px;
}

.ttd-item__summary {
  margin: 0;
  color: #4b5563;
  line-height: 1.55;
  font-size: 14px;
}

.ttd-item__link {
  flex-shrink: 0;
  color: #2962ff;
  font-weight: 700;
  text-decoration: none;
}

.ttd-loading,
.ttd-empty,
.ttd-error {
  padding: 24px 8px;
}

.ttd-skel {
  height: 132px;
  border-radius: 20px;
  background: linear-gradient(90deg, #eef2f7 0%, #f6f8fb 50%, #eef2f7 100%);
  background-size: 200% 100%;
  animation: ttdShimmer 1.2s linear infinite;
}

.ttd-skel + .ttd-skel {
  margin-top: 12px;
}

.ttd-empty__title,
.ttd-error p {
  margin: 0 0 6px;
  font-weight: 700;
  color: #111827;
}

.ttd-empty__sub {
  margin: 0;
  color: #6b7280;
}

.ttd-icon {
  width: 22px;
  height: 22px;
}

@keyframes ttdShimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}
</style>
