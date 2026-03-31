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

os.environ.setdefault('LLM_PROVIDER', 'deepseek')
os.environ.setdefault('DEEPSEEK_API_KEY', 'sk-f288fe90b4694dbbb841d439936b48ab')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 注册蓝图（所有 /api/* 路由统一由蓝图处理）
from ticai.routes import ticai_bp
from market_routes import market_bp
from strategy_routes import strategy_bp
from tv_udf_routes import tv_udf_bp
app.register_blueprint(ticai_bp)
app.register_blueprint(market_bp)
app.register_blueprint(strategy_bp)
app.register_blueprint(tv_udf_bp, url_prefix='/tv_udf')

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
    使用指定智能体的 Prompt 工程调用 LLM API（支持混元/DeepSeek）
    POST body: { "provider": "tencent"|"deepseek", "api_key": "..." }
    返回结构化 JSON + 原始 markdown 供前端直接消费
    """
    try:
        from agent_prompts import get_agent, build_messages, extract_json_from_response, sanitize_parsed_agent_output
        import requests

        agent = get_agent(agent_id)
        if not agent:
            return jsonify({"success": False, "error": f"未知 Agent ID: {agent_id}"})

        # 取 Provider 和 API Key
        data = request.get_json() or {}
        provider = data.get('provider') or os.environ.get('LLM_PROVIDER', 'deepseek')
        api_key = data.get('api_key') or os.environ.get(
            'HUNYUAN_API_KEY' if provider == 'tencent' else 'DEEPSEEK_API_KEY', ''
        )
        if not api_key:
            return jsonify({"success": False, "error": f"请提供 {provider} 的 API Key"})

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
        from junge_trader import format_holdings_for_prompt
        from datetime import datetime
        scan_date = latest_scan.get('scan_time', '')[:10]
        news_list = fetch_market_news(scan_date)
        news_text = _format_news_for_agent(news_list)
        try:
            holdings = db.get_all_holdings()
            holdings_text = format_holdings_for_prompt(holdings)
        except Exception:
            holdings_text = "【暂无历史持仓数据】"
        current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')
        messages = build_messages(agent, scan_data_text, news_text, holdings_text, current_time, scan_date)

        # 调用 LLM（支持混元 / DeepSeek）
        logger.info("[AgentAnalyze] agent_id=%s provider=%s model=%s temperature=%s max_tokens=%s messages_count=%d",
                    agent_id, provider,
                    'deepseek-chat' if provider == 'deepseek' else 'hunyuan-lite',
                    agent['temperature'], agent['max_tokens'], len(messages))

        if provider == 'deepseek':
            resp = requests.post(
                'https://api.deepseek.com/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    "model": "deepseek-chat",
                    "messages": messages,
                    "temperature": agent['temperature'],
                    "max_tokens": agent['max_tokens'],
                    "stream": False,
                },
                timeout=120,
            )
        else:
            resp = requests.post(
                'https://api.hunyuan.cloud.tencent.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    "model": "hunyuan-lite",
                    "messages": messages,
                    "temperature": agent['temperature'],
                    "max_tokens": agent['max_tokens'],
                    "stream": False,
                },
                timeout=120,
            )
        result = resp.json()
        logger.info("[AgentAnalyze] agent_id=%s provider=%s raw_response_len=%d usage=%s",
                    agent_id, provider,
                    len(resp.text), result.get('usage', {}))
        if 'error' in result:
            return jsonify({"success": False, "error": result['error'].get('message', 'API 错误')})

        content = result['choices'][0]['message']['content']
        usage = result.get('usage', {})

        # 解析结构化 JSON，并剔除不在扫描表中的虚构推荐 / Prompt 占位句
        logger.info("[AgentAnalyze] agent_id=%s content_preview=%.80s...",
                    agent_id, content[:80])
        structured = extract_json_from_response(content)
        if structured:
            logger.info("[AgentAnalyze] agent_id=%s parsed stance=%s confidence=%s recommendedStocks_count=%d",
                        agent_id, structured.get('stance'), structured.get('confidence'),
                        len(structured.get('recommendedStocks') or []))
            structured = sanitize_parsed_agent_output(
                structured, all_stocks, default_advise_type=agent['adviseType'])
            logger.info("[AgentAnalyze] agent_id=%s after_sanitize recommendedStocks_count=%d",
                        agent_id, len(structured.get('recommendedStocks') or []))
        else:
            logger.warning("[AgentAnalyze] agent_id=%s JSON 解析失败，raw content 前200字: %.200s",
                           agent_id, content[:200])

        # 持久化分析历史（Agent+日期唯一，历史锁定）
        try:
            report_date = datetime.now().strftime('%Y-%m-%d')
            ar_payload = {'structured': structured, 'raw_text': content}
            snap = db.build_analysis_holdings_snapshot(holdings, ar_payload)
            db.save_agent_analysis_history(
                agent_id=agent_id,
                report_date=report_date,
                holdings_snapshot=snap,
                analysis_result=ar_payload,
                raw_response=content,
                stance=structured.get('stance', '') if structured else '',
                confidence=int(structured.get('confidence', 0)) if structured else 0,
                tokens_used=usage.get('total_tokens', 0),
            )
            logger.info(f"[AgentAnalyze] 历史已写入 agent_id={agent_id} date={report_date}")
        except Exception as hist_err:
            logger.warning(f"[AgentAnalyze] 保存分析历史失败: {hist_err}")

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
        from agent_prompts import AGENTS, build_messages, extract_json_from_response, compute_consensus, sanitize_parsed_agent_output
        from ai_service import fetch_market_news
        from datetime import datetime

        data = request.get_json() or {}
        provider = data.get('provider') or os.environ.get('LLM_PROVIDER', 'deepseek')
        api_key = data.get('api_key') or os.environ.get(
            'HUNYUAN_API_KEY' if provider == 'tencent' else 'DEEPSEEK_API_KEY', ''
        )
        if not api_key:
            return jsonify({"success": False, "error": f"请提供 {provider} 的 API Key"})

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
        try:
            holdings = db.get_all_holdings()
            from junge_trader import format_holdings_for_prompt
            holdings_text = format_holdings_for_prompt(holdings)
        except Exception:
            holdings_text = "【暂无历史持仓数据】"
        current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }

        def call_one(agent):
            try:
                messages = build_messages(agent, scan_data_text, news_text, holdings_text, current_time, scan_date)
                if provider == 'deepseek':
                    resp = requests.post(
                        'https://api.deepseek.com/chat/completions',
                        headers=headers,
                        json={
                            "model": "deepseek-chat",
                            "messages": messages,
                            "temperature": agent['temperature'],
                            "max_tokens": agent['max_tokens'],
                            "stream": False,
                        },
                        timeout=120,
                    )
                else:
                    resp = requests.post(
                        'https://api.hunyuan.cloud.tencent.com/v1/chat/completions',
                        headers=headers,
                        json={
                            "model": "hunyuan-lite",
                            "messages": messages,
                            "temperature": agent['temperature'],
                            "max_tokens": agent['max_tokens'],
                            "stream": False,
                        },
                        timeout=120,
                    )
                result = resp.json()
                logger.info("[Batch] agent_id=%s provider=%s raw_response_len=%d usage=%s",
                            agent['id'], provider, len(resp.text), result.get('usage', {}))
                if 'error' in result:
                    return {"agent_id": agent['id'], "success": False, "error": result['error'].get('message')}
                content = result['choices'][0]['message']['content']
                logger.info("[Batch] agent_id=%s content_preview=%.80s...",
                            agent['id'], content[:80])
                structured = extract_json_from_response(content)
                if structured:
                    logger.info("[Batch] agent_id=%s parsed stance=%s confidence=%s recommendedStocks_count=%d",
                                agent['id'], structured.get('stance'), structured.get('confidence'),
                                len(structured.get('recommendedStocks') or []))
                    structured = sanitize_parsed_agent_output(
                        structured, all_stocks, default_advise_type=agent['adviseType'])
                    logger.info("[Batch] agent_id=%s after_sanitize recommendedStocks_count=%d",
                                agent['id'], len(structured.get('recommendedStocks') or []))
                else:
                    logger.warning("[Batch] agent_id=%s JSON 解析失败，raw content 前200字: %.200s",
                                  agent['id'], content[:200])
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

        # 持久化每个 Agent 的分析历史
        report_date = datetime.now().strftime('%Y-%m-%d')
        for r in agent_list:
            if r.get('success'):
                try:
                    ar_payload = {'structured': r.get('structured'), 'raw_text': r.get('analysis')}
                    snap = db.build_analysis_holdings_snapshot(holdings, ar_payload)
                    db.save_agent_analysis_history(
                        agent_id=r.get('agent_id', ''),
                        report_date=report_date,
                        holdings_snapshot=snap,
                        analysis_result=ar_payload,
                        raw_response=r.get('analysis', ''),
                        stance=r.get('structured', {}).get('stance', '') if r.get('structured') else '',
                        confidence=int(r.get('structured', {}).get('confidence', 0)) if r.get('structured') else 0,
                        tokens_used=r.get('tokens_used', 0),
                    )
                except Exception as hist_err:
                    logger.warning(f"[BatchAnalyze] 保存 Agent 历史失败 {r.get('agent_id')}: {hist_err}")

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
CHARTING_LIB_DIR = os.path.join(os.path.dirname(__file__), 'charting_library')


@app.route('/charting_library/<path:filename>')
def serve_charting_library(filename):
    """TradingView Charting Library 静态资源（含 mobile_white.html）"""
    if '..' in filename or filename.startswith(('/', '\\')):
        abort(404)
    full = os.path.normpath(os.path.join(CHARTING_LIB_DIR, filename))
    if not full.startswith(os.path.normpath(CHARTING_LIB_DIR + os.sep)):
        abort(404)
    if not os.path.isfile(full):
        abort(404)
    if filename.endswith('.html'):
        abort(403)
    return send_from_directory(CHARTING_LIB_DIR, filename)


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

# ─────────────────────────────────────────────────────────────────────────────
# 持仓管理 API
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/holdings', methods=['GET'])
def api_get_holdings():
    """获取所有持仓"""
    try:
        holdings = db.get_all_holdings()
        total_count = len(holdings)
        total_position_value = sum(
            (h.get('position_ratio', 0) or 0) for h in holdings
        )
        total_profit_loss = sum(
            (h.get('profit_loss_amount', 0) or 0) for h in holdings
        )
        return jsonify({
            'success': True,
            'data': {
                'holdings': holdings,
                'totalPositionCount': total_count,
                'totalPositionValue': round(total_position_value, 2),
                'totalProfitLoss': round(total_profit_loss, 2),
            }
        })
    except Exception as e:
        logging.error(f"获取持仓失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/holdings', methods=['POST'])
def api_save_holding():
    """新增/更新单条持仓"""
    try:
        data = request.get_json() or {}
        code = data.get('code') or data.get('stock_code')
        name = data.get('name') or data.get('stock_name')
        if not code or not name:
            return jsonify({'success': False, 'error': '缺少 code 或 name'}), 400

        ok = db.upsert_holding(
            code=code,
            name=name,
            sector=data.get('sector', ''),
            avg_cost=float(data.get('avgCost', 0) or 0),
            current_price=float(data.get('currentPrice', 0) or 0),
            position_ratio=float(data.get('positionRatio', 0) or 0),
            profit_loss_pct=float(data.get('profitLossPct', 0) or 0),
            profit_loss_amount=float(data.get('profitLossAmount', 0) or 0),
            hold_days=int(data.get('holdDays', 0) or 0),
            position_type=data.get('positionType', 'long'),
            remark=data.get('remark', ''),
        )
        return jsonify({'success': ok})
    except Exception as e:
        logging.error(f"保存持仓失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/holdings/batch', methods=['POST'])
def api_save_holdings_batch():
    """批量新增/更新持仓"""
    try:
        data = request.get_json() or {}
        holdings_list = data.get('holdings', [])
        if not holdings_list:
            return jsonify({'success': False, 'error': '缺少 holdings 列表'}), 400

        count = db.upsert_holdings_batch(holdings_list)
        return jsonify({'success': True, 'updated': count})
    except Exception as e:
        logging.error(f"批量保存持仓失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/holdings/<code>', methods=['DELETE'])
def api_delete_holding(code):
    """删除一条持仓"""
    try:
        ok = db.delete_holding(code)
        return jsonify({'success': ok})
    except Exception as e:
        logging.error(f"删除持仓失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/agents/<agent_id>/analysis/latest', methods=['GET'])
def api_get_latest_agent_analysis(agent_id):
    """获取某 Agent 最新一次分析记录（含持仓快照和分析结果）"""
    try:
        record = db.get_latest_agent_analysis(agent_id)
        if record is None:
            return jsonify({'success': False, 'error': '未找到该 Agent 的分析记录'}), 404
        return jsonify({'success': True, 'data': record})
    except Exception as e:
        import traceback
        logging.error(f"获取 Agent 分析历史失败 [{agent_id}]: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': f'服务器内部错误: {str(e)}'}), 500


@app.route('/api/agents/<agent_id>/analysis/history', methods=['GET'])
def api_get_agent_analysis_history(agent_id):
    """获取某 Agent 所有历史分析记录"""
    try:
        limit = request.args.get('limit', 10, type=int)
        records = db.get_agent_analysis_history(agent_id, limit=limit)
        return jsonify({'success': True, 'data': records})
    except Exception as e:
        import traceback
        logging.error(f"获取 Agent 分析历史失败 [{agent_id}]: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': f'服务器内部错误: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5002)
