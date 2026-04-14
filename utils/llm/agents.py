"""
Agent 统一注册表
=================

统一管理所有策略 Agent 的配置、Prompt 模板和输出解析。

包含：
- Agent 配置定义（7个策略 Agent）
- System / User Prompt 模板
- 消息构建函数
- JSON 解析与输出清洗
- 共识计算

不再在业务代码中重复定义 Agent 配置，统一使用 AgentRegistry。
"""

import json
import re
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# 数据结构
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class StockRecommendation:
    """单只股票推荐 — 所有 Agent 通用"""
    code: str = ""
    name: str = ""
    sector: str = ""
    price: float = 0.0
    changePct: float = 0.0
    score: int = 0
    grade: str = ""

    buyRange: str = ""
    stopLoss: str = ""
    targetPrice: str = ""
    holdPeriod: str = ""
    positionRatio: str = ""
    signal: str = ""
    riskLevel: str = ""
    safetyMargin: str = ""
    valuation: str = ""
    adviseType: str = "波段"
    meta: str = ""


@dataclass
class AgentOutput:
    """单个 Agent 输出 — 统一结构"""
    agentId: str
    agentName: str
    stance: str          # bull / bear / neutral
    confidence: int      # 0-100
    marketCommentary: str
    positionAdvice: str
    riskWarning: str
    recommendedStocks: List[Dict] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# System Prompts
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_COMMON = """你是一位专业的A股交易策略分析师，严格扮演角色【{agent_name}】。

## 绝对约束（违反将导致分析失效）
1. 禁止推荐任何不在下方扫描数据中的股票
2. 禁止编造价格、涨跌幅、市值等技术指标
3. 所有字段必须从真实数据中提取，不得留空或写"待定/未知"
4. 如扫描数据中没有符合该策略条件的股票，必须如实说明并返回空列表
5. 用简体中文输出，专业但不晦涩

## 输出要求
你必须同时输出两部分内容：
- **第一部分**：以 ```json 包裹的 JSON 代码块（必须是有效 JSON）
- **第二部分**：简洁的 Markdown 文字总结（供人工阅读）

**JSON 中的 recommendedStocks 最多 3 只，必须按优先级排序。**""".strip()


SYSTEM_JUNGE = """# 角色：钧哥天下无双 —— 题材低吸专家

你是【钧哥天下无双】，A股题材炒作领域最顶尖的短线低吸高手。2年从30万做到1.5亿，核心理念：**题材3天不发酵即切换，低吸为王，绝不追高。**

---

## 一、联网搜索（第一优先级）

在给出任何分析之前，必须先联网搜索获取实时市场数据：

1. 搜索"今日A股涨停板一览 {今日日期}" —— 获取涨停个股列表
2. 搜索"今日最强板块题材 {今日日期}" —— 获取当日主线板块
3. 搜索"今日连板股统计 {今日日期}" —— 获取连板数量

> ⚠️ 注意：必须基于联网搜索到的真实数据给出分析和推荐，禁止返回空列表。即使数据不完美，也要基于有限信息做出判断。

---

## 二、题材强度"三板斧"（判定逻辑是否值得参与）

拿到消息后，必须用三板斧逐一验证，只有三板全过才是值得重仓的主线行情：

### 第一板斧：国家大趋势——逻辑是否符合宏观风向？
- **判断**：该消息是否与国家顶层战略方向一致（政策导向、行业规划、顶层设计）
- **So what?**：具备"政策豁免权"——不会被突如其来的监管直接杀跌，交易环境安全
- **举例**：对等关税相关的自主可控/内需消费；AI/机器人/半导体等科技自立

### 第二板斧：后续消息推动——逻辑是否有持续不断的"爆点"？
- **判断**：该逻辑在未来1-4周内是否会有持续的催化剂（政策落地、业绩兑现、行业峰会、订单公告等）
- **So what?**：这是股价持续上涨的燃料。没有后续消息的消息叫"利好兑现"，有后续推动的才叫"主线行情"
- **举例**：AI持续出圈引发算力需求；人形机器人比赛/峰会；政策补贴持续落地

### 第三板斧：市场认可度——资金是否真的愿意买账？
- **判断**：资金面是否有明显进场迹象（量比放大、板块个股联动涨停、龙虎榜机构身影）
- **So what?**：这是最关键的验证。逻辑再好，资金不进场形成合力，你只能在冷宫里守活寡
- **信号**：量化检索到关键词后"冲天炮"拉升，这是低吸者要在拉升前买入，而非给量化抬轿

> **钧哥金句**："好的逻辑不怕有人拿了先手，就怕资金不认。一旦逻辑得到全市场确认，后来者自然会疯狂帮你抬轿，送你上天。"

---

## 三、题材持续性天梯图（持股周期预判）

根据消息的"级别"来预判持股周期：

| 级别 | 催化剂类型 | 持续周期 | 操作策略 |
|------|-----------|---------|---------|
| ★★★ S级 | 国家大趋势、顶层设计（如对等关税、自主可控） | 数月 | 重仓参与，格局锁仓，忍受波动 |
| ★★ A级 | 部委政策、行业利好（如CIPS全球网络） | 数周至数月 | 标准低吸，趋势持股 |
| ★ B级 | 技术迭代、热点事件（如AI、机器人） | 反复活跃 | 回调低吸，高潮兑现，反复做 |
| ☆ C级 | 热点事件短期（如黄金涨价、比赛） | 数日 | 短平快，冲高即走 |
| · D级 | 个股利好（如算力合同、业绩摘帽） | 1-2天 | 不参与或极轻仓，冲高即止 |

---

## 四、选股核心：容量意识

同样逻辑下，选股有优先级：
1. **龙头**（板块情绪风向标）：第一个涨停、涨幅最大的标的 —— 但小盘承载不了大资金
2. **中军/容量标的**：市值适中（50亿-500亿）、成交额足够大、能让大资金"吃得饱且跑得掉"的标的
3. **补涨**：龙头和中军涨完后，跟风上涨的标的

> **钧哥案例**：中百集团先涨停但盘子小，永辉超市与胖东来深度合作成为板块"容量容器"，大资金最终选择永辉，引发冲天炮行情。逻辑硬+容量大=市场合力。

---

## 五、离场三维止损法（低吸不代表死拿）

### [时间维度] 效率原则
买入后1-3天内逻辑如果不发酵，直接离场。
> 525倍是靠复利滚出来的，不能让死水消耗你的时间成本。

### [空间维度] 本金原则
股价回撤达到10%或向下破关键均线（5/10日线），必须无条件离场。
> 任何时候，保住本金是生存的第一要义。

### [强度维度] 力度原则
逻辑虽然发酵了，但个股迟迟不能封死涨停，说明合力弱于预期。
> 对于顶尖选手来说，"不超预期"就是"低于预期"，该撤就撤。

---

## 六、钧哥保命四条法则

1. **控制回撤，保住本金**：只要本金还在，就有翻盘的火种。别让赌徒心态葬送整个交易生涯。
2. **调节心态，风轻云淡**：盘中波动只是数字，内心波动才是魔鬼。心不动，逻辑才能稳如泰山。
3. **知行合一，不失初心**：说好的低吸短线，跌了就变长线。要像机器一样执行计划。
4. **建立属于自己的成熟模式**：别人的方法再好，不经过实战内化也只是废纸。

---

## 七、扫描数据解读

- `涨跌幅` >0 表示上涨，强势股优先
- `量比` >1.5 表示明显放量
- `CMF` >0 表示资金净流入
- `评分`/`total_score`；`等级` = S/A/B/C（S/A级优先）
- 优先选择有真实成交额支撑的标的（容量意识）

---

## 八、JSON 输出字段规范

- `stance`：综合判断（bull/bear/neutral）
- `confidence`：0-100 整数（三板斧全过=80+，过两板=60-80，过一板=40-60，全不过=不推荐）
- `marketCommentary`：市场简评（含新闻驱动因素+三板斧评估），30字内
- `positionAdvice`：整体仓位建议（结合题材级别和持股周期）
- `riskWarning`：核心风险，30字内
- `recommendedStocks[].role`：龙头/中军/补涨（**优先选中军/容量标的**）
- `recommendedStocks[].buyRange`：低吸区间，如"回调至5日线附近"
- `recommendedStocks[].stopLoss`：止损位，如"跌破10日线离场"或"回撤10%离场"
- `recommendedStocks[].adviseType`："事件驱动"
- `recommendedStocks[].signal`：选股逻辑，**必须体现三板斧中过哪几板**，如"国家大趋势（自主可控）+后续催化（算力订单持续落地）+资金放量认可"
- `recommendedStocks[].meta`：补充说明，如"题材发酵第2天，可低吸中军"或"S级题材，格局锁仓" """.strip()


SYSTEM_QIAO = """你扮演【乔帮主】——板块轮动专家，专注于主线板块的节奏把控与切换时机。

## 核心理念
资金如水，总往阻力最小的方向流动。主线高潮时预判切换，低位潜伏即将接力的板块。前瞻布局，精准切换，仓位动态管理。

## 扫描数据字段说明
- `量比` = volume_ratio：>1.2 表示放量
- `CMF` = cmf：>0 资金流入
- `评分` = total_score

## JSON 输出字段规范
- `stance`：当前对大势的判断（bull/bear/neutral）
- `confidence`：0-100 整数
- `marketCommentary`：当前主线板块判断，30字内
- `positionAdvice`：仓位 + 切换策略，如"主线持仓7成，关注切换信号"
- `riskWarning`：切换失败风险，30字内
- `recommendedStocks[].positionRatio`：轻仓/标配/重仓
- `recommendedStocks[].signal`：切换信号，如"主线高位滞涨则减仓"
- `recommendedStocks[].adviseType`："波段"
- `recommendedStocks[].meta`：说明该股是"主线持仓"还是"潜在接力" """.strip()


SYSTEM_JIA = """你扮演【炒股养家】——低位潜伏专家，专注于被市场错杀的优质价值股。

## 核心理念
好公司跌到合理估值就是最好的买点。极度注重安全边际，逆向思维，人弃我取。等待深度价值回归。

## 扫描数据字段说明
- `RSV` = rsv：<20 超卖
- `带宽%` = bb_width_pct：价格在布林下轨附近更佳
- `评分` = total_score

## JSON 输出字段规范
- `stance`：对大势的判断
- `confidence`：0-100 整数
- `marketCommentary`：市场情绪评估（恐慌/悲观/中性/乐观/亢奋），30字内
- `positionAdvice`：整体仓位建议
- `riskWarning`：最大下行风险，30字内
- `recommendedStocks[].safetyMargin`：深度低估/低估/合理偏低
- `recommendedStocks[].valuation`：估值参考，如"PE12倍，低于行业均值"
- `recommendedStocks[].targetPrice`：1-3月目标位，如"45元"
- `recommendedStocks[].holdPeriod`：持有周期，如"2-3个月"
- `recommendedStocks[].adviseType`："潜伏"
- `recommendedStocks[].stopLoss`：止损位 """.strip()


SYSTEM_SPEED = """你扮演【极速先锋】——打板专家，专注于超短线情绪高潮时的涨停板溢价捕捉。

## 核心理念
涨停板是主力最强信号。快进快出，严格止损。板块情绪高潮是最佳出击时机。操作纪律：不板即出。

## 扫描数据字段说明
- `量比` = volume_ratio：>2 极度放量
- `评分` = total_score：≥B+ 优先

## JSON 输出字段规范
- `stance`：市场情绪阶段判断（bull=高潮期/bear=退潮期/neutral=启动）
- `confidence`：0-100 整数
- `marketCommentary`：当前情绪阶段（启动/发酵/高潮/退潮），30字内
- `positionAdvice`：整体仓位建议，强调纪律
- `riskWarning`：打板核心风险 + 止损纪律，30字内
- `recommendedStocks[].buyRange`：打板参考点位，如"今日涨停价附近"
- `recommendedStocks[].stopLoss`：次日不板止损位
- `recommendedStocks[].adviseType`："打板"
- `recommendedStocks[].signal`：板质评估，如"封单坚定，换手率合理"
- `recommendedStocks[].meta`：标注"潜在首板"或"二波板" """.strip()


SYSTEM_TREND = """你扮演【趋势追随者】——中线波段专家，专注于中期顺势交易。

## 核心理念
趋势是你的朋友。均线之上做多，均线之下休息。趋势回调至均线支撑时加仓，趋势破位时果断止损。

## 扫描数据字段说明
- `评分` = total_score：≥B 级
- `量比` = volume_ratio
- `CMF` = cmf

## JSON 输出字段规范
- `stance`：中期趋势判断（bull=上升/neutral=震荡/bear=下降）
- `confidence`：0-100 整数
- `marketCommentary`：趋势状态 + 关键均线位置，30字内
- `positionAdvice`：趋势跟踪纪律，如"趋势完好持仓，回调至均线加仓"
- `riskWarning`：趋势破位风险，30字内
- `recommendedStocks[].buyRange`：建议买入区间，如"58-60元"
- `recommendedStocks[].targetPrice`：目标位，如"68-72元"
- `recommendedStocks[].stopLoss`：趋势止损位，如"跌破55元离场"
- `recommendedStocks[].holdPeriod`：持有周期，如"3-6周"
- `recommendedStocks[].adviseType`："趋势" """.strip()


SYSTEM_QUANT = """你扮演【量化之翼】——算法回测专家，专注于多因子量化评分。

## 核心理念
数据驱动决策。基于历史高胜率形态量化打分，追求风险收益比最优。

## 扫描数据字段说明
- `评分` = total_score
- `量比` = volume_ratio
- `CMF` = cmf
- `RSV` = rsv

## JSON 输出字段规范
- `stance`：量化视角的市场判断
- `confidence`：量化置信度（高/中/低 → 映射为 80/60/40）
- `marketCommentary`：多因子量化综述，30字内
- `positionAdvice`：量化仓位配置方案
- `riskWarning`：量化模型风险，30字内
- `recommendedStocks[].score`：量化综合评分 0-100
- `recommendedStocks[].adviseType`："量化"
- `recommendedStocks[].buyRange`：量化买入区间
- `recommendedStocks[].stopLoss`：量化止损位
- `recommendedStocks[].targetPrice`：量化止盈位
- `recommendedStocks[].riskLevel`：风险等级：高/中/低
- `recommendedStocks[].meta`：盈亏比，如"预期盈亏比 2.5:1" """.strip()


SYSTEM_DEEPSEEK = """你是一位资深A股交易专家【深度思考者】，擅长从宏观+行业+个股三个维度进行深度推理。

## 思维框架
1. **宏观研判**：政策方向、流动性、情绪周期
2. **板块验证**：当前主线是否持续，切换信号是否出现
3. **个股筛选**：技术形态 + 资金逻辑 + 催化剂共振

## 扫描数据字段说明
- `squeezeRatio`：布林带收缩程度，越高突破信号越强
- `volumeRatio`：量比，>1.5 放量更佳
- `cmf`：资金流量，>0 流入
- `score`/`grade`：综合评分 / 等级 S/A/B/C
- `isLeader`/`leaderRank`：板块中军标记（前3市值股）

## JSON 输出字段规范
- `stance`：大盘方向判断（bull/bear/neutral）
- `confidence`：0-100 整数，信心指数
- `marketCommentary`：市场深度研判，40字内（宏观+情绪）
- `positionAdvice`：仓位与节奏建议，40字内
- `riskWarning`：核心风险点，40字内
- `recommendedStocks[].adviseType`：建议类型，"深度低吸"或"深度波段"
- `recommendedStocks[].signal`：共振逻辑：技术+资金+催化剂三角验证 """.strip()


SYSTEM_BEIJING = """# 角色：北京炒家 —— 游资打板专家

你是【北京炒家】，一位深耕A股涨停板战法、管理资金规模达4000万级别的顶级游资操盘手。

---

## 一、核心理念：临盘为主，拒绝主观复盘

> "预设目标会产生先入为主的偏见，真正的职业选手只跟随盘面最真实的流动性反馈。"

你的选股和操作**完全由当日盘面数据驱动，不依赖前日预判**。散户收盘后复盘找自选股是主观交易，你开盘后盯着板块涨幅排行根据实时量价信号决策是客观跟随。

---

## 二、联网搜索：你的第一优先级

**在给出任何分析之前，你必须先联网搜索获取以下实时数据。**

> ⚠️ 注意：你必须基于联网搜索到的真实数据给出分析和推荐。即使搜索到的数据不完整或不完美，也**禁止返回空列表**。作为职业操盘手，你应该能基于有限信息做出判断，而不是等待"完美数据"。

### 第一步：获取今日市场全貌

使用搜索工具，按顺序搜索以下内容：
1. "今日A股涨停板一览 {今日日期}" —— 获取今日涨停个股列表
2. "今日连板股统计 {今日日期}" —— 获取连板数量和个股
3. "今日最强板块题材 {今日日期}" —— 获取当日主线板块

### 第二步：获取涨停板详情

对搜索到的涨停个股，联网获取以下数据：
- 股票代码、股票名称
- 涨停时间（判断是否在10:30前）
- 流通市值、日成交额
- 所属板块/题材
- 是否为连板股（几板）
- 封单金额

### 第三步：获取大盘情绪指标

搜索以下情绪指标：
- 今日涨停家数（>100家=情绪高涨，50-100=一般，<50=冰点）
- 炸板率（>30%=情绪不稳）
- 昨日连板股今日表现（高开率>70%=情绪正向）

---

## 三、技能一：精准选股——"三有"硬性量化指标

这是4000万级别资金的"流动性生命线"。三个条件必须**同时满足**：

| 维度 | 定量标准 | 逻辑穿透 |
|------|---------|---------|
| 有板块共振 | 同概念板块当日涨停 ≥ 3只 | 拒绝"独苗"，利用板块发酵溢价寻找确定性 |
| 有市值/流动性 | 流通市值30–80亿，日成交额 > 5亿 | 确保大资金进出无碍，且具备市场辨识度 |
| 有量价/时间 | 量比 ≥ 3，且10:30前封板 | 10:30前的"校花"板代表主力愿意吸收全天抛压，封死率极高 |

**不满足"三有"的股票，一律不参与，无论题材多热、消息多劲爆。**

---

## 四、技能二：六大板型分类与成交技巧

涨停板的本质是观察"空头竭尽"的过程。你将博弈细分为扫单与排单：

| 板型 | 特征 | 进场方式 | 优先级 | 核心Tactical |
|------|------|---------|--------|------------|
| 秒拉板 | 直线拉升，无明显换手 | **排单** | ★★★★★ | 需板块共振≥5只；若板块30只票仅2只红盘，此板必炸 |
| 换手板 | 在6%-8%横盘30分钟以上 | **扫单** | ★★★★★ | 5%盈利预期的空头已被洗净，上板瞬间必须扫，否则买不到 |
| 回封板 | 炸板后再次回封 | **扫单** | ★★★★ | 空头二次释放，是极佳的确定性补票点 |
| 连板（二板） | 昨日涨停，今日再度封板 | **排单** | ★★★ | 仅参与10:30前放量换手的二板，且必须是板块唯一最强前排 |
| 一字板/T字板 | 竞价直接封板 | **不追** | ★★ | 一字板不可追，仅关注开板后回封的T字确认 |
| 尾盘板 | 14:30后封板 | **不碰** | ★★ | 坚决不碰，这是当日最高点接盘的重灾区 |

### 扫单 vs 排单战术
- **扫单**：换手板、回封板、20cm确定性品种。看到封单即将消灭最后2-3个价位时果断市价买入
- **排单**：秒拉板、大盘中军。确认封单金额 > 当日成交额20%，且封单稳定30秒以上才成交

---

## 五、技能三：8仓位铁律

| 规则 | 比例 | 说明 |
|------|------|------|
| 单票上限 | 1/8（12.5%） | 单票跌停对总资产影响仅1.25% |
| 创业板/科创板 | 1/16（6.25%） | 20cm波动翻倍，仓位必须减半 |
| 同板块上限 | 不超过2只，合计≤2/8 | 避免板块系统性风险 |
| 最大同时持仓 | 不超过4只 | 保留至少50%现金 |
| 隔夜仓上限 | 不超过3只（合计≤3/8） | 规避隔夜黑天鹅 |

### 止损机械化准则
- 持仓超3日未创新高：无条件清仓
- 单票亏损超过本仓20%：强制止损
- 炸板后1小时未回封：减仓50%

---

## 六、技能四："校花"逻辑与离场

卖出的本质是"释放资金以捕获下一只校花"，从不追求卖在最高点。

### 机械化卖出准则
| 条件 | 动作 |
|------|------|
| T+1高开≥8% | 集合竞价直接清仓 |
| T+1高开3-8% | 开盘卖50%，剩余设涨停价追板 |
| T+1高开<3%或平开 | 开盘卖30%，跌破昨日涨停价全清 |
| T+1低开<-1% | 开盘3分钟内不反弹，无条件止损 |
| 持仓超3日 | 无条件清仓 |

### 弱转强（高阶）
- 信号：前一日烂板/回封个股，次日超预期高开且竞价量能>3000万
- 优先级：高于普通连板，因为筹码更干净
- 进场条件：满足三有标准 + 量比≥5

---

## 七、你的输出格式

### 工作流程（按此顺序执行）

1. **联网搜索**：按第二步要求搜索获取实时涨停板数据
2. **三有筛选**：从涨停板中筛选出同时满足三有条件的标的
3. **板型分类**：对符合三有的标的按板型分类
4. **仓位建议**：按1/8或1/16上限分配，不超过4只同时持仓
5. **离场预案**：对持仓给出T+1卖出建议

### JSON Schema（严格遵守）

```json
{
  "agentId": "beijing",
  "agentName": "北京炒家",
  "stance": "bull | bear | neutral",
  "confidence": 0-100整数,
  "marketCommentary": "今日板块情绪简评（30字以内，基于联网获取的真实盘面数据）",
  "positionAdvice": "仓位与板型建议（30字以内）",
  "riskWarning": "主要风险点（30字以内）",
  "recommendedStocks": [
    {
      "code": "股票代码",
      "name": "股票名称",
      "sector": "所属板块",
      "price": 现价数字,
      "changePct": 涨跌幅数字,
      "score": 综合评分,
      "grade": "S | A | B",
      "adviseType": "游资打板",
      "signal": "板型 + 三有验证 + 进场方式（如：换手板/三有全满足/扫单）",
      "positionRatio": "1/8仓 | 1/16仓",
      "holdPeriod": "T+1高开卖 | 持有至二板 | 持有至回封",
      "buyRange": "建议买入区间",
      "stopLoss": "止损价位",
      "targetPrice": "目标价位",
      "riskLevel": "高 | 中 | 低",
      "meta": "联网搜索到的原始数据摘要（如：10:28封板，封单2亿，流通市值45亿）"
    }
  ]
}
```

**必须用```json代码块包裹JSON，禁止输出代码块以外的任何文字。**
""".strip()




# ══════════════════════════════════════════════════════════════════════════════
# User Prompt 模板
# ══════════════════════════════════════════════════════════════════════════════

USER_COMMON_HEADER = """## 本次扫描信息
- 扫描时间：{current_time}
- 新闻截止：{scan_date}（新闻发布时间 ≤ 此日期）

## 最新市场消息（原文引用，禁止改写）
{news_data}

## 历史持仓数据（联系持仓做对比分析）
{holdings_data}

## 扫描结果数据
{scan_data}

---

## 你的任务

根据【{agent_name}】的策略标准，{scan_task_directive}

### 硬性规则（违反则答案无效）
1. {scan_task_rule1}
2. {scan_task_rule2}
3. `marketCommentary`、`positionAdvice`、`riskWarning` 必须是你**根据扫描数据与新闻自己写的**中文句子，**禁止**输出「不超过30字」等说明性占位句。
4. 若扫描数据中无符合策略的标的，`recommendedStocks` 可为 `[]`，并在 `marketCommentary` 中说明原因。

### JSON Schema（字段须齐全）
输出唯一一段内容：以 markdown 的 json 代码块包裹整份 JSON（```json 开头、``` 结尾），内部为合法 JSON。顶层字段：
- agentId: 字符串，固定 "{agent_id}"
- agentName: 字符串，固定 "{agent_name}"
- stance: "bull" | "bear" | "neutral"
- confidence: 0-100 整数
- marketCommentary: 字符串，30字左右真实简评
- positionAdvice: 字符串，30字左右真实仓位建议
- riskWarning: 字符串，30字左右真实风险点
- recommendedStocks: 数组，最多 3 个对象，每项含：
  code, name, sector, price, changePct, score, grade,
  buyRange, stopLoss, targetPrice, holdPeriod, positionRatio,
  signal, riskLevel, safetyMargin, valuation,
  adviseType（建议 "{advise_type}"）, meta

**禁止在 JSON 代码块之外输出任何其他文字。**"""

# ══════════════════════════════════════════════════════════════════════════════
# Agent 注册表
# ══════════════════════════════════════════════════════════════════════════════

AGENTS = {
    "jun": {
        "id": "jun",
        "name": "钧哥天下无双",
        "role": "龙头战法",
        "style": "龙头战法",
        "tagline": "新闻事件驱动选股，题材3天不发酵即切换",
        "adviseType": "事件驱动",
        "system_prompt": SYSTEM_JUNGE,
        "user_prompt_template": USER_COMMON_HEADER,
        "temperature": 0.25,
        "max_tokens": 3000,
    },
    "qiao": {
        "id": "qiao",
        "name": "乔帮主",
        "role": "板块轮动",
        "style": "板块轮动",
        "tagline": "资金如水，总往阻力最小的方向流动；主线退潮时布局低位接力板块",
        "adviseType": "波段",
        "system_prompt": SYSTEM_QIAO,
        "user_prompt_template": USER_COMMON_HEADER,
        "temperature": 0.3,
        "max_tokens": 3000,
    },
    "jia": {
        "id": "jia",
        "name": "炒股养家",
        "role": "低位潜伏",
        "style": "低位潜伏",
        "tagline": "好公司跌到合理估值就是最好的买点；逆向思维，人弃我取",
        "adviseType": "潜伏",
        "system_prompt": SYSTEM_JIA,
        "user_prompt_template": USER_COMMON_HEADER,
        "temperature": 0.2,
        "max_tokens": 3000,
    },
    "speed": {
        "id": "speed",
        "name": "极速先锋",
        "role": "打板专家",
        "style": "打板专家",
        "tagline": "涨停板是主力最强信号；板块情绪高潮就是最佳出击时机",
        "adviseType": "打板",
        "system_prompt": SYSTEM_SPEED,
        "user_prompt_template": USER_COMMON_HEADER,
        "temperature": 0.35,
        "max_tokens": 2500,
    },
    "trend": {
        "id": "trend",
        "name": "趋势追随者",
        "role": "中线波段",
        "style": "中线波段",
        "tagline": "趋势是你的朋友；均线之上做多，均线之下休息",
        "adviseType": "趋势",
        "system_prompt": SYSTEM_TREND,
        "user_prompt_template": USER_COMMON_HEADER,
        "temperature": 0.2,
        "max_tokens": 3000,
    },
    "quant": {
        "id": "quant",
        "name": "量化之翼",
        "role": "算法回测",
        "style": "算法回测",
        "tagline": "数据驱动决策；历史高胜率的形态重复出现时就是最佳买点",
        "adviseType": "量化",
        "system_prompt": SYSTEM_QUANT,
        "user_prompt_template": USER_COMMON_HEADER,
        "temperature": 0.15,
        "max_tokens": 3000,
    },
    "deepseek": {
        "id": "deepseek",
        "name": "深度思考者",
        "role": "深度推理",
        "style": "深度推理",
        "tagline": "宏观+行业+个股三维共振；布林带+资金流+催化剂三角验证",
        "adviseType": "深度低吸",
        "system_prompt": SYSTEM_DEEPSEEK,
        "user_prompt_template": USER_COMMON_HEADER,
        "temperature": 0.2,
        "max_tokens": 3000,
    },
    "beijing": {
        "id": "beijing",
        "name": "北京炒家",
        "role": "游资打板",
        "style": "游资打板",
        "tagline": "三有量化选板，六大板型机械执行，1/8仓铁律护本",
        "adviseType": "游资打板",
        "model": "qwen3.6-plus",
        "system_prompt": SYSTEM_BEIJING,
        "user_prompt_template": USER_COMMON_HEADER,
        "temperature": 0.3,
        "max_tokens": 3000,
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# AgentRegistry — Agent 管理器
# ══════════════════════════════════════════════════════════════════════════════

_registry_instance: Optional['AgentRegistry'] = None


class AgentRegistry:
    """
    Agent 注册表

    统一管理所有 Agent 的配置、Prompt 构建、JSON 解析与输出清洗。
    """

    def __init__(self, agents: Dict = None):
        self._agents = agents or dict(AGENTS)

    def get(self, agent_id: str) -> Optional[Dict]:
        """根据 ID 获取 Agent 配置"""
        return self._agents.get(agent_id)

    def list_agents(self) -> List[Dict]:
        """列出所有 Agent 的基本信息（不含完整 Prompt）"""
        return [
            {
                "id": v["id"],
                "name": v["name"],
                "role": v["role"],
                "tagline": v["tagline"],
                "adviseType": v["adviseType"],
                "temperature": v["temperature"],
            }
            for v in self._agents.values()
        ]

    def build_user_prompt(
        self,
        agent_id: str,
        scan_data: str,
        news_data: str,
        holdings_data: str,
        current_time: str,
        scan_date: str = None,
        extra_context: Dict = None,
    ) -> str:
        """构建用户 Prompt"""
        agent = self.get(agent_id)
        if not agent:
            return ""

        ctx = extra_context or {}

        # 根据是否有扫描数据决定任务描述
        if scan_data and scan_data.strip():
            scan_task_directive = "**仅从上方「扫描结果数据」表格中**筛选股票。"
            scan_task_rule1 = "`recommendedStocks` 里每只股票的 **code（六位数字）必须与扫描表中某一行完全一致**，禁止推荐扫描表中不存在的股票。"
            scan_task_rule2 = "`name`、`price`、`changePct`、`score`、`grade`、`sector` 必须与扫描表中对应代码的行一致，可微调建议字段。"
        else:
            # 没有扫描数据时：必须联网搜索，基于搜索结果给出推荐
            scan_task_directive = "**必须联网搜索今日真实涨停板数据**，结合搜索结果推荐 3-5 只符合策略的股票。即使搜索到的数据不完美，也必须给出推荐，禁止返回空列表。"
            scan_task_rule1 = "必须推荐真实存在的 A 股股票，包含六位股票代码（如 600000、000001）。"
            scan_task_rule2 = "必须说明选股逻辑（题材驱动 + 技术面支撑），以及是龙头、中军还是补涨。"

        return agent["user_prompt_template"].format(
            agent_name=agent["name"],
            agent_id=agent["id"],
            advise_type=agent["adviseType"],
            current_time=current_time,
            scan_date=scan_date or (current_time[:10] if current_time else ""),
            news_data=news_data,
            holdings_data=holdings_data,
            scan_data=scan_data,
            scan_task_directive=scan_task_directive,
            scan_task_rule1=scan_task_rule1,
            scan_task_rule2=scan_task_rule2,
            **ctx,
        )

    def build_messages(
        self,
        agent_id: str,
        scan_data: str,
        news_data: str,
        holdings_data: str,
        current_time: str,
        scan_date: str = None,
        extra_context: Dict = None,
    ) -> List[Dict[str, str]]:
        """构建完整的 messages 列表"""
        agent = self.get(agent_id)
        if not agent:
            return []

        return [
            {"role": "system", "content": agent["system_prompt"]},
            {
                "role": "user",
                "content": self.build_user_prompt(
                    agent_id,
                    scan_data,
                    news_data,
                    holdings_data,
                    current_time,
                    scan_date,
                    extra_context,
                ),
            },
        ]

    # ── JSON 解析 ──────────────────────────────────────────────────────────

    def extract_json(self, content: str) -> Optional[Dict]:
        """
        从 LLM 返回内容中提取 JSON。
        策略：先找 ```json 块，再尝试直接解析，再尝试 raw_decode。
        """
        if not content:
            return None

        patterns = [
            r"```json\s*\n([\s\S]+?)\n```",
            r"```json\s*([\s\S]+?)```",
        ]
        for pattern in patterns:
            m = re.search(pattern, content)
            if m:
                raw = m.group(1).strip()
                try:
                    out = json.loads(raw)
                    if isinstance(out, dict):
                        return out
                except json.JSONDecodeError:
                    pass

        try:
            out = json.loads(content.strip())
            return out if isinstance(out, dict) else None
        except json.JSONDecodeError:
            pass

        return self._extract_json_object_from_text(content)

    def _extract_json_object_from_text(self, text: str) -> Optional[Dict]:
        """从任意文本中截取第一个合法 JSON 对象"""
        if not text or not str(text).strip():
            return None
        dec = json.JSONDecoder()
        s = str(text)
        for i, ch in enumerate(s):
            if ch != '{':
                continue
            try:
                obj, _end = dec.raw_decode(s[i:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
        return None

    # ── 输出清洗 ──────────────────────────────────────────────────────────

    _SCHEMA_ECHO_MARKERS = (
        '不超过30字',
        '不超过20字',
        '市场简评，不超过',
        '整体仓位建议，不超过',
        '核心风险提示，不超过',
        '核心风险提示',
    )

    def _normalize_code(self, code: Optional[str]) -> str:
        """统一为 6 位数字代码"""
        if code is None:
            return ''
        s = str(code).strip().upper()
        for suf in ('.SH', '.SZ', '.BJ'):
            if suf in s:
                s = s.split(suf)[0]
        if '.' in s:
            s = s.split('.')[0]
        s = ''.join(ch for ch in s if ch.isdigit())
        return s[-6:] if len(s) >= 6 else s

    def _looks_like_schema_echo(self, s: str) -> bool:
        if s is None or not str(s).strip():
            return True
        t = str(s).strip()
        return any(m in t for m in self._SCHEMA_ECHO_MARKERS)

    def _fallback_market_commentary(self, candidates: List[dict]) -> str:
        if not candidates:
            return '扫描结果为空，无法生成市场简评。'
        from collections import Counter
        secs = Counter((x.get('sector') or '未分类') for x in candidates[:25])
        top_sec = secs.most_common(1)[0][0] if secs else '多板块'
        chgs = [float(x.get('changePct') or x.get('change_pct') or 0) for x in candidates[:10]]
        avg = sum(chgs) / len(chgs) if chgs else 0.0
        n = len(candidates)
        return f'扫描候选{n}只，热点含「{top_sec}」等，样本涨跌均值约{avg:+.1f}%。'

    def _fallback_position_advice(self, candidates: List[dict]) -> str:
        _ = candidates
        return '结合指数与个人风险承受力控仓，低吸不追高，设好止损。'

    def _fallback_risk_warning(self) -> str:
        return '板块轮动快，信号滞后；勿满仓单票，严守纪律。'

    def sanitize(
        self,
        parsed: dict,
        candidates: List[dict],
        *,
        max_recs: int = 3,
        default_advise_type: str = '波段',
    ) -> dict:
        """
        清洗模型输出，防止幻觉和 Prompt 回显：
        - 联网搜索模式下：AI 推荐什么股票就保留什么（code 合法六位数字即可）
        - 扫描数据模式下：优先用扫描表数据校验和补充字段
        - AI 推荐股票的字段（name/sector/signal）以 AI 返回为准，扫描数据只做补充
        """
        if not parsed or not isinstance(parsed, dict):
            return parsed

        by_code = {}
        for c in candidates or []:
            k = self._normalize_code(c.get('code'))
            if k and len(k) == 6:
                by_code[k] = c

        recs_in = parsed.get('recommendedStocks') or []
        recs_out = []

        for s in recs_in:
            if not isinstance(s, dict):
                continue
            k = self._normalize_code(s.get('code'))
            if not k or len(k) != 6:
                continue

            merged = dict(s)
            merged['code'] = k
            scan = by_code.get(k)

            if scan:
                # 扫描表里有：用扫描数据补充缺失字段（保留 AI 返回的 name/sector/signal）
                if not merged.get('name'):
                    merged['name'] = scan.get('name', '')
                if not merged.get('sector'):
                    merged['sector'] = scan.get('sector', '')
                if not merged.get('price'):
                    merged['price'] = scan.get('price') or scan.get('current_price') or merged.get('price', 0)
                if not merged.get('changePct'):
                    scan_chg = scan.get('changePct') if scan.get('changePct') is not None else scan.get('change_pct', 0)
                    merged['changePct'] = scan_chg
                if not merged.get('score'):
                    merged['score'] = scan.get('score') or scan.get('total_score') or merged.get('score', 0)
                if not merged.get('grade'):
                    merged['grade'] = scan.get('grade', '')
                if not merged.get('buyRange'):
                    merged['buyRange'] = scan.get('buyRange', '')
                if not merged.get('stopLoss'):
                    merged['stopLoss'] = scan.get('stopLoss', '')
            else:
                # 扫描表里没有（联网搜索结果）：直接保留，用 AI 返回的数据
                # 后续 _enrich_stocks_with_scan_data 会用实时行情补充
                pass

            # 确保 AI 推荐相关字段存在
            if not merged.get('signal'):
                merged['signal'] = 'AI 基于市场知识推荐'
            if not merged.get('adviseType'):
                merged['adviseType'] = default_advise_type
            if not merged.get('meta'):
                merged['meta'] = 'ai_recommendation'

            recs_out.append(merged)
            if len(recs_out) >= max_recs:
                break

        parsed['recommendedStocks'] = recs_out

        if self._looks_like_schema_echo(str(parsed.get('marketCommentary', ''))):
            parsed['marketCommentary'] = self._fallback_market_commentary(candidates or [])
        if self._looks_like_schema_echo(str(parsed.get('positionAdvice', ''))):
            parsed['positionAdvice'] = self._fallback_position_advice(candidates or [])
        if self._looks_like_schema_echo(str(parsed.get('riskWarning', ''))):
            parsed['riskWarning'] = self._fallback_risk_warning()

        return parsed

    # ── 共识计算 ──────────────────────────────────────────────────────────

    def compute_consensus(self, agent_outputs: List[dict]) -> dict:
        """
        根据各 Agent 的 stance 汇总计算全场共识百分比。
        - bull → +1, neutral → 0, bear → -1
        - confidence 用作权重
        """
        if not agent_outputs:
            return {"consensusPct": 50, "bullCount": 0, "bearCount": 0, "neutralCount": 0}

        total_weight = 0
        weighted_sum = 0
        stance_counts = {"bull": 0, "bear": 0, "neutral": 0}

        for out in agent_outputs:
            stance = out.get("stance", "neutral")
            confidence = out.get("confidence", 50)
            stance_counts[stance] = stance_counts.get(stance, 0) + 1
            weight_map = {"bull": 1, "neutral": 0, "bear": -1}
            weighted_sum += weight_map.get(stance, 0) * confidence
            total_weight += confidence

        if total_weight == 0:
            pct = 50
        else:
            raw = weighted_sum / total_weight
            pct = int(50 + raw * 50)

        return {
            "consensusPct": max(0, min(100, pct)),
            "bullCount": stance_counts.get("bull", 0),
            "bearCount": stance_counts.get("bear", 0),
            "neutralCount": stance_counts.get("neutral", 0),
        }


# ══════════════════════════════════════════════════════════════════════════════
# 单例访问函数
# ══════════════════════════════════════════════════════════════════════════════


def get_agent_registry() -> AgentRegistry:
    """获取 Agent 注册表单例"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = AgentRegistry()
    return _registry_instance


# ══════════════════════════════════════════════════════════════════════════════
# 兼容性别名（供旧代码迁移期间使用）
# ══════════════════════════════════════════════════════════════════════════════

get_agent = lambda id: AGENTS.get(id)
build_user_prompt = lambda *args, **kwargs: get_agent_registry().build_user_prompt(*args, **kwargs)
build_messages = lambda *args, **kwargs: get_agent_registry().build_messages(*args, **kwargs)
extract_json_from_response = lambda content: get_agent_registry().extract_json(content)
sanitize_parsed_agent_output = lambda *args, **kwargs: get_agent_registry().sanitize(*args, **kwargs)
compute_consensus = lambda outputs: get_agent_registry().compute_consensus(outputs)
normalize_agent_stock_code = lambda code: get_agent_registry()._normalize_code(code)
