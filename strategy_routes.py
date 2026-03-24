#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略中心路由模块
"""

from flask import Blueprint, jsonify, request
import database as db
import threading
import time
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)
strategy_bp = Blueprint('strategy', __name__)

# 全局变量存储当前扫描状态
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
    """获取热点板块列表"""
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
    
    top_sectors = max(1, min(20, int(top_sectors)))
    min_days = max(1, min(10, int(min_days)))
    period = max(10, min(60, int(period)))
    
    logger.info(f"开始扫描: sectors={top_sectors}, min_days={min_days}, period={period}")
    
    params = {
        'sectors': top_sectors,
        'min_days': min_days,
        'period': period
    }
    scan_id = db.create_scan_record(params)
    
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
            
            def fetch_kline(code):
                try:
                    kline_df = get_stock_kline_sina(code, days=120)
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
    """获取历史扫描记录列表"""
    limit = request.args.get('limit', 20, type=int)
    limit = max(1, min(100, limit))
    records = db.get_scan_list(limit=limit)
    return jsonify({
        'success': True,
        'data': records
    })


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
