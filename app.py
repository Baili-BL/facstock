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

# 加载 .env 文件
from dotenv import load_dotenv
load_dotenv()

import database as db
from utils.llm import get_client

os.environ.setdefault('LLM_PROVIDER', 'deepseek')
os.environ.setdefault('DASHSCOPE_API_KEY', 'sk-bac2a0f93a7744858239db7e69979729')
os.environ.setdefault('DASHSCOPE_MODEL', 'deepseek-chat')

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
    client = get_client()
    return jsonify({'success': True, 'configured': client.is_configured()})

@app.route('/api/ai/config', methods=['POST'])
def set_ai_config():
    try:
        data = request.get_json()
        api_key = data.get('api_key', '')
        if not api_key:
            return jsonify({'success': False, 'error': '请提供 API Key'})
        # 设置到环境变量，下次 get_client() 会使用新配置
        os.environ['DASHSCOPE_API_KEY'] = api_key
        client = get_client()
        return jsonify({'success': True, 'configured': client.is_configured()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ai/analyze', methods=['POST'])
def ai_analyze():
    """
    AI 分析接口（已迁移到统一的 Agent 系统）
    实际调用 /api/agents/analyze/jun
    """
    try:
        client = get_client()
        if not client.is_configured():
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

        from utils.llm import get_agent_registry
        from datetime import datetime

        registry = get_agent_registry()
        scan_data_text = ""
        scan_date = latest_scan.get('scan_time', '')[:10]
        news_list = []
        from ai_service import fetch_market_news
        for idx, n in enumerate((fetch_market_news(scan_date) or [])[:8], 1):
            news_list.append(f"【新闻{idx}】「[{n.get('time','')}] {n.get('title','')}」（{n.get('source','')}）")
        news_text = "\n".join(news_list) if news_list else "【暂无最新消息】"

        try:
            holdings = db.get_all_holdings()
            from junge_trader import format_holdings_for_prompt
            holdings_text = format_holdings_for_prompt(holdings)
        except Exception:
            holdings_text = "【暂无历史持仓数据】"

        current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')

        messages = registry.build_messages(
            agent_id='jun',
            scan_data=scan_data_text,
            news_data=news_text,
            holdings_data=holdings_text,
            current_time=current_time,
            scan_date=scan_date,
        )

        from utils.llm import CallOptions
        options = CallOptions(temperature=0.25, max_tokens=3000)
        resp = client.call_messages(messages, options)

        if not resp.success:
            return jsonify({'success': False, 'error': f'AI 分析失败: {resp.error}'})

        structured = registry.extract_json(resp.content)
        if structured:
            structured = registry.sanitize(structured, all_stocks, default_advise_type='波段')
            analysis_text = structured.get('marketCommentary', '') + '\n\n' + structured.get('positionAdvice', '')
        else:
            analysis_text = resp.content

        scan_id = latest_scan.get('id')
        report_id = db.save_ai_report(
            analysis=analysis_text,
            model=f"{resp.provider}/{resp.model}",
            tokens_used=resp.tokens_used,
            scan_id=scan_id,
            scan_data_summary=f"共{len(all_stocks)}只股票"
        )

        return jsonify({
            'success': True,
            'analysis': analysis_text,
            'model': f"{resp.provider}/{resp.model}",
            'tokens_used': resp.tokens_used,
            'report_id': report_id
        })
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


@app.route('/api/agents/<agent_id>/prompt')
def get_agent_prompt_detail(agent_id):
    """返回单个 Agent 的 system_prompt 和 user_prompt_template（供前端展示）"""
    try:
        from utils.llm import get_agent_registry
        registry = get_agent_registry()
        agent = registry.get(agent_id)
        if not agent:
            return jsonify({"success": False, "error": f"未知 Agent ID: {agent_id}"}), 404
        return jsonify({
            "success": True,
            "data": {
                "id": agent.get("id"),
                "name": agent.get("name"),
                "role": agent.get("role"),
                "tagline": agent.get("tagline", ""),
                "adviseType": agent.get("adviseType", ""),
                "system_prompt": agent.get("system_prompt", ""),
                "user_prompt_template": agent.get("user_prompt_template", ""),
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/agents/analyze/<agent_id>', methods=['POST'])
def analyze_with_agent(agent_id):
    """
    使用统一 AgentRegistry（与 junge_trader.py 完全一致）调用 LLM API。
    确保所有 Agent 的结果数据一致。

    POST body: { "provider": "dashscope", "api_key": "..." }
    返回结构化 JSON + 原始 markdown 供前端直接消费
    """
    try:
        # 使用与 junge_trader.py 完全相同的 AgentRegistry
        from utils.llm import get_client, get_agent_registry
        from ai_service import fetch_market_news, fetch_junge_enhanced_news
        from junge_trader import format_holdings_for_prompt, format_scan_data_for_prompt
        from openai import OpenAI
        from datetime import datetime

        registry = get_agent_registry()
        client = get_client()
        agent_config = registry.get(agent_id)

        if not agent_config:
            return jsonify({"success": False, "error": f"未知 Agent ID: {agent_id}"})

        # 取 Provider 和 API Key
        data = request.get_json() or {}
        from utils.llm.client import DASHSCOPE_API_KEY as _DEFAULT_KEY
        api_key = data.get('api_key') or os.environ.get('DASHSCOPE_API_KEY', '') or _DEFAULT_KEY
        # DeepSeek 配置
        DEEPSEEK_BASE_URL = "https://api.deepseek.com"
        model = data.get('model') or os.environ.get('DASHSCOPE_MODEL', 'deepseek-chat')
        if not api_key:
            return jsonify({"success": False, "error": "请提供 API Key"})

        # 取最新扫描数据
        latest_scan = db.get_latest_scan()
        all_stocks = []
        if latest_scan:
            results_dict = latest_scan.get('results', {})
            for sector_name, sector_data in results_dict.items():
                if isinstance(sector_data, dict):
                    for stock in sector_data.get('stocks', []):
                        if isinstance(stock, dict):
                            stock['sector'] = sector_name
                            all_stocks.append(stock)
            scan_data_text = format_scan_data_for_prompt(all_stocks) if all_stocks else ""
            scan_date = latest_scan.get('scan_time', '')[:10]
        else:
            scan_data_text = ""
            scan_date = ""

        # 根据 Agent 类型获取新闻（钧哥使用增强版新闻）
        if agent_id == 'jun':
            news_list = fetch_junge_enhanced_news(scan_date)
        else:
            news_list = fetch_market_news(scan_date)

        news_lines = []
        for idx, n in enumerate((news_list or [])[:8], 1):
            news_lines.append(
                f"【新闻{idx}】「[{n.get('time','')}] {n.get('title','')}」（{n.get('source','')}）"
            )
        news_text = "\n".join(news_lines) if news_lines else "【暂无最新消息】"

        # 获取持仓数据（按 agent_id 过滤，避免不同 agent 持仓混用）
        try:
            holdings = db.get_holdings_by_agent(agent_id)
            holdings_text = format_holdings_for_prompt(holdings)
        except Exception:
            holdings_text = "【暂无历史持仓数据】"

        current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')

        # 构建 User Prompt（与 junge_trader.py 完全一致）
        user_prompt = registry.build_user_prompt(
            agent_id=agent_id,
            scan_data=scan_data_text,
            news_data=news_text,
            holdings_data=holdings_text,
            current_time=current_time,
            scan_date=scan_date,
        )

        # 获取 System Prompt
        system_content = agent_config.get('system_prompt', '')

        # 调用阿里云百炼 API（使用与 junge_trader.py 完全相同的参数）
        logger.info("[AgentAnalyze] agent_id=%s model=%s temperature=%s max_tokens=%s",
                    agent_id, model, agent_config.get('temperature', 0.3), agent_config.get('max_tokens', 3000))

        client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, timeout=300)
        # DeepSeek 联网搜索 + 深度思考
        extra_body = {
            "thinking": {"type": "enabled"},
            "enable_search": True,
        }
        tools = [
            {"type": "function", "function": {
                "name": "web_search",
                "description": "Search the web for real-time A-share market news and information",
                "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Search query in Chinese"}}, "required": ["query"]}
            }},
            {"type": "function", "function": {
                "name": "get_limit_up_stocks",
                "description": "Get today's A-share limit-up (涨停) stocks data from East Money, including stock code, name, price, change percentage, and trading volume",
                "parameters": {"type": "object", "properties": {}}
            }}
        ]

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt}
        ]

        # 处理工具调用循环（DeepSeek 可能多次调用 web_search）
        MAX_TOOL_CALLS = 5
        for _ in range(MAX_TOOL_CALLS):
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=agent_config.get('temperature', 0.3),
                max_tokens=agent_config.get('max_tokens', 3000),
                extra_body=extra_body,
                tools=tools,
                tool_choice="auto",
            )
            choice = response.choices[0]
            msg = choice.message

            # 有内容，直接使用
            if msg.content and msg.content.strip():
                content = msg.content
                reasoning_content = msg.reasoning_content or ''
                usage = response.usage
                break

            # 有工具调用，执行并继续
            tool_calls = msg.tool_calls or []
            if tool_calls:
                for tc in tool_calls:
                    func_name = tc.function.name
                    func_args = tc.function.arguments
                    if func_name == 'web_search':
                        import json as _json
                        args = _json.loads(func_args)
                        query = args.get('query', '')
                        search_result = _do_web_search(query)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": search_result or "未找到相关数据",
                        })
                    elif func_name == 'get_limit_up_stocks':
                        stocks = _get_limit_up_stocks()
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": stocks,
                        })
                    else:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": f"未知工具: {func_name}",
                        })
                # 继续循环
                continue
            else:
                # 既没有内容也没有工具调用（异常情况）
                content = msg.content or ''
                reasoning_content = msg.reasoning_content or ''
                usage = response.usage
                break
        else:
            # 工具调用超过上限
            content = ''
            reasoning_content = ''
            usage = None

        thinking_text = reasoning_content

        logger.info("[AgentAnalyze] agent_id=%s response_len=%d usage=%s thinking_len=%d",
                    agent_id, len(content) if content else 0,
                    usage.total_tokens if usage else 0, len(thinking_text))

        # 解析结构化 JSON
        logger.info("[AgentAnalyze] agent_id=%s content_preview=%.80s...",
                    agent_id, content[:80] if content else '')
        structured = registry.extract_json(content)

        # 使用与 junge_trader.py 完全相同的 sanitize 逻辑
        if structured:
            structured = registry.sanitize(
                structured,
                all_stocks,
                default_advise_type=agent_config.get('adviseType', '波段'),
            )
            # 用扫描数据回填涨跌幅和现价
            structured = _enrich_stocks_with_scan_data(structured, all_stocks)
            logger.info("[AgentAnalyze] agent_id=%s parsed stance=%s confidence=%s recommendedStocks_count=%d",
                        agent_id, structured.get('stance'), structured.get('confidence'),
                        len(structured.get('recommendedStocks') or []))
        else:
            logger.warning("[AgentAnalyze] agent_id=%s JSON 解析失败，raw content 前200字: %.200s",
                           agent_id, content[:200] if content else '')

        # 持久化分析历史
        try:
            report_date = datetime.now().strftime('%Y-%m-%d')
            rec_stocks = structured.get('recommendedStocks', []) if structured else []
            logger.info(f"[AgentAnalyze] agent_id={agent_id} rec_stocks_count={len(rec_stocks)}")
            
            ar_payload = {
                'structured': structured,
                'raw_text': content,
                'thinking': thinking_text,
                'marketCommentary': structured.get('marketCommentary', '') if structured else '',
                'positionAdvice': structured.get('positionAdvice', '') if structured else '',
                'riskWarning': structured.get('riskWarning', '') if structured else '',
                'stance': structured.get('stance', '') if structured else '',
                'confidence': structured.get('confidence', 0) if structured else 0,
                'recommendedStocks': rec_stocks,
            }
            
            # 持倉快照：優先使用 AI 推薦股票（與持倉頁面保持一致）
            # 只有當推薦股票為空且有真實持倉時才使用真實持倉
            if rec_stocks:
                snap = db.snapshot_rows_from_recommended_stocks(rec_stocks)
            else:
                snap = db.snapshot_rows_from_db_holdings(db.get_holdings_by_agent(agent_id))
            db.save_agent_analysis_history(
                agent_id=agent_id,
                report_date=report_date,
                holdings_snapshot=snap,
                analysis_result=ar_payload,
                raw_response=content or '',
                thinking=thinking_text,
                stance=structured.get('stance', '') if structured else '',
                confidence=int(structured.get('confidence', 0)) if structured else 0,
                tokens_used=usage.total_tokens if usage else 0,
            )
            logger.info(f"[AgentAnalyze] 历史已写入 agent_id={agent_id} date={report_date}")

            # 自动把 recommendedStocks 写入持仓表
            rec_stocks = structured.get('recommendedStocks', []) if structured else []
            logger.info(f"[AgentAnalyze] agent_id={agent_id} 准备写入持仓 rec_stocks_count={len(rec_stocks)}")
            if rec_stocks:
                for s in rec_stocks:
                    logger.info(f"[AgentAnalyze] agent_id={agent_id} 持仓股票: code={s.get('code')} name={s.get('name')} price={s.get('price')} chg={s.get('changePct', s.get('chg_pct'))}")
                try:
                    saved = db.save_recommended_stocks_as_holdings(agent_id, rec_stocks)
                    logger.info(f"[AgentAnalyze] agent_id={agent_id} 写入 holdings 成功，共 {saved} 条")
                except Exception as save_err:
                    logger.error(f"[AgentAnalyze] agent_id={agent_id} 写入 holdings 失败: {save_err}", exc_info=True)
        except Exception as hist_err:
            logger.warning(f"[AgentAnalyze] agent_id={agent_id} 保存分析历史失败: {hist_err}", exc_info=True)

        return jsonify({
            "success": True,
            "agent_id": agent_id,
            "agent_name": agent_config.get('name', agent_id),
            "structured": structured,
            "analysis": content,
            "thinking": thinking_text,
            "tokens_used": usage.total_tokens if usage else 0,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/agents/analyze/<agent_id>/stream', methods=['POST'])
def analyze_with_agent_stream(agent_id):
    """
    流式版本：使用 Server-Sent Events 实时返回 LLM 输出。
    前端可逐块接收并显示，实现实时打印效果。
    """
    from flask import Response, stream_with_context

    def generate():
        try:
            from utils.llm import get_client, get_agent_registry
            from ai_service import fetch_market_news, fetch_junge_enhanced_news
            from junge_trader import format_holdings_for_prompt, format_scan_data_for_prompt
            from openai import OpenAI
            from datetime import datetime
            import json as _json

            logger.info(f"[Stream] agent_id={agent_id} 开始流式分析")

            registry = get_agent_registry()
            agent_config = registry.get(agent_id)
            if not agent_config:
                err = f'未知 Agent ID: {agent_id}'
                logger.error(f"[Stream] {err}")
                yield f"data: {_json.dumps({'type': 'error', 'error': err})}\n\n"
                return

            data = request.get_json() or {}
            from utils.llm.client import DASHSCOPE_API_KEY as _DEFAULT_KEY
            api_key = data.get('api_key') or os.environ.get('DASHSCOPE_API_KEY', '') or _DEFAULT_KEY
            DEEPSEEK_BASE_URL = "https://api.deepseek.com"
            model = data.get('model') or os.environ.get('DASHSCOPE_MODEL', 'deepseek-chat')
            if not api_key:
                err = '请提供 API Key'
                logger.error(f"[Stream] {err}")
                yield f"data: {_json.dumps({'type': 'error', 'error': err})}\n\n"
                return
            logger.info(f"[Stream] api_key 长度={len(api_key)}, model={model}")

            # 发送准备阶段信息
            yield f"data: {_json.dumps({'type': 'status', 'message': '正在准备数据...'})}\n\n"

            latest_scan = db.get_latest_scan()
            all_stocks = []
            if latest_scan:
                results_dict = latest_scan.get('results', {})
                for sector_name, sector_data in results_dict.items():
                    if isinstance(sector_data, dict):
                        for stock in sector_data.get('stocks', []):
                            if isinstance(stock, dict):
                                stock['sector'] = sector_name
                                all_stocks.append(stock)
                scan_data_text = format_scan_data_for_prompt(all_stocks) if all_stocks else ""
                scan_date = latest_scan.get('scan_time', '')[:10]
            else:
                scan_data_text = ""
                scan_date = ""

            if agent_id == 'jun':
                news_list = fetch_junge_enhanced_news(scan_date)
            else:
                news_list = fetch_market_news(scan_date)

            news_lines = []
            for idx, n in enumerate((news_list or [])[:8], 1):
                news_lines.append(
                    f"【新闻{idx}】「[{n.get('time','')}] {n.get('title','')}」（{n.get('source','')}）"
                )
            news_text = "\n".join(news_lines) if news_lines else "【暂无最新消息】"

            try:
                holdings = db.get_holdings_by_agent(agent_id)
                holdings_text = format_holdings_for_prompt(holdings)
            except Exception:
                holdings_text = "【暂无历史持仓数据】"

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

            yield f"data: {_json.dumps({'type': 'status', 'message': '正在调用 AI 分析...'})}\n\n"

            client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, timeout=300)
            extra_body = {
                "thinking": {"type": "enabled"},
                "enable_search": True,
            }
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


            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_prompt}
            ]

            # 处理工具调用循环
            MAX_TOOL_CALLS = 5
            content = ""
            reasoning_content = ""
            usage = None

            for _ in range(MAX_TOOL_CALLS):
                logger.info(f"[Stream] agent_id={agent_id} 调用 LLM (第{_+1}轮)")
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=agent_config.get('temperature', 0.3),
                        max_tokens=agent_config.get('max_tokens', 3000),
                        extra_body=extra_body,
                        tools=tools,
                        tool_choice="auto",
                        stream=True,  # 启用流式
                    )
                except Exception as llm_err:
                    logger.exception(f"[Stream] LLM 调用失败: {llm_err}")
                    yield f"data: {_json.dumps({'type': 'error', 'error': f'LLM 调用失败: {llm_err}'})}\n\n"
                    return

                chunk_content = ""
                chunk_reasoning = ""
                tool_calls_buffer = []

                for chunk in response:
                    # 发送推理内容（thinking）
                    if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[0].delta.reasoning_content:
                        rc = chunk.choices[0].delta.reasoning_content
                        chunk_reasoning += rc
                        yield f"data: {_json.dumps({'type': 'thinking', 'content': rc})}\n\n"

                    # 发送正文内容
                    if chunk.choices[0].delta.content:
                        cc = chunk.choices[0].delta.content
                        chunk_content += cc
                        yield f"data: {_json.dumps({'type': 'content', 'content': cc})}\n\n"

                    # 处理工具调用
                    if chunk.choices[0].delta.tool_calls:
                        for tc in chunk.choices[0].delta.tool_calls:
                            # 累积工具调用信息
                            if tc.function and tc.function.arguments:
                                tool_calls_buffer.append({
                                    'id': tc.id,
                                    'name': tc.function.name,
                                    'arguments': tc.function.arguments
                                })

                # 流结束后处理
                content += chunk_content
                reasoning_content += chunk_reasoning

                # 判断是否需要工具调用
                if tool_calls_buffer:
                    # 执行工具调用
                    for tc in tool_calls_buffer:
                        func_name = tc['name']
                        func_args = tc['arguments']
                        if func_name == 'web_search':
                            args = _json.loads(func_args)
                            query = args.get('query', '')
                            search_result = _do_web_search(query)
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc['id'],
                                "content": search_result or "未找到相关数据",
                            })
                        elif func_name == 'get_limit_up_stocks':
                            stocks = _get_limit_up_stocks()
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc['id'],
                                "content": stocks,
                            })
                        else:
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc['id'],
                                "content": f"未知工具: {func_name}",
                            })
                    # 继续下一轮
                    continue
                else:
                    # 没有工具调用，结束
                    usage = response.usage if hasattr(response, 'usage') else None
                    break

            thinking_text = reasoning_content

            yield f"data: {_json.dumps({'type': 'status', 'message': '正在解析结果...'})}\n\n"

            structured = registry.extract_json(content)

            if structured:
                structured = registry.sanitize(
                    structured,
                    all_stocks,
                    default_advise_type=agent_config.get('adviseType', '波段'),
                )
                structured = _enrich_stocks_with_scan_data(structured, all_stocks)

            yield f"data: {_json.dumps({'type': 'status', 'message': '正在保存历史记录...'})}\n\n"

            # 保存历史
            try:
                report_date = datetime.now().strftime('%Y-%m-%d')
                rec_stocks = structured.get('recommendedStocks', []) if structured else []
                ar_payload = {
                    'structured': structured,
                    'raw_text': content,
                    'thinking': thinking_text,
                    'marketCommentary': structured.get('marketCommentary', '') if structured else '',
                    'positionAdvice': structured.get('positionAdvice', '') if structured else '',
                    'riskWarning': structured.get('riskWarning', '') if structured else '',
                    'stance': structured.get('stance', '') if structured else '',
                    'confidence': structured.get('confidence', 0) if structured else 0,
                    'recommendedStocks': rec_stocks,
                }

                if rec_stocks:
                    snap = db.snapshot_rows_from_recommended_stocks(rec_stocks)
                else:
                    snap = db.snapshot_rows_from_db_holdings(db.get_holdings_by_agent(agent_id))
                db.save_agent_analysis_history(
                    agent_id=agent_id,
                    report_date=report_date,
                    holdings_snapshot=snap,
                    analysis_result=ar_payload,
                    raw_response=content or '',
                    thinking=thinking_text,
                    stance=structured.get('stance', '') if structured else '',
                    confidence=int(structured.get('confidence', 0)) if structured else 0,
                    tokens_used=usage.total_tokens if usage else 0,
                )

                rec_stocks = structured.get('recommendedStocks', []) if structured else []
                if rec_stocks:
                    for s in rec_stocks:
                        pass  # 日志可忽略
                    try:
                        saved = db.save_recommended_stocks_as_holdings(agent_id, rec_stocks)
                    except Exception as save_err:
                        logger.error(f"[AgentAnalyzeStream] agent_id={agent_id} 写入 holdings 失败: {save_err}")
            except Exception as hist_err:
                logger.warning(f"[AgentAnalyzeStream] agent_id={agent_id} 保存分析历史失败: {hist_err}")

            # 发送最终结果
            yield f"data: {_json.dumps({'type': 'done', 'success': True, 'agent_id': agent_id, 'agent_name': agent_config.get('name', agent_id), 'structured': structured, 'analysis': content, 'thinking': thinking_text, 'tokens_used': usage.total_tokens if usage else 0})}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {_json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route('/api/agents/batch', methods=['POST'])
def batch_analyze_agents():
    """
    批量运行全部智能体（并行或层次化）
    POST body: {
        "api_key": "...",
        "mode": "parallel" | "hierarchical"  # 默认 parallel
    }

    返回：
      - consensus: 全局共识数据（供 AISummaryDetail 环形图）
      - agentResults[]: 每个 Agent 的结构化输出（供主力头寸卡片）
      - consensusOpportunities[]: TOP 3 共识股票（供核心投资机会区块）
      - master（仅 hierarchical 模式）: 主控 Agent 分析结果
      - synthesis（仅 hierarchical 模式）: 综合建议
    """
    try:
        data = request.get_json() or {}
        mode = data.get('mode', 'parallel')

        if mode == 'hierarchical':
            return _hierarchical_batch_analyze(data)
        else:
            return _parallel_batch_analyze(data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


def _hierarchical_batch_analyze(data: dict):
    """
    层次化批量分析：
    1. 主控 Agent 分析市场核心意图
    2. 根据优先级并行调用子 Agent
    3. 聚合输出，生成综合建议
    """
    from utils.llm import get_client, get_agent_registry, AgentOrchestrator
    from ai_service import fetch_market_news
    from junge_trader import format_holdings_for_prompt, format_scan_data_for_prompt

    api_key = data.get('api_key') or os.environ.get('DASHSCOPE_API_KEY', '')
    model = data.get('model') or os.environ.get('DASHSCOPE_MODEL', 'deepseek-chat')
    if not api_key:
        return jsonify({"success": False, "error": "请提供 API Key"})

    DEEPSEEK_BASE_URL = "https://api.deepseek.com"

    # 获取扫描数据
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

    scan_data_text = format_scan_data_for_prompt(all_stocks)
    scan_date = latest_scan.get('scan_time', '')[:10]
    news_list = fetch_market_news(scan_date)
    news_text = _format_news_for_agent(news_list)
    current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')

    # 获取持仓数据
    try:
        holdings = db.get_all_holdings()
        holdings_text = format_holdings_for_prompt(holdings)
    except Exception:
        holdings_text = "【暂无历史持仓数据】"

    # 创建 OpenAI 客户端（兼容现有代码）
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, timeout=300)

    # 创建包装器以兼容 orchestrator
    class ClientWrapper:
        def __init__(self, client):
            self._client = client

        def call_messages(self, messages, options=None):
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

            extra_body = {
                "thinking": {"type": "enabled"},
                "enable_search": True,
            }

            for _ in range(5):
                response = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=options.temperature if options else 0.2,
                    max_tokens=options.max_tokens if options else 2000,
                    extra_body=extra_body,
                    tools=tools,
                    tool_choice="auto",
                )
                choice = response.choices[0]
                msg = choice.message

                if msg.content and msg.content.strip():
                    return type('Response', (), {
                        'success': True,
                        'content': msg.content,
                        'reasoning_content': getattr(msg, 'reasoning_content', '') or '',
                        'tokens_used': response.usage.total_tokens if response.usage else 0,
                        'error': None
                    })()

                tool_calls = msg.tool_calls or []
                if tool_calls:
                    for tc in tool_calls:
                        func_name = tc.function.name
                        func_args = tc.function.arguments
                        if func_name == 'web_search':
                            import json as _json
                            args = _json.loads(func_args)
                            query = args.get('query', '')
                            search_result = _do_web_search(query)
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": search_result or "未找到相关数据",
                            })
                        elif func_name == 'get_limit_up_stocks':
                            stocks = _get_limit_up_stocks()
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": stocks,
                            })
                    continue
                else:
                    return type('Response', (), {
                        'success': True,
                        'content': msg.content or '',
                        'reasoning_content': getattr(msg, 'reasoning_content', '') or '',
                        'tokens_used': response.usage.total_tokens if response.usage else 0,
                        'error': None
                    })()

            return type('Response', (), {
                'success': False,
                'content': '',
                'reasoning_content': '',
                'tokens_used': 0,
                'error': 'Maximum tool calls exceeded'
            })()

    wrapper = ClientWrapper(client)
    registry = get_agent_registry()
    orchestrator = AgentOrchestrator(wrapper, registry)

    from utils.llm import CallOptions
    options = CallOptions(temperature=0.2, max_tokens=2000)

    # 执行层次化分析
    result = orchestrator.analyze_hierarchical(
        scan_data=scan_data_text,
        news_data=news_text,
        holdings_data=holdings_text,
        current_time=current_time,
        scan_date=scan_date,
        options=options,
    )

    # 转换结果为前端兼容格式
    agent_results = []
    for agent_id, res in result.agent_results.items():
        structured = res.get('structured') or {}
        agent_config = registry.get(agent_id)

        # 清洗和丰富数据
        if structured:
            structured = registry.sanitize(
                structured,
                all_stocks,
                default_advise_type=agent_config.get('adviseType', '波段') if agent_config else '波段',
            )
            structured = _enrich_stocks_with_scan_data(structured, all_stocks)

        agent_results.append({
            "agent_id": agent_id,
            "agent_name": agent_config.get('name', agent_id) if agent_config else agent_id,
            "success": res.get('success', False),
            "structured": structured,
            "analysis": res.get('raw_response', ''),
            "thinking": res.get('thinking', ''),
            "tokens_used": res.get('tokens_used', 0),
        })

    # 持久化分析历史
    report_date = datetime.now().strftime('%Y-%m-%d')
    for r in agent_results:
        if r.get('success'):
            _save_agent_analysis_result(r, report_date, all_stocks)

    return jsonify({
        "success": True,
        "scan_time": scan_date,
        "mode": "hierarchical",
        "master": {
            "marketCoreIntent": result.master.market_core_intent if result.master else "",
            "marketPhase": result.master.market_phase if result.master else "",
            "riskAppetite": result.master.risk_appetite if result.master else "",
            "agentPriority": result.master.agent_priority if result.master else [],
            "keyTheme": result.master.key_theme if result.master else "",
            "riskFactors": result.master.risk_factors if result.master else [],
            "coordinationNotes": result.master.coordination_notes if result.master else "",
        } if result.master else None,
        "consensus": result.consensus,
        "agentResults": agent_results,
        "consensusOpportunities": result.top_opportunities,
        "synthesis": result.synthesis,
        "lastUpdated": current_time,
    })


def _parallel_batch_analyze(data: dict):
    """
    并行批量分析（原有逻辑）
    """
    import concurrent.futures
    from agent_prompts import AGENTS, build_messages, extract_json_from_response, compute_consensus, sanitize_parsed_agent_output
    from ai_service import fetch_market_news
    from junge_trader import format_holdings_for_prompt

    api_key = data.get('api_key') or os.environ.get('DASHSCOPE_API_KEY', '')
    model = data.get('model') or os.environ.get('DASHSCOPE_MODEL', 'deepseek-chat')
    if not api_key:
        return jsonify({"success": False, "error": "请提供 API Key"})

    DEEPSEEK_BASE_URL = "https://api.deepseek.com"

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

    from junge_trader import format_scan_data_for_prompt
    scan_data_text = format_scan_data_for_prompt(all_stocks)
    scan_date = latest_scan.get('scan_time', '')[:10]
    news_list = fetch_market_news(scan_date)
    news_text = _format_news_for_agent(news_list)
    current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')

    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, timeout=300)
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

    def call_one(agent):
        try:
            try:
                holdings_text = format_holdings_for_prompt(db.get_holdings_by_agent(agent['id']))
            except Exception:
                holdings_text = "【暂无历史持仓数据】"
            messages = build_messages(agent, scan_data_text, news_text, holdings_text, current_time, scan_date)
            system_content = ''
            user_content = ''
            for msg in messages:
                if msg.get('role') == 'system':
                    system_content = msg.get('content', '')
                elif msg.get('role') == 'user':
                    user_content = msg.get('content', '')

            msgs = [{"role": "system", "content": system_content}, {"role": "user", "content": user_content}]

            # 处理工具调用循环
            MAX_TOOL_CALLS = 5
            for _ in range(MAX_TOOL_CALLS):
                response = client.chat.completions.create(
                    model=model,
                    messages=msgs,
                    temperature=agent['temperature'],
                    max_tokens=agent['max_tokens'],
                    extra_body={
                        "thinking": {"type": "enabled"},
                        "enable_search": True,
                    },
                    tools=tools,
                    tool_choice="auto",
                )
                choice = response.choices[0]
                msg = choice.message

                # 有内容
                if msg.content and msg.content.strip():
                    content = msg.content
                    thinking_text = msg.reasoning_content or ''
                    usage = response.usage
                    break

                # 有工具调用
                tool_calls = msg.tool_calls or []
                if tool_calls:
                    for tc in tool_calls:
                        func_name = tc.function.name
                        if func_name == 'web_search':
                            import json as _json
                            args = _json.loads(tc.function.arguments)
                            query = args.get('query', '')
                            search_result = _do_web_search(query)
                            msgs.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": search_result or "未找到相关数据",
                            })
                        elif func_name == 'get_limit_up_stocks':
                            stocks = _get_limit_up_stocks()
                            msgs.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": stocks,
                            })
                        else:
                            msgs.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": f"未知工具: {func_name}",
                            })
                    continue
                else:
                    content = msg.content or ''
                    thinking_text = msg.reasoning_content or ''
                    usage = response.usage
                    break
            else:
                content = ''
                thinking_text = ''
                usage = None
            logger.info("[Batch] agent_id=%s model=%s response_len=%d usage=%s thinking_len=%d",
                        agent['id'], model, len(content) if content else 0,
                        usage.total_tokens if usage else 0, len(thinking_text))
            structured = extract_json_from_response(content) if content else None
            if structured:
                logger.info("[Batch] agent_id=%s parsed stance=%s confidence=%s recommendedStocks_count=%d",
                            agent['id'], structured.get('stance'), structured.get('confidence'),
                            len(structured.get('recommendedStocks') or []))
                structured = sanitize_parsed_agent_output(
                    structured, all_stocks, default_advise_type=agent['adviseType'])
                structured = _enrich_stocks_with_scan_data(structured, all_stocks)
                logger.info("[Batch] agent_id=%s after_sanitize recommendedStocks_count=%d",
                            agent['id'], len(structured.get('recommendedStocks') or []))
            else:
                logger.warning("[Batch] agent_id=%s JSON 解析失败，raw content 前200字: %.200s",
                              agent['id'], content[:200] if content else '')
            return {
                "agent_id": agent['id'],
                "agent_name": agent['name'],
                "success": True,
                "structured": structured,
                "analysis": content or '',
                "thinking": thinking_text,
                "tokens_used": usage.total_tokens if usage else 0,
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

    # 聚合 TOP 3
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

    # 持久化分析历史
    report_date = datetime.now().strftime('%Y-%m-%d')
    for r in agent_list:
        if r.get('success'):
            _save_agent_analysis_result(r, report_date, all_stocks)

    return jsonify({
        "success": True,
        "scan_time": scan_date,
        "mode": "parallel",
        "consensus": consensus,
        "agentResults": agent_list,
        "consensusOpportunities": top3,
        "lastUpdated": current_time,
    })


def _save_agent_analysis_result(r: dict, report_date: str, all_stocks: list):
    """保存 Agent 分析结果到数据库"""
    try:
        s = r.get('structured') or {}
        ar_payload = {
            'structured': s,
            'raw_text': r.get('analysis'),
            'marketCommentary': s.get('marketCommentary', ''),
            'positionAdvice': s.get('positionAdvice', ''),
            'riskWarning': s.get('riskWarning', ''),
            'stance': s.get('stance', ''),
            'confidence': s.get('confidence', 0),
            'recommendedStocks': s.get('recommendedStocks', []),
        }
        snap = db.build_analysis_holdings_snapshot(
            db.get_holdings_by_agent(r.get('agent_id', '')), ar_payload
        )
        db.save_agent_analysis_history(
            agent_id=r.get('agent_id', ''),
            report_date=report_date,
            holdings_snapshot=snap,
            analysis_result=ar_payload,
            raw_response=r.get('analysis', ''),
            stance=s.get('stance', '') if s else '',
            confidence=int(s.get('confidence', 0)) if s else 0,
            tokens_used=r.get('tokens_used', 0),
        )
        rec_stocks = s.get('recommendedStocks', []) or []
        if rec_stocks:
            try:
                saved = db.save_recommended_stocks_as_holdings(r.get('agent_id', ''), rec_stocks)
                logger.info(f"[BatchAnalyze] agent_id={r.get('agent_id')} recommendedStocks 已写入 holdings，共 {saved} 条")
            except Exception as save_err:
                logger.warning(f"[BatchAnalyze] 保存推荐股到持仓失败 {r.get('agent_id')}: {save_err}")
    except Exception as hist_err:
        logger.warning(f"[BatchAnalyze] 保存 Agent 历史失败 {r.get('agent_id')}: {hist_err}")


def _enrich_stocks_with_scan_data(structured: dict, all_stocks: list) -> dict:
    """将扫描数据 + 实时行情中的现价和涨跌幅回填到 recommendedStocks"""
    if not structured:
        return structured

    recs = structured.get('recommendedStocks') or []
    if not recs:
        return structured

    # 建立 code → 扫描数据的映射
    scan_map = {}
    for s in all_stocks or []:
        code = str(s.get('code', '')).strip()
        if code:
            scan_map[code] = s

    # 收集需要实时查询的股票代码（扫描数据里没有的）
    codes_to_fetch = []
    for rec in recs:
        code = str(rec.get('code', '')).strip()
        if code and code not in scan_map:
            codes_to_fetch.append(code)

    # 用 akshare 实时查询涨跌幅
    realtime_data = {}
    if codes_to_fetch:
        try:
            realtime_data = _fetch_realtime_quotes(codes_to_fetch)
        except Exception as e:
            logger.warning(f"[Enrich] 实时行情查询失败: {e}")

    # 回填每只推荐股票
    for rec in recs:
        code = str(rec.get('code', '')).strip()
        scan = scan_map.get(code, {})

        if scan:
            # 有扫描数据：用扫描表数据
            if not rec.get('price'):
                rec['price'] = scan.get('current_price') or scan.get('price') or 0
            scan_chg = scan.get('change_pct') or scan.get('changePct') or 0
            if not rec.get('chg_pct'):
                rec['chg_pct'] = float(scan_chg)
            if not rec.get('changePct'):
                rec['changePct'] = float(scan_chg)
        elif code in realtime_data:
            # 无扫描数据但有实时行情：用实时数据
            rt = realtime_data[code]
            if not rec.get('price'):
                rec['price'] = rt.get('current_price', 0)
            if not rec.get('chg_pct'):
                rec['chg_pct'] = rt.get('change_pct', 0)
            if not rec.get('changePct'):
                rec['changePct'] = rt.get('change_pct', 0)
        else:
            # 都没有：归一化
            _normalize_stock_chg(rec)

    return structured


def _fetch_realtime_quotes(codes: list) -> dict:
    """
    用 akshare 实时查询股票现价和涨跌幅（并行，最多5秒超时）。
    返回 {code: {current_price, change_pct}}
    """
    if not codes:
        return {}

    from concurrent.futures import ThreadPoolExecutor, as_completed
    import akshare as ak
    import datetime

    result = {}

    def fetch_one(code: str) -> tuple:
        try:
            today = datetime.date.today()
            start = (today - datetime.timedelta(days=5)).strftime('%Y%m%d')
            end = today.strftime('%Y%m%d')
            df = ak.stock_zh_a_hist(
                symbol=code, period="daily",
                start_date=start, end_date=end, adjust=""
            )
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                return code, float(latest['收盘']), float(latest['涨跌幅'])
        except Exception:
            pass
        return code, 0, 0

    try:
        with ThreadPoolExecutor(max_workers=min(len(codes), 10)) as pool:
            futures = {pool.submit(fetch_one, c): c for c in codes}
            for f in as_completed(futures, timeout=5):
                try:
                    code, price, chg = f.result()
                    if code:
                        result[code] = {'current_price': price, 'change_pct': chg}
                except Exception:
                    pass
    except Exception:
        pass

    return result


def _normalize_stock_chg(s: dict):
    """统一将涨跌幅转为浮点 chg_pct（支持字符串/数字/None）"""
    raw = s.get('chg_pct') or s.get('changePct') or s.get('change_pct') or 0
    try:
        s['chg_pct'] = float(raw)
    except (TypeError, ValueError):
        s['chg_pct'] = 0
    # 确保 changePct 也统一
    if s.get('chg_pct') and not s.get('changePct'):
        s['changePct'] = s['chg_pct']


def _fetch_realtime_quotes_safe(codes: list) -> dict:
    """
    用 akshare 批量实时查询股票现价和涨跌幅（安全版，最多8秒超时）。
    返回 {code: {current_price, change_pct}}
    """
    if not codes:
        return {}

    from concurrent.futures import ThreadPoolExecutor, as_completed
    import akshare as ak
    import datetime as dt

    result = {}

    def fetch_one(code: str) -> tuple:
        try:
            today = dt.date.today()
            start = (today - dt.timedelta(days=5)).strftime('%Y%m%d')
            end = today.strftime('%Y%m%d')
            df = ak.stock_zh_a_hist(
                symbol=code, period="daily",
                start_date=start, end_date=end, adjust=""
            )
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                return code, float(latest['收盘']), float(latest['涨跌幅'])
        except Exception:
            pass
        return code, 0, 0

    try:
        with ThreadPoolExecutor(max_workers=min(len(codes), 10)) as pool:
            futures = {pool.submit(fetch_one, c): c for c in codes}
            for f in as_completed(futures, timeout=8):
                try:
                    code, price, chg = f.result()
                    if code and price > 0:
                        result[code] = {'current_price': price, 'change_pct': chg}
                except Exception:
                    pass
    except Exception:
        pass
    return result


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
                f"【股票{i}】{name}（{code}）[{s.get('sector', '')}] — "
                f"{s.get('total_score', 0)}分（{s.get('grade', 'N/A')}级）"
            )
            lines.append(
                f"  现价={price:.2f} | 涨跌幅={change_pct:+.2f}% | 成交额={s.get('volume', s.get('amount', 0))}万 | "
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
PUBLIC_DIR = os.path.join(os.path.dirname(__file__), 'public')


@app.route('/charting_library/<path:filename>')
def serve_charting_library(filename):
    """TradingView Charting Library 静态资源（含 charting_library.standalone.js 在子目录 charting_library/ 下）。"""
    if '..' in filename or filename.startswith(('/', '\\')):
        abort(404)

    # 1. 优先在根目录查找（mobile_white.html、bundles 等）
    full = os.path.normpath(os.path.join(CHARTING_LIB_DIR, filename))
    if full.startswith(os.path.normpath(CHARTING_LIB_DIR + os.sep)) and os.path.isfile(full):
        return send_from_directory(CHARTING_LIB_DIR, filename)

    # 2. 再尝试 charting_library/ 子目录（TV 主库文件：charting_library.standalone.js 等）
    full_sub = os.path.normpath(os.path.join(CHARTING_LIB_DIR, 'charting_library', filename))
    if full_sub.startswith(os.path.normpath(os.path.join(CHARTING_LIB_DIR, 'charting_library') + os.sep)) and os.path.isfile(full_sub):
        return send_from_directory(os.path.join(CHARTING_LIB_DIR, 'charting_library'), filename)

    abort(404)


# ── 前端 SPA（路由 /frontend/*） ───────────────────────────────────────────

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
    # 如果文件存在则直接返回，否则返回 index.html（SPA fallback）
    if os.path.isfile(os.path.join(DIST_DIR, filename)):
        return send_from_directory(DIST_DIR, filename)
    return send_from_directory(DIST_DIR, 'index.html')


@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """静态资源路由（从前端构建产物）"""
    assets_dir = os.path.join(DIST_DIR, 'assets')
    if not os.path.isdir(assets_dir):
        abort(404)
    return send_from_directory(assets_dir, filename)


@app.route('/<path:filename>')
def serve_public(filename):
    """public目录静态文件（如 favicon.svg），找不到则 SPA fallback"""
    if not '..' in filename and not filename.startswith(('/', '\\')):
        # 先查 public 目录
        if os.path.isdir(PUBLIC_DIR):
            full_path = os.path.normpath(os.path.join(PUBLIC_DIR, filename))
            if full_path.startswith(os.path.normpath(PUBLIC_DIR + os.sep)) and os.path.isfile(full_path):
                return send_from_directory(PUBLIC_DIR, filename)
        # 再查 dist 目录（静态资源）
        if os.path.isdir(DIST_DIR):
            dist_path = os.path.normpath(os.path.join(DIST_DIR, filename))
            if dist_path.startswith(os.path.normpath(DIST_DIR + os.sep)) and os.path.isfile(dist_path):
                return send_from_directory(DIST_DIR, filename)
    # SPA fallback：所有前端路由返回 index.html
    if os.path.isdir(DIST_DIR):
        return send_from_directory(DIST_DIR, 'index.html')
    abort(404)

# ─────────────────────────────────────────────────────────────────────────────
# 持仓管理 API
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/holdings', methods=['GET'])
def api_get_holdings():
    """获取持仓（支持按 agent_id 过滤）"""
    try:
        agent_id = request.args.get('agent_id', '').strip()
        holdings = db.get_holdings_by_agent(agent_id) if agent_id else db.get_all_holdings()
        # 字段映射：数据库列名 → Vue 期望的列名
        for h in holdings:
            h['stock_name'] = h.get('stock_name', h.get('name', ''))
            h['stock_code'] = h.get('stock_code', h.get('code', ''))
            h['current_price'] = h.get('current_price', h.get('price', 0))
            # Vue 使用 changePct / change_pct，回填数据库的 profit_loss_pct
            h.setdefault('changePct', h.get('profit_loss_pct', 0))
            h.setdefault('change_pct', h.get('profit_loss_amount', 0))
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


@app.route('/api/agents/<agent_id>/performance', methods=['GET'])
def api_get_agent_performance(agent_id):
    """计算 Agent 胜率与收益率（基于历史分析持仓快照）"""
    try:
        records = db.get_agent_analysis_history(agent_id, limit=30)
        if not records:
            return jsonify({'success': True, 'data': {'winRate': 0, 'returnPct': 0, 'analysisCount': 0}})

        all_positions = []
        for r in records:
            snap = r.get('holdings_snapshot') or []
            all_positions.extend(snap)

        if not all_positions:
            return jsonify({'success': True, 'data': {'winRate': 0, 'returnPct': 0, 'analysisCount': len(records)}})

        profits = [float(p.get('profit_loss_pct') or p.get('changePct') or 0) for p in all_positions]
        win_count = sum(1 for p in profits if p > 0)
        win_rate = round(win_count / len(profits) * 100, 1) if profits else 0
        avg_return = round(sum(profits) / len(profits), 2) if profits else 0

        return jsonify({'success': True, 'data': {
            'winRate': win_rate,
            'returnPct': avg_return,
            'analysisCount': len(records),
        }})
    except Exception as e:
        logging.error(f"获取 Agent 绩效失败 [{agent_id}]: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/agents/<agent_id>/analysis/today', methods=['GET'])
def api_get_today_agent_analysis(agent_id):
    """获取某 Agent 今日分析记录，无则返回 None（不报错）"""
    try:
        record = db.get_today_agent_analysis(agent_id)
        if record is None:
            return jsonify({'success': True, 'data': None})
        if record.get('holdings_snapshot'):
            record['holdings_snapshot'] = [
                {
                    'name': h.get('stock_name', h.get('name', '')),
                    'code': h.get('stock_code', h.get('code', '')),
                    'price': h.get('current_price', h.get('price', 0)),
                    'changePct': h.get('profit_loss_pct', h.get('changePct', 0)),
                    'sector': h.get('sector', ''),
                }
                for h in record['holdings_snapshot']
            ]
        return jsonify({'success': True, 'data': record})
    except Exception as e:
        import traceback
        logging.error(f"获取今日分析失败 [{agent_id}]: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': f'服务器内部错误: {str(e)}'}), 500


@app.route('/api/agents/<agent_id>/analysis/latest', methods=['GET'])
def api_get_latest_agent_analysis(agent_id):
    """获取某 Agent 最新一次分析记录（含持仓快照和分析结果）"""
    try:
        record = db.get_latest_agent_analysis(agent_id)
        if record is None:
            return jsonify({'success': False, 'error': '未找到该 Agent 的分析记录'}), 404
        # holdings_snapshot 字段映射：数据库 → Vue 期望
        if record.get('holdings_snapshot'):
            record['holdings_snapshot'] = [
                {
                    'name': h.get('stock_name', h.get('name', '')),
                    'code': h.get('stock_code', h.get('code', '')),
                    'price': h.get('current_price', h.get('price', 0)),
                    'changePct': h.get('profit_loss_pct', h.get('changePct', 0)),
                    'sector': h.get('sector', ''),
                }
                for h in record['holdings_snapshot']
            ]
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
        for record in records:
            # holdings_snapshot 字段映射：数据库 → Vue 期望
            if record.get('holdings_snapshot'):
                record['holdings_snapshot'] = [
                    {
                        'name': h.get('stock_name', h.get('name', '')),
                        'code': h.get('stock_code', h.get('code', '')),
                        'price': h.get('current_price', h.get('price', 0)),
                        'changePct': h.get('profit_loss_pct', h.get('changePct', 0)),
                        'sector': h.get('sector', ''),
                    }
                    for h in record['holdings_snapshot']
                ]
        return jsonify({'success': True, 'data': records})
    except Exception as e:
        import traceback
        logging.error(f"获取 Agent 分析历史失败 [{agent_id}]: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': f'服务器内部错误: {str(e)}'}), 500


@app.route('/api/agents/<agent_id>/holdings', methods=['GET'])
def api_get_agent_holdings(agent_id):
    """
    获取某 Agent 的持仓（独立接口，直接从最新分析快照返回，数据最准确）。
    """
    try:
        import akshare as ak
        import datetime as dt

        # 1. 取最新分析快照
        latest = db.get_latest_agent_analysis(agent_id)
        snap = latest.get('holdings_snapshot') if latest else None
        ar = (latest or {}).get('analysis_result') or {}

        # 2. 收集推荐股代码，用于实时行情查询
        rec_stocks = ar.get('recommendedStocks') or []
        if not rec_stocks and isinstance(ar.get('structured'), dict):
            rec_stocks = ar['structured'].get('recommendedStocks') or []

        codes = [s.get('code', '') for s in (snap or []) if s.get('code')]
        # 也加入 analysis_result 里的代码（可能有扫描数据回填的）
        extra_codes = [s.get('code', '') for s in rec_stocks if s.get('code')]
        all_codes = list({c: True for c in codes + extra_codes if c})

        # 3. 用 akshare 批量查实时行情（并行，最多5秒超时）
        rt_map = {}
        if all_codes:
            try:
                rt_map = _fetch_realtime_quotes_safe(all_codes)
            except Exception as e:
                logger.warning(f"[AgentHoldings] 实时行情查询失败 [{agent_id}]: {e}")

        # 4. 构建持仓列表
        positions = []
        seen = {}
        for s in (snap or []):
            code = s.get('code') or s.get('stock_code') or ''
            if not code or code in seen:
                continue
            seen[code] = True
            r = rt_map.get(code, {})
            chg = r.get('change_pct')
            if chg is None:
                chg = s.get('changePct') or s.get('profit_loss_pct') or 0
            positions.append({
                'name':       s.get('name') or s.get('stock_name') or '',
                'code':       code,
                'price':      r.get('current_price') or s.get('price') or s.get('current_price') or 0,
                'changePct':  float(chg) if chg is not None else 0,
                'sector':     s.get('sector') or '',
            })

        # 5. 总资产（估算：持股市值 × 评分系数）
        total_value = sum(p.get('price', 0) * 10000 for p in positions)  # 简单估算
        if not positions:
            total_value = 0
        total_pnl = sum(
            (float(p.get('changePct') or 0) / 100) * (p.get('price', 0) * 10000)
            for p in positions
        )

        return jsonify({
            'success': True,
            'data': {
                'agent_id':           agent_id,
                'holdings':           positions,
                'totalPositionCount': len(positions),
                'totalPositionValue': round(total_value, 2),
                'totalProfitLoss':     round(total_pnl, 2),
                # AI 持仓总览（从 analysis_result 提取）
                'report_date':         latest.get('report_date') if latest else None,
                'analysis': {
                    'stance':     ar.get('stance') or (ar.get('structured') or {}).get('stance', ''),
                    'confidence':  ar.get('confidence') or (ar.get('structured') or {}).get('confidence', 0),
                    'marketCommentary':  ar.get('marketCommentary') or (ar.get('structured') or {}).get('marketCommentary', ''),
                    'positionAdvice':    ar.get('positionAdvice') or (ar.get('structured') or {}).get('positionAdvice', ''),
                    'riskWarning':      ar.get('riskWarning') or (ar.get('structured') or {}).get('riskWarning', ''),
                    'recommendedStocks': rec_stocks,
                },
                'hasRealData': bool(snap),
            }
        })
    except Exception as e:
        import traceback
        logger.error(f"[AgentHoldings] 获取持仓失败 [{agent_id}]: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _get_limit_up_stocks() -> str:
    """
    获取东方财富实时涨停板数据
    """
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
        logger.warning("[LimitUp] 获取涨停数据失败: %s", e)
    
    return "暂时无法获取涨停板数据"


def _do_web_search(query: str) -> str:
    """
    使用百度搜索获取实时信息
    """
    if not query or not query.strip():
        return "查询为空，请提供有效的搜索关键词。"

    logger.info("[WebSearch] query=%s", query)

    try:
        import requests
        import re
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
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
    except Exception as e:
        logger.warning("[WebSearch] 百度搜索失败: %s", e)

    # 降级：使用 DuckDuckGo
    try:
        import requests
        params = {
            "q": query,
            "kl": "zh-cn",
            "format": "json",
            "no_redirect": "1",
            "no_html": "1",
        }
        resp = requests.get(
            "https://duckduckgo.com/ac/",
            params=params,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        if resp.status_code == 200:
            suggestions = resp.json()
            if isinstance(suggestions, list) and suggestions:
                lines = []
                for i, s in enumerate(suggestions[:5], 1):
                    text = s.get("phrase") or s.get("text") or str(s)
                    lines.append(f"{i}. {text}")
                return "\n".join(lines) if lines else "未找到相关搜索建议。"
    except:
        pass

    return f"搜索「{query}」暂时无法获取结果。请根据您已有的市场知识进行判断。"


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5002, threaded=True)
