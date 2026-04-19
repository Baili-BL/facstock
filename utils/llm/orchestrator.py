"""
Agent 协调器 - 层次化任务拆解与调度
==========================================

核心设计理念：
1. **任务拆解**：将复杂分析分解为可管理的子任务
2. **步骤排序**：明确任务执行顺序和依赖关系
3. **决策调度**：根据状态动态分配资源和决策路径
4. **依赖控制**：管理任务间的数据依赖和执行顺序
5. **异常处理**：完善的错误捕获、恢复和降级机制
6. **状态流转**：清晰的任务状态管理和转换

状态机：
    PENDING → RUNNING → COMPLETED
                ↓
              FAILED → RETRYING → RUNNING
                ↓
             FALLBACK → COMPLETED（降级结果）

调度策略：
- 主控 Agent（master）：必须首先执行，作为其他 Agent 的输入
- 阶段一 Agent（jun, qiao, jia）：可以并行执行，彼此无依赖
- 阶段二 Agent（speed, trend, quant）：可以并行执行，彼此无依赖
- 阶段三 Agent（deepseek, beijing）：可以并行执行，彼此无依赖
"""

import json
import logging
import time
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# 枚举定义
# ══════════════════════════════════════════════════════════════════════════════


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"          # 等待执行
    RUNNING = "running"          # 执行中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"           # 失败
    RETRYING = "retrying"       # 重试中
    FALLBACK = "fallback"       # 降级
    SKIPPED = "skipped"         # 跳过


class ExecutionPhase(Enum):
    """执行阶段"""
    MASTER = "master"            # 主控阶段（必须首先执行）
    PHASE_1 = "phase_1"        # 第一阶段（题材分析）
    PHASE_2 = "phase_2"        # 第二阶段（技术分析）
    PHASE_3 = "phase_3"        # 第三阶段（综合分析）
    AGGREGATION = "aggregation"  # 聚合阶段


# ══════════════════════════════════════════════════════════════════════════════
# 数据结构
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class TaskResult:
    """任务执行结果"""
    agent_id: str
    status: TaskStatus
    success: bool = False
    result: Any = None
    error: str = ""
    raw_response: str = ""
    thinking: str = ""
    tokens_used: int = 0
    execution_time_ms: int = 0
    retry_count: int = 0
    fallback_used: bool = False


@dataclass
class ExecutionContext:
    """执行上下文 - 贯穿整个任务执行过程"""
    scan_data: str = ""
    news_data: str = ""
    holdings_data: str = ""
    current_time: str = ""
    scan_date: str = ""
    master_result: Optional['TaskResult'] = None
    agent_results: Dict[str, TaskResult] = field(default_factory=dict)
    execution_log: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_log(self, phase: str, agent_id: str, status: str, message: str):
        """添加执行日志"""
        self.execution_log.append({
            "timestamp": datetime.now().isoformat(),
            "phase": phase,
            "agent_id": agent_id,
            "status": status,
            "message": message
        })

    def get_successful_results(self) -> List[TaskResult]:
        """获取所有成功的任务结果"""
        return [r for r in self.agent_results.values() if r.success]


@dataclass
class MasterAnalysis:
    """主控 Agent 分析结果"""
    market_core_intent: str = ""          # 市场核心意图
    market_phase: str = ""                # 市场阶段
    risk_appetite: str = ""               # 风险偏好
    agent_priority: List[str] = field(default_factory=list)  # Agent 优先级
    key_theme: str = ""                   # 主线题材
    risk_factors: List[str] = field(default_factory=list)    # 风险因素
    coordination_notes: str = ""           # 协调建议
    success: bool = False
    raw_response: str = ""


@dataclass
class HierarchicalResult:
    """层次化分析结果"""
    master: Optional[MasterAnalysis] = None
    agent_results: Dict[str, Any] = field(default_factory=dict)
    consensus: Dict[str, Any] = field(default_factory=dict)
    top_opportunities: List[Dict] = field(default_factory=list)
    synthesis: str = ""      # 综合建议
    execution_log: List[Dict] = field(default_factory=list)  # 执行日志
    success_rate: float = 0.0  # 成功率
    metadata: Dict[str, Any] = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════════════
# Agent 核心目标定义（第一性原理）
# ══════════════════════════════════════════════════════════════════════════════

AGENT_CORE_OBJECTIVES = {
    "jun": {
        "core_objective": "找到有后续催化剂+资金认可+容量足够的标的，在拉升前低吸买入",
        "subtasks": [
            "分析题材级别（S/A/B/C/D级）",
            "三板斧验证（政策豁免+后续催化+资金放量）",
            "选容量标的（中军优先）",
            "制定离场预案（时间/空间/力度止损）"
        ],
        "focus_fields": ["themeLevel", "threeAxesPassed", "role"],
        "phase": ExecutionPhase.PHASE_1,
        "dependencies": [],
        "timeout_ms": 60000,
    },
    "qiao": {
        "core_objective": "在主线高潮前潜伏，在退潮前切换",
        "subtasks": [
            "识别当前主线",
            "判断主线阶段（启动/发酵/高潮/退潮）",
            "预判切换方向",
            "制定切换策略"
        ],
        "focus_fields": ["mainTheme", "stage", "type"],
        "phase": ExecutionPhase.PHASE_1,
        "dependencies": [],
        "timeout_ms": 60000,
    },
    "jia": {
        "core_objective": "找到被市场错误定价的优质资产，等待价值回归",
        "subtasks": [
            "寻找超跌标的",
            "评估安全边际",
            "判断催化剂",
            "制定潜伏计划"
        ],
        "focus_fields": ["safetyMargin", "valuation", "catalyst"],
        "phase": ExecutionPhase.PHASE_1,
        "dependencies": [],
        "timeout_ms": 60000,
    },
    "speed": {
        "core_objective": "在情绪高潮时捕捉涨停溢价，快进快出",
        "subtasks": [
            "判断市场情绪阶段",
            "筛选板质",
            "制定进场策略（排单/扫单）",
            "制定离场策略"
        ],
        "focus_fields": ["emotionStage", "boardType", "boardQuality"],
        "phase": ExecutionPhase.PHASE_2,
        "dependencies": ["jun"],
        "timeout_ms": 60000,
    },
    "trend": {
        "core_objective": "在上升趋势中顺势而为，让利润奔跑",
        "subtasks": [
            "判断中期趋势方向",
            "寻找趋势中的回调买点",
            "制定持仓策略",
            "制定止损策略"
        ],
        "focus_fields": ["trendStage", "direction", "keyLevel"],
        "phase": ExecutionPhase.PHASE_2,
        "dependencies": ["qiao"],
        "timeout_ms": 60000,
    },
    "quant": {
        "core_objective": "找到历史胜率高的形态，在最佳位置买入",
        "subtasks": [
            "多因子评分",
            "风险收益比计算",
            "量化选股",
            "仓位优化"
        ],
        "focus_fields": ["score", "riskRewardRatio", "factorBreakdown"],
        "phase": ExecutionPhase.PHASE_2,
        "dependencies": [],
        "timeout_ms": 60000,
    },
    "deepseek": {
        "core_objective": "预判未来，找到预期差最大的方向",
        "subtasks": [
            "宏观研判（政策/流动性/情绪）",
            "行业验证",
            "个股筛选（三角验证）",
            "风险评估"
        ],
        "focus_fields": ["triangularVerification", "macroFit", "共振逻辑"],
        "phase": ExecutionPhase.PHASE_3,
        "dependencies": ["jun", "qiao", "jia"],
        "timeout_ms": 90000,
    },
    "beijing": {
        "core_objective": "三有量化选板，机械执行1/8仓铁律",
        "subtasks": [
            "联网搜索获取实时涨停数据",
            "三有筛选（市值/流动性/量价时间）",
            "板型分类",
            "仓位分配与离场预案"
        ],
        "focus_fields": ["boardType", "positionRatio", "buyMethod"],
        "phase": ExecutionPhase.PHASE_3,
        "dependencies": ["speed"],
        "timeout_ms": 90000,
    }
}


# ══════════════════════════════════════════════════════════════════════════════
# 异常处理
# ══════════════════════════════════════════════════════════════════════════════


class AgentExecutionError(Exception):
    """Agent 执行异常"""
    def __init__(self, agent_id: str, message: str, is_retryable: bool = True):
        self.agent_id = agent_id
        self.is_retryable = is_retryable
        super().__init__(f"[{agent_id}] {message}")


class TaskDependencyError(Exception):
    """任务依赖异常"""
    pass


class TaskTimeoutError(Exception):
    """任务超时异常"""
    pass


# ══════════════════════════════════════════════════════════════════════════════
# Agent 协调器
# ══════════════════════════════════════════════════════════════════════════════


class AgentOrchestrator:
    """
    Agent 协调器 - 负责层次化任务拆解和协调

    核心职责：
    1. 任务拆解：将复杂分析分解为可管理的子任务
    2. 步骤排序：根据阶段和依赖关系排序任务
    3. 决策调度：动态分配执行资源和决策路径
    4. 依赖控制：管理任务间的数据依赖
    5. 异常处理：完善的错误捕获和恢复机制
    6. 状态流转：清晰的任务状态管理
    """

    # 最大重试次数
    MAX_RETRIES = 2

    # 重试间隔（毫秒）
    RETRY_DELAY_MS = 1000

    def __init__(self, client, agent_registry):
        self.client = client
        self.registry = agent_registry

    def analyze_hierarchical(
        self,
        scan_data: str,
        news_data: str,
        holdings_data: str,
        current_time: str,
        scan_date: str,
        options=None,
    ) -> HierarchicalResult:
        """
        层次化分析主流程

        执行顺序：
        1. 主控 Agent（master）→ 分析市场核心意图
        2. 阶段一 Agent（jun, qiao, jia）→ 题材分析（并行）
        3. 阶段二 Agent（speed, trend, quant）→ 技术分析（并行，依赖阶段一）
        4. 阶段三 Agent（deepseek, beijing）→ 综合分析（并行，依赖阶段一二）
        5. 聚合层 → 加权共识 + 综合建议
        """
        # 初始化执行上下文
        ctx = ExecutionContext(
            scan_data=scan_data,
            news_data=news_data,
            holdings_data=holdings_data,
            current_time=current_time,
            scan_date=scan_date,
        )

        logger.info("[Orchestrator] ========== 开始层次化分析 ==========")
        ctx.add_log("init", "system", "START", "开始执行层次化分析")

        try:
            # 阶段0：主控 Agent（必须首先执行）
            ctx = self._execute_master_phase(ctx, options)

            # 检查主控 Agent 是否成功
            if not ctx.master_result or not ctx.master_result.success:
                logger.warning("[Orchestrator] 主控 Agent 执行失败，使用默认配置")
                ctx.master_result = TaskResult(
                    agent_id="master",
                    status=TaskStatus.FALLBACK,
                    success=True,
                    fallback_used=True,
                )
                ctx.metadata["master_fallback"] = True

            # 计算 Agent 权重
            agent_weights = self._compute_agent_weights(ctx)

            # 阶段一：题材分析（可以并行）
            ctx = self._execute_phase(ctx, ExecutionPhase.PHASE_1, agent_weights, options)

            # 阶段二：技术分析（可以并行，依赖阶段一）
            ctx = self._execute_phase(ctx, ExecutionPhase.PHASE_2, agent_weights, options)

            # 阶段三：综合分析（可以并行，依赖阶段一二）
            ctx = self._execute_phase(ctx, ExecutionPhase.PHASE_3, agent_weights, options)

            # 聚合阶段
            consensus = self._compute_weighted_consensus(ctx.agent_results, agent_weights)
            top_opportunities = self._extract_top_opportunities(ctx.agent_results, consensus)
            synthesis = self._generate_synthesis(ctx, consensus)

            # 计算成功率
            total_agents = len(ctx.agent_results)
            successful_agents = len(ctx.get_successful_results())
            success_rate = successful_agents / total_agents if total_agents > 0 else 0

            logger.info(f"[Orchestrator] ========== 分析完成 ==========")
            logger.info(f"[Orchestrator] 成功率: {success_rate:.1%} ({successful_agents}/{total_agents})")

            return HierarchicalResult(
                master=self._parse_master_analysis(ctx.master_result),
                agent_results=self._format_agent_results(ctx.agent_results),
                consensus=consensus,
                top_opportunities=top_opportunities,
                synthesis=synthesis,
                execution_log=ctx.execution_log,
                success_rate=success_rate,
                metadata=ctx.metadata,
            )

        except Exception as e:
            logger.error(f"[Orchestrator] 执行异常: {e}", exc_info=True)
            ctx.add_log("error", "system", "ERROR", str(e))
            return HierarchicalResult(
                master=None,
                agent_results={},
                consensus={"consensusPct": 50, "error": str(e)},
                top_opportunities=[],
                synthesis="系统执行异常，请稍后重试",
                execution_log=ctx.execution_log,
                success_rate=0.0,
                metadata={"error": str(e)},
            )

    def _execute_master_phase(self, ctx: ExecutionContext, options) -> ExecutionContext:
        """执行主控阶段"""
        logger.info("[Orchestrator] [阶段0] 执行主控 Agent")
        ctx.add_log("master", "master", "RUNNING", "开始执行主控 Agent")

        start_time = time.time()
        result = self._execute_single_agent(
            agent_id="master",
            ctx=ctx,
            options=options,
            timeout_ms=45000,
        )
        result.execution_time_ms = int((time.time() - start_time) * 1000)

        ctx.master_result = result
        ctx.metadata["master_execution_time_ms"] = result.execution_time_ms

        if result.success:
            logger.info(f"[Orchestrator] [阶段0] 主控 Agent 执行成功 ({result.execution_time_ms}ms)")
            ctx.add_log("master", "master", "COMPLETED",
                       f"执行成功，耗时 {result.execution_time_ms}ms")
        else:
            logger.warning(f"[Orchestrator] [阶段0] 主控 Agent 执行失败: {result.error}")
            ctx.add_log("master", "master", "FAILED", f"执行失败: {result.error}")

        return ctx

    def _execute_phase(
        self,
        ctx: ExecutionContext,
        phase: ExecutionPhase,
        weights: Dict[str, float],
        options,
    ) -> ExecutionContext:
        """执行指定阶段的所有 Agent"""
        phase_agents = [
            agent_id for agent_id, config in AGENT_CORE_OBJECTIVES.items()
            if config["phase"] == phase
        ]

        if not phase_agents:
            return ctx

        logger.info(f"[Orchestrator] [{phase.value}] 执行阶段 Agent: {phase_agents}")
        ctx.add_log(phase.value, "system", "RUNNING", f"开始执行 {phase.value} 阶段")

        # 检查依赖
        agents_to_run = []
        for agent_id in phase_agents:
            config = AGENT_CORE_OBJECTIVES[agent_id]
            deps = config.get("dependencies", [])

            # 检查依赖是否都成功完成
            deps_satisfied = all(
                ctx.agent_results.get(dep_id, TaskResult(agent_id=dep_id, status=TaskStatus.PENDING)).success
                for dep_id in deps
            )

            if deps_satisfied:
                agents_to_run.append(agent_id)
                logger.info(f"[Orchestrator] [{phase.value}] Agent {agent_id} 依赖满足")
            else:
                logger.warning(f"[Orchestrator] [{phase.value}] Agent {agent_id} 依赖未满足，跳过")
                ctx.agent_results[agent_id] = TaskResult(
                    agent_id=agent_id,
                    status=TaskStatus.SKIPPED,
                    success=False,
                    error="依赖未满足",
                )
                ctx.add_log(phase.value, agent_id, "SKIPPED", "依赖未满足，跳过执行")

        # 并行执行阶段内的 Agent
        for agent_id in agents_to_run:
            start_time = time.time()
            config = AGENT_CORE_OBJECTIVES[agent_id]

            ctx.add_log(phase.value, agent_id, "RUNNING",
                       f"开始执行，子任务: {config['subtasks']}")

            result = self._execute_single_agent(
                agent_id=agent_id,
                ctx=ctx,
                options=options,
                timeout_ms=config.get("timeout_ms", 60000),
                extra_context=self._build_agent_context(agent_id, ctx, weights),
            )
            result.execution_time_ms = int((time.time() - start_time) * 1000)

            ctx.agent_results[agent_id] = result

            if result.success:
                logger.info(f"[Orchestrator] [{phase.value}] Agent {agent_id} 执行成功 ({result.execution_time_ms}ms)")
                ctx.add_log(phase.value, agent_id, "COMPLETED",
                           f"执行成功，耗时 {result.execution_time_ms}ms")
            else:
                logger.warning(f"[Orchestrator] [{phase.value}] Agent {agent_id} 执行失败: {result.error}")
                ctx.add_log(phase.value, agent_id, "FAILED",
                           f"执行失败: {result.error}，已重试 {result.retry_count} 次")

        ctx.add_log(phase.value, "system", "COMPLETED", f"{phase.value} 阶段完成")
        return ctx

    def _execute_single_agent(
        self,
        agent_id: str,
        ctx: ExecutionContext,
        options,
        timeout_ms: int = 60000,
        retry_count: int = 0,
        extra_context: Dict = None,
    ) -> TaskResult:
        """
        执行单个 Agent（带重试机制）
        """
        if retry_count >= self.MAX_RETRIES:
            logger.warning(f"[Orchestrator] Agent {agent_id} 达到最大重试次数，返回降级结果")
            return TaskResult(
                agent_id=agent_id,
                status=TaskStatus.FAILED,
                success=False,
                error=f"达到最大重试次数 ({self.MAX_RETRIES})",
                retry_count=retry_count,
            )

        try:
            # 构建消息
            messages = self.registry.build_messages(
                agent_id=agent_id,
                scan_data=ctx.scan_data,
                news_data=ctx.news_data,
                holdings_data=ctx.holdings_data,
                current_time=ctx.current_time,
                scan_date=ctx.scan_date,
                extra_context=extra_context,
            )

            if not messages:
                raise AgentExecutionError(agent_id, "构建消息失败", is_retryable=False)

            # 调用 LLM
            resp = self.client.call_messages(messages, options or self._default_options())

            if not resp.success:
                raise AgentExecutionError(agent_id, resp.error or "调用失败")

            # 解析结果
            parsed = self.registry.extract_json(resp.content)

            return TaskResult(
                agent_id=agent_id,
                status=TaskStatus.COMPLETED,
                success=True,
                result=parsed,
                raw_response=resp.content,
                thinking=getattr(resp, "reasoning_content", "") or "",
                tokens_used=resp.tokens_used or 0,
                retry_count=retry_count,
            )

        except AgentExecutionError as e:
            if e.is_retryable and retry_count < self.MAX_RETRIES:
                logger.warning(f"[Orchestrator] Agent {agent_id} 执行失败，{self.RETRY_DELAY_MS}ms 后重试 ({retry_count + 1}/{self.MAX_RETRIES})")
                time.sleep(self.RETRY_DELAY_MS / 1000)
                return self._execute_single_agent(
                    agent_id=agent_id,
                    ctx=ctx,
                    options=options,
                    timeout_ms=timeout_ms,
                    retry_count=retry_count + 1,
                    extra_context=extra_context,
                )
            else:
                return TaskResult(
                    agent_id=agent_id,
                    status=TaskStatus.FAILED,
                    success=False,
                    error=str(e),
                    retry_count=retry_count,
                )

        except Exception as e:
            logger.error(f"[Orchestrator] Agent {agent_id} 执行异常: {e}", exc_info=True)
            return TaskResult(
                agent_id=agent_id,
                status=TaskStatus.FAILED,
                success=False,
                error=str(e),
                retry_count=retry_count,
            )

    def _build_agent_context(
        self,
        agent_id: str,
        ctx: ExecutionContext,
        weights: Dict[str, float],
    ) -> Dict[str, Any]:
        """构建 Agent 执行上下文"""
        master = ctx.master_result
        if master and master.success and master.result:
            parsed = self.registry.extract_json(master.raw_response) if master.raw_response else {}
        else:
            parsed = {}

        return {
            "master_coordination": parsed.get("coordinationNotes", "基于市场分析执行本策略"),
            "agent_weight": weights.get(agent_id, 1.0),
            "key_theme": parsed.get("keyTheme", "当前主线待确认"),
            "market_phase": parsed.get("marketPhase", "震荡市"),
            "risk_appetite": parsed.get("riskAppetite", "中"),
            "market_core_intent": parsed.get("marketCoreIntent", ""),
            "execution_phase": AGENT_CORE_OBJECTIVES.get(agent_id, {}).get("phase", "").value,
        }

    def _compute_agent_weights(self, ctx: ExecutionContext) -> Dict[str, float]:
        """
        根据主控 Agent 的 agentPriority 计算各子 Agent 的权重
        """
        master = ctx.master_result
        if master and master.success and master.raw_response:
            parsed = self.registry.extract_json(master.raw_response)
            if parsed and parsed.get("agentPriority"):
                priority_list = parsed["agentPriority"]
                weights = {}
                for i, agent_id in enumerate(priority_list):
                    if agent_id in AGENT_CORE_OBJECTIVES:
                        position_weight = 1.0 - (i * 0.1)
                        weights[agent_id] = max(0.3, position_weight)
                # 未在列表中的 Agent 给默认权重
                for agent_id in AGENT_CORE_OBJECTIVES:
                    if agent_id not in weights:
                        weights[agent_id] = 0.5
                logger.info(f"[Orchestrator] Agent 权重（主控指定）: {weights}")
                return weights

        # 默认权重
        weights = {agent_id: 1.0 for agent_id in AGENT_CORE_OBJECTIVES}
        logger.info(f"[Orchestrator] Agent 权重（默认）: {weights}")
        return weights

    def _compute_weighted_consensus(
        self,
        agent_results: Dict[str, TaskResult],
        weights: Dict[str, float],
    ) -> Dict[str, Any]:
        """计算加权共识"""
        total_weight = 0
        weighted_stance = 0
        weighted_confidence = 0
        stance_counts = {"bull": 0, "bear": 0, "neutral": 0}

        stance_map = {"bull": 1, "neutral": 0, "bear": -1}

        for agent_id, result in agent_results.items():
            if not result.success or not result.result:
                continue

            weight = weights.get(agent_id, 1.0)
            stance = result.result.get("stance", "neutral")
            confidence = int(result.result.get("confidence", 50) or 50)

            weighted_stance += stance_map.get(stance, 0) * weight
            weighted_confidence += confidence * weight
            total_weight += weight

            stance_counts[stance] = stance_counts.get(stance, 0) + 1

        if total_weight == 0:
            return {
                "consensusPct": 50,
                "bullCount": 0,
                "bearCount": 0,
                "neutralCount": 0,
                "weightedConfidence": 50,
            }

        raw = weighted_stance / total_weight
        consensus_pct = int(50 + raw * 50)

        return {
            "consensusPct": max(0, min(100, consensus_pct)),
            "bullCount": stance_counts.get("bull", 0),
            "bearCount": stance_counts.get("bear", 0),
            "neutralCount": stance_counts.get("neutral", 0),
            "weightedConfidence": int(weighted_confidence / total_weight),
        }

    def _extract_top_opportunities(
        self,
        agent_results: Dict[str, TaskResult],
        consensus: Dict[str, Any],
    ) -> List[Dict]:
        """提取 TOP 机会"""
        stock_votes = defaultdict(lambda: {
            "code": "",
            "name": "",
            "sector": "",
            "score": 0,
            "changePct": 0,
            "voteCount": 0,
            "agents": [],
            "weightScore": 0,
            "adviseTypes": [],
            "signals": [],
        })

        for agent_id, result in agent_results.items():
            if not result.success or not result.result:
                continue

            rec_stocks = result.result.get("recommendedStocks") or []

            for stock in rec_stocks:
                code = str(stock.get("code", "")).strip()
                if not code:
                    continue

                stock_votes[code]["code"] = code
                stock_votes[code]["name"] = stock.get("name", code)
                stock_votes[code]["sector"] = stock.get("sector", "")
                stock_votes[code]["changePct"] = stock.get("changePct", 0)
                stock_votes[code]["voteCount"] += 1

                agent_name = result.result.get("agentName", agent_id)
                if agent_name not in stock_votes[code]["agents"]:
                    stock_votes[code]["agents"].append(agent_name)

                advise_type = stock.get("adviseType", "")
                if advise_type and advise_type not in stock_votes[code]["adviseTypes"]:
                    stock_votes[code]["adviseTypes"].append(advise_type)

                signal = stock.get("signal", "")
                if signal and signal not in stock_votes[code]["signals"]:
                    stock_votes[code]["signals"].append(signal)

        sorted_stocks = sorted(
            stock_votes.values(),
            key=lambda x: (x["voteCount"], x["weightScore"]),
            reverse=True
        )

        top3 = []
        for i, s in enumerate(sorted_stocks[:3], 1):
            agents_str = "、".join(s["agents"]) if s["agents"] else ""
            top3.append({
                "rank": f"0{i}",
                "title": s["name"],
                "code": s["code"],
                "badge": self._badge_from_score(s["voteCount"]),
                "badgeKind": "primary" if s["voteCount"] >= 3 else "muted",
                "meta": f"共识智能体: {agents_str}" if agents_str else "",
                "chg": s.get("changePct", 0),
                "flowLabel": "资金关注" if s.get("changePct", 0) >= 0 else "资金流出",
                "adviseTypes": s.get("adviseTypes", []),
                "signals": s.get("signals", []),
            })

        return top3

    def _generate_synthesis(self, ctx: ExecutionContext, consensus: Dict[str, Any]) -> str:
        """生成综合建议"""
        lines = []

        # 从主控结果中提取信息
        master_parsed = {}
        if ctx.master_result and ctx.master_result.success and ctx.master_result.raw_response:
            master_parsed = self.registry.extract_json(ctx.master_result.raw_response) or {}

        if master_parsed.get("marketCoreIntent"):
            lines.append(f"【市场核心意图】{master_parsed['marketCoreIntent']}")

        if master_parsed.get("marketPhase"):
            risk = master_parsed.get("riskAppetite", "中")
            lines.append(f"【市场阶段】{master_parsed['marketPhase']} | 【风险偏好】{risk}")

        consensus_pct = consensus.get("consensusPct", 50)
        bull_count = consensus.get("bullCount", 0)
        bear_count = consensus.get("bearCount", 0)

        if bull_count > bear_count:
            sentiment = f"偏多（{bull_count}看多 vs {bear_count}看空）"
        elif bear_count > bull_count:
            sentiment = f"偏空（{bear_count}看空 vs {bull_count}看多）"
        else:
            sentiment = f"中性（{bull_count}看多 vs {bear_count}看空）"

        lines.append(f"【智能体共识】{sentiment} | 全局信心指数: {consensus_pct}%")

        if master_parsed.get("keyTheme"):
            lines.append(f"【主线题材】{master_parsed['keyTheme']}")

        risk_factors = master_parsed.get("riskFactors", [])
        if risk_factors:
            risk_str = "、".join(risk_factors[:2])
            lines.append(f"【风险提示】{risk_str}")

        if master_parsed.get("coordinationNotes"):
            lines.append(f"【操作建议】{master_parsed['coordinationNotes']}")

        return "\n".join(lines)

    def _parse_master_analysis(self, result: Optional[TaskResult]) -> Optional[MasterAnalysis]:
        """解析主控 Agent 分析结果"""
        if not result:
            return None

        if result.success and result.raw_response:
            parsed = self.registry.extract_json(result.raw_response)
            if parsed:
                return MasterAnalysis(
                    market_core_intent=parsed.get("marketCoreIntent", ""),
                    market_phase=parsed.get("marketPhase", ""),
                    risk_appetite=parsed.get("riskAppetite", ""),
                    agent_priority=parsed.get("agentPriority", []),
                    key_theme=parsed.get("keyTheme", ""),
                    risk_factors=parsed.get("riskFactors", []),
                    coordination_notes=parsed.get("coordinationNotes", ""),
                    success=True,
                    raw_response=result.raw_response,
                )

        return MasterAnalysis(success=False)

    def _format_agent_results(self, agent_results: Dict[str, TaskResult]) -> Dict[str, Any]:
        """格式化 Agent 结果"""
        formatted = {}
        for agent_id, result in agent_results.items():
            formatted[agent_id] = {
                "agent_id": agent_id,
                "agent_name": self.registry.get(agent_id).get("name", agent_id) if self.registry.get(agent_id) else agent_id,
                "success": result.success,
                "status": result.status.value,
                "structured": result.result,
                "analysis": result.raw_response,
                "thinking": result.thinking,
                "tokens_used": result.tokens_used,
                "execution_time_ms": result.execution_time_ms,
                "retry_count": result.retry_count,
                "fallback_used": result.fallback_used,
            }
            if not result.success:
                formatted[agent_id]["error"] = result.error
        return formatted

    def _badge_from_score(self, score: float) -> str:
        """根据评分返回徽章文本"""
        if score >= 5:
            return "强力买入"
        elif score >= 3:
            return "增持"
        elif score >= 2:
            return "关注"
        else:
            return "观察"

    def _default_options(self):
        """获取默认调用选项"""
        from utils.llm import CallOptions
        return CallOptions(temperature=0.2, max_tokens=2000)
