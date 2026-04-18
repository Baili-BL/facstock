import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'

import App from './App.vue'
import Home from './views/Home.vue'
import Sectors from './views/Sectors.vue'
import SectorHeatmap from './views/SectorHeatmap.vue'
import Watchlist from './views/Watchlist.vue'
import WatchlistSettings from './views/WatchlistSettings.vue'
import AppSettings from './views/AppSettings.vue'
import News from './views/News.vue'
import Strategy from './views/Strategy.vue'
import Bollinger from './views/Bollinger.vue'
import BollingerHistory from './views/BollingerHistory.vue'
import BollingerScanDetail from './views/BollingerScanDetail.vue'
import BollingerScanRecommendations from './views/BollingerScanRecommendations.vue'
import BollingerAlertList from './views/BollingerAlertList.vue'
import BollingerAlertEdit from './views/BollingerAlertEdit.vue'
import AIStrategy from './views/AIStrategy.vue'
import AISummaryDetail from './views/AISummaryDetail.vue'
import StrategyAgents from './views/StrategyAgents.vue'
import AgentHoldings from './views/AgentHoldings.vue'
import AgentAnalysis from './views/AgentAnalysis.vue'
import AgentDetailSummary from './views/AgentDetailSummary.vue'
import Ticai from './views/Ticai.vue'
import TicaiHistory from './views/TicaiHistory.vue'
import TicaiPerformance from './views/TicaiPerformance.vue'
import StockDetail from './views/StockDetail.vue'
import Backtest from './views/Backtest.vue'
import FactorPrompt from './views/FactorPrompt.vue'

const routes = [
  { path: '/', component: Home },
  { path: '/stock/:code', name: 'StockDetail', component: StockDetail },
  { path: '/sectors', component: Sectors },
  { path: '/sectors/heatmap', component: SectorHeatmap },
  { path: '/watchlist', component: Watchlist },
  { path: '/settings', component: AppSettings },
  { path: '/watchlist/settings', component: WatchlistSettings },
  { path: '/news', component: News },
  { path: '/strategy', component: Strategy },
  { path: '/strategy/bollinger/history', component: BollingerHistory },
  { path: '/strategy/bollinger/scan/:id/recommendations', component: BollingerScanRecommendations },
  { path: '/strategy/bollinger/scan/:id', component: BollingerScanDetail },
  { path: '/strategy/bollinger/alerts', component: BollingerAlertList },
  { path: '/strategy/bollinger/alert/:id', component: BollingerAlertEdit },
  { path: '/strategy/bollinger', component: Bollinger },
  { path: '/strategy/ai/summary', component: AISummaryDetail },
  { path: '/strategy/ai', component: AIStrategy },
  { path: '/strategy/agents', component: StrategyAgents },
  { path: '/strategy/agents/:id', component: AgentHoldings },
  { path: '/strategy/agents/:id/analysis', component: AgentAnalysis },
  { path: '/strategy/agents/:id/summary', component: AgentDetailSummary },
  { path: '/strategy/backtest', component: Backtest },
  { path: '/strategy/factor-prompt', component: FactorPrompt },
  { path: '/ticai', component: Ticai },
  { path: '/ticai/history', component: TicaiHistory },
  { path: '/ticai/performance', component: TicaiPerformance },
  // 兜底：未匹配路由重定向到首页
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

const app = createApp(App)
app.use(router)
app.mount('#app')
