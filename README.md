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

### 综合评分系统

| 维度 | 权重 | 说明 |
|------|------|------|
| 收缩强度 | 30分 | 带宽收窄程度和连续天数 |
| 趋势得分 | 25分 | MA5>MA10>MA20>MA60 多头排列 |
| 动量得分 | 20分 | MACD金叉、RSI中性区间 |
| 位置得分 | 15分 | 价格在布林带中轨之上 |
| 人气得分 | 10分 | 换手率活跃度 |

---

## 腾讯云部署

> 详细部署文档见 [deploy/MANUAL_DEPLOY.md](deploy/MANUAL_DEPLOY.md)

### 快速开始

#### 首次部署（3步）

```bash
# 1. 克隆代码（GitHub 或 Gitee 二选一）
git clone https://github.com/Baili-BL/facSstock.git ~/facSstock
# 或
git clone https://gitee.com/Baili-BL/facSstock.git ~/facSstock

# 2. 安装环境
conda create -y -n facstock_env python=3.10
conda activate facstock_env
pip install -r ~/facSstock/requirements.txt gunicorn

# 3. 启动服务
cd ~/facSstock
gunicorn -w 2 -b 0.0.0.0:5001 app:app
```

访问：`http://服务器IP:5001`

#### 更新部署（2步）

**方式一：本地上传**
```bash
# Mac 本地执行（使用 rsync 保留数据库）
rsync -av --exclude='data/' --exclude='__pycache__/' \
    /Users/kevin/Desktop/facSstock/ root@111.229.238.115:/opt/facstock/

# 服务器执行
supervisorctl restart facstock
```

**方式二：Git 拉取**
```bash
# 服务器执行（保留数据库）
cd ~/facSstock && git pull origin main
rsync -av --exclude='data/' ~/facSstock/ /opt/facstock/
supervisorctl restart facstock
```

> **重要**：使用 `rsync --exclude='data/'` 保留数据库，避免扫描历史被覆盖

### 常用命令

```bash
# 查看服务状态
supervisorctl status

# 重启服务
supervisorctl restart facstock

# 查看日志
tail -f /opt/facstock/logs/supervisor_out.log
```

### 腾讯云安全组配置

在腾讯云控制台 → 安全组 → 添加入站规则：

| 协议 | 端口 | 来源 | 说明 |
|------|------|------|------|
| TCP | 22 | 0.0.0.0/0 | SSH |
| TCP | 80 | 0.0.0.0/0 | HTTP |
| TCP | 5001 | 0.0.0.0/0 | facstock |
| TCP | 5002 | 0.0.0.0/0 | Ticai（如需） |

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
