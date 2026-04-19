"""
策略智能体 Prompt 工程 v2（兼容层）
=====================================

此文件已迁移至 `utils.llm.agents`。

**保留理由：** 供旧代码（`junge_trader.py`、`strategy_routes.py` 等）
在迁移期间 import 此文件时仍然可用。

**新代码请直接 import：**
    from utils.llm import get_agent_registry
    from utils.llm.agents import AGENTS, AgentOutput, StockRecommendation

**迁移清单：**
- 所有 Agent 配置    → utils/llm/agents.py 的 AGENTS
- 所有 Prompt 模板  → utils/llm/agents.py 的 SYSTEM_* / USER_COMMON_HEADER
- 所有数据结构      → utils/llm/agents.py 的 AgentOutput / StockRecommendation
- build_messages()  → utils.llm.agents.build_messages()
- extract_json_from_response() → utils.llm.agents.extract_json_from_response()
- sanitize_parsed_agent_output() → utils.llm.agents.sanitize_parsed_agent_output()
- compute_consensus() → utils.llm.agents.compute_consensus()
"""

# ── 兼容性别名（向后兼容）───────────────────────────────────────────────────
from utils.llm.agents import (
    AGENTS,
    AgentOutput,
    StockRecommendation,
    SYSTEM_COMMON,
    SYSTEM_JUNGE,
    SYSTEM_QIAO,
    SYSTEM_JIA,
    SYSTEM_SPEED,
    SYSTEM_TREND,
    SYSTEM_QUANT,
    SYSTEM_DEEPSEEK,
    USER_COMMON_HEADER,
    get_agent,
    build_user_prompt,
    build_messages,
    extract_json_from_response,
    sanitize_parsed_agent_output,
    compute_consensus,
    normalize_agent_stock_code,
    AgentRegistry,
    get_agent_registry,
)

__all__ = [
    # Agent 配置
    "AGENTS",
    "get_agent",
    # 数据结构
    "AgentOutput",
    "StockRecommendation",
    # Prompt 模板
    "SYSTEM_COMMON",
    "SYSTEM_JUNGE",
    "SYSTEM_QIAO",
    "SYSTEM_JIA",
    "SYSTEM_SPEED",
    "SYSTEM_TREND",
    "SYSTEM_QUANT",
    "SYSTEM_DEEPSEEK",
    "USER_COMMON_HEADER",
    # 函数
    "build_user_prompt",
    "build_messages",
    "extract_json_from_response",
    "sanitize_parsed_agent_output",
    "compute_consensus",
    "normalize_agent_stock_code",
    # 注册表
    "AgentRegistry",
    "get_agent_registry",
]
