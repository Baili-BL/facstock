"""
LLM 统一客户端
==============

单例模式，统一封装所有 LLM Provider 的调用逻辑：
- 阿里云百炼（DashScope / 通义千问）
- 智谱 GLM（Zhipu）

同时统一管理：
- API Key / Base URL / Model 等配置
- 请求日志与错误处理
- Token 用量统计

使用方式：
    from utils.llm import get_client

    client = get_client()
    # 同步调用
    result = client.call(prompt="...", system="...")
    # Agent 调用
    result = client.call_agent(agent_id="jun", scan_data=..., news=..., holdings=...)
"""

import os
import json
import logging
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# 配置常量（统一入口，禁止在其他文件中重复定义）
# ══════════════════════════════════════════════════════════════════════════════

# 当前选中的 Provider：'dashscope'（阿里云百炼）或 'zhipu'（智谱 GLM）或 'deepseek'
LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'deepseek')

# ── 阿里云百炼 ────────────────────────────────────────────────────────────────

DASHSCOPE_API_KEY = os.environ.get('DASHSCOPE_API_KEY', '')
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_MODEL = os.environ.get('DASHSCOPE_MODEL', 'qwen3.6-plus')
DASHSCOPE_TIMEOUT = int(os.environ.get('DASHSCOPE_TIMEOUT', '120'))

# ── DeepSeek ─────────────────────────────────────────────────────────────────

DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')
DEEPSEEK_TIMEOUT = int(os.environ.get('DEEPSEEK_TIMEOUT', '300'))

# ── 智谱 GLM ─────────────────────────────────────────────────────────────────

ZHIPU_API_KEY = os.environ.get('ZHIPU_API_KEY', '')
ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
ZHIPU_MODEL = os.environ.get('ZHIPU_MODEL', 'glm-4-flash')
ZHIPU_TIMEOUT = int(os.environ.get('ZHIPU_TIMEOUT', '120'))

# ══════════════════════════════════════════════════════════════════════════════
# 数据结构
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class LLMResponse:
    """LLM 调用结果"""
    content: str              # 模型原始输出文本
    tokens_used: int = 0      # 消耗的 token 数量
    model: str = ""           # 实际使用的模型名称
    provider: str = ""        # Provider 名称
    success: bool = True      # 是否成功
    error: str = ""           # 错误信息（如有）
    reasoning_content: str = ""  # 思考过程（DeepSeek reasoning 模式）


@dataclass
class CallOptions:
    """LLM 调用选项"""
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 3000
    system: str = ""
    timeout: int = 120


# ══════════════════════════════════════════════════════════════════════════════
# LLM 客户端（单例）
# ══════════════════════════════════════════════════════════════════════════════

_client_instance: Optional['LLMClient'] = None


class LLMClient:
    """
    统一 LLM 客户端

    支持多 Provider 自动路由，提供统一的 call() 接口。
    内部管理 OpenAI 兼容客户端实例的懒加载。
    """

    def __init__(self, provider: str = None):
        self.provider = provider or LLM_PROVIDER
        self._dashscope_client = None
        self._deepseek_client = None
        self._stats = {"calls": 0, "total_tokens": 0}

    # ── 公开接口 ─────────────────────────────────────────────────────────────

    def call(
        self,
        prompt: str,
        system: str = "",
        options: CallOptions = None,
    ) -> LLMResponse:
        """
        统一调用接口。

        Args:
            prompt: 用户输入的 prompt
            system: 系统指令（system prompt）
            options: 调用选项

        Returns:
            LLMResponse 对象
        """
        opts = options or CallOptions()

        if self.provider == 'zhipu':
            return self._call_zhipu(prompt, system, opts)
        elif self.provider == 'deepseek':
            return self._call_deepseek(prompt, system, opts)
        else:
            return self._call_dashscope(prompt, system, opts)

    def call_messages(
        self,
        messages: List[Dict[str, str]],
        options: CallOptions = None,
    ) -> LLMResponse:
        """
        通过消息列表调用（支持多轮对话）。

        Args:
            messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
            options: 调用选项

        Returns:
            LLMResponse 对象
        """
        opts = options or CallOptions()

        if self.provider == 'zhipu':
            return self._call_zhipu_messages(messages, opts)
        elif self.provider == 'deepseek':
            return self._call_deepseek_messages(messages, opts)
        else:
            return self._call_dashscope_messages(messages, opts)

    def is_configured(self) -> bool:
        """检查是否已配置有效的 API Key"""
        if self.provider == 'zhipu':
            return bool(ZHIPU_API_KEY)
        elif self.provider == 'deepseek':
            return bool(DEEPSEEK_API_KEY)
        return bool(DASHSCOPE_API_KEY)

    def stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        return dict(self._stats)

    # ── 阿里云百炼 ───────────────────────────────────────────────────────────

    def _get_dashscope_client(self):
        """懒加载 DashScope OpenAI 客户端"""
        if self._dashscope_client is None:
            import os
            from openai import OpenAI
            # 清除代理环境变量
            for k in list(os.environ.keys()):
                if 'proxy' in k.lower():
                    del os.environ[k]
            try:
                import httpx
                http_client = httpx.Client(trust_env=False, timeout=120.0)
            except Exception:
                http_client = None
            self._dashscope_client = OpenAI(
                api_key=DASHSCOPE_API_KEY,
                base_url=DASHSCOPE_BASE_URL,
                http_client=http_client,
            )
        return self._dashscope_client

    def _call_dashscope(
        self,
        prompt: str,
        system: str,
        options: CallOptions,
    ) -> LLMResponse:
        """调用阿里云百炼（requests 方式，避免代理问题）"""
        import os
        import json
        import requests

        model = options.model or DASHSCOPE_MODEL

        # 清除代理
        for k in list(os.environ.keys()):
            if 'proxy' in k.lower():
                del os.environ[k]

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": options.temperature,
            "max_tokens": options.max_tokens,
        }

        try:
            logger.info(
                "[LLM] provider=dashscope model=%s temperature=%s prompt_len=%d",
                model, options.temperature, len(prompt)
            )

            resp = requests.post(
                f"{DASHSCOPE_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()

            content = data['choices'][0]['message']['content']
            tokens = data.get('usage', {}).get('total_tokens', 0)

            self._stats['calls'] += 1
            self._stats['total_tokens'] += tokens

            logger.info(
                "[LLM] success=true content_len=%d tokens=%d",
                len(content), tokens
            )

            return LLMResponse(
                content=content,
                tokens_used=tokens,
                model=model,
                provider='dashscope',
                success=True,
            )

        except Exception as e:
            logger.error("[LLM] provider=dashscope error=%s", e)
            return LLMResponse(
                content='',
                tokens_used=0,
                model=model,
                provider='dashscope',
                success=False,
                error=str(e),
            )

    def _call_dashscope_messages(
        self,
        messages: List[Dict[str, str]],
        options: CallOptions,
    ) -> LLMResponse:
        """通过 messages 调用百炼"""
        model = options.model or DASHSCOPE_MODEL

        # 提取 system prompt
        system_content = ''
        user_content = ''
        for msg in messages:
            role = msg.get('role', '')
            content = msg.get('content', '')
            if role == 'system':
                system_content = content
            elif role == 'user':
                user_content = content

        return self._call_dashscope(user_content, system_content, options)

    # ── 智谱 GLM ─────────────────────────────────────────────────────────────

    def _call_zhipu(
        self,
        prompt: str,
        system: str,
        options: CallOptions,
    ) -> LLMResponse:
        """调用智谱 GLM"""
        if not ZHIPU_API_KEY:
            return LLMResponse(
                content='',
                tokens_used=0,
                model=ZHIPU_MODEL,
                provider='zhipu',
                success=False,
                error='ZHIPU_API_KEY 未配置',
            )

        model = options.model or ZHIPU_MODEL

        try:
            import urllib.request

            payload = json.dumps({
                "model": model,
                "messages": (
                    [{"role": "system", "content": system}] if system else []
                ) + [{"role": "user", "content": prompt}],
                "temperature": options.temperature,
                "max_tokens": options.max_tokens,
            }).encode('utf-8')

            req = urllib.request.Request(
                f"{ZHIPU_BASE_URL}/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {ZHIPU_API_KEY}",
                    "Content-Type": "application/json",
                },
                method='POST',
            )

            with urllib.request.urlopen(req, timeout=options.timeout) as resp:
                data = json.loads(resp.read())
                content = data['choices'][0]['message']['content'].strip()

                # 估算 token（GLM 不返回 usage 时使用字符数估算）
                usage = data.get('usage', {})
                tokens = usage.get('total_tokens', len(prompt) // 2)

                self._stats['calls'] += 1
                self._stats['total_tokens'] += tokens

                return LLMResponse(
                    content=content,
                    tokens_used=tokens,
                    model=model,
                    provider='zhipu',
                    success=True,
                )

        except Exception as e:
            logger.error("[LLM] provider=zhipu error=%s", e)
            return LLMResponse(
                content='',
                tokens_used=0,
                model=model,
                provider='zhipu',
                success=False,
                error=str(e),
            )

    def _call_zhipu_messages(
        self,
        messages: List[Dict[str, str]],
        options: CallOptions,
    ) -> LLMResponse:
        """通过 messages 调用智谱"""
        system_msgs = []
        user_msgs = []
        for msg in messages:
            if msg.get('role') == 'system':
                system_msgs.append(msg)
            else:
                user_msgs.append(msg)

        payload = {
            "model": options.model or ZHIPU_MODEL,
            "messages": system_msgs + user_msgs,
            "temperature": options.temperature,
            "max_tokens": options.max_tokens,
        }

        try:
            import urllib.request

            data_bytes = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                f"{ZHIPU_BASE_URL}/chat/completions",
                data=data_bytes,
                headers={
                    "Authorization": f"Bearer {ZHIPU_API_KEY}",
                    "Content-Type": "application/json",
                },
                method='POST',
            )

            with urllib.request.urlopen(req, timeout=options.timeout) as resp:
                result = json.loads(resp.read())
                content = result['choices'][0]['message']['content'].strip()
                tokens = result.get('usage', {}).get('total_tokens', 0)

                self._stats['calls'] += 1
                self._stats['total_tokens'] += tokens

                return LLMResponse(
                    content=content,
                    tokens_used=tokens,
                    model=options.model or ZHIPU_MODEL,
                    provider='zhipu',
                    success=True,
                )

        except Exception as e:
            logger.error("[LLM] provider=zhipu messages error=%s", e)
            return LLMResponse(
                content='',
                tokens_used=0,
                model=options.model or ZHIPU_MODEL,
                provider='zhipu',
                success=False,
                error=str(e),
            )

    # ── DeepSeek ─────────────────────────────────────────────────────────────────

    def _get_deepseek_client(self):
        """懒加载 DeepSeek OpenAI 客户端"""
        if self._deepseek_client is None:
            import os
            from openai import OpenAI
            for k in list(os.environ.keys()):
                if 'proxy' in k.lower():
                    del os.environ[k]
            try:
                import httpx
                http_client = httpx.Client(trust_env=False, timeout=300.0)
            except Exception:
                http_client = None
            self._deepseek_client = OpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_BASE_URL,
                http_client=http_client,
            )
        return self._deepseek_client

    def _call_deepseek(
        self,
        prompt: str,
        system: str,
        options: CallOptions,
    ) -> LLMResponse:
        """调用 DeepSeek（chat.completions + 思考模式）"""
        model = options.model or DEEPSEEK_MODEL

        try:
            client = self._get_deepseek_client()
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=options.temperature,
                max_tokens=options.max_tokens,
                extra_body={"thinking": {"type": "enabled"}},
            )

            choice = resp.choices[0]
            content = choice.message.content or ''
            reasoning_content = choice.message.reasoning_content or ''
            tokens = resp.usage.total_tokens if resp.usage else 0

            self._stats['calls'] += 1
            self._stats['total_tokens'] += tokens

            logger.info(
                "[LLM] provider=deepseek model=%s content_len=%d reasoning_len=%d tokens=%d",
                model, len(content), len(reasoning_content), tokens
            )

            # content 包含 reasoning_content + 最终答案，分离处理
            # reasoning_content 单独存储，content 只保留最终答案
            return LLMResponse(
                content=content,
                tokens_used=tokens,
                model=model,
                provider='deepseek',
                success=True,
                reasoning_content=reasoning_content,
            )

        except Exception as e:
            logger.error("[LLM] provider=deepseek error=%s", e)
            return LLMResponse(
                content='',
                tokens_used=0,
                model=model,
                provider='deepseek',
                success=False,
                error=str(e),
            )

    def _call_deepseek_messages(
        self,
        messages: List[Dict[str, str]],
        options: CallOptions,
    ) -> LLMResponse:
        """通过 messages 调用 DeepSeek（chat.completions + 思考模式）"""
        model = options.model or DEEPSEEK_MODEL

        try:
            client = self._get_deepseek_client()
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=options.temperature,
                max_tokens=options.max_tokens,
                extra_body={
                    "thinking": {"type": "enabled"},
                    "enable_search": True,
                },
            )

            choice = resp.choices[0]
            content = choice.message.content or ''
            reasoning_content = choice.message.reasoning_content or ''
            tokens = resp.usage.total_tokens if resp.usage else 0

            self._stats['calls'] += 1
            self._stats['total_tokens'] += tokens

            logger.info(
                "[LLM] provider=deepseek messages model=%s content_len=%d reasoning_len=%d tokens=%d",
                model, len(content), len(reasoning_content), tokens
            )

            return LLMResponse(
                content=content,
                tokens_used=tokens,
                model=model,
                provider='deepseek',
                success=True,
                reasoning_content=reasoning_content,
            )

        except Exception as e:
            logger.error("[LLM] provider=deepseek messages error=%s", e)
            return LLMResponse(
                content='',
                tokens_used=0,
                model=model,
                provider='deepseek',
                success=False,
                error=str(e),
            )

    # ── Agent 场景封装 ─────────────────────────────────────────────────────

    def call_agent(
        self,
        agent_id: str,
        scan_data: str = "",
        news_data: str = "",
        holdings_data: str = "",
        current_time: str = "",
        scan_date: str = None,
        candidates: List[Dict] = None,
        extra_context: Dict = None,
    ) -> Dict:
        """
        调用指定 Agent 的完整流程。

        整合 Prompt 构建 → LLM 调用 → JSON 解析 → 输出清洗。

        Args:
            agent_id: Agent ID（如 "jun", "qiao" 等）
            scan_data: 格式化的扫描数据文本
            news_data: 格式化的新闻数据文本
            holdings_data: 格式化的持仓数据文本
            current_time: 当前时间字符串
            scan_date: 扫描日期
            candidates: 原始候选股列表（用于清洗验证）
            extra_context: 额外上下文（如大盘涨跌、市场情绪等）

        Returns:
            对齐 AgentOutput 结构的结果字典：
            {
                "agentId", "agentName", "stance", "confidence",
                "marketCommentary", "positionAdvice", "riskWarning",
                "recommendedStocks": [...],
                "tokens_used", "raw_response", "success"
            }
        """
        from utils.llm.agents import get_agent_registry

        registry = get_agent_registry()
        agent = registry.get(agent_id)

        if not agent:
            logger.warning("[LLM] call_agent failed: agent_id=%s not found", agent_id)
            return {"success": False, "error": f"Agent '{agent_id}' not found"}

        # 构建 Prompt
        messages = registry.build_messages(
            agent_id=agent_id,
            scan_data=scan_data,
            news_data=news_data,
            holdings_data=holdings_data,
            current_time=current_time,
            scan_date=scan_date,
            extra_context=extra_context,
        )

        # 调用 LLM（支持 per-agent model 覆盖）
        options = CallOptions(
            model=agent.get('model', ''),
            temperature=agent.get('temperature', 0.3),
            max_tokens=agent.get('max_tokens', 3000),
        )

        resp = self.call_messages(messages, options)

        if not resp.success or not resp.content:
            logger.warning("[LLM] call_agent failed: agent_id=%s resp=%s", agent_id, resp.error)
            return {
                "success": False,
                "error": resp.error or "LLM 调用返回为空",
                "tokens_used": resp.tokens_used,
            }

        logger.info(
            "[LLM] call_agent success: agent_id=%s tokens=%d content_preview=%.100s...",
            agent_id, resp.tokens_used, resp.content[:100]
        )

        # 解析 JSON
        parsed = registry.extract_json(resp.content)

        if parsed:
            # 清洗输出
            parsed = registry.sanitize(
                parsed,
                candidates or [],
                default_advise_type=agent.get('adviseType', '波段'),
            )
        else:
            logger.warning("[LLM] JSON 解析失败，agent=%s raw=%.200s", agent_id, resp.content[:200])

        # 构建推荐股列表
        recommended = []
        if parsed:
            for s in (parsed.get('recommendedStocks') or [])[:3]:
                code = s.get('code', '')
                src = next((c for c in (candidates or []) if c.get('code') == code), {})
                recommended.append({
                    'code': s.get('code', '') or src.get('code', ''),
                    'name': s.get('name', '') or src.get('name', ''),
                    'sector': s.get('sector', '') or src.get('sector', ''),
                    # 使用 if is not None 判断，保留 0 这样的有效值
                    'price': s.get('price') if s.get('price') is not None else src.get('price', 0),
                    'changePct': s.get('changePct') if s.get('changePct') is not None else src.get('changePct', 0),
                    'score': s.get('score') if s.get('score') is not None else src.get('score', 0),
                    'grade': s.get('grade', '') or src.get('grade', ''),
                    'buyRange': s.get('buyRange', '') or src.get('buyRange', ''),
                    'stopLoss': s.get('stopLoss', '') or src.get('stopLoss', ''),
                    'targetPrice': s.get('targetPrice', ''),
                    'holdPeriod': s.get('holdPeriod', ''),
                    'positionRatio': s.get('positionRatio', ''),
                    'signal': s.get('signal', ''),
                    'riskLevel': s.get('riskLevel', ''),
                    'safetyMargin': s.get('safetyMargin', ''),
                    'valuation': s.get('valuation', ''),
                    'adviseType': s.get('adviseType', '') or agent.get('adviseType', '波段'),
                    'meta': s.get('meta', ''),
                })

        return {
            'success': True,
            'agentId': agent_id,
            'agentName': agent.get('name', ''),
            'stance': parsed.get('stance', 'neutral') if parsed else 'neutral',
            'confidence': int(parsed.get('confidence', 50)) if parsed else 50,
            'marketCommentary': str(parsed.get('marketCommentary', '')) if parsed else '',
            'positionAdvice': str(parsed.get('positionAdvice', '')) if parsed else '',
            'riskWarning': str(parsed.get('riskWarning', '')) if parsed else '',
            'recommendedStocks': recommended,
            'raw_response': resp.content,
            'structured': parsed,
            'tokens_used': resp.tokens_used,
        }


# ══════════════════════════════════════════════════════════════════════════════
# 单例访问函数
# ══════════════════════════════════════════════════════════════════════════════


def get_client(provider: str = None) -> LLMClient:
    """
    获取 LLM 客户端单例。

    Args:
        provider: 可选，强制指定 Provider（覆盖环境变量）

    Returns:
        LLMClient 单例实例
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = LLMClient(provider=provider)
    return _client_instance


def reset_client():
    """重置客户端单例（用于切换 Provider 或更换 API Key）"""
    global _client_instance
    _client_instance = None
