<template>
  <div>
    <!-- 顶部分段 -->
    <div class="ths-tabs">
      <div class="ths-tab active">大盘</div>
      <div class="ths-tab" @click="$router.push('/sectors')">板块</div>
      <div class="ths-tab" @click="$router.push('/strategy')">个股</div>
      <div class="ths-tab-underline"></div>
    </div>

    <div class="ths-status-row">
      <div class="ths-status-left">
        <span class="ths-status-badge">{{ marketStatus }}</span>
        <span class="ths-status-date">{{ dateText }}</span>
      </div>
      <div class="ths-status-right">
        <div class="ths-inflow-label">大盘资金净流入</div>
        <div class="ths-inflow-value">{{ formatNumber(flow.north_money?.north_net_inflow || 0) }}</div>
      </div>
    </div>

    <!-- 三大指数卡片 -->
    <div class="ths-index-grid">
      <div v-for="item in top3" :key="item.name" class="ths-index-card">
        <div class="ths-index-name">{{ item.name }}</div>
        <div class="ths-index-price">{{ item.idx.price ? item.idx.price.toFixed(2) : '--' }}</div>
        <div class="ths-index-change" :class="item.idx.change >= 0 ? 'up' : 'down'">
          <span>{{ (item.idx.change_amount || 0) >= 0 ? '+' : '' }}{{ (item.idx.change_amount || 0).toFixed(2) }}</span>
          <span style="margin-left:6px">{{ item.idx.change >= 0 ? '+' : '' }}{{ (item.idx.change || 0).toFixed(2) }}%</span>
        </div>
      </div>
    </div>

    <!-- 市场统计 -->
    <div class="section">
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon">🚀</div>
          <div class="stat-label">涨停数</div>
          <div class="stat-value up">{{ limit.limit_up_count || 0 }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">📉</div>
          <div class="stat-label">跌停数</div>
          <div class="stat-value down">{{ limit.limit_down_count || 0 }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">💰</div>
          <div class="stat-label">北向资金</div>
          <div class="stat-value" :class="(flow.north_money?.north_net_inflow || 0) >= 0 ? 'up' : 'down'">
            {{ (flow.north_money?.north_net_inflow || 0) >= 0 ? '+' : '' }}{{ formatNumber(flow.north_money?.north_net_inflow || 0) }}
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">⏰</div>
          <div class="stat-label">更新时间</div>
          <div class="stat-value neutral" style="font-size:14px">{{ flow.time || '--:--' }}</div>
        </div>
      </div>
    </div>

    <!-- 热点板块 -->
    <div class="section">
      <div class="section-header">
        <span class="section-title">
          <svg class="icon"><use href="#icon-fire"/></svg>
          热点板块
        </span>
        <span class="more-link" @click="$router.push('/sectors')">更多 ></span>
      </div>
      <div class="sector-list">
        <div v-for="(s, i) in sectors.slice(0,8)" :key="s.name" class="sector-item">
          <span class="sector-rank" :class="i < 3 ? 'rank-' + (i+1) : 'rank-other'">{{ i + 1 }}</span>
          <div class="sector-info">
            <div class="sector-name">{{ s.name }}</div>
            <div class="sector-leader">领涨: {{ s.leader || '--' }}</div>
          </div>
          <div class="sector-change" :class="s.change >= 0 ? 'up' : 'down'">
            {{ s.change >= 0 ? '+' : '' }}{{ (s.change || 0).toFixed(2) }}%
          </div>
        </div>
      </div>
    </div>

    <!-- 活跃股票 -->
    <div class="section">
      <div class="section-header">
        <span class="section-title">
          <svg class="icon" style="fill:var(--apple-purple)"><use href="#icon-fire"/></svg>
          换手率排行
        </span>
      </div>
      <div class="stock-list">
        <div v-for="s in turnover.slice(0,8)" :key="s.code" class="stock-item">
          <div class="stock-left">
            <div class="stock-name">{{ s.name }}</div>
            <div class="stock-code">{{ s.code }}</div>
          </div>
          <div class="stock-right">
            <div class="stock-turnover">{{ (s.turnover_rate || 0).toFixed(1) }}%</div>
            <div class="stock-change" :class="(s.change || 0) >= 0 ? 'up' : 'down'">
              {{ (s.change || 0) >= 0 ? '+' : '' }}{{ (s.change || 0).toFixed(2) }}%
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { market } from '@/api/market.js'

const overview = ref([])
const flow = ref({ north_money: {} })
const limit = ref({})
const sectors = ref([])
const turnover = ref([])
const loading = ref(true)

const now = new Date()
const dateText = now.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).replaceAll('/', '-')
const weekText = ['日','一','二','三','四','五','六'][now.getDay()]
const marketStatus = (now.getHours() >= 15 || now.getHours() < 9) ? '已收盘' : '交易中'

const top3 = computed(() => [
  { name: '上证指数', idx: overview.value.find(i => i.name === '上证指数') || {} },
  { name: '深证成指', idx: overview.value.find(i => i.name === '深证成指') || {} },
  { name: '创业板指', idx: overview.value.find(i => i.name === '创业板指') || {} },
])

function formatNumber(num) {
  if (Math.abs(num) >= 100000000) return (num / 100000000).toFixed(2) + '亿'
  if (Math.abs(num) >= 10000) return (num / 10000).toFixed(2) + '万'
  return num.toFixed(2)
}

onMounted(async () => {
  try {
    const [ov, fl, lm, sc, tr] = await Promise.all([
      market.overview(),
      market.flow(),
      market.limit(),
      market.sectors(),
      market.turnover(),
    ])
    overview.value = Array.isArray(ov) ? ov : []
    flow.value = fl || {}
    limit.value = lm || {}
    sectors.value = Array.isArray(sc) ? sc : []
    turnover.value = Array.isArray(tr) ? tr : []
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
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
  font-size: 16px;
  font-weight: 600;
  color: var(--apple-text3);
  padding: 10px 6px 12px;
  cursor: pointer;
}
.ths-tab.active { color: var(--apple-text); }
.ths-tab-underline {
  position: absolute;
  height: 3px;
  width: 36px;
  background: #FF3B30;
  border-radius: 2px;
  bottom: 0;
  left: calc(16.66% - 18px);
}

.ths-status-row {
  margin: 12px 16px 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ths-status-left { display: flex; flex-direction: column; gap: 6px; }
.ths-status-badge { display: inline-flex; align-items: center; gap: 6px; font-size: 18px; font-weight: 700; }
.ths-status-date { font-size: 13px; color: var(--apple-text3); }
.ths-status-right { text-align: right; }
.ths-inflow-label { font-size: 12px; color: var(--apple-text3); }
.ths-inflow-value { font-size: 18px; font-weight: 800; color: #FF3B30; margin-top: 4px; }

.ths-index-grid {
  margin: 0 16px 6px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.ths-index-card {
  background: #F5F5F7;
  border-radius: 14px;
  padding: 12px 12px 10px;
}
.ths-index-name { font-size: 14px; font-weight: 700; color: var(--apple-text2); }
.ths-index-price { font-size: 22px; font-weight: 800; margin-top: 8px; color: #FF3B30; }
.ths-index-change { font-size: 12px; font-weight: 700; margin-top: 6px; }
.ths-index-change.up { color: #FF3B30; }
.ths-index-change.down { color: var(--apple-green); }

.section { margin: 16px; }
.section-header { margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }
.section-title { font-size: 17px; font-weight: 600; display: flex; align-items: center; gap: 6px; }
.section-title .icon { fill: var(--apple-orange); }
.more-link { font-size: 13px; color: var(--apple-blue); cursor: pointer; }

.stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.stat-card { background: var(--apple-card); border-radius: 14px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
.stat-icon { font-size: 24px; margin-bottom: 8px; }
.stat-label { font-size: 13px; color: var(--apple-text3); margin-bottom: 4px; }
.stat-value { font-size: 22px; font-weight: 700; }
.stat-value.up { color: var(--apple-red); }
.stat-value.down { color: var(--apple-green); }
.stat-value.neutral { color: var(--apple-orange); }

.sector-list { background: var(--apple-card); border-radius: 14px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
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
.sector-leader { font-size: 12px; color: var(--apple-text3); margin-top: 2px; }
.sector-change { font-size: 18px; font-weight: 700; flex-shrink: 0; }
.sector-change.up { color: var(--apple-red); }
.sector-change.down { color: var(--apple-green); }

.stock-list { background: var(--apple-card); border-radius: 14px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
.stock-item {
  padding: 13px 16px; display: flex; align-items: center; gap: 12px;
  border-bottom: 0.5px solid var(--apple-gray5);
}
.stock-item:last-child { border-bottom: none; }
.stock-left { flex: 1; min-width: 0; }
.stock-name { font-size: 15px; font-weight: 600; }
.stock-code { font-size: 12px; color: var(--apple-text3); margin-top: 2px; }
.stock-right { text-align: right; }
.stock-turnover { font-size: 15px; font-weight: 700; color: var(--apple-orange); }
.stock-change { font-size: 13px; font-weight: 600; margin-top: 2px; }
.up { color: var(--apple-red) !important; }
.down { color: var(--apple-green) !important; }
</style>

