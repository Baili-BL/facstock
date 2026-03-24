<template>
  <div>
    <nav class="navbar">
      <span class="nav-title">策略中心</span>
    </nav>

    <div class="container">
      <!-- 顶部 Banner -->
      <div class="hub-header">
        <div class="hub-header-title">
          <svg class="icon" style="width:26px;height:26px;fill:#fff"><use href="#icon-strategy"/></svg>
          FacSstock 策略中心
        </div>
        <div class="hub-header-sub">量化选股 · 题材挖掘 · AI 智能分析</div>
        <div class="hub-header-stats">
          <div class="hub-stat">
            <div class="hub-stat-num">{{ stats.scans }}</div>
            <div class="hub-stat-label">扫描次数</div>
          </div>
          <div class="hub-stat">
            <div class="hub-stat-num">{{ stats.stocks }}</div>
            <div class="hub-stat-label">覆盖股票</div>
          </div>
          <div class="hub-stat">
            <div class="hub-stat-num">{{ stats.sectors }}</div>
            <div class="hub-stat-label">监测板块</div>
          </div>
        </div>
      </div>

      <!-- 热点板块速览 -->
      <div class="quick-scan">
        <div class="qs-header">
          <div class="qs-title">
            <svg class="icon icon-lg"><use href="#icon-fire"/></svg>
            今日热点板块
          </div>
          <span style="font-size:12px;color:var(--apple-text3);display:flex;align-items:center">
            <span class="live-dot"></span>实时
          </span>
        </div>

        <div v-if="sectorsLoading" class="loading">
          <div class="spinner"></div>
        </div>
        <div v-else-if="sectors.length === 0" class="empty">暂无热点数据</div>
        <div v-else class="qs-sectors">
          <div v-for="s in sectors" :key="s.name" class="qs-sector">
            <div class="qs-sector-name">
              <svg class="icon"><use href="#icon-fire"/></svg>
              {{ s.name }}
            </div>
            <div class="qs-sector-right">
              <span class="qs-sector-count">{{ s.stock_count || 0 }}只</span>
              <span class="qs-sector-change" :class="s.change >= 0 ? 'up' : 'down'">
                {{ s.change >= 0 ? '+' : '' }}{{ (s.change || 0).toFixed(2) }}%
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 三大策略入口 -->
      <div class="featured-label">
        <svg class="icon icon-sm"><use href="#icon-strategy"/></svg>
        选股策略
      </div>

      <router-link to="/strategy/bollinger" class="strategy-card">
        <div class="card-icon-wrap" style="background: linear-gradient(135deg, #5856D6, #007AFF)">
          <svg class="icon"><use href="#icon-strategy"/></svg>
        </div>
        <div class="card-info">
          <div class="card-name">布林收缩策略</div>
          <div class="card-desc">基于布林带收口检测，提前发现蓄势突破的股票</div>
          <div class="card-tags">
            <span class="card-tag">量价分析</span>
            <span class="card-tag">趋势跟踪</span>
            <span class="card-tag">资金流向</span>
          </div>
        </div>
        <div class="card-arrow">
          <svg class="icon" style="fill:var(--apple-gray3)"><use href="#icon-chevron"/></svg>
        </div>
      </router-link>

      <router-link to="/ticai" class="strategy-card">
        <div class="card-icon-wrap" style="background: linear-gradient(135deg, #FF9500, #FF3B30)">
          <svg class="icon"><use href="#icon-fire"/></svg>
        </div>
        <div class="card-info">
          <div class="card-name">题材挖掘</div>
          <div class="card-desc">AI 驱动的热点题材分析，追踪板块轮动与龙头股</div>
          <div class="card-tags">
            <span class="card-tag">AI分析</span>
            <span class="card-tag">题材轮动</span>
            <span class="card-tag">龙头追踪</span>
          </div>
        </div>
        <div class="card-arrow">
          <svg class="icon" style="fill:var(--apple-gray3)"><use href="#icon-chevron"/></svg>
        </div>
      </router-link>

      <router-link to="/strategy/ai" class="strategy-card">
        <div class="card-icon-wrap" style="background: linear-gradient(135deg, #AF52DE, #FF2D55)">
          <svg class="icon"><use href="#icon-ai"/></svg>
        </div>
        <div class="card-info">
          <div class="card-name">AI 智能策略</div>
          <div class="card-desc">腾讯混元大模型深度解读市场，寻找优质标的</div>
          <div class="card-tags">
            <span class="card-tag">LLM</span>
            <span class="card-tag">智能选股</span>
            <span class="card-tag">市场解读</span>
          </div>
        </div>
        <div class="card-arrow">
          <svg class="icon" style="fill:var(--apple-gray3)"><use href="#icon-chevron"/></svg>
        </div>
      </router-link>

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { hotSectors } from '@/api/market.js'

const sectors = ref([])
const sectorsLoading = ref(true)
const stats = ref({ scans: '--', stocks: '--', sectors: '--' })

async function loadHotSectors() {
  try {
    const data = await hotSectors()
    sectors.value = (data || []).slice(0, 5)
  } catch {
    sectors.value = []
  } finally {
    sectorsLoading.value = false
  }
}

async function loadStats() {
  try {
    const res = await fetch('/api/scan/history?limit=100')
    const json = await res.json()
    if (json.success && json.data && json.data.length > 0) {
      const total = json.data.length
      const stocks = json.data.reduce((s, d) => s + (d.stock_count || 0), 0)
      const sectorSet = new Set()
      json.data.forEach(d => (d.hot_sectors || []).forEach(s => sectorSet.add(s.name || s)))
      stats.value = { scans: total, stocks, sectors: sectorSet.size }
    }
  } catch {}
}

onMounted(() => {
  loadHotSectors()
  loadStats()
})
</script>

<style scoped>
.navbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(255,255,255,0.78);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  padding: 10px 16px;
  padding-top: calc(10px + env(safe-area-inset-top));
  display: flex; align-items: center; justify-content: center;
}
.nav-title { font-size: 17px; font-weight: 600; letter-spacing: -0.41px; }

.container { padding: 16px; }

.hub-header {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  border-radius: 20px; padding: 28px 22px;
  margin-bottom: 20px; color: #fff; text-align: center;
}
.hub-header-title {
  font-size: 24px; font-weight: 700; letter-spacing: -0.5px;
  margin-bottom: 6px; display: flex; align-items: center; justify-content: center; gap: 8px;
}
.hub-header-sub { font-size: 14px; color: rgba(255,255,255,0.65); font-weight: 400; }
.hub-header-stats { display: flex; justify-content: center; gap: 32px; margin-top: 18px; }
.hub-stat { text-align: center; }
.hub-stat-num { font-size: 22px; font-weight: 700; }
.hub-stat-label { font-size: 11px; color: rgba(255,255,255,0.5); margin-top: 2px; }

.featured-label {
  font-size: 13px; font-weight: 600; color: var(--apple-text3);
  letter-spacing: 0.5px; margin-bottom: 14px;
  display: flex; align-items: center; gap: 6px;
}

.strategy-card {
  background: var(--apple-card);
  border-radius: 18px; padding: 18px;
  margin-bottom: 14px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.05);
  display: flex; align-items: center;
  text-decoration: none; color: inherit;
  transition: transform 0.15s, box-shadow 0.15s;
  cursor: pointer;
}
.strategy-card:active { transform: scale(0.98); }

.card-icon-wrap {
  width: 56px; height: 56px; border-radius: 16px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; margin-right: 14px;
}
.card-icon-wrap .icon { width: 28px; height: 28px; fill: #fff; }
.card-info { flex: 1; min-width: 0; }
.card-name { font-size: 17px; font-weight: 600; margin-bottom: 3px; }
.card-desc { font-size: 13px; color: var(--apple-text3); line-height: 1.4; }
.card-tags { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 8px; }
.card-tag {
  font-size: 11px; font-weight: 500; padding: 2px 8px; border-radius: 6px;
  background: var(--apple-gray6); color: var(--apple-text2);
}
.card-arrow { color: var(--apple-gray3); flex-shrink: 0; margin-left: 10px; }

.quick-scan {
  background: var(--apple-card);
  border-radius: 18px; padding: 18px;
  margin-bottom: 14px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.05);
}
.qs-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.qs-title { font-size: 15px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.qs-title .icon { fill: var(--apple-orange); }
.live-dot {
  width: 8px; height: 8px; border-radius: 50%; background: var(--apple-green);
  display: inline-block; margin-right: 4px;
  animation: pulse 2s infinite;
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

.qs-sectors { display: flex; flex-direction: column; gap: 8px; }
.qs-sector {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; background: var(--apple-gray6); border-radius: 10px;
}
.qs-sector-name { font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: 5px; }
.qs-sector-name .icon { width: 14px; height: 14px; fill: var(--apple-orange); }
.qs-sector-right { display: flex; align-items: center; gap: 8px; }
.qs-sector-change { font-size: 14px; font-weight: 600; }
.qs-sector-count { font-size: 12px; color: var(--apple-text3); }
.up { color: var(--apple-red) !important; }
.down { color: var(--apple-green) !important; }

.loading { text-align: center; padding: 30px; color: var(--apple-gray); }
.spinner {
  width: 24px; height: 24px; border: 2px solid var(--apple-gray5);
  border-top-color: var(--apple-blue); border-radius: 50%;
  animation: spin 0.7s linear infinite; margin: 0 auto 10px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.empty { text-align: center; padding: 30px; color: var(--apple-gray); font-size: 14px; }
</style>

