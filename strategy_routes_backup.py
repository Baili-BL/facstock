#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略中心路由模块
"""

import os
from flask import Blueprint, jsonify, request
from typing import Optional
import database as db
import json
import math
import requests
import threading
import time
import random
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import pandas as _pd
from cache import get, set as _cache_set, invalidate
import logging
from utils.feishu_notifier import send_feishu_scan_alert, send_feishu_test

logger = logging.getLogger(__name__)
strategy_bp = Blueprint('strategy', __name__)

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
    """
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

                for future in as_completed(futures):
                    if scan_status.get('cancelled'):
                        break
                    code, df = future.result()
                    if df is not None:
                        kline_data[code] = df
                        fetched_count += 1
                        if fetched_count % 50 == 0:
                            progress = 25 + int(fetched_count / len(stock_codes) * 30)
                            scan_status['progress'] = min(55, progress)
                            print(f"  📊 K线进度: {fetched_count}/{len(stock_codes)}")

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
                        'macd_golden': bool(latest.get('macd_golden', False)),
                        'cmf_bullish': bool(latest.get('cmf_bullish', False)),
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

        result = _get_quote_sina(code)
        if result:
            return jsonify({'success': True, **result})

        # 备选：东方财富批量接口
        mkt = "1" if code.startswith(("6", "9")) else "0"
        secid = f"{mkt}.{code}"
        try:
            resp = requests.get(
                "http://push2.eastmoney.com/api/qt/ulist/get",
                params={
                    "fltt": "2",
                    "secids": secid,
                    "fields": "f2,f3,f4,f5,f6,f8,f10,f12,f14,f15,f16,f17,f18,f20,f62",
                },
                timeout=8,
            )
            items = resp.json().get('data', {}).get('diff', [])
            if items:
                item = items[0]
                return jsonify({
                    'success': True,
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
                })
        except Exception:
            pass

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

from typing import Dict, List, Optional, Any
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
        parts = [
            f"【市场解读】{parsed.get('marketCommentary','')}",
            f"【策略建议】{parsed.get('positionAdvice','')}",
            f"【风险提示】{parsed.get('riskWarning','')}",
        ]
        recs = parsed.get('recommendedStocks', [])
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


@strategy_bp.route('/api/agents/analyze/<agent_id>', methods=['POST'])
def analyze_single_agent_api(agent_id):
    """单 Agent 分析接口"""
    registry = get_agent_registry()
    if not registry.get(agent_id):
        return jsonify({'success': False, 'error': '未知 Agent'}), 404

    result = analyze_single_agent(agent_id)
    # 内层 result 含 success: False 时不可与外层 success 合并，否则覆盖为 false 导致前端误判失败
    agent_success = result.pop('success', True)
    return jsonify({'success': True, 'agent_success': agent_success, **result})


@strategy_bp.route('/api/agents/analyze/<agent_id>/stream', methods=['POST'])
def analyze_single_agent_stream(agent_id):
    """
    单 Agent 流式分析接口（SSE）
    支持 Function Calling，实时推送 thinking 过程和最终结果
    """
    import flask
    import json
    from utils.llm.agents import get_agent_registry, AGENT_TOOLS, COMMON_TOOLS
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
        
        if not profile:
            yield f"data: {json.dumps({'type': 'error', 'error': '未知 Agent'})}\n\n"
            return

        try:
            # 获取市场数据
            market = get_market_snapshot()
            prompt = render_prompt(profile, market)

            # 获取 Agent 专属工具
            tools = get_agent_tools(_agent_id)
            
            # 构建消息
            messages = [
                {"role": "system", "content": profile.get('system_prompt', '')},
                {"role": "user", "content": prompt}
            ]

            # 流式调用 LLM（带 Function Calling）
            from utils.llm.client import get_client, CallOptions, LLMResponse
            
            client = get_client()
            model = profile.get('model') or 'deepseek-chat'
            temperature = profile.get('temperature', 0.3)
            max_tokens = profile.get('max_tokens', 3000)

            # 发送准备完成消息
            yield f"data: {json.dumps({'type': 'status', 'message': '正在调用 AI 分析...'})}\n\n"

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

                # 收集思考过程
                if resp.reasoning_content:
                    all_thinking += resp.reasoning_content
                    thinking_lines = resp.reasoning_content.strip().split('\n')
                    for line in thinking_lines:
                        if line.strip():
                            yield f"data: {json.dumps({'type': 'thinking', 'content': line.strip()})}\n\n"

                # 收集最终内容
                final_content = resp.content
                total_tokens += resp.tokens_used

                # 检查是否有工具调用
                if resp.tool_calls:
                    # 执行工具调用并添加到消息
                    for tc in resp.tool_calls:
                        tool_name = tc['name']
                        tool_args = tc.get('arguments', {})
                        
                        # 发送工具调用信息
                        yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name, 'args': tool_args})}\n\n"
                        
                        # 执行工具
                        tool_result = execute_tool(tool_name, tool_args)
                        
                        # 发送工具结果
                        yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_name, 'result': tool_result[:500]})}\n\n"
                        
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

            yield f"data: {json.dumps({
                'type': 'done', 
                'agent_id': _agent_id, 
                'agent_name': profile.get('name', ''), 
                'structured': structured, 
                'analysis': final_content, 
                'thinking': all_thinking, 
                'tokens_used': total_tokens
            })}\n\n"

        except Exception as e:
            import traceback
            logger.error(f"[Stream] agent={_agent_id} error={e}\n{traceback.format_exc()}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

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


@strategy_bp.route('/api/agents/batch', methods=['POST'])
def batch_analyze_agents():
    """
    批量分析全部 6 个 Agent，并计算共识结果。
    并行调用，超时保护。
    """
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