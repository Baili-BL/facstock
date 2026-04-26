<template>
  <div class="st-map" :style="{ height: height + 'px' }">
    <svg
      class="st-map__svg"
      :width="containerW"
      :height="height"
      :viewBox="`0 0 ${containerW} ${height}`"
    >
      <g>
        <rect
          v-for="(cell, i) in layout"
          :key="i"
          class="st-map__cell"
          :x="cell.x0 + 1"
          :y="cell.y0 + 1"
          :width="Math.max(cell.x1 - cell.x0 - 2, 0)"
          :height="Math.max(cell.y1 - cell.y0 - 2, 0)"
          :fill="fillForChange(cell.change)"
          :rx="2"
          @click="onCellClick(cell)"
        />
      </g>
    </svg>

    <!-- HTML label overlay -->
    <div class="st-map__labels" :style="{ width: containerW + 'px', height: height + 'px' }">
      <div
        v-for="(cell, i) in layout"
        :key="'lbl' + i"
        class="st-map__label"
        :style="labelStyle(cell)"
        @click="onCellClick(cell)"
      >
        <span class="st-map__label-name">{{ cell.name }}</span>
        <span class="st-map__label-chg" :class="cell.change >= 0 ? 'up' : 'dn'">
          {{ cell.change >= 0 ? '+' : '' }}{{ cell.change.toFixed(2) }}%
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { hierarchy, treemap } from 'd3-hierarchy'

const props = defineProps({
  data: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  height: {
    type: Number,
    default: 200,
  },
})

const emit = defineEmits(['cell-click'])

const containerRef = ref(null)
const containerW = ref(360)
let resizeObserver = null

// 首页热门板块按用户习惯使用：红涨绿跌
const UP_LIGHT = [253, 232, 232]
const UP_DARK  = [242,  54,  69]
const DN_LIGHT = [213, 245, 227]
const DN_DARK  = [8,   153, 129]

function mixRgb(light, dark, t) {
  const a = Math.round(light[0] + (dark[0] - light[0]) * t)
  const b = Math.round(light[1] + (dark[1] - light[1]) * t)
  const c = Math.round(light[2] + (dark[2] - light[2]) * t)
  return `rgb(${a}, ${b}, ${c})`
}

function fillForChange(change) {
  const t = Math.min(Math.abs(Number(change) || 0) / 4, 1)
  if (change >= 0) return mixRgb(UP_LIGHT, UP_DARK, t * 0.8 + 0.05)
  return mixRgb(DN_LIGHT, DN_DARK, t * 0.8 + 0.05)
}

function textColor(change) {
  return '#ffffff'
}

function labelStyle(cell) {
  const w = cell.x1 - cell.x0
  const h = cell.y1 - cell.y0
  const fontSize = Math.min(13, Math.max(9, Math.floor(Math.min(w, h) / 4.5)))
  return {
    left:     cell.x0 + 'px',
    top:      cell.y0 + 'px',
    width:    w + 'px',
    height:   h + 'px',
    fontSize: fontSize + 'px',
    color:    textColor(cell.change),
  }
}

const layout = ref([])

function computeLayout() {
  if (!props.data || !props.data.length) {
    layout.value = []
    return
  }
  const sectors = [...props.data]
    .sort((a, b) => Math.abs(Number(b.change) || 0) - Math.abs(Number(a.change) || 0))
    .slice(0, 80)

  const root = hierarchy({ name: 'root', children: sectors })
    .sum(d => d.change !== undefined ? Math.abs(Number(d.change) || 0.01) : 0)
    .sort((a, b) => (b.value || 0) - (a.value || 0))

  treemap()
    .size([containerW.value, props.height])
    .paddingInner(2)
    .paddingOuter(2)
    .round(true)
    (root)

  layout.value = root.leaves().map(d => ({
    x0: Math.round(d.x0),
    y0: Math.round(d.y0),
    x1: Math.round(d.x1),
    y1: Math.round(d.y1),
    name: d.data.name || '',
    change: Number(d.data.change) || 0,
    total: root.leaves().length,
  }))
}

function updateWidth() {
  if (containerRef.value) {
    containerW.value = containerRef.value.clientWidth || 360
    computeLayout()
  }
}

function onCellClick(cell) {
  emit('cell-click', { name: cell.name, change: cell.change })
}

watch(() => props.data, async () => {
  await nextTick()
  computeLayout()
}, { deep: true })

watch(() => props.loading, async (val) => {
  if (!val) {
    await nextTick()
    updateWidth()
  }
})

onMounted(() => {
  updateWidth()
  resizeObserver = new ResizeObserver(() => updateWidth())
  if (containerRef.value) {
    resizeObserver.observe(containerRef.value)
  }
})

onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect()
})
</script>

<style scoped>
.st-map {
  position: relative;
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.st-map__svg {
  display: block;
}

.st-map__cell {
  cursor: pointer;
  transition: filter 0.1s;
  stroke: rgba(255, 255, 255, 0.7);
  stroke-width: 1;
}

.st-map__cell:hover {
  filter: brightness(0.9);
}

.st-map__labels {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
}

.st-map__label {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
  padding: 4px 4px 2px;
  pointer-events: all;
  cursor: pointer;
  text-align: center;
  overflow: hidden;
  box-sizing: border-box;
}

.st-map__label-name {
  font-weight: 700;
  line-height: 1.1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.st-map__label-chg {
  font-weight: 800;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.st-map__label-chg.up  { color: #ffffff; }
.st-map__label-chg.dn  { color: #ffffff; }
</style>
