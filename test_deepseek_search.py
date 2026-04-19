"""
测试 DeepSeek 联网搜索 - 使用东方财富API获取实时数据
"""
import json
import os
import requests
from openai import OpenAI
from datetime import datetime

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

def get_limit_up_stocks():
    """获取东方财富涨停板数据"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'https://data.eastmoney.com/',
    }
    
    url = 'https://push2.eastmoney.com/api/qt/clist/get'
    params = {
        'pn': 1,
        'pz': 100,  # 获取100只
        'po': 1,
        'np': 1,
        'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
        'fltt': 2,
        'invt': 2,
        'fid': 'f3',
        'fs': 'm:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23',  # 涨停板筛选
        'fields': 'f12,f14,f2,f3,f4,f5,f6,f62,f184',
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data and data['data']:
                stocks = data['data'].get('diff', [])
                results = []
                for s in stocks[:50]:  # 取前50只
                    results.append({
                        'code': s.get('f12', ''),      # 股票代码
                        'name': s.get('f14', ''),      # 股票名称
                        'price': s.get('f2', 0),       # 最新价
                        'change': s.get('f3', 0),       # 涨跌幅
                        'volume': s.get('f5', 0),      # 成交量
                        'amount': s.get('f6', 0),      # 成交额
                        'net_inflow': s.get('f62', 0), # 主力净流入
                    })
                return results
    except Exception as e:
        return None
    return None

def format_stocks_for_ai(stocks):
    """格式化股票数据为AI可读的文本"""
    if not stocks:
        return "暂无数据"
    
    lines = []
    for i, s in enumerate(stocks, 1):
        amount_wan = s['amount'] / 10000 if s['amount'] else 0
        net_inflow_wan = s['net_inflow'] / 10000 if s['net_inflow'] else 0
        
        lines.append(f"{i}. {s['name']}({s['code']}) | 现价:{s['price']} | 涨幅:{s['change']}% | 成交额:{amount_wan:.0f}万")
    
    return '\n'.join(lines)

# 工具定义
tools = [{
    "type": "function",
    "function": {
        "name": "get_limit_up_stocks",
        "description": "获取今日A股涨停板数据，包括股票代码、名称、现价、涨幅、成交额等",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}]

print("=" * 60)
print(f"测试: DeepSeek + 东方财富实时涨停数据")
print(f"日期: {today}")
print("=" * 60)

# 先获取实时数据
print("\n[获取实时涨停数据]")
stocks = get_limit_up_stocks()
if stocks:
    print(f"获取到 {len(stocks)} 只涨停股票")
    formatted = format_stocks_for_ai(stocks[:20])  # 只显示前20只
    print("\n涨停股票列表(前20只):")
    print(formatted)
else:
    print("获取涨停数据失败")

messages = [
    {"role": "system", "content": "你是一个专业的A股短线交易专家。请根据提供的涨停板数据，分析今日涨停板特征、热点板块、龙头股，并给出投资建议。用中文回答。"},
    {"role": "user", "content": f"请分析今天({today})的A股涨停板情况，给出详细分析。"}
]

max_turns = 3
turn = 0

while turn < max_turns:
    turn += 1
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )
    response_message = response.choices[0].message
    
    if response_message.content:
        print(f"\n[模型第{turn}步]:\n{response_message.content[:500]}")
    
    if response_message.tool_calls:
        messages.append(response_message)
        
        for tool_call in response_message.tool_calls:
            func_name = tool_call.function.name
            
            if func_name == 'get_limit_up_stocks':
                print(f"\n>>> 调用: get_limit_up_stocks()")
                result = get_limit_up_stocks()
                formatted_result = format_stocks_for_ai(result)
                
                print(f"获取到 {len(result) if result else 0} 只涨停股票")
                print(formatted_result[:500] if formatted_result else "")
                
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": func_name,
                    "content": formatted_result,
                })
    else:
        print(f"\n{'='*60}")
        print("最终分析结果:")
        print("=" * 60)
        print(response_message.content)
        break
