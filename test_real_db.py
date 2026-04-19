"""
模拟实际 API：用数据库扫描数据 + 工具调用
"""
import json
import os
import sys

for k in list(os.environ.keys()):
    if 'proxy' in k.lower():
        del os.environ[k]

sys.path.insert(0, '/Users/kevin/Desktop/facSstock')

import logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

from utils.llm import get_agent_registry
from junge_trader import format_holdings_for_prompt, format_scan_data_for_prompt
from openai import OpenAI
from datetime import datetime
import database as db

DEEPSEEK_API_KEY = 'sk-bac2a0f93a7744858239db7e69979729'
model = "deepseek-chat"

def _get_limit_up_stocks():
    import requests
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://data.eastmoney.com/',
        'Accept': 'application/json',
    }
    url = 'https://push2.eastmoney.com/api/qt/clist/get'
    params = {'pn': 1, 'pz': 100, 'po': 1, 'np': 1,
              'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
              'fltt': 2, 'invt': 2, 'fid': 'f3',
              'fs': 'm:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23',
              'fields': 'f12,f14,f2,f3,f4,f5,f6,f62,f184'}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data and data['data']:
                stocks = data['data'].get('diff', [])
                lines = [f"今日涨停股票共 {len(stocks)} 只:\n"]
                for i, s in enumerate(stocks[:50], 1):
                    lines.append(f"{i}. {s.get('f14','')}({s.get('f12','')}) | 现价:{s.get('f2',0)} | 涨幅:{s.get('f3',0)}% | 成交额:{s.get('f6',0)//10000}万")
                return '\n'.join(lines)
    except Exception as e:
        print(f"  ⚠️ get_limit_up_stocks 失败: {e}")
    return "暂时无法获取涨停板数据"

def _do_web_search(query):
    import requests, re
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "zh-CN,zh;q=0.9"}
    try:
        url = f"https://www.baidu.com/s?wd={requests.utils.quote(query)}&rn=5"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200 and len(resp.text) > 5000:
            results = []
            for m in re.findall(r'<h3[^>]*>(.*?)</h3>', resp.text, re.DOTALL)[:10]:
                clean = re.sub(r'<[^>]+>', '', m).strip()
                if len(clean) > 10 and any('\u4e00' <= c <= '\u9fff' for c in clean):
                    results.append(clean)
            seen = set()
            unique = [r for r in results if not (r in seen or seen.add(r))][:5]
            if unique:
                return '\n'.join([f"{i+1}. {r}" for i, r in enumerate(unique)])
    except:
        pass
    return f"搜索「{query}」无结果"

# ========== 开始测试 ==========
agent_id = 'beijing'
registry = get_agent_registry()
agent_config = registry.get(agent_id)

print("=" * 70)
print("1. 从数据库获取扫描数据（模拟实际接口）")
print("=" * 70)

latest_scan = db.get_latest_scan()
all_stocks = []
if latest_scan:
    print(f"✅ 扫描时间: {latest_scan.get('scan_time', '')}")
    results_dict = latest_scan.get('results', {})
    for sector_name, sector_data in results_dict.items():
        if isinstance(sector_data, dict):
            for stock in sector_data.get('stocks', []):
                if isinstance(stock, dict):
                    stock['sector'] = sector_name
                    all_stocks.append(stock)
    print(f"   股票数量: {len(all_stocks)}")

    # 显示数据质量
    has_price = sum(1 for s in all_stocks if s.get('price'))
    has_change = sum(1 for s in all_stocks if s.get('changePct') is not None)
    print(f"   有价格: {has_price}/{len(all_stocks)}")
    print(f"   有涨幅: {has_change}/{len(all_stocks)}")
else:
    print("❌ 没有扫描数据")

# 获取新闻和持仓
from ai_service import fetch_market_news
scan_date = latest_scan.get('scan_time', '')[:10] if latest_scan else ""
news_list = fetch_market_news(scan_date)
news_lines = [f"【新闻{idx}】「[{n.get('time','')}] {n.get('title','')}」（{n.get('source','')}）"
              for idx, n in enumerate((news_list or [])[:8], 1)]
news_text = "\n".join(news_lines) if news_lines else "【暂无最新消息】"

try:
    holdings = db.get_holdings_by_agent(agent_id)
    holdings_text = format_holdings_for_prompt(holdings)
except:
    holdings_text = "【暂无历史持仓数据】"

print("\n" + "=" * 70)
print("2. 构建 Prompt（使用 format_scan_data_for_prompt）")
print("=" * 70)

scan_data_text = format_scan_data_for_prompt(all_stocks) if all_stocks else ""
current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')

user_prompt = registry.build_user_prompt(
    agent_id=agent_id,
    scan_data=scan_data_text,
    news_data=news_text,
    holdings_data=holdings_text,
    current_time=current_time,
    scan_date=scan_date,
)
system_content = agent_config.get('system_prompt', '')

print(f"Prompt 长度: {len(user_prompt)} 字符")
print(f"\nPrompt 中的扫描数据部分（前1000字）:")
# 找到扫描数据部分
if "## 本次扫描信息" in user_prompt:
    start = user_prompt.find("## 本次扫描信息")
    end = user_prompt.find("\n\n##", start + 10)
    print(user_prompt[start:end] if end > 0 else user_prompt[start:start+1000])

print("\n" + "=" * 70)
print("3. 调用 DeepSeek（带工具）")
print("=" * 70)

tools = [
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    }},
    {"type": "function", "function": {
        "name": "get_limit_up_stocks",
        "description": "Get today's limit-up stocks",
        "parameters": {"type": "object", "properties": {}}
    }}
]

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com", timeout=300)
messages = [
    {"role": "system", "content": system_content},
    {"role": "user", "content": user_prompt}
]

for turn in range(5):
    print(f"\n[第{turn+1}次调用]")
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
        max_tokens=3000,
        extra_body={"thinking": {"type": "enabled"}, "enable_search": True},
        tools=tools,
        tool_choice="auto",
    )

    msg = response.choices[0].message
    tool_calls = msg.tool_calls or []

    if tool_calls:
        print(f"  调用工具: ", end="")
        
        # 保存 assistant 消息
        assistant_msg = {
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ]
        }
        messages.append(assistant_msg)

        for tc in tool_calls:
            func_name = tc.function.name
            print(f"{func_name} ", end="", flush=True)

            if func_name == 'get_limit_up_stocks':
                result = _get_limit_up_stocks()
            elif func_name == 'web_search':
                args = json.loads(tc.function.arguments)
                query = args.get('query', '')
                print(f"\n    搜索词: {query[:50]}...")
                result = _do_web_search(query)
            else:
                result = f"未知工具: {func_name}"

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": func_name,
                "content": result
            })
        print()
    else:
        print(f"\n✅ 完成！")
        print(f"\n最终结果:")
        print(msg.content[:1500] if msg.content else "(无内容)")
        break

print("\n" + "=" * 70)
