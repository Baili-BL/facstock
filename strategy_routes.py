#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略中心路由模块
"""

import os
from flask import Blueprint, jsonify, request, current_app
from typing import Optional
import database as db
import json
import math
import requests
import threading
import time
import random
from datetime import datetime, timedelta
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
import pandas as _pd
from cache import get, set as _cache_set, invalidate
import logging
from utils.feishu_notifier import FeishuNotifier, send_feishu_scan_alert, send_feishu_test

logger = logging.getLogger(__name__)
strategy_bp = Blueprint('strategy', __name__)


def _strip_json_from_analysis(content: str) -> str:
    """
    从模型原始输出中移除 JSON 代码块，只保留 Markdown 总结文字。
    模型输出格式：```json\n{...}\n``` + Markdown 总结
    """
    if not content:
        return ''
    import re
    # 去掉 ```json ... ``` 块
    result = re.sub(r'```json\s*\n?[\s\S]*?\n?```', '', content)
    # 去掉 ```json ... ``` 单行变体
    result = re.sub(r'```json\s*\n?[\s\S]*?```', '', result)
    result = result.strip()
    # 如果去掉 JSON 后只剩空内容，返回原始内容
    return result if result else content


# 自定义因子 Prompt 工程 — 与前端 factor_template 对齐
FACTOR_TEMPLATE_VERSION = '2.4.1'
FACTOR_CODE_TEMPLATE = """\
class CustomFactor(BaseAlphaFactor):
    \"\"\"
    自定义量化 alpha 因子生成的基类模板。
    \"\"\"
    def __init__(self, universe, params):
        super().__init__(universe)
        self.params = params

    def compute_factor(self, data):
        # 在此处插入您的逻辑
        # DeepSeek 将在下方提供具体实现

        close_prices = data.get('close')
        volume = data.get('volume')

        # 开始逻辑注入

        # 结束逻辑注入
        return factor_values
"""
FACTOR_MARKER_START = '# 开始逻辑注入'
FACTOR_MARKER_END = '# 结束逻辑注入'


def _merge_factor_injected_code(injected_raw: str) -> str:
    """将模型返回的注入段合并进因子模板（8 空格缩进）。"""
    from textwrap import dedent

    body = dedent(injected_raw or '').strip('\n')
    prefix = '        '
    if not body:
        return FACTOR_CODE_TEMPLATE
    lines = body.splitlines()
    indented = '\n'.join(prefix + line for line in lines)
    needle = f"        {FACTOR_MARKER_START}\n\n        {FACTOR_MARKER_END}"
    replacement = f"        {FACTOR_MARKER_START}\n{indented}\n\n        {FACTOR_MARKER_END}"
    if needle not in FACTOR_CODE_TEMPLATE:
        return FACTOR_CODE_TEMPLATE
    return FACTOR_CODE_TEMPLATE.replace(needle, replacement, 1)


def _safe_json_dumps(obj):
    """JSON 序列化，兼容 NaN/Infinity（TradingView 指标常见）。"""
    return json.dumps(obj, ensure_ascii=False, default=lambda v: (
        None if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else v
    ))


def _eastmoney_mkt_cap_yuan(item: dict) -> Optional[float]:
    """东财 ulist 条目：总市值优先 f20，其次 f62（单位：元）。"""
    if not item:
        return None
    for k in ('f20', 'f62'):
        v = item.get(k)
        if v is None or v == '' or v == '-':
            continue
        try:
            x = float(v)
            if x > 0:
                return x
        except (TypeError, ValueError):
            continue
    return None

# 全局变量存储当前扫描状态
last_api_request_time = 0.0
API_REQUEST_INTERVAL = 1.0
scan_lock = threading.Lock()
scan_status = {
    'is_scanning': False,
    'scan_id': None,
    'progress': 0,
    'current_sector': '',
    'error': None,
    'cancelled': False
}


def analyze_single_stock(strategy, stock_info, precache_kline=True):
    """分析单只股票"""
    from bollinger_squeeze_strategy import BollingerSqueezeStrategy
    import time as t
    
    t.sleep(random.uniform(0.05, 0.15))
    
    try:
        code = stock_info['code']
        name = stock_info['name']
        result = strategy.analyze_stock(code, name, return_df=precache_kline)
        
        if result:
            df = None
            if isinstance(result, tuple):
                result, df = result
            
            result['sector_name'] = stock_info.get('sector_name', '')
            result['sector_change'] = stock_info.get('sector_change', 0)
            result['is_leader'] = stock_info.get('is_leader', False)
            result['leader_rank'] = stock_info.get('leader_rank', 0)
            result['market_cap'] = stock_info.get('market_cap', 0)
            
            tags = []
            grade = result.get('grade', 'C')
            if grade == 'S':
                tags.append("S级")
            elif grade == 'A':
                tags.append("A级")
            
            if result['is_leader']:
                tags.append(f"中军#{result['leader_rank']}")
            
            if result.get('cmf_strong_bullish'):
                tags.append("强势流入")
            elif result.get('cmf_bullish') and result.get('cmf_rising'):
                tags.append("资金流入")
            elif result.get('cmf_bullish'):
                tags.append("资金净流入")
            
            if result.get('rsv_recovering'):
                tags.append("超卖回升")
            elif result.get('rsv_golden'):
                rsv_val = result.get('rsv', 50)
                tags.append("RSV强势" if rsv_val >= 65 else "RSV健康")
            
            if result.get('ma_full_bullish'):
                tags.append("多头排列")
            elif result.get('ma_bullish'):
                tags.append("短多")
            if result.get('cross_above_ma5'):
                tags.append("上穿M5")
            
            if result.get('macd_golden') and result.get('macd_hist_positive'):
                tags.append("MACD强势")
            elif result.get('macd_golden'):
                tags.append("MACD金叉")
            
            if result.get('is_volume_price_up'):
                tags.append("量价齐升")
            elif result.get('is_volume_up'):
                tags.append("放量")
            
            if result.get('low_volatility'):
                tags.append("低波蓄势")
            
            turnover = result.get('turnover', 0)
            if 3 <= turnover <= 10:
                tags.append("人气旺")
            elif turnover > 10:
                tags.append("超人气")
            elif 1 <= turnover < 3:
                tags.append("有关注")
            
            if result.get('pct_change', 0) >= 5:
                tags.append("先锋")
            
            result['tags'] = tags
            
            if df is not None and precache_kline:
                try:
                    kline_data = prepare_kline_data(df)
                    if kline_data:
                        db.save_kline_cache(code, kline_data)
                except Exception as e:
                    print(f"[WARN] 预缓存K线数据失败 {code}: {e}")
            
            return result
    except Exception:
        pass
    return None


def prepare_kline_data(df):
    """从DataFrame准备K线数据"""
    import pandas as pd
    
    try:
        # 保留所有有效行（至少要有 OHLC），不依赖指标列过滤
        base_cols = ['open', 'high', 'low', 'close']
        if set(base_cols).issubset(df.columns):
            df = df.dropna(subset=base_cols)
        df = df.tail(60)
        
        if len(df) == 0:
            return None
        
        def safe_list(series):
            return [None if pd.isna(x) else float(x) for x in series]
        
        def date_to_str(d):
            if hasattr(d, 'strftime'):
                return d.strftime('%Y-%m-%d')
            return str(d)
        
        candles = []
        for _, row in df.iterrows():
            candles.append({
                'time': date_to_str(row['date']),
                'open': float(row['open']) if pd.notna(row['open']) else None,
                'high': float(row['high']) if pd.notna(row['high']) else None,
                'low': float(row['low']) if pd.notna(row['low']) else None,
                'close': float(row['close']) if pd.notna(row['close']) else None,
            })
        
        volume_data = []
        for _, row in df.iterrows():
            color = '#ef5350' if row['close'] >= row['open'] else '#26a69a'
            volume_data.append({
                'time': date_to_str(row['date']),
                'value': float(row['volume']) if pd.notna(row['volume']) else 0,
                'color': color
            })
        
        bb_upper_data = [{'time': date_to_str(row['date']), 'value': float(row['bb_upper'])} for _, row in df.iterrows() if pd.notna(row['bb_upper'])]
        bb_middle_data = [{'time': date_to_str(row['date']), 'value': float(row['bb_middle'])} for _, row in df.iterrows() if pd.notna(row['bb_middle'])]
        bb_lower_data = [{'time': date_to_str(row['date']), 'value': float(row['bb_lower'])} for _, row in df.iterrows() if pd.notna(row['bb_lower'])]
        
        cmf_data = safe_list(df['cmf']) if 'cmf' in df.columns else []
        pct_change_data = safe_list(df['pct_change']) if 'pct_change' in df.columns else []
        
        latest = df.iloc[-1] if len(df) > 0 else None
        latest_info = None
        if latest is not None:
            latest_info = {
                'close': float(latest['close']) if pd.notna(latest['close']) else 0,
                'pct_change': float(latest['pct_change']) if pd.notna(latest['pct_change']) else 0,
                'date': date_to_str(latest['date']),
            }
        
        return {
            'candles': candles,
            'volumes': volume_data,
            'bb_upper': bb_upper_data,
            'bb_middle': bb_middle_data,
            'bb_lower': bb_lower_data,
            'bb_width': safe_list(df['bb_width_pct']),
            'width_ma5': safe_list(df['width_ma_short']),
            'width_ma10': safe_list(df['width_ma_long']),
            'cmf': cmf_data,
            'pct_change': pct_change_data,
            'latest': latest_info,
            'dates': df['date'].astype(str).tolist(),
            'vp_obv': safe_list(df['vp_obv']) if 'vp_obv' in df.columns else [],
            'vp_std_vol': safe_list(df['vp_std_vol']) if 'vp_std_vol' in df.columns else [],
            'vp_max_vol': safe_list(df['vp_max_vol']) if 'vp_max_vol' in df.columns else [],
            'vp_color': [int(x) if pd.notna(x) else 0 for x in df['vp_color']] if 'vp_color' in df.columns else [],
            'vp_lxtp': [bool(x) if pd.notna(x) else False for x in df['vp_lxtp']] if 'vp_lxtp' in df.columns else [],
            'vp_lxtp1': [bool(x) if pd.notna(x) else False for x in df['vp_lxtp1']] if 'vp_lxtp1' in df.columns else [],
            'vp_super_vol': [bool(x) if pd.notna(x) else False for x in df['vp_super_vol']] if 'vp_super_vol' in df.columns else [],
            'vp_vol_break_up': [bool(x) if pd.notna(x) else False for x in df['vp_vol_break_up']] if 'vp_vol_break_up' in df.columns else [],
            'vp_vol_break_down': [bool(x) if pd.notna(x) else False for x in df['vp_vol_break_down']] if 'vp_vol_break_down' in df.columns else [],
            'vp_bull_signal': [bool(x) if pd.notna(x) else False for x in df['vp_bull_signal']] if 'vp_bull_signal' in df.columns else [],
            'vp_bear_signal': [bool(x) if pd.notna(x) else False for x in df['vp_bear_signal']] if 'vp_bear_signal' in df.columns else [],
            'vp_main_buy_signal': [bool(x) if pd.notna(x) else False for x in df['vp_main_buy_signal']] if 'vp_main_buy_signal' in df.columns else [],
            'vp_ma_golden': [bool(x) if pd.notna(x) else False for x in df['vp_ma_golden']] if 'vp_ma_golden' in df.columns else [],
            'vp_cost_break': [bool(x) if pd.notna(x) else False for x in df['vp_cost_break']] if 'vp_cost_break' in df.columns else [],
            'vp_dbhs': safe_list(df['vp_dbhs']) if 'vp_dbhs' in df.columns else [],
        }
    except Exception as e:
        print(f"[ERROR] prepare_kline_data 失败: {e}")
        return None


# ==================== API 接口 ====================

@strategy_bp.route('/strategy')
def strategy_page():
    """策略中心页面 - 重定向到 Vue 前端"""
    from flask import redirect
    return redirect('/frontend/strategy')


@strategy_bp.route('/strategy/bollinger')
def bollinger_page():
    """布林收缩策略页面 - 重定向到 Vue 前端"""
    from flask import redirect
    return redirect('/frontend/strategy/bollinger')


@strategy_bp.route('/strategy/ticai')
def ticai_page():
    """题材挖掘页面 - 保留旧路由供兼容，返回提示信息"""
    return jsonify({
        'message': '题材挖掘页面已迁移至 Vue 组件，请访问 /strategy/ticai',
        'redirect': '/strategy/ticai'
    })


@strategy_bp.route('/strategy/ai')
def ai_strategy_page():
    """AI 策略页面 - Vue 组件直接调用 API，不再使用 iframe"""
    return jsonify({
        'message': 'AI 策略页面由 Vue 组件渲染，请访问 /frontend/strategy/ai',
        'vue_route': '/strategy/ai'
    })


@strategy_bp.route('/api/hot-sectors')
def get_hot_sectors():
    """获取热点板块列表（Redis 缓存 30s）"""
    cache_key = 'scan/hot-sectors'
    hit = get(cache_key)
    if hit is not None:
        return jsonify({'success': True, 'data': hit})

    try:
        from utils.ths_crawler import get_ths_industry_list

        limit = request.args.get('limit', 20, type=int)
        limit = max(1, min(50, limit))

        df = get_ths_industry_list()

        if df is None or len(df) == 0:
            return jsonify({'success': False, 'error': '无法获取数据'})

        sectors = []
        for _, row in df.head(limit).iterrows():
            sectors.append({
                'name': row['板块'],
                'change': round(float(row['涨跌幅']), 2),
                'leader': row.get('领涨股', ''),
                'leader_change': round(float(row.get('领涨股-涨跌幅', 0)), 2)
            })

        _cache_set(cache_key, sectors, ttl=30)
        return jsonify({'success': True, 'data': sectors})

    except Exception as e:
        logger.error(f"获取热点板块失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@strategy_bp.route('/api/scan/start', methods=['POST'])
def start_scan():
    """开始扫描任务"""
    global scan_status
    
    with scan_lock:
        if scan_status['is_scanning']:
            return jsonify({'success': False, 'error': '扫描正在进行中'})
    
    data = request.json or {}
    top_sectors = data.get('sectors', 5)
    min_days = data.get('min_days', 3)
    period = data.get('period', 20)
    bb_width_max = data.get('bb_width_max', 20)

    top_sectors = max(1, min(30, int(top_sectors)))
    min_days = max(0, min(100, int(min_days)))
    period = max(10, min(365, int(period)))
    bb_width_max = max(5, min(50, int(bb_width_max)))

    logger.info(f"开始扫描: sectors={top_sectors}, min_days={min_days}, period={period}, bb_width_max={bb_width_max}%")

    params = {
        'sectors': top_sectors,
        'min_days': min_days,
        'period': period,
        'bb_width_max': bb_width_max,
    }
    scan_id = db.create_scan_record(params)
    invalidate('scan/history')

    with scan_lock:
        scan_status = {
            'is_scanning': True,
            'scan_id': scan_id,
            'progress': 0,
            'current_sector': '准备中...',
            'error': None,
            'cancelled': False
        }
    
    import sys
    thread = threading.Thread(
        target=run_scan,
        args=(scan_id, top_sectors, min_days, period, bb_width_max)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'message': '扫描已开始', 'scan_id': scan_id})


@strategy_bp.route('/api/scan/cancel', methods=['POST'])
def cancel_scan():
    """取消当前扫描"""
    global scan_status
    
    if not scan_status['is_scanning']:
        return jsonify({'success': False, 'error': '没有正在进行的扫描'})
    
    scan_status['cancelled'] = True
    scan_status['current_sector'] = '正在取消...'
    
    return jsonify({'success': True, 'message': '正在取消扫描'})


api_semaphore = threading.Semaphore(3)


def fetch_with_rate_limit(func, delay=0.3):
    """带限流的请求包装器"""
    with api_semaphore:
        time.sleep(delay)
        return func()


def _fetch_kline_worker(code: str, fetch_days: int, period: int):
    """
    进程级 K 线抓取 worker（必须在模块顶层，以支持 ProcessPoolExecutor）。
    每只股票独立进程，天然隔离 mini_racer，避免多线程崩溃。
    10秒超时保护，防止网络卡死。
    """
    import sys
    try:
        from utils.ths_crawler import get_stock_kline_sina
        kline_df = get_stock_kline_sina(code, days=min(fetch_days, 800))
        if kline_df is not None and len(kline_df) >= period + 10:
            return (code, kline_df)
        return (code, None)
    except Exception:
        return (code, None)


def run_scan(scan_id: int, top_sectors: int, min_days: int, period: int, bb_width_max: int = 20):
    """高效扫描任务"""
    global scan_status
    
    from utils.ths_crawler import (
        get_ths_industry_list, 
        fetch_ths_industry_stocks,
        get_stock_kline_sina
    )
    from bollinger_squeeze_strategy import BollingerSqueezeStrategy
    import pandas as pd
    
    try:
        start_time = time.time()
        print(f"🚀 开始扫描: scan_id={scan_id}, sectors={top_sectors}, min_days={min_days}, period={period}, bb_width_max={bb_width_max}%")
        
        strategy = BollingerSqueezeStrategy(
            period=period,
            min_squeeze_days=min_days
        )
        
        # 获取热点板块
        print("📊 获取热点板块...")
        scan_status['current_sector'] = '获取热点板块...'
        
        try:
            df = get_ths_industry_list()
        except Exception as e1:
            print(f"[WARN] 第一次获取失败: {e1}，重试...")
            time.sleep(2)
            df = get_ths_industry_list()
        
        if df is None or len(df) == 0:
            raise Exception('无法获取热点板块数据')
        
        hot_sectors_list = []
        for _, row in df.head(top_sectors).iterrows():
            hot_sectors_list.append({
                'name': row['板块'],
                'code': row.get('代码', ''),
                'change': round(float(row['涨跌幅']), 2),
                'leader': row.get('领涨股', ''),
                'leader_change': round(float(row.get('领涨股-涨跌幅', 0)), 2)
            })
        
        db.save_hot_sectors(scan_id, hot_sectors_list)
        sector_names = [s['name'] for s in hot_sectors_list]
        print(f"✅ 热点板块: {sector_names}")
        
        # 获取成分股
        print(f"\n📥 获取 {len(hot_sectors_list)} 个板块的成分股...")
        scan_status['current_sector'] = '获取成分股...'
        scan_status['progress'] = 10
        
        cached_sectors = db.get_all_sector_stocks_cache(sector_names)
        sectors_to_fetch = [s for s in hot_sectors_list if s['name'] not in cached_sectors]
        all_sector_stocks = dict(cached_sectors)
        
        if sectors_to_fetch:
            for sector_info in sectors_to_fetch:
                if scan_status.get('cancelled'):
                    break
                sector_name = sector_info['name']
                sector_code = sector_info['code']
                
                if not sector_code:
                    print(f"  ⚠️ {sector_name}: 无行业代码，跳过")
                    continue
                
                try:
                    print(f"  📥 爬取 {sector_name}({sector_code})...")
                    stocks = fetch_ths_industry_stocks(sector_code, sector_name)
                    
                    if stocks:
                        stocks.sort(key=lambda x: x.get('market_cap', 0), reverse=True)
                        db.save_sector_stocks_cache(sector_name, stocks)
                        all_sector_stocks[sector_name] = stocks
                        print(f"  ✅ {sector_name}: {len(stocks)} 只")
                except Exception as e:
                    print(f"  ❌ {sector_name}: {e}")
        
        # 合并去重
        stock_info_map = {}
        for sector_info in hot_sectors_list:
            sector_name = sector_info['name']
            stocks = all_sector_stocks.get(sector_name, [])
            for idx, stock in enumerate(stocks):
                code = stock['code']
                if code not in stock_info_map:
                    stock_info_map[code] = {
                        **stock,
                        'sector_name': sector_name,
                        'sector_change': sector_info['change'],
                        'is_leader': idx < 3,
                        'leader_rank': idx + 1 if idx < 3 else 0,
                    }
        
        stock_codes = list(stock_info_map.keys())
        print(f"📊 成分股: {len(stock_codes)} 只\n")
        
        # 获取K线数据
        print(f"📈 获取K线数据...")
        scan_status['current_sector'] = '获取K线数据...'
        scan_status['progress'] = 25
        
        kline_data = {}

        if stock_codes:
            print(f"  🌐 需要获取: {len(stock_codes)} 只股票K线")

            fetch_days = max(120, int(period) + 40)

            fetched_count = 0

            with ProcessPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(_fetch_kline_worker, code, fetch_days, period): code
                    for code in stock_codes
                }

                pending = set(futures.keys())
                while pending:
                    if scan_status.get('cancelled'):
                        for f in pending:
                            f.cancel()
                        scan_status['current_sector'] = '已取消'
                        return
                    done, still_pending = wait(pending, timeout=15, return_when=FIRST_COMPLETED)
                    for future in done:
                        try:
                            code, df = future.result(timeout=5)
                            if df is not None:
                                kline_data[code] = df
                                fetched_count += 1
                                if fetched_count % 50 == 0:
                                    progress = 25 + int(fetched_count / len(stock_codes) * 30)
                                    scan_status['progress'] = min(55, progress)
                                    print(f"  📊 K线进度: {fetched_count}/{len(stock_codes)}")
                        except Exception:
                            pass
                    pending = still_pending
                    if not done and not still_pending:
                        break

            print(f"  ✅ K线获取完成: {fetched_count}/{len(stock_codes)}")
        
        # 计算指标并筛选
        print(f"\n📈 计算技术指标...")
        scan_status['current_sector'] = '计算指标...'
        scan_status['progress'] = 60
        
        analyzed_results = []
        total = len(kline_data)
        
        for idx, (code, df) in enumerate(kline_data.items()):
            if scan_status.get('cancelled'):
                print("⚠️ 扫描已取消")
                break
            
            if df is None or (isinstance(df, pd.DataFrame) and len(df) < period + 10):
                continue
            
            try:
                df = strategy.calculate_bollinger_bands(df)
                df = strategy.calculate_squeeze_signal(df)
                df = strategy.calculate_volume_signal(df)
                df = strategy.calculate_trend_indicators(df)
                df = strategy.calculate_volume_profile(df)
                df = strategy.calculate_composite_score(df)
                
                latest = df.iloc[-1]
                bb_width_pct = float(latest.get('bb_width_pct', 0) or 0)
                
                # 窄幅筛选：bb_width_pct <= bb_width_max
                if latest['squeeze_streak'] >= min_days and bb_width_pct <= bb_width_max:
                    info = stock_info_map.get(code, {})
                    result = {
                        'code': code,
                        'name': info.get('name', ''),
                        'sector_name': info.get('sector_name', ''),
                        'sector_change': info.get('sector_change', 0),
                        'is_leader': info.get('is_leader', False),
                        'leader_rank': info.get('leader_rank', 0),
                        'market_cap': info.get('market_cap', 0),
                        'close': round(float(latest['close']), 2),
                        'pct_change': round(float(latest.get('pct_change', 0)), 2),
                        'turnover': round(float(latest['turnover']), 2) if pd.notna(latest.get('turnover')) else 0,
                        'squeeze_days': int(latest['squeeze_streak']),
                        'total_score': int(latest['total_score']),
                        'grade': latest['grade'],
                        'bb_width_pct': round(float(latest['bb_width_pct']), 2),
                        'ma_bullish': bool(latest.get('ma_bullish', False)),
                        'cross_above_ma5': bool(latest.get('cross_above_ma5', False)),
                        'ma_full_bullish': bool(latest.get('ma_full_bullish', False)),
                        'macd_golden': bool(latest.get('macd_golden', False)),
                        'macd_hist_positive': bool(latest.get('macd_hist_positive', False)),
                        'cmf_bullish': bool(latest.get('cmf_bullish', False)),
                        'cmf_strong_bullish': bool(latest.get('cmf_strong_bullish', False)),
                        'cmf_rising': bool(latest.get('cmf_rising', False)),
                        'rsv': round(float(latest['rsv']), 2) if pd.notna(latest.get('rsv')) else 50.0,
                        'rsv_recovering': bool(latest.get('rsv_recovering', False)),
                        'rsv_golden': bool(latest.get('rsv_golden', False)),
                        'is_volume_up': bool(latest.get('is_volume_up', False)),
                        'is_volume_price_up': bool(latest.get('is_volume_price_up', False)),
                        'low_volatility': bool(latest.get('low_volatility', False)),
                        'volume_ratio': round(float(latest['volume_ratio']), 2)
                        if pd.notna(latest.get('volume_ratio')) else 0.0,
                    }
                    
                    # 生成完整标签
                    tags = []
                    grade = latest.get('grade', 'C')
                    if grade == 'S':
                        tags.append("S级")
                    elif grade == 'A':
                        tags.append("A级")

                    if result['is_leader']:
                        tags.append(f"中军#{result['leader_rank']}")

                    # CMF 资金流标签
                    if latest.get('cmf_strong_bullish'):
                        tags.append("强势流入")
                    elif latest.get('cmf_bullish') and latest.get('cmf_rising'):
                        tags.append("资金流入")
                    elif latest.get('cmf_bullish'):
                        tags.append("资金净流入")

                    # RSV 标签
                    if latest.get('rsv_recovering'):
                        tags.append("超卖回升")
                    elif latest.get('rsv_golden'):
                        rsv_val = latest.get('rsv', 50)
                        tags.append("RSV强势" if rsv_val >= 65 else "RSV健康")

                    # 趋势标签
                    if latest.get('ma_full_bullish'):
                        tags.append("多头排列")
                    elif latest.get('ma_bullish'):
                        tags.append("短多")
                    if latest.get('cross_above_ma5'):
                        tags.append("上穿M5")

                    # MACD标签
                    if latest.get('macd_golden') and latest.get('macd_hist_positive'):
                        tags.append("MACD强势")
                    elif latest.get('macd_golden'):
                        tags.append("MACD金叉")

                    # 量能标签
                    if latest.get('is_volume_price_up'):
                        tags.append("量价齐升")
                    elif latest.get('is_volume_up'):
                        tags.append("放量")

                    # 波动率标签
                    if latest.get('low_volatility'):
                        tags.append("低波蓄势")

                    # 人气标签
                    turnover_val = latest.get('turnover', 0)
                    if 3 <= turnover_val <= 10:
                        tags.append("人气旺")
                    elif turnover_val > 10:
                        tags.append("超人气")
                    elif 1 <= turnover_val < 3:
                        tags.append("有关注")

                    # 先锋标签
                    if latest.get('pct_change', 0) >= 5:
                        tags.append("先锋")

                    result['tags'] = tags
                    # VRR 波动回归率
                    result['vrr'] = round(float(latest['vrr']), 4) if pd.notna(latest.get('vrr')) else 0
                    result['svrr'] = round(float(latest['svrr']), 4) if pd.notna(latest.get('svrr')) else 0
                    result['vrr_score'] = int(latest['vrr_score']) if pd.notna(latest.get('vrr_score')) else 0
                    result['combo_score'] = int(latest['combo_score']) if pd.notna(latest.get('combo_score')) else 0

                    analyzed_results.append(result)
                
                if (idx + 1) % 100 == 0:
                    progress = 60 + int((idx + 1) / total * 30)
                    scan_status['progress'] = min(90, progress)
                    
            except Exception:
                continue
        
        print(f"📈 分析完成，符合条件: {len(analyzed_results)} 只")
        
        # 兜底逻辑：如果收口股票太少，按涨跌幅补充
        min_fallback_count = 10  # 最少需要展示的股票数量
        if len(analyzed_results) < min_fallback_count and kline_data:
            print(f"📈 收口股票不足，按涨跌幅补充...")
            # 按涨跌幅排序所有股票
            fallback_results = []
            for code, df in kline_data.items():
                if df is None or len(df) < period + 10:
                    continue
                if any(r['code'] == code for r in analyzed_results):
                    continue  # 已在收口列表中
                
                latest = df.iloc[-1]
                bb_w = float(latest.get('bb_width_pct', 0) or 0)
                pct = float(latest.get('pct_change', 0) or 0)
                
                # 只取窄幅 ≤ bb_width_max 的
                if bb_w <= bb_width_max:
                    info = stock_info_map.get(code, {})
                    result = {
                        'code': code,
                        'name': info.get('name', ''),
                        'sector_name': info.get('sector_name', ''),
                        'sector_change': info.get('sector_change', 0),
                        'is_leader': info.get('is_leader', False),
                        'leader_rank': info.get('leader_rank', 0),
                        'market_cap': info.get('market_cap', 0),
                        'close': round(float(latest['close']), 2),
                        'pct_change': round(pct, 2),
                        'turnover': round(float(latest.get('turnover', 0) or 0), 2),
                        'squeeze_days': 0,
                        'total_score': 0,
                        'grade': 'C',
                        'bb_width_pct': round(float(latest.get('bb_width_pct', 0) or 0), 2),
                        'ma_bullish': False,
                        'cross_above_ma5': False,
                        'macd_golden': False,
                        'cmf_bullish': False,
                        'is_volume_up': False,
                        'is_volume_price_up': False,
                        'low_volatility': False,
                        'volume_ratio': 0.0,
                        'tags': ['窄幅股'],
                    }
                    fallback_results.append(result)
            
            # 按涨跌幅排序，取前几名
            fallback_results.sort(key=lambda x: x['pct_change'], reverse=True)
            needed = min_fallback_count - len(analyzed_results)
            analyzed_results.extend(fallback_results[:needed])
            print(f"📈 补充涨幅股 {len(fallback_results[:needed])} 只")
        
        # ── 实时行情：统一替换为当日最新涨跌幅 ──────────────────────────────
        # 板块涨幅来自 THS/EM（实时），个股涨幅来自 K 线（可能落后）
        # 这里统一用东财实时接口拉当日的涨跌幅，确保板块和个股同时间源
        all_codes = [r['code'] for r in analyzed_results if r.get('code')]
        if all_codes:
            try:
                secids = [
                    f"{'1' if c.startswith(('6','9')) else '0'}.{c}"
                    for c in all_codes
                ]
                live_resp = requests.get(
                    "http://push2.eastmoney.com/api/qt/ulist/get",
                    params={
                        "fltt": "2",
                        "secids": ",".join(secids),
                        "fields": "f2,f3,f12",
                    },
                    timeout=10,
                )
                live_map = {}
                live_items = json.loads(live_resp.text).get('data', {}).get('diff', [])
                for it in live_items:
                    live_map[str(it.get('f12', ''))] = it
                updated = 0
                for r in analyzed_results:
                    live = live_map.get(r['code'])
                    if live:
                        r['pct_change'] = round(float(live.get('f3') or 0), 2)
                        r['close'] = round(float(live.get('f2') or r.get('close')), 2)
                        updated += 1
                print(f"  📡 实时行情更新: {updated}/{len(all_codes)} 只")
            except Exception as e:
                print(f"  [WARN] 实时行情获取失败，沿用K线数据: {e}")

        # 保存结果
        scan_status['current_sector'] = '保存结果...'
        scan_status['progress'] = 95

        sector_results = {}
        for r in analyzed_results:
            sector = r.get('sector_name', '未知')
            if sector not in sector_results:
                sector_results[sector] = []
            sector_results[sector].append(r)
        
        for sector_name, results in sector_results.items():
            results.sort(key=lambda x: x.get('total_score', 0), reverse=True)
            sector_change = results[0].get('sector_change', 0) if results else 0
            db.save_sector_result(scan_id, sector_name, sector_change, results)
            print(f"  💾 {sector_name}: {len(results)} 只")
        
        elapsed = time.time() - start_time
        scan_status['progress'] = 100
        scan_status['current_sector'] = '扫描完成'
        db.update_scan_status(scan_id, 'completed')
        print(f"\n✅ 扫描完成! 耗时: {elapsed:.1f}秒")

        # ── 飞书通知推送 ────────────────────────────────────────────────
        try:
            from utils.feishu_notifier import send_feishu_scan_alert
            scan_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ok = send_feishu_scan_alert(
                scan_id=scan_id,
                scan_time=scan_time_str,
                sector_results=sector_results,
                hot_sectors=hot_sectors_list,
                params={'top_sectors': top_sectors, 'min_days': min_days, 'period': period, 'bb_width_max': f'{bb_width_max}%'},
            )
            if ok:
                print(f"📱 飞书通知推送成功")
            else:
                print(f"⚠️ 飞书通知推送失败（可能未启用或 Webhook 未配置）")
        except Exception as feishu_err:
            print(f"⚠️ 飞书通知异常: {feishu_err}")
        # ── 飞书通知推送结束 ─────────────────────────────────────────────

    except Exception as e:
        scan_status['error'] = str(e)
        db.update_scan_status(scan_id, 'error', str(e))
        print(f"❌ 扫描出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        with scan_lock:
            scan_status['is_scanning'] = False


@strategy_bp.route('/api/feishu/test', methods=['POST', 'GET'])
def test_feishu():
    """测试飞书 Webhook 连接；POST JSON 可传 webhook_url 测当前输入框地址"""
    try:
        from utils.feishu_notifier import send_feishu_test
        url = None
        if request.method == 'POST' and request.is_json:
            body = request.json or {}
            u = (body.get('webhook_url') or '').strip()
            if u and u.startswith('http'):
                url = u
        ok = send_feishu_test(webhook_url=url)
        if ok:
            return jsonify({'success': True, 'message': '飞书测试消息发送成功！请检查飞书群。'})
        return jsonify({'success': False, 'error': '飞书测试消息发送失败，请检查 Webhook 地址或飞书群设置。'})
    except Exception as e:
        logger.exception('飞书测试失败')
        return jsonify({'success': False, 'error': str(e)})


def _get_trader_agent_push_service():
    return current_app.extensions.get('trader_agent_push_service')


def _get_trader_agent_push_scheduler():
    return current_app.extensions.get('trader_agent_push_scheduler')


@strategy_bp.route('/api/agents/push/status', methods=['GET'])
def get_agent_push_status():
    """返回游资智能体飞书推送调度状态。"""
    try:
        service = _get_trader_agent_push_service()
        scheduler = _get_trader_agent_push_scheduler()
        if not service:
            return jsonify({'success': False, 'error': '游资智能体推送服务尚未初始化'}), 503

        service_status = service.status()
        scheduler_status = scheduler.status() if scheduler else {
            'enabled': False,
            'running': False,
            'slots': [],
            'nextSlot': None,
        }
        return jsonify({
            'success': True,
            'data': {
                **service_status,
                **scheduler_status,
            },
        })
    except Exception as e:
        logger.exception('获取游资智能体推送状态失败')
        return jsonify({'success': False, 'error': str(e)}), 500


@strategy_bp.route('/api/agents/push/trigger', methods=['POST'])
def trigger_agent_push():
    """手动触发一次游资智能体飞书推送。"""
    try:
        service = _get_trader_agent_push_service()
        if not service:
            return jsonify({'success': False, 'error': '游资智能体推送服务尚未初始化'}), 503

        body = request.get_json(silent=True) or {}
        agent_ids = body.get('agent_ids') or body.get('agentIds')
        slot_key = str(body.get('slot_key') or body.get('slotKey') or '').strip() or None
        slot_label = str(body.get('slot_label') or body.get('slotLabel') or '').strip() or None
        webhook_url = str(body.get('webhook_url') or body.get('webhookUrl') or '').strip() or None
        dry_run = bool(body.get('dry_run') if 'dry_run' in body else body.get('dryRun', False))
        include_payload = bool(body.get('include_payload') if 'include_payload' in body else body.get('includePayload', False))

        result = service.run_push(
            agent_ids=agent_ids,
            slot_key=slot_key,
            slot_label=slot_label,
            trigger_type='manual',
            webhook_url=webhook_url,
            dry_run=dry_run,
        )

        if include_payload:
            notifier = FeishuNotifier(webhook_url=webhook_url)
            result['payloadPreview'] = notifier.build_agent_digest_payload(result.get('digest') or {})

        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.exception('手动触发游资智能体推送失败')
        return jsonify({'success': False, 'error': str(e)}), 500


@strategy_bp.route('/api/bollinger/alerts', methods=['GET'])
def list_bollinger_alerts():
    """布林带飞书告警规则列表"""
    try:
        limit = request.args.get('limit', 100, type=int)
        rows = db.list_bollinger_alert_rules(limit=limit)
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        logger.exception('list_bollinger_alerts: %s', e)
        return jsonify({'success': False, 'error': str(e)})


@strategy_bp.route('/api/bollinger/alerts', methods=['POST'])
def create_bollinger_alert():
    """新建告警规则"""
    try:
        payload = request.json or {}
        scan_id = payload.get('scan_id')
        if scan_id is not None and scan_id != '':
            try:
                sid = int(scan_id)
                if not db.get_scan_detail(sid):
                    scan_id = None
                else:
                    scan_id = sid
            except (TypeError, ValueError):
                scan_id = None
        else:
            scan_id = None
        payload = {**payload, 'scan_id': scan_id}
        new_id = db.create_bollinger_alert_rule(payload)
        row = db.get_bollinger_alert_rule(new_id)
        return jsonify({'success': True, 'data': row})
    except Exception as e:
        logger.exception('create_bollinger_alert: %s', e)
        return jsonify({'success': False, 'error': str(e)})


@strategy_bp.route('/api/bollinger/alerts/<int:rule_id>', methods=['GET'])
def get_bollinger_alert(rule_id: int):
    """单条告警规则"""
    row = db.get_bollinger_alert_rule(rule_id)
    if not row:
        return jsonify({'success': False, 'error': '规则不存在'}), 404
    return jsonify({'success': True, 'data': row})


@strategy_bp.route('/api/bollinger/alerts/<int:rule_id>', methods=['PUT'])
def update_bollinger_alert(rule_id: int):
    """更新告警规则"""
    try:
        payload = request.json or {}
        if 'scan_id' in payload:
            sid = payload.get('scan_id')
            if sid is not None and sid != '':
                try:
                    sid = int(sid)
                    payload['scan_id'] = sid if db.get_scan_detail(sid) else None
                except (TypeError, ValueError):
                    payload['scan_id'] = None
            else:
                payload['scan_id'] = None
        ok = db.update_bollinger_alert_rule(rule_id, payload)
        if not ok:
            return jsonify({'success': False, 'error': '规则不存在或未变更'}), 404
        return jsonify({'success': True, 'data': db.get_bollinger_alert_rule(rule_id)})
    except Exception as e:
        logger.exception('update_bollinger_alert: %s', e)
        return jsonify({'success': False, 'error': str(e)})


@strategy_bp.route('/api/bollinger/alerts/<int:rule_id>', methods=['DELETE'])
def delete_bollinger_alert(rule_id: int):
    """删除告警规则"""
    if not db.delete_bollinger_alert_rule(rule_id):
        return jsonify({'success': False, 'error': '规则不存在'}), 404
    return jsonify({'success': True, 'data': True})


@strategy_bp.route('/api/scan/status')
def get_scan_status():
    """获取当前扫描状态"""
    return jsonify({
        'is_scanning': scan_status['is_scanning'],
        'scan_id': scan_status.get('scan_id'),
        'progress': scan_status['progress'],
        'current_sector': scan_status['current_sector'],
        'error': scan_status['error'],
        'cancelled': scan_status.get('cancelled', False)
    })


@strategy_bp.route('/api/scan/results')
def get_scan_results():
    """获取扫描结果"""
    scan_id = request.args.get('scan_id', type=int)
    
    if scan_id:
        scan_detail = db.get_scan_detail(scan_id)
    else:
        scan_detail = db.get_latest_scan()
    
    if not scan_detail:
        return jsonify({
            'success': True,
            'results': {},
            'hot_sectors': [],
            'last_update': None
        })
    
    return jsonify({
        'success': True,
        'scan_id': scan_detail['id'],
        'results': scan_detail.get('results', {}),
        'hot_sectors': scan_detail.get('hot_sectors', []),
        'last_update': scan_detail['scan_time']
    })


@strategy_bp.route('/api/scan/history')
def get_scan_history():
    """获取历史扫描记录列表（Redis 缓存 60s，扫描开始/删除时失效）"""
    cache_key = 'scan/history'
    hit = get(cache_key)
    if hit is not None:
        return jsonify({'success': True, 'data': hit})

    limit = request.args.get('limit', 20, type=int)
    limit = max(1, min(100, limit))
    records = db.get_scan_list(limit=limit)
    _cache_set(cache_key, records, ttl=60)
    return jsonify({
        'success': True,
        'data': records
    })


# ── AI 摘要辅助函数（必须在路由前定义）──────────────────────────────────────

def _scan_valid_stock_codes(detail: dict) -> set:
    """扫描结果中出现的 6 位股票代码集合，用于过滤模型幻觉推荐。"""
    import builtins
    from agent_prompts import normalize_agent_stock_code
    valid = builtins.set()
    for _, block in (detail.get('results') or {}).items():
        for s in block.get('stocks') or []:
            c = normalize_agent_stock_code(s.get('code'))
            if c:
                valid.add(c)
    return valid


def _build_scan_llm_payload(detail: dict) -> tuple:
    """(板块概要文本, 股票行列表)"""
    sector_lines = []
    for name, block in (detail.get('results') or {}).items():
        try:
            ch = float(block.get('change') or 0)
        except (TypeError, ValueError):
            ch = 0.0
        sector_lines.append(f"- {name}：板块涨跌 {ch:+.2f}%")
    stock_rows = []
    for sec_name, block in (detail.get('results') or {}).items():
        for s in block.get('stocks') or []:
            code = s.get('code', '')
            nm = s.get('name', '')
            gr = s.get('grade', '')
            pct = s.get('pct_change', '')
            sq = s.get('squeeze_days', '')
            bw = s.get('bandwidth_pct', s.get('bandwidth', ''))
            sc = s.get('total_score', s.get('score', ''))
            stock_rows.append(
                f"{code}\t{nm}\t{sec_name}\tgrade={gr}\tpct={pct}\tsqueeze={sq}\tbw={bw}\tscore={sc}"
            )
    return '\n'.join(sector_lines), stock_rows


@strategy_bp.route('/api/scan/<int:scan_id>/ai-summary', methods=['GET'])
def scan_ai_summary(scan_id: int):
    """
    DeepSeek：单次扫描小结 + Chain-of-Thought 推理 + 至多 3 只跟踪建议（非投资建议）。
    结果写入 scan_records.ai_summary_json，GET 默认返回缓存；?refresh=1 强制重新调用模型。
    无缓存且非 refresh 时返回 data: null，由前端「生成 / 再解读」触发 refresh。
    """
    from agent_prompts import normalize_agent_stock_code

    refresh = request.args.get('refresh', default=0, type=int) == 1

    detail = db.get_scan_detail(scan_id)
    if not detail:
        return jsonify({'success': False, 'error': '扫描记录不存在'}), 404

    stock_rows_all = []
    for _, block in (detail.get('results') or {}).items():
        stock_rows_all.extend(block.get('stocks') or [])

    # 无成分股：写入静态 empty 小结，不调用模型
    if not stock_rows_all:
        empty_out = {
            'cot_steps': [
                {'title': '数据', 'content': '本次扫描暂无成分股结果，无法生成模型推理与推荐。'}
            ],
            'recommendations': [],
            'closing_note': '',
            'source': 'empty',
        }
        if not refresh:
            cached = db.get_scan_ai_summary(scan_id)
            if cached is not None:
                return jsonify({'success': True, 'data': cached, 'cached': True})
        db.save_scan_ai_summary(scan_id, empty_out)
        data = db.get_scan_ai_summary(scan_id)
        return jsonify({'success': True, 'data': data, 'cached': False})

    # 有成分股：默认只读库；无缓存则返回 null（不自动打模型）
    if not refresh:
        cached = db.get_scan_ai_summary(scan_id)
        if cached is not None:
            return jsonify({'success': True, 'data': cached, 'cached': True})
        return jsonify({'success': True, 'data': None, 'cached': False})

    if not get_client().is_configured():
        logger.warning('scan_ai_summary: LLM 未配置')
        return jsonify({
            'success': False,
            'error': 'LLM 服务未配置',
            'data': {'fallback': True},
        }), 503

    sector_text, stock_rows = _build_scan_llm_payload(detail)
    stock_rows = stock_rows[:120]
    stock_text = '\n'.join(stock_rows)
    params = detail.get('params') or {}

    user_prompt = f"""扫描时间：{detail.get('scan_time')}
扫描参数：{json.dumps(params, ensure_ascii=False)}

【板块概要】
{sector_text}

【股票明细】（制表符分隔：代码、名称、所属板块、grade、pct、squeeze、bw、score）
{stock_text}

请作为资深 A 股量化与技术面分析师，基于本次「布林带收缩策略」扫描结果完成：

1. 用 Chain-of-Thought 方式分步写出推理（至少 3 步）：先概括样本与数据质量 → 再解读板块轮动与布林带/收缩含义 → 再讨论风险与不确定性。
2. 仅在上述股票明细中出现过的标的里，选出至多 3 只「相对更值得持续跟踪」的标的（必须使用该表中的 6 位数字代码），每只需说明理由与单独的风险提示。
3. 输出**仅一段合法 JSON**（不要用 markdown 代码围栏），格式如下：
{{"cot_steps":[{{"title":"string","content":"string"}}],"recommendations":[{{"code":"6位数字","name":"","sector":"","reason":"","risk":""}}],"closing_note":"string"}}
若你认为不宜推荐任何标的，可将 recommendations 设为 []，并在 closing_note 中说明。"""

    system_msg = (
        '你只输出 JSON，不要输出 JSON 以外的任何文字。'
        '分析仅供研究参考，不构成投资建议，禁止给出具体买卖价位。'
    )

    try:
        options = CallOptions(temperature=0.35, max_tokens=3800)
        resp = get_client().call(user_prompt, system=system_msg, options=options)
        if not resp.success:
            return jsonify({'success': False, 'error': resp.error or 'LLM 调用失败'}), 500

        content = resp.content
        logger.info("[scan_ai_summary] provider=%s model=%s response_len=%d tokens=%d",
                    resp.provider, resp.model, len(content) if content else 0, resp.tokens_used)

        parsed = get_agent_registry().extract_json(content) if content else None
        valid_codes = _scan_valid_stock_codes(detail)

        if not parsed:
            out = {
                'cot_steps': [
                    {'title': '思考过程', 'content': (content or '')[:4000]}
                ],
                'recommendations': [],
                'closing_note': (content or '')[:1200] if content else '',
                'raw_text': (content or '')[:8000],
                'source': f'{resp.provider}_raw',
            }
            db.save_scan_ai_summary(scan_id, out)
            data = db.get_scan_ai_summary(scan_id)
            return jsonify({'success': True, 'data': data, 'cached': False})

        recs_in = parsed.get('recommendations') or []
        filtered = []
        for r in recs_in:
            if len(filtered) >= 3:
                break
            c = normalize_agent_stock_code(r.get('code'))
            if c in valid_codes:
                filtered.append({
                    'code': c,
                    'name': (r.get('name') or '')[:32],
                    'sector': (r.get('sector') or '')[:64],
                    'reason': (r.get('reason') or '')[:800],
                    'risk': (r.get('risk') or '')[:500],
                })

        cot = parsed.get('cot_steps') or []
        if not isinstance(cot, list):
            cot = []
        cot_clean = []
        for step in cot[:12]:
            if not isinstance(step, dict):
                continue
            tit = str(step.get('title') or '步骤')[:80]
            con = str(step.get('content') or '')[:2000]
            cot_clean.append({'title': tit, 'content': con})

        out = {
            'cot_steps': cot_clean,
            'recommendations': filtered,
            'closing_note': str(parsed.get('closing_note') or '')[:1200],
            'raw_text': None,
            'source': resp.provider,
        }
        db.save_scan_ai_summary(scan_id, out)
        data = db.get_scan_ai_summary(scan_id)
        return jsonify({'success': True, 'data': data, 'cached': False})
    except Exception as e:
        logger.exception('scan_ai_summary failed: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@strategy_bp.route('/api/strategy/factor/template', methods=['GET'])
def factor_prompt_template():
    """返回未注入的 Python 框架源码（与生成结果对齐）。"""
    return jsonify({
        'success': True,
        'data': {
            'code': FACTOR_CODE_TEMPLATE,
            'version': FACTOR_TEMPLATE_VERSION,
        },
    })


@strategy_bp.route('/api/strategy/factor/status', methods=['GET'])
def factor_prompt_status():
    """LLM 配置状态（供前端展示）"""
    client = get_client()
    return jsonify({
        'success': True,
        'connected': client.is_configured(),
        'model_display': '通义千问3.6-Plus' if client.is_configured() else None,
        'model_id': client.provider if client.is_configured() else None,
        'template_version': FACTOR_TEMPLATE_VERSION,
    })


@strategy_bp.route('/api/strategy/factor/generate', methods=['POST'])
def factor_prompt_generate():
    """
    根据自然语言指令调用 LLM，返回合并后的 factor_template.py 文本。
    非量化因子类请求由模型在 JSON 内标记为 rejected。
    """
    try:
        data = request.get_json(silent=True) or {}
        instruction = (data.get('instruction') or data.get('prompt') or '').strip()
    except Exception:
        instruction = ''

    if len(instruction) < 4:
        return jsonify({
            'success': False,
            'error': '请输入更具体的因子描述（至少 4 个字符）',
            'filtered': True,
        }), 400

    if not get_client().is_configured():
        return jsonify({
            'success': False,
            'error': 'LLM 服务未配置',
        }), 503

    system_msg = (
        '你是 A 股量化因子工程助手。你必须只输出一段合法 JSON（不要用 markdown 代码围栏），UTF-8，键为：\n'
        '  "intent": 字符串，取 "factor_development" 或 "rejected"\n'
        '  "reject_reason": 当 intent 为 rejected 时必填，中文一句话\n'
        '  "injected_code": 当 intent 为 factor_development 时必填，为 Python 源码字符串\n'
        '规则：\n'
        '- 若用户请求与股票因子、量价 alpha、技术指标（如均线/RSI/成交量衍生）等无关，intent 必须为 rejected。\n'
        '- injected_code 只写「逻辑注入区」内的代码：可使用已有变量 close_prices、volume（与行情长度对齐，可为 pandas Series 或 numpy 数组）；'
        '必须赋值 factor_values，形状与 close_prices 对齐（可为 Series、ndarray 或与之一致的标量广播）。\n'
        '- 如需 import，仅写在 injected_code 内；优先 numpy（np）与 pandas（pd）。\n'
        '- 不要重复 class 定义或 compute_factor 签名；不要包含「开始/结束逻辑注入」注释行。'
    )

    user_msg = f'用户因子指令：\n{instruction}'

    try:
        options = CallOptions(temperature=0.25, max_tokens=4096)
        resp = get_client().call(user_msg, system=system_msg, options=options)
        if not resp.success:
            return jsonify({'success': False, 'error': resp.error or 'LLM 调用失败'}), 500

        content = resp.content
        parsed = get_agent_registry().extract_json(content) if content else None

        if not isinstance(parsed, dict):
            return jsonify({
                'success': False,
                'error': '模型返回无法解析为 JSON，请换一句描述或稍后重试',
            }), 502

        intent = str(parsed.get('intent') or '').strip().lower()
        if intent == 'rejected':
            reason = str(parsed.get('reject_reason') or '该请求与因子开发无关，已过滤').strip()
            return jsonify({
                'success': False,
                'error': reason,
                'filtered': True,
                'intent': 'rejected',
            }), 422

        injected = str(parsed.get('injected_code') or '').strip()
        if not injected:
            return jsonify({
                'success': False,
                'error': '模型未返回 injected_code，请重试',
            }), 502

        merged = _merge_factor_injected_code(injected)

        return jsonify({
            'success': True,
            'data': {
                'code': merged,
                'template_version': FACTOR_TEMPLATE_VERSION,
                'intent': 'factor_development',
                'model': resp.model,
                'tokens_used': resp.tokens_used,
            },
        })
    except Exception as e:
        logger.exception('factor_prompt_generate failed: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


def _find_stock_in_scan_detail(detail: dict, code: str):
    """在单次扫描结果中查找股票；(stock_row, sector_name, sector_change) 或 None。"""
    from agent_prompts import normalize_agent_stock_code

    target = normalize_agent_stock_code(code)
    if not target:
        return None
    for sec_name, block in (detail.get('results') or {}).items():
        try:
            sec_chg = float(block.get('change') or 0)
        except (TypeError, ValueError):
            sec_chg = 0.0
        for s in block.get('stocks') or []:
            c = normalize_agent_stock_code(s.get('code'))
            if c == target:
                return (dict(s), sec_name, sec_chg)
    return None


def _normalize_stock_ai_parsed(parsed: dict) -> dict:
    """
    模型偶发把整段 JSON 当作字符串写进 summary，或仅 content 为合法 JSON 而外层错位。
    """
    from agent_prompts import extract_json_object_from_text

    if not isinstance(parsed, dict):
        return {}
    sm = parsed.get('summary')
    if isinstance(sm, str) and sm.strip().startswith('{'):
        inner = extract_json_object_from_text(sm)
        if isinstance(inner, dict):
            has_cot = isinstance(inner.get('cot_steps'), list) and len(inner.get('cot_steps') or []) > 0
            has_sum = bool(str(inner.get('summary') or '').strip())
            has_risk = bool(str(inner.get('risk_note') or '').strip())
            if has_cot or has_sum or has_risk:
                return inner
    return parsed


@strategy_bp.route('/api/scan/<int:scan_id>/stock-ai-analysis', methods=['POST'])
def scan_stock_ai_analysis(scan_id: int):
    """
    LLM：针对扫描内单只标的，结合布林带收缩相关指标与标签做简析（非投资建议）。
    不入库缓存，每次请求现算。
    """
    from agent_prompts import normalize_agent_stock_code

    detail = db.get_scan_detail(scan_id)
    if not detail:
        return jsonify({'success': False, 'error': '扫描记录不存在'}), 404

    body = request.get_json(silent=True) or {}
    raw_code = (body.get('code') or '').strip()
    if not raw_code:
        return jsonify({'success': False, 'error': '缺少股票代码'}), 400

    found = _find_stock_in_scan_detail(detail, raw_code)
    if not found:
        return jsonify({'success': False, 'error': '该股票不在本次扫描结果中'}), 404

    stock, sector_name, sector_change = found
    norm_code = normalize_agent_stock_code(stock.get('code')) or raw_code

    if not get_client().is_configured():
        return jsonify({'success': False, 'error': 'LLM 服务未配置'}), 503

    tags = stock.get('tags')
    if isinstance(tags, list):
        tag_str = '、'.join(str(t) for t in tags[:20] if t)
    else:
        tag_str = str(tags or '')

    stock_payload = {
        'code': norm_code,
        'name': stock.get('name', ''),
        'sector': sector_name,
        'sector_change_pct': round(sector_change, 2),
        'pct_change': stock.get('pct_change'),
        'grade': stock.get('grade', ''),
        'total_score': stock.get('total_score', stock.get('score')),
        'squeeze_days': stock.get('squeeze_days'),
        'bb_width_pct': stock.get('bb_width_pct', stock.get('bandwidth_pct', stock.get('bandwidth'))),
        'volume_ratio': stock.get('volume_ratio'),
        'is_leader': stock.get('is_leader'),
        'leader_rank': stock.get('leader_rank'),
        'tags': tag_str,
    }

    scan_params = detail.get('params') or {}
    user_prompt = f"""你正在辅助解读一次「布林带收缩策略」扫描中的单只股票（仅供研究参考，不构成投资建议）。

【扫描背景】
扫描时间：{detail.get('scan_time')}
扫描参数：{json.dumps(scan_params, ensure_ascii=False)}

【标的快照】（JSON）
{json.dumps(stock_payload, ensure_ascii=False)}

请完成：
1. 用 Chain-of-Thought 分步推理（至少 3 步）：先概括该标的在扫描中的技术位态（收缩天数、带宽、评分/等级）→ 再结合板块涨跌与标签含义 → 最后讨论风险与不确定性。
2. 输出**仅一段合法 JSON**（不要用 markdown 代码围栏），格式严格如下：
{{"cot_steps":[{{"title":"string","content":"string"}}],"summary":"用一段话给出非买卖价位的跟踪要点（不超过200字）","risk_note":"单独一段风险提示（不超过120字）"}}
禁止输出 JSON 以外的任何文字。"""

    system_msg = (
        '你只输出 JSON，不要输出 JSON 以外的任何文字。'
        '分析仅供研究参考，不构成投资建议，禁止给出具体买卖价位与仓位建议。'
    )

    try:
        options = CallOptions(temperature=0.2, max_tokens=2800)
        resp = get_client().call(user_prompt, system=system_msg, options=options)
        if not resp.success:
            return jsonify({'success': False, 'error': resp.error or 'LLM 调用失败'}), 500

        content = resp.content
        parsed = get_agent_registry().extract_json(content) if content else None
        if not parsed:
            parsed = get_agent_registry()._extract_json_object_from_text(content) if content else None
        if isinstance(parsed, dict):
            parsed = _normalize_stock_ai_parsed(parsed)

        if not parsed:
            out = {
                'cot_steps': [
                    {'title': '模型输出', 'content': (content or '无内容')[:4000]}
                ],
                'summary': (content or '')[:800],
                'risk_note': '',
                'source': f'{resp.provider}_raw',
            }
            return jsonify({'success': True, 'data': out})

        cot = parsed.get('cot_steps') or []
        if not isinstance(cot, list):
            cot = []
        cot_clean = []
        for step in cot[:12]:
            if not isinstance(step, dict):
                continue
            tit = str(step.get('title') or '步骤')[:80]
            con = str(step.get('content') or '')[:2000]
            cot_clean.append({'title': tit, 'content': con})

        out = {
            'cot_steps': cot_clean,
            'summary': str(parsed.get('summary') or '')[:600],
            'risk_note': str(parsed.get('risk_note') or '')[:400],
            'source': resp.provider,
        }
        return jsonify({'success': True, 'data': out})
    except Exception as e:
        logger.exception('scan_stock_ai_analysis failed: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@strategy_bp.route('/api/scan/<int:scan_id>', methods=['GET'])
def get_scan_detail(scan_id: int):
    """获取指定扫描的详细结果"""
    scan_detail = db.get_scan_detail(scan_id)

    if not scan_detail:
        return jsonify({
            'success': False,
            'error': '扫描记录不存在'
        }), 404

    return jsonify({
        'success': True,
        'data': scan_detail
    })


@strategy_bp.route('/api/scan/<int:scan_id>', methods=['DELETE'])
def delete_scan(scan_id: int):
    """删除指定扫描记录"""
    global scan_status
    
    if scan_status['is_scanning'] and scan_status.get('scan_id') == scan_id:
        return jsonify({
            'success': False,
            'error': '无法删除正在进行的扫描'
        }), 400
    
    success = db.delete_scan(scan_id)

    if success:
        invalidate('scan/history')
        return jsonify({
            'success': True,
            'message': '删除成功'
        })
    else:
        return jsonify({
            'success': False,
            'error': '扫描记录不存在'
        }), 404


@strategy_bp.route('/api/stock/<code>')
def get_stock_detail(code: str):
    """获取单只股票详情"""
    global last_api_request_time
    last_api_request_time = 0
    API_REQUEST_INTERVAL = 1.0

    # 读取并验证 interval 参数
    interval_arg = request.args.get('interval', 'daily')
    if interval_arg not in ('daily', 'weekly', 'monthly'):
        interval_arg = 'daily'

    from utils.ths_crawler import get_stock_kline_sina

    if not code or not code.isdigit() or len(code) != 6:
        return jsonify({'success': False, 'error': '无效的股票代码'})

    try:
        # 缓存暂不支持 interval 分开存储，共用现有缓存
        cached_data = db.get_kline_cache(code)
        if cached_data and 'vp_obv' in cached_data:
            logger.info(f"[CACHE HIT] 股票 {code} 使用缓存数据")
            return jsonify({'success': True, 'data': cached_data, 'cached': True})

        if cached_data and 'vp_obv' not in cached_data:
            logger.info(f"[CACHE STALE] 股票 {code} 缓存缺少量能画像数据，重新获取")

        logger.info(f"[CACHE MISS] 股票 {code} 从新浪API获取数据")

        current_time = time.time()
        time_since_last = current_time - last_api_request_time
        if time_since_last < API_REQUEST_INTERVAL:
            time.sleep(API_REQUEST_INTERVAL - time_since_last)

        last_api_request_time = time.time()

        from bollinger_squeeze_strategy import BollingerSqueezeStrategy

        df = get_stock_kline_sina(code, days=120, interval=interval_arg)

        if df is None or df.empty:
            return jsonify({'success': False, 'error': '数据获取失败，请稍后重试'})

        strategy = BollingerSqueezeStrategy()
        df = strategy.calculate_bollinger_bands(df)
        df = strategy.calculate_squeeze_signal(df)
        df = strategy.calculate_trend_indicators(df)
        df = strategy.calculate_volume_profile(df)

        data = prepare_kline_data(df)

        if data is None:
            return jsonify({'success': False, 'error': '数据处理失败'})

        db.save_kline_cache(code, data)
        logger.info(f"[CACHE SAVE] 股票 {code} 数据已缓存")

        # 同时写入 Raw 缓存（TV 图表直读，不再重抓）
        # kline_cache 里 candles/volumes 的 time 字段就是日期字符串
        if data.get('candles'):
            raw_bars = []
            for c in data['candles']:
                raw_bars.append({
                    'date': c.get('time', ''),
                    'open':  c.get('open'),
                    'high':  c.get('high'),
                    'low':   c.get('low'),
                    'close': c.get('close'),
                    'volume': 0.0,
                })
            if raw_bars:
                db.save_kline_raw_cache(code, _pd.DataFrame(raw_bars))

        return jsonify({'success': True, 'data': data, 'cached': False})

    except Exception as e:
        logger.error(f"获取股票 {code} 详情失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ==================== 自选股 API ====================

@strategy_bp.route('/api/watchlist')
def get_watchlist():
    """获取自选列表"""
    try:
        stocks = db.get_watchlist()
        return jsonify({'success': True, 'data': stocks})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@strategy_bp.route('/api/cache/clear', methods=['POST'])
def clear_all_cache():
    """清空所有缓存数据"""
    try:
        results = db.clear_all_cache()
        return jsonify({'success': True, 'data': results, 'message': '缓存已清空'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@strategy_bp.route('/api/watchlist/enriched')
def get_watchlist_enriched():
    """
    获取自选列表（含实时行情 + 迷你K线）
    并行查询行情数据，返回 close/pct_change/amount/vol 等字段
    Redis 缓存 15s（外部 API 调用较重）
    """
    # 缓存 key 包含股票代码列表，添加/删除自选时自动失效
    cache_key = 'watchlist/enriched'
    hit = get(cache_key)
    if hit is not None:
        return jsonify({'success': True, 'data': hit})

    try:
        stocks = db.get_watchlist()
        if not stocks:
            return jsonify({'success': True, 'data': []})

        codes = []
        for s in stocks:
            code = s.get('stock_code') or s.get('code') or ''
            codes.append(code)

        # 东方财富批量行情接口（优先），失败后用新浪备选
        secids = []
        for c in codes:
            m = "1" if c.startswith(("6", "9")) else "0"
            secids.append(f"{m}.{c}")
        price_map = {}
        try:
            resp = requests.get(
                "http://push2.eastmoney.com/api/qt/ulist/get",
                params={
                    "fltt": "2",
                    "secids": ",".join(secids),
                    "fields": "f2,f3,f4,f5,f6,f7,f8,f10,f12,f14,f15,f16,f17,f18,f20,f62",
                },
                timeout=8,
            )
            raw = resp.text
            try:
                items = json.loads(raw).get('data', {}).get('diff', [])
            except Exception:
                items = []
            for item in items:
                code = str(item.get('f12', ''))
                cap = _eastmoney_mkt_cap_yuan(item)
                price_map[code] = {
                    'close':      item.get('f2'),
                    'pct_change': item.get('f3'),
                    'change':     item.get('f4'),
                    'volume':     item.get('f5'),
                    'amount':     item.get('f6'),
                    'high':       item.get('f15'),
                    'low':        item.get('f16'),
                    'open':       item.get('f17'),
                    'prev_close': item.get('f18'),
                    'turnover':   item.get('f8'),
                    'qty_ratio':  item.get('f10'),
                    'mkt_cap':    cap,
                }
        except Exception as e:
            logger.warning(f"东方财富批量行情获取失败: {e}")

        # 备选：新浪实时行情（分批请求，每批20只）
        if not price_map:
            try:
                for batch in [codes[i:i+20] for i in range(0, len(codes), 20)]:
                    sina_codes = ",".join(
                        f"{'sh' if c.startswith(('6','9')) else 'sz'}{c}" for c in batch
                    )
                    resp = requests.get(
                        f"http://hq.sinajs.cn/list={sina_codes}",
                        headers={"Referer": "http://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"},
                        timeout=8,
                    )
                    if resp.status_code == 200:
                        for line in resp.text.strip().split("\n"):
                            if "=" not in line:
                                continue
                            sym = line.split('="')[0].split("_")[-1]
                            raw = line.split('="')[1].rstrip('";\r\n')
                            parts = raw.split(",")
                            if len(parts) < 32:
                                continue
                            code = sym[2:] if sym.startswith(("sh", "sz")) else sym
                            prev_close = float(parts[2]) if parts[2] else 0
                            close_price = float(parts[3]) if parts[3] else 0
                            change = round(close_price - prev_close, 3) if prev_close else 0
                            pct_change = round((change / prev_close) * 100, 2) if prev_close else 0
                            price_map[code] = {
                                'close': close_price,
                                'pct_change': pct_change,
                                'change': change,
                                'volume': float(parts[8]) if parts[8] else 0,
                                'amount': float(parts[9]) if parts[9] else 0,
                                'high': float(parts[4]) if parts[4] else 0,
                                'low': float(parts[5]) if parts[5] else 0,
                                'open': float(parts[1]) if parts[1] else 0,
                                'prev_close': prev_close,
                                'turnover': 0,
                                'qty_ratio': None,
                                'mkt_cap': None,
                            }
            except Exception as e2:
                logger.warning(f"新浪批量行情获取失败: {e2}")

        # 迷你K线（最近10日收盘价，用于缩略图）
        mini_kline_map = {}
        try:
            from utils.ths_crawler import get_stock_kline_sina
            import pandas as pd
            for c in codes:
                try:
                    df = get_stock_kline_sina(c, days=15)
                    if df is not None and len(df) > 0:
                        closes = df['close'].astype(str).tolist()[-10:]
                        dates = pd.to_datetime(df['date']).astype(str).tolist()[-10:]
                        mini_kline_map[c] = {'dates': dates, 'closes': closes}
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"迷你K线获取失败: {e}")

        result = []
        for s in stocks:
            code = s.get('stock_code') or s.get('code') or ''
            p = price_map.get(code, {})
            mk = mini_kline_map.get(code, {})
            result.append({
                **s,
                'code':        code,
                'name':        s.get('stock_name') or s.get('name') or '',
                'sector':      s.get('sector_name') or s.get('sector') or '',
                'close':       p.get('close'),
                'pct_change':  p.get('pct_change'),
                'change_amt':   p.get('change'),
                'volume':       p.get('volume'),
                'amount':       p.get('amount'),
                'high':         p.get('high'),
                'low':          p.get('low'),
                'open':         p.get('open'),
                'prev_close':   p.get('prev_close'),
                'turnover':     p.get('turnover'),
                'qty_ratio':    p.get('qty_ratio'),
                'mkt_cap':      p.get('mkt_cap'),
                'mini_kline':   mk,
            })

        _cache_set(cache_key, result, ttl=15)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"自选股 enriched 加载失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@strategy_bp.route('/api/watchlist/add', methods=['POST'])
def add_to_watchlist():
    """添加股票到自选"""
    try:
        data = request.json
        if not data or not data.get('code') or not data.get('name'):
            return jsonify({'success': False, 'error': '缺少股票代码或名称'})
        
        success = db.add_to_watchlist(
            stock_code=data['code'],
            stock_name=data['name'],
            sector_name=data.get('sector'),
            note=data.get('note')
        )
        
        if success:
            invalidate('watchlist/')
            return jsonify({'success': True, 'message': '已添加到自选'})
        else:
            return jsonify({'success': False, 'error': '添加失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@strategy_bp.route('/api/watchlist/remove', methods=['POST'])
def remove_from_watchlist():
    """从自选移除股票"""
    try:
        data = request.json
        if not data or not data.get('code'):
            return jsonify({'success': False, 'error': '缺少股票代码'})
        
        success = db.remove_from_watchlist(data['code'])
        
        if success:
            invalidate('watchlist/')
            return jsonify({'success': True, 'message': '已从自选移除'})
        else:
            return jsonify({'success': False, 'error': '移除失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@strategy_bp.route('/api/watchlist/check/<code>')
def check_watchlist(code: str):
    """检查股票是否在自选中"""
    try:
        in_watchlist = db.is_in_watchlist(code)
        return jsonify({'success': True, 'in_watchlist': in_watchlist})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@strategy_bp.route('/api/watchlist/strategy/catalog')
def watchlist_strategy_catalog():
    """自选技术指标策略列表（TA-Lib 优先，无则 pandas 近似）。"""
    try:
        from utils.watchlist_talib_strategies import get_catalog, talib_status
        return jsonify({
            'success': True,
            'data': {
                'strategies': get_catalog(),
                'engine': talib_status(),
            },
        })
    except Exception as e:
        logger.exception('watchlist strategy catalog')
        return jsonify({'success': False, 'error': str(e)}), 500


@strategy_bp.route('/api/watchlist/strategy/run', methods=['POST'])
def watchlist_strategy_run():
    """
    对当前自选列表逐只拉日线并运行指定 TA 策略（仅自选）。
    body: { "strategy_id": "rsi_extreme" } 或 { "strategy_ids": ["rsi_extreme", "macd_turn"] }
    """
    try:
        payload = request.get_json(silent=True) or {}
        raw_ids = payload.get('strategy_ids')
        strategy_id = payload.get('strategy_id') or payload.get('id')
        if isinstance(raw_ids, list) and raw_ids:
            strategy_ids = [str(x).strip() for x in raw_ids if x is not None and str(x).strip()]
        elif strategy_id and isinstance(strategy_id, str):
            strategy_ids = [strategy_id.strip()]
        else:
            return jsonify({'success': False, 'error': '缺少 strategy_id 或 strategy_ids'}), 400

        if not strategy_ids:
            return jsonify({'success': False, 'error': 'strategy_ids 为空'}), 400

        stocks = db.get_watchlist()
        if not stocks:
            from utils.watchlist_talib_strategies import talib_status
            return jsonify({
                'success': True,
                'data': {
                    'strategy_id': strategy_ids[0],
                    'strategy_ids': strategy_ids,
                    'strategy_name': strategy_ids[0],
                    'talib': talib_status(),
                    'count': 0,
                    'items': [],
                    'hint': '自选为空',
                },
            })

        codes = []
        for s in stocks:
            code = str(s.get('stock_code') or s.get('code') or '').strip()
            if code.isdigit() and len(code) == 6:
                codes.append(code)

        if not codes:
            return jsonify({
                'success': True,
                'data': {
                    'strategy_id': strategy_ids[0],
                    'strategy_ids': strategy_ids,
                    'strategy_name': strategy_ids[0],
                    'count': 0,
                    'items': [],
                    'hint': '自选代码格式无效',
                },
            })

        # 延迟导入：避免启动时失败
        import signal
        from concurrent.futures import ProcessPoolExecutor, as_completed
        from utils.watchlist_talib_strategies import (
            run_multi_strategies_on_watchlist,
            run_strategy_on_watchlist,
        )

        # 拉 K 线（进程隔离，避免 mini_racer 多线程崩溃）
        from utils.ths_crawler import get_stock_kline_sina
        _KLINE_TIMEOUT = 15  # 秒/只

        def _one(c: str):
            try:
                return _fetch_kline_worker(c, 120, 20)
            except Exception as ex:
                logger.warning('watchlist kline %s: %s', c, ex)
                return c, None

        dfs = {}
        with ProcessPoolExecutor(max_workers=min(6, len(codes))) as pool:
            futures = {pool.submit(_one, c): c for c in codes}
            for fut in as_completed(futures):
                try:
                    c, df = fut.result()
                    dfs[c] = df
                except Exception as ex:
                    logger.warning('watchlist process: %s', ex)

        def fetch_df(code: str):
            return dfs.get(code)

        # 在主线程执行策略，避免多线程 pickle 问题
        try:
            if len(strategy_ids) == 1:
                result = run_strategy_on_watchlist(strategy_ids[0], stocks, fetch_df)
            else:
                result = run_multi_strategies_on_watchlist(strategy_ids, stocks, fetch_df)
        except Exception as ex:
            logger.exception('run_strategy_on_watchlist failed')
            return jsonify({'success': False, 'error': f'策略计算异常: {ex}'}), 500

        if result.get('error'):
            return jsonify({'success': False, 'error': result['error']}), 400
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.exception('watchlist strategy run')
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== 股票搜索 / 同步 / 行情 API ====================

@strategy_bp.route('/api/stocks/search')
def search_stocks():
    """
    模糊搜索股票（支持代码、名称、拼音首字母）。
    前端调用: /api/stocks/search?q=关键词&limit=20
    """
    try:
        keyword = request.args.get('q', '').strip()
        limit = max(1, min(50, request.args.get('limit', 20, type=int)))

        if not keyword:
            return jsonify({'success': True, 'data': [], 'stock_count': db.get_all_stocks_count()})

        results = db.search_stocks(keyword, limit=limit)
        total = db.get_all_stocks_count()
        needs_sync = total == 0

        return jsonify({
            'success': True,
            'data': results,
            'stock_count': total,
            'needs_sync': needs_sync,
        })
    except Exception as e:
        logger.error(f"股票搜索失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@strategy_bp.route('/api/stocks/status')
def stocks_status():
    """
    获取股票数据库状态。
    返回数据库中股票数量，以及是否需要同步。
    """
    try:
        total = db.get_all_stocks_count()
        return jsonify({
            'success': True,
            'count': total,
            'needs_sync': total == 0,
        })
    except Exception as e:
        logger.error(f"获取股票状态失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@strategy_bp.route('/api/stocks/sync', methods=['POST'])
def sync_stocks():
    """
    从 akshare 同步全量 A 股股票基础数据到本地数据库。
    同步完成后前端可以正常搜索股票。
    后台运行，不阻塞请求。
    """
    import threading as _t
    import akshare as _ak
    import pandas as _pd

    def _do_sync():
        logger.info("[StockSync] 开始同步股票数据...")
        saved = 0
        try:
            # 沪深京A股列表（不需要参数）
            try:
                df_all = _ak.stock_info_a_code_name()
                if df_all is not None and not df_all.empty:
                    records = []
                    for _, row in df_all.iterrows():
                        code = str(row.get('code', '') or row.get('证券代码', '')).strip()
                        name = str(row.get('name', '') or row.get('证券简称', '')).strip()
                        if code and name and len(code) == 6 and code.isdigit():
                            mtype = 'sh' if code.startswith(('6', '9')) else 'sz' if code.startswith(('0', '3')) else 'bj'
                            records.append({
                                'code': code,
                                'name': name,
                                'market_type': mtype,
                            })
                    if records:
                        saved = db.upsert_stocks_batch(records)
                        logger.info(f"[StockSync] 写入 {len(records)} 条股票记录")
            except Exception as e:
                logger.warning(f"[StockSync] 同步失败: {e}")
                import traceback
                traceback.print_exc()

            # 如果上述接口失败，使用备用方案
            if saved == 0:
                try:
                    df_all = _ak.stock_zh_a_spot_em()
                    if df_all is not None and not df_all.empty:
                        code_col = next((c for c in df_all.columns if '代码' in c), None)
                        name_col = next((c for c in df_all.columns if '名称' in c), None)
                        if code_col and name_col:
                            records = []
                            for _, row in df_all.iterrows():
                                code = str(row[code_col]).strip()
                                name = str(row[name_col]).strip()
                                if code and name and len(code) == 6 and code.isdigit():
                                    mtype = 'sh' if code.startswith(('6', '9')) else 'sz' if code.startswith(('0', '3')) else 'bj'
                                    records.append({'code': code, 'name': name, 'market_type': mtype})
                            if records:
                                saved = db.upsert_stocks_batch(records)
                                logger.info(f"[StockSync] 备用方案写入 {len(records)} 条股票记录")
                except Exception as e:
                    logger.warning(f"[StockSync] 备用方案（全市场快照）失败: {e}")

            logger.info(f"[StockSync] 同步完成，共写入 {saved} 条股票记录")

        except Exception as e:
            logger.error(f"[StockSync] 同步过程异常: {e}")
            import traceback
            traceback.print_exc()

    # 后台线程执行，避免阻塞 HTTP 请求
    t = _t.Thread(target=_do_sync, daemon=True)
    t.start()

    try:
        total = db.get_all_stocks_count()
    except Exception:
        total = 0

    return jsonify({
        'success': True,
        'message': '同步任务已启动',
        'total': total,
    })


@strategy_bp.route('/api/stocks/quotes', methods=['POST'])
def get_stocks_quotes():
    """
    批量获取多只股票的实时行情。
    用于 AI 分析完成后补充缺失的 price / changePct 数据。

    请求体: { "codes": ["600501", "300274", ...] }
    返回:   { "success": True, "data": { "600501": {close, pct_change, ...}, ... } }
    """
    try:
        data = request.get_json()
        codes = data.get('codes', [])
        if not codes:
            return jsonify({'success': True, 'data': {}})

        codes = [str(c).strip() for c in codes if str(c).strip()]
        results = {}
        for code in codes:
            result = _get_quote_sina(code)
            if result:
                results[code] = result
            else:
                mkt = "1" if code.startswith(("6", "9")) else "0"
                try:
                    resp = requests.get(
                        "http://push2.eastmoney.com/api/qt/ulist/get",
                        params={
                            "fltt": "2", "secids": f"{mkt}.{code}",
                            "fields": "f2,f3,f4,f5,f6,f8,f10,f12,f14,f15,f16,f17,f18,f20,f62",
                        },
                        timeout=8,
                    )
                    items = resp.json().get('data', {}).get('diff', [])
                    if items:
                        item = items[0]
                        results[code] = {
                            'code': code, 'name': item.get('f14', ''),
                            'close': item.get('f2'), 'pct_change': item.get('f3'),
                            'change': item.get('f4'), 'volume': item.get('f5'),
                            'amount': item.get('f6'), 'turnover': item.get('f8'),
                            'qty_ratio': item.get('f10'), 'high': item.get('f15'),
                            'low': item.get('f16'), 'open': item.get('f17'),
                            'prev_close': item.get('f18'),
                        }
                except Exception:
                    pass

        return jsonify({'success': True, 'data': results})
    except Exception as e:
        logger.error(f"批量获取行情失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@strategy_bp.route('/api/stock/<code>/quote')
def get_stock_quote(code: str):
    """
    获取单只股票实时行情。
    优先使用新浪接口（更稳定），东方财富作为备选。
    返回字段与前端 Watchlist.vue 期望一致。
    """
    try:
        if not code or not code.isdigit() or len(code) != 6:
            return jsonify({'success': False, 'error': '无效股票代码'}), 400

        result = _get_quote_with_fallback(code)
        if result:
            return jsonify({'success': True, **result})

        return jsonify({'success': False, 'error': '未找到行情数据'}), 404

    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': '请求超时，请稍后重试'}), 504
    except Exception as e:
        logger.error(f"获取股票 {code} 行情失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _get_quote_sina(code: str) -> Optional[dict]:
    """
    使用新浪实时行情接口获取股票数据。
    返回格式: {code, name, close, pct_change, change, volume, amount,
               turnover, qty_ratio, high, low, open, prev_close, mkt_cap}
    """
    prefix = "sh" if code.startswith(("6", "9")) else "sz"
    try:
        resp = requests.get(
            f"http://hq.sinajs.cn/list={prefix}{code}",
            headers={
                "Referer": "http://finance.sina.com.cn",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=8,
        )
        if resp.status_code != 200:
            return None
        text = resp.text.strip()
        if "=" not in text or text.count(",") < 30:
            return None

        raw = text.split('="')[1].rstrip('";')
        parts = raw.split(",")
        if len(parts) < 32:
            return None

        def _f(val: str) -> Optional[float]:
            try:
                v = float(val)
                return None if v == 0 else v
            except Exception:
                return None

        name = parts[0]
        prev_close = _f(parts[2])   # 昨收
        open_price = _f(parts[1])   # 今开
        close_price = _f(parts[3])  # 最新价
        high_price = _f(parts[4])   # 最高
        low_price = _f(parts[5])    # 最低
        volume = float(parts[8]) if parts[8] else 0   # 成交量（手）
        amount = float(parts[9]) if parts[9] else 0   # 成交额（元）
        date_str = parts[30] if len(parts) > 30 else ""
        time_str = parts[31] if len(parts) > 31 else ""

        pct_change = 0.0
        change = 0.0
        if prev_close and close_price:
            change = round(close_price - prev_close, 3)
            pct_change = round((change / prev_close) * 100, 2)

        turnover = 0.0
        qty_ratio = None
        mkt_cap = None

        return {
            "code": code,
            "name": name,
            "close": close_price,
            "pct_change": pct_change,
            "change": change,
            "volume": volume,
            "amount": amount,
            "turnover": turnover,
            "qty_ratio": qty_ratio,
            "high": high_price,
            "low": low_price,
            "open": open_price,
            "prev_close": prev_close,
            "mkt_cap": mkt_cap,
        }
    except Exception:
        return None


def _get_quote_with_fallback(code: str) -> Optional[dict]:
    """优先新浪，失败后降级东方财富。"""
    result = _get_quote_sina(code)
    if result:
        return result

    mkt = "1" if code.startswith(("6", "9")) else "0"
    try:
        resp = requests.get(
            "http://push2.eastmoney.com/api/qt/ulist/get",
            params={
                "fltt": "2",
                "secids": f"{mkt}.{code}",
                "fields": "f2,f3,f4,f5,f6,f8,f10,f12,f14,f15,f16,f17,f18,f20,f62",
            },
            timeout=8,
        )
        items = resp.json().get('data', {}).get('diff', [])
        if not items:
            return None
        item = items[0]
        return {
            'code': code,
            'name': item.get('f14', ''),
            'close': item.get('f2'),
            'pct_change': item.get('f3'),
            'change': item.get('f4'),
            'volume': item.get('f5'),
            'amount': item.get('f6'),
            'turnover': item.get('f8'),
            'qty_ratio': item.get('f10'),
            'high': item.get('f15'),
            'low': item.get('f16'),
            'open': item.get('f17'),
            'prev_close': item.get('f18'),
            'mkt_cap': _eastmoney_mkt_cap_yuan(item),
        }
    except Exception:
        return None


def _enrich_stocks_realtime(structured: dict) -> None:
    """
    批量获取推荐股票的实时行情，并回填到 structured 中。
    对扫描型推荐（如北京炒家的可买候选）会强制刷新，避免沿用旧扫描快照。
    """
    target_groups = []

    recs = structured.get('recommendedStocks', []) or []
    if recs:
        target_groups.append(recs)

    execution = structured.get('personaExecution') or {}
    actionables = execution.get('actionableCandidates', []) or []
    board_candidates = execution.get('boardCandidates', []) or []
    if actionables:
        target_groups.append(actionables)
    if board_candidates:
        target_groups.append(board_candidates)

    if not target_groups:
        return

    # 收集需要补调的代码
    codes_to_fetch = []
    code_rows = {}
    for rows in target_groups:
        for rec in rows:
            code = str(rec.get('code') or '').strip()
            if len(code) != 6 or not code.isdigit():
                continue
            force_refresh = bool(
                rec.get('forceRealtimeQuote')
                or rec.get('actionSource') == 'scan'
                or rec.get('boardType') == '未上板'
            )
            price = rec.get('price')
            chg = rec.get('changePct') or rec.get('chg_pct') or rec.get('change_pct')
            need_fetch = force_refresh or price in (None, '', 0) or chg in (None, '', 0)
            if need_fetch and code not in codes_to_fetch:
                codes_to_fetch.append(code)
            if need_fetch:
                code_rows.setdefault(code, []).append((rec, force_refresh))

    if not codes_to_fetch:
        return

    # 批量查询（新浪优先，逐个降级东方财富）
    for code in codes_to_fetch:
        q = _get_quote_with_fallback(code)

        if q and q.get('close'):
            for rec, force_refresh in code_rows.get(code, []):
                if force_refresh or rec.get('price') in (None, '', 0):
                    rec['price'] = q['close']
                if force_refresh or rec.get('changePct') in (None, '', 0) or rec.get('chg_pct') in (None, '', 0):
                    rec['changePct'] = q['pct_change']
                # 如果后端没有 name 但行情有，也补上
                if not rec.get('name') and q.get('name'):
                    rec['name'] = q['name']


# ══════════════════════════════════════════════════════════════════════════════
# Agent 分析系统（统一使用 utils.llm 模块）
# ══════════════════════════════════════════════════════════════════════════════
# 以下内容已迁移至 utils/llm/ 模块：
#   - LLM 配置常量（LLM_PROVIDER / DASHSCOPE_API_KEY 等）→ utils.llm.client
#   - LLM 调用函数（_llm_invoke）→ utils.llm.client.LLMClient
#   - AgentProfile 数据结构 → utils.llm.agents.AgentRegistry
#   - Agent 配置字典（AGENT_PROFILES）→ utils.llm.agents.AgentRegistry._agents
# ══════════════════════════════════════════════════════════════════════════════

from utils.llm import get_client, get_agent_registry, CallOptions

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


# ── 市场数据获取 ────────────────────────────────────────────────────────────

def get_market_snapshot() -> Dict[str, Any]:
    """获取当前市场快照，用于填充 Prompt"""
    try:
        import akshare as ak
        df = ak.stock_zh_index_spot_em()
        if df is not None and not df.empty:
            sh = df[df['名称'] == '上证指数']
            if not sh.empty:
                change = float(sh.iloc[0].get('涨跌幅', 0) or 0)
            else:
                change = 0.0
        else:
            change = 0.0
    except Exception:
        change = 0.0

    # 情绪判断
    if change >= 2:
        sentiment = '极度亢奋'
    elif change >= 1:
        sentiment = '强势看多'
    elif change >= 0:
        sentiment = '偏乐观'
    elif change >= -1:
        sentiment = '偏谨慎'
    elif change >= -2:
        sentiment = '弱势震荡'
    else:
        sentiment = '恐慌情绪'

    # 尝试从 Redis 获取今日热门题材数据
    hot_themes_str = ''
    top_stocks_str = ''
    try:
        cached = get('ticai/all')
        if cached:
            themes = cached.get('data', {}) if isinstance(cached, dict) else cached
            if isinstance(themes, dict):
                lines = []
                for name, data in list(themes.items())[:5]:
                    info = data.get('info', {})
                    stocks = data.get('stocks', [])[:3]
                    chg = info.get('change_pct', 0)
                    lines.append(f"- {name}（涨幅{chg:+.2f}%）")
                    for s in stocks:
                        lines.append(f"  · {s.get('name','')}({s.get('code','')}): {s.get('change_pct',0):+.2f}%")
                hot_themes_str = '\n'.join(lines) if lines else '暂无数据'
            else:
                hot_themes_str = '暂无数据'
        else:
            hot_themes_str = '暂无数据'
    except Exception:
        hot_themes_str = '暂无数据'

    try:
        from utils.ths_crawler import get_ths_industry_list
        df_ind = get_ths_industry_list()
        if df_ind is not None and not df_ind.empty:
            rows = []
            for _, r in df_ind.head(10).iterrows():
                rows.append(f"- {r['板块']}: {r['涨跌幅']:+.2f}% | 领涨: {r.get('领涨股','')}")
            top_stocks_str = '\n'.join(rows)
        else:
            top_stocks_str = '暂无数据'
    except Exception:
        top_stocks_str = '暂无数据'

    # 统计涨停家数（估算）
    try:
        import akshare as ak
        df_zt = ak.stock_zt_pool_em(date=datetime.now().strftime('%Y%m%d'))
        limit_up_count = len(df_zt) if df_zt is not None else 50
    except Exception:
        limit_up_count = 50

    return {
        'market_change': change,
        'sentiment': sentiment,
        'limit_up_count': limit_up_count,
        'break_rate': '18',
        'hot_themes': hot_themes_str,
        'top_stocks': top_stocks_str,
        'sector_rotation': '主线清晰，题材与价值轮动' if change >= 0 else '防御板块占优，资金观望',
        'top_inflow_sectors': '半导体、锂电池、新能源车',
        'top_outflow_sectors': '房地产、银行',
        'low_pe_sectors': '银行、电力、基建',
        'oversold_sectors': '医药生物、消费电子',
        'ma_system': '5/10/20日均线多头排列' if change >= 0 else '均线系统走弱',
        'trend_state': '上升趋势' if change >= 0 else '下降趋势',
        'bb_state': '布林带开口收窄，蓄势突破' if abs(change) < 1 else '布林带上轨压制' if change < 0 else '突破布林上轨',
        'macd_signal': 'MACD 红柱扩大，强势信号' if change >= 0 else 'MACD 绿柱，空头信号',
        'rsi_value': 'RSI 65，偏强区域' if change >= 0 else 'RSI 42，偏弱区域',
        'volume_state': '量能温和放大' if change >= 0 else '量能萎缩，观望情绪浓厚',
    }


# ── Prompt 渲染（适配旧模板格式）───────────────────────────────────────────

def render_prompt(profile: Dict, market: Dict[str, Any]) -> str:
    """将市场数据填充到 Agent 的 Prompt 模板"""
    # profile 是字典，字段名是 user_prompt_template（下划线，不是 tpl）
    tpl = profile.get('user_prompt_template', '') or profile.get('user_prompt_tpl', '')
    for key, val in market.items():
        placeholder = '{' + key + '}'
        tpl = tpl.replace(placeholder, str(val))
    return tpl


# ── 单个 Agent 分析 ─────────────────────────────────────────────────────────

def analyze_single_agent(agent_id: str) -> Dict[str, Any]:
    """调用 LLM 执行单个 Agent 的策略分析"""

    # ── 特殊处理：jun（钧哥）使用 JunGeTrader ──────────────────────────────
    if agent_id == 'jun':
        try:
            from junge_trader import JunGeTrader
            trader = JunGeTrader(use_ai=True)
            scan_result = trader.run_daily_scan(top_sectors=5, enhance=True)

            ai_result = scan_result.get('agentResult')
            if ai_result and ai_result.get('success'):
                structured = ai_result.get('structured', {})
                return {
                    'agent_id': 'jun',
                    'agent_name': '钧哥天下无双',
                    'name_brand': '钧哥天下无双',
                    'role_subtitle': '龙头战法',
                    'avatar_url': 'https://lh3.googleusercontent.com/aida-public/AB6AXuD97zD2NIGTCO_1tiXq1wsbA98aL5lltkwfWvGuW5ykcn7zacGqWOfQaC0Cgqq8Y70ssQbZDu4WTh34HYBodcl31NA-stzpx7g9dxTWCMuzM7s7gcIOeZVI8i8nHPZnB0F4J3ToG2bh9x5rvE7Qe3qAnETQRHznWRcVuYltPv923yduEQvww9hwsCd_YcKQjJrZK_VVNT5V0-w_9fQ5GDMZ9eGfWPxUPX4PFFDFtZaCN0EpwpuQSgMG_xOxIR3Btmz_rneBA88VIGp0',
                    'success': True,
                    'raw_response': ai_result.get('raw_response', ''),
                    'structured': structured,
                    'analysis': ai_result.get('analysis', ''),
                    'tokens_used': ai_result.get('tokens_used', 0),
                    '_junGeExtra': {
                        'scanTime': scan_result.get('scanTime'),
                        'elapsedSeconds': scan_result.get('elapsedSeconds'),
                        'scanMode': scan_result.get('scanMode'),
                        'market': scan_result.get('market'),
                        'hotSectors': scan_result.get('hotSectors'),
                        'stats': scan_result.get('stats'),
                        'recommendations': scan_result.get('recommendations'),
                        'candidates': scan_result.get('candidates'),
                        'summary': scan_result.get('summary'),
                    },
                }
            else:
                return {
                    'agent_id': 'jun',
                    'agent_name': '钧哥天下无双',
                    'name_brand': '钧哥天下无双',
                    'role_subtitle': '龙头战法',
                    'avatar_url': 'https://lh3.googleusercontent.com/aida-public/AB6AXuD97zD2NIGTCO_1tiXq1wsbA98aL5lltkwfWvGuW5ykcn7zacGqWOfQaC0Cgqq8Y70ssQbZDu4WTh34HYBodcl31NA-stzpx7g9dxTWCMuzM7s7gcIOeZVI8i8nHPZnB0F4J3ToG2bh9x5rvE7Qe3qAnETQRHznWRcVuYltPv923yduEQvww9hwsCd_YcKQjJrZK_VVNT5V0-w_9fQ5GDMZ9eGfWPxUPX4PFFDFtZaCN0EpwpuQSgMG_xOxIR3Btmz_rneBA88VIGp0',
                    'success': True,
                    'raw_response': '',
                    'structured': {
                        'agentId': 'jun',
                        'agentName': '钧哥天下无双',
                        'stance': 'bull',
                        'confidence': 60,
                        'marketCommentary': '布林带收缩策略扫描完成，请查看推荐股票',
                        'positionAdvice': '关注S/A级布林带收缩标的，止损设置5%',
                        'riskWarning': '市场波动，注意止损纪律',
                        'recommendedStocks': [],
                    },
                    'analysis': scan_result.get('summary', '扫描完成'),
                    'tokens_used': 0,
                    '_junGeExtra': {
                        'scanTime': scan_result.get('scanTime'),
                        'elapsedSeconds': scan_result.get('elapsedSeconds'),
                        'scanMode': scan_result.get('scanMode'),
                        'market': scan_result.get('market'),
                        'hotSectors': scan_result.get('hotSectors'),
                        'stats': scan_result.get('stats'),
                        'recommendations': scan_result.get('recommendations'),
                        'candidates': scan_result.get('candidates'),
                        'summary': scan_result.get('summary'),
                    },
                }
        except Exception as e:
            logger.error(f"JunGeTrader 执行失败: {e}")
            return {
                'agent_id': 'jun',
                'success': False,
                'error': f'JunGeTrader 执行失败: {e}',
            }

    # ── 其他 Agent：使用统一 LLM 模块 ────────────────────────────────────
    registry = get_agent_registry()
    profile = registry.get(agent_id)
    if not profile:
        return {'agent_id': agent_id, 'success': False, 'error': f'未知 Agent: {agent_id}'}

    if agent_id == 'beijing':
        try:
            overview_text = _get_market_overview()
            beijing_artifacts = _build_beijing_execution_artifacts(overview_text=overview_text)
            beijing_context = _build_beijing_execution_context_text(beijing_artifacts)
            prompt_bundle = _load_single_agent_prompt_bundle(
                agent_id,
                registry,
                search_data=beijing_artifacts.get('searchDataPreview', ''),
                agent_execution_context=beijing_context,
                force_empty_scan=True,
            )

            options = CallOptions(
                temperature=profile.get('temperature', 0.3),
                max_tokens=profile.get('max_tokens', 3000),
            )
            resp = get_client().call(
                prompt=prompt_bundle['user_prompt'],
                system=profile.get('system_prompt', ''),
                options=options,
            )

            result = {
                'agent_id': agent_id,
                'agent_name': profile.get('name', ''),
                'name_brand': profile.get('name', ''),
                'role_subtitle': profile.get('role', ''),
                'avatar_url': '',
                'success': False,
                'raw_response': resp.content if resp.success else '',
                'structured': None,
                'analysis': '',
                'tokens_used': resp.tokens_used,
            }

            if not resp.success:
                result['error'] = resp.error or 'LLM 调用返回空'
                fallback = _build_beijing_fallback_structured(beijing_artifacts)
                result['structured'] = _merge_beijing_structured(fallback, beijing_artifacts)
                _enrich_stocks_realtime(result['structured'])
                result['analysis'] = '【北京炒家执行工件】\n' + beijing_context
                return result

            parsed = registry.extract_json(resp.content)
            structured = parsed or _build_beijing_fallback_structured(beijing_artifacts)
            structured = registry.sanitize(
                structured,
                prompt_bundle['all_stocks'],
                default_advise_type=profile.get('adviseType', '游资打板'),
            )
            structured = _merge_beijing_structured(structured, beijing_artifacts)
            _enrich_stocks_realtime(structured)

            markdown_analysis = _strip_json_from_analysis(resp.content).strip()
            if not markdown_analysis:
                markdown_analysis = '【北京炒家执行工件】\n' + beijing_context

            result['success'] = True
            result['structured'] = structured
            result['analysis'] = markdown_analysis
            return result
        except Exception as exc:
            logger.error('北京炒家执行失败: %s', exc, exc_info=True)
            return {
                'agent_id': agent_id,
                'success': False,
                'error': f'北京炒家执行失败: {exc}',
            }

    if agent_id == 'qiao':
        try:
            overview_text = _get_market_overview()
            qiao_artifacts = _build_qiao_execution_artifacts(overview_text=overview_text)
            qiao_context = _build_qiao_execution_context_text(qiao_artifacts)
            prompt_bundle = _load_single_agent_prompt_bundle(
                agent_id,
                registry,
                search_data=qiao_artifacts.get('searchDataPreview', ''),
                agent_execution_context=qiao_context,
                force_empty_scan=True,
            )

            options = CallOptions(
                temperature=profile.get('temperature', 0.3),
                max_tokens=profile.get('max_tokens', 3000),
            )
            resp = get_client().call(
                prompt=prompt_bundle['user_prompt'],
                system=profile.get('system_prompt', ''),
                options=options,
            )

            result = {
                'agent_id': agent_id,
                'agent_name': profile.get('name', ''),
                'name_brand': profile.get('name', ''),
                'role_subtitle': profile.get('role', ''),
                'avatar_url': '',
                'success': False,
                'raw_response': resp.content if resp.success else '',
                'structured': None,
                'analysis': '',
                'tokens_used': resp.tokens_used,
            }

            if not resp.success:
                result['error'] = resp.error or 'LLM 调用返回空'
                fallback = _build_qiao_fallback_structured(qiao_artifacts)
                result['structured'] = _merge_qiao_structured(fallback, qiao_artifacts)
                _enrich_stocks_realtime(result['structured'])
                result['analysis'] = '【乔帮主执行工件】\n' + qiao_context
                return result

            parsed = registry.extract_json(resp.content)
            structured = parsed or _build_qiao_fallback_structured(qiao_artifacts)
            structured = registry.sanitize(
                structured,
                prompt_bundle['all_stocks'],
                default_advise_type=profile.get('adviseType', '龙头主升'),
            )
            structured = _merge_qiao_structured(structured, qiao_artifacts)
            _enrich_stocks_realtime(structured)

            markdown_analysis = _strip_json_from_analysis(resp.content).strip()
            if not markdown_analysis:
                markdown_analysis = '【乔帮主执行工件】\n' + qiao_context

            result['success'] = True
            result['structured'] = structured
            result['analysis'] = markdown_analysis
            return result
        except Exception as exc:
            logger.error('乔帮主执行失败: %s', exc, exc_info=True)
            return {
                'agent_id': agent_id,
                'success': False,
                'error': f'乔帮主执行失败: {exc}',
            }

    if agent_id == 'jia':
        try:
            overview_text = _get_market_overview()
            jia_artifacts = _build_jia_execution_artifacts(overview_text=overview_text)
            jia_context = _build_jia_execution_context_text(jia_artifacts)
            prompt_bundle = _load_single_agent_prompt_bundle(
                agent_id,
                registry,
                search_data=jia_artifacts.get('searchDataPreview', ''),
                agent_execution_context=jia_context,
                force_empty_scan=True,
            )

            options = CallOptions(
                temperature=profile.get('temperature', 0.3),
                max_tokens=profile.get('max_tokens', 3000),
            )
            resp = get_client().call(
                prompt=prompt_bundle['user_prompt'],
                system=profile.get('system_prompt', ''),
                options=options,
            )

            result = {
                'agent_id': agent_id,
                'agent_name': profile.get('name', ''),
                'name_brand': profile.get('name', ''),
                'role_subtitle': profile.get('role', ''),
                'avatar_url': '',
                'success': False,
                'raw_response': resp.content if resp.success else '',
                'structured': None,
                'analysis': '',
                'tokens_used': resp.tokens_used,
            }

            if not resp.success:
                result['error'] = resp.error or 'LLM 调用返回空'
                fallback = _build_jia_fallback_structured(jia_artifacts)
                result['structured'] = _merge_jia_structured(fallback, jia_artifacts)
                _enrich_stocks_realtime(result['structured'])
                result['analysis'] = '【炒股养家执行工件】\n' + jia_context
                return result

            parsed = registry.extract_json(resp.content)
            structured = parsed or _build_jia_fallback_structured(jia_artifacts)
            structured = registry.sanitize(
                structured,
                prompt_bundle['all_stocks'],
                default_advise_type=profile.get('adviseType', '情绪龙头'),
            )
            structured = _merge_jia_structured(structured, jia_artifacts)
            _enrich_stocks_realtime(structured)

            markdown_analysis = _strip_json_from_analysis(resp.content).strip()
            if not markdown_analysis:
                markdown_analysis = '【炒股养家执行工件】\n' + jia_context

            result['success'] = True
            result['structured'] = structured
            result['analysis'] = markdown_analysis
            return result
        except Exception as exc:
            logger.error('炒股养家执行失败: %s', exc, exc_info=True)
            return {
                'agent_id': agent_id,
                'success': False,
                'error': f'炒股养家执行失败: {exc}',
            }

    market = get_market_snapshot()
    prompt = render_prompt(profile, market)

    # 使用统一 LLM 客户端调用
    options = CallOptions(
        temperature=profile.get('temperature', 0.3),
        max_tokens=3000,
    )
    resp = get_client().call(
        prompt=prompt,
        system=profile.get('system_prompt', ''),
        options=options,
    )

    result = {
        'agent_id': agent_id,
        'agent_name': profile.get('name', ''),
        'name_brand': profile.get('name', ''),
        'role_subtitle': profile.get('role', ''),
        'avatar_url': '',
        'success': False,
        'raw_response': resp.content if resp.success else '',
        'structured': None,
        'analysis': '',
        'tokens_used': resp.tokens_used,
    }

    if not resp.success or not resp.content:
        result['error'] = resp.error or 'LLM 调用返回空'
        return result

    # 使用统一 AgentRegistry 解析 JSON
    parsed = registry.extract_json(resp.content)
    if parsed:
        result['success'] = True
        result['structured'] = {
            'agentId': parsed.get('agent_id', agent_id),
            'agentName': parsed.get('agent_name', profile.get('name', '')),
            'stance': parsed.get('stance', 'neutral'),
            'confidence': int(parsed.get('confidence', 50)),
            'marketCommentary': str(parsed.get('marketCommentary', '')),
            'positionAdvice': str(parsed.get('positionAdvice', '')),
            'riskWarning': str(parsed.get('riskWarning', '')),
            'recommendedStocks': parsed.get('recommendedStocks', []),
        }
        # 补调实时行情
        _enrich_stocks_realtime(result['structured'])
        parts = [
            f"【市场解读】{parsed.get('marketCommentary','')}",
            f"【策略建议】{parsed.get('positionAdvice','')}",
            f"【风险提示】{parsed.get('riskWarning','')}",
        ]
        recs = result['structured'].get('recommendedStocks', [])
        if recs:
            recs_lines = [f"推荐关注：{r.get('name','')}({r.get('code','')}) - {r.get('role','')}: {r.get('reason','')}"
                          for r in recs[:5]]
            parts.append('\n'.join(recs_lines))
        result['analysis'] = '\n'.join(parts)
    else:
        result['success'] = True
        result['analysis'] = resp.content
        result['structured'] = {
            'agentId': agent_id,
            'agentName': profile.get('name', ''),
            'stance': 'neutral',
            'confidence': 50,
            'marketCommentary': resp.content[:100],
            'positionAdvice': resp.content[100:200],
            'riskWarning': '',
            'recommendedStocks': [],
        }

    return result


# ── API 路由 ────────────────────────────────────────────────────────────────

@strategy_bp.route('/api/agents/prompts')
def get_agent_prompts():
    """返回所有 Agent 的元信息（前端渲染用）"""
    registry = get_agent_registry()
    agents = registry.list_agents()
    return jsonify({'success': True, 'data': agents})


@strategy_bp.route('/api/agents/architecture')
def get_agent_architecture():
    """返回策略智能体系统架构、层级说明与人格目录。"""
    registry = get_agent_registry()
    return jsonify({'success': True, 'data': registry.get_architecture_overview()})


@strategy_bp.route('/api/agents/analyze/<agent_id>', methods=['POST'])
def analyze_single_agent_api(agent_id):
    """单 Agent 分析接口"""
    registry = get_agent_registry()
    if not registry.get(agent_id):
        return jsonify({'success': False, 'error': '未知 Agent'}), 404

    result = analyze_single_agent(agent_id)
    # 内层 result 含 success: False 时不可与外层 success 合并，否则覆盖为 false 导致前端误判失败
    agent_success = result.pop('success', True)
    if agent_success:
        try:
            structured = result.get('structured') or {}
            report_date = datetime.now().strftime('%Y-%m-%d')
            raw_text = result.get('raw_response') or result.get('analysis') or ''
            thinking = result.get('thinking') or ''
            ar_payload = {
                'structured': structured,
                'raw_text': raw_text,
                'thinking': thinking,
                'marketCommentary': structured.get('marketCommentary', ''),
                'positionAdvice': structured.get('positionAdvice', ''),
                'riskWarning': structured.get('riskWarning', ''),
                'stance': structured.get('stance', ''),
                'confidence': structured.get('confidence', 0),
                'recommendedStocks': structured.get('recommendedStocks', []),
            }
            snap = db.build_analysis_holdings_snapshot(
                db.get_holdings_by_agent(agent_id),
                ar_payload,
            )
            db.save_agent_analysis_history(
                agent_id=agent_id,
                report_date=report_date,
                holdings_snapshot=snap,
                analysis_result=ar_payload,
                raw_response=raw_text,
                thinking=thinking,
                stance=structured.get('stance', ''),
                confidence=int(structured.get('confidence', 0) or 0),
                tokens_used=int(result.get('tokens_used', 0) or 0),
            )

            rec_stocks = structured.get('recommendedStocks', []) or []
            if rec_stocks:
                try:
                    db.save_recommended_stocks_as_holdings(agent_id, rec_stocks)
                except Exception as save_err:
                    logger.warning('[Analyze] 保存推荐股到持仓失败 agent=%s err=%s', agent_id, save_err)
        except Exception as hist_err:
            logger.warning('[Analyze] 保存分析历史失败 agent=%s err=%s', agent_id, hist_err)
    return jsonify({'success': True, 'agent_success': agent_success, **result})


@strategy_bp.route('/api/agents/analyze/<agent_id>/stream', methods=['POST'])
def analyze_single_agent_stream(agent_id):
    """
    单 Agent 流式分析接口（SSE）
    支持 Function Calling，实时推送 thinking 过程和最终结果
    """
    import flask
    import json
    from utils.llm.agents import (
        AGENT_TOOLS,
        COMMON_TOOLS,
        get_agent_registry,
        get_agent_task_decomposition,
    )
    from flask import request

    def get_agent_tools(agent_id: str):
        """获取 Agent 对应的工具列表"""
        return AGENT_TOOLS.get(agent_id, COMMON_TOOLS)

    def execute_tool(tool_name: str, tool_args: dict) -> str:
        """执行工具调用"""
        if tool_name == 'web_search':
            return _do_web_search(tool_args.get('query', ''))
        elif tool_name == 'get_limit_up_stocks':
            return _get_limit_up_stocks()
        elif tool_name == 'get_yesterday_limit_up_stocks':
            return _get_yesterday_limit_up_stocks()
        elif tool_name == 'get_stock_quote':
            return _get_stock_quote(tool_args.get('code', ''))
        elif tool_name == 'get_market_overview':
            return _get_market_overview()
        else:
            return f"未知工具: {tool_name}"

    def stream_response():
        _agent_id = agent_id
        registry = get_agent_registry()
        profile = registry.get(_agent_id)
        agent_view = registry.describe_agent(_agent_id, include_prompts=True) or {}
        
        if not profile:
            yield f"data: {json.dumps({'type': 'error', 'error': '未知 Agent'})}\n\n"
            return

        def sse(payload: Dict[str, Any]) -> str:
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        try:
            task_decomposition = get_agent_task_decomposition(_agent_id)
            current_task_step = 0

            def next_task_step_payload():
                nonlocal current_task_step
                if not task_decomposition or current_task_step >= len(task_decomposition):
                    return None
                step_info = task_decomposition[current_task_step]
                current_task_step += 1
                return {
                    'type': 'task_step',
                    'step': current_task_step,
                    'total': len(task_decomposition),
                    'title': step_info.get('title', f'步骤 {current_task_step}'),
                    'desc': step_info.get('description', ''),
                    'status': 'running',
                }

            if task_decomposition:
                yield sse({
                    'type': 'task_flow_init',
                    'total': len(task_decomposition),
                    'coreObjective': agent_view.get('coreObjective', ''),
                    'steps': [
                        {
                            'step': idx + 1,
                            'title': item.get('title', f'步骤 {idx + 1}'),
                            'desc': item.get('description', ''),
                            'done': False,
                        }
                        for idx, item in enumerate(task_decomposition)
                    ],
                })

            # ══ 共享事实层：优先读取轻量级市场概览，避免一开始就被东财快照阻塞 ═════════
            yield sse({
                'type': 'cot',
                'step': 1,
                'total': 3,
                'title': '共享事实同步',
                'message': '正在读取大盘概览、扫描结果和可复用市场上下文...',
            })
            overview_text = _get_market_overview()
            if overview_text and '暂时无法获取' not in overview_text:
                snapshot_lines = [f"  {line.strip()}" for line in overview_text.split('\n') if line.strip()]
                if snapshot_lines and _agent_id not in {'beijing', 'qiao', 'jia'}:
                    yield sse({'type': 'cot_data', 'step': 1, 'lines': snapshot_lines})
            elif _agent_id not in {'beijing', 'qiao', 'jia'}:
                yield sse({
                    'type': 'cot_data',
                    'step': 1,
                    'lines': ['  [警告] 暂未拿到实时指数快照，缺失字段将按待观察处理'],
                })

            yield sse({
                'type': 'cot',
                'step': 2,
                'total': 3,
                'title': '联网补充',
                'message': '正在补充涨停板、市场情绪、主线题材与新闻催化...',
            })

            search_result = _call_deepseek_search(
                prompt=(
                    f"当前时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}\n\n"
                    "请联网搜索今日A股市场数据，返回以下信息（用中文）：\n"
                    "1. 今日涨停板：涨停家数、重点连板股（名称、代码、连板数、涨停原因）\n"
                    "2. 市场空间板：最高板是谁，龙头股\n"
                    "3. 市场情绪：赚钱效应（强/中/弱）、亏钱效应（无/局部/扩散）\n"
                    "4. 主线题材：今日最强题材板块及龙头\n"
                    "5. 今日重要新闻/政策（影响市场的）"
                ),
                model='qwen-plus',
            )

            if not search_result.success:
                search_data = '【联网补充失败，请仅基于共享事实层已有数据分析，缺失字段统一写“待观察”】'
                if _agent_id not in {'beijing', 'qiao', 'jia'}:
                    yield sse({
                        'type': 'cot_data',
                        'step': 2,
                        'lines': [f"  [警告] 联网补充失败: {search_result.error}"],
                    })
            else:
                search_data = search_result.content or ''

            yield sse({
                'type': 'cot',
                'step': 3,
                'total': 3,
                'title': '方法论执行',
                'message': f"{profile.get('name', _agent_id)} 正在按既定方法论拆解当前市场...",
            })

            all_stocks = _collect_latest_scan_candidates()
            beijing_artifacts = None
            qiao_artifacts = None
            jia_artifacts = None
            auto_task_progress = _agent_id not in {'beijing', 'qiao', 'jia'}

            if _agent_id not in {'beijing', 'qiao', 'jia'}:
                task_payload = next_task_step_payload()
                if task_payload:
                    yield sse(task_payload)

                # 非人格工件型 Agent 保留联网数据逐段回放
                for para in search_data.split('\n'):
                    if para.strip():
                        yield sse({'type': 'cot_data', 'step': 2, 'lines': [para.strip()]})

            # ── 第二步：构建 prompt 并分析 ──────────────────────────────────
            if _agent_id == 'beijing':
                beijing_artifacts = _build_beijing_execution_artifacts(
                    search_data=search_data,
                    overview_text=overview_text,
                )
                beijing_context = _build_beijing_execution_context_text(beijing_artifacts)
                prompt_bundle = _load_single_agent_prompt_bundle(
                    _agent_id,
                    registry,
                    search_data=search_data,
                    agent_execution_context=beijing_context,
                    force_empty_scan=True,
                )
                prompt = prompt_bundle['user_prompt']
                all_stocks = prompt_bundle['all_stocks']
                tools = []

                for step_output in beijing_artifacts.get('stepOutputs', []):
                    task_payload = next_task_step_payload()
                    if task_payload:
                        yield sse(task_payload)
                    step_no = task_payload.get('step') if task_payload else int(step_output.get('step') or 0)
                    lines = []
                    summary = str(step_output.get('summary') or '').strip()
                    if summary:
                        lines.append(summary)
                    lines.extend([f"方法论：{line}" for line in (step_output.get('frameworkLines', [])[:3])])
                    lines.extend([f"当日判断：{line}" for line in (step_output.get('lines', [])[:3])])
                    if lines:
                        yield sse({'type': 'cot_data', 'step': step_no, 'lines': lines})
            elif _agent_id == 'qiao':
                qiao_artifacts = _build_qiao_execution_artifacts(
                    search_data=search_data,
                    overview_text=overview_text,
                )
                qiao_context = _build_qiao_execution_context_text(qiao_artifacts)
                prompt_bundle = _load_single_agent_prompt_bundle(
                    _agent_id,
                    registry,
                    search_data=search_data,
                    agent_execution_context=qiao_context,
                    force_empty_scan=True,
                )
                prompt = prompt_bundle['user_prompt']
                all_stocks = prompt_bundle['all_stocks']
                tools = []

                for step_output in qiao_artifacts.get('stepOutputs', []):
                    task_payload = next_task_step_payload()
                    if task_payload:
                        yield sse(task_payload)
                    step_no = task_payload.get('step') if task_payload else int(step_output.get('step') or 0)
                    lines = []
                    summary = str(step_output.get('summary') or '').strip()
                    if summary:
                        lines.append(summary)
                    lines.extend([f"方法论：{line}" for line in (step_output.get('frameworkLines', [])[:3])])
                    lines.extend([f"当日判断：{line}" for line in (step_output.get('lines', [])[:3])])
                    if lines:
                        yield sse({'type': 'cot_data', 'step': step_no, 'lines': lines})
            elif _agent_id == 'jia':
                jia_artifacts = _build_jia_execution_artifacts(
                    search_data=search_data,
                    overview_text=overview_text,
                )
                jia_context = _build_jia_execution_context_text(jia_artifacts)
                prompt_bundle = _load_single_agent_prompt_bundle(
                    _agent_id,
                    registry,
                    search_data=search_data,
                    agent_execution_context=jia_context,
                    force_empty_scan=True,
                )
                prompt = prompt_bundle['user_prompt']
                all_stocks = prompt_bundle['all_stocks']
                tools = []

                for step_output in jia_artifacts.get('stepOutputs', []):
                    task_payload = next_task_step_payload()
                    if task_payload:
                        yield sse(task_payload)
                    step_no = task_payload.get('step') if task_payload else int(step_output.get('step') or 0)
                    lines = []
                    summary = str(step_output.get('summary') or '').strip()
                    if summary:
                        lines.append(summary)
                    lines.extend([f"方法论：{line}" for line in (step_output.get('frameworkLines', [])[:3])])
                    lines.extend([f"当日判断：{line}" for line in (step_output.get('lines', [])[:3])])
                    if lines:
                        yield sse({'type': 'cot_data', 'step': step_no, 'lines': lines})
            else:
                # 在 market 数据中加入联网搜索结果
                market = get_market_snapshot()
                market['search_data'] = search_data
                prompt = render_prompt(profile, market)

                # 获取 Agent 专属工具（用于分析阶段查个股行情）
                tools = get_agent_tools(_agent_id)

            # 构建消息
            messages = [
                {"role": "system", "content": profile.get('system_prompt', '')},
                {"role": "user", "content": prompt}
            ]

            # 流式调用 LLM（带 Function Calling）
            from utils.llm.client import get_client, CallOptions, LLMResponse

            client = get_client()
            model = profile.get('model') or 'deepseek-v3.2'
            temperature = profile.get('temperature', 0.3)
            max_tokens = profile.get('max_tokens', 3000)

            # 发送准备完成消息
            yield sse({'type': 'status', 'message': '正在调用 AI 分析...'})

            # 处理 Function Calling 循环
            MAX_TOOL_CALLS = 5
            all_thinking = ""
            final_content = ""
            total_tokens = 0

            for _ in range(MAX_TOOL_CALLS):
                # 调用 LLM
                resp = _call_llm_with_tools(
                    client=client,
                    model=model,
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                if not resp.success:
                    yield f"data: {json.dumps({'type': 'error', 'error': resp.error})}\n\n"
                    return

                # 收集思考过程（整块发送，前端按【章节分批展示）
                if resp.reasoning_content:
                    all_thinking += resp.reasoning_content
                    thinking_content = resp.reasoning_content.strip()
                    if thinking_content:
                        yield sse({'type': 'thinking', 'content': thinking_content})

                        if auto_task_progress:
                            task_payload = next_task_step_payload()
                            if task_payload:
                                yield sse(task_payload)

                # 收集最终内容
                final_content = resp.content
                total_tokens += resp.tokens_used

                # 检查是否有工具调用
                if resp.tool_calls:
                    # 执行工具调用并添加到消息
                    for tc in resp.tool_calls:
                        tool_name = tc['name']
                        tool_args = tc.get('arguments', {})

                        # 执行工具
                        tool_result = execute_tool(tool_name, tool_args)

                        # 添加到消息历史
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": tc['id'],
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": json.dumps(tool_args)
                                }
                            }]
                        })
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc['id'],
                            "content": tool_result
                        })
                else:
                    # 没有更多工具调用，退出循环
                    break

            # 解析 JSON 输出
            parsed = registry.extract_json(final_content)

            if parsed:
                structured = {
                    'agentId': parsed.get('agent_id', _agent_id),
                    'agentName': parsed.get('agent_name', profile.get('name', '')),
                    'stance': parsed.get('stance', 'neutral'),
                    'confidence': int(parsed.get('confidence', 50)),
                    'marketCommentary': str(parsed.get('marketCommentary', '')),
                    'positionAdvice': str(parsed.get('positionAdvice', '')),
                    'riskWarning': str(parsed.get('riskWarning', '')),
                    'recommendedStocks': parsed.get('recommendedStocks', []),
                }
            else:
                structured = {
                    'agentId': _agent_id,
                    'agentName': profile.get('name', ''),
                    'stance': 'neutral',
                    'confidence': 50,
                    'marketCommentary': final_content[:200] if final_content else '',
                    'positionAdvice': '',
                    'riskWarning': '',
                    'recommendedStocks': [],
                }

            structured = registry.sanitize(
                structured,
                all_stocks,
                default_advise_type=profile.get('adviseType', '波段'),
            )
            if _agent_id == 'beijing' and beijing_artifacts:
                structured = _merge_beijing_structured(structured, beijing_artifacts)
            if _agent_id == 'qiao' and qiao_artifacts:
                structured = _merge_qiao_structured(structured, qiao_artifacts)
            if _agent_id == 'jia' and jia_artifacts:
                structured = _merge_jia_structured(structured, jia_artifacts)

            # ── 批量补调推荐股票的实时行情 ──────────────────────────────────
            _enrich_stocks_realtime(structured)

            if auto_task_progress:
                task_payload = next_task_step_payload()
                if task_payload:
                    yield sse(task_payload)

            # 把分析内容分段落实时发送到前端（去掉 JSON 代码块，只留 Markdown）
            markdown_content = _strip_json_from_analysis(final_content).strip()
            if _agent_id == 'beijing' and beijing_artifacts:
                looks_like_json_only = not markdown_content or markdown_content.startswith('{') or markdown_content.startswith('```json')
                if looks_like_json_only:
                    markdown_content = _build_beijing_markdown_summary(structured, beijing_artifacts)
            if _agent_id == 'qiao' and qiao_artifacts:
                looks_like_json_only = not markdown_content or markdown_content.startswith('{') or markdown_content.startswith('```json')
                if looks_like_json_only:
                    markdown_content = _build_qiao_markdown_summary(structured, qiao_artifacts)
            if _agent_id == 'jia' and jia_artifacts:
                looks_like_json_only = not markdown_content or markdown_content.startswith('{') or markdown_content.startswith('```json')
                if looks_like_json_only:
                    markdown_content = _build_jia_markdown_summary(structured, jia_artifacts)
            for para in markdown_content.split('\n'):
                if para.strip():
                    yield sse({'type': 'content', 'content': para.strip()})

            try:
                report_date = datetime.now().strftime('%Y-%m-%d')
                ar_payload = {
                    'structured': structured,
                    'raw_text': final_content,
                    'thinking': all_thinking,
                    'marketCommentary': structured.get('marketCommentary', ''),
                    'positionAdvice': structured.get('positionAdvice', ''),
                    'riskWarning': structured.get('riskWarning', ''),
                    'stance': structured.get('stance', ''),
                    'confidence': structured.get('confidence', 0),
                    'recommendedStocks': structured.get('recommendedStocks', []),
                }
                snap = db.build_analysis_holdings_snapshot(
                    db.get_holdings_by_agent(_agent_id),
                    ar_payload,
                )
                db.save_agent_analysis_history(
                    agent_id=_agent_id,
                    report_date=report_date,
                    holdings_snapshot=snap,
                    analysis_result=ar_payload,
                    raw_response=final_content or '',
                    thinking=all_thinking,
                    stance=structured.get('stance', ''),
                    confidence=int(structured.get('confidence', 0) or 0),
                    tokens_used=total_tokens,
                )

                rec_stocks = structured.get('recommendedStocks', []) or []
                if rec_stocks:
                    try:
                        db.save_recommended_stocks_as_holdings(_agent_id, rec_stocks)
                    except Exception as save_err:
                        logger.warning('[Stream] 保存推荐股到持仓失败 agent=%s err=%s', _agent_id, save_err)
            except Exception as hist_err:
                logger.warning('[Stream] 保存分析历史失败 agent=%s err=%s', _agent_id, hist_err)

            done_payload = {
                'type': 'done',
                'agent_id': _agent_id,
                'agent_name': profile.get('name', ''),
                'structured': structured,
                'analysis': markdown_content,
                'thinking': all_thinking,
                'tokens_used': total_tokens,
                'task_decomposition': task_decomposition,
                'task_core_objective': agent_view.get('coreObjective', ''),
            }
            yield sse(done_payload)

        except Exception as e:
            import traceback
            logger.error(f"[Stream] agent={_agent_id} error={e}\n{traceback.format_exc()}")
            yield sse({'type': 'error', 'error': str(e)})

    return flask.Response(
        stream_response(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )


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
        # 判断模型类型：百炼 deepseek 系列走 deepseek 分支，其他走 qwen 分支
        is_deepseek = 'deepseek' in model.lower()

        if is_deepseek:
            # 百炼 DeepSeek（禁用思考模式，因为 function calling 仅非思考模式支持）
            return _call_deepseek_with_tools(client, model, messages, tools, temperature, max_tokens)
        else:
            # Qwen/DashScope 模型调用
            return _call_dashscope_with_tools(model, messages, tools, temperature, max_tokens)

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
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # Qwen 的 tools 格式不同
        if tools:
            payload["tools"] = tools
        
        resp = requests.post(
            f"{DASHSCOPE_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
            proxies={"http": None, "https": None},
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
        # 兼容模式的响应是 OpenAI 格式：choices 在根级别
        # 旧版百炼 API 格式：choices 在 output 里
        # 优先用 OpenAI 兼容格式
        choices = data.get('choices') or data.get('output', {}).get('choices') or []
        output_msg = data.get('choices', [{}])[0].get('message') if data.get('choices') else (data.get('output', {}).get('choices', [{}])[0].get('message') if data.get('output', {}).get('choices') else None)

        if not choices:
            logger.warning(f"[_call_dashscope_with_tools] No choices. resp.keys={list(data.keys())}, resp={resp.text[:300]}")
            return SimpleResponse(
                content='',
                tokens_used=data.get('usage', {}).get('total_tokens', 0),
                model=model,
                provider='dashscope',
                success=False,
                error=f"No choices in response: {resp.text[:200]}",
                tool_calls=[],
            )

        # 解析消息内容
        if output_msg:
            content = output_msg.get('content', '') or ''
            raw_calls = output_msg.get('tool_calls', [])
        else:
            # fallback
            first_choice = choices[0] if choices else {}
            message = first_choice.get('message', {}) if isinstance(first_choice, dict) else {}
            content = message.get('content', '') or ''
            raw_calls = message.get('tool_calls', []) or []

        # 兼容：content 可能是数组
        if isinstance(content, list):
            content = ''.join(c.get('text', '') for c in content if isinstance(c, dict))

        logger.info(f"[_call_dashscope_with_tools] content len={len(content)}, tool_calls={len(raw_calls)}")

        # 解析 tool_calls
        tool_calls = []
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
        import traceback
        logger.error(f"[_call_dashscope_with_tools] error={e}\n{traceback.format_exc()}")
        return SimpleResponse(
            content='',
            tokens_used=0,
            model=model,
            provider='dashscope',
            success=False,
            error=str(e),
            tool_calls=[],
        )


def _call_deepseek_search(prompt: str, model: str = 'qwen-plus'):
    """
    调用百炼 qwen-plus 联网搜索获取市场数据（不走 Function Calling，纯联网）
    """
    import logging
    import httpx
    import os

    logger = logging.getLogger(__name__)

    try:
        for k in list(os.environ.keys()):
            if 'proxy' in k.lower():
                del os.environ[k]

        http_client = httpx.Client(trust_env=False, timeout=120.0)
        from utils.llm.client import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL
        from openai import OpenAI
        client = OpenAI(
            api_key=DASHSCOPE_API_KEY,
            base_url=DASHSCOPE_BASE_URL,
            http_client=http_client,
        )

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个专业的A股市场分析师，擅长联网搜索获取实时数据。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000,
            extra_body={
                "enable_search": True,
            },
        )

        content = resp.choices[0].message.content or ''
        tokens = resp.usage.total_tokens if resp.usage else 0

        return SimpleResponse(
            content=content,
            tokens_used=tokens,
            model=model,
            provider='dashscope',
            success=True,
            reasoning_content='',
            tool_calls=[],
        )

    except Exception as e:
        logger.error(f"[_call_deepseek_search] error={e}")
        return SimpleResponse(
            content='',
            tokens_used=0,
            model=model,
            provider='dashscope',
            success=False,
            error=str(e),
            reasoning_content='',
            tool_calls=[],
        )


def _call_deepseek_with_tools(client, model, messages, tools, temperature, max_tokens):
    """
    调用百炼 DeepSeek 模型（禁用思考模式 + 支持 Function Calling）
    """
    import logging
    import httpx
    import os

    logger = logging.getLogger(__name__)

    try:
        for k in list(os.environ.keys()):
            if 'proxy' in k.lower():
                del os.environ[k]

        http_client = httpx.Client(trust_env=False, timeout=300.0)
        from utils.llm.client import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL
        from openai import OpenAI
        ds_client = OpenAI(
            api_key=DASHSCOPE_API_KEY,
            base_url=DASHSCOPE_BASE_URL,
            http_client=http_client,
        )

        resp = ds_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body={
                "enable_thinking": False,
            },
            tools=tools if tools else None,
            tool_choice="auto" if tools else None,
        )

        choice = resp.choices[0]
        content = choice.message.content or ''
        reasoning_content = getattr(choice.message, 'reasoning_content', '') or ''
        tokens = resp.usage.total_tokens if resp.usage else 0

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
            reasoning_content='',
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



def _do_web_search(query: str) -> str:
    """搜索实时市场信息"""
    import requests
    import re
    import logging
    logger = logging.getLogger(__name__)
    
    if not query or not query.strip():
        return "查询为空，请提供有效的搜索关键词。"

    try:
        # 清除代理，避免超时
        for k in list(os.environ.keys()):
            if 'proxy' in k.lower():
                del os.environ[k]

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        url = f"https://www.baidu.com/s?wd={requests.utils.quote(query)}&rn=10"
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200 and len(resp.text) > 10000:
            results = []
            pattern = r'<h3[^>]*>(.*?)</h3>'
            matches = re.findall(pattern, resp.text, re.DOTALL)
            for m in matches[:15]:
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

    return f"搜索「{query}」暂无结果，请尝试其他关键词。"


def _get_limit_up_stocks() -> str:
    """获取今日涨停板数据"""
    import requests
    import logging
    logger = logging.getLogger(__name__)

    # 清除代理，避免超时
    for k in list(os.environ.keys()):
        if 'proxy' in k.lower():
            del os.environ[k]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'https://data.eastmoney.com/',
    }
    
    url = 'https://push2.eastmoney.com/api/qt/clist/get'
    params = {
        'pn': 1, 'pz': 50, 'po': 1, 'np': 1,
        'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
        'fltt': 2, 'invt': 2, 'fid': 'f3',
        'fs': 'm:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23',
        'fields': 'f12,f14,f2,f3,f4,f5,f6',
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data and data['data']:
                stocks = data['data'].get('diff', [])
                lines = [f"今日涨停股票共 {len(stocks)} 只:\n"]
                for i, s in enumerate(stocks[:30], 1):
                    code = s.get('f12', '')
                    name = s.get('f14', '')
                    price = s.get('f2', 0)
                    change = s.get('f3', 0)
                    amount = s.get('f6', 0)
                    amount_wan = amount / 10000 if amount else 0
                    lines.append(f"{i}. {name}({code}) | 现价:{price} | 涨幅:{change}% | 成交:{amount_wan:.0f}万")
                return '\n'.join(lines)
    except Exception as e:
        logger.warning("[LimitUp] 获取涨停数据失败: %s", e)
    
    return "暂时无法获取涨停板数据"


def _get_yesterday_limit_up_stocks() -> str:
    """获取昨日涨停板数据（用于分析参考）"""
    import requests
    from datetime import datetime, timedelta
    import logging
    logger = logging.getLogger(__name__)

    for k in list(os.environ.keys()):
        if 'proxy' in k.lower():
            del os.environ[k]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'https://data.eastmoney.com/',
    }

    # 获取昨日日期
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    # 东方财富 涨停板历史数据接口
    url = 'https://data.eastmoney.com/DataCenter/PageApi/RealTimeTrend/GetZTPool'

    try:
        # 尝试获取昨日涨停池数据
        params = {
            'sortColumns': 'SECURITY_CODE',
            'sortTypes': 1,
            'pageSize': 100,
            'pageNumber': 1,
            'reportName': 'RPT_LIMIT_UP_POOL_HISTORY_DETAILS',
            'filter': f"(TRADE_DATE='{yesterday}')",
            'columns': 'ALL',
        }
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            rows = data.get('data', {}).get('result', {}).get('data', []) or []
            if rows:
                lines = [f"昨日({yesterday})涨停股票共 {len(rows)} 只:\n"]
                for i, row in enumerate(rows[:50], 1):
                    code = row.get('SECURITY_CODE', '')
                    name = row.get('SECURITY_NAME_ABBR', '')
                    change_pct = row.get('CHANGE_RATE', 0)
                    amount_wan = (row.get('TURNOVER', 0) or 0) / 10000
                    reason = row.get('CONTINUOUS_COUNT', '') or ''
                    lines.append(f"{i}. {name}({code}) | 涨幅:{change_pct:.2f}% | 成交:{amount_wan:.0f}万 | {reason}")
                return '\n'.join(lines)
    except Exception as e:
        logger.warning("[YesterdayLimitUp] 获取昨日涨停数据失败: %s", e)

    # Fallback: 用今日涨停数据作为参考（如果昨日数据获取失败）
    today_data = _get_limit_up_stocks()
    return f"（未能获取昨日涨停数据，以下为今日涨停参考：）\n{today_data}"


def _get_stock_quote(code: str) -> str:
    """获取个股行情"""
    import requests
    import logging
    logger = logging.getLogger(__name__)
    
    if not code:
        return "股票代码不能为空"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://finance.sina.com.cn/',
        }
        url = f'https://hq.sinajs.cn/list={code}'
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            text = resp.text
            # 解析格式: var hq_str_sh600000="名称,现价,昨收,今开,最高,最低,..."
            match = text.split('"')[1] if '"' in text else ''
            if match:
                parts = match.split(',')
                if len(parts) >= 32:
                    name = parts[0]
                    price = parts[3]   # 现价
                    yclose = parts[2]   # 昨收
                    open_p = parts[1]   # 今开
                    high = parts[33]    # 最高
                    low = parts[34]     # 最低
                    vol = parts[8]      # 成交量
                    amount = parts[9]   # 成交额
                    change = float(price) - float(yclose) if price and yclose else 0
                    pct = (change / float(yclose) * 100) if yclose and float(yclose) > 0 else 0
                    
                    return (f"{name}({code}) 行情:\n"
                           f"现价: {price} | 涨跌: {change:+.2f} ({pct:+.2f}%)\n"
                           f"今开: {open_p} | 最高: {high} | 最低: {low}\n"
                           f"成交量: {vol} | 成交额: {amount}")
    except Exception as e:
        logger.warning("[StockQuote] 获取行情失败: %s", e)
    
    return f"暂时无法获取 {code} 的行情数据"


def _get_market_overview() -> str:
    """获取市场概览"""
    import requests
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://finance.sina.com.cn/',
        }
        # 上证指数和深证成指
        url = 'https://hq.sinajs.cn/list=s_sh000001,s_sh000300,s_sz399001,s_sz399006'
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            lines = []
            texts = resp.text.split('\n')
            names = ['上证指数', '沪深300', '深证成指', '创业板指']
            indices = ['sh000001', 'sh000300', 'sz399001', 'sz399006']
            
            for i, idx in enumerate(indices):
                for line in texts:
                    if idx in line:
                        match = line.split('"')[1] if '"' in line else ''
                        if match:
                            parts = match.split(',')
                            if len(parts) >= 4:
                                name = names[i]
                                price = parts[1] if parts[1] else '0'
                                change = parts[2] if parts[2] else '0'
                                pct = parts[3] if parts[3] else '0'
                                lines.append(f"{name}: {price} | {float(change):+.2f} ({float(pct):+.2f}%)")
                        break
            
            if lines:
                return '\n'.join(lines)
    except Exception as e:
        logger.warning("[MarketOverview] 获取市场概览失败: %s", e)
    
    return "暂时无法获取市场概览数据"


def _format_news_for_batch(news_list) -> str:
    """将新闻列表格式化为统一的批量分析输入文本。"""
    lines = []
    for idx, item in enumerate((news_list or [])[:10], 1):
        title = item.get('title', '') if isinstance(item, dict) else ''
        source = item.get('source', '') if isinstance(item, dict) else ''
        news_time = item.get('time', '') if isinstance(item, dict) else ''
        lines.append(f"【新闻{idx}】[{news_time}] {title}（{source}）")
    return '\n'.join(lines) if lines else '【暂无最新消息】'


def _safe_float_num(val, default: float = 0.0) -> float:
    if val is None or val == '':
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        text = str(val).strip().replace(',', '').replace('%', '').replace('+', '')
        return float(text)
    except (TypeError, ValueError):
        return default


def _safe_int_num(val, default: int = 0) -> int:
    if val is None or val == '':
        return default
    if isinstance(val, int):
        return val
    try:
        text = str(val).strip().replace(',', '').split('.')[0]
        return int(text)
    except (TypeError, ValueError):
        return default


def _normalize_code6(code: Any) -> str:
    raw = ''.join(ch for ch in str(code or '').strip() if ch.isdigit())
    return raw[-6:] if len(raw) >= 6 else raw


def _format_clock_hhmm(val: Any) -> str:
    raw = str(val or '').strip()
    if not raw or raw.lower() == 'nan':
        return '待观察'
    digits = ''.join(ch for ch in raw if ch.isdigit())
    if not digits:
        return '待观察'
    digits = digits.zfill(6)[-6:]
    return f'{digits[:2]}:{digits[2:4]}'


def _clock_to_int(val: Any) -> int:
    raw = str(val or '').strip()
    if not raw or raw.lower() == 'nan':
        return 0
    digits = ''.join(ch for ch in raw if ch.isdigit())
    return int(digits.zfill(6)[-6:]) if digits else 0


def _to_yi(val: Any) -> float:
    return round(_safe_float_num(val) / 100000000, 2)


def _normalize_scan_pct_change(val: Any) -> float:
    pct = _safe_float_num(val)
    if abs(pct) <= 1.0:
        pct *= 100.0
    return round(pct, 2)


def _code_to_tencent_symbol(code: Any) -> str:
    norm = _normalize_code6(code)
    if norm.startswith(('6', '9')):
        return f'sh{norm}'
    return f'sz{norm}'


def _estimate_prev_close(price: Any, change_pct: Any) -> float:
    latest_price = _safe_float_num(price)
    pct = _safe_float_num(change_pct)
    if latest_price <= 0:
        return 0.0
    base = 1 + pct / 100.0
    if abs(base) < 1e-9:
        return 0.0
    prev_close = latest_price / base
    return round(prev_close, 4) if prev_close > 0 else 0.0


def _extract_json_payload(text: str) -> str:
    raw = str(text or '').strip()
    if not raw:
        return ''

    import re

    fenced = re.search(r'```json\s*([\s\S]*?)```', raw, re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    fenced = re.search(r'```\s*([\s\S]*?)```', raw)
    if fenced:
        return fenced.group(1).strip()

    for start, end in (('[', ']'), ('{', '}')):
        s = raw.find(start)
        e = raw.rfind(end)
        if s != -1 and e != -1 and e > s:
            return raw[s:e + 1].strip()
    return raw


def _load_json_loose(text: str) -> Any:
    payload = _extract_json_payload(text)
    if not payload:
        return None
    try:
        return json.loads(payload)
    except Exception:
        return None


def _get_stock_intraday_minutes_tencent(code: str) -> List[Dict[str, Any]]:
    symbol = _code_to_tencent_symbol(code)
    url = 'https://web.ifzq.gtimg.cn/appstock/app/minute/query'
    params = {
        '_var': f'min_data_{symbol}',
        'code': symbol,
        'r': str(int(datetime.now().timestamp())),
    }
    headers = {
        'Referer': 'https://finance.qq.com',
        'User-Agent': 'Mozilla/5.0',
    }

    try:
        session = requests.Session()
        session.trust_env = False
        resp = session.get(url, params=params, headers=headers, timeout=8)
        text = resp.text or ''

        import re

        matched = re.search(r'=(\{.*\})', text, re.DOTALL)
        if not matched:
            return []

        raw = json.loads(matched.group(1))
        symbol_data = (raw.get('data') or {}).get(symbol, {})
        lines = ((symbol_data.get('data') or {}).get('data') or []) if isinstance(symbol_data, dict) else []
        if not lines:
            return []

        today = datetime.now().strftime('%Y-%m-%d')
        result: List[Dict[str, Any]] = []
        for line in lines:
            parts = str(line or '').split(' ')
            if len(parts) < 2:
                continue
            hhmm = ''.join(ch for ch in parts[0] if ch.isdigit()).zfill(4)[-4:]
            try:
                price = float(parts[1])
            except (TypeError, ValueError):
                continue
            volume = _safe_float_num(parts[2]) if len(parts) > 2 else 0.0
            amount = _safe_float_num(parts[3]) if len(parts) > 3 else 0.0
            result.append({
                'time': f'{today} {hhmm[:2]}:{hhmm[2:]}',
                'hhmm': int(hhmm),
                'price': price,
                'volume': volume,
                'amount': amount,
            })
        return result
    except Exception as exc:
        logger.debug('[Beijing] 腾讯分时获取失败 code=%s err=%s', code, exc)
        return []


def _normalize_intraday_price_scale(minutes: List[Dict[str, Any]], latest_price: float) -> List[Dict[str, Any]]:
    if not minutes or latest_price <= 0:
        return minutes

    tail_price = _safe_float_num(minutes[-1].get('price'))
    if tail_price <= 0:
        return minutes

    scale_candidates = [1, 10, 100, 1000]
    best_scale = 1
    best_error = float('inf')
    for scale in scale_candidates:
        scaled = tail_price / scale
        err = abs(scaled - latest_price) / max(latest_price, 1e-6)
        if err < best_error:
            best_error = err
            best_scale = scale

    if best_scale == 1:
        return minutes

    normalized: List[Dict[str, Any]] = []
    for item in minutes:
        one = dict(item)
        one['price'] = round(_safe_float_num(item.get('price')) / best_scale, 4)
        normalized.append(one)
    return normalized


def _analyze_beijing_minute_evidence(
    code: str,
    *,
    latest_price: Any,
    change_pct: Any,
    first_seal_int: int = 0,
) -> Dict[str, Any]:
    default = {
        'minuteDataStatus': 'unavailable',
        'openChangeProxy': None,
        'minuteTurnoverMinutes': 0,
        'minuteLongestStreak': 0,
        'minuteTurnoverLabel': '待观察',
        'minuteEvidence': '分钟级换手证据待观察',
    }

    prev_close = _estimate_prev_close(latest_price, change_pct)
    if prev_close <= 0:
        return default

    minutes = _get_stock_intraday_minutes_tencent(code)
    if not minutes:
        return default

    latest_price_num = _safe_float_num(latest_price)
    minutes = _normalize_intraday_price_scale(minutes, latest_price_num)
    seal_hhmm = max(0, int(first_seal_int or 0) // 100)
    scoped = [item for item in minutes if not seal_hhmm or int(item.get('hhmm') or 0) <= seal_hhmm]
    scoped = scoped or minutes

    zone_total = 0
    zone_longest = 0
    current = 0
    for item in scoped:
        pct = (_safe_float_num(item.get('price')) - prev_close) / prev_close * 100
        if 5.8 <= pct <= 8.2:
            zone_total += 1
            current += 1
            zone_longest = max(zone_longest, current)
        else:
            current = 0

    open_price = _safe_float_num(scoped[0].get('price')) if scoped else 0.0
    open_change_proxy = round((open_price - prev_close) / prev_close * 100, 2) if open_price > 0 else None

    if zone_longest >= 25:
        label = '横盘半小时'
        evidence = f'上板前在6%-8%区间最长横盘 {zone_longest} 分钟，累计 {zone_total} 分钟，接近北京炒家“横半小时换手板”审美。'
    elif zone_longest >= 15:
        label = '长换手'
        evidence = f'上板前在6%-8%区间最长横盘 {zone_longest} 分钟，累计 {zone_total} 分钟，换手已较充分。'
    elif zone_total >= 10:
        label = '反复换手'
        evidence = f'上板前在6%-8%区间累计停留 {zone_total} 分钟，存在一定抛压交换。'
    else:
        label = '待观察'
        evidence = f'上板前在6%-8%区间累计仅 {zone_total} 分钟，分钟级换手仍偏一般。'

    return {
        'minuteDataStatus': 'ok',
        'openChangeProxy': open_change_proxy,
        'minuteTurnoverMinutes': zone_total,
        'minuteLongestStreak': zone_longest,
        'minuteTurnoverLabel': label,
        'minuteEvidence': evidence,
    }


def _build_beijing_peer_snapshot(
    item: Dict[str, Any],
    sector_map: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    sector = str(item.get('sector') or '').strip()
    if not sector:
        return {
            'peerBoardCount': 0,
            'peerEarlyCount': 0,
            'peerSummary': '缺少明确板块队友，更多看个股自身强度。',
        }

    peers = [peer for peer in sector_map.get(sector, []) if peer.get('code') != item.get('code')]
    if not peers:
        return {
            'peerBoardCount': 0,
            'peerEarlyCount': 0,
            'peerSummary': '同板块没有明显涨停队友，板块带动偏弱。',
        }

    early_peers = [peer for peer in peers if int(peer.get('firstSealInt') or 0) and int(peer.get('firstSealInt') or 0) <= 100000]
    preview = '、'.join(peer.get('name', '') for peer in sorted(peers, key=lambda one: int(one.get('firstSealInt') or 999999))[:2] if peer.get('name'))
    if early_peers:
        summary = f'同板块有 {len(peers)} 只涨停队友，{preview or "前排队友"} 较早封板，具备带动效应。'
    else:
        summary = f'同板块有 {len(peers)} 只队友，但更像同步跟涨，带动性一般。'
    return {
        'peerBoardCount': len(peers),
        'peerEarlyCount': len(early_peers),
        'peerSummary': summary,
    }


def _beijing_heuristic_auction_strength(
    *,
    open_change_proxy: Any,
    board_type: str,
    first_seal_int: int,
) -> str:
    open_change = _safe_float_num(open_change_proxy, default=999.0)
    if board_type == '一字板' or open_change >= 8:
        return '竞价涨停'
    if open_change >= 5:
        return '竞价强势'
    if open_change >= 3:
        return '高开强势'
    if open_change <= -2:
        return '低开弱势'
    if first_seal_int and first_seal_int <= 93500:
        return '高开强势'
    if open_change != 999.0:
        return '平开待确认'
    return '待观察'


def _beijing_heuristic_teammate_strength(
    *,
    resonance_count: int,
    peer_early_count: int,
    peer_board_count: int,
) -> str:
    if resonance_count >= 3 and peer_early_count >= 1:
        return '队友强'
    if resonance_count >= 2 and peer_board_count >= 1:
        return '队友一般'
    if peer_board_count >= 1:
        return '队友弱'
    return '待观察'


def _infer_beijing_auction_teammates_with_qwen(
    items: List[Dict[str, Any]],
    *,
    search_data: str = '',
) -> Dict[str, Dict[str, Any]]:
    if not items:
        return {}

    search_hint_lines = []
    for raw_line in str(search_data or '').splitlines():
        text = str(raw_line or '').strip().lstrip('-').strip()
        if not text or text in {'---', '***'}:
            continue
        search_hint_lines.append(text)
        if len(search_hint_lines) >= 6:
            break

    prompt = (
        f"当前时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}\n"
        "你是北京炒家的盘口助手。请结合公开盘面信息和给定事实，只输出 JSON 数组，不要写任何解释。\n"
        "数组元素字段严格为：code, auctionStrength, teammateStrength, summary。\n"
        "约束：\n"
        "1. auctionStrength 只能是：竞价涨停 / 竞价强势 / 高开强势 / 平开待确认 / 低开弱势 / 待观察\n"
        "2. teammateStrength 只能是：队友强 / 队友一般 / 队友弱 / 待观察\n"
        "3. summary 控制在 18 个字以内\n"
        "4. 若公开信息不足，输出待观察，不要编造具体竞价金额。\n\n"
        f"联网补充摘要：{'; '.join(search_hint_lines) if search_hint_lines else '待观察'}\n\n"
        f"候选列表：\n{json.dumps(items, ensure_ascii=False)}"
    )

    try:
        response = _call_deepseek_search(prompt=prompt, model='qwen-plus')
        if not response.success:
            return {}
        parsed = _load_json_loose(response.content or '')
        if isinstance(parsed, dict):
            parsed = parsed.get('items') or parsed.get('data') or []
        if not isinstance(parsed, list):
            return {}

        result: Dict[str, Dict[str, Any]] = {}
        for item in parsed:
            if not isinstance(item, dict):
                continue
            code = _normalize_code6(item.get('code'))
            if not code:
                continue
            result[code] = {
                'auctionStrength': str(item.get('auctionStrength') or '').strip(),
                'teammateStrength': str(item.get('teammateStrength') or '').strip(),
                'auctionTeammateSummary': str(item.get('summary') or '').strip(),
            }
        return result
    except Exception as exc:
        logger.warning('[Beijing] Qwen 竞价/队友判断失败: %s', exc)
        return {}


def _collect_latest_scan_candidates() -> List[Dict[str, Any]]:
    latest_scan = db.get_latest_scan()
    if not latest_scan:
        return []

    candidates: List[Dict[str, Any]] = []
    results_dict = latest_scan.get('results', {}) or {}
    for sector_name, sector_data in results_dict.items():
        if not isinstance(sector_data, dict):
            continue
        for stock in sector_data.get('stocks', []) or []:
            if not isinstance(stock, dict):
                continue
            one = dict(stock)
            one['sector'] = one.get('sector') or sector_name
            one['code'] = _normalize_code6(one.get('code'))
            if one['code']:
                candidates.append(one)
    return candidates


def _load_single_agent_prompt_bundle(
    agent_id: str,
    registry,
    *,
    search_data: str = '',
    agent_execution_context: str = '',
    force_empty_scan: bool = False,
) -> Dict[str, Any]:
    from ai_service import fetch_market_news, fetch_junge_enhanced_news
    from junge_trader import format_holdings_for_prompt, format_scan_data_for_prompt

    all_stocks = _collect_latest_scan_candidates()
    latest_scan = db.get_latest_scan()
    scan_time = latest_scan.get('scan_time', '') if latest_scan else ''
    scan_date = scan_time[:10] if scan_time else datetime.now().strftime('%Y-%m-%d')

    if force_empty_scan:
        scan_data_text = ''
    else:
        try:
            scan_data_text = format_scan_data_for_prompt(all_stocks) if all_stocks else ''
        except Exception:
            scan_data_text = ''

    try:
        news_list = fetch_junge_enhanced_news(scan_date) if agent_id == 'jun' else fetch_market_news(scan_date)
        news_text = _format_news_for_batch(news_list)
    except Exception:
        news_text = '【暂无最新消息】'

    try:
        holdings_text = format_holdings_for_prompt(db.get_holdings_by_agent(agent_id))
    except Exception:
        holdings_text = '【暂无历史持仓数据】'

    current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')
    user_prompt = registry.build_user_prompt(
        agent_id=agent_id,
        scan_data=scan_data_text,
        news_data=news_text,
        holdings_data=holdings_text,
        current_time=current_time,
        scan_date=scan_date,
        extra_context={
            'search_data': search_data,
            'agent_execution_context': agent_execution_context,
        },
    )

    return {
        'all_stocks': all_stocks,
        'scan_data_text': scan_data_text,
        'news_text': news_text,
        'holdings_text': holdings_text,
        'current_time': current_time,
        'scan_date': scan_date,
        'user_prompt': user_prompt,
    }


def _parse_market_overview_metrics(overview_text: str) -> Dict[str, Any]:
    import re

    metrics = []
    for raw_line in (overview_text or '').splitlines():
        line = str(raw_line or '').strip()
        if not line:
            continue
        match = re.search(r'([+-]?\d+(?:\.\d+)?)%\)', line)
        if not match:
            continue
        name = line.split(':', 1)[0].strip()
        pct = _safe_float_num(match.group(1))
        metrics.append({'name': name, 'pct': pct})

    positive_count = sum(1 for item in metrics if item['pct'] >= 0.30)
    negative_count = sum(1 for item in metrics if item['pct'] <= -0.30)

    return {
        'metrics': metrics,
        'positiveCount': positive_count,
        'negativeCount': negative_count,
    }


def _build_beijing_market_gate(
    overview_text: str,
    search_data: str,
    *,
    today_count: int,
    qualified_count: int,
    early_count: int,
    top_industries: List[tuple],
) -> Dict[str, Any]:
    text = f"{overview_text}\n{search_data}"
    overview_metrics = _parse_market_overview_metrics(overview_text)

    positive_hits = sum(
        1 for kw in (
            '赚钱效应强', '情绪回暖', '情绪修复', '主线明确', '强修复', '市场回暖', '强势', '普涨',
        ) if kw in text
    )
    negative_hits = sum(
        1 for kw in (
            '亏钱效应扩散', '退潮', '冰点', '高位补跌', '分化明显', '弱势', '情绪退潮', '杀跌',
        ) if kw in text
    )

    score = 0
    score += 2 if today_count >= 40 else 1 if today_count >= 25 else -2
    score += 2 if early_count >= 10 else 1 if early_count >= 5 else -1
    score += 2 if qualified_count >= 4 else 1 if qualified_count >= 2 else -1
    score += 1 if top_industries and top_industries[0][1] >= 3 else 0
    score += 1 if overview_metrics['positiveCount'] > overview_metrics['negativeCount'] else -1 if overview_metrics['negativeCount'] > overview_metrics['positiveCount'] else 0
    score += min(2, positive_hits)
    score -= min(2, negative_hits)

    if score >= 4:
        status = '放行'
        action = '首板模式放行，优先题材前排与强换手回封。'
        position_cap = '3/8以内'
    elif score >= 1:
        status = '轻仓试错'
        action = '只做最强换手板或回封板，秒拉与尾盘板回避。'
        position_cap = '1/8-2/8'
    else:
        status = '空仓等待'
        action = '首板模式关闭，宁愿空仓，也不勉强出手。'
        position_cap = '0-1/16观察'

    reasons = []
    if overview_metrics['metrics']:
        reasons.append(
            '指数概况：' + ' / '.join(
                f"{item['name']}{item['pct']:+.2f}%"
                for item in overview_metrics['metrics'][:4]
            )
        )
    reasons.append(f'涨停池 {today_count} 只，10:30 前强板 {early_count} 只，三有达标 {qualified_count} 只')
    if top_industries:
        reasons.append(
            '热点板块：' + '、'.join(
                f'{sector}{count}只' for sector, count in top_industries[:3]
            )
        )
    reasons.append(f'情绪判定：{action}')

    return {
        'status': status,
        'action': action,
        'positionCap': position_cap,
        'score': score,
        'reasons': reasons,
    }


def _build_beijing_time_anchor(now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now()
    hhmm = now.hour * 100 + now.minute
    label = now.strftime('%H:%M')

    if hhmm < 925:
        return {
            'phaseCode': 'preopen',
            'phase': '盘前预备',
            'window': f'{label}｜先做预备池，不给追价指令',
            'summary': '盘前先看题材发酵、队友预期与预备池，不在竞价前主观重仓。',
            'executionFocus': '只列预备池，等待竞价确认',
            'positionBias': '不开新仓，最多观察仓',
            'rules': [
                '先看题材与队友，谁更可能卡位前排。',
                '盘前不抢买点，真正的先手要等竞价和开盘确认。',
                '把候选缩到最强 3-5 只，等 9:30 后再做动作。',
            ],
        }
    if hhmm < 930:
        return {
            'phaseCode': 'auction',
            'phase': '集合竞价',
            'window': f'{label}｜只看竞价强弱与队友表现',
            'summary': '集合竞价阶段重点看高开强弱、队友联动和主线是否继续发酵。',
            'executionFocus': '竞价确认，不提前追价',
            'positionBias': '只做竞价确认，不做无脑抢单',
            'rules': [
                '竞价强但队友弱，要防独苗冲高回落。',
                '队友强时，自己的票竞价一般也可能被板块带起来。',
                '竞价阶段只确认方向，真正下手要等开盘承接。',
            ],
        }
    if hhmm < 1000:
        return {
            'phaseCode': 'open_attack',
            'phase': '早盘抢先手',
            'window': f'{label}｜谁先板干谁，优先题材前排',
            'summary': '这是北京炒家最积极的时间窗，优先做前排强板与最早转强票。',
            'executionFocus': '前排先手 / 半路跟随',
            'positionBias': '可用标准仓位，最强票可更积极',
            'rules': [
                '优先题材前排、最早转强、板块带动性强的票。',
                '看到资金坚决点火，可以半路跟随，不必等完全封死。',
                '独苗票和弱板块票仍然谨慎，先手不等于乱追。',
            ],
        }
    if hhmm < 1030:
        return {
            'phaseCode': 'morning_confirm',
            'phase': '换手确认',
            'window': f'{label}｜核心看 6%-8% 换手与早回封',
            'summary': '最适合确认换手板、回封板和强分歧转一致，质量通常高于情绪乱点火。',
            'executionFocus': '换手板 / 回封板',
            'positionBias': '标准仓位，优先做充分换手',
            'rules': [
                '6%-8% 横住越久，越接近理想换手板。',
                '早回封优于尾盘回封，空头释放后再上板更稳。',
                '10:30 前仍是核心窗口，超过后就别乱追拖沓板。',
            ],
        }
    if hhmm < 1130:
        return {
            'phaseCode': 'late_morning',
            'phase': '上午后段',
            'window': f'{label}｜降一档仓位，只做辨识度与回封确认',
            'summary': '前排先手优势下降，后面更适合做辨识度后排、回封确认或分歧低吸。',
            'executionFocus': '辨识度后排 / 分歧低吸',
            'positionBias': '仓位降一档，不追慢板',
            'rules': [
                '不再乱追上午后段才启动的拖沓板。',
                '只做有板块、有辨识度、有承接的后排与回封。',
                '高位直线拉升宁愿错过，也不做情绪化接盘。',
            ],
        }
    if hhmm < 1300:
        return {
            'phaseCode': 'lunch',
            'phase': '午间观察',
            'window': f'{label}｜整理预案，不做主动进攻',
            'summary': '午间阶段不做新开仓，重点是复核板池、承接与下午回流方向。',
            'executionFocus': '观察 / 复核',
            'positionBias': '不开新仓',
            'rules': [
                '复核上午最强题材是否具备下午回流条件。',
                '整理卖出预案和下午重点票，不凭情绪乱追。',
                '午间没有新的确定性买点，耐心比出手更重要。',
            ],
        }
    if hhmm < 1400:
        return {
            'phaseCode': 'afternoon',
            'phase': '午后回流',
            'window': f'{label}｜只做回流、回封与辨识度低吸',
            'summary': '午后主要看主线回流、强回封和辨识度票，不做无脑追高。',
            'executionFocus': '回流确认 / 低吸跟随',
            'positionBias': '轻一档仓位',
            'rules': [
                '只做主线回流，不做边角题材补涨。',
                '更适合低吸或回封确认，不适合盲目追秒板。',
                '队友掉队、板块散乱时宁愿不做。',
            ],
        }
    if hhmm < 1430:
        return {
            'phaseCode': 'tail_guard',
            'phase': '尾盘谨慎',
            'window': f'{label}｜尾盘板风险抬升，观察优先',
            'summary': '2 点后越往后越像偷鸡阶段，只考虑极少数高确定性补票。',
            'executionFocus': '观察为主 / 极少数确认点',
            'positionBias': '极轻仓或观察',
            'rules': [
                '尾盘板不是主战场，封不住就是最高点接盘。',
                '若要出手，也只做强回封和绝对主线。',
                '大多数情况下，留现金比抢最后一板更重要。',
            ],
        }
    if hhmm < 1505:
        return {
            'phaseCode': 'tail_avoid',
            'phase': '尾盘回避',
            'window': f'{label}｜2点半后原则上不再新开',
            'summary': '2 点半以后更偏投机和偷鸡，重点转向卖出与次日剧本，不再新开仓。',
            'executionFocus': '不新开 / 卖出预案',
            'positionBias': '0-1/16 观察',
            'rules': [
                '2 点半后新开仓的赔率显著变差。',
                '把精力放在持仓处理和次日卖法，不去接最后一棒。',
                '除非极少数绝对核心回封，否则默认放弃。',
            ],
        }
    return {
        'phaseCode': 'after_close',
        'phase': '收盘复核',
        'window': f'{label}｜收盘后只做复核与次日预案',
        'summary': '收盘后不再给盘中追价建议，重点复核板池、队友与次日卖出预案。',
        'executionFocus': '复核 / 预案',
        'positionBias': '不开新仓',
        'rules': [
            '复核最强题材、前排顺序与后排辨识度。',
            '整理次日卖法，不脑补隔夜神话。',
            '把买点留给下一个真实盘中确认，而不是收盘后幻想。',
        ],
    }


def _classify_beijing_board_type(row: Dict[str, Any], yesterday_row: Optional[Dict[str, Any]] = None) -> str:
    first_seal = _clock_to_int(row.get('首次封板时间'))
    last_seal = _clock_to_int(row.get('最后封板时间') or row.get('首次封板时间'))
    broken_count = _safe_int_num(row.get('炸板次数'))
    consecutive = _safe_int_num(row.get('连板数') or (yesterday_row or {}).get('昨日连板数'))
    turnover_rate = _safe_float_num(row.get('换手率'))

    if first_seal == 92500 and last_seal == 92500 and broken_count == 0:
        return '一字板'
    if last_seal >= 140000:
        return '尾盘板'
    if consecutive >= 2 and first_seal and first_seal <= 103000:
        return '连板'
    if broken_count > 0:
        return '回封板'
    if first_seal and first_seal <= 93500 and turnover_rate < 5:
        return '秒拉板'
    return '换手板'


def _beijing_selection_type(
    *,
    board_type: str,
    resonance_count: int,
    first_seal_int: int,
    mkt_cap_yi: float,
    turnover_yi: float,
    turnover_rate: float,
    seal_amount_yi: float,
    scan_row: Dict[str, Any],
    consecutive_days: int,
) -> tuple:
    is_first_board = consecutive_days <= 1
    front_row = bool(first_seal_int and first_seal_int <= 100000 and resonance_count >= 2)
    recognition_high = bool(scan_row) or mkt_cap_yi >= 60 or turnover_yi >= 10 or seal_amount_yi >= 2 or turnover_rate >= 8

    if board_type == '连板':
        return '换手连板', '只做有板块效应、10:30前完成换手的最强连板', front_row
    if is_first_board and front_row:
        return '板块前排首板', '题材先手最重要，优先做最先上板的前排强票', True
    if is_first_board and resonance_count >= 2 and recognition_high:
        return '后排辨识度首板', '错过前排后，优先容量、封单或评分更强的辨识度后排', False
    if resonance_count <= 1 and (turnover_yi >= 8 or turnover_rate >= 6):
        return '独立图形票', '没有板块时，只做自己看得懂的独立强势图形', False
    return '普通跟随', '不在最优审美区间，只能低仓位观察或放弃', False


def _beijing_buy_method(board_type: str, *, front_row: bool = False, pass_count: int = 0) -> str:
    if board_type in ('一字板', '尾盘板'):
        return '观察'
    if board_type in ('换手板', '回封板'):
        return '扫板'
    if board_type == '秒拉板':
        return '扫板' if front_row and pass_count >= 2 else '排板'
    if board_type == '连板':
        return '扫板' if front_row and pass_count >= 3 else '排板'
    return '观察'


def _beijing_position_ratio(
    code: str,
    board_type: str,
    pass_count: int,
    *,
    gate_status: str = '轻仓试错',
    front_row: bool = False,
) -> str:
    if board_type in ('一字板', '尾盘板') or gate_status == '空仓等待':
        return '0仓观察'
    if str(code).startswith(('30', '68')):
        return '1/16仓'
    if gate_status == '放行' and front_row and pass_count >= 2 and board_type in ('换手板', '回封板', '秒拉板'):
        return '1/6仓'
    if gate_status == '放行' and pass_count >= 2:
        return '1/8仓'
    return '1/16仓'


def _beijing_hold_period(board_type: str, *, front_row: bool = False) -> str:
    if board_type == '连板':
        return '只给首小时弱转强窗口'
    if board_type == '回封板':
        return '次日看是否继续走强，弱则走'
    if board_type == '换手板':
        return '次日冲高不板就兑现'
    if board_type == '秒拉板':
        return '竞价不及预期先减仓'
    return '仅观察，不主动隔夜追价'


def _beijing_buy_range(board_type: str, *, front_row: bool = False) -> str:
    if board_type == '回封板':
        return '炸板后即将回封涨停时扫板'
    if board_type == '换手板':
        return '6%-8%充分换手后上板介入'
    if board_type == '连板':
        return '10:30前放量换手确认后参与'
    if board_type == '秒拉板':
        return '板块共振强时扫板，否则排板'
    if board_type == '一字板':
        return '只看开板后的T字回封'
    return '仅观察，不主动追价'


def _beijing_stop_loss(board_type: str) -> str:
    if board_type in ('尾盘板', '一字板'):
        return '不参与，无需设置'
    if board_type == '回封板':
        return '炸板未回封就走，次日回抽不涨立卖'
    if board_type == '秒拉板':
        return '竞价转弱或开盘翻绿立刻撤'
    return '高开低走、低开低走反抽、跌停必走'


def _beijing_next_day_sell_plan(board_type: str, *, front_row: bool = False) -> str:
    if board_type == '连板':
        return '看9:45-10:00是否弱转强，不转强就兑现'
    if board_type == '回封板':
        return '高开冲高不板先卖，低开反抽无力立走'
    if board_type == '换手板':
        return '高开低于2%要谨慎，冲高不板或翻绿即走'
    if board_type == '秒拉板':
        return '竞价不及预期直接减，封板次日优先兑现'
    if board_type == '一字板':
        return '除非开板后再度转强，否则不追不留'
    return '尾盘偷板次日不幻想，先保命再说'


def _beijing_scan_selection_type(
    *,
    sector_heat: int,
    pct_change: float,
    score: int,
    market_cap_yi: float,
    sector_rank: int = 999,
) -> str:
    if sector_heat >= 2 and sector_rank <= 2 and pct_change >= 2.0:
        return '板块前排预备'
    if sector_heat >= 2 and sector_rank <= 5 and (score >= 78 or market_cap_yi >= 50):
        return '后排辨识度预备'
    if score >= 78 and market_cap_yi >= 20:
        return '独立图形票'
    return '普通观察'


def _beijing_actionable_setup(
    *,
    pct_change: float,
    volume_ratio: float,
    gate_status: str,
    time_anchor: Optional[Dict[str, Any]] = None,
    sector_heat: int = 0,
    score: int = 0,
) -> Dict[str, str]:
    phase_code = str((time_anchor or {}).get('phaseCode') or '').strip()

    if gate_status == '空仓等待':
        return {
            'tradeStatus': '仅观察',
            'buyMethod': '观察',
            'entryPlan': '等待',
            'entryModel': '空仓等待',
            'entryTrigger': '闸门未开，不做主动进攻。',
        }

    if phase_code in {'preopen', 'auction'}:
        if pct_change >= 0 or volume_ratio >= 1.2:
            return {
                'tradeStatus': '竞价确认',
                'buyMethod': '观察',
                'entryPlan': '竞价确认',
                'entryModel': '竞价强弱确认',
                'entryTrigger': '先看9:25-9:30强弱与队友，真正动作等开盘后承接确认。',
            }
        return {
            'tradeStatus': '仅观察',
            'buyMethod': '观察',
            'entryPlan': '等待',
            'entryModel': '盘前预备',
            'entryTrigger': '盘前阶段优先做预备池，不给主观追价指令。',
        }

    if phase_code == 'after_close':
        if pct_change >= 0 or volume_ratio >= 1.1:
            return {
                'tradeStatus': '竞价确认',
                'buyMethod': '观察',
                'entryPlan': '次日竞价确认',
                'entryModel': '次日竞价确认',
                'entryTrigger': '次日 9:25 先看竞价和队友，再决定是否跟随，不做收盘后意淫追价。',
            }
        return {
            'tradeStatus': '仅观察',
            'buyMethod': '观察',
            'entryPlan': '等待',
            'entryModel': '收盘复核',
            'entryTrigger': '收盘后只做预案与过滤，不给主观追价指令。',
        }

    if phase_code in {'lunch', 'tail_avoid'}:
        return {
            'tradeStatus': '仅观察',
            'buyMethod': '观察',
            'entryPlan': '等待',
            'entryModel': '时段回避',
            'entryTrigger': '当前时间窗不适合主动开新仓，优先复核与卖出预案。',
        }

    if phase_code == 'tail_guard':
        if 0.0 <= pct_change < 3.0 and volume_ratio >= 1.2:
            return {
                'tradeStatus': '可低吸',
                'buyMethod': '低吸',
                'entryPlan': '尾盘低吸',
                'entryModel': '均线回踩承接',
                'entryTrigger': '只在绝对主线、承接清晰时轻仓低吸，不能追最后一板。',
            }
        return {
            'tradeStatus': '仅观察',
            'buyMethod': '观察',
            'entryPlan': '等待',
            'entryModel': '尾盘回避',
            'entryTrigger': '2点后风险显著抬升，宁愿错过也别乱追。',
        }

    if phase_code in {'late_morning', 'afternoon'}:
        if 5.0 <= pct_change < 8.8 and volume_ratio >= 1.6 and sector_heat >= 2:
            return {
                'tradeStatus': '可半路',
                'buyMethod': '半路',
                'entryPlan': '回流半路',
                'entryModel': '分时前高突破',
                'entryTrigger': '板块回流后再次越过分时前高，且量能继续放大时跟随。',
            }
        if 0.5 <= pct_change < 4.8 and volume_ratio >= 1.1:
            return {
                'tradeStatus': '可低吸',
                'buyMethod': '低吸',
                'entryPlan': '分歧低吸',
                'entryModel': '均线回踩承接',
                'entryTrigger': '回踩分时均线或关键承接位不破，再次拐头时分批跟随。',
            }
        if -1.5 <= pct_change < 0.5:
            return {
                'tradeStatus': '可埋伏',
                'buyMethod': '低吸',
                'entryPlan': '小仓预埋',
                'entryModel': '均线回踩承接',
                'entryTrigger': '只对主线辨识度票做小仓预埋，等回流确认再加。',
            }
        return {
            'tradeStatus': '仅观察',
            'buyMethod': '观察',
            'entryPlan': '等待',
            'entryModel': '等待确认',
            'entryTrigger': '当前位置更像追高或拖沓震荡，不是理想买点。',
        }

    if 6.0 <= pct_change < 9.4 and volume_ratio >= 1.8 and sector_heat >= 2 and score >= 74:
        return {
            'tradeStatus': '可半路',
            'buyMethod': '半路',
            'entryPlan': '前高突破',
            'entryModel': '分时前高突破',
            'entryTrigger': '放量上冲后再过分时前高，且板块没有掉队时跟随。',
        }
    if 3.0 <= pct_change < 7.5 and volume_ratio >= 1.3:
        return {
            'tradeStatus': '可半路',
            'buyMethod': '半路',
            'entryPlan': '放量半路',
            'entryModel': '分时前高突破',
            'entryTrigger': '量比继续抬升、分时突破前高且板块不掉队时跟随。',
        }
    if 0.8 <= pct_change < 4.5:
        return {
            'tradeStatus': '可低吸',
            'buyMethod': '低吸',
            'entryPlan': '分歧低吸',
            'entryModel': '均线回踩承接',
            'entryTrigger': '回踩分时均线或昨高不破，承接稳定后分批跟随。',
        }
    if -1.5 <= pct_change < 1.0:
        return {
            'tradeStatus': '可埋伏',
            'buyMethod': '低吸',
            'entryPlan': '小仓预埋',
            'entryModel': '均线回踩承接',
            'entryTrigger': '先小仓埋伏，等板块继续发酵、量能抬升后再加。',
        }
    return {
        'tradeStatus': '仅观察',
        'buyMethod': '观察',
        'entryPlan': '等待',
        'entryModel': '等待确认',
        'entryTrigger': '涨幅位置或节奏不理想，先不着急动手。',
    }


def _beijing_actionable_position_ratio(
    *,
    code: str,
    trade_status: str,
    gate_status: str,
    score: int,
    sector_heat: int,
) -> str:
    if gate_status == '空仓等待' or trade_status == '仅观察':
        return '0-1/16观察'
    if str(code).startswith(('30', '68')):
        return '1/16仓'
    if trade_status == '可半路' and gate_status == '放行' and score >= 78 and sector_heat >= 3:
        return '1/6仓'
    if trade_status in ('可半路', '可低吸'):
        return '1/8仓'
    return '1/16仓'


def _beijing_actionable_labels(
    *,
    selection_type: str,
    trade_status: str,
    sector_heat: int,
    volume_ratio: float,
    score: int,
) -> List[str]:
    labels: List[str] = []
    if selection_type:
        labels.append(selection_type)
    if trade_status == '可半路':
        labels.append('盘中可买')
        labels.append('放量半路')
    elif trade_status == '可低吸':
        labels.append('盘中可买')
        labels.append('分歧低吸')
    elif trade_status == '可埋伏':
        labels.append('预埋伏')
    if sector_heat >= 3:
        labels.append('板块联动')
    if volume_ratio >= 1.5:
        labels.append('量比抬升')
    if score >= 80:
        labels.append('高分命中')

    seen = set()
    deduped: List[str] = []
    for label in labels:
        text = str(label or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped[:6]


def _beijing_selection_type_detail(selection_type: str) -> str:
    mapping = {
        '板块前排首板': '题材前排与先手优先，谁先板干谁。',
        '后排辨识度首板': '错过前排后，优先做容量、逻辑、图形更强的辨识度后排。',
        '换手连板': '只做有板块效应、10:30 前完成换手的强连板。',
        '独立图形票': '没有板块时，只做看得懂的独立强图形。',
        '板块前排预备': '虽然未上板，但已具备题材前排和先手特征，可先纳入盘中预备池。',
        '后排辨识度预备': '错过前排后，保留仍可参与的辨识度后排。',
    }
    return mapping.get(selection_type, '当前仍需继续观察题材地位与辨识度。')


def _beijing_entry_model_for_board(
    *,
    board_type: str,
    minute_turnover_label: str,
    broken_count: int,
    front_row: bool,
) -> str:
    if board_type == '回封板' or broken_count > 0:
        return '回封确认'
    if board_type == '换手板':
        if minute_turnover_label in {'横盘半小时', '长换手'}:
            return '分时前高突破'
        return '均线回踩承接'
    if board_type == '秒拉板':
        return '分时前高突破'
    if board_type == '连板':
        return '强更强确认'
    if board_type == '尾盘板':
        return '尾盘回避'
    if board_type == '一字板':
        return '只看T字回封'
    return '待观察'


def _beijing_matched_rules(
    item: Dict[str, Any],
    *,
    market_gate: Dict[str, Any],
    time_anchor: Dict[str, Any],
    is_actionable: bool = False,
) -> List[Dict[str, str]]:
    rules: List[Dict[str, str]] = []

    phase = str(time_anchor.get('phase') or '当前时段').strip()
    execution_focus = str(time_anchor.get('executionFocus') or '看最强票').strip()
    rules.append({
        'title': '时间锚定',
        'detail': f'{phase}阶段优先{execution_focus}，不是全天都用同一套打法。',
    })

    selection_type = str(item.get('selectionType') or '').strip()
    if selection_type:
        rules.append({
            'title': '选股路径',
            'detail': _beijing_selection_type_detail(selection_type),
        })

    entry_model = str(item.get('entryModel') or '').strip()
    entry_trigger = str(item.get('entryTrigger') or '').strip()
    if entry_model or entry_trigger:
        detail = entry_model or '待观察'
        if entry_trigger:
            detail = f'{detail}：{entry_trigger}'
        rules.append({
            'title': '入场模型',
            'detail': detail,
        })

    if is_actionable:
        sector_heat = int(item.get('sectorHeat') or 0)
        score = int(item.get('score') or 0)
        volume_ratio = float(item.get('volumeRatio') or 0)
        rules.append({
            'title': '盘中可买',
            'detail': (
                f"{item.get('tradeStatus','待观察')}，评分 {score}，板块热度 {sector_heat}，"
                f"量比 {volume_ratio:.2f}。"
            ),
        })
    else:
        minute_turnover = str(item.get('minuteTurnoverLabel') or '').strip()
        minute_evidence = str(item.get('minuteEvidence') or '').strip()
        board_type = str(item.get('boardType') or '').strip()
        if board_type == '回封板' or int(item.get('brokenBoardCount') or 0) > 0:
            rules.append({
                'title': '回封更稳',
                'detail': item.get('classificationReason') or '炸板后回封代表空头释放，早回封优于尾盘回封。',
            })
        elif minute_turnover and minute_turnover != '待观察':
            rules.append({
                'title': '换手证据',
                'detail': minute_evidence or f'{minute_turnover}，更接近理想换手板审美。',
            })

        auction_strength = str(item.get('auctionStrength') or '').strip()
        teammate_strength = str(item.get('teammateStrength') or '').strip()
        if auction_strength or teammate_strength:
            rules.append({
                'title': '竞价与队友',
                'detail': item.get('auctionTeammateSummary') or f'{auction_strength} / {teammate_strength}',
            })

    position_ratio = str(item.get('positionRatio') or '').strip()
    stop_loss = str(item.get('stopLoss') or '').strip()
    gate_status = str(market_gate.get('status') or '待观察').strip()
    if position_ratio or stop_loss:
        risk_text = f'闸门{gate_status}，仓位 {position_ratio or "待观察"}。'
        if stop_loss:
            risk_text = f'{risk_text} {stop_loss}'
        rules.append({
            'title': '仓位风控',
            'detail': risk_text,
        })

    deduped: List[Dict[str, str]] = []
    seen = set()
    for one in rules:
        title = str(one.get('title') or '').strip()
        detail = str(one.get('detail') or '').strip()
        if not title or not detail:
            continue
        key = (title, detail)
        if key in seen:
            continue
        seen.add(key)
        deduped.append({'title': title, 'detail': detail})
    return deduped[:5]


def _beijing_refresh_actionable_candidates(
    candidates: List[Dict[str, Any]],
    *,
    market_gate: Dict[str, Any],
    time_anchor: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """用实时行情刷新预备池，避免扫描快照和展示/标签错位。"""
    if not candidates:
        return []

    for item in candidates:
        code = _normalize_code6(item.get('code'))
        if not code:
            continue
        quote = _get_quote_with_fallback(code)
        if not quote:
            continue
        close_price = _safe_float_num(quote.get('close'))
        pct_change = _safe_float_num(quote.get('pct_change'))
        if close_price > 0:
            item['price'] = round(close_price, 2)
        item['changePct'] = round(pct_change, 2)

    sector_members: Dict[str, List[Dict[str, Any]]] = {}
    for item in candidates:
        sector = str(item.get('sector') or '').strip()
        if sector:
            sector_members.setdefault(sector, []).append(item)

    sector_rank_map: Dict[str, int] = {}
    for sector, members in sector_members.items():
        ranked = sorted(
            members,
            key=lambda one: (
                _safe_float_num(one.get('changePct')),
                _safe_float_num(one.get('score')),
                _safe_float_num(one.get('volumeRatio')),
            ),
            reverse=True,
        )
        for idx, one in enumerate(ranked, 1):
            code = _normalize_code6(one.get('code'))
            if code:
                sector_rank_map[code] = idx

    refreshed: List[Dict[str, Any]] = []
    gate_status = str(market_gate.get('status') or '轻仓试错')
    action_priority = {
        '可半路': 5,
        '可低吸': 4,
        '可埋伏': 3,
        '竞价确认': 2,
        '仅观察': 0,
    }
    for item in candidates:
        code = _normalize_code6(item.get('code'))
        pct_change = round(_safe_float_num(item.get('changePct')), 2)
        volume_ratio = round(_safe_float_num(item.get('volumeRatio')), 2)
        score = int(item.get('score') or 0)
        sector_heat = int(item.get('sectorHeat') or 0)
        sector_rank = int(sector_rank_map.get(code, item.get('sectorRank') or 999))
        market_cap_yi = _safe_float_num(item.get('marketCapYi') or 0)

        # 实时表现明显转弱或已经封死的，不再当成“可买预备池”。
        if pct_change <= -3.0 or pct_change >= 9.4:
            continue

        setup = _beijing_actionable_setup(
            pct_change=pct_change,
            volume_ratio=volume_ratio,
            gate_status=gate_status,
            time_anchor=time_anchor,
            sector_heat=sector_heat,
            score=score,
        )
        trade_status = setup.get('tradeStatus') or '仅观察'
        if trade_status == '仅观察':
            continue

        selection_type = _beijing_scan_selection_type(
            sector_heat=sector_heat,
            pct_change=pct_change,
            score=score,
            market_cap_yi=market_cap_yi,
            sector_rank=sector_rank,
        )
        position_ratio = _beijing_actionable_position_ratio(
            code=code,
            trade_status=trade_status,
            gate_status=gate_status,
            score=score,
            sector_heat=sector_heat,
        )
        labels = _beijing_actionable_labels(
            selection_type=selection_type,
            trade_status=trade_status,
            sector_heat=sector_heat,
            volume_ratio=volume_ratio,
            score=score,
        )
        actionable_now = trade_status in {'可半路', '可低吸', '可埋伏'} and time_anchor.get('phaseCode') not in {
            'preopen', 'auction', 'lunch', 'tail_avoid', 'after_close',
        }

        item.update({
            'selectionType': selection_type,
            'tradeStatus': trade_status,
            'buyMethod': setup.get('buyMethod', '观察'),
            'entryPlan': setup.get('entryPlan', ''),
            'entryModel': setup.get('entryModel', ''),
            'entryTrigger': setup.get('entryTrigger', ''),
            'positionRatio': position_ratio,
            'labels': labels,
            'signal': f"{selection_type}/{trade_status}/{setup.get('buyMethod', '观察')}",
            'actionableNow': actionable_now,
            'sectorRank': sector_rank,
            'classificationReason': (
                f"{time_anchor.get('phase', '当前时段')}优先做{setup.get('entryPlan', '待观察')}，"
                f"当前涨幅 {pct_change:+.2f}%，量比 {volume_ratio:.2f}。"
            ),
            'reason': (
                f"{selection_type}｜{time_anchor.get('phase', '当前时段')}｜{trade_status}｜"
                f"板块热度 {sector_heat}，板块排序 #{sector_rank}，评分 {score}，更适合 {setup.get('entryPlan', '待观察')}。"
            ),
            'meta': (
                f"当前涨幅 {pct_change:+.2f}%｜量比 {volume_ratio:.2f}｜评分 {score}｜"
                f"板块热度 {sector_heat}｜时段 {time_anchor.get('phase', '待观察')}"
            ),
        })
        refreshed.append(item)

    refreshed.sort(
        key=lambda item: (
            1 if item.get('actionableNow') else 0,
            action_priority.get(str(item.get('tradeStatus') or ''), 0),
            -int(item.get('sectorRank') or 999),
            1 if item.get('selectionType') == '板块前排预备' else 0,
            float(item.get('sectorHeat') or 0),
            float(item.get('score') or 0),
            float(item.get('changePct') or 0),
        ),
        reverse=True,
    )
    return refreshed


def _beijing_method_labels(
    *,
    board_type: str,
    selection_type: str,
    gate_status: str,
    first_seal_int: int,
    last_seal_int: int,
    broken_count: int,
    resonance_count: int,
    turnover_rate: float,
    turnover_yi: float,
    mkt_cap_yi: float,
    front_row: bool,
    minute_turnover_label: str = '',
    minute_longest_streak: int = 0,
    auction_strength: str = '',
    teammate_strength: str = '',
) -> List[str]:
    labels: List[str] = []

    if selection_type:
        labels.append(selection_type)
    if front_row:
        labels.append('前排先手')
    elif selection_type == '后排辨识度首板':
        labels.append('辨识度后排')

    if gate_status == '轻仓试错':
        labels.append('轻仓试错')
    elif gate_status == '空仓等待':
        labels.append('空仓优先')

    if resonance_count >= 3:
        labels.append('板块联动')
    elif board_type == '秒拉板':
        labels.append('独苗秒板风险')

    if mkt_cap_yi >= 80 or turnover_yi >= 20:
        labels.append('大容量')

    if minute_turnover_label == '横盘半小时':
        labels.append('横盘半小时')
    elif minute_turnover_label == '长换手':
        labels.append('长换手')
    elif minute_turnover_label == '反复换手':
        labels.append('反复换手')

    if minute_longest_streak >= 25:
        labels.append('6-8换手充分')

    if auction_strength in ('竞价涨停', '竞价强势', '高开强势'):
        labels.append(auction_strength)
    elif auction_strength == '低开弱势':
        labels.append('竞价偏弱')

    if teammate_strength == '队友强':
        labels.append('队友带动')
    elif teammate_strength == '队友弱':
        labels.append('队友偏弱')

    if board_type == '换手板':
        labels.extend(['换手板优先', '可直接扫板'])
        if turnover_rate >= 8:
            labels.append('换手充分')
        if minute_longest_streak >= 25:
            labels.append('横盘后上板')
        elif 100000 <= first_seal_int <= 110000:
            labels.append('疑似长换手')
    elif board_type == '回封板':
        labels.extend(['回封更稳', '空头释放'])
        if broken_count >= 1:
            labels.append('炸板后回封')
        if last_seal_int and last_seal_int <= 110000:
            labels.append('早回封优先')
    elif board_type == '秒拉板':
        labels.extend(['秒板新手回避', '仅排不扫'])
        if front_row or resonance_count >= 3:
            labels.append('板块先锋')
    elif board_type == '连板':
        labels.extend(['换手连板', '只做强更强'])
        if first_seal_int and first_seal_int <= 103000:
            labels.append('10:30前连板')
    elif board_type == '一字板':
        labels.extend(['一字不追', '只看T字回封'])
    elif board_type == '尾盘板':
        labels.append('尾盘慎打')
        if last_seal_int >= 143000:
            labels.append('2点半投机板')
        elif last_seal_int >= 140000:
            labels.append('2点后少打')

    seen = set()
    deduped: List[str] = []
    for one in labels:
        text = str(one or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped[:6]


def _build_beijing_execution_artifacts(search_data: str = '', overview_text: str = '') -> Dict[str, Any]:
    from market_data import _ak_eastmoney_direct, _get_ak

    today = datetime.now().strftime('%Y%m%d')
    today_df = _pd.DataFrame()
    yesterday_df = _pd.DataFrame()
    yesterday_date = ''

    try:
        with _ak_eastmoney_direct():
            today_df = _get_ak().stock_zt_pool_em(date=today)
    except Exception as exc:
        logger.warning('[Beijing] 今日涨停池获取失败: %s', exc)

    for delta in range(1, 8):
        probe_date = (datetime.now() - timedelta(days=delta)).strftime('%Y%m%d')
        try:
            with _ak_eastmoney_direct():
                probe_df = _get_ak().stock_zt_pool_previous_em(date=probe_date)
            if probe_df is not None and not probe_df.empty:
                yesterday_df = probe_df
                yesterday_date = probe_date
                break
        except Exception as exc:
            logger.debug('[Beijing] 昨日涨停池探测失败 date=%s err=%s', probe_date, exc)

    scan_candidates = _collect_latest_scan_candidates()
    scan_map = {_normalize_code6(item.get('code')): item for item in scan_candidates}
    yesterday_map = {}
    if yesterday_df is not None and not yesterday_df.empty:
        for _, row in yesterday_df.iterrows():
            row_dict = row.to_dict()
            yesterday_map[_normalize_code6(row_dict.get('代码'))] = row_dict

    industry_counts: Dict[str, int] = {}
    if today_df is not None and not today_df.empty:
        for _, row in today_df.iterrows():
            sector = str(row.get('所属行业') or '').strip()
            if sector:
                industry_counts[sector] = industry_counts.get(sector, 0) + 1

    board_priority = {
        '换手板': 5,
        '回封板': 4,
        '秒拉板': 3,
        '连板': 3,
        '一字板': 1,
        '尾盘板': 0,
    }

    board_candidates: List[Dict[str, Any]] = []
    if today_df is not None and not today_df.empty:
        for _, row in today_df.iterrows():
            row_dict = row.to_dict()
            code = _normalize_code6(row_dict.get('代码'))
            if not code:
                continue

            scan_row = scan_map.get(code, {})
            yesterday_row = yesterday_map.get(code, {})
            sector = str(row_dict.get('所属行业') or scan_row.get('sector') or '').strip()
            resonance_count = industry_counts.get(sector, 0) if sector else 0
            turnover_yi = _to_yi(row_dict.get('成交额'))
            mkt_cap_yi = _to_yi(row_dict.get('流通市值'))
            turnover_rate = _safe_float_num(row_dict.get('换手率'))
            seal_amount_yi = _to_yi(row_dict.get('封板资金'))
            volume_ratio = _safe_float_num(
                scan_row.get('volume_ratio')
                if scan_row.get('volume_ratio') is not None
                else scan_row.get('volumeRatio')
            )
            first_seal_int = _clock_to_int(row_dict.get('首次封板时间'))
            first_seal = _format_clock_hhmm(row_dict.get('首次封板时间'))
            last_seal = _format_clock_hhmm(row_dict.get('最后封板时间') or row_dict.get('首次封板时间'))
            broken_count = _safe_int_num(row_dict.get('炸板次数'))
            consecutive_days = _safe_int_num(row_dict.get('连板数') or yesterday_row.get('昨日连板数') or 1)
            board_type = _classify_beijing_board_type(row_dict, yesterday_row)

            have_resonance = resonance_count >= 3
            have_liquidity = 20 <= mkt_cap_yi <= 200 and turnover_yi >= 5
            have_timing = bool(first_seal_int and first_seal_int <= 103000 and (volume_ratio >= 3 or turnover_rate >= 3))
            passed = []
            if have_resonance:
                passed.append('板块共振')
            if have_liquidity:
                passed.append('市值流动性')
            if have_timing:
                passed.append('量价时间')
            pass_count = len(passed)
            selection_type, recognition_reason, front_row = _beijing_selection_type(
                board_type=board_type,
                resonance_count=resonance_count,
                first_seal_int=first_seal_int,
                mkt_cap_yi=mkt_cap_yi,
                turnover_yi=turnover_yi,
                turnover_rate=turnover_rate,
                seal_amount_yi=seal_amount_yi,
                scan_row=scan_row,
                consecutive_days=consecutive_days,
            )

            if board_type == '回封板':
                classification_reason = f'炸板 {broken_count} 次后回封，空头二次释放。'
            elif board_type == '换手板':
                classification_reason = f'首封 {first_seal}，换手率 {turnover_rate:.1f}%，更偏换手确认。'
            elif board_type == '秒拉板':
                classification_reason = f'首封 {first_seal} 较早，快速上板，需板块共振确认。'
            elif board_type == '连板':
                classification_reason = f'当前连板 {consecutive_days}，前排强度明确。'
            elif board_type == '一字板':
                classification_reason = '竞价或开盘即一字封死，仅看不追。'
            else:
                classification_reason = f'末封 {last_seal} 偏晚，尾盘博弈属性重。'

            score = int(
                scan_row.get('score')
                or scan_row.get('total_score')
                or min(99, 56 + pass_count * 10 + board_priority.get(board_type, 0) * 4 + (8 if scan_row else 0))
            )
            grade = str(scan_row.get('grade') or ('S' if pass_count == 3 else 'A' if pass_count == 2 else 'B'))

            meta_parts = [
                f'首封 {first_seal}',
                f'末封 {last_seal}',
                f'炸板 {broken_count} 次',
                f'封板资金 {seal_amount_yi:.2f} 亿' if seal_amount_yi > 0 else '封板资金 待观察',
                f'流通市值 {mkt_cap_yi:.1f} 亿' if mkt_cap_yi > 0 else '流通市值 待观察',
            ]
            if volume_ratio > 0:
                meta_parts.append(f'量比 {volume_ratio:.2f}')
            elif turnover_rate > 0:
                meta_parts.append(f'换手率 {turnover_rate:.2f}%')

            board_candidates.append({
                'code': code,
                'name': str(row_dict.get('名称') or scan_row.get('name') or code),
                'sector': sector or str(scan_row.get('sector') or ''),
                'price': round(_safe_float_num(row_dict.get('最新价')), 2),
                'changePct': round(_safe_float_num(row_dict.get('涨跌幅')), 2),
                'score': score,
                'grade': grade,
                'boardType': board_type,
                'threeHaveSummary': f'{pass_count}/3通过' + (f'（{" + ".join(passed)}）' if passed else '（待补验证）'),
                'threeHavePassed': passed,
                'passCount': pass_count,
                'firstSealTime': first_seal,
                'lastSealTime': last_seal,
                'firstSealInt': first_seal_int,
                'lastSealInt': _clock_to_int(row_dict.get('最后封板时间') or row_dict.get('首次封板时间')),
                'brokenBoardCount': broken_count,
                'consecutiveLimitUpDays': consecutive_days,
                'sealAmountYi': seal_amount_yi,
                'turnoverYi': turnover_yi,
                'marketCapYi': mkt_cap_yi,
                'turnoverRate': round(turnover_rate, 2),
                'volumeRatio': round(volume_ratio, 2) if volume_ratio > 0 else 0,
                'resonanceCount': resonance_count,
                'scanMatched': bool(scan_row),
                'selectionType': selection_type,
                'recognitionReason': recognition_reason,
                'frontRow': front_row,
                'isFirstBoard': consecutive_days <= 1,
                'classificationReason': classification_reason,
                'metaParts': meta_parts,
            })

    sector_map: Dict[str, List[Dict[str, Any]]] = {}
    for item in board_candidates:
        sector = str(item.get('sector') or '').strip()
        if not sector:
            continue
        sector_map.setdefault(sector, []).append(item)

    pre_ranked = sorted(
        board_candidates,
        key=lambda item: (
            1 if item.get('frontRow') else 0,
            1 if item.get('isFirstBoard') else 0,
            int(item.get('passCount') or 0),
            board_priority.get(item.get('boardType', ''), 0),
            int(item.get('resonanceCount') or 0),
            float(item.get('sealAmountYi') or 0),
            float(item.get('score') or 0),
        ),
        reverse=True,
    )
    enrich_targets = pre_ranked[:10]
    for item in enrich_targets:
        item.update(_analyze_beijing_minute_evidence(
            item.get('code', ''),
            latest_price=item.get('price'),
            change_pct=item.get('changePct'),
            first_seal_int=int(item.get('firstSealInt') or 0),
        ))
        item.update(_build_beijing_peer_snapshot(item, sector_map))

    qwen_inputs = []
    for item in enrich_targets[:8]:
        qwen_inputs.append({
            'code': item.get('code'),
            'name': item.get('name'),
            'sector': item.get('sector'),
            'boardType': item.get('boardType'),
            'selectionType': item.get('selectionType'),
            'firstSealTime': item.get('firstSealTime'),
            'resonanceCount': item.get('resonanceCount'),
            'openChangeProxy': item.get('openChangeProxy'),
            'minuteTurnoverLabel': item.get('minuteTurnoverLabel'),
            'minuteEvidence': item.get('minuteEvidence'),
            'peerSummary': item.get('peerSummary'),
        })
    qwen_judgements = _infer_beijing_auction_teammates_with_qwen(qwen_inputs, search_data=search_data)

    for item in board_candidates:
        qwen_meta = qwen_judgements.get(item.get('code', ''), {})
        auction_strength = qwen_meta.get('auctionStrength') or _beijing_heuristic_auction_strength(
            open_change_proxy=item.get('openChangeProxy'),
            board_type=item.get('boardType', ''),
            first_seal_int=int(item.get('firstSealInt') or 0),
        )
        teammate_strength = qwen_meta.get('teammateStrength') or _beijing_heuristic_teammate_strength(
            resonance_count=int(item.get('resonanceCount') or 0),
            peer_early_count=int(item.get('peerEarlyCount') or 0),
            peer_board_count=int(item.get('peerBoardCount') or 0),
        )
        auction_teammate_summary = qwen_meta.get('auctionTeammateSummary') or (
            f'{auction_strength} / {teammate_strength}'
            if auction_strength != '待观察' or teammate_strength != '待观察'
            else '盘口强弱待观察'
        )
        item.update({
            'auctionStrength': auction_strength,
            'teammateStrength': teammate_strength,
            'auctionTeammateSummary': auction_teammate_summary,
        })

    board_type_counter: Dict[str, int] = {}
    for item in board_candidates:
        board_type_counter[item['boardType']] = board_type_counter.get(item['boardType'], 0) + 1

    scan_overlap_count = sum(1 for item in board_candidates if item.get('scanMatched'))
    top_industries = [
        (sector, count)
        for sector, count in sorted(industry_counts.items(), key=lambda item: item[1], reverse=True)
        if sector
    ]
    search_preview_lines: List[str] = []
    seen_preview = set()
    for raw_line in (search_data or '').splitlines():
        text = str(raw_line or '').strip()
        if not text:
            continue
        text = text.lstrip('-').strip()
        if not text or text in {'---', '***'}:
            continue
        if len(text) > 86:
            text = text[:86].rstrip() + '…'
        if text in seen_preview:
            continue
        seen_preview.add(text)
        search_preview_lines.append(text)
        if len(search_preview_lines) >= 2:
            break

    today_count = len(today_df) if today_df is not None else 0
    yesterday_count = len(yesterday_df) if yesterday_df is not None else 0
    early_count = sum(1 for item in board_candidates if item.get('firstSealInt') and item.get('firstSealInt') <= 103000)
    three_have_qualified = [item for item in board_candidates if item.get('passCount', 0) >= 2]
    minute_confirmed_count = sum(1 for item in board_candidates if int(item.get('minuteLongestStreak') or 0) >= 25)
    strong_auction_count = sum(1 for item in board_candidates if item.get('auctionStrength') in {'竞价涨停', '竞价强势', '高开强势'})
    strong_teammate_count = sum(1 for item in board_candidates if item.get('teammateStrength') == '队友强')
    market_gate = _build_beijing_market_gate(
        overview_text,
        search_data,
        today_count=today_count,
        qualified_count=len(three_have_qualified),
        early_count=early_count,
        top_industries=top_industries,
    )
    time_anchor = _build_beijing_time_anchor()

    scan_sector_counts: Dict[str, int] = {}
    scan_sector_members: Dict[str, List[Dict[str, Any]]] = {}
    for item in scan_candidates:
        sector = str(item.get('sector') or item.get('sector_name') or '').strip()
        if sector:
            scan_sector_counts[sector] = scan_sector_counts.get(sector, 0) + 1
            scan_sector_members.setdefault(sector, []).append(item)

    scan_sector_rank_map: Dict[str, int] = {}
    for sector, members in scan_sector_members.items():
        ranked = sorted(
            members,
            key=lambda one: (
                _normalize_scan_pct_change(one.get('pct_change')),
                _safe_float_num(one.get('total_score') or one.get('score') or 0),
                _safe_float_num(one.get('volume_ratio') if one.get('volume_ratio') is not None else one.get('volumeRatio')),
            ),
            reverse=True,
        )
        for idx, one in enumerate(ranked, 1):
            code = _normalize_code6(one.get('code'))
            if code:
                scan_sector_rank_map[code] = idx

    actionable_candidates: List[Dict[str, Any]] = []
    seen_actionable = set()
    gate_status = market_gate.get('status', '轻仓试错')
    action_priority = {
        '可半路': 5,
        '可低吸': 4,
        '可埋伏': 3,
        '竞价确认': 2,
        '仅观察': 0,
    }
    for scan_row in scan_candidates:
        code = _normalize_code6(scan_row.get('code'))
        if not code or code in seen_actionable:
            continue

        pct_change = _normalize_scan_pct_change(scan_row.get('pct_change'))
        score = int(scan_row.get('total_score') or scan_row.get('score') or 0)
        volume_ratio = _safe_float_num(
            scan_row.get('volume_ratio') if scan_row.get('volume_ratio') is not None else scan_row.get('volumeRatio')
        )
        market_cap_yi = _to_yi(scan_row.get('market_cap') or scan_row.get('marketCap') or 0)
        sector = str(scan_row.get('sector') or scan_row.get('sector_name') or '').strip()
        sector_heat = max(industry_counts.get(sector, 0), scan_sector_counts.get(sector, 0))
        sector_rank = int(scan_sector_rank_map.get(code, 999))

        if pct_change >= 9.4 or pct_change <= -3:
            continue
        if score < 68:
            continue
        if volume_ratio < 1.1 and pct_change < 1:
            continue
        if sector_heat < 2 and score < 78:
            continue

        selection_type = _beijing_scan_selection_type(
            sector_heat=sector_heat,
            pct_change=pct_change,
            score=score,
            market_cap_yi=market_cap_yi,
            sector_rank=sector_rank,
        )
        setup = _beijing_actionable_setup(
            pct_change=pct_change,
            volume_ratio=volume_ratio,
            gate_status=gate_status,
            time_anchor=time_anchor,
            sector_heat=sector_heat,
            score=score,
        )
        trade_status = setup['tradeStatus']
        if trade_status == '仅观察':
            continue

        position_ratio = _beijing_actionable_position_ratio(
            code=code,
            trade_status=trade_status,
            gate_status=gate_status,
            score=score,
            sector_heat=sector_heat,
        )
        labels = _beijing_actionable_labels(
            selection_type=selection_type,
            trade_status=trade_status,
            sector_heat=sector_heat,
            volume_ratio=volume_ratio,
            score=score,
        )
        name = str(scan_row.get('name') or code)
        grade = str(scan_row.get('grade') or ('S' if score >= 80 else 'A' if score >= 70 else 'B'))
        actionable_now = trade_status in {'可半路', '可低吸', '可埋伏'} and time_anchor.get('phaseCode') not in {
            'preopen', 'auction', 'lunch', 'tail_avoid', 'after_close',
        }
        classification_reason = (
            f"{time_anchor.get('phase', '当前时段')}优先做{setup['entryPlan']}，"
            f"当前涨幅 {pct_change:+.2f}%，量比 {volume_ratio:.2f}。"
        )
        reason = (
            f"{selection_type}｜{time_anchor.get('phase', '当前时段')}｜{trade_status}｜"
            f"板块热度 {sector_heat}，板块排序 #{sector_rank}，评分 {score}，更适合 {setup['entryPlan']}。"
        )
        actionable_candidates.append({
            'code': code,
            'name': name,
            'sector': sector,
            'price': round(_safe_float_num(scan_row.get('close') or scan_row.get('price')), 2),
            'changePct': round(pct_change, 2),
            'score': score,
            'grade': grade,
            'adviseType': '游资打板',
            'boardType': '未上板',
            'selectionType': selection_type,
            'tradeStatus': trade_status,
            'buyMethod': setup['buyMethod'],
            'entryPlan': setup['entryPlan'],
            'entryModel': setup.get('entryModel', ''),
            'entryTrigger': setup['entryTrigger'],
            'labels': labels,
            'threeHaveSummary': f'扫描评分 {score} / 量比 {volume_ratio:.2f} / 板块热度 {sector_heat}',
            'signal': f"{selection_type}/{trade_status}/{setup['buyMethod']}",
            'positionRatio': position_ratio,
            'holdPeriod': '盘中跟随为主，不强求封板，次日先看冲高兑现',
            'buyRange': '围绕分时均线、前高或回封确认分批跟随',
            'stopLoss': '分时转弱、跌破承接位或板块掉队就撤',
            'nextDaySellPlan': '若当天未顺利转强，次日冲高先兑现；走弱直接撤。',
            'targetPrice': '先看分时前高，再看是否有试板动作',
            'riskLevel': '中' if pct_change >= 3 else '低',
            'reason': reason,
            'classificationReason': classification_reason,
            'meta': (
                f"当前涨幅 {pct_change:+.2f}%｜量比 {volume_ratio:.2f}｜评分 {score}｜"
                f"板块热度 {sector_heat}｜时段 {time_anchor.get('phase', '待观察')}"
            ),
            'actionableNow': actionable_now,
            'actionSource': 'scan',
            'sectorHeat': sector_heat,
            'sectorRank': sector_rank,
            'marketCapYi': market_cap_yi,
            'volumeRatio': round(volume_ratio, 2) if volume_ratio > 0 else 0,
            'timeAnchorPhase': time_anchor.get('phase', ''),
            'timeAnchorWindow': time_anchor.get('window', ''),
        })
        seen_actionable.add(code)

    actionable_candidates.sort(
        key=lambda item: (
            1 if item.get('actionableNow') else 0,
            action_priority.get(str(item.get('tradeStatus') or ''), 0),
            -int(item.get('sectorRank') or 999),
            1 if item.get('selectionType') == '板块前排预备' else 0,
            float(item.get('sectorHeat') or 0),
            float(item.get('score') or 0),
            float(item.get('changePct') or 0),
        ),
        reverse=True,
    )
    actionable_candidates = _beijing_refresh_actionable_candidates(
        actionable_candidates,
        market_gate=market_gate,
        time_anchor=time_anchor,
    )

    for item in board_candidates:
        board_type = item.get('boardType', '')
        pass_count = int(item.get('passCount') or 0)
        front_row = bool(item.get('frontRow'))
        gate_status = market_gate.get('status', '轻仓试错')
        recommendable = (
            gate_status != '空仓等待'
            and pass_count >= 2
            and board_type not in ('一字板', '尾盘板')
            and (
                item.get('isFirstBoard')
                or (
                    board_type == '连板'
                    and int(item.get('consecutiveLimitUpDays') or 0) <= 2
                    and int(item.get('firstSealInt') or 0) <= 103000
                )
            )
        )
        if board_type == '秒拉板' and int(item.get('resonanceCount') or 0) < 3:
            recommendable = False
        if gate_status == '轻仓试错' and board_type == '秒拉板':
            recommendable = False

        buy_method = _beijing_buy_method(board_type, front_row=front_row, pass_count=pass_count)
        position_ratio = _beijing_position_ratio(
            item.get('code', ''),
            board_type,
            pass_count,
            gate_status=gate_status,
            front_row=front_row,
        )
        hold_period = _beijing_hold_period(board_type, front_row=front_row)
        buy_range = _beijing_buy_range(board_type, front_row=front_row)
        stop_loss = _beijing_stop_loss(board_type)
        next_day_sell_plan = _beijing_next_day_sell_plan(board_type, front_row=front_row)
        risk_level = '高' if board_type in ('秒拉板', '连板') else '中' if board_type in ('换手板', '回封板') else '低'
        meta = '｜'.join(item.get('metaParts') or [])
        labels = _beijing_method_labels(
            board_type=board_type,
            selection_type=item.get('selectionType', ''),
            gate_status=gate_status,
            first_seal_int=int(item.get('firstSealInt') or 0),
            last_seal_int=int(item.get('lastSealInt') or 0),
            broken_count=int(item.get('brokenBoardCount') or 0),
            resonance_count=int(item.get('resonanceCount') or 0),
            turnover_rate=float(item.get('turnoverRate') or 0),
            turnover_yi=float(item.get('turnoverYi') or 0),
            mkt_cap_yi=float(item.get('marketCapYi') or 0),
            front_row=front_row,
            minute_turnover_label=str(item.get('minuteTurnoverLabel') or ''),
            minute_longest_streak=int(item.get('minuteLongestStreak') or 0),
            auction_strength=str(item.get('auctionStrength') or ''),
            teammate_strength=str(item.get('teammateStrength') or ''),
        )
        reason = (
            f"{item.get('selectionType', '待观察')}｜{item.get('classificationReason', '')}｜"
            f"{item.get('recognitionReason', '')}｜{item.get('minuteEvidence', '分钟级证据待观察')}｜"
            f"{item.get('auctionTeammateSummary', '盘口强弱待观察')}｜次日策略：{next_day_sell_plan}"
        )
        entry_model = _beijing_entry_model_for_board(
            board_type=board_type,
            minute_turnover_label=str(item.get('minuteTurnoverLabel') or ''),
            broken_count=int(item.get('brokenBoardCount') or 0),
            front_row=front_row,
        )
        if item.get('minuteTurnoverLabel') and item.get('minuteTurnoverLabel') != '待观察':
            meta = f"{meta}｜{item.get('minuteTurnoverLabel')}"
        if item.get('auctionStrength'):
            meta = f"{meta}｜竞价 {item.get('auctionStrength')}"
        if item.get('teammateStrength'):
            meta = f"{meta}｜队友 {item.get('teammateStrength')}"

        item.update({
            'buyMethod': buy_method,
            'positionRatio': position_ratio,
            'holdPeriod': hold_period,
            'buyRange': buy_range,
            'stopLoss': stop_loss,
            'nextDaySellPlan': next_day_sell_plan,
            'recommendable': recommendable,
            'marketGateStatus': gate_status,
            'riskLevel': risk_level,
            'reason': reason,
            'labels': labels,
            'signal': f"{item.get('selectionType', '待观察')}/{board_type}/{buy_method}",
            'entryPlan': buy_method,
            'entryModel': entry_model,
            'entryTrigger': buy_range,
            'meta': meta,
            'sortKey': (
                1 if recommendable else 0,
                1 if front_row else 0,
                1 if item.get('isFirstBoard') else 0,
                pass_count,
                board_priority.get(board_type, 0),
                int(item.get('resonanceCount') or 0),
                item.get('sealAmountYi') or 0,
                item.get('score') or 0,
            ),
        })

    board_candidates.sort(key=lambda item: item.get('sortKey', (0, 0, 0, 0, 0, 0, 0, 0)), reverse=True)
    for item in board_candidates:
        item.pop('sortKey', None)
        item.pop('metaParts', None)
        item['matchedRules'] = _beijing_matched_rules(
            item,
            market_gate=market_gate,
            time_anchor=time_anchor,
            is_actionable=False,
        )

    for item in actionable_candidates:
        item['matchedRules'] = _beijing_matched_rules(
            item,
            market_gate=market_gate,
            time_anchor=time_anchor,
            is_actionable=True,
        )

    qualified = [item for item in board_candidates if item.get('recommendable')]
    recommended = []
    recommended_source = actionable_candidates[:3] if actionable_candidates else qualified[:3]
    for item in recommended_source:
        recommended.append({
            'code': item['code'],
            'name': item['name'],
            'sector': item.get('sector', ''),
            'price': item.get('price', ''),
            'changePct': item.get('changePct', 0),
            'score': item.get('score', 0),
            'grade': item.get('grade', ''),
            'adviseType': item.get('adviseType', '游资打板'),
            'boardType': item.get('boardType', ''),
            'selectionType': item.get('selectionType', ''),
            'buyMethod': item.get('buyMethod', '观察'),
            'tradeStatus': item.get('tradeStatus', ''),
            'entryPlan': item.get('entryPlan', ''),
            'entryModel': item.get('entryModel', ''),
            'entryTrigger': item.get('entryTrigger', ''),
            'actionableNow': bool(item.get('actionableNow')),
            'labels': item.get('labels', []),
            'matchedRules': item.get('matchedRules', []),
            'threeHaveSummary': item.get('threeHaveSummary', ''),
            'firstSealTime': item.get('firstSealTime', ''),
            'lastSealTime': item.get('lastSealTime', ''),
            'brokenBoardCount': item.get('brokenBoardCount', 0),
            'minuteTurnoverLabel': item.get('minuteTurnoverLabel', ''),
            'minuteEvidence': item.get('minuteEvidence', ''),
            'minuteLongestStreak': item.get('minuteLongestStreak', 0),
            'auctionStrength': item.get('auctionStrength', ''),
            'teammateStrength': item.get('teammateStrength', ''),
            'auctionTeammateSummary': item.get('auctionTeammateSummary', ''),
            'signal': item.get('signal', ''),
            'positionRatio': item.get('positionRatio', ''),
            'holdPeriod': item.get('holdPeriod', ''),
            'buyRange': item.get('buyRange', ''),
            'stopLoss': item.get('stopLoss', ''),
            'nextDaySellPlan': item.get('nextDaySellPlan', ''),
            'targetPrice': item.get('targetPrice', '次日冲高兑现'),
            'riskLevel': item.get('riskLevel', ''),
            'meta': item.get('meta', ''),
            'classificationReason': item.get('classificationReason', ''),
            'reason': item.get('reason', ''),
            'timeAnchorPhase': item.get('timeAnchorPhase', time_anchor.get('phase', '')),
            'timeAnchorWindow': item.get('timeAnchorWindow', time_anchor.get('window', '')),
        })

    market_commentary = (
        f"{time_anchor.get('phase','当前时段')}，闸门{market_gate.get('status','待观察')}，盘中可买{len(actionable_candidates)}只。"
        if today_count or actionable_candidates else
        '共享事实不足，先保守观察，避免主观打板。'
    )
    if market_gate.get('status') == '放行':
        position_advice = (
            f"{time_anchor.get('phase','当前时段')}优先{time_anchor.get('executionFocus','前排强板')}，"
            f"仓位上限{market_gate.get('positionCap')}。"
        )
    elif market_gate.get('status') == '轻仓试错':
        position_advice = (
            f"{time_anchor.get('phase','当前时段')}轻仓试错，只做{time_anchor.get('executionFocus','换手回封')}。"
        )
    else:
        position_advice = (
            f"{time_anchor.get('phase','当前时段')}不主动进攻，首板模式空仓等待或极轻仓观察。"
        )
    risk_warning = (
        '退潮时强行打板最伤，一字板、尾盘板、高位秒拉都是陷阱。'
        if market_gate.get('status') != '放行'
        else '高位秒拉、尾盘偷板、一字接力依旧是大面源头。'
    )

    step_outputs = [
        {
            'step': 1,
            'title': '市场闸门',
            'summary': (
                f"{time_anchor.get('phase','当前时段')}｜闸门{market_gate.get('status','待观察')}："
                f"{market_gate.get('action','等待更多信号')}"
            ),
            'frameworkLines': [
                '闸门只分三档：放行 / 轻仓试错 / 空仓等待。',
                '核心先看指数情绪、涨停溢价、主线题材是否有联动。',
                '退潮或分歧大时，宁愿空仓，也不强行打首板。',
                '点开分析的当下时间，也会改变执行方式：早盘抢先手，10点后更重视换手与回封确认。',
            ],
            'lines': (
                [f"时间锚点：{time_anchor.get('window', '待观察')}"]
                + list(market_gate.get('reasons') or [])[:3]
                + [f'联网补充：{line}' for line in search_preview_lines[:1]]
            )[:4] or ['先看指数、情绪、涨停溢价，再决定是否允许首板模式出手。'],
        },
        {
            'step': 2,
            'title': '题材与首板池',
            'summary': (
                f"三有候选 {len(three_have_qualified)} 只，可买预备池 {len(actionable_candidates)} 只，"
                f"优先前排，错过再做辨识度后排。"
            ),
            'frameworkLines': [
                '选股类型：板块前排首板 / 后排辨识度首板 / 换手连板 / 独立图形票。',
                '盘中可买池：板块前排预备 / 后排辨识度预备 / 独立图形票，不必非等封死涨停才动手。',
                '判断依据：板块共振数量、首封时间、流通市值、成交额、封板资金、换手率、扫描命中。',
                '队友强时，自己的票竞价一般也可能被带起来；独苗票则更谨慎。',
            ],
            'lines': [
                (
                    f"{item['name']}({item['code']})｜{item['selectionType']}｜{item.get('tradeStatus', item['threeHaveSummary'])}｜"
                    f"{item.get('entryModel', item.get('entryPlan', item.get('threeHaveSummary', '待观察')))}｜"
                    f"竞价 {item.get('auctionStrength','待观察')}｜队友 {item.get('teammateStrength','待观察')}"
                )
                for item in (actionable_candidates[:4] or board_candidates[:4])
            ] or ['当前没有同时满足题材、辨识度与三有过滤的候选，先空仓等待。'],
        },
        {
            'step': 3,
            'title': '板型与成交方式',
            'summary': (
                (' / '.join(f"{k}{v}只" for k, v in list(board_type_counter.items())[:5]) or '暂无可分类样本')
                + f"｜横盘半小时 {minute_confirmed_count} 只"
            ),
            'frameworkLines': [
                '支持板型：秒拉板 / 换手板 / 回封板 / 连板 / 一字板 / 尾盘板。',
                '换手板：5-8个点震荡较久、上板后抛压小，横半小时通常更值得直接扫。',
                '回封板：炸板后回封代表空头释放，早回封优于尾盘勉强回封。',
                '秒拉板：默认仅排不扫，强板块时更像先锋，独苗秒板炸板风险高。',
                '尾盘板：2点后少打，2点半以后偏投机，封不住就是最高点接盘。',
            ],
            'lines': [
                f"{item['name']}({item['code']})｜{item['boardType']}｜{item['buyMethod']}｜{item.get('minuteTurnoverLabel','待观察')}｜{item['classificationReason']}"
                for item in board_candidates[:4]
            ] or ['涨停池样本不足，待下一轮板池刷新后再分类。'],
        },
        {
            'step': 4,
            'title': '仓位与执行',
            'summary': (
                f"{time_anchor.get('phase','当前时段')}优先{time_anchor.get('executionFocus','前排强板')}，"
                f"执行上限 {market_gate.get('positionCap','待观察')}；竞价偏强 {strong_auction_count} 只，队友强 {strong_teammate_count} 只。"
            ),
            'frameworkLines': [
                '仓位模板：主板默认 1/8，20cm 默认 1/16，把握度高的大票可提到 1/6。',
                '执行倾向：前排强板、回封确认、换手充分偏扫板；容量大或把握度低偏排板。',
                '方法论标签会显式输出：换手板优先、回封更稳、秒板新手回避、尾盘慎打等。',
                '当前时间窗会改变执行偏好：早盘偏先手，10点后偏换手回封，午后偏回流低吸，尾盘偏观察。',
            ],
            'lines': [
                f"{item['name']}({item['code']})｜{item['positionRatio']}｜{item.get('tradeStatus', item['buyMethod'])}｜"
                f"{item.get('entryModel', item.get('entryPlan', item['buyMethod']))}｜{item.get('entryTrigger', item['buyRange'])}"
                for item in recommended[:3]
            ] or ['闸门未放行或候选不够强，只保留现金与观察仓。'],
        },
        {
            'step': 5,
            'title': '次日卖出计划',
            'summary': '高开低走、低开低走反抽、跌停必走；多数票在首小时完成处理。',
            'frameworkLines': [
                '卖法铁律：高开低走卖，低开低走反抽无力卖，跌停或明显走弱必走。',
                '多数票在首小时处理，不研究花哨卖点，只追求执行一致性。',
            ],
            'lines': [
                f"{item['name']}({item['code']})｜{item['nextDaySellPlan']}｜{item['stopLoss']}"
                for item in recommended[:3]
            ] or ['没有足够确定性的隔夜计划时，不勉强持股过夜。'],
        },
    ]

    selection_path_defs = {
        '板块前排首板': '谁先板干谁，优先题材前排与先手。',
        '后排辨识度首板': '错过前排后，改做容量、逻辑、图形更强的辨识度后排。',
        '换手连板': '只做有板块效应、10:30前换手完成的强连板。',
        '独立图形票': '没有板块时，只做看得懂的独立强图形。',
        '板块前排预备': '还没封板但已具备前排先手特征，可做盘中预备池。',
        '后排辨识度预备': '错过前排后，优先保留可买的辨识度后排预备池。',
    }
    selection_path_counts: Dict[str, int] = {key: 0 for key in selection_path_defs}
    for item in list(board_candidates) + list(actionable_candidates):
        selection_type = str(item.get('selectionType') or '').strip()
        if selection_type in selection_path_counts:
            selection_path_counts[selection_type] += 1

    selection_path = [
        {
            'type': key,
            'count': selection_path_counts.get(key, 0),
            'description': desc,
        }
        for key, desc in selection_path_defs.items()
    ]

    board_playbook_defs = [
        ('秒拉板', '默认谨慎，偏排不偏扫；板块强时更像先锋。'),
        ('换手板', '5-8个点震荡换手后上板，是北京炒家核心审美。'),
        ('回封板', '炸板后回封代表空头释放，早回封更优。'),
        ('连板', '只做有板块效应、强更强的换手连板。'),
        ('一字板', '一字不追，只看T字回封确认。'),
        ('尾盘板', '2点后少打，2点半以后更偏投机。'),
    ]
    board_playbook = [
        {
            'type': board_type,
            'count': board_type_counter.get(board_type, 0),
            'description': desc,
        }
        for board_type, desc in board_playbook_defs
    ]

    label_counts: Dict[str, int] = {}
    for item in list(board_candidates) + list(actionable_candidates):
        for label in item.get('labels') or []:
            text = str(label or '').strip()
            if not text:
                continue
            label_counts[text] = label_counts.get(text, 0) + 1
    label_hits = [
        {'label': label, 'count': count}
        for label, count in sorted(label_counts.items(), key=lambda one: (one[1], one[0]), reverse=True)[:12]
    ]

    front_row_count = (
        sum(1 for item in board_candidates if item.get('frontRow'))
        + sum(1 for item in actionable_candidates if item.get('selectionType') == '板块前排预备')
    )
    rearfocus_count = (
        sum(1 for item in board_candidates if item.get('selectionType') == '后排辨识度首板')
        + sum(1 for item in actionable_candidates if item.get('selectionType') == '后排辨识度预备')
    )
    reboard_count = board_type_counter.get('回封板', 0)
    spike_count = board_type_counter.get('秒拉板', 0)
    tail_count = board_type_counter.get('尾盘板', 0)
    actionable_now_count = sum(1 for item in actionable_candidates if item.get('actionableNow'))
    daily_rule_hits = [
        {
            'title': '时间锚点',
            'status': time_anchor.get('phase', '待观察'),
            'detail': time_anchor.get('summary', '按当前时段切换执行风格。'),
        },
        {
            'title': '市场闸门',
            'status': market_gate.get('status', '待观察'),
            'detail': market_gate.get('action', '等待更多信号'),
        },
        {
            'title': '盘中可买',
            'status': f'{actionable_now_count}只命中',
            'detail': '优先推荐尚未封死、当前仍有执行空间的候选，而不是只报已涨停个股。',
        },
        {
            'title': '前排优先',
            'status': f'{front_row_count}只命中',
            'detail': '题材前排首板是首选路径，谁先板干谁。',
        },
        {
            'title': '后排辨识度',
            'status': f'{rearfocus_count}只命中',
            'detail': '错过前排后，再做容量、图形、逻辑更强的辨识度后排。',
        },
        {
            'title': '横盘半小时',
            'status': f'{minute_confirmed_count}只命中',
            'detail': '分钟级 6%-8% 横盘越久，越接近理想换手板。',
        },
        {
            'title': '回封更稳',
            'status': f'{reboard_count}只命中',
            'detail': '炸板后回封代表空头释放，早回封优于尾盘勉强回封。',
        },
        {
            'title': '秒板谨慎',
            'status': f'{spike_count}只样本',
            'detail': '默认仅排不扫，独苗秒板炸板风险更高。',
        },
        {
            'title': '尾盘回避',
            'status': f'{tail_count}只样本',
            'detail': '2点后少打，2点半以后更偏投机。',
        },
        {
            'title': '竞价偏强',
            'status': f'{strong_auction_count}只命中',
            'detail': '竞价涨停 / 竞价强势 / 高开强势是优先观察对象。',
        },
        {
            'title': '队友带动',
            'status': f'{strong_teammate_count}只命中',
            'detail': '队友强时，自己的票竞价一般也可能被板块带起来。',
        },
    ]
    actionable_pool = [
        {
            'code': item.get('code', ''),
            'name': item.get('name', ''),
            'selectionType': item.get('selectionType', ''),
            'tradeStatus': item.get('tradeStatus', ''),
            'entryPlan': item.get('entryPlan', ''),
            'entryModel': item.get('entryModel', ''),
            'entryTrigger': item.get('entryTrigger', ''),
            'score': item.get('score', 0),
            'changePct': item.get('changePct', 0),
            'matchedRules': item.get('matchedRules', []),
        }
        for item in actionable_candidates[:6]
    ]

    return {
        'kind': 'beijing',
        'version': 'v3',
        'generatedAt': datetime.now().isoformat(),
        'todayDate': today,
        'yesterdayDate': yesterday_date,
        'stats': {
            'todayLimitUps': today_count,
            'yesterdayLimitUps': yesterday_count,
            'scanOverlapCount': scan_overlap_count,
            'qualifiedCount': len(three_have_qualified),
            'recommendedCount': len(recommended),
            'actionableCount': len(actionable_candidates),
            'earlyBoardCount': early_count,
            'minuteConfirmedCount': minute_confirmed_count,
            'strongAuctionCount': strong_auction_count,
            'strongTeammateCount': strong_teammate_count,
            'marketGateStatus': market_gate.get('status'),
        },
        'marketGate': market_gate,
        'timeAnchor': time_anchor,
        'strategyPanels': {
            'timeAnchor': time_anchor,
            'selectionPath': selection_path,
            'boardPlaybook': board_playbook,
            'labelHits': label_hits,
            'dailyRuleHits': daily_rule_hits,
            'actionablePool': actionable_pool,
        },
        'boardTypeSummary': [
            {'type': board_type, 'count': count}
            for board_type, count in sorted(board_type_counter.items(), key=lambda item: item[1], reverse=True)
        ],
        'boardCandidates': board_candidates[:8],
        'actionableCandidates': actionable_candidates[:8],
        'recommendedStocks': recommended,
        'stepOutputs': step_outputs,
        'marketCommentary': market_commentary,
        'positionAdvice': position_advice,
        'riskWarning': risk_warning,
        'searchDataPreview': (search_data or '')[:1200],
    }


def _build_beijing_execution_context_text(artifacts: Dict[str, Any]) -> str:
    if not artifacts:
        return '【暂无北京炒家执行工件】'

    stats = artifacts.get('stats', {})
    market_gate = artifacts.get('marketGate', {})
    time_anchor = artifacts.get('timeAnchor', {})
    lines = [
        '## 北京炒家执行工件（系统预处理）',
        f"- 时间锚点：{time_anchor.get('phase', '待观察')}｜{time_anchor.get('window', '等待更多信号')}",
        f"- 市场闸门：{market_gate.get('status', '待观察')}｜{market_gate.get('action', '等待更多信号')}",
        f"- 今日涨停池：{stats.get('todayLimitUps', 0)} 只",
        f"- 昨日涨停池：{stats.get('yesterdayLimitUps', 0)} 只",
        f"- 三有达标：{stats.get('qualifiedCount', 0)} 只",
        f"- 盘中可买：{stats.get('actionableCount', 0)} 只",
        f"- 推荐候选：{stats.get('recommendedCount', 0)} 只",
        '',
        '### 板型分布',
    ]
    for item in artifacts.get('boardTypeSummary', [])[:6]:
        lines.append(f"- {item.get('type', '待观察')}：{item.get('count', 0)} 只")

    lines.append('')
    lines.append('### 盘中可买候选（优先使用这些结构化结果）')
    for item in artifacts.get('actionableCandidates', [])[:6]:
        lines.append(
            f"- {item.get('name','')}({item.get('code','')})｜{item.get('selectionType','待观察')}｜"
            f"{item.get('tradeStatus','待观察')}｜{item.get('entryModel') or item.get('entryPlan','待观察')}｜"
            f"{item.get('entryTrigger','待观察')}｜"
            f"{' / '.join((item.get('labels') or [])[:3])}"
        )
    if not artifacts.get('actionableCandidates'):
        for item in artifacts.get('boardCandidates', [])[:4]:
            lines.append(
                f"- {item.get('name','')}({item.get('code','')})｜{item.get('boardType','待观察')}｜"
                f"{item.get('selectionType','待观察')}｜{item.get('threeHaveSummary','待观察')}｜"
                f"{item.get('entryModel') or item.get('buyMethod','观察')}｜{item.get('minuteTurnoverLabel','待观察')}｜"
                f"{item.get('auctionStrength','待观察')}｜{item.get('teammateStrength','待观察')}｜"
                f"{item.get('nextDaySellPlan','待观察')}｜"
                f"{' / '.join((item.get('labels') or [])[:3])}"
            )

    return '\n'.join(lines)


def _build_beijing_fallback_structured(artifacts: Dict[str, Any]) -> Dict[str, Any]:
    recommended = list(artifacts.get('recommendedStocks') or [])
    return {
        'agentId': 'beijing',
        'agentName': '北京炒家',
        'stance': 'bull' if recommended else 'neutral',
        'confidence': 78 if recommended else 52,
        'marketCommentary': artifacts.get('marketCommentary', ''),
        'positionAdvice': artifacts.get('positionAdvice', ''),
        'riskWarning': artifacts.get('riskWarning', ''),
        'recommendedStocks': recommended,
    }


def _merge_beijing_structured(structured: Dict[str, Any], artifacts: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(structured or {})
    recommended = list(merged.get('recommendedStocks') or [])
    candidate_sources = (
        list(artifacts.get('recommendedStocks') or [])
        + list(artifacts.get('actionableCandidates') or [])
        + list(artifacts.get('boardCandidates') or [])
    )
    candidates_by_code = {
        _normalize_code6(item.get('code')): item
        for item in candidate_sources
        if _normalize_code6(item.get('code'))
    }

    merged_recs = []
    for item in recommended:
        code = _normalize_code6(item.get('code'))
        candidate = candidates_by_code.get(code, {})
        one = dict(candidate) if candidate else {}
        one.update(item)
        for key, value in candidate.items():
            one.setdefault(key, value)
        if code:
            one['code'] = code
        merged_recs.append(one)

    artifact_recommended = list(artifacts.get('recommendedStocks') or [])
    if artifact_recommended:
        merged['recommendedStocks'] = artifact_recommended[:3]
    else:
        merged['recommendedStocks'] = merged_recs[:3]
    merged['personaExecution'] = {
        'kind': 'beijing',
        'version': artifacts.get('version', 'v1'),
        'coreObjective': '临盘只做看得懂的强势首板，先判市场闸门，再做前排与辨识度后排',
        'stats': artifacts.get('stats', {}),
        'marketGate': artifacts.get('marketGate', {}),
        'timeAnchor': artifacts.get('timeAnchor', {}),
        'strategyPanels': artifacts.get('strategyPanels', {}),
        'boardTypeSummary': artifacts.get('boardTypeSummary', []),
        'boardCandidates': artifacts.get('boardCandidates', []),
        'actionableCandidates': artifacts.get('actionableCandidates', []),
        'stepOutputs': artifacts.get('stepOutputs', []),
    }

    if not str(merged.get('marketCommentary') or '').strip():
        merged['marketCommentary'] = artifacts.get('marketCommentary', '')
    if not str(merged.get('positionAdvice') or '').strip():
        merged['positionAdvice'] = artifacts.get('positionAdvice', '')
    if not str(merged.get('riskWarning') or '').strip():
        merged['riskWarning'] = artifacts.get('riskWarning', '')

    return merged


def _build_beijing_markdown_summary(structured: Dict[str, Any], artifacts: Dict[str, Any]) -> str:
    market_gate = artifacts.get('marketGate', {})
    time_anchor = artifacts.get('timeAnchor', {})
    lines = [
        f"【时间锚点】{time_anchor.get('phase','待观察')}｜{time_anchor.get('window','等待更多信号')}",
        f"【市场闸门】{market_gate.get('status','待观察')}｜{market_gate.get('action','等待更多信号')}",
        f"【市场解读】{structured.get('marketCommentary') or artifacts.get('marketCommentary') or '暂无明确板池结论'}",
        f"【仓位建议】{structured.get('positionAdvice') or artifacts.get('positionAdvice') or '控制仓位，优先前排'}",
        f"【风险提示】{structured.get('riskWarning') or artifacts.get('riskWarning') or '一字板不追，尾盘板不碰'}",
    ]
    recs = (structured.get('recommendedStocks') or [])[:3]
    if recs:
        lines.append('【重点候选】')
        for item in recs:
            lines.append(
                f"- {item.get('name','')}({item.get('code','')})｜{item.get('boardType','待观察')}｜"
                f"{item.get('selectionType','待观察')}｜{item.get('entryModel') or item.get('tradeStatus') or item.get('buyMethod','观察')}｜"
                f"{item.get('nextDaySellPlan') or item.get('reason') or item.get('meta') or ''}｜"
                f"{' / '.join((item.get('labels') or [])[:3])}"
            )
    else:
        lines.append('【重点候选】当前无三有与板型同时达标的隔夜标的，维持观察仓。')
    return '\n'.join(lines)


def _build_qiao_time_anchor(now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now()
    hhmm = now.hour * 100 + now.minute
    label = now.strftime('%H:%M')

    if hhmm < 925:
        return {
            'phaseCode': 'preopen',
            'phase': '盘前预案',
            'window': f'{label}｜先做主线预案，不抢主观先手',
            'summary': '盘前只锁定主线、龙头和预备池，不做脱离市场的预判式交易。',
            'executionFocus': '锁定主线与龙头预备池',
            'positionBias': '不开新仓，最多观察仓',
            'rules': [
                '先看主线，再看龙头，再看是否存在可低吸的转折位。',
                '盘前不做意淫式埋伏，真正的机会等竞价与开盘确认。',
                '优先保留 3-5 只大众情人，避免信息过载。',
            ],
        }
    if hhmm < 930:
        return {
            'phaseCode': 'auction',
            'phase': '竞价验证',
            'window': f'{label}｜看竞价、看队友、看龙头是否继续强势',
            'summary': '竞价阶段重点验证龙头强弱、板块队友表现与当日主线是否延续。',
            'executionFocus': '竞价确认，不提前重仓',
            'positionBias': '小仓确认，拒绝竞价主观梭哈',
            'rules': [
                '队友强时，龙头竞价一般弱一点也有机会被带起来。',
                '独苗高开更危险，要防一致转分歧。',
                '竞价只做方向确认，不把竞价当全部结论。',
            ],
        }
    if hhmm < 1030:
        return {
            'phaseCode': 'morning_leader',
            'phase': '早盘龙头确认',
            'window': f'{label}｜只看主线最强，不在杂毛里找机会',
            'summary': '早盘是确认总龙头、板块龙头与大众情人的关键窗口。',
            'executionFocus': '总龙头 / 板块龙头 / 最强跟随',
            'positionBias': '主升放行，退潮克制',
            'rules': [
                '早盘优先确认谁是总龙头，而不是猜谁会成龙。',
                '主线不清晰时宁可慢，不急着出手。',
                '不做弱票补涨臆测，只做市场已经给出合力的票。',
            ],
        }
    if hhmm < 1400:
        return {
            'phaseCode': 'dip_reflow',
            'phase': '分歧低吸',
            'window': f'{label}｜优先看 5/10 日线低吸与分歧回流',
            'summary': '午前至午后早段更适合做主升龙头的分歧低吸与均线承接。',
            'executionFocus': '5日线低吸 / 10日线低吸 / 分歧回流',
            'positionBias': '围绕承接位分批试错',
            'rules': [
                '低吸只吸强势龙头，不吸冷门弱票。',
                '分歧不是风险本身，关键看是否能放量转强。',
                '回踩均线不破、分时重新走强时更接近买点。',
            ],
        }
    if hhmm < 1450:
        return {
            'phaseCode': 'afternoon_board',
            'phase': '下午换手板',
            'window': f'{label}｜偏爱充分换手后的下午板',
            'summary': '下午更看重充分换手后的确定性打板，而不是无脑追秒板。',
            'executionFocus': '下午换手板 / 主升打板 / 回封确认',
            'positionBias': '只做确定性，不追最后一脚',
            'rules': [
                '换手决定高度，充分换手后的板更有确定性。',
                '主升中的下午换手板，往往比早盘一致性板更好接。',
                '炸板回封要看队友是否掉队，不做孤勇者。',
            ],
        }
    if hhmm < 1500:
        return {
            'phaseCode': 'tail_review',
            'phase': '尾盘观察',
            'window': f'{label}｜尾盘更偏复核，不追情绪末端',
            'summary': '尾盘一致性过强时更容易转次日兑现，优先做明天的预案而不是今天的冲动单。',
            'executionFocus': '观察次日预备池',
            'positionBias': '不追尾盘一致，不补情绪末端',
            'rules': [
                '尾盘的意义更多是复核强弱，而不是强行找买点。',
                '没有足够把握时，把机会留给次日竞价确认。',
                '尾盘乱点火最容易变成第二天的兑现盘。',
            ],
        }
    return {
        'phaseCode': 'after_close',
        'phase': '收盘复核',
        'window': f'{label}｜只做次日计划，不虚构盘中执行',
        'summary': '收盘后重点是复核主线、龙头、阶段与次日竞价预案，不假装还能盘中追单。',
        'executionFocus': '次日竞价确认 / 次日分歧计划',
        'positionBias': '收盘后不给盘中追价建议',
        'rules': [
            '收盘后的推荐应优先输出次日可确认机会，而不是已经买不到的涨停板。',
            '次日关注龙头竞价、队友强弱与是否延续主升。',
            '如果阶段转差，预案的核心是降低仓位而不是找借口上仓。',
        ],
    }


def _build_qiao_market_gate(
    overview_text: str,
    search_data: str,
    *,
    today_count: int,
    leader_height: int,
    main_theme_count: int,
) -> Dict[str, Any]:
    overview_metrics = _parse_market_overview_metrics(overview_text)
    text = f'{overview_text}\n{search_data}'
    positive_hits = sum(
        1 for kw in ('主线明确', '赚钱效应强', '强修复', '情绪回暖', '放量', '强势')
        if kw in text
    )
    negative_hits = sum(
        1 for kw in ('退潮', '高位补跌', '亏钱效应扩散', '弱势', '恐慌', '冰点')
        if kw in text
    )

    score = 0
    score += 2 if today_count >= 40 else 1 if today_count >= 25 else -1
    score += 2 if leader_height >= 4 else 1 if leader_height >= 3 else -1
    score += 2 if main_theme_count >= 4 else 1 if main_theme_count >= 2 else -1
    score += 1 if overview_metrics['positiveCount'] > overview_metrics['negativeCount'] else -1 if overview_metrics['negativeCount'] > overview_metrics['positiveCount'] else 0
    score += min(2, positive_hits)
    score -= min(2, negative_hits)

    if negative_hits >= 2 and today_count < 25:
        stage = '退潮'
    elif today_count >= 55 and leader_height >= 4 and main_theme_count >= 5:
        stage = '高潮'
    elif today_count >= 32 and leader_height >= 3 and main_theme_count >= 3:
        stage = '主升'
    elif today_count >= 20 and main_theme_count >= 2:
        stage = '发酵'
    else:
        stage = '启动'

    if stage == '退潮' or score <= 0:
        status = '空仓等待'
        action = '退潮优先休息，只留极轻观察仓，拒绝主观抄底。'
        position_cap = '0-1/16观察'
    elif stage == '主升' and score >= 4:
        status = '放行'
        action = '主升浪允许进攻，优先龙头低吸、分歧回流与下午换手板。'
        position_cap = '2/8-4/8'
    else:
        status = '轻仓试错'
        action = '只做最强龙头与可验证分歧，放弃模式外一致性追涨。'
        position_cap = '1/8-2/8'

    reasons = []
    if overview_metrics['metrics']:
        reasons.append(
            '指数概况：' + ' / '.join(
                f"{item['name']}{item['pct']:+.2f}%"
                for item in overview_metrics['metrics'][:4]
            )
        )
    reasons.append(f'涨停池 {today_count} 只，空间板 {leader_height} 连板，主线联动 {main_theme_count} 只')
    reasons.append(f'阶段判断：{stage}')
    reasons.append(f'执行结论：{action}')

    return {
        'stage': stage,
        'status': status,
        'action': action,
        'positionCap': position_cap,
        'score': score,
        'reasons': reasons,
    }


def _qiao_fetch_ma_snapshot(code: str, latest_price: Any = 0) -> Dict[str, Any]:
    snapshot = {
        'ma5': 0.0,
        'ma10': 0.0,
        'ma20': 0.0,
        'distToMa5Pct': 0.0,
        'distToMa10Pct': 0.0,
        'nearMa5': False,
        'nearMa10': False,
        'trendBias': '待观察',
        'maSupportSummary': '均线关系待观察',
    }
    try:
        from utils.ths_crawler import get_stock_kline_sina

        df = get_stock_kline_sina(code, days=40)
        if df is None or df.empty or 'close' not in df.columns:
            return snapshot
        close = _pd.to_numeric(df['close'], errors='coerce').dropna()
        if len(close) < 12:
            return snapshot

        latest = _safe_float_num(latest_price)
        if latest <= 0:
            latest = float(close.iloc[-1])
        ma5 = float(close.tail(5).mean())
        ma10 = float(close.tail(10).mean())
        ma20 = float(close.tail(min(20, len(close))).mean())
        prev_close = close.iloc[:-1] if len(close) > 1 else close
        prev_ma5 = float(prev_close.tail(5).mean()) if len(prev_close) >= 5 else ma5
        prev_ma10 = float(prev_close.tail(10).mean()) if len(prev_close) >= 10 else ma10

        dist5 = ((latest - ma5) / ma5 * 100.0) if ma5 else 0.0
        dist10 = ((latest - ma10) / ma10 * 100.0) if ma10 else 0.0
        near_ma5 = abs(dist5) <= 1.8
        near_ma10 = abs(dist10) <= 2.8

        if latest >= ma5 >= ma10 and ma5 >= prev_ma5 and ma10 >= prev_ma10:
            trend_bias = '主升'
        elif latest >= ma10 and ma10 >= prev_ma10:
            trend_bias = '偏强'
        elif latest >= ma20:
            trend_bias = '震荡'
        else:
            trend_bias = '调整'

        if near_ma5:
            summary = f'贴近 5 日线 {dist5:+.2f}%'
        elif near_ma10:
            summary = f'贴近 10 日线 {dist10:+.2f}%'
        else:
            summary = f'距 5 日线 {dist5:+.2f}% / 距 10 日线 {dist10:+.2f}%'

        snapshot.update({
            'ma5': round(ma5, 2),
            'ma10': round(ma10, 2),
            'ma20': round(ma20, 2),
            'distToMa5Pct': round(dist5, 2),
            'distToMa10Pct': round(dist10, 2),
            'nearMa5': near_ma5,
            'nearMa10': near_ma10,
            'trendBias': trend_bias,
            'maSupportSummary': summary,
        })
        return snapshot
    except Exception as exc:
        logger.debug('[Qiao] 均线快照获取失败 %s: %s', code, exc)
        return snapshot


def _qiao_entry_plan_from_model(entry_model: str, phase_code: str, gate_status: str) -> Dict[str, str]:
    closed_phase = phase_code in {'preopen', 'auction', 'tail_review', 'after_close'}
    if gate_status == '空仓等待':
        return {
            'tradeStatus': '观察',
            'entryPlan': '退潮回避',
            'entryTrigger': '等待主线重新明确',
        }

    mapping = {
        '5日线低吸': ('可低吸', '围绕 5 日线低吸确认', '回踩 5 日线不破并重新翻红'),
        '10日线低吸': ('可低吸', '围绕 10 日线分歧低吸', '回踩 10 日线止跌，分时重新走强'),
        '分歧回流': ('可低吸', '分歧后只做回流确认', '早盘分歧后重新放量翻红'),
        '下午换手板': ('可半路', '等待下午充分换手后再打板', '13:30 后换手充分再试板'),
        '主升打板': ('可半路', '只打主升最强突破', '主线龙头放量突破分时前高'),
        '回封确认': ('可半路', '炸板后只做强回封', '开板后再度回封且队友不掉队'),
        '竞价确认': ('竞价确认', '次日竞价确认', '竞价高开 2%-5% 且队友不弱'),
        '观察': ('观察', '等待更强信号', '等待龙头与主线重新共振'),
    }
    trade_status, entry_plan, entry_trigger = mapping.get(entry_model, mapping['观察'])
    if closed_phase and trade_status in {'可低吸', '可半路'}:
        trade_status = '竞价确认'
    return {
        'tradeStatus': trade_status,
        'entryPlan': entry_plan if trade_status != '竞价确认' else '次日竞价确认',
        'entryTrigger': entry_trigger,
    }


def _qiao_position_ratio(
    *,
    code: str,
    gate_status: str,
    leader_type: str,
    entry_model: str,
    market_cap_yi: float,
) -> str:
    if gate_status == '空仓等待':
        return '0-1/16观察'

    high_volatility = code.startswith(('30', '68', '8', '9'))
    if high_volatility:
        return '1/16'

    if leader_type == '总龙头' and entry_model in {'下午换手板', '主升打板', '回封确认'} and market_cap_yi >= 80:
        return '1/6'
    if entry_model in {'5日线低吸', '10日线低吸', '分歧回流'}:
        return '1/8'
    return '1/8'


def _qiao_labels(
    *,
    leader_type: str,
    selection_type: str,
    entry_model: str,
    stage: str,
    volume_ratio: float,
    sector_rank: int,
    gate_status: str,
) -> List[str]:
    labels: List[str] = []
    if leader_type in {'总龙头', '板块龙头'}:
        labels.append('只做龙头')
    else:
        labels.append('只做最强')

    if stage == '主升':
        labels.append('主升浪')
    if entry_model == '5日线低吸':
        labels.extend(['龙头低吸', '5日线低吸'])
    elif entry_model == '10日线低吸':
        labels.extend(['龙头低吸', '10日线低吸'])
    elif entry_model == '分歧回流':
        labels.append('分歧回流')
    elif entry_model == '下午换手板':
        labels.append('下午换手板')
    elif entry_model == '主升打板':
        labels.append('量能放大')
    elif entry_model == '回封确认':
        labels.append('回封确认')

    labels.append('次日必卖')
    labels.append('跟随不预判')
    if gate_status == '空仓等待':
        labels.append('退潮回避')
    if sector_rank <= 2:
        labels.append('大众情人')
    if volume_ratio >= 1.8:
        labels.append('有量才安全')
    if selection_type == '切换预备':
        labels.append('切换预备')

    seen = set()
    deduped = []
    for label in labels:
        text = str(label or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped[:7]


def _qiao_matched_rules(item: Dict[str, Any]) -> List[Dict[str, str]]:
    rules = [
        {
            'title': '时间锚定',
            'detail': f"{item.get('timeAnchorPhase', '当前时段')}｜{item.get('timeAnchorWindow', '等待更强信号')}",
        },
        {
            'title': '龙头路径',
            'detail': f"{item.get('selectionType', '待观察')}｜{item.get('leaderType', '待观察')}｜{item.get('sector', '待观察')}",
        },
        {
            'title': '入场模型',
            'detail': f"{item.get('entryModel', '待观察')}｜{item.get('entryTrigger', '等待触发')}",
        },
        {
            'title': '均线/量能',
            'detail': f"{item.get('maSupportSummary', '均线待观察')}｜量比 {float(item.get('volumeRatio') or 0):.2f}",
        },
        {
            'title': '次日纪律',
            'detail': item.get('nextDaySellPlan', '买完第二天除非涨停，必卖。'),
        },
    ]
    return [rule for rule in rules if rule.get('title') and rule.get('detail')]


def _build_qiao_execution_artifacts(search_data: str = '', overview_text: str = '') -> Dict[str, Any]:
    from market_data import _ak_eastmoney_direct, _get_ak

    today = datetime.now().strftime('%Y%m%d')
    today_df = _pd.DataFrame()

    try:
        with _ak_eastmoney_direct():
            today_df = _get_ak().stock_zt_pool_em(date=today)
    except Exception as exc:
        logger.warning('[Qiao] 今日涨停池获取失败: %s', exc)

    scan_candidates = _collect_latest_scan_candidates()
    scan_map = {_normalize_code6(item.get('code')): item for item in scan_candidates}

    today_sector_counts: Dict[str, int] = {}
    sector_leader_rows: Dict[str, List[Dict[str, Any]]] = {}
    leader_height = 0
    board_candidates: List[Dict[str, Any]] = []

    if today_df is not None and not today_df.empty:
        for _, row in today_df.iterrows():
            row_dict = row.to_dict()
            code = _normalize_code6(row_dict.get('代码'))
            if not code:
                continue
            scan_row = scan_map.get(code, {})
            sector = str(row_dict.get('所属行业') or scan_row.get('sector') or '').strip()
            if sector:
                today_sector_counts[sector] = today_sector_counts.get(sector, 0) + 1
            consecutive_days = _safe_int_num(row_dict.get('连板数') or 1)
            leader_height = max(leader_height, consecutive_days)
            item = {
                'code': code,
                'name': str(row_dict.get('名称') or scan_row.get('name') or code),
                'sector': sector,
                'price': round(_safe_float_num(row_dict.get('最新价')), 2),
                'changePct': round(_safe_float_num(row_dict.get('涨跌幅')), 2),
                'score': int(scan_row.get('total_score') or scan_row.get('score') or min(99, 68 + consecutive_days * 5 + today_sector_counts.get(sector, 0) * 2)),
                'grade': str(scan_row.get('grade') or ('S' if consecutive_days >= 3 else 'A' if consecutive_days >= 2 else 'B')),
                'consecutiveDays': consecutive_days,
                'firstSealTime': _format_clock_hhmm(row_dict.get('首次封板时间')),
                'firstSealInt': _clock_to_int(row_dict.get('首次封板时间')),
                'lastSealTime': _format_clock_hhmm(row_dict.get('最后封板时间') or row_dict.get('首次封板时间')),
                'lastSealInt': _clock_to_int(row_dict.get('最后封板时间') or row_dict.get('首次封板时间')),
                'brokenBoardCount': _safe_int_num(row_dict.get('炸板次数')),
                'turnoverRate': round(_safe_float_num(row_dict.get('换手率')), 2),
                'sealAmountYi': _to_yi(row_dict.get('封板资金')),
                'marketCapYi': _to_yi(row_dict.get('流通市值')),
                'volumeRatio': round(_safe_float_num(scan_row.get('volume_ratio') if scan_row.get('volume_ratio') is not None else scan_row.get('volumeRatio')), 2),
            }
            board_candidates.append(item)
            sector_leader_rows.setdefault(sector, []).append(item)

    scan_sector_counts: Dict[str, int] = {}
    scan_sector_scores: Dict[str, float] = {}
    scan_sector_rank_map: Dict[str, int] = {}
    scan_sector_members: Dict[str, List[Dict[str, Any]]] = {}
    for scan_row in scan_candidates:
        sector = str(scan_row.get('sector') or scan_row.get('sector_name') or '').strip()
        code = _normalize_code6(scan_row.get('code'))
        if not sector or not code:
            continue
        scan_sector_counts[sector] = scan_sector_counts.get(sector, 0) + 1
        scan_sector_scores[sector] = scan_sector_scores.get(sector, 0.0) + _safe_float_num(scan_row.get('total_score') or scan_row.get('score'))
        scan_sector_members.setdefault(sector, []).append(scan_row)

    for sector, members in scan_sector_members.items():
        ranked = sorted(
            members,
            key=lambda one: (
                _normalize_scan_pct_change(one.get('pct_change')),
                _safe_float_num(one.get('total_score') or one.get('score')),
                _safe_float_num(one.get('volume_ratio') if one.get('volume_ratio') is not None else one.get('volumeRatio')),
            ),
            reverse=True,
        )
        for idx, one in enumerate(ranked, 1):
            code = _normalize_code6(one.get('code'))
            if code:
                scan_sector_rank_map[code] = idx

    theme_scores: List[Dict[str, Any]] = []
    for sector in sorted(set(list(today_sector_counts.keys()) + list(scan_sector_counts.keys()))):
        score = today_sector_counts.get(sector, 0) * 3 + scan_sector_counts.get(sector, 0)
        score += min(3.0, scan_sector_scores.get(sector, 0.0) / 180.0)
        theme_scores.append({
            'name': sector,
            'score': round(score, 2),
            'limitUps': today_sector_counts.get(sector, 0),
            'scanCount': scan_sector_counts.get(sector, 0),
        })
    theme_scores.sort(key=lambda item: (item['score'], item['limitUps'], item['scanCount']), reverse=True)

    main_theme = theme_scores[0] if theme_scores else {'name': '待观察', 'score': 0, 'limitUps': 0, 'scanCount': 0}
    backup_theme = theme_scores[1] if len(theme_scores) > 1 else {'name': '待观察', 'score': 0, 'limitUps': 0, 'scanCount': 0}

    market_gate = _build_qiao_market_gate(
        overview_text,
        search_data,
        today_count=len(today_df) if today_df is not None else 0,
        leader_height=leader_height,
        main_theme_count=int(main_theme.get('limitUps') or 0),
    )
    time_anchor = _build_qiao_time_anchor()
    main_stage = str(market_gate.get('stage') or '待观察')

    board_by_code: Dict[str, Dict[str, Any]] = {}
    for item in board_candidates:
        sector = str(item.get('sector') or '').strip()
        sector_rank = 1
        if sector:
            ranked_rows = sorted(
                sector_leader_rows.get(sector, []),
                key=lambda one: (
                    int(one.get('consecutiveDays') or 0),
                    float(one.get('sealAmountYi') or 0),
                    float(one.get('score') or 0),
                ),
                reverse=True,
            )
            for idx, row in enumerate(ranked_rows, 1):
                if row.get('code') == item.get('code'):
                    sector_rank = idx
                    break
        item['sectorRank'] = sector_rank
        if sector == main_theme.get('name') and sector_rank == 1 and int(item.get('consecutiveDays') or 0) == leader_height and leader_height >= 2:
            leader_type = '总龙头'
            selection_type = '主线龙头'
        elif sector == main_theme.get('name') and sector_rank == 1:
            leader_type = '板块龙头'
            selection_type = '主线龙头'
        elif sector == backup_theme.get('name') and sector_rank == 1:
            leader_type = '切换预备龙头'
            selection_type = '切换预备'
        else:
            leader_type = '高辨识度跟随'
            selection_type = '高辨识度跟随'

        if item.get('brokenBoardCount'):
            entry_model = '回封确认'
        elif int(item.get('firstSealInt') or 0) >= 133000 and float(item.get('turnoverRate') or 0) >= 5:
            entry_model = '下午换手板'
        else:
            entry_model = '主升打板'

        item.update({
            'leaderType': leader_type,
            'selectionType': selection_type,
            'stage': main_stage,
            'entryModel': entry_model,
            'tradeStatus': '龙头样本',
            'entryPlan': '龙头样本观察',
            'entryTrigger': '仅作主线强度样本',
            'timeAnchorPhase': time_anchor.get('phase', ''),
            'timeAnchorWindow': time_anchor.get('window', ''),
            'nextDaySellPlan': '买完第二天除非涨停，必卖；若转弱更要先走。',
            'maSupportSummary': '涨停样本，均线低吸意义较弱',
            'classificationReason': (
                f"{sector or '待观察'}｜{leader_type}｜连板 {int(item.get('consecutiveDays') or 0)}｜"
                f"首封 {item.get('firstSealTime', '待观察')}"
            ),
            'reason': (
                f"{selection_type}｜{leader_type}｜当前阶段 {main_stage}｜"
                f"更适合作为主线强度样本与次日预案锚点。"
            ),
            'matchedRules': [],
        })
        item['labels'] = _qiao_labels(
            leader_type=leader_type,
            selection_type=selection_type,
            entry_model=entry_model,
            stage=main_stage,
            volume_ratio=float(item.get('volumeRatio') or 0),
            sector_rank=int(item.get('sectorRank') or 99),
            gate_status=market_gate.get('status', '轻仓试错'),
        )
        item['matchedRules'] = _qiao_matched_rules(item)
        board_by_code[item['code']] = item

    leader_candidates = sorted(
        board_candidates,
        key=lambda item: (
            1 if item.get('leaderType') == '总龙头' else 0,
            1 if item.get('leaderType') == '板块龙头' else 0,
            int(item.get('consecutiveDays') or 0),
            float(item.get('score') or 0),
        ),
        reverse=True,
    )[:8]

    main_leader = leader_candidates[0] if leader_candidates else {
        'code': '',
        'name': '待观察',
        'leaderType': '待观察',
    }

    actionable_candidates: List[Dict[str, Any]] = []
    for scan_row in scan_candidates:
        code = _normalize_code6(scan_row.get('code'))
        if not code:
            continue
        sector = str(scan_row.get('sector') or scan_row.get('sector_name') or '').strip()
        score = int(scan_row.get('total_score') or scan_row.get('score') or 0)
        pct_change = _normalize_scan_pct_change(scan_row.get('pct_change'))
        volume_ratio = _safe_float_num(scan_row.get('volume_ratio') if scan_row.get('volume_ratio') is not None else scan_row.get('volumeRatio'))
        market_cap_yi = _to_yi(scan_row.get('market_cap') or scan_row.get('marketCap') or 0)
        sector_rank = int(scan_sector_rank_map.get(code, 999))
        if pct_change <= -6 or pct_change >= 9.8:
            continue
        if score < 70:
            continue
        if sector not in {main_theme.get('name'), backup_theme.get('name')} and score < 82:
            continue

        board_sample = board_by_code.get(code, {})
        ma_snapshot = _qiao_fetch_ma_snapshot(
            code,
            latest_price=scan_row.get('close') or scan_row.get('price'),
        )

        if code == main_leader.get('code'):
            leader_type = '总龙头' if main_leader.get('leaderType') == '总龙头' else '板块龙头'
            selection_type = '主线龙头'
        elif sector == main_theme.get('name') and sector_rank == 1:
            leader_type = '板块龙头'
            selection_type = '主线龙头'
        elif sector == backup_theme.get('name') and sector_rank <= 2:
            leader_type = '切换预备龙头'
            selection_type = '切换预备'
        else:
            leader_type = '高辨识度跟随'
            selection_type = '高辨识度跟随'

        if board_sample.get('entryModel') == '回封确认':
            entry_model = '回封确认'
        elif ma_snapshot.get('nearMa5') and main_stage in {'发酵', '主升'} and -3.5 <= pct_change <= 4.5:
            entry_model = '5日线低吸'
        elif ma_snapshot.get('nearMa10') and main_stage in {'启动', '发酵', '主升'} and -5.5 <= pct_change <= 2.5:
            entry_model = '10日线低吸'
        elif time_anchor.get('phaseCode') == 'dip_reflow' and volume_ratio >= 1.2 and -2.5 <= pct_change <= 5.0:
            entry_model = '分歧回流'
        elif time_anchor.get('phaseCode') == 'afternoon_board' and 4.5 <= pct_change <= 9.5 and volume_ratio >= 1.4:
            entry_model = '下午换手板'
        elif pct_change >= 6.5 and volume_ratio >= 1.6:
            entry_model = '主升打板'
        elif time_anchor.get('phaseCode') in {'after_close', 'preopen', 'auction', 'tail_review'}:
            entry_model = '竞价确认'
        else:
            entry_model = '观察'

        plan = _qiao_entry_plan_from_model(
            entry_model,
            phase_code=time_anchor.get('phaseCode', ''),
            gate_status=market_gate.get('status', '轻仓试错'),
        )
        position_ratio = _qiao_position_ratio(
            code=code,
            gate_status=market_gate.get('status', '轻仓试错'),
            leader_type=leader_type,
            entry_model=entry_model,
            market_cap_yi=market_cap_yi,
        )
        next_day_sell_plan = (
            '买完第二天除非继续涨停，否则优先冲高兑现；弱开弱走直接撤。'
            if entry_model in {'下午换手板', '主升打板', '回封确认'}
            else '买完第二天除非涨停必卖，分时走弱不格局。'
        )
        labels = _qiao_labels(
            leader_type=leader_type,
            selection_type=selection_type,
            entry_model=entry_model,
            stage=main_stage,
            volume_ratio=volume_ratio,
            sector_rank=sector_rank,
            gate_status=market_gate.get('status', '轻仓试错'),
        )

        classification_reason = (
            f"{sector or '待观察'}｜{leader_type}｜{ma_snapshot.get('maSupportSummary', '均线待观察')}｜"
            f"量比 {volume_ratio:.2f}｜评分 {score}"
        )
        reason = (
            f"{selection_type}｜{leader_type}｜当前阶段 {main_stage}｜"
            f"{entry_model}｜{classification_reason}｜"
            f"{'主线题材优先' if sector == main_theme.get('name') else '作为切换预备保留'}。"
        )
        item = {
            'code': code,
            'name': str(scan_row.get('name') or code),
            'sector': sector,
            'price': round(_safe_float_num(scan_row.get('close') or scan_row.get('price')), 2),
            'changePct': round(pct_change, 2),
            'score': score,
            'grade': str(scan_row.get('grade') or ('S' if score >= 82 else 'A' if score >= 74 else 'B')),
            'adviseType': '龙头主升',
            'leaderType': leader_type,
            'selectionType': selection_type,
            'stage': main_stage,
            'tradeStatus': plan['tradeStatus'],
            'entryPlan': plan['entryPlan'],
            'entryModel': entry_model,
            'entryTrigger': plan['entryTrigger'],
            'positionRatio': position_ratio,
            'holdPeriod': '1-2 天超短，次日不涨停优先兑现',
            'buyRange': (
                '围绕 5/10 日线、分时均线或分歧回流点分批介入'
                if entry_model in {'5日线低吸', '10日线低吸', '分歧回流'}
                else '只在回封、分时前高突破或换手充分后跟随'
            ),
            'stopLoss': '跌破承接位、均线失守或主线掉队就撤',
            'nextDaySellPlan': next_day_sell_plan,
            'targetPrice': '次日优先看冲高兑现与是否继续涨停',
            'riskLevel': '低' if entry_model in {'5日线低吸', '10日线低吸'} else '中',
            'signal': f'{selection_type}/{entry_model}/{plan["tradeStatus"]}',
            'reason': reason,
            'classificationReason': classification_reason,
            'meta': (
                f"评分 {score}｜量比 {volume_ratio:.2f}｜板块热度 {int(main_theme.get('score') or 0)}｜"
                f"{ma_snapshot.get('maSupportSummary', '均线待观察')}"
            ),
            'labels': labels,
            'matchedRules': [],
            'ma5': ma_snapshot.get('ma5', 0),
            'ma10': ma_snapshot.get('ma10', 0),
            'ma20': ma_snapshot.get('ma20', 0),
            'maSupportSummary': ma_snapshot.get('maSupportSummary', ''),
            'volumeRatio': round(volume_ratio, 2),
            'marketCapYi': market_cap_yi,
            'timeAnchorPhase': time_anchor.get('phase', ''),
            'timeAnchorWindow': time_anchor.get('window', ''),
            'actionableNow': plan['tradeStatus'] in {'可低吸', '可半路'} and market_gate.get('status') != '空仓等待',
        }
        item['matchedRules'] = _qiao_matched_rules(item)
        actionable_candidates.append(item)

    actionable_candidates.sort(
        key=lambda item: (
            1 if item.get('actionableNow') else 0,
            1 if item.get('selectionType') == '主线龙头' else 0,
            1 if item.get('leaderType') in {'总龙头', '板块龙头'} else 0,
            float(item.get('score') or 0),
            float(item.get('volumeRatio') or 0),
            float(item.get('changePct') or 0),
        ),
        reverse=True,
    )

    recommended = [item for item in actionable_candidates if item.get('tradeStatus') != '观察'][:3]
    if not recommended:
        recommended = actionable_candidates[:3]

    entry_model_counts: Dict[str, int] = {}
    leader_type_counts: Dict[str, int] = {}
    label_counts: Dict[str, int] = {}
    for item in actionable_candidates:
        entry_model = str(item.get('entryModel') or '').strip()
        leader_type = str(item.get('leaderType') or '').strip()
        if entry_model:
            entry_model_counts[entry_model] = entry_model_counts.get(entry_model, 0) + 1
        if leader_type:
            leader_type_counts[leader_type] = leader_type_counts.get(leader_type, 0) + 1
        for label in item.get('labels') or []:
            text = str(label or '').strip()
            if text:
                label_counts[text] = label_counts.get(text, 0) + 1

    entry_playbook_defs = [
        ('5日线低吸', '强势龙头回踩 5 日线时低吸，买在转折。'),
        ('10日线低吸', '更深一层的分歧吸，要求主升未坏。'),
        ('分歧回流', '早盘分歧后重新放量转强，回流才出手。'),
        ('下午换手板', '偏爱充分换手后的下午板，抛压更小。'),
        ('主升打板', '只打主升最强，不打模式外杂毛板。'),
        ('回封确认', '炸板后回封更看承接与队友。'),
    ]
    entry_playbook = [
        {
            'type': name,
            'count': entry_model_counts.get(name, 0),
            'description': desc,
        }
        for name, desc in entry_playbook_defs
    ]

    leader_paths_defs = [
        ('总龙头', '市场总辨识度最高，主线最强承载。'),
        ('板块龙头', '所属主线板块的第一强票。'),
        ('高辨识度跟随', '不是绝对龙头，但市场认知度高。'),
        ('切换预备龙头', '次主线里可能走出来的预备选手。'),
    ]
    leader_paths = [
        {
            'type': name,
            'count': leader_type_counts.get(name, 0),
            'description': desc,
        }
        for name, desc in leader_paths_defs
    ]

    cycle_map = [
        {'stage': '启动', 'count': 1 if main_stage == '启动' else 0, 'description': '题材刚异动，先轻仓试错。'},
        {'stage': '发酵', 'count': 1 if main_stage == '发酵' else 0, 'description': '联动增强，可逐步聚焦龙头。'},
        {'stage': '主升', 'count': 1 if main_stage == '主升' else 0, 'description': '龙头最具盈亏比，分歧转强优先。'},
        {'stage': '高潮', 'count': 1 if main_stage == '高潮' else 0, 'description': '一致性过强，更多偏兑现。'},
        {'stage': '退潮', 'count': 1 if main_stage == '退潮' else 0, 'description': '高位风险释放，优先休息。'},
    ]

    label_hits = [
        {'label': label, 'count': count}
        for label, count in sorted(label_counts.items(), key=lambda one: (one[1], one[0]), reverse=True)[:12]
    ]

    daily_rule_hits = [
        {
            'title': '主线优先',
            'status': main_theme.get('name', '待观察'),
            'detail': f"当前主线优先看 {main_theme.get('name', '待观察')}，只在主线里找最强。",
        },
        {
            'title': '只做主升',
            'status': main_stage,
            'detail': '调整段不硬做，退潮期宁可降低出手频率。',
        },
        {
            'title': '只做龙头',
            'status': main_leader.get('name', '待观察'),
            'detail': f"{main_leader.get('leaderType', '待观察')}：{main_leader.get('name', '待观察')}({main_leader.get('code', '')})",
        },
        {
            'title': '5/10 日线低吸',
            'status': f"{entry_model_counts.get('5日线低吸', 0) + entry_model_counts.get('10日线低吸', 0)}只命中",
            'detail': '只吸强势龙头，不吸冷门弱票。',
        },
        {
            'title': '分歧回流',
            'status': f"{entry_model_counts.get('分歧回流', 0)}只命中",
            'detail': '分歧后能重新放量转强，才配叫买点。',
        },
        {
            'title': '下午换手板',
            'status': f"{entry_model_counts.get('下午换手板', 0)}只命中",
            'detail': '偏爱充分换手后的下午板，追求更高确定性。',
        },
        {
            'title': '次日必卖',
            'status': '纪律常驻',
            'detail': '买完第二天除非涨停，必卖。',
        },
        {
            'title': '跟随不预判',
            'status': market_gate.get('status', '待观察'),
            'detail': market_gate.get('action', '等待更多市场确认'),
        },
    ]

    main_judgement = {
        'mainTheme': main_theme.get('name', '待观察'),
        'backupTheme': backup_theme.get('name', '待观察'),
        'stage': main_stage,
        'leader': main_leader.get('name', '待观察'),
        'leaderCode': main_leader.get('code', ''),
        'summary': (
            f"{main_theme.get('name', '待观察')} 当前更像主线，阶段偏 {main_stage}，"
            f"优先看 {main_leader.get('name', '待观察')} 这一条龙头路径。"
        ),
        'reasons': [
            f"主线强度：涨停 {int(main_theme.get('limitUps') or 0)} 只，扫描命中 {int(main_theme.get('scanCount') or 0)} 只",
            f"次主线：{backup_theme.get('name', '待观察')}",
            f"空间板：{leader_height} 连板",
        ],
    }

    step_outputs = [
        {
            'step': 1,
            'title': '主线识别',
            'summary': f"当前主线更偏 {main_theme.get('name', '待观察')}，次主线看 {backup_theme.get('name', '待观察')}。",
            'frameworkLines': [
                '先找市场主线，再谈个股，不先看题材就不谈买点。',
                '主线判断优先看涨停家数、板块联动、辨识度与市场关注度。',
                '不能只说热门板块，必须明确谁是龙头、谁只是跟随。',
            ],
            'lines': [
                main_judgement.get('summary', ''),
                *main_judgement.get('reasons', [])[:2],
            ],
        },
        {
            'step': 2,
            'title': '情绪阶段',
            'summary': f"当前更偏 {main_stage}，市场闸门 {market_gate.get('status', '待观察')}。",
            'frameworkLines': [
                '启动 / 发酵 / 主升 / 高潮 / 退潮决定了能不能做、该怎么做。',
                '主升阶段优先参与，高潮更重兑现，退潮优先休息。',
                '行情好，多做；行情不好，多休息。',
            ],
            'lines': list(market_gate.get('reasons') or [])[:3],
        },
        {
            'step': 3,
            'title': '龙头路径',
            'summary': f"总龙头看 {main_leader.get('name', '待观察')}，只做龙头或最强跟随。",
            'frameworkLines': [
                '龙头是走出来的，不是预判出来的。',
                '只做总龙头、板块龙头、高辨识度跟随与切换预备龙头。',
                '模式外的弱票不参与，避免浪费仓位与注意力。',
            ],
            'lines': [
                f"{item.get('name','')}({item.get('code','')})｜{item.get('leaderType','待观察')}｜{item.get('selectionType','待观察')}｜{item.get('sector','待观察')}"
                for item in leader_candidates[:4]
            ] or ['暂无清晰龙头路径，优先等待主线明确。'],
        },
        {
            'step': 4,
            'title': '入场模型',
            'summary': f"优先 {time_anchor.get('executionFocus', '待观察')}，当前可买 {len(actionable_candidates)} 只。",
            'frameworkLines': [
                '核心模型只有 5日线低吸 / 10日线低吸 / 分歧回流 / 下午换手板 / 主升打板 / 回封确认。',
                '低吸是买在转折，打板是买在确认，二者都服务于主升龙头。',
                '有量才安全，无量不上，无量不追。',
            ],
            'lines': [
                f"{item.get('name','')}({item.get('code','')})｜{item.get('entryModel','待观察')}｜{item.get('tradeStatus','待观察')}｜{item.get('maSupportSummary','均线待观察')}"
                for item in actionable_candidates[:4]
            ] or ['当前没有可执行的主线龙头模型，继续等待。'],
        },
        {
            'step': 5,
            'title': '次日卖出',
            'summary': '买完第二天除非涨停，必卖；走弱就卖，不格局。',
            'frameworkLines': [
                '超短的核心不是恋战，而是次日纪律极强。',
                '不及预期就走，弱开弱走更要快。',
                '跑得快，是杜绝大亏的前提。',
            ],
            'lines': [
                f"{item.get('name','')}({item.get('code','')})｜{item.get('nextDaySellPlan','待观察')}"
                for item in recommended[:3]
            ] or ['没有进入执行模式的个股时，不提前编造卖点。'],
        },
    ]

    market_commentary = (
        f"主线偏 {main_theme.get('name','待观察')}，阶段 {main_stage}，龙头看 {main_leader.get('name','待观察')}。"
        if main_theme.get('name') and main_theme.get('name') != '待观察'
        else '主线尚不清晰，先等最强方向自己走出来。'
    )
    if market_gate.get('status') == '放行':
        position_advice = f"{time_anchor.get('phase','当前时段')}可重点参与，优先龙头低吸与下午换手板。"
    elif market_gate.get('status') == '轻仓试错':
        position_advice = f"{time_anchor.get('phase','当前时段')}轻仓试错，只做最强龙头与分歧转强。"
    else:
        position_advice = f"{time_anchor.get('phase','当前时段')}以等待为主，不做主观抄底。"
    risk_warning = '退潮期硬做、预判式买入、模式外弱票，是回撤的主要来源。'

    return {
        'kind': 'qiao',
        'version': 'v1',
        'generatedAt': datetime.now().isoformat(),
        'stats': {
            'todayLimitUps': len(today_df) if today_df is not None else 0,
            'leaderCount': len(leader_candidates),
            'actionableCount': len(actionable_candidates),
            'lowAbsorbCount': entry_model_counts.get('5日线低吸', 0) + entry_model_counts.get('10日线低吸', 0),
            'boardModelCount': entry_model_counts.get('下午换手板', 0) + entry_model_counts.get('主升打板', 0) + entry_model_counts.get('回封确认', 0),
            'marketGateStatus': market_gate.get('status'),
        },
        'marketGate': market_gate,
        'timeAnchor': time_anchor,
        'mainTheme': {
            'name': main_theme.get('name', '待观察'),
            'stage': main_stage,
            'strength': '强' if market_gate.get('status') == '放行' else '中' if market_gate.get('status') == '轻仓试错' else '弱',
        },
        'backupTheme': {
            'name': backup_theme.get('name', '待观察'),
            'reason': f"当前次主线更偏 {backup_theme.get('name', '待观察')}，可作为切换预备。",
        },
        'mainLeader': {
            'code': main_leader.get('code', ''),
            'name': main_leader.get('name', '待观察'),
            'leaderType': main_leader.get('leaderType', '待观察'),
        },
        'entryStyle': time_anchor.get('executionFocus', ''),
        'sellDiscipline': '买完第二天除非涨停，必卖',
        'strategyPanels': {
            'timeAnchor': time_anchor,
            'mainJudgement': main_judgement,
            'cycleMap': cycle_map,
            'leaderPaths': leader_paths,
            'entryPlaybook': entry_playbook,
            'labelHits': label_hits,
            'dailyRuleHits': daily_rule_hits,
        },
        'leaderCandidates': leader_candidates,
        'actionableCandidates': actionable_candidates[:8],
        'recommendedStocks': recommended,
        'stepOutputs': step_outputs,
        'marketCommentary': market_commentary,
        'positionAdvice': position_advice,
        'riskWarning': risk_warning,
        'searchDataPreview': (search_data or '')[:1200],
    }


def _build_qiao_execution_context_text(artifacts: Dict[str, Any]) -> str:
    if not artifacts:
        return '【暂无乔帮主执行工件】'

    stats = artifacts.get('stats', {})
    market_gate = artifacts.get('marketGate', {})
    time_anchor = artifacts.get('timeAnchor', {})
    main_theme = artifacts.get('mainTheme', {})
    backup_theme = artifacts.get('backupTheme', {})
    main_leader = artifacts.get('mainLeader', {})
    lines = [
        '## 乔帮主执行工件（系统预处理）',
        f"- 时间锚点：{time_anchor.get('phase', '待观察')}｜{time_anchor.get('window', '等待更多信号')}",
        f"- 市场闸门：{market_gate.get('status', '待观察')}｜{market_gate.get('action', '等待更多信号')}",
        f"- 当前主线：{main_theme.get('name', '待观察')}｜阶段 {main_theme.get('stage', '待观察')}",
        f"- 次主线：{backup_theme.get('name', '待观察')}",
        f"- 当前龙头：{main_leader.get('name', '待观察')}({main_leader.get('code', '')})｜{main_leader.get('leaderType', '待观察')}",
        f"- 主线样本：{stats.get('leaderCount', 0)} 只",
        f"- 可买候选：{stats.get('actionableCount', 0)} 只",
        '',
        '### 乔帮主当前偏好的可买候选',
    ]
    for item in artifacts.get('actionableCandidates', [])[:6]:
        lines.append(
            f"- {item.get('name','')}({item.get('code','')})｜{item.get('selectionType','待观察')}｜"
            f"{item.get('leaderType','待观察')}｜{item.get('entryModel','待观察')}｜"
            f"{item.get('tradeStatus','待观察')}｜{item.get('maSupportSummary','均线待观察')}｜"
            f"{' / '.join((item.get('labels') or [])[:3])}"
        )
    if not artifacts.get('actionableCandidates'):
        for item in artifacts.get('leaderCandidates', [])[:4]:
            lines.append(
                f"- {item.get('name','')}({item.get('code','')})｜{item.get('leaderType','待观察')}｜"
                f"{item.get('selectionType','待观察')}｜{item.get('entryModel','待观察')}｜"
                f"{item.get('nextDaySellPlan','待观察')}"
            )
    return '\n'.join(lines)


def _build_qiao_fallback_structured(artifacts: Dict[str, Any]) -> Dict[str, Any]:
    recommended = list(artifacts.get('recommendedStocks') or [])
    return {
        'agentId': 'qiao',
        'agentName': '乔帮主',
        'stance': 'bull' if recommended else 'neutral',
        'confidence': 80 if recommended else 54,
        'marketCommentary': artifacts.get('marketCommentary', ''),
        'positionAdvice': artifacts.get('positionAdvice', ''),
        'riskWarning': artifacts.get('riskWarning', ''),
        'mainTheme': artifacts.get('mainTheme', {}),
        'backupTheme': artifacts.get('backupTheme', {}),
        'mainLeader': artifacts.get('mainLeader', {}),
        'entryStyle': artifacts.get('entryStyle', ''),
        'sellDiscipline': artifacts.get('sellDiscipline', ''),
        'recommendedStocks': recommended,
    }


def _merge_qiao_structured(structured: Dict[str, Any], artifacts: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(structured or {})
    recommended = list(merged.get('recommendedStocks') or [])
    candidate_sources = (
        list(artifacts.get('recommendedStocks') or [])
        + list(artifacts.get('actionableCandidates') or [])
        + list(artifacts.get('leaderCandidates') or [])
    )
    candidates_by_code = {
        _normalize_code6(item.get('code')): item
        for item in candidate_sources
        if _normalize_code6(item.get('code'))
    }

    merged_recs = []
    for item in recommended:
        code = _normalize_code6(item.get('code'))
        candidate = candidates_by_code.get(code, {})
        one = dict(candidate) if candidate else {}
        one.update(item)
        for key, value in candidate.items():
            one.setdefault(key, value)
        if code:
            one['code'] = code
        merged_recs.append(one)

    artifact_recommended = list(artifacts.get('recommendedStocks') or [])
    merged['recommendedStocks'] = artifact_recommended[:3] if artifact_recommended else merged_recs[:3]
    merged['mainTheme'] = merged.get('mainTheme') or artifacts.get('mainTheme', {})
    merged['backupTheme'] = merged.get('backupTheme') or artifacts.get('backupTheme', {})
    merged['mainLeader'] = merged.get('mainLeader') or artifacts.get('mainLeader', {})
    merged['entryStyle'] = merged.get('entryStyle') or artifacts.get('entryStyle', '')
    merged['sellDiscipline'] = merged.get('sellDiscipline') or artifacts.get('sellDiscipline', '')
    merged['personaExecution'] = {
        'kind': 'qiao',
        'version': artifacts.get('version', 'v1'),
        'coreObjective': '只做主线龙头与主升机会，在分歧转强处低吸或打板，次日严格兑现',
        'stats': artifacts.get('stats', {}),
        'marketGate': artifacts.get('marketGate', {}),
        'timeAnchor': artifacts.get('timeAnchor', {}),
        'mainTheme': artifacts.get('mainTheme', {}),
        'backupTheme': artifacts.get('backupTheme', {}),
        'mainLeader': artifacts.get('mainLeader', {}),
        'entryStyle': artifacts.get('entryStyle', ''),
        'sellDiscipline': artifacts.get('sellDiscipline', ''),
        'strategyPanels': artifacts.get('strategyPanels', {}),
        'leaderCandidates': artifacts.get('leaderCandidates', []),
        'actionableCandidates': artifacts.get('actionableCandidates', []),
        'stepOutputs': artifacts.get('stepOutputs', []),
    }

    if not str(merged.get('marketCommentary') or '').strip():
        merged['marketCommentary'] = artifacts.get('marketCommentary', '')
    if not str(merged.get('positionAdvice') or '').strip():
        merged['positionAdvice'] = artifacts.get('positionAdvice', '')
    if not str(merged.get('riskWarning') or '').strip():
        merged['riskWarning'] = artifacts.get('riskWarning', '')

    return merged


def _build_qiao_markdown_summary(structured: Dict[str, Any], artifacts: Dict[str, Any]) -> str:
    market_gate = artifacts.get('marketGate', {})
    time_anchor = artifacts.get('timeAnchor', {})
    main_theme = artifacts.get('mainTheme', {})
    main_leader = artifacts.get('mainLeader', {})
    lines = [
        f"【时间锚点】{time_anchor.get('phase','待观察')}｜{time_anchor.get('window','等待更多信号')}",
        f"【市场闸门】{market_gate.get('status','待观察')}｜{market_gate.get('action','等待更多信号')}",
        f"【主线判断】{main_theme.get('name','待观察')}｜阶段 {main_theme.get('stage','待观察')}｜龙头 {main_leader.get('name','待观察')}",
        f"【市场解读】{structured.get('marketCommentary') or artifacts.get('marketCommentary') or '主线尚未完全明确'}",
        f"【仓位建议】{structured.get('positionAdvice') or artifacts.get('positionAdvice') or '轻仓试错，优先主线龙头'}",
        f"【风险提示】{structured.get('riskWarning') or artifacts.get('riskWarning') or '预判式买入和退潮硬做最伤'}",
    ]
    recs = (structured.get('recommendedStocks') or [])[:3]
    if recs:
        lines.append('【重点候选】')
        for item in recs:
            lines.append(
                f"- {item.get('name','')}({item.get('code','')})｜{item.get('selectionType','待观察')}｜"
                f"{item.get('leaderType','待观察')}｜{item.get('entryModel') or item.get('entryPlan','观察')}｜"
                f"{item.get('nextDaySellPlan') or item.get('reason') or item.get('meta') or ''}｜"
                f"{' / '.join((item.get('labels') or [])[:3])}"
            )
    return '\n'.join(lines)


def _build_jia_time_anchor(now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now()
    hhmm = now.hour * 100 + now.minute
    label = now.strftime('%H:%M')

    if hhmm < 925:
        return {
            'phaseCode': 'preopen',
            'phase': '盘前情绪预案',
            'window': f'{label}｜先定情绪，再定龙头，不做脱离周期的预判',
            'summary': '盘前先锁定情绪阶段、主流题材和龙头结构，原则上不提前抢主观先手。',
            'executionFocus': '情绪定档与龙头预备',
            'positionBias': '不开新仓，最多保留观察仓',
            'rules': [
                '先看赚钱效应，再谈交易机会。',
                '盘前只做预案，不做脱离市场的信仰单。',
                '先列主线、龙头、切换候选，再等竞价确认。',
            ],
        }
    if hhmm < 930:
        return {
            'phaseCode': 'auction',
            'phase': '竞价定强弱',
            'window': f'{label}｜看龙头竞价、看队友强弱、看是否延续赚钱效应',
            'summary': '竞价阶段重点验证主流题材是否延续，龙头与队友是否继续占据资金焦点。',
            'executionFocus': '竞价确认，不做竞价梭哈',
            'positionBias': '轻仓确认，等盘面自己说话',
            'rules': [
                '竞价强不等于全天强，但竞价弱往往意味着先别急。',
                '队友强，龙头一般竞价也不会太差。',
                '竞价只做方向确认，不把竞价当全部答案。',
            ],
        }
    if hhmm < 1030:
        return {
            'phaseCode': 'morning_anchor',
            'phase': '早盘龙头定锚',
            'window': f'{label}｜优先确认谁是最强，谁只是跟风',
            'summary': '早盘是给情绪定档、给龙头定锚的关键窗口，弱票与伪强应尽早剔除。',
            'executionFocus': '龙头定锚与强弱切割',
            'positionBias': '只做最强，不在杂毛里找补涨',
            'rules': [
                '只围绕主流题材里的最强龙头展开。',
                '跟风再好看，也不如龙头抗分歧。',
                '退潮感增强时，宁可放弃也不硬做。',
            ],
        }
    if hhmm < 1400:
        return {
            'phaseCode': 'divergence_buy',
            'phase': '分歧试错',
            'window': f'{label}｜只在分歧低吸、真回封与反包确认里找机会',
            'summary': '午前到午后早段更适合做分歧低吸、真回封打板与反包确认，不追一致性末端。',
            'executionFocus': '分歧低吸 / 真回封 / 反包确认',
            'positionBias': '围绕最强龙头试错，不做补涨',
            'rules': [
                '龙头未死且承接在，分歧才是买点。',
                '回封要快、要放量、要封单稳定，假回封不碰。',
                '反包只能做龙头重夺主动权的确认，不做弱修复。',
            ],
        }
    if hhmm < 1450:
        return {
            'phaseCode': 'rebound_board',
            'phase': '回封与反包',
            'window': f'{label}｜重点看真假回封与是否出现龙头切换',
            'summary': '午后更适合验证真回封、辨别假回封，并观察是否出现新龙头切换信号。',
            'executionFocus': '真回封 / 反包确认 / 龙头切换',
            'positionBias': '只做能重新聚拢情绪的强者',
            'rules': [
                '真回封能重新聚拢合力，假回封常常只是拖时间。',
                '旧龙头掉队时，先看新龙头是否真的带动板块。',
                '只做最抗分歧的票，不给弱票第二次机会。',
            ],
        }
    if hhmm < 1500:
        return {
            'phaseCode': 'tail_caution',
            'phase': '尾盘谨慎',
            'window': f'{label}｜尾盘更重复核与次日预案，不追情绪末端',
            'summary': '尾盘一致性过强更像次日兑现盘，优先做次日预案，而不是今天最后一脚。',
            'executionFocus': '次日预备池',
            'positionBias': '不追尾盘强行一致',
            'rules': [
                '尾盘买点必须比早盘更谨慎。',
                '没有明显真回封和龙头修复时，不为尾盘点火买单。',
                '尾盘更重要的是确认强弱与切换，而不是情绪冲动。',
            ],
        }
    return {
        'phaseCode': 'after_close',
        'phase': '收盘复核',
        'window': f'{label}｜只做次日计划，不虚构盘中执行',
        'summary': '收盘后重点复核情绪阶段、主流题材、龙头结构与次日竞价预案，不假装还能盘中买入。',
        'executionFocus': '次日竞价确认 / 次日分歧预案',
        'positionBias': '收盘后不提供盘中追价建议',
        'rules': [
            '收盘后的推荐优先输出次日可确认机会。',
            '若情绪转退潮，核心是降低仓位而不是硬找买点。',
            '次日重点看竞价强弱、队友表现和龙头是否继续最强。',
        ],
    }


def _jia_fetch_strength_snapshot(code: str, latest_price: Any = 0) -> Dict[str, Any]:
    snapshot = _qiao_fetch_ma_snapshot(code, latest_price)
    support_summary = '均线承接待观察'
    if snapshot.get('nearMa5'):
        support_summary = '贴近 5 日线，具备分歧低吸观察位'
    elif snapshot.get('nearMa10'):
        support_summary = '贴近 10 日线，具备更深分歧承接位'
    elif snapshot.get('trendBias') == '主升':
        support_summary = '主升结构仍在，但更适合等分歧后承接'
    elif snapshot.get('trendBias') == '调整':
        support_summary = '结构偏调整，除非反包确认否则谨慎'
    snapshot['supportSummary'] = support_summary
    return snapshot


def _build_jia_emotion_cycle(
    overview_text: str,
    search_data: str,
    *,
    today_count: int,
    leader_height: int,
    main_theme_count: int,
    board_candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    overview_metrics = _parse_market_overview_metrics(overview_text)
    text = f'{overview_text}\n{search_data}'
    positive_hits = sum(
        1 for kw in ('回暖', '修复', '赚钱效应', '主线明确', '爆发', '连板', '放量', '强势')
        if kw in text
    )
    negative_hits = sum(
        1 for kw in ('退潮', '亏钱效应', '跌停', '恐慌', '扩散', '补跌', '无人接力', '炸板增多')
        if kw in text
    )
    broken_count = sum(1 for item in board_candidates if int(item.get('brokenBoardCount') or 0) > 0)
    broken_ratio = (broken_count / max(len(board_candidates), 1)) if board_candidates else 0.0

    if ('龙头跌停' in text or '亏钱效应扩散' in text or '退潮' in text) and (negative_hits >= 2 or today_count < 28):
        stage = '退潮'
    elif today_count <= 12 and leader_height <= 2 and negative_hits >= positive_hits:
        stage = '冰点'
    elif today_count >= 35 and leader_height >= 4 and main_theme_count >= 3 and positive_hits >= negative_hits:
        stage = '主升'
    elif broken_ratio >= 0.35 and today_count >= 18 and leader_height >= 3:
        stage = '分歧'
    elif today_count >= 18 and leader_height >= 2 and positive_hits + overview_metrics['positiveCount'] >= negative_hits:
        stage = '回暖'
    else:
        stage = '分歧' if today_count >= 18 else '冰点'

    mapping = {
        '冰点': {
            'status': '冰点试错',
            'tradeable': False,
            'action': '空仓或极轻仓试错，只保留观察仓。',
            'positionCap': '0-20%',
        },
        '回暖': {
            'status': '轻仓试错',
            'tradeable': True,
            'action': '轻仓试错，只做主流题材里的最强龙头。',
            'positionCap': '30-50%',
        },
        '主升': {
            'status': '重仓进攻',
            'tradeable': True,
            'action': '主升阶段重点进攻，优先龙头分歧低吸、真回封与反包确认。',
            'positionCap': '70-100%',
        },
        '分歧': {
            'status': '只做强者',
            'tradeable': True,
            'action': '分歧期只做最抗分歧的龙头，拒绝补涨和跟风。',
            'positionCap': '30-50%',
        },
        '退潮': {
            'status': '空仓',
            'tradeable': False,
            'action': '退潮优先空仓，等待新周期龙头和赚钱效应重新出现。',
            'positionCap': '0%',
        },
    }
    current = mapping[stage]
    reasons = []
    if overview_metrics['metrics']:
        reasons.append(
            '指数概况：' + ' / '.join(
                f"{item['name']}{item['pct']:+.2f}%"
                for item in overview_metrics['metrics'][:4]
            )
        )
    reasons.append(f'涨停池 {today_count} 只，空间板 {leader_height} 连板，主线联动 {main_theme_count} 只')
    reasons.append(f'炸板样本 {broken_count} 只，占比 {broken_ratio * 100:.0f}%')
    reasons.append(f'情绪判断：{stage}')
    reasons.append(f'执行结论：{current["action"]}')

    summary = {
        '冰点': '亏钱效应占优，原则上空仓或极轻仓试错。',
        '回暖': '赚钱效应恢复，可轻仓围绕龙头试错。',
        '主升': '连板高度与板块爆发同步抬升，适合围绕最强龙头进攻。',
        '分歧': '分化加大，但强者仍强，只做最抗分歧的龙头。',
        '退潮': '高位风险释放，优先休息，等待新龙头出现。',
    }[stage]

    return {
        'stage': stage,
        'status': current['status'],
        'tradeable': current['tradeable'],
        'action': current['action'],
        'positionCap': current['positionCap'],
        'brokenRatio': round(broken_ratio * 100, 2),
        'summary': summary,
        'reasons': reasons,
    }


def _jia_rebound_seal_verdict(
    *,
    broken_board_count: Any,
    last_seal_int: int,
    turnover_rate: Any,
    seal_amount_yi: Any,
) -> Dict[str, str]:
    broken = _safe_int_num(broken_board_count)
    turnover = _safe_float_num(turnover_rate)
    seal_amount = _safe_float_num(seal_amount_yi)

    if broken <= 0:
        return {
            'reboundSealVerdict': '待观察',
            'sealVerdictSummary': '暂无回封结构，更多看分歧低吸或反包确认。',
        }
    if broken == 1 and last_seal_int and last_seal_int <= 110000 and turnover >= 5 and seal_amount >= 0.05:
        return {
            'reboundSealVerdict': '真回封',
            'sealVerdictSummary': '回封较快、放量且封单稳定，接近可参与的真回封。',
        }
    if broken >= 3 or (last_seal_int and last_seal_int >= 143000):
        return {
            'reboundSealVerdict': '假回封',
            'sealVerdictSummary': '回封偏慢或反复炸板，更像假回封，原则上回避。',
        }
    return {
        'reboundSealVerdict': '待观察',
        'sealVerdictSummary': '存在回封迹象，但真假仍需继续观察。',
    }


def _jia_entry_plan(
    buy_point_type: str,
    *,
    phase_code: str,
    emotion_stage: str,
    tradeable: bool,
) -> Dict[str, str]:
    if not tradeable:
        return {
            'tradeStatus': '空仓',
            'entryPlan': '等待下一轮赚钱效应',
            'entryTrigger': '情绪从冰点/退潮重新回暖后再考虑出手',
        }

    closed_phase = phase_code in {'preopen', 'auction', 'tail_caution', 'after_close'}
    mapping = {
        '分歧低吸': ('可交易', '围绕龙头分歧承接位低吸', '龙头未死、分歧后承接在，重新翻红或站回承接位'),
        '回封打板': ('回封关注', '只做真回封，不扫假回封', '涨停被砸后快速回封，放量且封单稳定增加'),
        '反包确认': ('可交易', '反包重新走强后再跟随', '前一日分歧后重新转强，确认重夺主动权'),
        '待观察': ('观察', '等待更清晰的龙头信号', '等待最强龙头或真回封自己走出来'),
    }
    trade_status, entry_plan, entry_trigger = mapping.get(buy_point_type, mapping['待观察'])
    if closed_phase and trade_status in {'可交易', '回封关注'}:
        trade_status = '竞价确认'
        entry_plan = '次日竞价确认'
    if emotion_stage == '冰点' and trade_status in {'可交易', '回封关注'}:
        trade_status = '试错仓'
    return {
        'tradeStatus': trade_status,
        'entryPlan': entry_plan,
        'entryTrigger': entry_trigger,
    }


def _jia_position_ratio(
    *,
    emotion_stage: str,
    leader_type: str,
    buy_point_type: str,
) -> str:
    if emotion_stage == '退潮':
        return '总仓 0%，空仓'
    if emotion_stage == '冰点':
        return '总仓 0-20%，单票试错 1/10-1/8'
    if emotion_stage == '回暖':
        return '总仓 30-50%，单票 1/6-1/4'
    if emotion_stage == '分歧':
        return '总仓 30-50%，只做最强，单票 1/6-1/4'
    if leader_type in {'总龙头', '板块龙头'} and buy_point_type in {'回封打板', '反包确认'}:
        return '总仓 70-100%，单票 1/3-1/2'
    return '总仓 70-100%，单票 1/4-1/3'


def _jia_labels(
    *,
    emotion_stage: str,
    leader_type: str,
    buy_point_type: str,
    rebound_seal_verdict: str,
    theme_role: str,
    trade_status: str,
) -> List[str]:
    labels: List[str] = ['情绪优先']
    if leader_type in {'总龙头', '板块龙头', '次龙头'}:
        labels.append('只做龙头')
    else:
        labels.append('只做强者')

    stage_map = {
        '冰点': '冰点试错',
        '回暖': '回暖试错',
        '主升': '主升进攻',
        '分歧': '分歧只做强者',
        '退潮': '退潮空仓',
    }
    labels.append(stage_map.get(emotion_stage, emotion_stage))
    if theme_role == '切换候选':
        labels.append('龙头切换')
    if buy_point_type == '分歧低吸':
        labels.append('分歧低吸')
    elif buy_point_type == '回封打板':
        labels.append('回封打板')
    elif buy_point_type == '反包确认':
        labels.append('反包确认')
    if rebound_seal_verdict == '真回封':
        labels.append('真回封')
    elif rebound_seal_verdict == '假回封':
        labels.append('假回封回避')
    if trade_status == '空仓':
        labels.append('空仓')

    seen = set()
    deduped: List[str] = []
    for label in labels:
        text = str(label or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped[:7]


def _jia_matched_rules(item: Dict[str, Any]) -> List[Dict[str, str]]:
    rules = [
        {
            'title': '情绪阶段',
            'detail': f"{item.get('emotionStage', '待观察')}｜{item.get('emotionFit', '等待更清晰的赚钱效应')}",
        },
        {
            'title': '主流与龙头',
            'detail': f"{item.get('selectionType', '待观察')}｜{item.get('leaderType', '待观察')}｜{item.get('sector', '待观察')}",
        },
        {
            'title': '买点模型',
            'detail': f"{item.get('buyPointType', '待观察')}｜{item.get('entryTrigger', '等待触发')}",
        },
        {
            'title': '回封真假',
            'detail': f"{item.get('reboundSealVerdict', '待观察')}｜{item.get('sealVerdictSummary', '暂无回封判断')}",
        },
        {
            'title': '卖点与切换',
            'detail': f"{item.get('exitTrigger', '龙头强转弱就走')}｜{item.get('rotationSignal', '暂未出现明确切换')}",
        },
    ]
    return [rule for rule in rules if rule.get('title') and rule.get('detail')]


def _build_jia_execution_artifacts(search_data: str = '', overview_text: str = '') -> Dict[str, Any]:
    from market_data import _ak_eastmoney_direct, _get_ak

    today = datetime.now().strftime('%Y%m%d')
    today_df = _pd.DataFrame()

    try:
        with _ak_eastmoney_direct():
            today_df = _get_ak().stock_zt_pool_em(date=today)
    except Exception as exc:
        logger.warning('[Jia] 今日涨停池获取失败: %s', exc)

    scan_candidates = _collect_latest_scan_candidates()
    scan_map = {_normalize_code6(item.get('code')): item for item in scan_candidates}

    today_sector_counts: Dict[str, int] = {}
    sector_board_rows: Dict[str, List[Dict[str, Any]]] = {}
    leader_height = 0
    board_candidates: List[Dict[str, Any]] = []

    if today_df is not None and not today_df.empty:
        for _, row in today_df.iterrows():
            row_dict = row.to_dict()
            code = _normalize_code6(row_dict.get('代码'))
            if not code:
                continue
            scan_row = scan_map.get(code, {})
            sector = str(row_dict.get('所属行业') or scan_row.get('sector') or '').strip()
            if sector:
                today_sector_counts[sector] = today_sector_counts.get(sector, 0) + 1
            consecutive_days = _safe_int_num(row_dict.get('连板数') or 1)
            leader_height = max(leader_height, consecutive_days)
            item = {
                'code': code,
                'name': str(row_dict.get('名称') or scan_row.get('name') or code),
                'sector': sector,
                'price': round(_safe_float_num(row_dict.get('最新价')), 2),
                'changePct': round(_safe_float_num(row_dict.get('涨跌幅')), 2),
                'score': int(scan_row.get('total_score') or scan_row.get('score') or min(99, 66 + consecutive_days * 5 + today_sector_counts.get(sector, 0) * 2)),
                'grade': str(scan_row.get('grade') or ('S' if consecutive_days >= 3 else 'A' if consecutive_days >= 2 else 'B')),
                'consecutiveDays': consecutive_days,
                'firstSealTime': _format_clock_hhmm(row_dict.get('首次封板时间')),
                'firstSealInt': _clock_to_int(row_dict.get('首次封板时间')),
                'lastSealTime': _format_clock_hhmm(row_dict.get('最后封板时间') or row_dict.get('首次封板时间')),
                'lastSealInt': _clock_to_int(row_dict.get('最后封板时间') or row_dict.get('首次封板时间')),
                'brokenBoardCount': _safe_int_num(row_dict.get('炸板次数')),
                'turnoverRate': round(_safe_float_num(row_dict.get('换手率')), 2),
                'sealAmountYi': _to_yi(row_dict.get('封板资金')),
                'marketCapYi': _to_yi(row_dict.get('流通市值')),
                'volumeRatio': round(_safe_float_num(scan_row.get('volume_ratio') if scan_row.get('volume_ratio') is not None else scan_row.get('volumeRatio')), 2),
            }
            board_candidates.append(item)
            sector_board_rows.setdefault(sector, []).append(item)

    scan_sector_counts: Dict[str, int] = {}
    scan_sector_scores: Dict[str, float] = {}
    scan_sector_members: Dict[str, List[Dict[str, Any]]] = {}
    scan_sector_rank_map: Dict[str, int] = {}
    for scan_row in scan_candidates:
        sector = str(scan_row.get('sector') or scan_row.get('sector_name') or '').strip()
        code = _normalize_code6(scan_row.get('code'))
        if not sector or not code:
            continue
        scan_sector_counts[sector] = scan_sector_counts.get(sector, 0) + 1
        scan_sector_scores[sector] = scan_sector_scores.get(sector, 0.0) + _safe_float_num(scan_row.get('total_score') or scan_row.get('score'))
        scan_sector_members.setdefault(sector, []).append(scan_row)

    for sector, members in scan_sector_members.items():
        ranked = sorted(
            members,
            key=lambda one: (
                _normalize_scan_pct_change(one.get('pct_change')),
                _safe_float_num(one.get('total_score') or one.get('score')),
                _safe_float_num(one.get('volume_ratio') if one.get('volume_ratio') is not None else one.get('volumeRatio')),
            ),
            reverse=True,
        )
        for idx, one in enumerate(ranked, 1):
            code = _normalize_code6(one.get('code'))
            if code:
                scan_sector_rank_map[code] = idx

    theme_scores: List[Dict[str, Any]] = []
    for sector in sorted(set(list(today_sector_counts.keys()) + list(scan_sector_counts.keys()))):
        score = today_sector_counts.get(sector, 0) * 3 + scan_sector_counts.get(sector, 0)
        score += min(3.0, scan_sector_scores.get(sector, 0.0) / 180.0)
        theme_scores.append({
            'name': sector,
            'score': round(score, 2),
            'limitUps': today_sector_counts.get(sector, 0),
            'scanCount': scan_sector_counts.get(sector, 0),
        })
    theme_scores.sort(key=lambda item: (item['score'], item['limitUps'], item['scanCount']), reverse=True)

    main_theme = theme_scores[0] if theme_scores else {'name': '待观察', 'score': 0, 'limitUps': 0, 'scanCount': 0}
    backup_theme = theme_scores[1] if len(theme_scores) > 1 else {'name': '待观察', 'score': 0, 'limitUps': 0, 'scanCount': 0}

    emotion_cycle = _build_jia_emotion_cycle(
        overview_text,
        search_data,
        today_count=len(today_df) if today_df is not None else 0,
        leader_height=leader_height,
        main_theme_count=int(main_theme.get('limitUps') or 0),
        board_candidates=board_candidates,
    )
    emotion_stage = str(emotion_cycle.get('stage') or '待观察')
    time_anchor = _build_jia_time_anchor()
    after_hours_like = time_anchor.get('phaseCode') in {'preopen', 'auction', 'tail_caution', 'after_close'}

    def _leader_type_for(sector: str, sector_rank: int, consecutive_days: int) -> Tuple[str, str, str]:
        if sector == main_theme.get('name') and sector_rank == 1 and consecutive_days == leader_height and leader_height >= 2:
            return '总龙头', '主线核心', '主线总龙头'
        if sector == main_theme.get('name') and sector_rank == 1:
            return '板块龙头', '主线核心', '主线板块龙头'
        if sector == main_theme.get('name') and sector_rank <= 2:
            return '次龙头', '主线次强', '主线次龙头'
        if sector == backup_theme.get('name') and sector_rank == 1:
            return '切换候选', '切换候选', '切换候选'
        return '补涨', '跟风补涨', '补涨观察'

    board_by_code: Dict[str, Dict[str, Any]] = {}
    leader_candidates: List[Dict[str, Any]] = []
    leader_priority = {'总龙头': 4, '板块龙头': 3, '次龙头': 2, '切换候选': 1, '补涨': 0}

    for item in board_candidates:
        sector = str(item.get('sector') or '').strip()
        sector_rank = 1
        if sector:
            ranked_rows = sorted(
                sector_board_rows.get(sector, []),
                key=lambda one: (
                    int(one.get('consecutiveDays') or 0),
                    float(one.get('sealAmountYi') or 0),
                    float(one.get('score') or 0),
                ),
                reverse=True,
            )
            for idx, row in enumerate(ranked_rows, 1):
                if row.get('code') == item.get('code'):
                    sector_rank = idx
                    break
        leader_type, theme_role, selection_type = _leader_type_for(
            sector,
            sector_rank,
            int(item.get('consecutiveDays') or 0),
        )
        rebound_info = _jia_rebound_seal_verdict(
            broken_board_count=item.get('brokenBoardCount'),
            last_seal_int=int(item.get('lastSealInt') or 0),
            turnover_rate=item.get('turnoverRate'),
            seal_amount_yi=item.get('sealAmountYi'),
        )
        item.update({
            'sectorRank': sector_rank,
            'leaderType': leader_type,
            'themeRole': theme_role,
            'selectionType': selection_type,
            'emotionStage': emotion_stage,
            'buyPointType': '回封打板' if rebound_info.get('reboundSealVerdict') == '真回封' else '待观察',
            'tradeStatus': '龙头样本',
            'entryPlan': '龙头强度样本',
            'entryTrigger': '仅作主线与龙头结构样本',
            'positionRatio': _jia_position_ratio(
                emotion_stage=emotion_stage,
                leader_type=leader_type,
                buy_point_type='回封打板' if rebound_info.get('reboundSealVerdict') == '真回封' else '待观察',
            ),
            'holdPeriod': '1-2 天游资超短',
            'exitTrigger': '龙头强转弱、放量滞涨、无人接力或情绪退潮',
            'reboundSealVerdict': rebound_info.get('reboundSealVerdict', '待观察'),
            'sealVerdictSummary': rebound_info.get('sealVerdictSummary', '待观察'),
            'emotionFit': f'{emotion_stage}阶段下优先观察其是否继续最抗分歧。',
            'rotationSignal': '若旧龙头继续掉队，需观察次主线是否接棒。',
            'boardType': '回封板' if int(item.get('brokenBoardCount') or 0) > 0 else ('连板' if int(item.get('consecutiveDays') or 0) >= 2 else '首板'),
            'reason': (
                f"{selection_type}｜{leader_type}｜{emotion_stage}阶段下更适合作为龙头结构样本，"
                f"看它是否继续带板块与承接分歧。"
            ),
        })
        item['labels'] = _jia_labels(
            emotion_stage=emotion_stage,
            leader_type=leader_type,
            buy_point_type=item.get('buyPointType', '待观察'),
            rebound_seal_verdict=item.get('reboundSealVerdict', '待观察'),
            theme_role=theme_role,
            trade_status=item.get('tradeStatus', ''),
        )
        item['matchedRules'] = _jia_matched_rules(item)
        board_by_code[item.get('code')] = item
        if leader_priority.get(leader_type, 0) > 0:
            leader_candidates.append(item)

    if not leader_candidates:
        for scan_row in scan_candidates[:5]:
            code = _normalize_code6(scan_row.get('code'))
            sector = str(scan_row.get('sector') or '').strip()
            if not code or not sector:
                continue
            sector_rank = scan_sector_rank_map.get(code, 99)
            leader_type, theme_role, selection_type = _leader_type_for(sector, sector_rank, 1)
            if leader_priority.get(leader_type, 0) <= 0:
                continue
            leader_candidates.append({
                'code': code,
                'name': str(scan_row.get('name') or code),
                'sector': sector,
                'leaderType': leader_type,
                'themeRole': theme_role,
                'selectionType': selection_type,
                'score': int(scan_row.get('total_score') or scan_row.get('score') or 0),
                'consecutiveDays': 1,
                'reboundSealVerdict': '待观察',
                'sealVerdictSummary': '未进入涨停样本，回封结构待观察。',
            })

    leader_candidates.sort(
        key=lambda item: (
            leader_priority.get(str(item.get('leaderType') or ''), 0),
            int(item.get('consecutiveDays') or 0),
            float(item.get('score') or 0),
            float(item.get('sealAmountYi') or 0),
        ),
        reverse=True,
    )
    leader_candidates = leader_candidates[:6]
    main_leader = leader_candidates[0] if leader_candidates else {
        'code': '',
        'name': '待观察',
        'leaderType': '待观察',
        'sector': main_theme.get('name', '待观察'),
    }

    if emotion_stage == '退潮':
        rotation_signal = '旧龙头退潮，等待新周期龙头与赚钱效应重新出现。'
    elif backup_theme.get('name') != '待观察' and _safe_float_num(backup_theme.get('score')) >= _safe_float_num(main_theme.get('score')) * 0.8:
        rotation_signal = f"次主线 {backup_theme.get('name', '待观察')} 正在接近主线强度，需警惕龙头切换。"
    else:
        rotation_signal = '主线暂未出现明确切换，仍围绕当前最强方向。'

    actionable_candidates: List[Dict[str, Any]] = []
    scan_rows = sorted(
        scan_candidates,
        key=lambda one: (
            _safe_float_num(one.get('total_score') or one.get('score')),
            _normalize_scan_pct_change(one.get('pct_change')),
            _safe_float_num(one.get('volume_ratio') if one.get('volume_ratio') is not None else one.get('volumeRatio')),
        ),
        reverse=True,
    )

    for scan_row in scan_rows[:12]:
        code = _normalize_code6(scan_row.get('code'))
        if not code:
            continue
        sector = str(scan_row.get('sector') or scan_row.get('sector_name') or '').strip()
        sector_rank = scan_sector_rank_map.get(code, 99)
        board_item = board_by_code.get(code, {})
        consecutive_days = int(board_item.get('consecutiveDays') or 1)
        leader_type, theme_role, selection_type = _leader_type_for(sector, sector_rank, consecutive_days)
        pct_change = _normalize_scan_pct_change(scan_row.get('pct_change'))
        latest_price = _safe_float_num(scan_row.get('close') or scan_row.get('price'))
        volume_ratio = _safe_float_num(scan_row.get('volume_ratio') if scan_row.get('volume_ratio') is not None else scan_row.get('volumeRatio'))
        score = int(scan_row.get('total_score') or scan_row.get('score') or 0)

        # 养家只盯最强赚钱效应，不在低优先级补涨里浪费大量分时/K线取证时间
        if leader_type == '补涨' and sector_rank > 2 and score < 72 and sector not in {main_theme.get('name'), backup_theme.get('name')}:
            continue

        if after_hours_like:
            strength_snapshot = {
                'ma5': 0.0,
                'ma10': 0.0,
                'ma20': 0.0,
                'nearMa5': False,
                'nearMa10': False,
                'trendBias': '待次日确认',
                'maSupportSummary': '当前时段以次日竞价与强弱确认替代盘中承接位',
                'supportSummary': '收盘后不虚构盘中承接，优先次日竞价确认',
            }
        else:
            strength_snapshot = _jia_fetch_strength_snapshot(code, latest_price)
        rebound_info = {
            'reboundSealVerdict': str(board_item.get('reboundSealVerdict') or '待观察'),
            'sealVerdictSummary': str(board_item.get('sealVerdictSummary') or '暂无回封结构，更多看分歧低吸或反包确认。'),
        }
        if rebound_info['reboundSealVerdict'] == '待观察' and board_item:
            rebound_info = _jia_rebound_seal_verdict(
                broken_board_count=board_item.get('brokenBoardCount'),
                last_seal_int=int(board_item.get('lastSealInt') or 0),
                turnover_rate=board_item.get('turnoverRate'),
                seal_amount_yi=board_item.get('sealAmountYi'),
            )

        if not emotion_cycle.get('tradeable'):
            buy_point_type = '待观察'
        elif rebound_info.get('reboundSealVerdict') == '真回封' and leader_type in {'总龙头', '板块龙头', '次龙头', '切换候选'}:
            buy_point_type = '回封打板'
        elif leader_type in {'总龙头', '板块龙头', '次龙头'} and emotion_stage in {'回暖', '主升', '分歧'} and (
            strength_snapshot.get('nearMa5') or strength_snapshot.get('nearMa10') or -3.0 <= pct_change <= 3.5
        ) and volume_ratio >= 0.9:
            buy_point_type = '分歧低吸'
        elif leader_type in {'总龙头', '板块龙头', '切换候选'} and emotion_stage in {'回暖', '主升'} and pct_change >= 2.0 and volume_ratio >= 1.4:
            buy_point_type = '反包确认'
        else:
            buy_point_type = '待观察'

        emotion_fit = (
            '退潮期不匹配，应优先空仓'
            if emotion_stage == '退潮'
            else '冰点只允许小仓试错'
            if emotion_stage == '冰点'
            else '主升阶段匹配度高'
            if emotion_stage == '主升' and buy_point_type in {'分歧低吸', '回封打板', '反包确认'}
            else '分歧期只做最强者'
            if emotion_stage == '分歧' and buy_point_type in {'分歧低吸', '回封打板'}
            else '回暖阶段可轻仓试错'
            if emotion_stage == '回暖' and buy_point_type != '待观察'
            else '与当前阶段匹配度一般，需继续观察'
        )
        entry_info = _jia_entry_plan(
            buy_point_type,
            phase_code=time_anchor.get('phaseCode', ''),
            emotion_stage=emotion_stage,
            tradeable=bool(emotion_cycle.get('tradeable')),
        )
        position_ratio = _jia_position_ratio(
            emotion_stage=emotion_stage,
            leader_type=leader_type,
            buy_point_type=buy_point_type,
        )
        exit_trigger = '龙头强转弱、放量滞涨、情绪退潮或无人接力时立即撤退'
        labels = _jia_labels(
            emotion_stage=emotion_stage,
            leader_type=leader_type,
            buy_point_type=buy_point_type,
            rebound_seal_verdict=rebound_info.get('reboundSealVerdict', '待观察'),
            theme_role=theme_role,
            trade_status=entry_info.get('tradeStatus', ''),
        )
        actionable_now = (
            entry_info.get('tradeStatus') in {'可交易', '回封关注', '试错仓'}
            and emotion_cycle.get('tradeable')
            and time_anchor.get('phaseCode') not in {'preopen', 'auction', 'tail_caution', 'after_close'}
        )
        reason = (
            f"{selection_type}｜{leader_type}｜当前情绪 {emotion_stage}｜"
            f"{buy_point_type}｜{strength_snapshot.get('supportSummary', '承接待观察')}｜"
            f"{'主线优先' if sector == main_theme.get('name') else '作为切换预备保留'}。"
        )

        item = {
            'code': code,
            'name': str(scan_row.get('name') or code),
            'sector': sector,
            'price': round(latest_price, 2),
            'changePct': round(pct_change, 2),
            'score': score,
            'grade': str(scan_row.get('grade') or ('S' if score >= 82 else 'A' if score >= 74 else 'B')),
            'adviseType': '情绪龙头',
            'leaderType': leader_type,
            'themeRole': theme_role,
            'selectionType': selection_type,
            'emotionStage': emotion_stage,
            'stage': emotion_stage,
            'emotionFit': emotion_fit,
            'tradeStatus': entry_info.get('tradeStatus', '观察'),
            'buyPointType': buy_point_type,
            'entryPlan': entry_info.get('entryPlan', '等待更清晰信号'),
            'entryModel': buy_point_type,
            'entryTrigger': entry_info.get('entryTrigger', '等待触发'),
            'exitTrigger': exit_trigger,
            'positionRatio': position_ratio,
            'holdPeriod': '1-2 天游资超短',
            'buyRange': '围绕龙头承接位、分时均线、回封确认位或反包突破位分批跟随',
            'stopLoss': '龙头掉队、承接失守、回封转假或情绪退潮即撤',
            'nextDaySellPlan': '卖在分歧，不卖在跌停；若龙头强转弱或无人接力，优先先走。',
            'riskLevel': '低' if buy_point_type == '分歧低吸' else '中' if buy_point_type != '待观察' else '高',
            'signal': f'{selection_type}/{buy_point_type}/{entry_info.get("tradeStatus","观察")}',
            'reason': reason,
            'classificationReason': (
                f"{sector or '待观察'}｜{leader_type}｜评分 {score}｜"
                f"量比 {volume_ratio:.2f}｜{strength_snapshot.get('supportSummary', '承接待观察')}"
            ),
            'meta': (
                f"评分 {score}｜量比 {volume_ratio:.2f}｜板块热度 {int(main_theme.get('score') or 0)}｜"
                f"{strength_snapshot.get('supportSummary', '承接待观察')}"
            ),
            'labels': labels,
            'matchedRules': [],
            'reboundSealVerdict': rebound_info.get('reboundSealVerdict', '待观察'),
            'sealVerdictSummary': rebound_info.get('sealVerdictSummary', '待观察'),
            'rotationSignal': rotation_signal,
            'maSupportSummary': strength_snapshot.get('maSupportSummary', ''),
            'supportSummary': strength_snapshot.get('supportSummary', ''),
            'volumeRatio': round(volume_ratio, 2),
            'marketCapYi': _safe_float_num(scan_row.get('market_cap') or scan_row.get('marketCapYi')),
            'timeAnchorPhase': time_anchor.get('phase', ''),
            'timeAnchorWindow': time_anchor.get('window', ''),
            'actionableNow': actionable_now,
        }
        item['matchedRules'] = _jia_matched_rules(item)
        actionable_candidates.append(item)

    actionable_candidates.sort(
        key=lambda item: (
            1 if item.get('actionableNow') else 0,
            1 if item.get('tradeStatus') in {'可交易', '回封关注', '试错仓'} else 0,
            leader_priority.get(str(item.get('leaderType') or ''), 0),
            float(item.get('score') or 0),
            float(item.get('volumeRatio') or 0),
            float(item.get('changePct') or 0),
        ),
        reverse=True,
    )

    recommended = [item for item in actionable_candidates if item.get('tradeStatus') not in {'观察', '空仓'}][:3]
    if not recommended:
        recommended = actionable_candidates[:3]

    buy_point_counts: Dict[str, int] = {}
    leader_type_counts: Dict[str, int] = {}
    seal_counts: Dict[str, int] = {}
    label_counts: Dict[str, int] = {}
    for item in actionable_candidates:
        buy_point = str(item.get('buyPointType') or '').strip()
        leader_type = str(item.get('leaderType') or '').strip()
        seal_verdict = str(item.get('reboundSealVerdict') or '').strip()
        if buy_point:
            buy_point_counts[buy_point] = buy_point_counts.get(buy_point, 0) + 1
        if leader_type:
            leader_type_counts[leader_type] = leader_type_counts.get(leader_type, 0) + 1
        if seal_verdict:
            seal_counts[seal_verdict] = seal_counts.get(seal_verdict, 0) + 1
        for label in item.get('labels') or []:
            text = str(label or '').strip()
            if text:
                label_counts[text] = label_counts.get(text, 0) + 1

    buy_point_playbook = [
        {'type': '分歧低吸', 'count': buy_point_counts.get('分歧低吸', 0), 'description': '龙头未死、有承接，才配低吸。'},
        {'type': '回封打板', 'count': buy_point_counts.get('回封打板', 0), 'description': '只做回封快、放量、封单稳定的真回封。'},
        {'type': '反包确认', 'count': buy_point_counts.get('反包确认', 0), 'description': '分歧后重新走强，确认龙头地位未丢。'},
    ]
    leader_structure = [
        {'type': '总龙头', 'count': leader_type_counts.get('总龙头', 0), 'description': '市场总辨识度最高，最能聚拢赚钱效应。'},
        {'type': '板块龙头', 'count': leader_type_counts.get('板块龙头', 0), 'description': '主流题材中最先走出来的核心票。'},
        {'type': '次龙头', 'count': leader_type_counts.get('次龙头', 0), 'description': '主线中的次强者，只在龙头未死时观察。'},
        {'type': '切换候选', 'count': leader_type_counts.get('切换候选', 0), 'description': '当旧龙头走弱时，次主线中的候选承接者。'},
    ]
    seal_verdict_hits = [
        {'type': '真回封', 'count': seal_counts.get('真回封', 0), 'description': '回封快、放量、封单稳定增加。'},
        {'type': '假回封', 'count': seal_counts.get('假回封', 0), 'description': '回封慢、封单不稳、反复炸板。'},
        {'type': '待观察', 'count': seal_counts.get('待观察', 0), 'description': '回封真假暂时看不清，宁可等。'},
    ]
    position_rules = [
        {'stage': '冰点', 'range': '0-20%', 'active': emotion_stage == '冰点'},
        {'stage': '回暖', 'range': '30-50%', 'active': emotion_stage == '回暖'},
        {'stage': '主升', 'range': '70-100%', 'active': emotion_stage == '主升'},
        {'stage': '分歧', 'range': '30-50%', 'active': emotion_stage == '分歧'},
        {'stage': '退潮', 'range': '0%', 'active': emotion_stage == '退潮'},
    ]
    label_hits = [
        {'label': label, 'count': count}
        for label, count in sorted(label_counts.items(), key=lambda one: (one[1], one[0]), reverse=True)[:12]
    ]
    daily_rule_hits = [
        {'title': '情绪优先', 'status': emotion_stage, 'detail': emotion_cycle.get('summary', '')},
        {'title': '主流题材', 'status': main_theme.get('name', '待观察'), 'detail': f"次主线看 {backup_theme.get('name', '待观察')}，只围绕赚钱效应最强方向。"},
        {'title': '只做龙头', 'status': f"{main_leader.get('name', '待观察')}({main_leader.get('code', '')})", 'detail': f"{main_leader.get('leaderType', '待观察')}｜最抗分歧者优先。"},
        {'title': '分歧低吸', 'status': f"{buy_point_counts.get('分歧低吸', 0)}只命中", 'detail': '龙头未死且有承接，才是低吸。'},
        {'title': '回封打板', 'status': f"{buy_point_counts.get('回封打板', 0)}只命中", 'detail': '只允许参与真回封，不做假回封。'},
        {'title': '反包确认', 'status': f"{buy_point_counts.get('反包确认', 0)}只命中", 'detail': '分歧后重新走强，才配确认。'},
        {'title': '龙头切换', 'status': backup_theme.get('name', '待观察'), 'detail': rotation_signal},
        {'title': '卖在分歧', 'status': '纪律常驻', 'detail': '强转弱、放量滞涨、无人接力或情绪退潮时先走。'},
    ]

    main_flow = {
        'mainTheme': main_theme.get('name', '待观察'),
        'backupTheme': backup_theme.get('name', '待观察'),
        'leader': main_leader.get('name', '待观察'),
        'leaderCode': main_leader.get('code', ''),
        'summary': (
            f"{main_theme.get('name', '待观察')} 当前更像主流赚钱效应集中地，"
            f"龙头看 {main_leader.get('name', '待观察')}，次主线观察 {backup_theme.get('name', '待观察')}。"
        ),
        'reasons': [
            f"主线强度：涨停 {int(main_theme.get('limitUps') or 0)} 只，扫描命中 {int(main_theme.get('scanCount') or 0)} 只",
            f"次主线：{backup_theme.get('name', '待观察')}",
            f"空间板：{leader_height} 连板",
        ],
    }
    rotation_panel = {
        'status': '切换预警' if '切换' in rotation_signal or '接近主线' in rotation_signal else '主线延续',
        'summary': rotation_signal,
        'oldLeader': f"{main_leader.get('name', '待观察')}({main_leader.get('code', '')})",
        'newLeader': backup_theme.get('name', '待观察'),
    }

    step_outputs = [
        {
            'step': 1,
            'title': '识别情绪阶段',
            'summary': f"当前更偏 {emotion_stage}，执行状态 {emotion_cycle.get('status', '待观察')}。",
            'frameworkLines': [
                '市场情绪优先于技术指标，不先定情绪就不谈买卖。',
                '冰点/回暖/主升/分歧/退潮决定仓位与出手频率。',
                '退潮不重仓，主升才允许重点进攻。',
            ],
            'lines': list(emotion_cycle.get('reasons') or [])[:3],
        },
        {
            'step': 2,
            'title': '锁定主流题材',
            'summary': f"当前主流题材更偏 {main_theme.get('name', '待观察')}，次主线看 {backup_theme.get('name', '待观察')}。",
            'frameworkLines': [
                '哪里赚钱效应最强，就去哪里。',
                '主流题材优先于冷门题材，赚钱效应比题材名字更重要。',
                '主线不清晰时，宁可等待也不硬找机会。',
            ],
            'lines': list(main_flow.get('reasons') or [])[:2] + [main_flow.get('summary', '')],
        },
        {
            'step': 3,
            'title': '识别龙头结构',
            'summary': f"当前龙头看 {main_leader.get('name', '待观察')}，只做龙头与切换候选。",
            'frameworkLines': [
                '龙头要么高度最高，要么最抗分歧，要么最能带板块。',
                '只做总龙头、板块龙头、次龙头与切换候选，不做杂毛。',
                '多个候选并存时，优先最抗分歧的那个。',
            ],
            'lines': [
                f"{item.get('name','')}({item.get('code','')})｜{item.get('leaderType','待观察')}｜{item.get('selectionType','待观察')}｜{item.get('sector','待观察')}"
                for item in leader_candidates[:4]
            ] or ['暂无清晰龙头结构，优先继续观察。'],
        },
        {
            'step': 4,
            'title': '匹配买点模型',
            'summary': f"当前只在三类模型里出手，可交易候选 {len(actionable_candidates)} 只。",
            'frameworkLines': [
                '买点只允许分歧低吸、回封打板、反包确认。',
                '真回封才配参与，假回封原则上回避。',
                '不满足三类模型，禁止出手。',
            ],
            'lines': [
                f"{item.get('name','')}({item.get('code','')})｜{item.get('buyPointType','待观察')}｜{item.get('tradeStatus','观察')}｜{item.get('sealVerdictSummary','待观察')}"
                for item in actionable_candidates[:4]
            ] or ['当前没有满足模式的龙头候选，继续等待。'],
        },
        {
            'step': 5,
            'title': '制定卖点与切换',
            'summary': '龙头强转弱就走，出现新龙头就切换，卖在分歧不卖在跌停。',
            'frameworkLines': [
                '卖点必须比买点更机械。',
                '强转弱、放量滞涨、无人接力、情绪退潮都应优先撤退。',
                '旧龙头走弱时，要同步评估新题材与新龙头的接力结构。',
            ],
            'lines': [
                rotation_signal,
                *[
                    f"{item.get('name','')}({item.get('code','')})｜{item.get('exitTrigger','待观察')}"
                    for item in recommended[:2]
                ],
            ],
        },
    ]

    market_commentary = (
        f"当前情绪 {emotion_stage}，主流题材偏 {main_theme.get('name','待观察')}，龙头看 {main_leader.get('name','待观察')}。"
        if main_theme.get('name') and main_theme.get('name') != '待观察'
        else f"当前情绪 {emotion_stage}，主线仍待进一步确认。"
    )
    position_advice = f"{emotion_cycle.get('status','待观察')}｜总仓建议 {emotion_cycle.get('positionCap','待观察')}"
    risk_warning = '退潮期硬做、假回封误判、补涨当龙头和无人接力，是回撤的主要来源。'

    return {
        'kind': 'jia',
        'version': 'v1',
        'generatedAt': datetime.now().isoformat(),
        'stats': {
            'todayLimitUps': len(today_df) if today_df is not None else 0,
            'leaderCount': len(leader_candidates),
            'actionableCount': len(actionable_candidates),
            'trueSealCount': seal_counts.get('真回封', 0),
            'rotationWatchCount': leader_type_counts.get('切换候选', 0),
            'marketGateStatus': emotion_cycle.get('status'),
        },
        'emotionCycle': emotion_cycle,
        'timeAnchor': time_anchor,
        'mainTheme': {
            'name': main_theme.get('name', '待观察'),
            'stage': emotion_stage,
            'strength': '强' if emotion_stage == '主升' else '中' if emotion_stage in {'回暖', '分歧'} else '弱',
        },
        'backupTheme': {
            'name': backup_theme.get('name', '待观察'),
            'reason': rotation_signal,
        },
        'mainLeader': {
            'code': main_leader.get('code', ''),
            'name': main_leader.get('name', '待观察'),
            'leaderType': main_leader.get('leaderType', '待观察'),
        },
        'tradeable': bool(emotion_cycle.get('tradeable') and recommended),
        'action': '买' if emotion_cycle.get('tradeable') and recommended else '空仓',
        'buyPointType': recommended[0].get('buyPointType', '待观察') if recommended else '待观察',
        'rotationSignal': rotation_signal,
        'strategyPanels': {
            'timeAnchor': time_anchor,
            'emotionStage': emotion_cycle,
            'mainFlow': main_flow,
            'leaderStructure': leader_structure,
            'buyPointPlaybook': buy_point_playbook,
            'sealVerdictHits': seal_verdict_hits,
            'positionRules': position_rules,
            'rotationSignal': rotation_panel,
            'labelHits': label_hits,
            'dailyRuleHits': daily_rule_hits,
        },
        'leaderCandidates': leader_candidates,
        'actionableCandidates': actionable_candidates[:8],
        'recommendedStocks': recommended,
        'stepOutputs': step_outputs,
        'marketCommentary': market_commentary,
        'positionAdvice': position_advice,
        'riskWarning': risk_warning,
        'searchDataPreview': (search_data or '')[:1200],
    }


def _build_jia_execution_context_text(artifacts: Dict[str, Any]) -> str:
    if not artifacts:
        return '【暂无炒股养家执行工件】'

    stats = artifacts.get('stats', {})
    emotion_cycle = artifacts.get('emotionCycle', {})
    time_anchor = artifacts.get('timeAnchor', {})
    main_theme = artifacts.get('mainTheme', {})
    backup_theme = artifacts.get('backupTheme', {})
    main_leader = artifacts.get('mainLeader', {})
    lines = [
        '## 炒股养家执行工件（系统预处理）',
        f"- 时间锚点：{time_anchor.get('phase', '待观察')}｜{time_anchor.get('window', '等待更多信号')}",
        f"- 当前情绪：{emotion_cycle.get('stage', '待观察')}｜{emotion_cycle.get('action', '等待更多确认')}",
        f"- 主流题材：{main_theme.get('name', '待观察')}",
        f"- 次主线：{backup_theme.get('name', '待观察')}",
        f"- 当前龙头：{main_leader.get('name', '待观察')}({main_leader.get('code', '')})｜{main_leader.get('leaderType', '待观察')}",
        f"- 龙头样本：{stats.get('leaderCount', 0)} 只",
        f"- 可交易候选：{stats.get('actionableCount', 0)} 只",
        f"- 真回封样本：{stats.get('trueSealCount', 0)} 只",
        '',
        '### 炒股养家当前偏好的可交易候选',
    ]
    for item in artifacts.get('actionableCandidates', [])[:6]:
        lines.append(
            f"- {item.get('name','')}({item.get('code','')})｜{item.get('selectionType','待观察')}｜"
            f"{item.get('buyPointType','待观察')}｜{item.get('tradeStatus','观察')}｜"
            f"{item.get('reboundSealVerdict','待观察')}｜{' / '.join((item.get('labels') or [])[:3])}"
        )
    if not artifacts.get('actionableCandidates'):
        for item in artifacts.get('leaderCandidates', [])[:4]:
            lines.append(
                f"- {item.get('name','')}({item.get('code','')})｜{item.get('leaderType','待观察')}｜"
                f"{item.get('selectionType','待观察')}｜{item.get('reboundSealVerdict','待观察')}"
            )
    return '\n'.join(lines)


def _build_jia_fallback_structured(artifacts: Dict[str, Any]) -> Dict[str, Any]:
    recommended = list(artifacts.get('recommendedStocks') or [])
    return {
        'agentId': 'jia',
        'agentName': '炒股养家',
        'stance': 'bull' if recommended and artifacts.get('tradeable') else 'neutral',
        'confidence': 80 if recommended and artifacts.get('tradeable') else 56,
        'marketCommentary': artifacts.get('marketCommentary', ''),
        'positionAdvice': artifacts.get('positionAdvice', ''),
        'riskWarning': artifacts.get('riskWarning', ''),
        'emotionStage': artifacts.get('emotionCycle', {}).get('stage', ''),
        'mainTheme': artifacts.get('mainTheme', {}),
        'mainLeader': artifacts.get('mainLeader', {}),
        'tradeable': artifacts.get('tradeable', False),
        'action': artifacts.get('action', '空仓'),
        'buyPointType': artifacts.get('buyPointType', '待观察'),
        'rotationSignal': artifacts.get('rotationSignal', ''),
        'recommendedStocks': recommended,
    }


def _merge_jia_structured(structured: Dict[str, Any], artifacts: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(structured or {})
    recommended = list(merged.get('recommendedStocks') or [])
    candidate_sources = (
        list(artifacts.get('recommendedStocks') or [])
        + list(artifacts.get('actionableCandidates') or [])
        + list(artifacts.get('leaderCandidates') or [])
    )
    candidates_by_code = {
        _normalize_code6(item.get('code')): item
        for item in candidate_sources
        if _normalize_code6(item.get('code'))
    }

    merged_recs = []
    for item in recommended:
        code = _normalize_code6(item.get('code'))
        candidate = candidates_by_code.get(code, {})
        one = dict(candidate) if candidate else {}
        one.update(item)
        for key, value in candidate.items():
            one.setdefault(key, value)
        if code:
            one['code'] = code
        merged_recs.append(one)

    artifact_recommended = list(artifacts.get('recommendedStocks') or [])
    merged['recommendedStocks'] = artifact_recommended[:3] if artifact_recommended else merged_recs[:3]
    merged['emotionStage'] = merged.get('emotionStage') or artifacts.get('emotionCycle', {}).get('stage', '')
    merged['mainTheme'] = merged.get('mainTheme') or artifacts.get('mainTheme', {})
    merged['mainLeader'] = merged.get('mainLeader') or artifacts.get('mainLeader', {})
    merged['tradeable'] = merged.get('tradeable') if 'tradeable' in merged else artifacts.get('tradeable', False)
    merged['action'] = merged.get('action') or artifacts.get('action', '空仓')
    merged['buyPointType'] = merged.get('buyPointType') or artifacts.get('buyPointType', '待观察')
    merged['rotationSignal'] = merged.get('rotationSignal') or artifacts.get('rotationSignal', '')
    merged['personaExecution'] = {
        'kind': 'jia',
        'version': artifacts.get('version', 'v1'),
        'coreObjective': '围绕情绪周期、主流题材与最强龙头，只在分歧低吸、回封打板、反包确认三类模型里出手',
        'stats': artifacts.get('stats', {}),
        'emotionCycle': artifacts.get('emotionCycle', {}),
        'timeAnchor': artifacts.get('timeAnchor', {}),
        'mainTheme': artifacts.get('mainTheme', {}),
        'backupTheme': artifacts.get('backupTheme', {}),
        'mainLeader': artifacts.get('mainLeader', {}),
        'tradeable': artifacts.get('tradeable', False),
        'action': artifacts.get('action', '空仓'),
        'buyPointType': artifacts.get('buyPointType', '待观察'),
        'rotationSignal': artifacts.get('rotationSignal', ''),
        'strategyPanels': artifacts.get('strategyPanels', {}),
        'leaderCandidates': artifacts.get('leaderCandidates', []),
        'actionableCandidates': artifacts.get('actionableCandidates', []),
        'stepOutputs': artifacts.get('stepOutputs', []),
    }

    if not str(merged.get('marketCommentary') or '').strip():
        merged['marketCommentary'] = artifacts.get('marketCommentary', '')
    if not str(merged.get('positionAdvice') or '').strip():
        merged['positionAdvice'] = artifacts.get('positionAdvice', '')
    if not str(merged.get('riskWarning') or '').strip():
        merged['riskWarning'] = artifacts.get('riskWarning', '')

    return merged


def _build_jia_markdown_summary(structured: Dict[str, Any], artifacts: Dict[str, Any]) -> str:
    emotion_cycle = artifacts.get('emotionCycle', {})
    time_anchor = artifacts.get('timeAnchor', {})
    main_theme = artifacts.get('mainTheme', {})
    main_leader = artifacts.get('mainLeader', {})
    lines = [
        f"【时间锚点】{time_anchor.get('phase','待观察')}｜{time_anchor.get('window','等待更多信号')}",
        f"【情绪阶段】{emotion_cycle.get('stage','待观察')}｜{emotion_cycle.get('action','等待更多信号')}",
        f"【主流题材】{main_theme.get('name','待观察')}｜龙头 {main_leader.get('name','待观察')}({main_leader.get('code','')})",
        f"【市场解读】{structured.get('marketCommentary') or artifacts.get('marketCommentary') or '赚钱效应仍待进一步确认'}",
        f"【仓位建议】{structured.get('positionAdvice') or artifacts.get('positionAdvice') or '按情绪阶段动态调整仓位'}",
        f"【风险提示】{structured.get('riskWarning') or artifacts.get('riskWarning') or '退潮硬做和假回封最伤'}",
    ]
    recs = (structured.get('recommendedStocks') or [])[:3]
    if recs:
        lines.append('【重点候选】')
        for item in recs:
            lines.append(
                f"- {item.get('name','')}({item.get('code','')})｜{item.get('selectionType','待观察')}｜"
                f"{item.get('buyPointType') or item.get('entryPlan','待观察')}｜{item.get('tradeStatus','观察')}｜"
                f"{item.get('reboundSealVerdict','待观察')}｜{item.get('reason') or item.get('meta') or ''}"
            )
    return '\n'.join(lines)


def _hierarchical_batch_analyze_response():
    """
    蓝图侧的层次化批量分析入口。

    目的不是替代 app.py 中更重的兼容逻辑，而是保证当前 /api/agents/batch
    即便命中了蓝图，也能真正走主控 -> 人格 -> 聚合这条架构链路。
    """
    from ai_service import fetch_market_news
    from junge_trader import format_holdings_for_prompt, format_scan_data_for_prompt
    from utils.llm import AgentOrchestrator

    latest_scan = db.get_latest_scan()
    if not latest_scan:
        return jsonify({'success': False, 'error': '没有可分析的扫描数据'}), 404

    results_dict = latest_scan.get('results', {}) or {}
    all_stocks = []
    for sector_name, sector_data in results_dict.items():
        if not isinstance(sector_data, dict):
            continue
        for stock in sector_data.get('stocks', []) or []:
            if not isinstance(stock, dict):
                continue
            one = dict(stock)
            one['sector'] = sector_name
            all_stocks.append(one)

    if not all_stocks:
        return jsonify({'success': False, 'error': '扫描结果为空'}), 422

    scan_time = latest_scan.get('scan_time', '')
    scan_date = scan_time[:10] if scan_time else datetime.now().strftime('%Y-%m-%d')
    current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')

    try:
        scan_data_text = format_scan_data_for_prompt(all_stocks)
    except Exception:
        scan_data_text = ''

    try:
        news_text = _format_news_for_batch(fetch_market_news(scan_date))
    except Exception:
        news_text = '【暂无最新消息】'

    try:
        holdings_text = format_holdings_for_prompt(db.get_all_holdings())
    except Exception:
        holdings_text = '【暂无历史持仓数据】'

    registry = get_agent_registry()
    client = get_client()
    orchestrator = AgentOrchestrator(client, registry)
    options = CallOptions(temperature=0.2, max_tokens=2400)
    result = orchestrator.analyze_hierarchical(
        scan_data=scan_data_text,
        news_data=news_text,
        holdings_data=holdings_text,
        current_time=current_time,
        scan_date=scan_date,
        options=options,
    )

    agent_results = []
    for agent_id, task_result in result.agent_results.items():
        agent_config = registry.get(agent_id) or {}
        if isinstance(task_result, dict):
            task_success = bool(task_result.get('success'))
            task_status = str(task_result.get('status', 'completed' if task_success else 'failed'))
            task_error = task_result.get('error', '')
            task_raw_response = task_result.get('analysis', '')
            task_thinking = task_result.get('thinking', '')
            task_tokens = task_result.get('tokens_used', 0)
            task_execution_time = task_result.get('execution_time_ms', 0)
            task_retry_count = task_result.get('retry_count', 0)
            structured = task_result.get('structured')
        else:
            task_success = bool(getattr(task_result, 'success', False))
            task_status_obj = getattr(task_result, 'status', '')
            task_status = getattr(task_status_obj, 'value', task_status_obj) or ('completed' if task_success else 'failed')
            task_error = getattr(task_result, 'error', '')
            task_raw_response = getattr(task_result, 'raw_response', '')
            task_thinking = getattr(task_result, 'thinking', '')
            task_tokens = getattr(task_result, 'tokens_used', 0)
            task_execution_time = getattr(task_result, 'execution_time_ms', 0)
            task_retry_count = getattr(task_result, 'retry_count', 0)
            structured = getattr(task_result, 'result', None)

        structured = structured or {
            'agentId': agent_id,
            'agentName': agent_config.get('name', agent_id),
            'stance': 'neutral',
            'confidence': 50,
            'marketCommentary': task_error or '分析未完成',
            'positionAdvice': '当前结果不足以给出仓位建议',
            'riskWarning': '请结合共享事实层补充验证',
            'recommendedStocks': [],
        }
        structured = registry.sanitize(
            structured,
            all_stocks,
            default_advise_type=agent_config.get('adviseType', '波段') if agent_config else '波段',
        )
        _enrich_stocks_realtime(structured)

        agent_results.append({
            'agent_id': agent_id,
            'agent_name': agent_config.get('name', agent_id),
            'success': task_success,
            'status': task_status,
            'structured': structured,
            'analysis': task_raw_response,
            'thinking': task_thinking,
            'tokens_used': task_tokens,
            'execution_time_ms': task_execution_time,
            'retry_count': task_retry_count,
        })

    return jsonify({
        'success': True,
        'scan_time': scan_time or datetime.now().isoformat(),
        'mode': 'hierarchical',
        'master': {
            'marketCoreIntent': result.master.market_core_intent if result.master else '',
            'marketPhase': result.master.market_phase if result.master else '',
            'riskAppetite': result.master.risk_appetite if result.master else '',
            'agentPriority': result.master.agent_priority if result.master else [],
            'keyTheme': result.master.key_theme if result.master else '',
            'riskFactors': result.master.risk_factors if result.master else [],
            'coordinationNotes': result.master.coordination_notes if result.master else '',
        } if result.master else None,
        'consensus': result.consensus,
        'agentResults': agent_results,
        'consensusOpportunities': result.top_opportunities,
        'synthesis': result.synthesis,
        'execution_log': result.execution_log,
        'task_decomposition': result.task_decomposition,
        'lastUpdated': current_time,
    })


@strategy_bp.route('/api/agents/batch', methods=['POST'])
def batch_analyze_agents():
    """
    批量分析智能体。
    - parallel: 并行批量
    - hierarchical: 主控 -> 人格 -> 聚合
    """
    data = request.get_json(silent=True) or {}
    mode = str(data.get('mode', 'parallel') or 'parallel').strip().lower()

    if mode == 'hierarchical':
        return _hierarchical_batch_analyze_response()

    registry = get_agent_registry()
    agent_ids = [a['id'] for a in registry.list_agents()]

    # 并行执行所有 Agent
    from concurrent.futures import ProcessPoolExecutor, as_completed
    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(analyze_single_agent, aid): aid for aid in agent_ids}
        for future in as_completed(futures, timeout=120):
            try:
                r = future.result()
                results.append(r)
            except Exception as e:
                aid = futures[future]
                results.append({'agent_id': aid, 'success': False, 'error': str(e)})

    # 保证顺序与 agent_ids 一致
    results.sort(key=lambda r: agent_ids.index(r['agent_id']))

    # 计算共识
    stances = [r.get('structured', {}).get('stance', 'neutral') for r in results if r.get('success')]
    confidences = [r.get('structured', {}).get('confidence', 50) for r in results if r.get('success')]
    bull_count = sum(1 for s in stances if s == 'bull')
    bear_count = sum(1 for s in stances if s == 'bear')
    neutral_count = sum(1 for s in stances if s == 'neutral')
    total = len(stances) or 1
    avg_conf = sum(confidences) / len(confidences) if confidences else 50

    # 共识百分比：bull→高分，bear→低分
    consensus_pct = max(10, min(95, int(50 + (bull_count - bear_count) / total * 50 + avg_conf / 4)))

    # 共识标签
    if bull_count >= 4:
        consensus_label = '乐观看多'
    elif bear_count >= 3:
        consensus_label = '谨慎防御'
    elif neutral_count >= 4:
        consensus_label = '中性观望'
    else:
        consensus_label = '分化震荡'

    # 聚合 TOP 机会（从各 Agent 推荐中取涨幅最大的前 3）
    all_recs = []
    for r in results:
        if r.get('success'):
            for s in r.get('structured', {}).get('recommendedStocks', []):
                chg = s.get('chg_pct')
                if chg is None:
                    chg = s.get('changePct') or s.get('change_pct') or 0
                all_recs.append({
                    'name': s.get('name', ''),
                    'code': s.get('code', ''),
                    'role': s.get('role') or s.get('adviseType') or s.get('grade') or '',
                    'reason': s.get('reason') or s.get('signal') or s.get('meta') or '',
                    'chg_pct': float(chg or 0),
                    'agent': r.get('agent_name', ''),
                })
    all_recs.sort(key=lambda x: x['chg_pct'], reverse=True)
    top_recs = all_recs[:3]

    # 构建共识机会列表
    badges = ['龙头共识', '多策略共振', '资金认可']
    badge_kinds = ['primary', 'primary', 'muted']
    consensus_opportunities = []
    for i, rec in enumerate(top_recs):
        sentiment_tag = '看多' if rec['chg_pct'] > 5 else '轮动'
        consensus_opportunities.append({
            'rank': i + 1,
            'title': f"{rec['name']} ({rec['code']})",
            'badge': badges[i] if i < len(badges) else '机会标的',
            'badgeKind': badge_kinds[i] if i < len(badge_kinds) else 'muted',
            'meta': f"{rec['role']} · {rec['reason'][:20]}" if rec['reason'] else rec['role'],
            'chg': rec['chg_pct'],
            'flowLabel': f"来源: {rec['agent']}",
        })

    return jsonify({
        'success': True,
        'scan_time': datetime.now().isoformat(),
        'mode': 'parallel',
        'consensus': {
            'consensusPct': consensus_pct,
            'bullCount': bull_count,
            'bearCount': bear_count,
            'neutralCount': neutral_count,
            'label': consensus_label,
            'avgConfidence': round(avg_conf, 1),
        },
        'agentResults': results,
        'consensusOpportunities': consensus_opportunities,
        'lastUpdated': datetime.now().strftime('%H:%M:%S'),
    })


# ══════════════════════════════════════════════════════════════════════════════
# JunGeTrader API - 钧哥智能交易员
# 使用 register_junge_routes 模式，避免循环导入
# ══════════════════════════════════════════════════════════════════════════════
try:
    from junge_trader import register_junge_routes
    register_junge_routes(strategy_bp, get, set, invalidate, db)
    logger.info("JunGeTrader 路由注册成功")
except ImportError as e:
    logger.warning(f"JunGeTrader 路由注册失败: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# 量化回测 API
# ══════════════════════════════════════════════════════════════════════════════

@strategy_bp.route('/api/backtest/catalog', methods=['GET'])
def backtest_catalog():
    """返回内置策略模板列表（含参数定义），前端据此渲染配置表单。"""
    from utils.backtest_engine import TEMPLATE_CATALOG
    return jsonify({'success': True, 'data': TEMPLATE_CATALOG})


@strategy_bp.route('/api/backtest/run', methods=['POST'])
def backtest_run():
    """
    执行量化回测。

    请求体：
    {
        "stock_code": "600519",
        "template_id": "ma_cross",
        "params": {"fast_ma": 5, "slow_ma": 20},
        "start_date": "2025-01-01",   // 可选，默认近 days 天
        "end_date": "2026-04-01",     // 可选，默认今天
        "days": 120,                  // 可选，默认 120
        "initial_cash": 100000.0,    // 可选，默认 10 万
        "commission_pct": 0.001      // 可选，默认千 1
    }

    返回：回测结果（含 K 线 + 买卖点 + 权益曲线 + 统计指标）
    """
    try:
        data = request.get_json() or {}
    except Exception:
        return jsonify({'success': False, 'error': '请求体必须是 JSON'}), 400

    code = (data.get('stock_code') or '').strip()
    if not code or len(code) != 6 or not code.isdigit():
        return jsonify({'success': False, 'error': '无效的 stock_code（需 6 位数字）'}), 400

    template_id = (data.get('template_id') or '').strip()
    if not template_id:
        return jsonify({'success': False, 'error': '缺少 template_id'}), 400

    params = data.get('params') or {}
    days = int(data.get('days', 120))
    initial_cash = float(data.get('initial_cash', 100000.0))
    commission_pct = float(data.get('commission_pct', 0.001))

    start_date = data.get('start_date')
    end_date = data.get('end_date')

    try:
        from utils.backtest_engine import execute_backtest, TEMPLATE_CATALOG
        valid_ids = {t['id'] for t in TEMPLATE_CATALOG}
        if template_id not in valid_ids:
            return jsonify({'success': False, 'error': f'未知策略模板: {template_id}'}), 400

        result = execute_backtest(
            stock_code=code,
            template_id=template_id,
            params=params,
            start_date=start_date,
            end_date=end_date,
            days=min(days, 800),       # 上限 800 天（约 3 年）
            initial_cash=initial_cash,
            commission_pct=commission_pct,
        )
        if not result.get('success'):
            return jsonify({'success': False, 'error': result.get('error', '回测失败')}), 422

        # 安全序列化（过滤 NaN/Inf）
        def _safe_json(obj):
            return json.loads(
                json.dumps(obj, ensure_ascii=False, default=lambda v: (
                    None if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else v
                ))
            )

        return jsonify({'success': True, 'data': _safe_json(result)})
    except Exception as e:
        logger.exception('backtest_run failed')
        return jsonify({'success': False, 'error': f'回测异常: {e}'}), 500


# ══════════════════════════════════════════════════════════════════════════════
# 新架构：Qwen + AKShare + DeepSeek 流式分析接口
# ══════════════════════════════════════════════════════════════════════════════


@strategy_bp.route('/api/analyze/stream', methods=['POST'])
def analyze_stream():
    """
    新架构流式分析接口 v2 - 结合现有 Agent Prompt 工程

    架构：
        IntentClassifier → 选择合适的 Agent
        DataProvider → Qwen + AKShare 获取数据
        Agent Prompt → 使用现有的专业 Prompt
        DeepSeek/Agent → 生成分析报告
    """
    from flask import Response
    import asyncio

    # 在请求上下文中解析数据
    req_data = request.get_json() or {}
    user_input = req_data.get('user_input', '')
    stock_codes = req_data.get('stock_codes', [])
    preferred_agents = req_data.get('preferred_agents', [])
    context = req_data.get('context', {})

    if not user_input:
        return jsonify({'success': False, 'error': '缺少 user_input'}), 400

    def generate():
        try:
            yield "data: {\"type\": \"status\", \"message\": \"开始分析...\"}\n\n"

            from utils.llm.deepseek_analyzer import AnalysisRequest, get_deepseek_analyzer

            analysis_request = AnalysisRequest(
                user_input=user_input,
                stock_codes=stock_codes,
                preferred_agents=preferred_agents,
                context=context
            )

            analyzer = get_deepseek_analyzer()
            result = analyzer.analyze_sync(analysis_request)

            if result.success:
                yield f"data: {{\"type\": \"analysis\", \"content\": {json.dumps(_strip_json_from_analysis(result.content))}}}\n\n"

                if result.thinking:
                    yield f"data: {{\"type\": \"thinking\", \"content\": {json.dumps(result.thinking)}}}\n\n"

                if result.structured:
                    yield f"data: {{\"type\": \"structured\", \"data\": {json.dumps(result.structured)}}}\n\n"

                yield f"data: {{\"type\": \"done\", \"agent_id\": \"{result.agent_id}\", \"agent_name\": \"{result.agent_name}\", \"tokens_used\": {result.tokens_used}, \"time_ms\": {result.execution_time_ms}}}\n\n"
            else:
                yield f"data: {{\"type\": \"error\", \"error\": {json.dumps(result.error)}}}\n\n"

        except Exception as e:
            logger.exception('[Stream] analyze_stream error')
            yield f"data: {{\"type\": \"error\", \"error\": {json.dumps(str(e))}}}\n\n"

        yield "data: {\"type\": \"close\"}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )


@strategy_bp.route('/api/analyze/multi', methods=['POST'])
def analyze_multi_agent():
    """
    多 Agent 协作分析接口

    请求体：
    {
        "user_input": "分析今日AI板块机会",
        "stock_codes": ["000001"],
        "agent_ids": ["beijing", "jun", "qiao"]  // 可选
    }

    返回：
    {
        "success": true,
        "data": {
            "results": [
                {"agent_id": "beijing", "agent_name": "北京炒家", "content": "...", "structured": {}},
                ...
            ]
        }
    }
    """
    import asyncio

    try:
        req_data = request.get_json() or {}
        user_input = req_data.get('user_input', '')
        stock_codes = req_data.get('stock_codes', [])
        agent_ids = req_data.get('agent_ids', [])

        if not user_input:
            return jsonify({'success': False, 'error': '缺少 user_input'}), 400

        from utils.llm.deepseek_analyzer import AnalysisRequest, get_deepseek_analyzer

        request_obj = AnalysisRequest(
            user_input=user_input,
            stock_codes=stock_codes
        )

        analyzer = get_deepseek_analyzer()
        results = asyncio.run(analyzer.multi_agent_analyze(request_obj, agent_ids))

        return jsonify({
            'success': True,
            'data': {
                'results': [r.to_dict() for r in results]
            }
        })

    except Exception as e:
        logger.exception('analyze_multi_agent error')
        return jsonify({'success': False, 'error': str(e)}), 500


@strategy_bp.route('/api/analyze/intent', methods=['POST'])
def analyze_intent():
    """
    意图识别接口（测试用）

    请求体：
    {
        "user_input": "分析今日AI板块机会"
    }

    返回：
    {
        "success": true,
        "data": {
            "intent": "thematic",
            "primary_source": "qwen",
            "required_tools": [...],
            "confidence": 0.8,
            "reasoning": "..."
        }
    }
    """
    try:
        data = request.get_json() or {}
        user_input = data.get('user_input', '')

        if not user_input:
            return jsonify({'success': False, 'error': '缺少 user_input'}), 400

        from utils.llm.intent_classifier import classify_intent

        result = classify_intent(user_input)
        result['intent'] = result['intent'].value  # Enum -> str

        return jsonify({'success': True, 'data': result})

    except Exception as e:
        logger.exception('analyze_intent error')
        return jsonify({'success': False, 'error': str(e)}), 500
