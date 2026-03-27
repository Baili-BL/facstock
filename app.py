#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
布林带收缩策略 - Flask Web 应用
"""

import sys
sys.stdout.reconfigure(line_buffering=True)

from flask import Flask, jsonify, request
import logging
import os
from flask import send_from_directory, abort

import database as db
from ai_service import get_ai_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 注册蓝图（所有 /api/* 路由统一由蓝图处理）
from ticai.routes import ticai_bp
from market_routes import market_bp
from strategy_routes import strategy_bp
app.register_blueprint(ticai_bp)
app.register_blueprint(market_bp)
app.register_blueprint(strategy_bp)

# ==================== AI 分析接口（保留在 app.py，与蓝图不冲突） ====================

@app.route('/api/ai/config', methods=['GET'])
def get_ai_config():
    ai_service = get_ai_service()
    return jsonify({'success': True, 'configured': ai_service.is_configured()})

@app.route('/api/ai/config', methods=['POST'])
def set_ai_config():
    try:
        data = request.get_json()
        api_key = data.get('api_key', '')
        if not api_key:
            return jsonify({'success': False, 'error': '请提供 API Key'})
        ai_service = get_ai_service(api_key)
        return jsonify({'success': True, 'configured': ai_service.is_configured()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ai/analyze', methods=['POST'])
def ai_analyze():
    try:
        ai_service = get_ai_service()
        if not ai_service.is_configured():
            return jsonify({'success': False, 'error': 'AI 服务未配置'})
        latest_scan = db.get_latest_scan()
        if not latest_scan:
            return jsonify({'success': False, 'error': '没有可分析的扫描数据，请先执行扫描'})
        results_dict = latest_scan.get('results', {})
        all_stocks = []
        for sector_name, sector_data in results_dict.items():
            if isinstance(sector_data, dict):
                for stock in sector_data.get('stocks', []):
                    if isinstance(stock, dict):
                        stock['sector'] = sector_name
                        all_stocks.append(stock)
        if not all_stocks:
            return jsonify({'success': False, 'error': '扫描结果为空，请重新执行扫描'})
        from datetime import datetime
        scan_data = {'results': all_stocks, 'scan_time': latest_scan.get('scan_time', '')}
        current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')
        result = ai_service.analyze_stocks(scan_data, current_time)
        if result.get('success'):
            scan_id = latest_scan.get('id')
            report_id = db.save_ai_report(
                analysis=result.get('analysis', ''),
                model=result.get('model', ''),
                tokens_used=result.get('tokens_used', 0),
                scan_id=scan_id,
                scan_data_summary=f"共{len(all_stocks)}只股票"
            )
            result['report_id'] = report_id
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ai/reports')
def get_ai_reports():
    try:
        limit = request.args.get('limit', 20, type=int)
        reports = db.get_ai_reports(limit)
        for report in reports:
            if report.get('analysis'):
                report['preview'] = report['analysis'][:100] + '...' if len(report['analysis']) > 100 else report['analysis']
                del report['analysis']
        return jsonify({'success': True, 'data': reports})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ai/reports/<int:report_id>')
def get_ai_report(report_id: int):
    try:
        report = db.get_ai_report(report_id)
        if report:
            return jsonify({'success': True, 'data': report})
        return jsonify({'success': False, 'error': '报告不存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ai/reports/<int:report_id>', methods=['DELETE'])
def delete_ai_report(report_id: int):
    try:
        if db.delete_ai_report(report_id):
            return jsonify({'success': True, 'message': '删除成功'})
        return jsonify({'success': False, 'error': '报告不存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ai/reports/clear', methods=['DELETE'])
def clear_ai_reports():
    try:
        count = db.delete_all_ai_reports()
        return jsonify({'success': True, 'message': f'已删除 {count} 条报告'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== 策略智能体 API ====================

@app.route('/api/agents/prompts')
def get_agent_prompts():
    """返回所有智能体的元信息（供前端展示）"""
    try:
        from agent_prompts import AGENTS
        agents_info = [
            {
                "id": a["id"],
                "name": a["name"],
                "role": a["role"],
                "style": a["style"],
                "tagline": a["tagline"],
                "adviseType": a["adviseType"],
            }
            for a in AGENTS.values()
        ]
        return jsonify({"success": True, "data": agents_info})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/agents/analyze/<agent_id>', methods=['POST'])
def analyze_with_agent(agent_id):
    """
    使用指定智能体的 Prompt 工程调用腾讯混元 API
    POST body: { "api_key": "..." }   （可选，默认使用 env 中的 key）
    返回结构化 JSON + 原始 markdown 供前端直接消费
    """
    try:
        from agent_prompts import get_agent, build_messages, extract_json_from_response
        import requests

        agent = get_agent(agent_id)
        if not agent:
            return jsonify({"success": False, "error": f"未知 Agent ID: {agent_id}"})

        # 取 API Key
        data = request.get_json() or {}
        api_key = data.get('api_key') or os.environ.get('HUNYUAN_API_KEY')
        if not api_key:
            return jsonify({"success": False, "error": "请提供 HUNYUAN_API_KEY"})

        # 取最新扫描数据
        latest_scan = db.get_latest_scan()
        if not latest_scan:
            return jsonify({"success": False, "error": "没有可分析的扫描数据，请先执行扫描"})
        results_dict = latest_scan.get('results', {})
        all_stocks = []
        for sector_name, sector_data in results_dict.items():
            if isinstance(sector_data, dict):
                for stock in sector_data.get('stocks', []):
                    if isinstance(stock, dict):
                        stock['sector'] = sector_name
                        all_stocks.append(stock)
        if not all_stocks:
            return jsonify({"success": False, "error": "扫描结果为空"})

        scan_data_text = _format_scan_data_for_agent(all_stocks)
        from ai_service import fetch_market_news
        from datetime import datetime
        scan_date = latest_scan.get('scan_time', '')[:10]
        news_list = fetch_market_news(scan_date)
        news_text = _format_news_for_agent(news_list)
        current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')
        messages = build_messages(agent, scan_data_text, news_text, current_time, scan_date)

        # 调用混元
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }
        payload = {
            'model': 'hunyuan-lite',
            'messages': messages,
            'temperature': agent['temperature'],
            'max_tokens': agent['max_tokens'],
            'stream': False,
        }
        resp = requests.post(
            'https://api.hunyuan.cloud.tencent.com/v1/chat/completions',
            headers=headers, json=payload, timeout=120,
        )
        result = resp.json()
        if 'error' in result:
            return jsonify({"success": False, "error": result['error'].get('message', 'API 错误')})

        content = result['choices'][0]['message']['content']
        usage = result.get('usage', {})

        # 解析结构化 JSON
        structured = extract_json_from_response(content)

        return jsonify({
            "success": True,
            "agent_id": agent_id,
            "agent_name": agent['name'],
            "structured": structured,        # 结构化数据（前端直接用）
            "analysis": content,            # 原始 markdown
            "tokens_used": usage.get('total_tokens', 0),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/agents/batch', methods=['POST'])
def batch_analyze_agents():
    """
    批量运行全部 6 个智能体（并行）
    POST body: { "api_key": "..." }
    返回：
      - consensus: 全局共识数据（供 AISummaryDetail 环形图）
      - agentResults[]: 每个 Agent 的结构化输出（供主力头寸卡片）
      - consensusOpportunities[]: TOP 3 共识股票（供核心投资机会区块）
    """
    try:
        import concurrent.futures, requests
        from agent_prompts import AGENTS, build_messages, extract_json_from_response, compute_consensus
        from ai_service import fetch_market_news
        from datetime import datetime

        data = request.get_json() or {}
        api_key = data.get('api_key') or os.environ.get('HUNYUAN_API_KEY')
        if not api_key:
            return jsonify({"success": False, "error": "请提供 HUNYUAN_API_KEY"})

        latest_scan = db.get_latest_scan()
        if not latest_scan:
            return jsonify({"success": False, "error": "没有可分析的扫描数据"})
        results_dict = latest_scan.get('results', {})
        all_stocks = []
        for sector_name, sector_data in results_dict.items():
            if isinstance(sector_data, dict):
                for stock in sector_data.get('stocks', []):
                    if isinstance(stock, dict):
                        stock['sector'] = sector_name
                        all_stocks.append(stock)
        if not all_stocks:
            return jsonify({"success": False, "error": "扫描结果为空"})

        scan_data_text = _format_scan_data_for_agent(all_stocks)
        scan_date = latest_scan.get('scan_time', '')[:10]
        news_list = fetch_market_news(scan_date)
        news_text = _format_news_for_agent(news_list)
        current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }

        def call_one(agent):
            try:
                messages = build_messages(agent, scan_data_text, news_text, current_time, scan_date)
                payload = {
                    'model': 'hunyuan-lite',
                    'messages': messages,
                    'temperature': agent['temperature'],
                    'max_tokens': agent['max_tokens'],
                    'stream': False,
                }
                resp = requests.post(
                    'https://api.hunyuan.cloud.tencent.com/v1/chat/completions',
                    headers=headers, json=payload, timeout=120,
                )
                result = resp.json()
                if 'error' in result:
                    return {"agent_id": agent['id'], "success": False, "error": result['error'].get('message')}
                content = result['choices'][0]['message']['content']
                structured = extract_json_from_response(content)
                return {
                    "agent_id": agent['id'],
                    "agent_name": agent['name'],
                    "success": True,
                    "structured": structured,
                    "analysis": content,
                    "tokens_used": result.get('usage', {}).get('total_tokens', 0),
                }
            except Exception as e:
                return {"agent_id": agent['id'], "success": False, "error": str(e)}

        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(call_one, a): a_id for a_id, a in AGENTS.items()}
            for future in concurrent.futures.as_completed(futures):
                r = future.result()
                results[r['agent_id']] = r

        agent_list = [results[aid] for aid in AGENTS]

        # 计算全局共识
        valid_structured = [r['structured'] for r in agent_list if r.get('success') and r.get('structured')]
        consensus = compute_consensus(valid_structured)

        # 聚合 TOP 3：统计各股票被多少 Agent 推荐，取前 3
        stock_votes = {}
        for out in valid_structured:
            for s in out.get('recommendedStocks', []):
                key = s.get('code') or ''
                if not key:
                    continue
                if key not in stock_votes:
                    stock_votes[key] = {
                        "code": key,
                        "name": s.get('name', key),
                        "sector": s.get('sector', ''),
                        "score": s.get('score', 0),
                        "changePct": s.get('changePct', 0),
                        "voteCount": 0,
                        "agents": [],
                        "badge": _badge_from_stance(out.get('stance', 'bull')),
                        "badgeKind": "primary",
                        "meta": "",
                    }
                stock_votes[key]['voteCount'] += 1
                agent_name = out.get('agentName', '')
                if agent_name and agent_name not in stock_votes[key]['agents']:
                    stock_votes[key]['agents'].append(agent_name)

        sorted_stocks = sorted(stock_votes.values(), key=lambda x: (x['voteCount'], x['score']), reverse=True)
        top3 = []
        for i, s in enumerate(sorted_stocks[:3]):
            agents_str = "、".join(s['agents']) if s['agents'] else ""
            top3.append({
                "rank": f"0{i+1}",
                "title": s['name'],
                "badge": _badge_from_tag(s['score']),
                "badgeKind": "primary" if s['score'] >= 70 else "muted",
                "meta": f"共识智能体: {agents_str}" if agents_str else "",
                "chg": s['changePct'],
                "flowLabel": "资金关注" if s['changePct'] >= 0 else "资金流出",
            })

        return jsonify({
            "success": True,
            "scan_time": scan_date,
            "consensus": consensus,
            "agentResults": agent_list,
            "consensusOpportunities": top3,
            "lastUpdated": current_time,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


def _format_scan_data_for_agent(all_stocks):
    """把扫描结果格式化为文本，注入 prompt"""
    main_board = [s for s in all_stocks if str(s.get('code', '')).startswith(('60', '00'))]
    main_board.sort(key=lambda x: x.get('total_score', 0), reverse=True)
    lines = [f"共扫描到 {len(all_stocks)} 只股票，以下为筛选结果：\n"]
    if main_board:
        lines.append("## 主板股票（请从以下股票中选择推荐）")
        for i, s in enumerate(main_board[:15], 1):
            name = s.get('name', '') or ''
            code = s.get('code', '') or ''
            price = s.get('current_price') or s.get('price') or 0
            change_pct = s.get('change_pct') or s.get('changePct') or 0
            lines.append(
                f"【股票{i}】{name}（{code}）— "
                f"{s.get('total_score', 0)}分（{s.get('grade', 'N/A')}级）"
            )
            lines.append(
                f"  现价={price:.2f} | 涨跌幅={change_pct:+.2f}% | "
                f"收缩率={s.get('squeeze_ratio', 0):.1f}% | "
                f"带宽={s.get('bb_width_pct', 0):.2f}% | "
                f"量比={s.get('volume_ratio', 0):.2f} | "
                f"CMF={s.get('cmf', 0):.3f} | "
                f"RSV={s.get('rsv', 0):.1f}"
            )
        lines.append("")
        lines.append("【注意：请仅从上述主板股票中选择推荐】")
    return "\n".join(lines)


def _badge_from_stance(stance: str) -> str:
    mapping = {"bull": "看多", "bear": "看空", "neutral": "中性"}
    return mapping.get(stance, "中性")


def _badge_from_tag(score: int) -> str:
    if score >= 80:
        return "强力买入"
    elif score >= 65:
        return "增持"
    else:
        return "观察名单"
    return "\n".join(lines)


def _format_news_for_agent(news_list):
    if not news_list:
        return "【暂无最新消息】"
    lines = [f"以下是今日及之前的真实新闻，引用时必须原文复制：\n"]
    for i, n in enumerate(news_list[:10], 1):
        lines.append(f"【新闻{i}】「[{n.get('time','')}] {n.get('title','')}」（{n.get('source','')}）")
    lines.append("\n★ 引用规则：必须原文复制「」内内容，禁止改写")
    return "\n".join(lines)


# ==================== 静态文件服务 ====================

DIST_DIR = os.path.join(os.path.dirname(__file__), 'dist')

@app.route('/frontend')
@app.route('/frontend/')
def serve_frontend():
    if not os.path.isdir(DIST_DIR):
        return ('<h2>请先构建前端</h2>'
                '<p>在 <code>frontend/</code> 目录下运行：</p>'
                '<pre>npm install\nnpm run build</pre>'
                '<p>构建完成后，访问 <a href="/frontend">/frontend</a> 即可。</p>'
                '<hr><p>开发模式下可同时运行 Vite：<code>cd frontend && npm run dev</code></p>',
                200, {'Content-Type': 'text/html; charset=utf-8'})
    return send_from_directory(DIST_DIR, 'index.html')

@app.route('/frontend/<path:filename>')
def serve_frontend_assets(filename):
    if not os.path.isdir(DIST_DIR):
        abort(404)
    return send_from_directory(DIST_DIR, filename)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5002)
