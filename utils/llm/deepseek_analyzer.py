"""
深度分析引擎 v2 - 结合现有 Agent Prompt 工程
============================================

架构：
    IntentClassifier → DataProvider → AgentPromptBuilder → DeepSeek/Agent 分析

核心改进：
1. 利用现有 Agent 的专业 Prompt 工程
2. 根据意图选择合适的 Agent 进行分析
3. 支持多 Agent 协作分析
"""

import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# 数据结构
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class AnalysisRequest:
    """分析请求"""
    user_input: str                              # 用户输入
    stock_codes: List[str] = field(default_factory=list)
    intent: Optional[str] = None                 # 已识别的意图
    context: Dict = field(default_factory=dict)
    # 新增：指定使用的 Agent
    preferred_agents: List[str] = field(default_factory=list)  # 如 ['beijing', 'jun']


@dataclass
class AnalysisResult:
    """分析结果"""
    success: bool
    agent_id: str = ""                          # 使用的 Agent ID
    agent_name: str = ""                        # Agent 名称
    content: str = ""
    structured: Dict = field(default_factory=dict)
    data_sources: Dict = field(default_factory=dict)
    thinking: str = ""
    tokens_used: int = 0
    execution_time_ms: int = 0
    error: str = ""

    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'agent_id': self.agent_id,
            'agent_name': self.agent_name,
            'content': self.content,
            'structured': self.structured,
            'data_sources': self.data_sources,
            'thinking': self.thinking,
            'tokens_used': self.tokens_used,
            'execution_time_ms': self.execution_time_ms,
            'error': self.error
        }


# ══════════════════════════════════════════════════════════════════════════════
# Agent 意图映射
# ══════════════════════════════════════════════════════════════════════════════

# 意图 -> 最佳 Agent 映射
INTENT_AGENT_MAP = {
    # 题材热点分析
    'thematic': {
        'primary': 'jun',           # 钧哥 - 龙头战法
        'secondary': ['qiao'],      # 乔帮主 - 板块轮动
        'fallback': 'master'         # 市场首席
    },
    # 技术分析
    'technical': {
        'primary': 'trend',         # 趋势追随者
        'secondary': ['quant'],
        'fallback': 'master'
    },
    # 涨停打板
    'limit_up': {
        'primary': 'beijing',       # 北京炒家 - 游资打板
        'secondary': ['speed'],     # 极速先锋
        'fallback': 'jun'
    },
    # 综合分析
    'comprehensive': {
        'primary': 'master',        # 市场首席
        'secondary': ['jun', 'qiao', 'jia'],
        'fallback': 'deepseek'      # 深度思考者
    },
    # 题材+技术
    'theme_tech': {
        'primary': 'master',
        'secondary': ['jun', 'trend'],
        'fallback': 'deepseek'
    },
    # 情绪分析
    'sentiment': {
        'primary': 'qiao',          # 乔帮主 - 板块轮动/情绪
        'secondary': ['speed'],
        'fallback': 'master'
    },
    # 价值/超跌
    'value': {
        'primary': 'jia',           # 炒股养家 - 低位潜伏
        'secondary': [],
        'fallback': 'master'
    },
    # 新闻事件
    'news': {
        'primary': 'jun',           # 钧哥 - 事件驱动
        'secondary': [],
        'fallback': 'master'
    },
}


# Agent 基础信息
AGENT_INFO = {
    'jun': {'name': '钧哥天下无双', 'style': '龙头战法/事件驱动'},
    'qiao': {'name': '乔帮主', 'style': '板块轮动/情绪周期'},
    'jia': {'name': '炒股养家', 'style': '低位潜伏/价值回归'},
    'speed': {'name': '极速先锋', 'style': '打板/情绪跟随'},
    'trend': {'name': '趋势追随者', 'style': '中线波段/趋势交易'},
    'quant': {'name': '量化之翼', 'style': '量化选股/数据驱动'},
    'deepseek': {'name': '深度思考者', 'style': '深度推理/预期差'},
    'beijing': {'name': '北京炒家', 'style': '游资打板/三有量化'},
    'master': {'name': '市场首席', 'style': '综合协调/全局视角'},
}


# ══════════════════════════════════════════════════════════════════════════════
# Agent Prompt 构建器
# ══════════════════════════════════════════════════════════════════════════════


class AgentPromptBuilder:
    """
    基于现有 Agent Prompt 工程构建分析 Prompt

    使用 agents.py 中定义的：
    - Agent System Prompts (SYSTEM_JUN, SYSTEM_QIAO, ...)
    - Agent Registry 中的配置
    """

    def __init__(self):
        self._init_agents()

    def _init_agents(self):
        """初始化 Agent 模块"""
        try:
            from utils.llm.agents import (
                get_agent_registry,
                SYSTEM_JUNGE, SYSTEM_QIAO, SYSTEM_JIA,
                SYSTEM_SPEED, SYSTEM_TREND, SYSTEM_QUANT,
                SYSTEM_DEEPSEEK, SYSTEM_BEIJING, SYSTEM_MASTER
            )
            self.registry = get_agent_registry
            self.system_prompts = {
                'jun': SYSTEM_JUNGE,
                'qiao': SYSTEM_QIAO,
                'jia': SYSTEM_JIA,
                'speed': SYSTEM_SPEED,
                'trend': SYSTEM_TREND,
                'quant': SYSTEM_QUANT,
                'deepseek': SYSTEM_DEEPSEEK,
                'beijing': SYSTEM_BEIJING,
                'master': SYSTEM_MASTER,
            }
            logger.info("[AgentPromptBuilder] Agent prompts loaded")
        except ImportError as e:
            logger.warning(f"[AgentPromptBuilder] Import error: {e}")
            self.registry = None
            self.system_prompts = {}

    def get_system_prompt(self, agent_id: str) -> str:
        """获取 Agent 的 System Prompt"""
        return self.system_prompts.get(agent_id, '')

    def get_agent_info(self, agent_id: str) -> Dict:
        """获取 Agent 信息"""
        return AGENT_INFO.get(agent_id, {'name': agent_id, 'style': '通用'})

    def build_prompt(self, agent_id: str, user_input: str, data: Dict) -> Dict:
        """
        构建完整的分析 Prompt

        Args:
            agent_id: Agent ID
            user_input: 用户输入
            data: 聚合后的数据

        Returns:
            {
                'system': str,
                'user': str,
                'tools': []
            }
        """
        system = self.get_system_prompt(agent_id)
        if not system:
            system = self._build_default_system(agent_id)

        # 构建用户输入部分
        user_parts = []

        # 用户原始问题
        user_parts.append(f"## 用户请求\n{user_input}\n")

        # 附加数据
        if data.get('market_snapshot'):
            user_parts.append(f"\n## 大盘快照\n{self._format_data(data['market_snapshot'])}")

        # Qwen 生成的数据
        if data.get('news_data'):
            user_parts.append(f"\n## 市场新闻（S/A/B级题材）\n{data['news_data']}")

        if data.get('capital_flow'):
            user_parts.append(f"\n## 板块资金流向\n{data['capital_flow']}")

        if data.get('limit_up'):
            user_parts.append(f"\n## 涨停板分析\n{data['limit_up']}")

        if data.get('sentiment'):
            user_parts.append(f"\n## 市场情绪\n{data['sentiment']}")

        if data.get('technical_data'):
            user_parts.append(f"\n## 技术数据\n{self._format_data(data['technical_data'])}")

        # 输出要求
        user_parts.append(f"""
## ⚠️ 重要约束

你必须严格基于上方「Qwen 联网搜索获取的真实数据」进行分析：
- **连板数**：必须来自「涨停板分析」中的「连板股」数据，禁止捏造连板数！
- **题材级别**：必须基于「市场新闻」中的 S/A/B 级标注
- **资金数据**：必须来自「板块资金流向」中的具体数字
- **如果某数据在上方未提供，不要自行推测填写，宁可写"待观察"！**

## 输出要求

请基于上述数据，给出：
1. **核心观点**（1-2句话）
2. **题材/逻辑分析**（针对用户问题）
3. **技术形态分析**（如果有）
4. **资金流向分析**（如果有）
5. **风险提示**
6. **操作建议**（如有）

请使用中文，格式清晰。
""")

        user = "\n".join(user_parts)

        # 获取 Agent 工具配置
        tools = self._get_agent_tools(agent_id)

        return {
            'system': system,
            'user': user,
            'tools': tools
        }

    def _build_default_system(self, agent_id: str) -> str:
        """构建默认 System Prompt"""
        info = self.get_agent_info(agent_id)
        return f"""你是一位专业的A股分析师，擅长{info['style']}。

请基于提供的数据，给出专业、客观的分析意见。"""

    def _format_data(self, data: Any, max_length: int = 3000) -> str:
        """格式化数据"""
        if not data:
            return "（暂无数据）"

        if isinstance(data, str):
            return data[:max_length] if len(data) > max_length else data

        try:
            text = json.dumps(data, ensure_ascii=False, indent=2)
            return text[:max_length] + "..." if len(text) > max_length else text
        except:
            return str(data)[:max_length]

    def _get_agent_tools(self, agent_id: str) -> List[Dict]:
        """获取 Agent 工具配置"""
        try:
            from utils.llm.agents import AGENT_TOOLS
            return AGENT_TOOLS.get(agent_id, [])
        except:
            return []


# ══════════════════════════════════════════════════════════════════════════════
# DeepSeek 分析器 v2
# ══════════════════════════════════════════════════════════════════════════════


class DeepSeekAnalyzer:
    """
    DeepSeek 深度分析器 v2

    结合现有 Agent Prompt 工程：
    1. 意图识别 → 选择合适的 Agent
    2. 数据获取 → Qwen + AKShare
    3. 使用 Agent 的专业 Prompt
    4. 调用 DeepSeek/Agent 生成分析
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.prompt_builder = AgentPromptBuilder()
        self._init_dependencies()

    def _init_dependencies(self):
        """初始化依赖模块"""
        try:
            from .intent_classifier import classify_intent, DataIntent
            from .data_provider import get_data_provider
            self.classify_intent = classify_intent
            self.DataIntent = DataIntent
            self.get_data_provider = get_data_provider
        except ImportError as e:
            self.logger.warning(f"[DeepSeekAnalyzer] Import warning: {e}")

    def _select_agent(self, intent: str, preferred: List[str] = None) -> str:
        """
        根据意图选择合适的 Agent

        Args:
            intent: 识别的意图
            preferred: 用户偏好的 Agent

        Returns:
            Agent ID
        """
        # 如果用户指定了偏好，优先使用
        if preferred:
            return preferred[0]

        # 根据意图选择
        mapping = INTENT_AGENT_MAP.get(intent, INTENT_AGENT_MAP['comprehensive'])
        return mapping['primary']

    async def analyze(self, request: AnalysisRequest,
                      progress_callback: Callable = None) -> AnalysisResult:
        """
        执行深度分析

        Args:
            request: 分析请求
            progress_callback: 进度回调

        Returns:
            AnalysisResult
        """
        import time
        start_time = time.time()

        try:
            # Step 1: 意图识别
            if not request.intent:
                intent_result = self.classify_intent(request.user_input)
                request.intent = intent_result['intent'].value
                self.logger.info(f"[DeepSeek v2] 意图识别: {request.intent}")

                # 发送意图信息
                await self._send_progress(progress_callback, {
                    'type': 'intent',
                    'intent': request.intent,
                    'primary_source': intent_result.get('primary_source', 'both'),
                    'confidence': intent_result.get('confidence', 0.5)
                })

            # Step 2: 选择 Agent
            agent_id = self._select_agent(request.intent, request.preferred_agents)
            agent_info = self.prompt_builder.get_agent_info(agent_id)

            await self._send_progress(progress_callback, {
                'type': 'status',
                'message': f'正在使用【{agent_info["name"]}】分析...'
            })

            # Step 3: 获取数据
            data_sources = await self._fetch_data(request)

            # Step 4: 构建 Prompt
            prompt_data = self.prompt_builder.build_prompt(
                agent_id, request.user_input, data_sources
            )

            # Step 5: 调用 DeepSeek
            deepseek_result = await self._call_llm(
                system=prompt_data['system'],
                user=prompt_data['user'],
                tools=prompt_data['tools']
            )

            # Step 6: 解析结果
            result = AnalysisResult(
                success=True,
                agent_id=agent_id,
                agent_name=agent_info['name'],
                content=deepseek_result.get('content', ''),
                structured=deepseek_result.get('structured', {}),
                data_sources={k: v for k, v in data_sources.items() if v},
                thinking=deepseek_result.get('thinking', ''),
                tokens_used=deepseek_result.get('tokens_used', 0),
                execution_time_ms=int((time.time() - start_time) * 1000)
            )

            await self._send_progress(progress_callback, {
                'type': 'done',
                'result': result.to_dict()
            })

            return result

        except Exception as e:
            self.logger.error(f"[DeepSeek v2] analyze error: {e}")
            error_result = AnalysisResult(
                success=False,
                error=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000)
            )

            await self._send_progress(progress_callback, {
                'type': 'error',
                'error': str(e)
            })

            return error_result

    def analyze_sync(self, request: AnalysisRequest) -> AnalysisResult:
        """同步版本的分析方法（用于 Flask 路由）"""
        import asyncio
        return asyncio.run(self.analyze(request))

    async def multi_agent_analyze(self, request: AnalysisRequest,
                                  agent_ids: List[str] = None,
                                  progress_callback: Callable = None) -> List[AnalysisResult]:
        """
        多 Agent 协作分析

        Args:
            request: 分析请求
            agent_ids: 要使用的 Agent 列表
            progress_callback: 进度回调

        Returns:
            多个 Agent 的分析结果
        """
        if agent_ids is None:
            # 根据意图自动选择多个 Agent
            intent = request.intent or 'comprehensive'
            mapping = INTENT_AGENT_MAP.get(intent, INTENT_AGENT_MAP['comprehensive'])
            agent_ids = [mapping['primary']] + mapping.get('secondary', [])

        results = []
        for i, agent_id in enumerate(agent_ids):
            request.preferred_agents = [agent_id]

            await self._send_progress(progress_callback, {
                'type': 'status',
                'message': f'[{i+1}/{len(agent_ids)}] 使用【{AGENT_INFO.get(agent_id, {}).get("name", agent_id)}】分析...'
            })

            result = await self.analyze(request, progress_callback)
            results.append(result)

        return results

    async def _fetch_data(self, request: AnalysisRequest) -> Dict:
        """获取数据"""
        provider = self.get_data_provider()
        intent = request.intent or 'comprehensive'

        data = {
            'market_snapshot': {},
            'news_data': '',
            'capital_flow': '',
            'limit_up': '',
            'sentiment': '',
            'technical_data': {}
        }

        try:
            # 始终获取市场快照
            data['market_snapshot'] = provider.fetch_market_snapshot()

            # Qwen 数据（题材/新闻/情绪）
            if intent in ['thematic', 'theme_tech', 'comprehensive', 'limit_up', 'news']:
                # 获取新闻数据
                news_result = provider.fetch_news_data()
                if news_result.get('success'):
                    data['news_data'] = news_result.get('data', '')

                # 获取涨停分析
                limit_result = provider.fetch_limit_up_analysis()
                if limit_result.get('success'):
                    data['limit_up'] = limit_result.get('data', '')

                # 获取情绪数据
                sentiment_result = provider.fetch_sentiment_data()
                if sentiment_result.get('success'):
                    data['sentiment'] = sentiment_result.get('data', '')

                # 获取资金流向
                flow_result = provider.fetch_capital_flow_data()
                if flow_result.get('success'):
                    data['capital_flow'] = flow_result.get('data', '')

            # AKShare 技术数据
            if request.stock_codes and intent in ['technical', 'theme_tech', 'comprehensive']:
                tech_data = {}
                for code in request.stock_codes[:5]:
                    tech = provider.fetch_technical_data(code)
                    if tech:
                        tech_data[code] = tech
                data['technical_data'] = tech_data

        except Exception as e:
            self.logger.error(f"[DeepSeek v2] _fetch_data error: {e}")

        return data

    async def _call_llm(self, system: str, user: str, tools: List[Dict] = None) -> Dict:
        """
        调用 LLM

        支持：
        1. DeepSeek (带 Function Calling)
        2. Qwen (带 Function Calling)
        """
        try:
            # 直接调用 DeepSeek（不使用 Flask 上下文）
            from utils.llm.client import get_client, CallOptions

            client = get_client()

            options = CallOptions(
                model="deepseek-chat",
                temperature=0.7,
                max_tokens=3000
            )

            # 组合 prompt
            full_prompt = f"{system}\n\n用户问题：{user}"

            resp = client.call(full_prompt, "", options)

            result = {
                'content': resp.content or '',
                'structured': {},
                'thinking': getattr(resp, 'reasoning_content', '') or '',
                'tokens_used': resp.tokens_used or 0
            }

            # 尝试解析 JSON
            self._try_parse_structured(result)

            return result

        except Exception as e:
            self.logger.error(f"[DeepSeek v2] _call_llm error: {e}")
            return {'content': '', 'structured': {}, 'thinking': '', 'tokens_used': 0, 'error': str(e)}

    def _try_parse_structured(self, result: Dict):
        """尝试从内容中解析结构化数据，并清理 content 中的 JSON 代码块"""
        import re
        try:
            content = result.get('content', '')
            for pattern in ['```json', '```{json}', '{"']:
                idx = content.find(pattern)
                if idx != -1:
                    json_str = content[idx:]
                    json_str = json_str.replace('```json', '').replace('```', '').strip()
                    result['structured'] = json.loads(json_str)
                    # 去掉 JSON 代码块，只保留 Markdown 总结文字
                    markdown_only = re.sub(r'```json\s*\n?[\s\S]*?\n?```', '', content).strip()
                    result['content'] = markdown_only if markdown_only else content
                    break
        except:
            pass

    async def _send_progress(self, callback: Callable, data: Dict):
        """发送进度"""
        if callback:
            try:
                await callback(data)
            except:
                pass


# ══════════════════════════════════════════════════════════════════════════════
# 全局实例
# ══════════════════════════════════════════════════════════════════════════════

_analyzer = None

def get_deepseek_analyzer() -> DeepSeekAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = DeepSeekAnalyzer()
    return _analyzer
