#!/usr/bin/env python3
"""修复 strategy_routes.py 的语法错误"""

# 新的函数定义
NEW_CODE = '''

def _call_llm_with_tools(client, model, messages, tools, temperature, max_tokens):
    """
    调用 LLM 并处理 Function Calling
    返回包含 tool_calls 的响应对象
    支持 DeepSeek 和 Qwen/DashScope 模型
    """
    import json
    import logging
    import os
    from typing import List, Dict
    
    logger = logging.getLogger(__name__)

    try:
        # 判断模型类型
        is_qwen = 'qwen' in model.lower()
        
        if is_qwen:
            # Qwen/DashScope 模型调用
            return _call_dashscope_with_tools(model, messages, tools, temperature, max_tokens)
        else:
            # DeepSeek 模型调用
            return _call_deepseek_with_tools(client, model, messages, tools, temperature, max_tokens)

    except Exception as e:
        logger.error(f"[_call_llm_with_tools] error={e}")
        return SimpleResponse(
            content='',
            tokens_used=0,
            model=model,
            provider='unknown',
            success=False,
            error=str(e),
            tool_calls=[],
        )


def _call_dashscope_with_tools(model, messages, tools, temperature, max_tokens):
    """调用 DashScope/Qwen 模型（支持 Function Calling）"""
    import json
    import requests
    from utils.llm.client import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL
    
    try:
        # 清除代理
        for k in list(os.environ.keys()):
            if 'proxy' in k.lower():
                del os.environ[k]
        
        headers = {
            "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model,
            "input": {"messages": messages},
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "result_format": "message",
            }
        }
        
        # Qwen 的 tools 格式不同
        if tools:
            payload["tools"] = tools
        
        resp = requests.post(
            f"{DASHSCOPE_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        
        if resp.status_code != 200:
            logger.warning(f"[DashScope] HTTP {resp.status_code}: {resp.text[:200]}")
            return SimpleResponse(
                content='',
                tokens_used=0,
                model=model,
                provider='dashscope',
                success=False,
                error=f"HTTP {resp.status_code}",
                tool_calls=[],
            )
        
        data = resp.json()
        output = data.get('output', {})
        choices = output.get('choices', [])
        
        if not choices:
            return SimpleResponse(
                content='',
                tokens_used=data.get('usage', {}).get('total_tokens', 0),
                model=model,
                provider='dashscope',
                success=False,
                error="No choices in response",
                tool_calls=[],
            )
        
        message = choices[0].get('message', {})
        content = message.get('content', [{}])[0].get('text', '') if message.get('content') else ''
        
        # 解析 Qwen 的 tool_calls
        tool_calls = []
        raw_calls = message.get('tool_calls', [])
        for tc in raw_calls:
            func = tc.get('function', {})
            try:
                args = json.loads(func.get('arguments', '{}'))
            except:
                args = {}
            tool_calls.append({
                'id': tc.get('id', f"call_{len(tool_calls)}"),
                'name': func.get('name', ''),
                'arguments': args
            })
        
        return SimpleResponse(
            content=content,
            tokens_used=data.get('usage', {}).get('total_tokens', 0),
            model=model,
            provider='dashscope',
            success=True,
            tool_calls=tool_calls,
        )
        
    except Exception as e:
        logger.error(f"[_call_dashscope_with_tools] error={e}")
        return SimpleResponse(
            content='',
            tokens_used=0,
            model=model,
            provider='dashscope',
            success=False,
            error=str(e),
            tool_calls=[],
        )


def _call_deepseek_with_tools(client, model, messages, tools, temperature, max_tokens):
    """调用 DeepSeek 模型（支持 Function Calling）"""
    import json
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        deepseek_client = client._get_deepseek_client()
        
        extra_body = {
            "thinking": {"type": "enabled"},
            "enable_search": True,
        }
        
        resp = deepseek_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=extra_body,
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
        )
        
        choice = resp.choices[0]
        content = choice.message.content or ''
        reasoning_content = getattr(choice.message, 'reasoning_content', '') or ''
        tokens = resp.usage.total_tokens if resp.usage else 0
        
        # 解析工具调用
        tool_calls = []
        raw_tool_calls = choice.message.tool_calls or []
        for tc in raw_tool_calls:
            if tc.function:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except:
                    args = {}
                tool_calls.append({
                    'id': tc.id or f"call_{len(tool_calls)}",
                    'name': tc.function.name,
                    'arguments': args
                })
        
        return SimpleResponse(
            content=content,
            tokens_used=tokens,
            model=model,
            provider='deepseek',
            success=True,
            reasoning_content=reasoning_content,
            tool_calls=tool_calls,
        )
        
    except Exception as e:
        logger.error(f"[_call_deepseek_with_tools] error={e}")
        return SimpleResponse(
            content='',
            tokens_used=0,
            model=model,
            provider='deepseek',
            success=False,
            error=str(e),
            tool_calls=[],
        )


class SimpleResponse:
    """简单响应对象，包含 tool_calls 支持"""
    def __init__(self, content='', tokens_used=0, model='', provider='',
                 success=True, error='', reasoning_content='', tool_calls=None):
        self.content = content
        self.tokens_used = tokens_used
        self.model = model
        self.provider = provider
        self.success = success
        self.error = error
        self.reasoning_content = reasoning_content
        self.tool_calls = tool_calls or []

'''

# 读取旧文件
with open('/Users/kevin/Desktop/facSstock/strategy_routes.py.bak', 'r') as f:
    content = f.read()

# 找到 _do_web_search 之前的位置
SEARCH_FUNC = '\ndef _do_web_search(query: str) -> str:'
idx = content.find(SEARCH_FUNC)

if idx == -1:
    print("ERROR: Could not find _do_web_search")
    exit(1)

# 提取开头的部分（到 _do_web_search 之前）
head = content[:idx]

# 提取尾部（从 _do_web_search 开始）
tail = content[idx:]

# 组合新内容
new_content = head + NEW_CODE + tail

# 写入新文件
with open('/Users/kevin/Desktop/facSstock/strategy_routes.py', 'w') as f:
    f.write(new_content)

print("File updated successfully!")

# 验证语法
import ast
try:
    ast.parse(new_content)
    print("Syntax check passed!")
except SyntaxError as e:
    print(f"Syntax error: {e}")
