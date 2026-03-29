<template>
  <div class="bsr-page">
    <header class="bsr-header">
      <button type="button" class="bsr-back" aria-label="返回" @click="goBack">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <h1 class="bsr-title">模型推荐标的</h1>
      <span class="bsr-header__spacer" aria-hidden="true" />
    </header>

    <main class="bsr-main">
      <div v-if="loading" class="bsr-state"><div class="bsr-spin" /></div>
      <div v-else-if="loadError" class="bsr-state bsr-state--err">{{ loadError }}</div>
      <template v-else>
        <p v-if="aiData?.stored_at" class="bsr-meta">已保存 · {{ aiData.stored_at }}</p>
        <BollingerRecommendationList
          v-if="recommendations.length"
          :recommendations="recommendations"
          :flat-stocks="flatStocks"
        />
        <div v-else class="bsr-empty">
          <p>暂无推荐标的记录。请返回布林带策略页生成 DeepSeek 推荐选股，或确认该次扫描已保存分析结果。</p>
          <button type="button" class="bsr-back-link" @click="goBack">返回</button>
        </div>

        <div v-if="recommendations.length && aiData?.closing_note" class="bsr-closing">
          <div class="bsr-closing__bar" />
          <p class="bsr-closing__text">{{ aiData.closing_note }}</p>
        </div>

        <details v-if="recommendations.length && aiData?.cot_steps?.length" class="bsr-cot">
          <summary class="bsr-cot__sum">查看完整推理过程（Chain-of-Thought）</summary>
          <div class="bsr-cot__body">
            <div
              v-for="(step, idx) in aiData.cot_steps"
              :key="idx"
              class="bsr-cot-step"
            >
              <p class="bsr-cot-step__t">{{ step.title }}</p>
              <p class="bsr-cot-step__c">{{ step.content }}</p>
            </div>
          </div>
        </details>

        <p v-if="recommendations.length" class="bsr-foot">由 DeepSeek 生成 · 仅供参考</p>
      </template>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { scan } from '@/api/strategy.js'
import BollingerRecommendationList from '@/components/BollingerRecommendationList.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const loadError = ref('')
const detail = ref(null)
const aiData = ref(null)

const scanId = computed(() => {
  const n = Number(route.params.id)
  return Number.isFinite(n) ? n : null
})

const flatStocks = computed(() => {
  const d = detail.value
  if (!d?.results) return []
  const list = []
  for (const [sectorName, block] of Object.entries(d.results)) {
    for (const s of block?.stocks || []) {
      list.push({ ...s, sector_name: sectorName })
    }
  }
  return list
})

const recommendations = computed(() => aiData.value?.recommendations || [])

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/strategy/bollinger')
}

async function loadAll() {
  const id = scanId.value
  if (id == null) {
    loadError.value = '无效的记录编号'
    loading.value = false
    return
  }
  loading.value = true
  loadError.value = ''
  try {
    const data = await scan.detail(id)
    if (!data || data.id == null) {
      loadError.value = '记录不存在'
      detail.value = null
      aiData.value = null
      return
    }
    detail.value = data

    const res = await fetch(`/api/scan/${id}/ai-summary`)
    const json = await res.json()
    if (!json?.success) {
      aiData.value = null
      return
    }
    aiData.value = json.data ?? null
  } catch (e) {
    loadError.value = e.message || '加载失败'
    detail.value = null
    aiData.value = null
  } finally {
    loading.value = false
  }
}

watch(scanId, () => loadAll())
onMounted(loadAll)
</script>

<style scoped>
.bsr-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: #f9f9fe;
  color: #1a1c1f;
  font-family: 'Inter', 'Manrope', 'PingFang SC', var(--font), system-ui, sans-serif;
  padding-bottom: calc(28px + env(safe-area-inset-bottom, 0px));
}

.bsr-header {
  display: grid;
  grid-template-columns: 44px 1fr 44px;
  align-items: center;
  padding: 10px 12px;
  padding-top: calc(10px + env(safe-area-inset-top, 0px));
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(16px);
  position: sticky;
  top: 0;
  z-index: 20;
  box-shadow: 0 1px 0 rgba(26, 28, 31, 0.06);
}
.bsr-back {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 12px;
  background: #f3f3f8;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #1a1c1f;
}
.bsr-back .icon {
  width: 20px;
  height: 20px;
  fill: currentColor;
}
.bsr-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 800;
  text-align: center;
}
.bsr-header__spacer {
  width: 40px;
}

.bsr-main {
  padding: 16px;
  max-width: 720px;
  margin: 0 auto;
}

.bsr-meta {
  margin: 0 0 14px;
  font-size: 11px;
  color: #9092a8;
}

.bsr-state {
  display: flex;
  justify-content: center;
  padding: 48px 16px;
  color: #737688;
}
.bsr-state--err {
  color: #f23645;
  text-align: center;
  font-size: 14px;
}
.bsr-spin {
  width: 32px;
  height: 32px;
  border: 3px solid #e2e2e7;
  border-top-color: #0052ff;
  border-radius: 50%;
  animation: bsr-spin 0.7s linear infinite;
}
@keyframes bsr-spin {
  to { transform: rotate(360deg); }
}

.bsr-empty {
  padding: 28px 16px;
  text-align: center;
  font-size: 14px;
  line-height: 1.6;
  color: #64748b;
  background: #fff;
  border-radius: 16px;
  border: 1px dashed #e2e8f0;
}
.bsr-empty p {
  margin: 0 0 16px;
}
.bsr-back-link {
  padding: 10px 24px;
  border: none;
  border-radius: 999px;
  font-size: 14px;
  font-weight: 700;
  font-family: inherit;
  cursor: pointer;
  color: #fff;
  background: linear-gradient(135deg, #003ec7, #0052ff);
}

.bsr-closing {
  display: flex;
  gap: 12px;
  margin-top: 20px;
  padding: 14px 14px 14px 16px;
  background: rgba(0, 82, 255, 0.05);
  border-radius: 14px;
  border: 1px solid rgba(0, 82, 255, 0.1);
}
.bsr-closing__bar {
  width: 3px;
  border-radius: 2px;
  background: linear-gradient(to bottom, #0052ff, #003ec7);
  flex-shrink: 0;
}
.bsr-closing__text {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  color: #434656;
}

.bsr-cot {
  margin-top: 16px;
  border: 1px solid #e8eaf2;
  border-radius: 16px;
  background: #fff;
  overflow: hidden;
}
.bsr-cot__sum {
  padding: 14px 16px;
  font-size: 14px;
  font-weight: 700;
  color: #0052ff;
  cursor: pointer;
  list-style: none;
  background: linear-gradient(180deg, #fafbff, #fff);
}
.bsr-cot__sum::-webkit-details-marker {
  display: none;
}
.bsr-cot__body {
  padding: 8px 16px 16px;
  border-top: 1px solid #f1f3f9;
}
.bsr-cot-step {
  margin-bottom: 14px;
}
.bsr-cot-step:last-child {
  margin-bottom: 0;
}
.bsr-cot-step__t {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 800;
  color: #1a1c1f;
}
.bsr-cot-step__c {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  color: #3d3f4c;
}

.bsr-foot {
  margin: 16px 0 0;
  padding: 10px 14px;
  font-size: 11px;
  color: #9092a8;
  background: #f3f3f8;
  border-radius: 10px;
  text-align: center;
}

.icon { fill: currentColor; }
</style>
