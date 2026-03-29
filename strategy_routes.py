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
import requests
import threading
import time
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from cache import get, set as _cache_set, invalidate
import logging

logger = logging.getLogger(__name__)
strategy_bp = Blueprint('strategy', __name__)

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
        df = df.dropna(subset=['bb_upper', 'bb_lower', 'bb_middle', 'width_ma_short', 'width_ma_long'])
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
    
    top_sectors = max(1, min(30, int(top_sectors)))
    min_days = max(0, min(100, int(min_days)))
    period = max(10, min(365, int(period)))
    
    logger.info(f"开始扫描: sectors={top_sectors}, min_days={min_days}, period={period}")
    
    params = {
        'sectors': top_sectors,
        'min_days': min_days,
        'period': period
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
        args=(scan_id, top_sectors, min_days, period)
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


def run_scan(scan_id: int, top_sectors: int, min_days: int, period: int):
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
        print(f"🚀 开始扫描: scan_id={scan_id}, sectors={top_sectors}, min_days={min_days}, period={period}")
        
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

            def fetch_kline(code):
                try:
                    kline_df = get_stock_kline_sina(code, days=min(fetch_days, 800))
                    if kline_df is not None and len(kline_df) >= period + 10:
                        return (code, kline_df)
                    return (code, None)
                except:
                    return (code, None)
            
            fetched_count = 0
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for code in stock_codes:
                    future = executor.submit(
                        fetch_with_rate_limit,
                        lambda c=code: fetch_kline(c),
                        delay=0.2
                    )
                    futures.append(future)
                
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
                
                if latest['squeeze_streak'] >= min_days:
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
        
    except Exception as e:
        scan_status['error'] = str(e)
        db.update_scan_status(scan_id, 'error', str(e))
        print(f"❌ 扫描出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        with scan_lock:
            scan_status['is_scanning'] = False


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
    from agent_prompts import extract_json_from_response, normalize_agent_stock_code

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

    api_key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    if not api_key:
        logger.warning('scan_ai_summary: DEEPSEEK_API_KEY 未配置')
        return jsonify({
            'success': False,
            'error': '未配置 DEEPSEEK_API_KEY，无法调用 DeepSeek 生成小结',
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
        resp = requests.post(
            'https://api.deepseek.com/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'deepseek-chat',
                'messages': [
                    {'role': 'system', 'content': system_msg},
                    {'role': 'user', 'content': user_prompt},
                ],
                'temperature': 0.35,
                'max_tokens': 3800,
                'stream': False,
            },
            timeout=120,
        )
        result = resp.json()
        logger.info("[scan_ai_summary] deepseek raw_response_len=%d keys=%s usage=%s",
                    len(resp.text), list(result.keys()), result.get('usage', {}))

        if resp.status_code >= 400 or result.get('error'):
            err = result.get('error') or {}
            msg = err.get('message', resp.text[:200] if resp.text else 'DeepSeek 请求失败')
            logger.warning('scan_ai_summary API error: %s', msg)
            return jsonify({'success': False, 'error': msg}), 502

        msg_data = result['choices'][0]['message']
        reasoning = msg_data.get('reasoning_content') or ''
        content = msg_data.get('content') or ''

        if reasoning:
            logger.info("[scan_ai_summary] reasoning_content length=%d preview=%.80s",
                         len(reasoning), reasoning[:80])

        raw_for_parse = reasoning if reasoning else content
        parsed = extract_json_from_response(raw_for_parse)
        if not parsed:
            parsed = extract_json_from_response(content)

        valid_codes = _scan_valid_stock_codes(detail)

        if not parsed:
            combined_raw = '\n'.join(x for x in [reasoning, content] if x)
            out = {
                'cot_steps': [
                    {'title': '思考过程', 'content': reasoning[:4000] if reasoning else content[:4000]}
                ],
                'recommendations': [],
                'closing_note': content[:1200] if content else '',
                'raw_text': combined_raw[:8000],
                'source': 'deepseek_raw',
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
            'source': 'deepseek',
        }
        db.save_scan_ai_summary(scan_id, out)
        data = db.get_scan_ai_summary(scan_id)
        return jsonify({'success': True, 'data': data, 'cached': False})
    except Exception as e:
        logger.exception('scan_ai_summary failed: %s', e)
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
    
    from utils.ths_crawler import get_stock_kline_sina
    
    if not code or not code.isdigit() or len(code) != 6:
        return jsonify({'success': False, 'error': '无效的股票代码'})
    
    try:
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
        
        df = get_stock_kline_sina(code, days=120)
        
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
                    "fields": "f2,f3,f4,f5,f6,f7,f8,f10,f12,f14,f15,f16,f17,f18,f62",
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
                    'mkt_cap':    item.get('f62'),
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
            # 沪市
            try:
                df_sh = _ak.stock_info_a_code_name(market="SH")
                if df_sh is not None and not df_sh.empty:
                    records = []
                    for _, row in df_sh.iterrows():
                        code = str(row.get('code', '') or row.get('证券代码', '')).strip()
                        name = str(row.get('name', '') or row.get('证券简称', '')).strip()
                        if code and name and len(code) == 6 and code.isdigit():
                            records.append({
                                'code': code,
                                'name': name,
                                'market_type': 'sh',
                            })
                    if records:
                        saved += db.upsert_stocks_batch(records)
            except Exception as e:
                logger.warning(f"[StockSync] 沪市同步失败: {e}")

            # 深市
            try:
                df_sz = _ak.stock_info_a_code_name(market="SZ")
                if df_sz is not None and not df_sz.empty:
                    records = []
                    for _, row in df_sz.iterrows():
                        code = str(row.get('code', '') or row.get('证券代码', '')).strip()
                        name = str(row.get('name', '') or row.get('证券简称', '')).strip()
                        if code and name and len(code) == 6 and code.isdigit():
                            records.append({
                                'code': code,
                                'name': name,
                                'market_type': 'sz',
                            })
                    if records:
                        saved += db.upsert_stocks_batch(records)
            except Exception as e:
                logger.warning(f"[StockSync] 深市同步失败: {e}")

            # 北交所
            try:
                df_bj = _ak.stock_info_a_code_name(market="BJ")
                if df_bj is not None and not df_bj.empty:
                    records = []
                    for _, row in df_bj.iterrows():
                        code = str(row.get('code', '') or row.get('证券代码', '')).strip()
                        name = str(row.get('name', '') or row.get('证券简称', '')).strip()
                        if code and name and len(code) == 6 and code.isdigit():
                            records.append({
                                'code': code,
                                'name': name,
                                'market_type': 'bj',
                            })
                    if records:
                        saved += db.upsert_stocks_batch(records)
            except Exception as e:
                logger.warning(f"[StockSync] 北交所同步失败: {e}")

            # 如果上述接口全部失败，使用备用方案
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
                    "fields": "f2,f3,f4,f5,f6,f8,f10,f12,f14,f15,f16,f17,f18,f62",
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
                    'mkt_cap': item.get('f62'),
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


# ==================== Agent 分析系统 ====================
# 腾讯混元 / 智谱 GLM Prompt Engineering + 多智能体聚合分析

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

# ── LLM 配置 ────────────────────────────────────────────────────────────────

LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'tencent')  # 'tencent' | 'zhipu'
TENANT_KEY = os.environ.get('TENANT_KEY', '')
HUNYUAN_API_KEY = os.environ.get('HUNYUAN_API_KEY', '')   # 腾讯混元 API Key
ZHIPU_API_KEY = os.environ.get('ZHIPU_API_KEY', '')

LLM_MODEL_MAP = {
    'tencent': 'hunyuan-pro',
    'zhipu': 'glm-4-flash',
}


def _llm_invoke(prompt: str, system: str = '', model: str = '',
                 temperature: float = 0.7) -> str:
    """统一调用 LLM 接口（腾讯混元 / 智谱 GLM），超时 60s"""
    if not model:
        model = LLM_MODEL_MAP.get(LLM_PROVIDER, 'hunyuan-pro')

    try:
        if LLM_PROVIDER == 'tencent' and HUNYUAN_API_KEY:
            import urllib.request, urllib.parse
            payload = json.dumps({
                "model": model,
                "messages": (
                    [{"role": "system", "content": system}] if system else []
                ) + [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": 2048,
            }).encode('utf-8')
            req = urllib.request.Request(
                "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {HUNYUAN_API_KEY}",
                    "Content-Type": "application/json",
                },
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data['choices'][0]['message']['content'].strip()

        elif LLM_PROVIDER == 'zhipu' and ZHIPU_API_KEY:
            import urllib.request
            payload = json.dumps({
                "model": model,
                "messages": (
                    [{"role": "system", "content": system}] if system else []
                ) + [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": 2048,
            }).encode('utf-8')
            req = urllib.request.Request(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {ZHIPU_API_KEY}",
                    "Content-Type": "application/json",
                },
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data['choices'][0]['message']['content'].strip()
    except Exception as e:
        logger.warning(f"LLM 调用失败 [{LLM_PROVIDER}]: {e}")
    return ''


# ── Agent Prompt 库 ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """你是一位专业的A股短线交易策略分析师，代号「{agent_name}」，使用{style}风格。
你拥有丰富的题材炒作、龙头战法、板块轮动实战经验，熟悉游资操盘手法与量化指标。
请始终以专业、严谨、客观的态度输出分析，禁止提供具体买卖价格建议。
分析结果仅供研究参考，不构成任何投资建议。"""


@dataclass
class AgentProfile:
    id: str
    name: str
    name_brand: str      # 前端显示简称
    style: str
    system_prompt: str
    user_prompt_tpl: str
    avatar_url: str
    role_subtitle: str
    temperature: float = 0.3   # LLM 随机性，越低越稳定


# 各 Agent Prompt 模板（参考钧哥天下无双格式）
AGENT_PROFILES: Dict[str, AgentProfile] = {
    'jun': AgentProfile(
        id='jun',
        name='钧哥天下无双',
        name_brand='钧哥',
        style='龙头战法',
        system_prompt=SYSTEM_PROMPT.format(agent_name='钧哥天下无双', style='龙头战法（聚焦龙头股、连板股、情绪周期）'),
        user_prompt_tpl="""你是一位A股短线策略分析师「钧哥天下无双」，擅长龙头战法。

请根据以下今日市场数据，从龙头视角给出你的策略分析：

【大盘概况】
上证指数涨跌幅: {market_change:+.2f}%
两市涨停家数: {limit_up_count} 家
市场情绪: {sentiment}

【热门题材 TOP5】
{hot_themes}

【强势股 TOP10】
{top_stocks}

请输出JSON格式的分析结果：
```json
{{
  "agent_id": "jun",
  "agent_name": "钧哥天下无双",
  "stance": "bull|bear|neutral",
  "confidence": 75,
  "marketCommentary": "市场情绪解读（50字以内）",
  "positionAdvice": "仓位建议与调仓方向（80字以内）",
  "riskWarning": "风险提示（50字以内）",
  "recommendedStocks": [
    {{
      "name": "股票名称",
      "code": "000000.SZ",
      "role": "龙头|跟风|补涨",
      "reason": "推荐逻辑（30字以内）",
      "chg_pct": 5.5
    }}
  ]
}}
```""",
        avatar_url='https://lh3.googleusercontent.com/aida-public/AB6AXuD97zD2NIGTCO_1tiXq1wsbA98aL5lltkwfWvGuW5ykcn7zacGqWOfQaC0Cgqq8Y70ssQbZDu4WTh34HYBodcl31NA-stzpx7g9dxTWCMuzM7s7gcIOeZVI8i8nHPZnB0F4J3ToG2bh9x5rvE7Qe3qAnETQRHznWRcVuYltPv923yduEQvww9hwsCd_YcKQjJrZK_VVNT5V0-w_9fQ5GDMZ9eGfWPxUPX4PFFDFtZaCN0EpwpuQSgMG_xOxIR3Btmz_rneBA88VIGp0',
        role_subtitle='龙头战法',
        temperature=0.25,
    ),
    'qiao': AgentProfile(
        id='qiao',
        name='乔帮主',
        name_brand='乔帮主',
        style='板块轮动',
        system_prompt=SYSTEM_PROMPT.format(agent_name='乔帮主', style='板块轮动（聚焦板块节奏、资金流向、产业周期）'),
        user_prompt_tpl="""你是一位A股策略分析师「乔帮主」，擅长板块轮动分析。

请根据以下今日市场数据，分析板块轮动节奏与配置方向：

【大盘概况】
上证指数涨跌幅: {market_change:+.2f}%
市场情绪: {sentiment}
板块轮动特征: {sector_rotation}

【热门题材】
{hot_themes}

【资金流向】
主力净流入板块: {top_inflow_sectors}
主力净流出板块: {top_outflow_sectors}

【强势股】
{top_stocks}

请输出JSON格式的分析结果：
```json
{{
  "agent_id": "qiao",
  "agent_name": "乔帮主",
  "stance": "bull|bear|neutral",
  "confidence": 70,
  "marketCommentary": "板块轮动特征解读（50字以内）",
  "positionAdvice": "板块配置与仓位建议（80字以内）",
  "riskWarning": "风格切换风险提示（50字以内）",
  "recommendedStocks": [
    {{
      "name": "股票名称",
      "code": "000000.SZ",
      "role": "主线龙头|轮动补涨|防御配置",
      "reason": "推荐逻辑（30字以内）",
      "chg_pct": 3.2
    }}
  ]
}}
```""",
        avatar_url='https://lh3.googleusercontent.com/aida-public/AB6AXuAkvzyqjBc8b9-yrIA6kgiCLQcivIp4wH7WIrTQUKwzMfdOzv2XtxUV1wNrNrhfqeTLIsfBuwrA3EAr241oN4kTt-lHWYMl71AITtxC7_wt8A4nW5MoITPdKsNLCU-voyo3kk-xnCUKV3_3FlxK00PYxoASCqVuhe9VcRsOmbddONa0gr6gZFUpH1G88RrCpk-PROMttjpPhO7TZ0ni-GVtLFYsVapWVFGzL1FCMkpV35eb1k3IDjJCoTwR7-_RArQ6FiGkkFrFe9QP',
        role_subtitle='板块轮动',
        temperature=0.30,
    ),
    'jia': AgentProfile(
        id='jia',
        name='炒股养家',
        name_brand='炒股养家',
        style='低位潜伏',
        system_prompt=SYSTEM_PROMPT.format(agent_name='炒股养家', style='低位潜伏（聚焦安全边际、估值修复、左侧布局）'),
        user_prompt_tpl="""你是一位A股价值型交易策略分析师「炒股养家」，擅长低位潜伏与安全边际分析。

请根据以下市场数据，从价值与安全边际角度给出分析：

【大盘概况】
上证指数涨跌幅: {market_change:+.2f}%
市场情绪: {sentiment}

【热门题材】
{hot_themes}

【估值与基本面线索】
PE 较低板块: {low_pe_sectors}
超跌板块: {oversold_sectors}

【强势股】
{top_stocks}

请输出JSON格式的分析结果：
```json
{{
  "agent_id": "jia",
  "agent_name": "炒股养家",
  "stance": "bull|bear|neutral",
  "confidence": 65,
  "marketCommentary": "市场安全边际评估（50字以内）",
  "positionAdvice": "低位布局方向与仓位策略（80字以内）",
  "riskWarning": "左侧布局风险提示（50字以内）",
  "recommendedStocks": [
    {{
      "name": "股票名称",
      "code": "000000.SZ",
      "role": "潜伏标的|价值修复|困境反转",
      "reason": "推荐逻辑（30字以内）",
      "chg_pct": 1.5
    }}
  ]
}}
```""",
        avatar_url='https://lh3.googleusercontent.com/aida-public/AB6AXuCGHKOsrw9P6UWNPtwRIbhOcdxdNbEN4ox5tJN9WMKrpuIDRMSGn8J3pzyTvreLu-7teIzU07GZxcA73Tcn15zCifb-gTMNKucYIvJRRtfnD8_yb5Lkp135iwwUdn2cR7vLp37g7uccbUfYOzGdXVQo5_HBrYIZiv5TgKFSeJ8t5-j0uQAu7VZkOuNLsDBQv8zcpObbrHC3y2ydOpBCzine4Ex3E-LQvcjIDCbWGcOWcetrGAmcOSofOp6KqiV9C8SjYZZV4crcvnKb',
        role_subtitle='低位潜伏',
        temperature=0.20,
    ),
    'speed': AgentProfile(
        id='speed',
        name='极速先锋',
        name_brand='极速先锋',
        style='打板专家',
        system_prompt=SYSTEM_PROMPT.format(agent_name='极速先锋', style='打板专家（聚焦涨停板、情绪高潮点、隔夜溢价）'),
        user_prompt_tpl="""你是一位A股超短线交易策略分析师「极速先锋」，专注涨停板研究与打板策略。

请根据以下市场数据，分析打板机会与风险：

【大盘概况】
上证指数涨跌幅: {market_change:+.2f}%
两市涨停家数: {limit_up_count} 家
炸板率: {break_rate}%
市场情绪: {sentiment}

【热门题材】
{hot_themes}

【连板股与涨停强势股】
{top_stocks}

请输出JSON格式的分析结果：
```json
{{
  "agent_id": "speed",
  "agent_name": "极速先锋",
  "stance": "bull|bear|neutral",
  "confidence": 60,
  "marketCommentary": "打板情绪与溢价空间评估（50字以内）",
  "positionAdvice": "打板方向与仓位控制建议（80字以内）",
  "riskWarning": "炸板与隔夜风险提示（50字以内）",
  "recommendedStocks": [
    {{
      "name": "股票名称",
      "code": "000000.SZ",
      "role": "首板|连板|一字板",
      "reason": "打板逻辑（30字以内）",
      "chg_pct": 10.0
    }}
  ]
}}
```""",
        avatar_url='https://lh3.googleusercontent.com/aida-public/AB6AXuBI1vgeMlusdYkzuj2NE-ZGv7Qn0PwPB9a_8WTgd0SGuQgcffIKV3DMdqPmLrjo_tJOUEbWfFAaM7etkCiK-DL0Kapz57lZHDU_E2NrtrhRLiyYhFUv4Wjod5RP80FRuRoaI6Imm8MC3xR_Fk4UVdMODD4y766SLxZpwZ6wfesd3pjueWfMgRetsFTOBrdDiR9sO0SmJ3UVyPu0w3xeOx2YfAI8VEUP5yhV5egxcDv0BQBPOWmUPY1n6ED5gCwKVlSooRXybPuYgEVS',
        role_subtitle='打板专家',
        temperature=0.35,
    ),
    'trend': AgentProfile(
        id='trend',
        name='趋势追随者',
        name_brand='趋势追随者',
        style='中线波段',
        system_prompt=SYSTEM_PROMPT.format(agent_name='趋势追随者', style='中线波段（聚焦趋势线、均线系统、趋势破坏信号）'),
        user_prompt_tpl="""你是一位A股中线波段策略分析师「趋势追随者」，擅长趋势跟踪与均线系统分析。

请根据以下市场数据，分析中期趋势方向与波段机会：

【大盘概况】
上证指数涨跌幅: {market_change:+.2f}%
市场情绪: {sentiment}

【趋势指标】
均线系统: {ma_system}
趋势状态: {trend_state}

【热门题材】
{hot_themes}

【强势股】
{top_stocks}

请输出JSON格式的分析结果：
```json
{{
  "agent_id": "trend",
  "agent_name": "趋势追随者",
  "stance": "bull|bear|neutral",
  "confidence": 72,
  "marketCommentary": "中期趋势方向判断（50字以内）",
  "positionAdvice": "波段操作建议与趋势保护（80字以内）",
  "riskWarning": "趋势破坏与止损提示（50字以内）",
  "recommendedStocks": [
    {{
      "name": "股票名称",
      "code": "000000.SZ",
      "role": "趋势股|波段标的|均线支撑",
      "reason": "趋势逻辑（30字以内）",
      "chg_pct": 4.8
    }}
  ]
}}
```""",
        avatar_url='https://lh3.googleusercontent.com/aida-public/AB6AXuC7iUecTzgh3H2Vfw_JF5So-Z65G9cEHtjtOH7DEpIkIAvZVHQD6hDEjwcthbiSx752DTPKTOWEo95r0Q7cwv2gz0FSSYH1TddIwzZy58u2sHd2jjQgjqv4Rz16eJOIaRUgO5y0uI_DjjZt935pLPrGECMwP4rGV9rg_9voHG4bA8bi_3seWorRDwsmUj7vNh2_FiyvN963Et2sHDidpmRnG2hntpi1oHnFFbScS5u_oIfAFIvKdj0DG6C7bTHJToK3ya0bUw5Mal3y',
        role_subtitle='中线波段',
        temperature=0.20,
    ),
    'quant': AgentProfile(
        id='quant',
        name='量化之翼',
        name_brand='量化之翼',
        style='算法回测',
        system_prompt=SYSTEM_PROMPT.format(agent_name='量化之翼', style='算法回测（聚焦多因子模型、波动率、量化择时）'),
        user_prompt_tpl="""你是一位量化策略分析师「量化之翼」，擅长多因子模型与量化择时分析。

请根据以下市场数据，给出量化视角的分析：

【大盘概况】
上证指数涨跌幅: {market_change:+.2f}%
市场情绪: {sentiment}

【量化指标】
布林带状态: {bb_state}
MACD信号: {macd_signal}
RSI指标: {rsi_value}
成交量状态: {volume_state}

【热门题材】
{hot_themes}

【强势股】
{top_stocks}

请输出JSON格式的分析结果：
```json
{{
  "agent_id": "quant",
  "agent_name": "量化之翼",
  "stance": "bull|bear|neutral",
  "confidence": 68,
  "marketCommentary": "量化指标综合解读（50字以内）",
  "positionAdvice": "量化模型仓位建议与因子配置（80字以内）",
  "riskWarning": "波动率风险与模型局限提示（50字以内）",
  "recommendedStocks": [
    {{
      "name": "股票名称",
      "code": "000000.SZ",
      "role": "因子强势|动量标的|低波防御",
      "reason": "量化逻辑（30字以内）",
      "chg_pct": 2.1
    }}
  ]
}}
```""",
        avatar_url='https://lh3.googleusercontent.com/aida-public/AB6AXuDGooDuo4HpiasBYDo6fvclBIFA-Gh4cz1OC5oVGRLDNxZJjYYx0j2REaQm6JDUHsEoUPFF1_w4cMBqT8qOZnTA6PHhdNfLvwxOrGe-V954yPvS_z1wJsPCEe5FQCb4-3dB2HiQjFwqveRFT0dOijk0eU_XX-RYIzJuzvzF9Y3eI343MalIdAFvOwUJH0NAGG3PxoqVPtKwHoNZRpT4MKFN-TGzRm55gHx_47AYleZV04gHMAVos0Y2tUQazlvkUpk9IyoyupmByD_e',
        role_subtitle='算法回测',
        temperature=0.15,
    ),
}


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


# ── Prompt 渲染 ─────────────────────────────────────────────────────────────

def render_prompt(profile: AgentProfile, market: Dict[str, Any]) -> str:
    """将市场数据填充到 Agent 的 Prompt 模板"""
    tpl = profile.user_prompt_tpl
    for key, val in market.items():
        placeholder = '{' + key + '}'
        tpl = tpl.replace(placeholder, str(val))
    return tpl


# ── JSON 解析 ───────────────────────────────────────────────────────────────

def extract_json(text: str) -> Optional[Dict]:
    """从 LLM 返回内容中提取 JSON"""
    # 优先找代码块
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass
    # 兜底：全文找 JSON 对象
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return None


# ── 单个 Agent 分析 ─────────────────────────────────────────────────────────

def analyze_single_agent(agent_id: str) -> Dict[str, Any]:
    """调用 LLM 执行单个 Agent 的策略分析"""

    # ── 特殊处理：jun（钧哥）使用 JunGeTrader ──────────────────────────────
    if agent_id == 'jun':
        try:
            from junge_trader import JunGeTrader
            trader = JunGeTrader(use_ai=True)
            scan_result = trader.run_daily_scan(top_sectors=5, enhance=True)

            # JunGeTrader AI 增强结果直接返回
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
                    # JunGeTrader 附加数据
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
                # AI 增强失败，返回纯扫描结果
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

    # ── 其他 Agent：原有逻辑 ────────────────────────────────────────────────
    profile = AGENT_PROFILES.get(agent_id)
    if not profile:
        return {'agent_id': agent_id, 'success': False, 'error': f'未知 Agent: {agent_id}'}

    market = get_market_snapshot()
    prompt = render_prompt(profile, market)
    raw = _llm_invoke(
        prompt,
        system=profile.system_prompt,
        temperature=profile.temperature,
    )

    result = {
        'agent_id': agent_id,
        'agent_name': profile.name,
        'name_brand': profile.name_brand,
        'role_subtitle': profile.role_subtitle,
        'avatar_url': profile.avatar_url,
        'success': False,
        'raw_response': raw,
        'structured': None,
        'analysis': '',
        'tokens_used': 0,
    }

    if not raw:
        result['error'] = 'LLM 调用返回空'
        return result

    # 解析结构化数据
    parsed = extract_json(raw)
    if parsed:
        result['success'] = True
        result['structured'] = {
            'agentId': parsed.get('agent_id', agent_id),
            'agentName': parsed.get('agent_name', profile.name),
            'stance': parsed.get('stance', 'neutral'),
            'confidence': int(parsed.get('confidence', 50)),
            'marketCommentary': str(parsed.get('marketCommentary', '')),
            'positionAdvice': str(parsed.get('positionAdvice', '')),
            'riskWarning': str(parsed.get('riskWarning', '')),
            'recommendedStocks': parsed.get('recommendedStocks', []),
        }
        # 拼接自然语言分析
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
        # 解析失败时将 raw 作为纯文本分析
        result['success'] = True
        result['analysis'] = raw
        result['structured'] = {
            'agentId': agent_id,
            'agentName': profile.name,
            'stance': 'neutral',
            'confidence': 50,
            'marketCommentary': raw[:100],
            'positionAdvice': raw[100:200],
            'riskWarning': '',
            'recommendedStocks': [],
        }

    return result


# ── API 路由 ────────────────────────────────────────────────────────────────

@strategy_bp.route('/api/agents/prompts')
def get_agent_prompts():
    """返回所有 Agent 的元信息（前端渲染用）"""
    data = []
    for p in AGENT_PROFILES.values():
        data.append({
            'id': p.id,
            'name': p.name,
            'name_brand': p.name_brand,
            'style': p.style,
            'avatar_url': p.avatar_url,
            'role_subtitle': p.role_subtitle,
        })
    return jsonify({'success': True, 'data': data})


@strategy_bp.route('/api/agents/analyze/<agent_id>', methods=['POST'])
def analyze_single_agent_api(agent_id):
    """单 Agent 分析接口"""
    if agent_id not in AGENT_PROFILES:
        return jsonify({'success': False, 'error': '未知 Agent'}), 404

    result = analyze_single_agent(agent_id)
    return jsonify({'success': True, **result})


@strategy_bp.route('/api/agents/batch', methods=['POST'])
def batch_analyze_agents():
    """
    批量分析全部 6 个 Agent，并计算共识结果。
    并行调用，超时保护。
    """
    agent_ids = list(AGENT_PROFILES.keys())

    # 并行执行所有 Agent
    from concurrent.futures import ThreadPoolExecutor, as_completed
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
                all_recs.append({
                    'name': s.get('name', ''),
                    'code': s.get('code', ''),
                    'role': s.get('role', ''),
                    'reason': s.get('reason', ''),
                    'chg_pct': float(s.get('chg_pct', 0)),
                    'agent': r.get('agent_name', ''),
                })
    all_recs.sort(key=lambda x: x['chg_pct'], reverse=True)
    top_recs = all_recs[:3]

    # 共识机会展示
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
            'meta': f"{rec['role']} · {rec['reason'][:20]}",
            'chg': rec['chg_pct'],
            'flowLabel': f"来源: {rec['agent']}",
        })

    # 如果没有推荐数据，填充演示数据
    if not consensus_opportunities:
        consensus_opportunities = [
            {'rank': 1, 'title': '宁德时代 (300750.SZ)', 'badge': '龙头共识', 'badgeKind': 'primary',
             'meta': '主线龙头 · 资金持续流入', 'chg': 5.8, 'flowLabel': '来源: 钧哥天下无双'},
            {'rank': 2, 'title': '北方华创 (002371.SZ)', 'badge': '多策略共振', 'badgeKind': 'primary',
             'meta': '趋势跟随 · 均线多头排列', 'chg': 4.2, 'flowLabel': '来源: 乔帮主'},
            {'rank': 3, 'title': '比亚迪 (002594.SZ)', 'badge': '资金认可', 'badgeKind': 'muted',
             'meta': '板块轮动 · 底部放量', 'chg': 3.1, 'flowLabel': '来源: 量化之翼'},
        ]

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


@strategy_bp.route('/api/agents/demo/<agent_id>')
def demo_agent(agent_id):
    """
    演示模式：不调 LLM，直接返回模拟分析结果。
    用于前端调试和 UI 展示。
    """
    demos = {
        'jun': {
            'agent_id': 'jun', 'agent_name': '钧哥天下无双', 'name_brand': '钧哥',
            'role_subtitle': '龙头战法',
            'success': True,
            'raw_response': '',
            'structured': {
                'agentId': 'jun', 'agentName': '钧哥天下无双',
                'stance': 'bull', 'confidence': 82,
                'marketCommentary': '市场情绪亢奋，龙头股联动效应显著，连板个股情绪高涨，适合聚焦主线龙头。',
                'positionAdvice': '维持8成仓位，重点配置当前主线龙头与连板强势股，跟随主力资金方向，积极参与情绪溢价。',
                'riskWarning': '警惕高位分歧加大，随时关注炸板率变化，做好隔夜仓控管理。',
                'recommendedStocks': [
                    {'name': '龙头股份', 'code': '600630.SH', 'role': '龙头', 'reason': '板块龙头连板，人气极高', 'chg_pct': 10.0},
                    {'name': '宁德时代', 'code': '300750.SZ', 'role': '中军', 'reason': '行业龙头，机构锁仓', 'chg_pct': 5.5},
                ],
            },
            'analysis': '【市场解读】市场情绪亢奋，龙头股联动效应显著，连板个股情绪高涨，适合聚焦主线龙头。\n【策略建议】维持8成仓位，重点配置当前主线龙头与连板强势股，跟随主力资金方向，积极参与情绪溢价。\n【风险提示】警惕高位分歧加大，随时关注炸板率变化，做好隔夜仓控管理。',
            'tokens_used': 0,
        },
        'qiao': {
            'agent_id': 'qiao', 'agent_name': '乔帮主', 'name_brand': '乔帮主',
            'role_subtitle': '板块轮动',
            'success': True,
            'raw_response': '',
            'structured': {
                'agentId': 'qiao', 'agentName': '乔帮主',
                'stance': 'bull', 'confidence': 74,
                'marketCommentary': '板块轮动有序，科技与消费交替上行，市场风格偏向成长，轮动节奏良好。',
                'positionAdvice': '维持7成仓位，主线持仓为主，辅以波段降本，关注板块轮动节奏变化。',
                'riskWarning': '警惕风格快速切换，保持组合灵活性，注意高位板块补跌风险。',
                'recommendedStocks': [
                    {'name': '北方华创', 'code': '002371.SZ', 'role': '轮动龙头', 'reason': '半导体主线，业绩超预期', 'chg_pct': 4.8},
                ],
            },
            'analysis': '【市场解读】板块轮动有序，科技与消费交替上行，市场风格偏向成长，轮动节奏良好。\n【策略建议】维持7成仓位，主线持仓为主，辅以波段降本，关注板块轮动节奏变化。',
            'tokens_used': 0,
        },
    }
    if agent_id not in demos:
        return jsonify({'success': False, 'error': '未知 Agent'}), 404
    return jsonify({'success': True, **demos[agent_id]})


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