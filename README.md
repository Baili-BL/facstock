# 布林带收缩策略 - 热点板块筛选器

[![GitHub](https://img.shields.io/badge/GitHub-Baili--BL%2Ffacstock-blue)](https://github.com/Baili-BL/facstock)
[![Gitee](https://img.shields.io/badge/Gitee-Baili--BL%2Ffacstock-red)](https://gitee.com/Baili-BL/facstock)

## 策略原理

布林带收缩（Bollinger Squeeze）是一种经典的技术分析策略，用于识别股票价格即将出现大幅波动的时机。

### 核心逻辑

1. **计算布林带**：基于20日移动平均线，上下轨为2倍标准差
2. **计算带宽**：上轨与下轨之间的距离（百分比形式）
3. **收缩信号**：带宽的5日均值 < 10日均值，表示波动性正在收缩
4. **连续收缩**：连续多日满足收缩条件，预示可能即将出现突破

### 数据源

- **行业板块排行**：同花顺 (https://q.10jqka.com.cn/thshy/)
- **行业成分股**：同花顺爬虫
- **K线数据**：同花顺日K接口

### 综合评分系统

| 维度 | 权重 | 说明 |
|------|------|------|
| 收缩强度 | 30分 | 带宽收窄程度和连续天数 |
| 趋势得分 | 25分 | MA5>MA10>MA20>MA60 多头排列 |
| 动量得分 | 20分 | MACD金叉、RSI中性区间 |
| 位置得分 | 15分 | 价格在布林带中轨之上 |
| 人气得分 | 10分 | 换手率活跃度 |

---

## 快速部署

### 方式一：Docker 部署（推荐）

```bash
# 1. 在 Mac 终端连接服务器
ssh root@<服务器IP>

# 2. 克隆代码（国内用 ghproxy 加速）
git clone https://ghproxy.com/https://github.com/Baili-BL/facSstock.git /opt/stock-scanner

# 3. 一键部署
cd /opt/stock-scanner/deploy/docker
chmod +x install.sh && ./install.sh

# 4. 访问
http://<服务器IP>:5001
```

**更新代码：**
```bash
# 方式1：git pull（网络好时）
cd /opt/stock-scanner && git pull
cd deploy/docker && docker compose up -d --build

# 方式2：rsync 上传（更稳定，在 Mac 执行）
rsync -avz --exclude='__pycache__/' --exclude='.git/' --exclude='venv/' \
  ~/Desktop/facSstock/ root@<服务器IP>:/opt/stock-scanner/
# 然后服务器上：cd /opt/stock-scanner/deploy/docker && docker compose up -d --build
```

**常用命令：**
```bash
cd /opt/stock-scanner/deploy/docker
docker compose ps          # 查看状态
docker compose logs -f app # 查看日志
docker compose restart     # 重启
docker compose down        # 停止
```

**常见问题见：** [deploy/MANUAL_DEPLOY.md](deploy/MANUAL_DEPLOY.md)

### 方式二：腾讯云部署（传统方式）

详见 [deploy/MANUAL_DEPLOY.md](deploy/MANUAL_DEPLOY.md)

```bash
# 一键部署
git clone https://github.com/Baili-BL/facSstock.git /opt/stock-scanner
cd /opt/stock-scanner/deploy/tencent
chmod +x install.sh && ./install.sh
```

### 方式三：火山引擎部署

详见 [deploy/volcengine/DEPLOY.md](deploy/volcengine/DEPLOY.md)

```bash
# 一键部署
git clone https://github.com/Baili-BL/facSstock.git /opt/stock-scanner
cd /opt/stock-scanner/deploy/volcengine
chmod +x install.sh && ./install.sh
```

---

## 本地开发

### 安装

```bash
# 从 GitHub 克隆
git clone https://github.com/Baili-BL/facstock.git

# 或从 Gitee 克隆（国内更快）
git clone https://gitee.com/Baili-BL/facstock.git

cd facstock
pip install -r requirements.txt
```

### MySQL 数据库配置

项目使用 MySQL 存储扫描结果和缓存数据。

**macOS 安装 MySQL：**
```bash
brew install mysql@8.0
brew services start mysql@8.0
```

**创建数据库：**
```bash
mysql -u root -e "CREATE DATABASE IF NOT EXISTS stock_scanner CHARACTER SET utf8mb4;"
```

**环境变量配置（可选）：**
```bash
export MYSQL_HOST=localhost      # 默认 localhost
export MYSQL_PORT=3306           # 默认 3306
export MYSQL_USER=root           # 默认 root
export MYSQL_PASSWORD=           # 默认空
export MYSQL_DATABASE=stock_scanner  # 默认 stock_scanner
```

> 程序启动时会自动创建所需的表结构

### 启动 Web 界面

```bash
python app.py
# 访问 http://localhost:5001
```

### 命令行使用

```bash
# 扫描热点板块
python bollinger_squeeze_strategy.py --mode hot

# 扫描全市场
python bollinger_squeeze_strategy.py --mode all

# 自定义参数
python bollinger_squeeze_strategy.py --mode hot --sectors 10 --min-days 5
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--mode` | hot | 扫描模式：hot=热点板块，all=全市场 |
| `--sectors` | 5 | 热点板块数量 |
| `--period` | 20 | 布林带周期 |
| `--std` | 2.0 | 标准差倍数 |
| `--ma-short` | 5 | 带宽短期均线 |
| `--ma-long` | 10 | 带宽长期均线 |
| `--min-days` | 3 | 最小连续收缩天数 |

---

## 输出说明

| 字段 | 说明 |
|------|------|
| 代码 | 股票代码 |
| 名称 | 股票名称 |
| 评分 | 综合评分（满分100） |
| 等级 | S/A/B/C 等级 |
| 带宽% | 当前布林带宽度百分比 |
| 收缩天数 | 连续收缩天数 |
| 量比 | 成交量/5日均量 |
| 涨跌幅 | 今日涨跌幅 |

---

## 注意事项

1. **数据来源**：使用 akshare 获取A股数据，需要网络连接
2. **扫描时间**：建议在交易日收盘后运行，数据更准确
3. **风险提示**：此策略仅供参考，不构成投资建议

---

## 项目结构

```
facstock/
├── app.py                        # Flask Web 应用
├── bollinger_squeeze_strategy.py # 策略核心代码
├── requirements.txt              # 依赖列表
├── templates/
│   └── index.html               # 前端页面
├── deploy/
│   └── MANUAL_DEPLOY.md         # 详细部署文档
└── README.md
```

---

## License

MIT License
