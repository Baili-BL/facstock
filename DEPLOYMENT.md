# 股票扫描器部署文档

## 部署信息

- **服务器**: 111.229.238.115
- **端口**: 5002
- **容器名**: stock_scanner
- **SSH密钥**: `~/.ssh/fasstock`
- **部署目录**: `/opt/stock-scanner`

## 快速部署命令

```bash
# 打包
tar --exclude='.git' --exclude='node_modules' --exclude='__pycache__' --exclude='*.pyc' --exclude='.venv' --exclude='venv' --exclude='dist' --exclude='frontend/node_modules' --exclude='frontend/.vite' --exclude='.env' --exclude='*.log' -czf /tmp/stock-scanner.tar.gz -C /Users/kevin/Desktop/facSstock . 2>/dev/null

# 上传并构建
scp -i ~/.ssh/fasstock /tmp/stock-scanner.tar.gz root@111.229.238.115:/tmp/
ssh -i ~/.ssh/fasstock root@111.229.238.115 "cd /opt/stock-scanner && tar -xzf /tmp/stock-scanner.tar.gz && rm /tmp/stock-scanner.tar.gz && cd deploy/docker && docker compose up -d --build"

# 查看日志
ssh -i ~/.ssh/fasstock root@111.229.238.115 "docker logs stock_scanner -f"

# 重启容器
ssh -i ~/.ssh/fasstock root@111.229.238.115 "docker restart stock_scanner"
```

## 数据库信息

- **主机**: host.docker.internal (宿主机MySQL)
- **端口**: 3306
- **用户**: root
- **密码**: StockPass@2024
- **数据库**: stock_scanner

## API端点

| API | 路径 | 说明 |
|-----|------|------|
| 股票搜索 | `/api/stocks/search?q=关键词&limit=20` | 搜索A股 |
| 股票同步 | `POST /api/stocks/sync` | 同步股票数据到数据库 |
| 大盘指数 | `/api/market/overview` | 上证、深证等指数 |
| 板块数据 | `/api/market/sectors` | 行业板块涨跌 |
| 板块资金流 | `/api/market/sectors/main-fund-flow` | 板块涨跌排行 |
| 涨跌停 | `/api/market/limit` | 涨停/跌停数据 |

## 已修复的问题

### 1. 股票搜索功能失效 (2026-04-07)
**问题**: akshare的`stock_info_a_code_name()` API不需要参数，代码错误地传入了`market`参数导致调用失败

**修复**:
```python
# 错误写法
df_sh = _ak.stock_info_a_code_name(market="SH")

# 正确写法
df_all = _ak.stock_info_a_code_name()  # 直接调用，无参数
```

### 2. 大盘指数无数据 (2026-04-07)
**问题**: 服务器无法访问东方财富的push2.eastmoney.com，使用新浪API替代

**修复**:
```python
# 直接在URL中拼接codes，不用params（避免逗号被编码）
codes_str = ','.join(needed.keys())
url = 'https://hq.sinajs.cn/list=' + codes_str
```

### 3. 板块资金流入无数据 (2026-04-07)
**问题**: push2.eastmoney.com网络不通，改用已有板块涨跌数据

**修复**: 利用已获取的`get_hot_sectors()`数据，按涨跌排序返回前3+后3

### 4. 移除北向资金显示 (2026-04-07)
**原因**: 服务器无法获取北向资金数据，从首页移除显示

**修改文件**: `frontend/src/views/Home.vue`
- 移除`北向净流入`标签
- 移除`flow`相关变量和调用

## 服务器网络限制

由于服务器IP被部分金融网站封锁，以下功能暂时无法获取真实数据：

| 功能 | 原因 | 替代方案 |
|------|------|----------|
| 板块主力净流入 | push2.eastmoney.com被封锁 | 使用板块涨跌排行 |
| 北向资金 | push2.eastmoney.com被封锁 | 已移除显示 |
| 大盘成交量 | 东方财富API不通 | 设为0 |
| 全A股现货数据 | 东方财富+新浪均不通 | 使用数据库缓存 |

## 可用的数据源

| 数据源 | 状态 | 说明 |
|--------|------|------|
| 新浪hq.sinajs.cn | ✅ 可用 | 指数、个股行情 |
| 腾讯qt.gtimg.cn | ✅ 可用 | 部分行情数据 |
| 东方财富push2 | ❌ 封锁 | 无法访问 |
| akshare(东财) | ❌ 封锁 | 无法访问 |
| akshare(新浪) | ⚠️ 不稳定 | 可能返回空数据 |

## 数据库股票数量

- 当前存储: **5497条** A股数据
- 同步命令: `curl -X POST http://111.229.238.115:5002/api/stocks/sync`
