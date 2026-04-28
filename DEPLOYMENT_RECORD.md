# 部署记录文档

## 服务器信息

- **服务器IP**: 111.229.238.115
- **SSH端口**: 22
- **应用端口**: 5002
- **SSH密钥**: `~/.ssh/fasstock`
- **容器名称**: stock_scanner

## 部署命令

```bash
# 本地打包
tar --exclude='.git' --exclude='node_modules' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' --exclude='venv' --exclude='dist' --exclude='frontend/node_modules' --exclude='frontend/.vite' --exclude='.env' --exclude='*.log' -czf /tmp/stock-scanner.tar.gz -C /Users/kevin/Desktop/facSstock . 2>/dev/null

# 上传到服务器
scp -i ~/.ssh/fasstock -o ConnectTimeout=30 /tmp/stock-scanner.tar.gz root@111.229.238.115:/tmp/

# 服务器解压并重启
ssh -i ~/.ssh/fasstock -o ConnectTimeout=15 root@111.229.238.115 "cd /opt/stock-scanner && tar -xzf /tmp/stock-scanner.tar.gz && rm /tmp/stock-scanner.tar.gz && cd deploy/docker && docker compose up -d --build"
```

## 查看日志

```bash
ssh -i ~/.ssh/fasstock root@111.229.238.115 "docker logs stock_scanner --tail 50"
```

## 查看容器状态

```bash
ssh -i ~/.ssh/fasstock root@111.229.238.115 "docker ps -a | grep stock"
```

## 测试API

```bash
# 测试指数
curl "http://111.229.238.115:5002/api/market/overview"

# 测试板块
curl "http://111.229.238.115:5002/api/market/sectors"

# 测试板块资金流
curl "http://111.229.238.115:5002/api/market/sectors/main-fund-flow"

# 测试股票搜索
curl "http://111.229.238.115:5002/api/stocks/search?q=茅台&limit=5"
```

---

# 近期修复记录

## 1. 股票搜索功能修复 (2026-04-07)

### 问题
自选股票无法进行股票搜索，搜索结果为空。

### 原因
`strategy_routes.py` 中的 `sync_stocks()` 函数错误地调用了 akshare 的 `stock_info_a_code_name()` API：
```python
# 错误写法
df_sh = _ak.stock_info_a_code_name(market="SH")  # akshare不支持market参数
```

### 修复
该API无需参数，直接调用即可返回沪深京A股列表：
```python
# 正确写法
df_all = _ak.stock_info_a_code_name()  # 直接调用，返回全部A股
```

### 修改文件
- `strategy_routes.py` (行1906-1998)

---

## 2. 大盘指数数据修复 (2026-04-07)

### 问题
大盘指数API返回空数据。

### 原因
服务器无法访问东方财富的 `push2.eastmoney.com` 接口（网络封锁），且新浪API使用 `params` 传参时URL编码不正确。

### 修复
改用新浪API，直接在URL中拼接参数：
```python
# 错误写法
resp = cr.get(url, params={'list': codes_str})  # 逗号被编码为%2C

# 正确写法
url = 'https://hq.sinajs.cn/list=' + codes_str
resp = cr.get(url, impersonate='chrome110', headers={'Referer': 'https://finance.sina.com.cn'})
```

### 修改文件
- `market_data.py` - `get_market_overview()` 函数

---

## 3. 板块数据修复 (2026-04-07)

### 问题
板块数据正常（akshare的东方财富接口可访问）

### 保持不变
- `market_data.py` - `get_hot_sectors()` 函数
- `market_data.py` - `get_hot_concept_sectors()` 函数

---

## 4. 板块资金流入数据修复 (2026-04-07)

### 问题
板块资金流入API返回空数据。

### 原因
服务器无法访问东方财富的 `push2.eastmoney.com` 接口，无法获取真实的主力净流入数据。

### 修复
改用已有的板块涨跌排行数据作为替代，显示涨跌幅最大的前3和后3板块：
```python
# 获取板块涨跌数据
sectors_data = get_hot_sectors()  # 调用同文件的板块数据函数
sorted_sectors = sorted(sectors_data, key=lambda x: float(x.get('change', 0) or 0), reverse=True)
```

### 修改文件
- `market_data.py` - `get_sector_main_fund_flow()` 函数

---

## 5. 移除北向净流入显示 (2026-04-07)

### 问题
北向资金数据由于服务器网络限制无法获取。

### 修复
从首页状态栏移除北向净流入的显示：
- 移除模板中的 `北向净流入` 标签和相关代码
- 移除 `flow` 变量和相关计算
- 移除 `loadFlow()` 函数调用
- 移除相关CSS样式

### 修改文件
- `frontend/src/views/Home.vue`

---

## 6. Dockerfile pip源修复 (2026-04-07)

### 问题
阿里云pip镜像源超时，Docker构建失败。

### 修复
改用清华大学pip镜像源，并增加超时时间：
```dockerfile
# 修复前
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip install --no-cache-dir -r requirements.txt gunicorn

# 修复后
RUN pip install --no-cache-dir --default-timeout=300 -i https://pypi.tuna.tsinghua.edu.cn/simple/ -r requirements.txt gunicorn || \
    pip install --no-cache-dir --default-timeout=300 -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt gunicorn
```

### 修改文件
- `deploy/docker/Dockerfile`

---

# 当前状态

## 可用功能 ✅

| 功能 | 状态 | 数据来源 |
|------|------|----------|
| 股票搜索 | ✅ 正常 | 数据库 + akshare同步 |
| 大盘指数 | ✅ 正常 | 新浪API |
| 板块涨跌 | ✅ 正常 | akshare |
| 板块资金流入 | ⚠️ 部分可用 | 使用板块涨跌代替 |
| 北向资金 | ❌ 已移除 | 无 |

## 网络限制说明

服务器无法直接访问以下域名：
- `push2.eastmoney.com` - 东方财富实时行情接口
- 部分A股实时数据接口

如有需要，可通过配置HTTP代理绕过：
```yaml
# docker-compose.yml
environment:
  - HTTP_PROXY=${HTTP_PROXY:-}
  - HTTPS_PROXY=${HTTPS_PROXY:-}
```

---

# 数据库信息

- **数据库**: MySQL
- **主机**: host.docker.internal:3306
- **数据库名**: stock_scanner
- **用户名**: root
- **密码**: StockPass@2024

### 常用SQL

```bash
# 连接数据库
ssh -i ~/.ssh/fasstock root@111.229.238.115
mysql -u root -p'StockPass@2024' stock_scanner

# 查看股票数量
SELECT COUNT(*) FROM stocks;

# 查看股票列表
SELECT name, code FROM stocks LIMIT 10;
```

---

# 股票同步API

```bash
# 触发同步
curl -X POST "http://111.229.238.115:5002/api/stocks/sync"

# 同步后查看股票数量
curl "http://111.229.238.115:5002/api/stocks/search?q=茅台"
```

---

# 前端构建

前端代码位于 `frontend/` 目录，在Docker构建时会自动构建并打包到容器中。

如需单独构建前端：
```bash
cd frontend
npm install
npm run build
```

---

*最后更新: 2026-04-09*

---

## 9. 量化回测模块 (2026-04-08)

### 功能
在策略中心新增「量化回测」入口，用户选择指标模板、股票代码、时间范围后，系统拉取 K 线进行历史回测，结果用 lightweight-charts 可视化。

### 回测指标（TA-Lib，pandas 降级）

| ID | 名称 | 可调参数 |
|----|------|---------|
| `ma_cross` | 均线交叉 | 快速均线周期、慢速均线周期 |
| `rsi_extreme` | RSI 超买超卖 | RSI 周期、买入阈值、卖出阈值 |
| `bollinger_break` | 布林带突破 | 布林周期、标准差倍数 |
| `macd_cross` | MACD 金叉死叉 | 无 |
| `kdj_extreme` | KDJ 超买超卖 | K 周期、超卖线、超买线 |
| `atr_trailing` | ATR 追踪止损 | ATR 周期、ATR 倍数 |

### 可视化输出
- **权益曲线**：总资金随时间变化
- **回撤曲线**：最大回撤百分比
- **K 线图**：含买入（橙）卖出（紫）标注
- **交易记录表**：每笔买入日期/价、卖出日期/价、收益率、持仓天数

### 技术实现
- 后端：`utils/backtest_engine.py`（talib 指标计算 + pandas 逐日模拟，无需 backtrader）
- 接口：`/api/backtest/catalog`（模板列表）、`/api/backtest/run`（执行回测）
- 前端：`Backtest.vue`（lightweight-charts v5 可视化）
- 数据源：新浪 K 线接口，每次请求独立拉取，不持久化

### 新增文件
- `utils/backtest_engine.py` — 回测引擎核心
- `frontend/src/api/backtest.js` — 回测 API 模块
- `frontend/src/views/Backtest.vue` — 回测前端页面

### 修改文件
- `strategy_routes.py` — 新增 `/api/backtest/*` 路由
- `frontend/src/main.js` — 路由 `/strategy/backtest`
- `frontend/src/views/Strategy.vue` — 策略中心入口卡片

---

## 7. TradingView 图表 404 修复 (2026-04-08)

### 问题
点击股票详情页的 TradingView H5 图表，页面空白，数据加载不出来。

### 原因
- `charting_library/` 目录下有一层嵌套子目录 `charting_library/charting_library/`
- `charting_library.standalone.js`（TV 核心引擎）在子目录里
- `mobile_white.html` 的 `library_path` 配置为 `'charting_library/'`
- TV 请求 `/charting_library/charting_library.standalone.js` → 旧版 `serve_charting_library` 只在根目录查找 → **404** → 图表无法初始化

### 修复
1. `deploy/docker/Dockerfile`：构建时自动将 TV 核心 JS 复制到根目录 `charting_library/` 下
2. `app.py`：`serve_charting_library` 同时在根目录和子目录查找文件（双重兜底）
3. 生产环境：已将 `charting_library.standalone.js` 等文件复制到容器内正确位置

### 修改文件
- `deploy/docker/Dockerfile`
- `app.py`

### 验证命令
```bash
curl -I http://111.229.238.115:5002/charting_library/charting_library.standalone.js
# 应返回 HTTP 200

curl http://111.229.238.115:5002/tv_udf/history?symbol=SSE:600519&resolution=1D&to=$(date +%s)&countback=5
# 应返回 {"s":"ok", "t":[...], "c":[...]}
```

---

## 8. 首页迷你走势图三线重复修复 (2026-04-08)

### 问题
首页三大指数（上证/深证/创业板）的迷你走势图三条线看起来完全相同。

### 原因
模板内直接调用普通函数 `buildMiniPath(item.symbol)` 画 SVG path，Vue 对深层嵌套的 `indexMiniData[symbol]` 依赖追踪不精确，三个 `<path>` 可能复用同一份渲染结果。

### 修复
- 改用 `computed` 按 symbol 预先计算 `indexSparkPaths`
- 给 `<path>` 加 `:key="'idx-spark-' + item.symbol"`，确保每个指数独立更新

### 修改文件
- `frontend/src/views/Home.vue`

---

## 11. SPA 路由 fallback 修复 (2026-04-09)

### 问题
点击策略中心的「自定义因子」卡片无法跳转，页面无响应。

### 原因
`/frontend/<path:filename>` 路由直接从 DIST_DIR 查找文件，Vue Router 的前端路由路径（如 `strategy/factor-prompt`）在磁盘上没有对应文件，导致 404。

### 修复
在 `serve_frontend_assets` 中加入 SPA fallback：文件存在则返回文件，否则返回 `index.html`，由 Vue Router 接管路由。

### 修改文件
- `app.py` - `serve_frontend_assets` 函数

---

## 10. compute_macro_sentiment abs() 类型错误修复 (2026-04-09)

### 问题
当上证指数下跌时，`compute_macro_sentiment()` 抛出 `TypeError: bad operand type for abs(): 'str'`。

### 原因
`_fmt()` 返回字符串，对字符串调用 `abs()` 会报错。

### 修复
```python
# 错误写法
f'上证指数跌 {abs(_fmt(sh_change))}%，'

# 正确写法
f'上证指数跌 {_fmt(abs(sh_change))}%，'
```

### 修改文件
- `market_data.py` 第1351行

---

## 12. Docker env_file 配置缺失 (2026-04-27)

### 问题
Agent 的 AI 分析功能报错 "未配置 API Key（DASHSCOPE_API_KEY 和 DEEPSEEK_API_KEY 均未设置）"

### 原因
1. `docker-compose.yml` 没有配置 `env_file: .env`，导致容器启动时没有加载环境变量
2. 打包脚本错误地排除了 `.env` 文件

### 修复
1. `deploy/docker/docker-compose.yml` 添加 `env_file: .env` 配置
2. 打包命令移除 `--exclude='.env'`

### 修改文件
- `deploy/docker/docker-compose.yml` - 添加 `env_file: .env`
- `DEPLOYMENT.md` - 更新部署文档

### 验证命令
```bash
# 检查容器内环境变量
docker exec stock_scanner env | grep DASHSCOPE
# 应输出: DASHSCOPE_API_KEY=sk-xxx
```
