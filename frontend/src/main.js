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
import MacroFlashReport from './views/MacroFlashReport.vue'
import TodayThemeDetail from './views/TodayThemeDetail.vue'
import AISummaryDetail from './views/AISummaryDetail.vue'
import StrategyAgents from './views/StrategyAgents.vue'
import StrategyAgentsIntro from './views/StrategyAgentsIntro.vue'
import StrategyAgentsIntroPrinciples from './views/StrategyAgentsIntroPrinciples.vue'
import YouziAgents from './views/YouziAgents.vue'
import AgentHoldings from './views/AgentHoldings.vue'
import AgentAnalysis from './views/AgentAnalysis.vue'
import AgentDetailSummary from './views/AgentDetailSummary.vue'
import FeishuPush from './views/FeishuPush.vue'
import FeishuPushHistory from './views/FeishuPushHistory.vue'
import FeishuPushLogs from './views/FeishuPushLogs.vue'
import XiaoyueyuTrader from './views/XiaoyueyuTrader.vue'
import JunGeTrader from './views/JunGeTrader.vue'
import ChenxiaoqunTrader from './views/ChenxiaoqunTrader.vue'
import Ticai from './views/Ticai.vue'
import TicaiHistory from './views/TicaiHistory.vue'
import TicaiPerformance from './views/TicaiPerformance.vue'
import StockDetail from './views/StockDetail.vue'
import Backtest from './views/Backtest.vue'
import FactorPrompt from './views/FactorPrompt.vue'
import TaskDashboard from './views/TaskDashboard.vue'

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
  { path: '/strategy/ai/macro-summary', component: AISummaryDetail },
  { path: '/strategy/ai', component: AIStrategy },
  { path: '/strategy/macro', component: MacroFlashReport },
  { path: '/strategy/today-theme', component: TodayThemeDetail },
  { path: '/strategy/agents', component: StrategyAgents },
  { path: '/strategy/youzi_agents', component: YouziAgents },
  { path: '/strategy/agents/intro', component: StrategyAgentsIntro },
  { path: '/strategy/agents/intro/principles', component: StrategyAgentsIntroPrinciples },
  { path: '/strategy/agents/:id', component: AgentHoldings },
  { path: '/strategy/agents/:id/analysis', component: AgentAnalysis },
  { path: '/strategy/agents/:id/summary', component: AgentDetailSummary },
  { path: '/strategy/agents/feishu', component: FeishuPushLogs },
  { path: '/strategy/agents/feishu/edit', component: FeishuPush },
  { path: '/strategy/agents/feishu/history', component: FeishuPushHistory },
  // youzi_agents 子路由（与上方 agents 子路由共用相同组件，URL 统一使用 youzi_agents 前缀）
  { path: '/strategy/youzi_agents/intro', component: StrategyAgentsIntro },
  { path: '/strategy/youzi_agents/intro/principles', component: StrategyAgentsIntroPrinciples },
  { path: '/strategy/youzi_agents/:id', component: AgentHoldings },
  { path: '/strategy/youzi_agents/:id/analysis', component: AgentAnalysis },
  { path: '/strategy/youzi_agents/:id/summary', component: AgentDetailSummary },
  { path: '/strategy/youzi_agents/feishu', component: FeishuPushLogs },
  { path: '/strategy/youzi_agents/feishu/edit', component: FeishuPush },
  { path: '/strategy/youzi_agents/feishu/history', component: FeishuPushHistory },
  // 小鳄鱼独立页面
  { path: '/strategy/youzi_agents/xiaoyueyu', component: XiaoyueyuTrader },
  // 钧哥独立页面
  { path: '/strategy/youzi_agents/jun', component: JunGeTrader },
  // 陈小群独立页面
  { path: '/strategy/youzi_agents/chenxiaoqun', component: ChenxiaoqunTrader },
  { path: '/strategy/backtest', component: Backtest },
  { path: '/strategy/factor-prompt', component: FactorPrompt },
  { path: '/ticai', component: Ticai },
  { path: '/ticai/history', component: TicaiHistory },
  { path: '/ticai/performance', component: TicaiPerformance },
  { path: '/tasks', component: TaskDashboard },
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
