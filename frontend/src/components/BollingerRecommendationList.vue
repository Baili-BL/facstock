<template>
  <div class="bbr-list">
    <div class="bbr-list__head">
      <h3 class="bbr-list__title">
        <svg class="icon" viewBox="0 0 24 24"><use href="#icon-star"/></svg>
        模型推荐标的
      </h3>
      <p class="bbr-list__disclaimer">以下仅基于本次扫描数据作研究参考，不构成投资建议。</p>
    </div>
    <article
      v-for="rec in recommendations"
      :key="rec.code"
      class="bbr-card"
    >
      <div class="bbr-card__top">
        <div class="bbr-card__left">
          <div class="bbr-card__title-row">
            <span class="bbr-card__name">{{ rec.name || rec.code }}</span>
            <span class="bbr-card__code">{{ rec.code }}</span>
          </div>
          <span v-if="rec.sector" class="bbr-card__sector-pill">{{ rec.sector }}</span>
        </div>
        <div class="bbr-card__price">
          <span class="bbr-card__pct" :class="recPctClass(rec)">{{ fmtRecPct(rec) }}</span>
          <span class="bbr-card__pct-label">当日涨幅</span>
        </div>
      </div>

      <div class="bbr-card__block bbr-card__block--reason">
        <div class="bbr-card__block-head bbr-card__block-head--reason">
          <svg class="bbr-card__bulb" viewBox="0 0 24 24" aria-hidden="true">
            <path
              fill="currentColor"
              d="M12 2C8.13 2 5 5.13 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.87-3.13-7-7-7zm2.85 11.1l-.65.36V16h-4.4v-2.54l-.65-.36C7.68 12.16 7 10.65 7 9c0-2.76 2.24-5 5-5s5 2.24 5 5c0 1.65-.68 3.16-1.85 4.1zM11 19h2v2h-2v-2z"
            />
          </svg>
          <span>入选理由</span>
        </div>
        <p class="bbr-card__block-text">{{ rec.reason || '—' }}</p>
      </div>

      <div class="bbr-card__block bbr-card__block--risk">
        <div class="bbr-card__block-head bbr-card__block-head--risk">
          <span class="bbr-card__risk-ic" aria-hidden="true">!</span>
          <span>风险提示</span>
        </div>
        <p class="bbr-card__block-text">{{ rec.risk || '—' }}</p>
      </div>
    </article>
  </div>
</template>

<script setup>
const props = defineProps({
  recommendations: { type: Array, default: () => [] },
  flatStocks: { type: Array, default: () => [] },
})

function stockByCode(code) {
  if (code == null || code === '') return null
  const c = String(code)
  return props.flatStocks.find(x => String(x.code) === c) || null
}

function fmtPct(s) {
  const v = Number(s?.pct_change)
  if (!Number.isFinite(v)) return '—'
  const sign = v > 0 ? '+' : ''
  return `${sign}${v.toFixed(2)}%`
}

function pctClass(s) {
  const v = Number(s?.pct_change)
  if (!Number.isFinite(v)) return ''
  if (v > 0) return 'bbr-up'
  if (v < 0) return 'bbr-down'
  return ''
}

function fmtRecPct(rec) {
  return fmtPct(stockByCode(rec?.code))
}

function recPctClass(rec) {
  return pctClass(stockByCode(rec?.code))
}
</script>

<style scoped>
.bbr-list__head {
  margin-bottom: 14px;
}
.bbr-list__title {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #1a1c1f;
}
.bbr-list__title .icon {
  width: 20px;
  height: 20px;
  fill: #ff9500;
}
.bbr-list__disclaimer {
  margin: 0;
  font-size: 11px;
  color: #787b86;
  line-height: 1.4;
}

.bbr-card {
  background: #fff;
  border-radius: 26px;
  padding: 22px 22px 20px;
  margin-bottom: 16px;
  border: 1px solid rgba(26, 28, 31, 0.08);
  box-shadow: 0 4px 24px rgba(26, 28, 31, 0.06);
}
.bbr-card:last-child {
  margin-bottom: 0;
}

.bbr-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.bbr-card__left {
  min-width: 0;
  flex: 1;
}
.bbr-card__title-row {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px 10px;
  margin-bottom: 8px;
}
.bbr-card__name {
  font-size: 1.125rem;
  font-weight: 800;
  color: #111827;
  letter-spacing: -0.02em;
}
.bbr-card__code {
  font-size: 0.8125rem;
  font-weight: 600;
  color: #6b7280;
}
.bbr-card__sector-pill {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #4b5563;
}

.bbr-card__price {
  flex-shrink: 0;
  text-align: right;
}
.bbr-card__pct {
  display: block;
  font-size: 1.25rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  line-height: 1.2;
}
.bbr-card__pct.bbr-up {
  color: #2563eb !important;
}
.bbr-card__pct.bbr-down {
  color: #dc2626 !important;
}
.bbr-card__pct-label {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  font-weight: 500;
  color: #9ca3af;
}

.bbr-card__block {
  border-radius: 16px;
  padding: 14px 14px 14px 16px;
  margin-bottom: 12px;
}
.bbr-card__block:last-of-type {
  margin-bottom: 0;
}

.bbr-card__block--reason {
  background: #eef4ff;
}
.bbr-card__block--risk {
  background: #fff;
  border: 1px solid #e5e7eb;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.bbr-card__block-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 800;
}
.bbr-card__block-head--reason {
  color: #2563eb;
}
.bbr-card__bulb {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  color: #2563eb;
}

.bbr-card__block-head--risk {
  color: #dc2626;
}
.bbr-card__risk-ic {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #ef4444;
  color: #fff;
  font-size: 12px;
  font-weight: 900;
  line-height: 18px;
  text-align: center;
  flex-shrink: 0;
}

.bbr-card__block-text {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.65;
  color: #374151;
}

.icon { fill: currentColor; }
</style>
