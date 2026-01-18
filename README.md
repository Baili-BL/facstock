# 布林带收缩策略 - 热点板块筛选器

## 策略原理

布林带收缩（Bollinger Squeeze）是一种经典的技术分析策略，用于识别股票价格即将出现大幅波动的时机。

### 核心逻辑

1. **计算布林带**：基于20日移动平均线，上下轨为2倍标准差
2. **计算带宽**：上轨与下轨之间的距离（百分比形式）
3. **收缩信号**：带宽的5日均值 < 10日均值，表示波动性正在收缩
4. **连续收缩**：连续多日满足收缩条件，预示可能即将出现突破

### 策略参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| period | 20 | 布林带计算周期 |
| std_dev | 2.0 | 标准差倍数 |
| ma_short | 5 | 带宽短期均线 |
| ma_long | 10 | 带宽长期均线 |
| min_squeeze_days | 3 | 最小连续收缩天数 |

## 安装

```bash
pip install -r requirements.txt
```

## 使用方法

### 1. 扫描热点板块（默认）

```bash
python bollinger_squeeze_strategy.py --mode hot
```

### 2. 扫描全市场

```bash
python bollinger_squeeze_strategy.py --mode all
```

### 3. 自定义参数

```bash
# 扫描前10个热点板块
python bollinger_squeeze_strategy.py --mode hot --sectors 10

# 调整布林带参数
python bollinger_squeeze_strategy.py --period 26 --std 2.5

# 调整收缩判断参数
python bollinger_squeeze_strategy.py --ma-short 5 --ma-long 10 --min-days 5
```

### 4. 完整参数列表

```bash
python bollinger_squeeze_strategy.py --help
```

参数说明：
- `--mode`: 扫描模式，`hot`=热点板块，`all`=全市场
- `--sectors`: 热点板块数量（默认5）
- `--period`: 布林带周期（默认20）
- `--std`: 标准差倍数（默认2.0）
- `--ma-short`: 带宽短期均线（默认5）
- `--ma-long`: 带宽长期均线（默认10）
- `--min-days`: 最小连续收缩天数（默认3）
- `--limit`: 限制扫描数量（测试用）

## 输出说明

| 字段 | 说明 |
|------|------|
| 代码 | 股票代码 |
| 名称 | 股票名称 |
| 收盘价 | 最新收盘价 |
| 带宽% | 当前布林带宽度百分比 |
| MA5 | 带宽5日均值 |
| MA10 | 带宽10日均值 |
| 收缩比 | MA5/MA10 × 100%，越小表示收缩越明显 |
| 收缩天数 | 连续收缩天数 |
| 涨跌幅 | 今日涨跌幅 |

## 注意事项

1. **数据来源**：使用 akshare 获取A股数据，需要网络连接
2. **扫描时间**：建议在交易日收盘后运行，数据更准确
3. **风险提示**：此策略仅供参考，不构成投资建议

## 策略解读

- **收缩比 < 90%**：收缩较为明显
- **收缩比 < 80%**：收缩非常明显，需重点关注
- **收缩天数 >= 5**：持续收缩，突破概率增加

布林带收缩后，股价通常会选择方向突破。结合成交量、趋势等其他指标，可以更好地判断突破方向。
# facstock
