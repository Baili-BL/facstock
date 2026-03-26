<template>
  <div class="wls">
    <header class="wls-bar">
      <button type="button" class="wls-back" aria-label="返回" @click="$router.back()">
        <svg class="wls-ico" viewBox="0 0 24 24" aria-hidden="true">
          <path fill="currentColor" d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
        </svg>
      </button>
      <h1 class="wls-title">自选设置</h1>
      <span class="wls-bar__sp" aria-hidden="true" />
    </header>

    <main class="wls-main">
      <section class="wls-card">
        <h2 class="wls-h2">仓位配置</h2>
        <p class="wls-desc">
          此处将用于单票仓位上限、总仓位、止损规则等配置。功能开发中，敬请期待。
        </p>
      </section>
    </main>
  </div>
</template>

<script setup>
</script>

<style scoped>
.wls {
  min-height: 100vh;
  min-height: 100dvh;
  background: #f8f9fa;
  color: #191c1d;
  padding-bottom: calc(env(safe-area-inset-bottom) + 72px);
}
.wls-bar {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: calc(48px + env(safe-area-inset-top, 0));
  padding: env(safe-area-inset-top, 0) 12px 0;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 1px 0 rgba(195, 197, 217, 0.15);
}
.wls-back {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  color: #434656;
  background: transparent;
  cursor: pointer;
}
.wls-back:active {
  background: #f3f4f5;
}
.wls-ico {
  width: 22px;
  height: 22px;
  display: block;
}
.wls-title {
  flex: 1;
  text-align: center;
  font-family: 'Manrope', var(--font, system-ui);
  font-size: 1.0625rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #003ec7;
  margin: 0;
}
.wls-bar__sp {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
}
.wls-main {
  padding: 16px 14px 24px;
}
.wls-card {
  background: #fff;
  border-radius: 8px;
  padding: 18px 16px;
  box-shadow: inset 0 0 0 1px rgba(195, 197, 217, 0.15);
}
.wls-h2 {
  font-size: 15px;
  font-weight: 800;
  margin: 0 0 10px;
  letter-spacing: -0.02em;
}
.wls-desc {
  font-size: 13px;
  line-height: 1.55;
  color: #434656;
  margin: 0;
}
</style>
