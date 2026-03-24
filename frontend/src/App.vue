<template>
  <div id="app-root">
    <SvgSymbols />
    <router-view />
    <BottomNav v-if="!hideBottomNav" />
  </div>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import BottomNav from '@/components/BottomNav.vue'
import SvgSymbols from '@/components/SvgSymbols.vue'

const route = useRoute()
/** 题材挖掘 & AI 策略页面隐藏底部 Tab */
const hideBottomNav = computed(
  () => route.path.startsWith('/ticai') || route.path.startsWith('/strategy/ai')
)

watch(hideBottomNav, (v) => {
  document.body.classList.toggle('ticai-no-nav', v)
}, { immediate: true })
</script>

<style>
/* 移动端适配 - 禁用点击延迟 */
* { touch-action: manipulation; -webkit-tap-highlight-color: transparent; }

/* 盒模型 */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* 根字体设置 */
html {
  font-size: 16px;
  -webkit-text-size-adjust: 100%;
  -ms-text-size-adjust: 100%;
}

/* 移动端安全区域 */
:root {
  --apple-blue:   #007AFF;
  --apple-red:    #FF3B30;
  --apple-green:  #34C759;
  --apple-orange: #FF9500;
  --apple-purple: #AF52DE;
  --apple-gray:   #8E8E93;
  --apple-gray2:  #AEAEB2;
  --apple-gray3:  #C7C7CC;
  --apple-gray4:  #D1D1D6;
  --apple-gray5:  #E5E5EA;
  --apple-gray6:  #F2F2F7;
  --apple-bg:     #F2F2F7;
  --apple-card:  #FFFFFF;
  --apple-text:  #000000;
  --apple-text2: #3C3C43;
  --apple-text3: rgba(60, 60, 67, 0.6);
  
  --safe-area-bottom: env(safe-area-inset-bottom, 0px);
  --nav-height: 5.3125rem; /* 85px */
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'PingFang SC', 'Helvetica Neue', sans-serif;
  background: var(--apple-bg);
  min-height: 100vh;
  min-height: 100dvh; /* 动态视口高度 */
  color: var(--apple-text);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  padding-bottom: calc(var(--nav-height) + var(--safe-area-bottom));
  overflow-x: hidden;
}
body.ticai-no-nav {
  padding-bottom: env(safe-area-inset-bottom);
}

/* 滚动优化 */
body {
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: none;
}

#app-root { min-height: 100vh; min-height: 100dvh; }

/*
 * SVG + <use href="#symbol">：未设宽高时部分环境会按极大默认尺寸渲染，导致 H5 上「巨大图标」
 */
svg.icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  display: inline-block;
  vertical-align: middle;
}
svg.icon-sm {
  width: 14px;
  height: 14px;
}
svg.icon-lg {
  width: 22px;
  height: 22px;
}
svg.icon.empty-icon {
  width: 40px;
  height: 40px;
}

/* 通用颜色 */
.up   { color: var(--apple-red) !important; }
.down { color: var(--apple-green) !important; }

/* 通用 loading */
.loading { text-align: center; padding: 3.75rem 1.25rem; color: var(--apple-gray); }
.loading-spinner {
  width: 1.75rem; height: 1.75rem;
  border: 0.156rem solid var(--apple-gray5);
  border-top-color: var(--apple-blue);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin: 0 auto 0.875rem;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 通用 error */
.error { text-align: center; padding: 3.75rem 1.25rem; color: var(--apple-red); }

/* 通用卡片 */
.card { background: var(--apple-card); border-radius: 0.875rem; box-shadow: 0 0.125rem 0.5rem rgba(0,0,0,0.04); }

/* 滚动条样式 */
::-webkit-scrollbar { width: 0; height: 0; }

/* 图片自适应 */
img { max-width: 100%; height: auto; }

/* 按钮样式优化 */
button {
  -webkit-appearance: none;
  appearance: none;
  border: none;
  outline: none;
  background: transparent;
  font-family: inherit;
}

/* 输入框样式优化 */
input, textarea {
  -webkit-appearance: none;
  appearance: none;
  font-family: inherit;
}
</style>
