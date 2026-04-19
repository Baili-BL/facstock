"""
测试完整 Agent 分析流程 - 增强版
"""
import json
import os
from openai import OpenAI
from datetime import datetime
import time

# 清除代理
for k in list(os.environ.keys()):
    if 'proxy' in k.lower():
        del os.environ[k]

DEEPSEEK_API_KEY = 'sk-bac2a0f93a7744858239db7e69979729'

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
    timeout=60,
)

today = datetime.now().strftime('%Y年%m月%d日')

# 系统提示词 - 更明确要求使用工具
system_prompt = """你是一位专业的A股短线交易策略分析师，严格扮演角色【题材猎手】。

你的核心任务是挖掘当日最强题材和龙头股。

绝对约束：
1. 禁止编造股票数据
2. 必须调用 get_limit_up_stocks 获取今日涨停数据
3. 结合涨停数据和市场资讯进行综合分析
4. 用简体中文输出

工作流程：
1. 首先调用 get_limit_up_stocks 获取今日涨停板数据
2. 分析涨停股的特征和题材分布
3. 如需更多信息，调用 web_search 搜索市场资讯
4. 给出最终分析报告"""

user_prompt = f"""请分析今天({today})的A股涨停板情况，找出最强题材和龙头股，给出投资建议。"""

def get_limit_up_stocks():
    """获取东方财富涨停板数据"""
    import requests
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'https://data.eastmoney.com/',
    }
    
    url = 'https://push2.eastmoney.com/api/qt/clist/get'
    params = {
        'pn': 1,
        'pz': 100,
        'po': 1,
        'np': 1,
        'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
        'fltt': 2,
        'invt': 2,
        'fid': 'f3',
        'fs': 'm:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23',
        'fields': 'f12,f14,f2,f3,f4,f5,f6,f62,f184',
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data and data['data']:
                stocks = data['data'].get('diff', [])
                lines = [f"今日涨停股票共 {len(stocks)} 只:\n"]
                for i, s in enumerate(stocks[:50], 1):
                    code = s.get('f12', '')
                    name = s.get('f14', '')
                    price = s.get('f2', 0)
                    change = s.get('f3', 0)
                    amount = s.get('f6', 0)
                    amount_wan = amount / 10000 if amount else 0
                    lines.append(f"{i}. {name}({code}) | 现价:{price} | 涨幅:{change}% | 成交额:{amount_wan:.0f}万")
                return '\n'.join(lines)
    except Exception as e:
        return f"获取涨停数据失败: {e}"
    
    return "暂时无法获取涨停板数据"

def do_web_search(query):
    """百度搜索 - 带重试"""
    import requests
    import re
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    
    for attempt in range(2):
        try:
            url = f"https://www.baidu.com/s?wd={requests.utils.quote(query)}&rn=10"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200 and len(resp.text) > 10000:
                results = []
                pattern1 = r'<h3[^>]*>(.*?)</h3>'
                matches1 = re.findall(pattern1, resp.text, re.DOTALL)
                for m in matches1[:15]:
                    clean = re.sub(r'<[^>]+>', '', m).strip()
                    if len(clean) > 10 and any('\u4e00' <= c <= '\u9fff' for c in clean):
                        results.append(clean)
                
                seen = set()
                unique_results = []
                for r in results:
                    if r not in seen and len(r) > 10:
                        seen.add(r)
                        unique_results.append(r)
                
                if unique_results:
                    return '\n'.join([f"{i+1}. {r}" for i, r in enumerate(unique_results[:8])])
            
            time.sleep(1)  # 重试前等待
        except Exception as e:
            time.sleep(1)
    
    return f"搜索「{query}」暂时无法获取结果"

# 工具定义
tools = [
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web for real-time A-share market news and information",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Search query in Chinese"}}, "required": ["query"]}
    }},
    {"type": "function", "function": {
        "name": "get_limit_up_stocks",
        "description": "Get today's A-share limit-up stocks data from East Money",
        "parameters": {"type": "object", "properties": {}}
    }}
]

print("=" * 70)
print(f"完整 Agent 分析流程测试 - {today}")
print("=" * 70)

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_prompt}
]

max_turns = 6
turn = 0
final_answer = None

while turn < max_turns and not final_answer:
    turn += 1
    print(f"\n{'='*70}")
    print(f"[第{turn}步] 调用 DeepSeek...")
    
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.3,
        max_tokens=3000,
        extra_body={
            "thinking": {"type": "enabled"},
            "enable_search": True,
        },
        tools=tools,
        tool_choice="auto"
    )
    
    response_message = response.choices[0].message
    
    # 检查是否有内容输出
    has_content = response_message.content and response_message.content.strip()
    
    if response_message.tool_calls:
        messages.append(response_message)
        
        tool_call_count = len(response_message.tool_calls)
        print(f"工具调用次数: {tool_call_count}")
        
        for tool_call in response_message.tool_calls:
            func_name = tool_call.function.name
            func_args = tool_call.function.arguments
            
            if func_name == 'get_limit_up_stocks':
                print(f"\n>>> 调用 get_limit_up_stocks()")
                result = get_limit_up_stocks()
                print(result[:300] + "..." if len(result) > 300 else result)
                
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": func_name,
                    "content": result,
                })
            elif func_name == 'web_search':
                args = json.loads(func_args)
                query = args.get('query', '')
                print(f"\n>>> 调用 web_search('{query}')")
                result = do_web_search(query)
                print(result[:200] + "..." if len(result) > 200 else result)
                
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": func_name,
                    "content": result,
                })
    else:
        print("无工具调用")
        final_answer = response_message.content
    
    # 如果有内容输出，也作为最终答案
    if has_content and not response_message.tool_calls:
        final_answer = response_message.content

if final_answer:
    print(f"\n{'='*70}")
    print("最终分析结果:")
    print("=" * 70)
    print(final_answer)
else:
    print("\n未能获取最终答案")
