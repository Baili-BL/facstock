# FacSstock 前端（Vue 3）

## 技术栈

- **Vue 3** + **Vue Router 4** + **Vite 6**
- 与后端 Flask 通过 RESTful API 通信

## 目录结构

```
frontend/
├── index.html          # Vue SPA 入口
├── vite.config.js     # Vite 配置（含 API 代理）
├── package.json
└── src/
    ├── main.js              # Vue 实例挂载 + 路由注册
    ├── App.vue              # 根组件（含底部导航）
    ├── api/
    │   ├── market.js        # /api/market/* 接口封装
    │   ├── strategy.js      # /api/scan/* /api/watchlist/* 接口封装
    │   └── ticai.js         # /api/ticai/* 接口封装
    ├── components/
    │   └── BottomNav.vue    # 底部 Tab 导航（大盘/板块/策略）
    └── views/               # 页面组件
        ├── Home.vue              # 首页（大盘概览）
        ├── Sectors.vue           # 板块页
        ├── Strategy.vue          # 策略中心
        ├── Bollinger.vue         # 布林带策略（iframe 过渡）
        ├── AIStrategy.vue        # AI 策略（iframe 过渡）
        ├── Ticai.vue             # 题材挖掘（iframe 过渡）
        ├── TicaiHistory.vue      # 题材历史报表
        └── TicaiPerformance.vue  # 题材收益统计
```

## 启动方式

### 方式一：独立开发（推荐）

前后端分开运行，互不影响：

```bash
# 后端 Flask（端口 5001）
MYSQL_PASSWORD="StockPass2024" python3 app.py

# 前端 Vite（端口 5173，自动代理 /api/* 等到 Flask）
cd frontend && npm install
npm run dev
# 访问 http://localhost:5173
```

### 方式二：直接构建（生产部署）

```bash
cd frontend
npm install
npm run build        # 输出到 ../dist/
```

构建后访问 `http://localhost:5001/frontend`（Flask 会自动从 `dist/` 夹回退）。

## 重要说明

1. **API 接口不变**：前端只调用已有的 `/api/*` 接口，不影响其他功能
2. **旧模板保留**：Flask 原有的 HTML 模板（`templates/`）完全不受影响
3. **iframe 过渡**：布林带/AI策略/题材挖掘页面暂时用 iframe 嵌入旧模板，后续逐步迁移到完整 Vue 组件
4. **底部导航**：大盘 → `/`、板块 → `/sectors`、策略 → `/strategy`（及其子路由）

## 新增依赖

```bash
cd frontend && npm install
```
