<template>
  <div id="app-root">
    <SvgSymbols />
    <router-view v-slot="{ Component }">
      <KeepAlive :include="['Home', 'Sectors', 'Watchlist', 'News', 'Strategy']">
        <component :is="Component" />
      </KeepAlive>
    </router-view>
    <BottomNav v-if="!hideBottomNav" />
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import BottomNav from '@/components/BottomNav.vue'
import SvgSymbols from '@/components/SvgSymbols.vue'

const route = useRoute()
/** 题材挖掘、AI 策略、布林带页隐藏底部 Tab */
const hideBottomNav = computed(
  () =>
    route.path.startsWith('/ticai') ||
    route.path.startsWith('/strategy/ai') ||
    route.path.startsWith('/strategy/macro') ||
    route.path.startsWith('/strategy/bollinger') ||
    route.path.startsWith('/strategy/factor-prompt') ||
    route.path.startsWith('/strategy/agents') ||
    route.path.startsWith('/strategy/backtest') ||
    route.path.startsWith('/sectors/heatmap') ||
    route.path === '/watchlist/settings'
)

watch(hideBottomNav, (v) => {
  document.body.classList.toggle('ticai-no-nav', v)
}, { immediate: true })
</script>

<style>
/* ═══════════════════════════════════════════════════════
   TradingView-Style Design System  (TV Mobile Design)
   ═══════════════════════════════════════════════════════ */

/* ── 1. CSS Design Tokens ─────────────────────────── */
:root {
  /* Brand / Accent */
  --brand:       #2962ff;   /* TV brand blue — primary CTA only */
  --brand-alpha:  rgba(41, 98, 255, 0.12);

  /* Functional — A 股语义：绿涨红跌（A股标准配色） */
  --up:          #089981;   /* 涨 · 绿色 */
  --down:        #f23645;   /* 跌 · 红色 */
  --up-alpha:    rgba(8, 153, 129, 0.12);
  --down-alpha:  rgba(242, 54, 69, 0.12);

  /* Surface — background layers */
  --bg:          #f2f2f2;    /* page background */
  --surface:     #ffffff;    /* card / panel */
  --surface-2:  #f7f8fa;    /* secondary surface */
  --divider:    #e9edf2;
  --divider-hover: #d4d7e0;

  /* Text */
  --text-1:      #0f0f0f;   /* primary text */
  --text-2:      #434651;   /* secondary */
  --text-3:      #787b86;   /* tertiary / muted */
  --text-4:      #aeaeb2;   /* placeholder */

  /* Typography */
  --font:        -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text',
                 'PingFang SC', 'Helvetica Neue', 'Roboto', sans-serif;
  --font-mono:    'Roboto Mono', 'SF Mono', 'Menlo', monospace;
  /* Font-size scale (px) */
  --text-2xs:    10px;
  --text-xs:     12px;
  --text-sm:     13px;
  --text-base:   14px;
  --text-md:     16px;
  --text-lg:     18px;
  --text-xl:     22px;
  --text-2xl:    28px;
  /* Line-height */
  --lh-tight:    1.15;
  --lh-snug:     1.3;
  --lh-base:     1.5;
  /* Letter-spacing */
  --ls-tight:    -0.02em;
  --ls-wide:     0.04em;
  /* Font-weight */
  --fw-normal:   400;
  --fw-medium:   500;
  --fw-semibold: 600;
  --fw-bold:     700;
  --fw-extrabold: 800;

  /* Spacing  (8px base grid) */
  --sp-1:   4px;
  --sp-2:   8px;
  --sp-3:   12px;
  --sp-4:   16px;
  --sp-5:   20px;
  --sp-6:   24px;
  --sp-8:   32px;
  --sp-10:  40px;

  /* Border-radius */
  --r-sm:   4px;
  --r-md:   8px;
  --r-lg:   12px;
  --r-xl:   16px;
  --r-2xl:  20px;
  --r-full: 999px;

  /* Shadows */
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.05);

  /* Transitions */
  --t-fast:  0.12s ease;
  --t-base:  0.2s ease;
  --t-slow:  0.35s ease;

  /* Layout */
  --nav-h:  80px;
  --safe-b: env(safe-area-inset-bottom, 0px);
  --page-px: var(--sp-4);   /* horizontal page padding */
}

/* ── 2. Base Reset ────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html {
  font-size: 16px;
  -webkit-text-size-adjust: 100%;
  -ms-text-size-adjust: 100%;
  text-size-adjust: 100%;
}

body {
  font-family: var(--font);
  font-size: var(--text-base);
  font-weight: var(--fw-normal);
  line-height: var(--lh-base);
  color: var(--text-1);
  background: var(--bg);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  padding-bottom: calc(var(--nav-h) + var(--safe-b));
  overflow-x: hidden;
}
body.ticai-no-nav { padding-bottom: var(--safe-b); }

#app-root { min-height: 100vh; min-height: 100dvh; }

/* ── 3. Text selection ────────────────────────────── */
::selection { background: var(--brand-alpha); color: var(--brand); }

/* ── 4. Scrollbar ──────────────────────────────────── */
::-webkit-scrollbar { width: 0; height: 0; }
body { scrollbar-width: none; }

/* ── 5. SVG Icons (global) ────────────────────────── */
svg.icon {
  width: 20px; height: 20px;
  flex-shrink: 0;
  display: inline-block;
  vertical-align: middle;
}
svg.icon-sm  { width: 14px; height: 14px; }
svg.icon-lg  { width: 24px; height: 24px; }
svg.icon-xl  { width: 32px; height: 32px; }
svg.icon-full { width: 40px; height: 40px; }

/* ── 5.1 Material Symbols (global) ───────────────── */
.mso,
.material-symbols-outlined {
  font-family: 'Material Symbols Outlined';
  font-weight: normal;
  font-style: normal;
  font-size: 24px;
  line-height: 1;
  letter-spacing: normal;
  text-transform: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  word-wrap: normal;
  direction: ltr;
  user-select: none;
  -webkit-font-smoothing: antialiased;
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
}

.mso-fill {
  font-variation-settings: 'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24;
}

/* ── 6. Utility colors ─────────────────────────────── */
.up    { color: var(--up)   !important; }
.down  { color: var(--down) !important; }
.muted { color: var(--text-3); }

/* ── 7. Financial numbers (tabular nums) ─────────── */
.tabular { font-variant-numeric: tabular-nums; }

/* ── 8. Page container ────────────────────────────── */
.page-px { padding-left: var(--page-px); padding-right: var(--page-px); }

/* ── 9. TV-style panel ───────────────────────────── */
.tv-panel {
  background: var(--surface);
  border-radius: var(--r-xl);
  padding: var(--sp-4);
  box-shadow: var(--shadow-sm);
}
.tv-panel--sm { padding: var(--sp-3); }
.tv-panel--none { background: transparent; box-shadow: none; border-radius: 0; }

/* ── 10. Typography helpers ────────────────────────── */
.text-xs     { font-size: var(--text-xs); }
.text-sm     { font-size: var(--text-sm); }
.text-base   { font-size: var(--text-base); }
.text-md     { font-size: var(--text-md); }
.text-lg     { font-size: var(--text-lg); }
.text-xl     { font-size: var(--text-xl); }
.text-2xs    { font-size: var(--text-2xs); }
.fw-medium  { font-weight: var(--fw-medium); }
.fw-semibold { font-weight: var(--fw-semibold); }
.fw-bold    { font-weight: var(--fw-bold); }
.text-muted { color: var(--text-3); }
.text-1     { color: var(--text-1); }

/* ── 11. Skeleton / Loading ──────────────────────── */
.skeleton {
  background: linear-gradient(90deg, #f0f3fa 25%, #e4e7f0 50%, #f0f3fa 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
  border-radius: var(--r-md);
}
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.loading {
  text-align: center;
  padding: var(--sp-10) var(--sp-4);
  color: var(--text-3);
  font-size: var(--text-sm);
}
.loading-spinner {
  width: 28px; height: 28px;
  border: 2px solid var(--divider);
  border-top-color: var(--brand);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin: 0 auto var(--sp-3);
}
@keyframes spin { to { transform: rotate(360deg); } }
.error {
  text-align: center;
  padding: var(--sp-10) var(--sp-4);
  color: var(--down);
  font-size: var(--text-sm);
}

/* ── 12. Button reset ─────────────────────────────── */
button {
  -webkit-appearance: none;
  appearance: none;
  border: none;
  outline: none;
  background: transparent;
  font-family: inherit;
  cursor: pointer;
}

/* ── 13. Input reset ──────────────────────────────── */
input, textarea {
  -webkit-appearance: none;
  appearance: none;
  font-family: inherit;
  touch-action: manipulation;
}
input:focus, textarea:focus { outline: none; }

/* ── 14. Image ─────────────────────────────────────── */
img { max-width: 100%; height: auto; display: block; }

/* ── 15. Transition helpers ───────────────────────── */
.fade-enter-active, .fade-leave-active { transition: opacity var(--t-base); }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
