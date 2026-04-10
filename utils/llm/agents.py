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


SYSTEM_JUNGE = """你扮演【钧哥天下无双】——龙头战法专家，专注于龙头股和强势股的低吸策略。

## 核心理念
布林带极度收缩是主力蓄力的标志，配合放量（量比>1 且 CMF>0）是关键启动信号。稳健低吸，不追高，顺势而为。

## 持仓联动分析（必须执行）
分析「历史持仓数据」时需重点关注：
1. **持仓亏损股**：亏损超过5%或持有超10日仍未起色的，分析是否需要调仓换股
2. **持仓盈利股**：盈利股是否出现本次扫描中更强的新信号，考虑是否加仓
3. **板块协同**：新候选股与现有持仓是否同板块，避免重复持仓同一主线
4. **仓位腾挪**：通过减亏/止盈旧仓位，释放资金给更有潜力的新候选

## 扫描数据字段说明
- `收缩率` = squeeze_ratio：越高布林带越紧，突破信号越强
- `带宽%` = bb_width_pct：<5% 为极度收缩
- `量比` = volume_ratio：>1.5 放量更佳
- `CMF` = cmf：>0 资金流入
- `RSV` = rsv：<20 超卖，>80 超买
- `评分` = total_score；`等级` = grade（S/A/B/C）

## JSON 输出字段规范
- `stance`：综合判断（bull/bear/neutral）
- `confidence`：0-100 整数，信心指数
- `marketCommentary`：市场简评，30字内
- `positionAdvice`：整体仓位建议，如"建议6-7成仓位"
- `riskWarning`：核心风险，30字内
- `recommendedStocks[].buyRange`：低吸区间，如"28.5-29.5"
- `recommendedStocks[].stopLoss`：止损位，如"27.5"
- `recommendedStocks[].adviseType`："低吸"
- `recommendedStocks[].signal`：低吸逻辑，如"布林带极度收缩+放量，可分批建仓" """.strip()


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

## 扫描结果数据（从以下数据中提取所有字段，禁止编造）
{scan_data}

---

## 你的任务

根据【{agent_name}】的策略标准，**仅从上方「扫描结果数据」表格中**筛选股票。

### 硬性规则（违反则答案无效）
1. `recommendedStocks` 里每只股票的 **code（六位数字）必须与扫描表中某一行完全一致**，禁止推荐扫描表中不存在的股票。
2. `name`、`price`、`changePct`、`score`、`grade`、`sector` 必须与扫描表中对应代码的行一致，可微调建议字段。
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
        "tagline": "布林带极度收缩是主力蓄力的标志，配合放量是关键启动信号",
        "adviseType": "低吸",
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

        return agent["user_prompt_template"].format(
            agent_name=agent["name"],
            agent_id=agent["id"],
            advise_type=agent["adviseType"],
            current_time=current_time,
            scan_date=scan_date or (current_time[:10] if current_time else ""),
            news_data=news_data,
            holdings_data=holdings_data,
            scan_data=scan_data,
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
        - 推荐股 code 必须在 candidates 中
        - 与扫描表冲突的字段以扫描数据为准
        - 照抄 Prompt 占位句的文案替换为兜底句
        """
        if not parsed or not isinstance(parsed, dict):
            return parsed

        by_code: dict = {}
        for c in candidates or []:
            k = self._normalize_code(c.get('code'))
            if k and len(k) == 6:
                by_code[k] = c

        recs_in = list(parsed.get('recommendedStocks') or [])
        recs_out: List[dict] = []
        seen = set()

        for s in recs_in:
            if not isinstance(s, dict):
                continue
            k = self._normalize_code(s.get('code'))
            if not k or k not in by_code or k in seen:
                continue
            seen.add(k)
            row = by_code[k]
            merged = dict(s)
            merged['code'] = row.get('code', k)
            merged['name'] = row.get('name', merged.get('name', ''))
            merged['sector'] = row.get('sector', merged.get('sector', ''))
            merged['price'] = row.get('price') or row.get('current_price') or merged.get('price', 0)
            merged['changePct'] = row.get('changePct') if row.get('changePct') is not None else row.get('change_pct', merged.get('changePct', 0))
            merged['score'] = row.get('score') or row.get('total_score', merged.get('score', 0))
            merged['grade'] = row.get('grade', merged.get('grade', ''))
            if not merged.get('buyRange'):
                merged['buyRange'] = row.get('buyRange', '')
            if not merged.get('stopLoss'):
                merged['stopLoss'] = row.get('stopLoss', '')
            recs_out.append(merged)
            if len(recs_out) >= max_recs:
                break

        if not recs_out and candidates:
            def _score(x):
                return float(x.get('score') or x.get('total_score') or 0)

            for row in sorted(candidates, key=_score, reverse=True)[:max_recs]:
                k = self._normalize_code(row.get('code'))
                if not k:
                    continue
                recs_out.append({
                    'code': row.get('code'),
                    'name': row.get('name', ''),
                    'sector': row.get('sector', ''),
                    'price': row.get('price') or row.get('current_price') or 0,
                    'changePct': row.get('changePct') if row.get('changePct') is not None else row.get('change_pct', 0),
                    'score': row.get('score') or row.get('total_score') or 0,
                    'grade': row.get('grade', ''),
                    'buyRange': row.get('buyRange', ''),
                    'stopLoss': row.get('stopLoss', ''),
                    'targetPrice': '',
                    'holdPeriod': '',
                    'positionRatio': '',
                    'signal': '扫描评分靠前；模型未给出独立逻辑，请结合盘面与止损纪律。',
                    'riskLevel': '',
                    'safetyMargin': '',
                    'valuation': '',
                    'adviseType': default_advise_type,
                    'meta': 'scan_fallback',
                })

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
