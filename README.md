# 布林带收缩策略 - 热点板块筛选器

[![GitHub](https://img.shields.io/badge/GitHub-Baili--BL%2Ffacstock-blue)](https://github.com/Baili-BL/facstock)

## 策略原理

布林带收缩（Bollinger Squeeze）是一种经典的技术分析策略，用于识别股票价格即将出现大幅波动的时机。

### 核心逻辑

1. **计算布林带**：基于20日移动平均线，上下轨为2倍标准差
2. **计算带宽**：上轨与下轨之间的距离（百分比形式）
3. **收缩信号**：带宽的5日均值 < 10日均值，表示波动性正在收缩
4. **连续收缩**：连续多日满足收缩条件，预示可能即将出现突破

### 综合评分系统

| 维度 | 权重 | 说明 |
|------|------|------|
| 收缩强度 | 30分 | 带宽收窄程度和连续天数 |
| 趋势得分 | 25分 | MA5>MA10>MA20>MA60 多头排列 |
| 动量得分 | 20分 | MACD金叉、RSI中性区间 |
| 位置得分 | 15分 | 价格在布林带中轨之上 |
| 人气得分 | 10分 | 换手率活跃度 |

---

## 🚀 腾讯云部署

### 方式一：一键部署（推荐）

SSH 登录腾讯云服务器后，执行：

```bash
# 下载并执行部署脚本
git clone https://github.com/Baili-BL/facstock.git /tmp/facstock
cd /tmp/facstock/deploy
chmod +x deploy.sh
sudo ./deploy.sh
```

部署完成后访问：`http://服务器IP:5001`

### 方式二：手动部署

```bash
# 1. 安装依赖
sudo apt update
sudo apt install -y git python3.10 python3.10-venv python3-pip nginx supervisor

# 2. 克隆代码
sudo git clone https://github.com/Baili-BL/facstock.git /opt/facstock

# 3. 创建虚拟环境
cd /opt/facstock
sudo python3.10 -m venv venv
sudo ./venv/bin/pip install -r requirements.txt

# 4. 启动应用
sudo ./venv/bin/gunicorn -w 2 -b 0.0.0.0:5001 app:app --daemon

# 5. 开放端口（腾讯云安全组也要开放）
sudo ufw allow 5001/tcp
```

### 同一台服务器部署多个应用

编辑 `deploy/deploy_multi.sh`，配置多个应用：

```bash
APPS=(
    "facstock:5001:main"        # 应用1: 端口5001
    "facstock_test:5002:develop" # 应用2: 端口5002
    "facstock_v2:5003:v2"       # 应用3: 端口5003
)
```

然后执行：

```bash
chmod +x deploy/deploy_multi.sh
sudo ./deploy/deploy_multi.sh
```

### 常用管理命令

```bash
# 查看应用状态
sudo supervisorctl status

# 重启应用
sudo supervisorctl restart facstock

# 查看日志
tail -f /opt/facstock/logs/supervisor_out.log

# 更新代码
cd /opt/facstock
sudo git pull origin main
sudo supervisorctl restart facstock
```

### 腾讯云安全组配置

在腾讯云控制台 → 安全组 → 添加入站规则：

| 协议 | 端口 | 来源 | 说明 |
|------|------|------|------|
| TCP | 22 | 0.0.0.0/0 | SSH |
| TCP | 80 | 0.0.0.0/0 | HTTP |
| TCP | 5001 | 0.0.0.0/0 | 应用1 |
| TCP | 5002 | 0.0.0.0/0 | 应用2（如需） |

---

## 💻 本地开发

### 安装

```bash
git clone https://github.com/Baili-BL/facstock.git
cd facstock
pip install -r requirements.txt
```

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

## 📊 输出说明

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

## ⚠️ 注意事项

1. **数据来源**：使用 akshare 获取A股数据，需要网络连接
2. **扫描时间**：建议在交易日收盘后运行，数据更准确
3. **风险提示**：此策略仅供参考，不构成投资建议

---

## 📁 项目结构

```
facstock/
├── app.py                      # Flask Web 应用
├── bollinger_squeeze_strategy.py # 策略核心代码
├── requirements.txt            # 依赖列表
├── templates/
│   └── index.html             # 前端页面
├── deploy/
│   ├── deploy.sh              # 单应用部署脚本
│   ├── deploy_multi.sh        # 多应用部署脚本
│   ├── update.sh              # 更新脚本
│   └── quick_install.sh       # 一键安装脚本
└── README.md
```

---

## License

MIT License
