<template>
  <div>
    <nav class="navbar">
      <div class="logo">
        <svg class="icon" style="fill:#FF9500"><use href="#icon-ths"/></svg>
        板块
      </div>
      <div class="update-time">{{ updateTimeStr }}</div>
    </nav>

    <!-- 顶部分段 -->
    <div class="ths-tabs">
      <div class="ths-tab" @click="$router.push('/')">大盘</div>
      <div class="ths-tab active">板块</div>
      <div class="ths-tab" @click="$router.push('/strategy')">个股</div>
      <div class="ths-tab-underline"></div>
    </div>

    <div class="container">
      <!-- 板块统计 6 宫格 -->
      <div class="stat2-grid">
        <div class="stat2-card">
          <div class="stat2-label">上涨</div>
          <div class="stat2-value up">{{ stats.up }}</div>
        </div>
        <div class="stat2-card">
          <div class="stat2-label">下跌</div>
          <div class="stat2-value down">{{ stats.down }}</div>
        </div>
        <div class="stat2-card">
          <div class="stat2-label">涨停</div>
          <div class="stat2-value up">{{ stats.limitUp }}</div>
        </div>
        <div class="stat2-card">
          <div class="stat2-label">跌停</div>
          <div class="stat2-value down">{{ stats.limitDown }}</div>
        </div>
        <div class="stat2-card">
          <div class="stat2-label">成交额</div>
          <div class="stat2-value orange">{{ stats.amount }}</div>
        </div>
        <div class="stat2-card">
          <div class="stat2-label">炸板</div>
          <div class="stat2-value down">0</div>
        </div>
      </div>

      <!-- 热门板块列表 -->
      <div class="sector-section">
        <div class="section-title">
          <svg style="width:18px;height:18px;fill:#FF9500"><use href="#icon-fire"/></svg>
          热门板块
        </div>

        <div v-if="loading" class="loading">
          <div class="spinner"></div>
          <div>加载中...</div>
        </div>
        <div v-else-if="sectors.length === 0" class="empty">暂无板块数据</div>
        <div v-else class="sector-list">
          <div v-for="(s, i) in sectors" :key="s.name" class="sector-item">
            <span class="sector-rank" :class="i < 3 ? 'rank-' + (i+1) : 'rank-other'">{{ i + 1 }}</span>
            <div class="sector-info">
              <div class="sector-name">{{ s.name }}</div>
              <div class="sector-sub">{{ s.leader ? '领涨: ' + s.leader : '' }}</div>
            </div>
            <div class="sector-change" :class="s.change >= 0 ? 'up' : 'down'">
              {{ s.change >= 0 ? '+' : '' }}{{ (s.change || 0).toFixed(2) }}%
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { market } from '@/api/market.js'

const overview = ref([])
const sectors = ref([])
const loading = ref(true)
const updateTimeStr = ref('--:--')

const stats = computed(() => {
  let up = 0, down = 0, limitUp = 0, limitDown = 0
  sectors.value.forEach(s => {
    if (s.change > 0) up++
    else if (s.change < 0) down++
    if (s.change >= 9.9) limitUp++
    if (s.change <= -9.9) limitDown++
  })
  const sh = overview.value.find(i => i.name === '上证指数') || {}
  const amt = sh.amount || 0
  let amountStr = ''
  if (Math.abs(amt) >= 100000000) amountStr = (amt / 100000000).toFixed(2) + '亿'
  else if (Math.abs(amt) >= 10000) amountStr = (amt / 10000).toFixed(0) + '万'
  else amountStr = amt.toFixed(0)
  return { up, down, limitUp, limitDown, amount: amountStr }
})

async function loadData() {
  try {
    const [ov, sc] = await Promise.all([
      market.overview(),
      market.sectors(),
    ])
    overview.value = Array.isArray(ov) ? ov : []
    sectors.value = Array.isArray(sc) ? sc : []
    updateTimeStr.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

let timer = null
onMounted(() => {
  loadData()
  timer = setInterval(loadData, 300000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.navbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(255,255,255,0.78);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  padding: 10px 16px;
  padding-top: calc(10px + env(safe-area-inset-top));
  display: flex; justify-content: space-between; align-items: center;
}
.logo { font-size: 17px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.logo .icon { fill: #FF9500; }
.update-time { font-size: 13px; color: var(--apple-gray); }

.ths-tabs {
  display: flex;
  justify-content: space-around;
  align-items: center;
  background: #fff;
  padding: 10px 10px 0;
  position: sticky;
  top: 52px;
  z-index: 99;
  border-bottom: 1px solid var(--apple-gray5);
}
.ths-tab {
  font-size: 16px; font-weight: 600; color: var(--apple-text3);
  padding: 10px 6px 12px; cursor: pointer;
}
.ths-tab.active { color: var(--apple-text); }
.ths-tab-underline {
  position: absolute;
  height: 3px; width: 36px;
  background: #FF3B30; border-radius: 2px;
  bottom: 0; left: calc(50% - 18px);
}

.container { padding: 12px 0 20px; }

.stat2-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  background: var(--apple-gray5);
  margin: 0 0 12px;
}
.stat2-card {
  background: #fff;
  padding: 14px 8px;
  text-align: center;
}
.stat2-label { font-size: 12px; color: var(--apple-text3); margin-bottom: 6px; }
.stat2-value { font-size: 20px; font-weight: 800; }
.stat2-value.up { color: var(--apple-red); }
.stat2-value.down { color: var(--apple-green); }
.stat2-value.orange { color: var(--apple-orange); }

.section-title {
  font-size: 17px; font-weight: 700;
  padding: 14px 16px 10px;
  display: flex; align-items: center; gap: 6px;
  background: #fff;
  border-bottom: 1px solid var(--apple-gray5);
}

.sector-list { background: #fff; }
.sector-item {
  padding: 13px 16px; display: flex; align-items: center; gap: 12px;
  border-bottom: 0.5px solid var(--apple-gray5);
}
.sector-item:last-child { border-bottom: none; }
.sector-rank {
  width: 24px; height: 24px; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; color: #fff; flex-shrink: 0;
}
.rank-1 { background: var(--apple-red); }
.rank-2 { background: var(--apple-orange); }
.rank-3 { background: var(--apple-purple); }
.rank-other { background: var(--apple-gray); }
.sector-info { flex: 1; min-width: 0; }
.sector-name { font-size: 15px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sector-sub { font-size: 12px; color: var(--apple-text3); margin-top: 2px; }
.sector-change { font-size: 18px; font-weight: 800; flex-shrink: 0; }
.sector-change.up { color: var(--apple-red); }
.sector-change.down { color: var(--apple-green); }

.loading { text-align: center; padding: 60px 20px; color: var(--apple-gray); }
.spinner {
  width: 28px; height: 28px;
  border: 2.5px solid var(--apple-gray5);
  border-top-color: var(--apple-blue);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin: 0 auto 14px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.empty { text-align: center; padding: 60px 20px; color: var(--apple-gray); font-size: 14px; }
</style>

