<template>
  <div class="aset">
    <header class="aset-bar">
      <button type="button" class="aset-icon" aria-label="返回" @click="$router.back()">
        <svg class="aset-svg" viewBox="0 0 24 24" aria-hidden="true">
          <path fill="currentColor" d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
        </svg>
      </button>
      <h1 class="aset-title">设置</h1>
      <span class="aset-icon aset-icon--ghost" aria-hidden="true" />
    </header>

    <main class="aset-main">
      <p class="aset-lead">TradingView 式分组：轻量、可扫读。以下为本地偏好，保存在本机浏览器。</p>

      <section class="aset-group">
        <p class="aset-group__k">交易与自选</p>
        <div class="aset-card">
          <button type="button" class="aset-row" @click="$router.push('/watchlist/settings')">
            <span class="aset-row__ico aset-row__ico--pri" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="22" height="22"><path fill="currentColor" d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/></svg>
            </span>
            <span class="aset-row__txt">
              <span class="aset-row__t">风控与告警</span>
              <span class="aset-row__d">仓位上限、执行频率、止盈止损、技术指标提醒</span>
            </span>
            <svg class="aset-chev" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
          </button>
        </div>
      </section>

      <section class="aset-group">
        <p class="aset-group__k">应用</p>
        <div class="aset-card">
          <button type="button" class="aset-row" @click="toast('图表与主题设置即将推出')">
            <span class="aset-row__ico" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="22" height="22"><path fill="currentColor" d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9-4.03-9-9-9zm0 16c-3.86 0-7-3.14-7-7s3.14-7 7-7 7 3.14 7 7-3.14 7-7 7zm3.5-9H14V7.5h-4V10H8.5v4H10v2.5h4V14h1.5v-4z"/></svg>
            </span>
            <span class="aset-row__txt">
              <span class="aset-row__t">显示与图表</span>
              <span class="aset-row__d">K 线、配色、十字线（规划中）</span>
            </span>
            <svg class="aset-chev" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
          </button>
          <button type="button" class="aset-row" @click="toast('通知渠道与免打扰即将推出')">
            <span class="aset-row__ico" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="22" height="22"><path fill="currentColor" d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/></svg>
            </span>
            <span class="aset-row__txt">
              <span class="aset-row__t">通知</span>
              <span class="aset-row__d">推送、声音与时段（规划中）</span>
            </span>
            <svg class="aset-chev" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
          </button>
          <button type="button" class="aset-row aset-row--last" @click="toast('FacSstock · 本地策略与行情工具')">
            <span class="aset-row__ico" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="22" height="22"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>
            </span>
            <span class="aset-row__txt">
              <span class="aset-row__t">关于</span>
              <span class="aset-row__d">版本与说明</span>
            </span>
            <svg class="aset-chev" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/></svg>
          </button>
        </div>
      </section>
    </main>

    <p v-if="hint" class="aset-toast" role="status">{{ hint }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const hint = ref('')

function toast(msg) {
  hint.value = msg
  setTimeout(() => { hint.value = '' }, 2400)
}
</script>

<style scoped>
/* DESIGN.md: surface tiers, ambient shadow, no harsh borders */
.aset {
  --as-surface: #f9f9fe;
  --as-surface-low: #f3f3f8;
  --as-surface-lowest: #ffffff;
  --as-surface-container: #ededf2;
  --as-on-surface: #1a1c1f;
  --as-on-variant: #434656;
  --as-primary: #003ec7;
  --as-primary-mid: #0052ff;
  --as-ghost: rgba(195, 197, 217, 0.22);

  min-height: 100vh;
  min-height: 100dvh;
  background: var(--as-surface);
  color: var(--as-on-surface);
  padding-bottom: calc(env(safe-area-inset-bottom) + 72px);
  font-family: Inter, var(--font, system-ui), sans-serif;
}

.aset-bar {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: calc(52px + env(safe-area-inset-top, 0));
  padding: env(safe-area-inset-top, 0) 16px 0;
  background: rgba(249, 249, 254, 0.88);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 8px 24px rgba(26, 28, 31, 0.06);
}
.aset-title {
  flex: 1;
  text-align: center;
  font-family: Manrope, var(--font), sans-serif;
  font-size: 1.0625rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin: 0;
  color: var(--as-on-surface);
}
.aset-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 12px;
  background: transparent;
  color: var(--as-primary-mid);
  cursor: pointer;
}
.aset-icon:active {
  background: var(--as-surface-low);
}
.aset-icon--ghost {
  pointer-events: none;
  visibility: hidden;
}
.aset-svg {
  width: 22px;
  height: 22px;
  display: block;
}

.aset-main {
  max-width: 560px;
  margin: 0 auto;
  padding: 20px 20px 32px;
}
.aset-lead {
  font-size: 13px;
  line-height: 1.5;
  color: var(--as-on-variant);
  margin: 0 0 24px;
}

.aset-group {
  margin-bottom: 22px;
}
.aset-group__k {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--as-on-variant);
  margin: 0 0 10px 4px;
  opacity: 0.85;
}

.aset-card {
  background: var(--as-surface-lowest);
  border-radius: 24px;
  box-shadow: 0 8px 24px rgba(26, 28, 31, 0.06);
  overflow: hidden;
}

.aset-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  color: inherit;
  box-shadow: 0 1px 0 var(--as-ghost);
}
.aset-row--last,
.aset-row:last-child {
  box-shadow: none;
}
.aset-row:active {
  background: var(--as-surface-low);
}
.aset-row__ico {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: var(--as-surface-container);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--as-on-variant);
  flex-shrink: 0;
}
.aset-row__ico--pri {
  background: rgba(0, 82, 255, 0.1);
  color: var(--as-primary-mid);
}
.aset-row__txt {
  flex: 1;
  min-width: 0;
}
.aset-row__t {
  display: block;
  font-family: Manrope, var(--font), sans-serif;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.aset-row__d {
  display: block;
  font-size: 12px;
  color: var(--as-on-variant);
  margin-top: 3px;
  line-height: 1.35;
}
.aset-chev {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  color: var(--as-on-variant);
  opacity: 0.45;
}

.aset-toast {
  position: fixed;
  left: 50%;
  bottom: calc(88px + env(safe-area-inset-bottom, 0));
  transform: translateX(-50%);
  max-width: 90%;
  padding: 10px 16px;
  border-radius: 999px;
  background: rgba(26, 28, 31, 0.88);
  color: #fff;
  font-size: 13px;
  z-index: 200;
  pointer-events: none;
}
</style>
