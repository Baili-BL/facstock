"""
测试脚本 — 批量运行 6 位策略智能体 Prompt，验证腾讯混元 API 输出
用法: python test_agents.py
"""

import os
import sys
import json
import re
import requests
from datetime import datetime

from agent_prompts import AGENTS, build_messages, extract_json_from_response, compute_consensus

HUNYUAN_API_KEY = os.environ.get(
    "HUNYUAN_API_KEY", "sk-YDYlUOiUi5VzumSjhppTWry9bBfWJFbN7IsCLN0XpD1ysM0Z"
)
HUNYUAN_BASE_URL = "https://api.hunyuan.cloud.tencent.com/v1"


# ── 演示数据（带价格和涨跌幅） ──────────────────────────────────────────────
DEMO_SCAN = """
共扫描到 8 只股票，以下为筛选结果：

## 主板股票（请从以下股票中选择推荐）

【股票1】宁德时代（300750）— 78分（A级）
  现价=245.80 | 涨跌幅=+2.35% | 收缩率=12.3% | 带宽=4.8% | 量比=1.85 | CMF=0.142 | RSV=35.2

【股票2】比亚迪（002594）— 72分（B+级）
  现价=198.60 | 涨跌幅=-0.85% | 收缩率=8.1% | 带宽=6.2% | 量比=1.32 | CMF=0.089 | RSV=52.1

【股票3】中国平安（601318）— 68分（B级）
  现价=42.30 | 涨跌幅=-1.20% | 收缩率=5.6% | 带宽=3.9% | 量比=0.95 | CMF=-0.021 | RSV=18.5

【股票4】北方华创（002371）— 85分（S级）
  现价=362.40 | 涨跌幅=+3.42% | 收缩率=15.4% | 带宽=4.1% | 量比=2.31 | CMF=0.203 | RSV=41.0

【股票5】隆基绿能（601012）— 61分（B级）
  现价=38.50 | 涨跌幅=+0.75% | 收缩率=7.2% | 带宽=7.8% | 量比=1.08 | CMF=0.034 | RSV=22.7

【股票6】中国中免（601888）— 65分（B级）
  现价=55.20 | 涨跌幅=-0.45% | 收缩率=4.3% | 带宽=3.2% | 量比=1.65 | CMF=0.111 | RSV=14.2

【股票7】中芯国际（688981）— 79分（A级）
  现价=48.90 | 涨跌幅=+1.85% | 收缩率=11.8% | 带宽=5.5% | 量比=1.93 | CMF=0.178 | RSV=38.9

【股票8】科大讯飞（002230）— 55分（B级）
  现价=42.15 | 涨跌幅=-0.22% | 收缩率=9.2% | 带宽=8.1% | 量比=0.78 | CMF=-0.055 | RSV=67.3

【注意：请仅从上述主板股票中选择推荐】
""".strip()

DEMO_NEWS = """以下是 2026-03-27 及之前的真实新闻，引用时必须原文复制：

【新闻1】「[03-27 09:15] 央行宣布定向降准0.25个百分点，释放长期资金约5000亿」（财联社）
★ 引用规则：必须原文复制「」内的内容，包括时间和标题，禁止改写

【新闻2】「[03-26 14:30] 科技部发布人工智能产业发展白皮书，提出到2027年产业规模翻番」（东方财富）
★ 引用规则：必须原文复制「」内的内容，包括时间和标题，禁止改写

【新闻3】「[03-26 10:45] 半导体设备国产化提速，多家龙头公司获大额订单」（同花顺）
★ 引用规则：必须原文复制「」内的内容，包括时间和标题，禁止改写

【新闻4】「[03-25 16:20] 新能源汽车2月销量同比增长35%，淡季不淡」（富途资讯）
★ 引用规则：必须原文复制「」内的内容，包括时间和标题，禁止改写

【新闻5】「[03-25 09:30] 北向资金当日净流入A股逾120亿元」（财联社）
★ 引用规则：必须原文复制「」内的内容，包括时间和标题，禁止改写
""".strip()


def call_hunyuan(messages, model="hunyuan-lite", temperature=0.3, max_tokens=3000):
    """调用腾讯混元 API"""
    headers = {
        "Authorization": f"Bearer {HUNYUAN_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    resp = requests.post(
        f"{HUNYUAN_BASE_URL}/chat/completions",
        headers=headers, json=payload, timeout=120,
    )
    resp.raise_for_status()
    result = resp.json()
    if "error" in result:
        raise RuntimeError(f"API Error: {result['error']}")
    return result


def test_agent(agent_id: str) -> dict:
    """测试单个 Agent，返回结构化 + markdown"""
    agent = AGENTS[agent_id]
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scan_date = datetime.now().strftime("%Y-%m-%d")
    messages = build_messages(agent, DEMO_SCAN, DEMO_NEWS, "【暂无历史持仓数据】", current_time, scan_date)

    print(f"\n{'='*60}")
    print(f"🤖 {agent['name']}（{agent['role']}）— {agent['adviseType']}策略")
    print(f"{'='*60}")
    print(f"[System Prompt] {len(messages[0]['content'])} 字")
    print(f"[User Prompt]   {len(messages[1]['content'])} 字")

    try:
        result = call_hunyuan(
            messages,
            temperature=agent['temperature'],
            max_tokens=agent['max_tokens'],
        )
        content = result['choices'][0]['message']['content']
        usage = result.get('usage', {})
        structured = extract_json_from_response(content)

        print(f"\n✅ API OK | tokens={usage.get('total_tokens', '?')}")
        print(f"\n{'─'*50}")
        print(f"📋 结构化 JSON 解析结果：")
        print(f"{'─'*50}")
        if structured:
            print(json.dumps(structured, ensure_ascii=False, indent=2))
        else:
            print("⚠️  JSON 解析失败，原始内容：")
            print(content[:800])

        return {
            "agent_id": agent_id,
            "agent_name": agent['name'],
            "success": True,
            "structured": structured,
            "analysis": content,
            "tokens": usage.get("total_tokens", 0),
        }
    except Exception as e:
        print(f"\n❌ 失败: {e}")
        return {"agent_id": agent_id, "agent_name": agent['name'], "success": False, "error": str(e)}


def main():
    print("🚀 策略智能体 Prompt 工程 v2 — 测试开始")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🤖 Agent 数量: {len(AGENTS)}")

    results = []
    for agent_id in ["jun", "qiao", "jia", "speed", "trend", "quant"]:
        r = test_agent(agent_id)
        results.append(r)

    # 汇总
    print(f"\n\n{'='*60}")
    print("📊 汇总")
    print(f"{'='*60}")
    for r in results:
        icon = "✅" if r["success"] else "❌"
        name = r["agent_name"]
        if r["success"]:
            s = r.get("structured") or {}
            stocks = s.get("recommendedStocks", [])
            stance = s.get("stance", "?")
            conf = s.get("confidence", "?")
            print(f"  {icon} {name:12s} | stance={stance} conf={conf}% | 推荐{len(stocks)}只")
        else:
            print(f"  {icon} {name:12s} | {r.get('error', '')[:60]}")

    # 全局共识
    valid = [r['structured'] for r in results if r.get('success') and r.get('structured')]
    if valid:
        consensus = compute_consensus(valid)
        bull = consensus['bullCount']
        bear = consensus['bearCount']
        neutral = consensus['neutralCount']
        pct = consensus['consensusPct']
        print(f"\n🌐 全局共识 | {pct}% | 看多{bull} 看空{bear} 中性{neutral}")

    # 保存
    out = f"agent_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"test_time": datetime.now().isoformat(), "results": [
            {**r, "analysis": r.get("analysis", "")[:500]}
            for r in results
        ]}, f, ensure_ascii=False, indent=2)
    print(f"\n💾 已保存: {out}")


if __name__ == "__main__":
    main()
