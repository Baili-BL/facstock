<template>
  <nav class="bottom-nav">
    <router-link to="/" class="nav-item" :class="{ active: route.path === '/' }">
      <span class="nav-item__glyph">
        <svg class="icon" viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>
      </span>
      <span>首页</span>
    </router-link>
    <router-link to="/sectors" class="nav-item" :class="{ active: route.path === '/sectors' }">
      <span class="nav-item__glyph">
        <svg class="icon" viewBox="0 0 24 24"><path d="M3 3h18v18H3V3zm2 2v14h14V5H5zm2 2h10v2H7V7zm0 4h10v2H7v-2zm0 4h7v2H7v-2z"/></svg>
      </span>
      <span>板块</span>
    </router-link>
    <router-link to="/watchlist" class="nav-item" :class="{ active: route.path === '/watchlist' }">
      <span class="nav-item__glyph">
        <svg class="icon" viewBox="0 0 24 24"><path d="M12 17.3l5.2 3.1-1.4-5.9L20 9.8l-6-.5L12 3.7 9.9 9.3l-6 .5 4.2 4.7-1.4 5.9 5.3-3.1z"/></svg>
      </span>
      <span>自选</span>
    </router-link>
    <router-link to="/news" class="nav-item" :class="{ active: route.path === '/news' }">
      <span class="nav-item__glyph">
        <svg class="icon" viewBox="0 0 24 24"><path d="M19 5v2h-4V5h4M9 5v6H5V5h4M14 5h4v8h-4V5M5 19h14v-6H5v6M19 19v-6h-4v6H5"/></svg>
      </span>
      <span>新闻</span>
    </router-link>
    <router-link to="/strategy" class="nav-item" :class="{ active: route.path.startsWith('/strategy') }">
      <span class="nav-item__glyph">
        <svg class="icon" viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>
      </span>
      <span>策略</span>
    </router-link>
  </nav>
</template>

<script setup>
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<style scoped>
.bottom-nav {
  position: fixed; bottom: 0; left: 0; right: 0;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  padding: 6px 0 4px;
  padding-bottom: calc(4px + env(safe-area-inset-bottom));
  display: flex; justify-content: space-around;
  z-index: 100;
  border-top: 1px solid var(--divider);
}
.nav-item {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  text-decoration: none;
  color: var(--text-3);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: -0.02em;
  flex: 1;
  padding: 4px 0;
}
.nav-item__glyph {
  width: 48px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  transition: background 0.15s ease, color 0.15s ease;
}
.nav-item .icon {
  width: 22px;
  height: 22px;
  fill: currentColor;
}
.nav-item.active {
  color: var(--brand);
}
.nav-item.active .nav-item__glyph {
  background: var(--brand);
  color: #fff;
}
</style>
