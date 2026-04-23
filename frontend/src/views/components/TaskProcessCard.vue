<template>
  <section class="task-card">
    <div class="task-card__head">
      <div class="task-card__head-left">
        <svg class="icon task-card__head-icon" viewBox="0 0 24 24" aria-hidden="true">
          <use href="#icon-strategy" />
        </svg>
        <h2 class="task-card__title">任务执行过程</h2>
      </div>
      <div class="task-card__head-right">
        <span v-if="isRunning" class="task-card__running-badge">
          <span class="task-card__running-dot" />
          执行中 · {{ elapsedTime }}
        </span>
        <span v-else-if="isDone" class="task-card__done-badge">
          <svg class="icon task-card__done-icon" viewBox="0 0 24 24" aria-hidden="true">
            <use href="#icon-check" />
          </svg>
          已完成
        </span>
      </div>
    </div>

    <!-- Steps horizontal stepper -->
    <div class="task-card__stepper">
      <div
        v-for="(step, idx) in steps"
        :key="idx"
        class="task-card__step"
        :class="{
          'task-card__step--active': idx === effectiveCurrentStep - 1 && isRunning,
          'task-card__step--done': step.done || (isDone && idx < steps.length - 1) || (idx < effectiveCurrentStep - 1),
          'task-card__step--pending': !step.done && idx >= effectiveCurrentStep - 1 && !isDone,
        }"
      >
        <div class="task-card__step-indicator">
          <!-- Active: pulsing ring -->
          <div v-if="idx === effectiveCurrentStep - 1 && isRunning" class="task-card__step-ring">
            <div class="task-card__step-ring-inner" />
          </div>
          <!-- Done: check icon -->
          <div v-else-if="step.done || (isDone && idx < steps.length - 1) || idx < effectiveCurrentStep - 1" class="task-card__step-check">
            <svg class="icon task-card__step-check-icon" viewBox="0 0 24 24" aria-hidden="true">
              <use href="#icon-check" />
            </svg>
          </div>
          <!-- Pending: number -->
          <div v-else class="task-card__step-num">{{ idx + 1 }}</div>
        </div>

        <!-- Connector line -->
        <div
          v-if="idx < steps.length - 1"
          class="task-card__step-connector"
          :class="{ 'task-card__step-connector--done': step.done || idx < effectiveCurrentStep - 1 || isDone }"
        />

        <!-- Label -->
        <div class="task-card__step-label">
          <span class="task-card__step-name">{{ step.title }}</span>
          <span v-if="step.desc" class="task-card__step-desc">{{ step.desc }}</span>
        </div>
      </div>
    </div>

    <!-- Active step detail panel -->
    <div v-if="effectiveCurrentStep > 0" class="task-card__detail">
      <div class="task-card__detail-header">
        <span class="task-card__detail-step-badge">
          步骤 {{ effectiveCurrentStep }} / {{ steps.length }}
        </span>
        <span class="task-card__detail-title">{{ effectiveCurrentTitle }}</span>
      </div>
      <div class="task-card__detail-body">
        <div class="task-card__detail-text">
          <svg class="icon task-card__detail-icon" viewBox="0 0 24 24" aria-hidden="true">
            <use href="#icon-chevron-right" />
          </svg>
          <p>{{ effectiveCurrentDetail }}</p>
        </div>
        <!-- Progress bar for active step -->
        <div v-if="isRunning" class="task-card__progress-bar">
          <div class="task-card__progress-fill" />
        </div>
      </div>
    </div>

    <!-- Overall consensus gauge (bottom) -->
    <div v-if="isDone" class="task-card__consensus">
      <div class="task-card__consensus-gauge">
        <svg viewBox="0 0 80 80" class="task-card__gauge-svg">
          <circle cx="40" cy="40" r="32" fill="none" stroke-width="6" stroke="var(--track)" />
          <circle
            cx="40" cy="40" r="32"
            fill="none"
            stroke-width="6"
            stroke-linecap="round"
            :stroke="consensusColor"
            :stroke-dasharray="gaugeCirc"
            :stroke-dashoffset="gaugeOffset"
            transform="rotate(-90 40 40)"
            class="task-card__gauge-arc"
          />
          <text x="40" y="38" text-anchor="middle" class="task-card__gauge-num">{{ confidence }}</text>
          <text x="40" y="50" text-anchor="middle" class="task-card__gauge-unit">%</text>
        </svg>
      </div>
      <div class="task-card__consensus-info">
        <div class="task-card__consensus-stance" :class="'task-card__consensus-stance--' + stance">
          {{ stanceLabel }}
        </div>
        <p class="task-card__consensus-desc">信心指数</p>
        <p v-if="marketCommentary" class="task-card__consensus-comment">{{ marketCommentary }}</p>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'

const props = defineProps({
  steps: {
    type: Array,
    default: () => [],
  },
  currentStep: {
    type: Number,
    default: 0,
  },
  totalSteps: {
    type: Number,
    default: 5,
  },
  currentStepTitle: {
    type: String,
    default: '',
  },
  currentStepDetail: {
    type: String,
    default: '',
  },
  isRunning: {
    type: Boolean,
    default: false,
  },
  isDone: {
    type: Boolean,
    default: false,
  },
  confidence: {
    type: Number,
    default: 0,
  },
  stance: {
    type: String,
    default: 'neutral',
  },
  marketCommentary: {
    type: String,
    default: '',
  },
})

// Elapsed time counter
const elapsedSeconds = ref(0)
let timer = null

watch(() => props.isRunning, (running) => {
  if (running) {
    elapsedSeconds.value = 0
    timer = setInterval(() => {
      elapsedSeconds.value++
    }, 1000)
  } else {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }
}, { immediate: true })

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})

const elapsedTime = computed(() => {
  const s = elapsedSeconds.value
  if (s < 60) return `${s}秒`
  const m = Math.floor(s / 60)
  const rem = s % 60
  return `${m}分${rem}秒`
})

// Gauge calculations
const gaugeR = 32
const gaugeCirc = computed(() => 2 * Math.PI * gaugeR)
const gaugeOffset = computed(() => gaugeCirc.value * (1 - props.confidence / 100))

const stanceLabel = computed(() => {
  const m = { bull: '看多', bear: '看空', neutral: '中性' }
  return m[props.stance] || '中性'
})

const consensusColor = computed(() => {
  const m = { bull: '#f23645', bear: '#089981', neutral: '#717786' }
  return m[props.stance] || '#717786'
})

const effectiveCurrentStep = computed(() => {
  if (props.isDone && props.steps.length) {
    return props.steps.length
  }
  return props.currentStep
})

const effectiveCurrentTitle = computed(() => {
  if (!props.isDone && props.currentStepTitle) {
    return props.currentStepTitle
  }
  const idx = effectiveCurrentStep.value - 1
  return props.steps[idx]?.title || ''
})

const effectiveCurrentDetail = computed(() => {
  if (!props.isDone && props.currentStepDetail) {
    return props.currentStepDetail
  }
  const idx = effectiveCurrentStep.value - 1
  return props.steps[idx]?.desc || (props.isRunning ? '正在执行...' : '全部任务步骤已完成')
})
</script>

<style scoped>
/* ── Card ─────────────────────────────────────────────────────────────── */
.task-card {
  background: var(--surface-container-lowest);
  border-radius: 20px;
  padding: 20px;
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Header ─────────────────────────────────────────────────────────── */
.task-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.task-card__head-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-card__head-icon {
  width: 20px;
  height: 20px;
  color: var(--primary-container);
}

.task-card__title {
  font-family: var(--font-headline);
  font-size: 1.05rem;
  font-weight: 800;
  color: var(--on-surface);
  letter-spacing: -0.02em;
  margin: 0;
}

.task-card__running-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  background: rgba(59, 31, 140, 0.08);
  padding: 4px 12px;
  border-radius: 999px;
}

.task-card__running-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary);
  animation: pulse-dot 1.2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.8); }
}

.task-card__done-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  color: var(--down);
  background: rgba(8, 153, 129, 0.1);
  padding: 4px 12px;
  border-radius: 999px;
}

.task-card__done-icon {
  width: 14px;
  height: 14px;
}

/* ── Horizontal Stepper ─────────────────────────────────────────────── */
.task-card__stepper {
  display: flex;
  align-items: flex-start;
  gap: 0;
  padding: 0 4px;
  overflow-x: auto;
  scrollbar-width: none;
}
.task-card__stepper::-webkit-scrollbar { display: none; }

.task-card__step {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  min-width: 80px;
  flex: 1;
}

.task-card__step-indicator {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 2;
  transition: all 0.3s ease;
  flex-shrink: 0;
}

/* Active state */
.task-card__step--active .task-card__step-indicator {
  background: var(--primary);
  color: white;
  box-shadow: 0 0 0 4px rgba(59, 31, 140, 0.15);
}

/* Done state */
.task-card__step--done .task-card__step-indicator {
  background: var(--down);
  color: white;
}

/* Pending state */
.task-card__step--pending .task-card__step-indicator {
  background: var(--surface-container);
  color: var(--on-surface-variant);
  border: 2px solid var(--outline-variant);
}

/* Ring animation for active */
.task-card__step-ring {
  position: absolute;
  inset: -6px;
  border-radius: 50%;
  border: 2px solid var(--primary);
  opacity: 0.4;
  animation: ring-pulse 1.5s ease-in-out infinite;
}

.task-card__step-ring-inner {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 2px solid var(--primary);
  opacity: 0.2;
  animation: ring-pulse 1.5s ease-in-out infinite 0.5s;
}

@keyframes ring-pulse {
  0% { transform: scale(1); opacity: 0.4; }
  100% { transform: scale(1.4); opacity: 0; }
}

.task-card__step-check {
  display: flex;
  align-items: center;
  justify-content: center;
}

.task-card__step-check-icon {
  width: 18px;
  height: 18px;
  color: white;
}

.task-card__step-num {
  font-family: var(--font-headline);
  font-size: 14px;
  font-weight: 700;
  color: var(--on-surface-variant);
}

/* Connector line */
.task-card__step-connector {
  position: absolute;
  top: 18px;
  left: calc(50% + 18px);
  right: calc(-50% + 18px);
  height: 2px;
  background: var(--outline-variant);
  z-index: 1;
  transition: background 0.4s ease;
}

.task-card__step-connector--done {
  background: var(--down);
}

/* Labels */
.task-card__step-label {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  margin-top: 8px;
  text-align: center;
  padding: 0 4px;
}

.task-card__step-name {
  font-size: 11px;
  font-weight: 600;
  color: var(--on-surface);
  line-height: 1.3;
}

.task-card__step-desc {
  font-size: 10px;
  color: var(--on-surface-variant);
  line-height: 1.3;
  max-width: 70px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-card__step--active .task-card__step-name {
  color: var(--primary);
  font-weight: 700;
}

.task-card__step--done .task-card__step-name {
  color: var(--down);
}

/* ── Active Step Detail ─────────────────────────────────────────────── */
.task-card__detail {
  background: var(--surface-container-low);
  border-radius: 14px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-left: 3px solid var(--primary);
}

.task-card__detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.task-card__detail-step-badge {
  font-size: 11px;
  font-weight: 700;
  color: var(--primary);
  background: rgba(59, 31, 140, 0.08);
  padding: 2px 8px;
  border-radius: 999px;
}

.task-card__detail-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--on-surface);
}

.task-card__detail-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-card__detail-text {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.task-card__detail-icon {
  width: 16px;
  height: 16px;
  color: var(--primary);
  flex-shrink: 0;
  margin-top: 1px;
}

.task-card__detail-text p {
  margin: 0;
  font-size: 13px;
  color: var(--on-surface);
  line-height: 1.5;
}

.task-card__progress-bar {
  height: 3px;
  background: var(--outline-variant);
  border-radius: 999px;
  overflow: hidden;
}

.task-card__progress-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 999px;
  animation: progress-indeterminate 1.5s ease-in-out infinite;
  width: 40%;
}

@keyframes progress-indeterminate {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(350%); }
}

/* ── Consensus Gauge ─────────────────────────────────────────────────── */
.task-card__consensus {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-top: 8px;
  border-top: 1px solid var(--outline-variant);
}

.task-card__consensus-gauge {
  flex-shrink: 0;
}

.task-card__gauge-svg {
  width: 80px;
  height: 80px;
}

.task-card__gauge-arc {
  transition: stroke-dashoffset 0.8s ease;
}

.task-card__gauge-num {
  font-family: var(--font-headline);
  font-size: 18px;
  font-weight: 800;
  fill: var(--on-surface);
}

.task-card__gauge-unit {
  font-family: var(--font-body);
  font-size: 10px;
  fill: var(--on-surface-variant);
}

.task-card__consensus-info {
  flex: 1;
  min-width: 0;
}

.task-card__consensus-stance {
  display: inline-flex;
  align-items: center;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.01em;
  padding: 2px 0;
}

.task-card__consensus-stance--bull { color: var(--up); }
.task-card__consensus-stance--bear { color: var(--down); }
.task-card__consensus-stance--neutral { color: var(--on-surface-variant); }

.task-card__consensus-desc {
  font-size: 12px;
  color: var(--on-surface-variant);
  margin: 0;
}

.task-card__consensus-comment {
  font-size: 12px;
  color: var(--on-surface);
  margin: 4px 0 0;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
</style>
