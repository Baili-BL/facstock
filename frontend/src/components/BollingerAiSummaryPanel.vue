<template>
  <section class="bsd-pick" :class="{ 'bsd-pick--embed': variant === 'embed' }">
    <!-- 加载 -->
    <div v-if="aiLoading" class="bsd-pick-loading">
      <div class="bsd-pick-loading__card">
        <div class="bsd-cot-spin" />
        <div>
          <p class="bsd-pick-loading__t">正在生成推荐选股…</p>
          <p class="bsd-pick-loading__s">DeepSeek 正在结合本次扫描结果推理</p>
        </div>
      </div>
    </div>

    <!-- 错误 -->
    <div v-else-if="aiError" class="bsd-cot-err">
      <p>{{ aiError }}</p>
      <button type="button" class="bsd-retry-btn" @click="fetchAi(true)">重试</button>
    </div>

    <!-- 无成分 -->
    <div v-else-if="aiData?.source === 'empty'" class="bsd-pick-entry bsd-pick-entry--muted">
      <div class="bsd-pick-entry__head">
        <span class="bsd-pick-entry__badge-ic" aria-hidden="true">
          <svg class="icon" viewBox="0 0 24 24"><use href="#icon-ai"/></svg>
        </span>
        <div>
          <h2 class="bsd-pick-entry__title">DeepSeek 推荐选股</h2>
          <p class="bsd-pick-entry__sub">布林带收缩策略 · 智能荐股</p>
        </div>
      </div>
      <p class="bsd-pick-entry__lead">
        {{ aiData.cot_steps?.[0]?.content || '本次扫描暂无成分股结果，无法生成推荐与推理。' }}
      </p>
    </div>

    <!-- 有 CoT：入口 + 推荐区 + 结语 + 折叠推理 -->
    <template v-else-if="aiData?.cot_steps?.length">
      <!-- 入口：不作为长文展示，仅作荐股入口 -->
      <div class="bsd-pick-entry">
        <div class="bsd-pick-entry__head">
          <span class="bsd-pick-entry__badge-ic" aria-hidden="true">
            <svg class="icon" viewBox="0 0 24 24"><use href="#icon-ai"/></svg>
          </span>
          <div class="bsd-pick-entry__titles">
            <h2 class="bsd-pick-entry__title">DeepSeek 推荐选股</h2>
            <p class="bsd-pick-entry__sub">布林带收缩策略 · 智能荐股</p>
          </div>
        </div>
        <p class="bsd-pick-entry__hint">
          {{ entryHint }}
        </p>
        <div class="bsd-pick-entry__row">
          <span v-if="aiData.stored_at" class="bsd-pick-entry__saved">已保存 · {{ aiData.stored_at }}</span>
          <div class="bsd-pick-entry__actions">
            <button
              v-if="linkRecommendations && aiData.recommendations?.length"
              type="button"
              class="bsd-pick-entry__detail"
              @click="goRecommendDetail"
            >查看详情</button>
            <button
              v-if="showRefresh"
              type="button"
              class="bsd-pick-entry__refresh"
              @click="fetchAi(true)"
            >再解读</button>
          </div>
        </div>
      </div>

      <!-- 扫描详情页等：内联展示推荐列表；主策略 embed：仅「查看详情」跳转 -->
      <div
        v-if="!linkRecommendations && aiData.recommendations?.length"
        class="bsd-pick-inline-recs"
      >
        <BollingerRecommendationList
          :recommendations="aiData.recommendations"
          :flat-stocks="flatStocks"
        />
      </div>

      <div v-else-if="!linkRecommendations && !aiData.recommendations?.length" class="bsd-pick-recs-empty">
        <p>本轮未输出具体推荐标的，可查看下方完整推理或点击「再解读」重试。</p>
      </div>

      <div v-if="aiData.closing_note" class="bsd-closing">
        <div class="bsd-closing__bar" />
        <p class="bsd-closing__text">{{ aiData.closing_note }}</p>
      </div>

      <!-- 完整 CoT：默认折叠，逻辑与原先一致 -->
      <details class="bsd-cot-details">
        <summary class="bsd-cot-details__summary">查看完整推理过程（Chain-of-Thought）</summary>
        <div class="bsd-cot-details__body">
          <div class="bsd-cot-rail">
            <div
              v-for="(step, idx) in aiData.cot_steps"
              :key="idx"
              class="bsd-cot-node"
            >
              <div class="bsd-cot-node__track">
                <span class="bsd-cot-node__dot" />
                <span v-if="idx < aiData.cot_steps.length - 1" class="bsd-cot-node__line" />
              </div>
              <div class="bsd-cot-node__body">
                <p class="bsd-cot-node__title">{{ step.title }}</p>
                <p class="bsd-cot-node__text">{{ step.content }}</p>
              </div>
            </div>
          </div>
        </div>
      </details>

      <details v-if="aiData.raw_text" class="bsd-raw">
        <summary class="bsd-raw__toggle">展开模型原始返回</summary>
        <pre class="bsd-raw__body">{{ aiData.raw_text }}</pre>
      </details>

      <p class="bsd-cot-source">由 DeepSeek 生成 · 仅供参考</p>
    </template>

    <!-- 仅 raw、无结构化 CoT -->
    <template v-else-if="aiData?.raw_text">
      <div class="bsd-pick-entry">
        <div class="bsd-pick-entry__head">
          <span class="bsd-pick-entry__badge-ic" aria-hidden="true">
            <svg class="icon" viewBox="0 0 24 24"><use href="#icon-ai"/></svg>
          </span>
          <div>
            <h2 class="bsd-pick-entry__title">DeepSeek 推荐选股</h2>
            <p class="bsd-pick-entry__sub">解析未完全结构化，请查看原始内容</p>
          </div>
        </div>
        <div class="bsd-pick-entry__row">
          <span v-if="aiData.stored_at" class="bsd-pick-entry__saved">已保存 · {{ aiData.stored_at }}</span>
          <button type="button" class="bsd-pick-entry__refresh" @click="fetchAi(true)">再解读</button>
        </div>
      </div>
      <details class="bsd-raw" open>
        <summary class="bsd-raw__toggle">模型返回内容</summary>
        <pre class="bsd-raw__body">{{ aiData.raw_text }}</pre>
      </details>
      <p class="bsd-cot-source">由 DeepSeek 生成 · 仅供参考</p>
    </template>

    <template v-else-if="aiData && fallbackSummary">
      <div class="bsd-pick-entry bsd-pick-entry--muted">
        <h2 class="bsd-pick-entry__title">DeepSeek 推荐选股</h2>
        <p class="bsd-model__sub">基于该次扫描结果，对布林带收缩相关信号做自动归纳（非投资建议）。</p>
        <div class="bsd-model__body">{{ fallbackSummary }}</div>
      </div>
    </template>

    <!-- 未生成：大入口 CTA -->
    <button
      v-if="!aiData && !aiLoading && !aiError"
      type="button"
      class="bsd-gen-btn"
      @click="fetchAi(true)"
    >
      <svg class="icon" viewBox="0 0 24 24"><use href="#icon-ai"/></svg>
      生成 DeepSeek 推荐选股
    </button>
  </section>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import BollingerRecommendationList from '@/components/BollingerRecommendationList.vue'

const props = defineProps({
  scanId: { type: Number, default: null },
  flatStocks: { type: Array, default: () => [] },
  fallbackSummary: { type: String, default: '' },
  variant: { type: String, default: 'default' },
})

const router = useRouter()

/** 主策略页：推荐列表进独立详情页 */
const linkRecommendations = computed(() => props.variant === 'embed')

const aiLoading = ref(false)
const aiError = ref('')
const aiData = ref(null)

const showRefresh = computed(() => {
  const d = aiData.value
  if (!d) return false
  return Boolean(
    d.cot_steps?.length ||
      d.source === 'empty' ||
      d.raw_text
  )
})

/** 入口说明：embed 引导进详情页 */
const entryHint = computed(() => {
  const d = aiData.value
  if (!d?.cot_steps?.length) return ''
  const n = d.recommendations?.length || 0
  if (linkRecommendations.value) {
    if (n > 0) {
      return `已根据本次扫描生成 ${n} 只跟踪建议，完整分步推理与标的详情请点击「查看详情」查阅。`
    }
    return '本轮未输出具体推荐标的，可展开下方推理或点击「再解读」重试。'
  }
  if (n > 0) {
    return `已根据本次扫描生成 ${n} 只跟踪建议，完整分步推理见文末折叠区。`
  }
  return '完整模型推理见下方折叠区；若需重新生成请点击「再解读」。'
})

function goRecommendDetail() {
  const id = props.scanId
  if (id == null) return
  router.push(`/strategy/bollinger/scan/${id}/recommendations`)
}

async function fetchAi(refresh = false) {
  const id = props.scanId
  if (id == null) return
  aiLoading.value = true
  aiError.value = ''
  try {
    const q = refresh ? '?refresh=1' : ''
    const res = await fetch(`/api/scan/${id}/ai-summary${q}`)
    const json = await res.json()
    if (!json?.success) {
      if (json?.data?.fallback) {
        aiError.value = '未配置 DeepSeek API Key，无法生成推荐选股。'
      } else {
        aiError.value = json?.error || '生成失败'
      }
      return
    }
    aiData.value = json.data ?? null
  } catch (e) {
    aiError.value = e.message || '网络错误，请重试'
  } finally {
    aiLoading.value = false
  }
}

watch(
  () => props.scanId,
  id => {
    aiData.value = null
    aiError.value = ''
    if (id != null) fetchAi(false)
  },
  { immediate: true }
)
</script>

<style scoped>
.bsd-pick {
  background: transparent;
  margin-bottom: 24px;
}
.bsd-pick--embed {
  margin-top: 20px;
  margin-bottom: 0;
}

/* —— 入口卡片 —— */
.bsd-pick-entry {
  position: relative;
  border-radius: 22px;
  padding: 20px 18px 18px;
  background: linear-gradient(145deg, #f8faff 0%, #ffffff 48%, #f4f7ff 100%);
  border: 1px solid rgba(0, 82, 255, 0.12);
  box-shadow: 0 8px 28px rgba(0, 52, 170, 0.08);
  margin-bottom: 20px;
  overflow: hidden;
}
.bsd-pick-entry::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: linear-gradient(180deg, #0052ff, #7c9cff);
  border-radius: 22px 0 0 22px;
}
.bsd-pick-entry--muted {
  background: #f9f9fe;
  border-color: rgba(26, 28, 31, 0.08);
  box-shadow: none;
}
.bsd-pick-entry--muted::before {
  background: #c5cad8;
}

.bsd-pick-entry__head {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
}
.bsd-pick-entry__badge-ic {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(135deg, #003ec7, #0052ff);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 4px 14px rgba(0, 82, 255, 0.35);
}
.bsd-pick-entry__badge-ic .icon {
  width: 24px;
  height: 24px;
  fill: currentColor;
}
.bsd-pick-entry__titles {
  min-width: 0;
}
.bsd-pick-entry__title {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #0f172a;
  line-height: 1.25;
}
.bsd-pick-entry__sub {
  margin: 4px 0 0;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}
.bsd-pick-entry__hint {
  margin: 0 0 14px;
  padding-left: 56px;
  font-size: 13px;
  line-height: 1.55;
  color: #475569;
}
@media (max-width: 380px) {
  .bsd-pick-entry__hint {
    padding-left: 0;
  }
}
.bsd-pick-entry__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding-top: 4px;
  padding-left: 56px;
  border-top: 1px solid rgba(0, 82, 255, 0.08);
}
@media (max-width: 380px) {
  .bsd-pick-entry__row {
    padding-left: 0;
  }
}
.bsd-pick-entry__saved {
  font-size: 11px;
  color: #9092a8;
  flex: 1;
  min-width: 0;
}
.bsd-pick-entry__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}
.bsd-pick-entry__detail {
  padding: 8px 16px;
  border: none;
  border-radius: 999px;
  background: linear-gradient(135deg, #003ec7, #0052ff);
  font-size: 13px;
  font-weight: 800;
  color: #fff;
  cursor: pointer;
  font-family: inherit;
  box-shadow: 0 4px 14px rgba(0, 62, 199, 0.3);
}
.bsd-pick-entry__detail:active {
  transform: scale(0.98);
}
.bsd-pick-entry__refresh {
  padding: 8px 18px;
  border: 1px solid rgba(0, 82, 255, 0.4);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  font-size: 13px;
  font-weight: 700;
  color: #0052ff;
  cursor: pointer;
  font-family: inherit;
}
.bsd-pick-entry__refresh:active {
  transform: scale(0.98);
}
.bsd-pick-entry__lead {
  margin: 0;
  padding-left: 56px;
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
}
@media (max-width: 380px) {
  .bsd-pick-entry__lead {
    padding-left: 0;
  }
}

.bsd-pick-recs-empty {
  padding: 16px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #64748b;
  background: #f8fafc;
  border-radius: 14px;
  border: 1px dashed #e2e8f0;
}
.bsd-pick-recs-empty p {
  margin: 0;
}

.bsd-pick-inline-recs {
  margin-bottom: 12px;
}

/* —— 折叠 CoT —— */
.bsd-cot-details {
  margin-top: 16px;
  border: 1px solid #e8eaf2;
  border-radius: 16px;
  background: #fff;
  overflow: hidden;
}
.bsd-cot-details__summary {
  padding: 14px 16px;
  font-size: 14px;
  font-weight: 700;
  color: #0052ff;
  cursor: pointer;
  list-style: none;
  user-select: none;
  background: linear-gradient(180deg, #fafbff, #fff);
}
.bsd-cot-details__summary::-webkit-details-marker {
  display: none;
}
.bsd-cot-details__summary::after {
  content: '▼';
  float: right;
  font-size: 10px;
  opacity: 0.5;
  transition: transform 0.2s;
}
.bsd-cot-details[open] .bsd-cot-details__summary::after {
  transform: rotate(-180deg);
}
.bsd-cot-details__body {
  padding: 8px 12px 16px 8px;
  border-top: 1px solid #f1f3f9;
}

.bsd-pick-loading__card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px;
  background: #fff;
  border-radius: 20px;
  border: 1px solid rgba(0, 82, 255, 0.1);
  box-shadow: 0 6px 20px rgba(26, 28, 31, 0.06);
}
.bsd-pick-loading__t {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 800;
  color: #1a1c1f;
}
.bsd-pick-loading__s {
  margin: 0;
  font-size: 12px;
  color: #787b86;
}

.bsd-cot-spin {
  width: 28px;
  height: 28px;
  border: 3px solid #e2e2e7;
  border-top-color: #0052ff;
  border-radius: 50%;
  animation: bsd-cot-spin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes bsd-cot-spin { to { transform: rotate(360deg); } }

.bsd-cot-err {
  padding: 16px;
  background: rgba(186, 26, 26, 0.06);
  border-radius: 12px;
  font-size: 14px;
  color: #f23645;
}
.bsd-cot-err p { margin: 0 0 10px; }
.bsd-retry-btn {
  padding: 8px 20px;
  border: none;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  font-family: inherit;
  cursor: pointer;
  background: rgba(0, 82, 255, 0.1);
  color: #0052ff;
}
.bsd-model__sub {
  margin: 0 0 8px;
  font-size: 13px;
  color: #737688;
}
.bsd-model__body {
  font-size: 14px;
  line-height: 1.65;
  color: #1a1c1f;
  white-space: pre-wrap;
}

.bsd-cot-rail {
  display: flex;
  flex-direction: column;
}
.bsd-cot-node {
  display: flex;
  gap: 0;
}
.bsd-cot-node__track {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 28px;
  flex-shrink: 0;
}
.bsd-cot-node__dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #0052ff;
  border: 3px solid #d6e0ff;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}
.bsd-cot-node__line {
  flex: 1;
  width: 3px;
  min-height: 24px;
  background: linear-gradient(to bottom, #0052ff, #d6e0ff);
  border-radius: 2px;
}
.bsd-cot-node__body {
  padding: 4px 0 20px 14px;
  min-width: 0;
}
.bsd-cot-node:last-child .bsd-cot-node__body {
  padding-bottom: 4px;
}
.bsd-cot-node__title {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 800;
  color: #1a1c1f;
  line-height: 1.3;
}
.bsd-cot-node__text {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.7;
  color: #3d3f4c;
}

.bsd-closing {
  display: flex;
  gap: 12px;
  margin: 16px 0 0;
  padding: 14px 14px 14px 16px;
  background: rgba(0, 82, 255, 0.05);
  border-radius: 14px;
  border: 1px solid rgba(0, 82, 255, 0.1);
}
.bsd-closing__bar {
  width: 3px;
  border-radius: 2px;
  background: linear-gradient(to bottom, #0052ff, #003ec7);
  flex-shrink: 0;
}
.bsd-closing__text {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  color: #434656;
}
.bsd-cot-source {
  margin: 14px 0 0;
  padding: 10px 14px;
  font-size: 11px;
  color: #9092a8;
  background: #f3f3f8;
  border-radius: 10px;
  text-align: center;
}

.bsd-gen-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  margin-top: 6px;
  padding: 16px;
  border: none;
  border-radius: 18px;
  font-size: 15px;
  font-weight: 800;
  font-family: inherit;
  cursor: pointer;
  color: #fff;
  background: linear-gradient(135deg, #003ec7, #0052ff);
  box-shadow: 0 8px 24px rgba(0, 62, 199, 0.35);
}
.bsd-gen-btn .icon {
  width: 20px;
  height: 20px;
  fill: #fff;
}
.bsd-gen-btn:active { transform: scale(0.99); }

.bsd-raw {
  margin: 12px 0 0;
  border: 1px solid #e2e2e7;
  border-radius: 12px;
  overflow: hidden;
  font-size: 12px;
}
.bsd-raw__toggle {
  padding: 10px 12px;
  cursor: pointer;
  background: #f9f9fe;
  font-weight: 600;
  color: #434656;
}
.bsd-raw__body {
  margin: 0;
  padding: 12px;
  max-height: 240px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  background: #fff;
  color: #3d3f4c;
  font-family: ui-monospace, monospace;
  font-size: 11px;
  line-height: 1.5;
}

.icon { fill: currentColor; }
</style>
