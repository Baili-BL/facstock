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
    app.run(debug=False, host='0.0.0.0', port=5001)
