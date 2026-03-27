<template>
  <div>
    <nav class="navbar">
      <span class="nav-title">
        <svg class="icon"><use href="#icon-analytics"/></svg>
        收益统计
      </span>
      <button class="update-btn" @click="updatePerf" :disabled="updating">
        <svg class="icon" :class="{ spinning: updating }"><use href="#icon-refresh"/></svg>
        {{ updating ? '更新中' : '更新' }}
      </button>
    </nav>

    <div class="container">
      <div v-if="loading" class="loading">
        <div class="spinner"></div>
        <div>加载中...</div>
      </div>
      <div v-else-if="error" class="error">{{ error }}</div>
      <div v-else>
        <!-- 核心指标 -->
        <div class="core-stats">
          <div class="stat-card">
            <div class="stat-label">
              <svg class="icon icon-sm"><use href="#icon-bar-chart"/></svg>
              平均收益
            </div>
            <div class="stat-value" :class="data.avg_profit_pct >= 0 ? 'up' : 'down'">
              {{ (data.avg_profit_pct || 0) >= 0 ? '+' : '' }}{{ (data.avg_profit_pct || 0).toFixed(2) }}%
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-label">
              <svg class="icon icon-sm"><use href="#icon-up"/></svg>
              总收益
            </div>
            <div class="stat-value" :class="data.total_profit_pct >= 0 ? 'up' : 'down'">
              {{ (data.total_profit_pct || 0) >= 0 ? '+' : '' }}{{ (data.total_profit_pct || 0).toFixed(2) }}%
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-label">
              <svg class="icon icon-sm"><use href="#icon-percent"/></svg>
              胜率
            </div>
            <div class="stat-value">{{ (data.win_rate || 0).toFixed(1) }}%</div>
          </div>
        </div>

        <!-- 策略分类收益 -->
        <div class="section" v-if="strategy">
          <div class="section-header">
            <svg class="icon"><use href="#icon-category"/></svg>
            <span class="section-title">策略分类收益</span>
          </div>
          <div class="section-body">
            <div class="strategy-grid">
              <div v-for="(info, name) in strategy.by_role" :key="name" class="strategy-card">
                <div class="strategy-name">{{ name }}</div>
                <div class="strategy-value" :class="(info.avg_profit_pct || 0) >= 0 ? 'up' : 'down'">
                  {{ (info.avg_profit_pct || 0) >= 0 ? '+' : '' }}{{ (info.avg_profit_pct || 0).toFixed(2) }}%
                </div>
                <div class="strategy-count">{{ info.count || 0 }}只</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 最佳策略 TOP3 -->
        <div class="section" v-if="data.best_strategies && data.best_strategies.length">
          <div class="section-header">
            <svg class="icon"><use href="#icon-trophy"/></svg>
            <span class="section-title">最佳策略 TOP3</span>
          </div>
          <div class="section-body">
            <div class="rank-list">
              <div v-for="(s, idx) in data.best_strategies.slice(0,3)" :key="s.name" class="rank-item">
                <div class="rank-left">
                  <span class="rank-badge" :class="'rank-' + (idx+1)">{{ idx+1 }}</span>
                  <span class="rank-name">{{ s.name }}</span>
                </div>
                <span class="rank-profit up">+{{ (s.avg_profit_pct || 0).toFixed(2) }}%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 无法买入的股票 -->
        <div class="section" v-if="data.unbuyable_stocks && data.unbuyable_stocks.length">
          <div class="section-header">
            <svg class="icon" style="fill:#f39c12"><use href="#icon-warning"/></svg>
            <span class="section-title">无法买入 ({{ data.unbuyable_stocks.length }}只)</span>
          </div>
          <div class="section-body">
            <div class="unbuyable-list">
              <div v-for="s in data.unbuyable_stocks.slice(0,10)" :key="s.stock_code" class="unbuyable-item">
                <div class="unbuyable-info">
                  <span class="unbuyable-name">{{ s.stock_name }}</span>
                  <span class="unbuyable-reason">
                    <svg class="icon icon-sm"><use href="#icon-warning"/></svg>
                    {{ s.unbuyable_reason || '无法买入' }}
                  </span>
                </div>
                <span class="unbuyable-change" :class="(s.change_pct || 0) >= 0 ? 'up' : 'down'">
                  {{ (s.change_pct || 0) >= 0 ? '+' : '' }}{{ (s.change_pct || 0).toFixed(2) }}%
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ticai } from '@/api/ticai.js'

const loading = ref(true)
const error = ref('')
const updating = ref(false)
const data = ref({})
const strategy = computed(() => data.value.strategy_analysis || {})

async function loadData() {
  try {
    data.value = await ticai.performance()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function updatePerf() {
  updating.value = true
  try {
    await ticai.updatePerf()
    await loadData()
  } catch (e) {
    alert('更新失败: ' + e.message)
  } finally {
    updating.value = false
  }
}

onMounted(() => loadData())
</script>

<style scoped>
.navbar {
  position: sticky; top: 0; z-index: 100;
  background: rgba(255,255,255,0.78);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  padding: 12px 16px;
  padding-top: calc(12px + env(safe-area-inset-top));
  display: flex; align-items: center; justify-content: space-between;
}
.nav-title { font-size: 17px; font-weight: 600; color: var(--apple-text); display: flex; align-items: center; gap: 6px; letter-spacing: -0.41px; }
.nav-title .icon { fill: var(--apple-blue); }
.update-btn {
  background: var(--apple-blue); color: #fff; border: none; padding: 8px 16px;
  border-radius: 20px; font-size: 15px; font-weight: 500; cursor: pointer;
  display: flex; align-items: center; gap: 4px;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(0,122,255,0.3);
}
.update-btn:disabled { opacity: 0.5; }
.update-btn .icon { fill: #fff; width: 16px; height: 16px; }
.spinning { animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.container { padding: 16px; }
.loading { text-align: center; padding: 80px 20px; color: var(--apple-gray); }
.spinner { width: 28px; height: 28px; border: 2.5px solid var(--apple-gray5); border-top-color: var(--apple-blue); border-radius: 50%; animation: spin 0.7s linear infinite; margin: 0 auto 14px; }
.error { text-align: center; padding: 60px 20px; color: var(--apple-red); }

.core-stats { display: flex; gap: 12px; margin-bottom: 16px; }
.stat-card { flex: 1; background: var(--apple-card); border-radius: 18px; padding: 18px 14px; text-align: center; box-shadow: 0 2px 12px rgba(0,0,0,0.04); }
.stat-label { font-size: 13px; color: var(--apple-text3); margin-bottom: 8px; display: flex; align-items: center; justify-content: center; gap: 4px; font-weight: 500; }
.stat-label .icon { fill: var(--apple-gray); }
.stat-value { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
.stat-value.up { color: var(--apple-red); }
.stat-value.down { color: var(--apple-green); }

.section { background: var(--apple-card); border-radius: 18px; margin-bottom: 14px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.04); }
.section-header { padding: 16px 18px; border-bottom: 0.5px solid var(--apple-gray5); display: flex; align-items: center; gap: 8px; }
.section-header .icon { fill: var(--apple-blue); }
.section-title { font-size: 16px; font-weight: 600; letter-spacing: -0.24px; }
.section-body { padding: 16px 18px; }

.strategy-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.strategy-card { background: var(--apple-gray6); border-radius: 14px; padding: 16px 14px; }
.strategy-name { font-size: 13px; color: var(--apple-text3); margin-bottom: 6px; display: flex; align-items: center; gap: 4px; font-weight: 500; }
.strategy-value { font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
.strategy-value.up { color: var(--apple-red); }
.strategy-value.down { color: var(--apple-green); }
.strategy-count { font-size: 12px; color: var(--apple-text3); margin-top: 4px; font-weight: 500; }

.rank-list { padding: 0; }
.rank-item { padding: 14px 0; border-bottom: 0.5px solid var(--apple-gray5); display: flex; justify-content: space-between; align-items: center; }
.rank-item:last-child { border-bottom: none; }
.rank-left { display: flex; align-items: center; gap: 12px; }
.rank-badge { width: 24px; height: 24px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; color: #fff; }
.rank-1 { background: var(--apple-red); }
.rank-2 { background: var(--apple-orange); }
.rank-3 { background: var(--apple-purple); }
.rank-name { font-size: 15px; font-weight: 600; letter-spacing: -0.24px; }
.rank-profit { font-size: 16px; font-weight: 700; letter-spacing: -0.24px; }
.rank-profit.up { color: var(--apple-red); }

.unbuyable-list { padding: 0; }
.unbuyable-item { padding: 12px 0; border-bottom: 0.5px solid var(--apple-gray5); display: flex; justify-content: space-between; align-items: center; }
.unbuyable-item:last-child { border-bottom: none; }
.unbuyable-info { display: flex; flex-direction: column; gap: 4px; }
.unbuyable-name { font-size: 15px; font-weight: 600; letter-spacing: -0.24px; }
.unbuyable-reason { font-size: 12px; color: var(--apple-orange); display: flex; align-items: center; gap: 4px; font-weight: 500; }
.unbuyable-reason .icon { fill: var(--apple-orange); }
.unbuyable-change { font-size: 15px; font-weight: 700; letter-spacing: -0.24px; }
.up { color: var(--apple-red) !important; }
.down { color: var(--apple-green) !important; }
</style>

