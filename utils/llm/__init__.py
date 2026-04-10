"""
LLM 统一管理模块
=================

统一管理所有 LLM 调用、Provider 切换、模型配置和输出解析。

架构层次：
- llm/client.py    — LLM 客户端（单例），封装所有 Provider 调用
- llm/agents.py   — Agent 注册表、Prompt 模板、数据结构、输出解析
- llm/__init__.py — 统一导出

使用示例：
    from utils.llm import get_client, get_agent_registry

    # 获取 LLM 客户端
    client = get_client()

    # 调用 LLM
    result = client.call(prompt="...", system="...", model="qwen3.6-plus")

    # 获取 Agent 注册表
    registry = get_agent_registry()
    agent = registry.get("jun")
"""

from utils.llm.client import LLMClient, get_client, CallOptions
from utils.llm.agents import AgentRegistry, get_agent_registry

__all__ = [
    "LLMClient",
    "get_client",
    "CallOptions",
    "AgentRegistry",
    "get_agent_registry",
]
