#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
布林带收缩策略 - Flask Web 应用
"""

import sys
# 禁用输出缓冲，确保 print 立即显示
sys.stdout.reconfigure(line_buffering=True)

from flask import Flask, render_template, jsonify, request
from bollinger_squeeze_strategy import BollingerSqueezeStrategy
from utils.retry import retry_request
import pandas as pd
from datetime import datetime, timedelta
import threading
import time
import random
import logging

# 导入数据库模块
import database as db

# 导入 AI 服务模块
from ai_service import get_ai_service

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 全局变量存储当前扫描状态（用于实时进度查询）
scan_status = {
    'is_scanning': False,
    'scan_id': None,
    'progress': 0,
    'current_sector': '',
    'error': None,
    'cancelled': False
}


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/hot-sectors')
def get_hot_sectors():
    """
    获取热点板块列表（同花顺数据源）
    
    返回当前A股市场涨幅前20的热点板块信息。
    
    Query Parameters:
        limit (int, optional): 返回数量限制，默认20，最大50
        
    Returns:
        JSON: {
            success: bool,
            data: [{name, change, leader, leader_change}, ...],
            error: str (仅失败时)
        }
    """
    try:
        from utils.ths_crawler import get_ths_industry_list
        
        # 获取并验证 limit 参数
        limit = request.args.get('limit', 20, type=int)
        limit = max(1, min(50, limit))  # 限制在 1-50 之间
        
        logger.info(f"获取热点板块列表(THS)，limit={limit}")
        
        df = retry_request(get_ths_industry_list, max_retries=3, delay=1.0)
        
        if df is None or len(df) == 0:
            logger.warning("热点板块数据为空")
            return jsonify({'success': False, 'error': '无法获取数据'})
        
        # 构建返回数据（已按涨跌幅排序）
        sectors = []
        for _, row in df.head(limit).iterrows():
            sectors.append({
                'name': row['板块'],
                'change': round(float(row['涨跌幅']), 2),
                'leader': row.get('领涨股', ''),
                'leader_change': round(float(row.get('领涨股-涨跌幅', 0)), 2)
            })
        
        logger.info(f"成功获取 {len(sectors)} 个热点板块")
        return jsonify({'success': True, 'data': sectors})
        
    except Exception as e:
        logger.error(f"获取热点板块失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/scan/start', methods=['POST'])
def start_scan():
    """
    开始扫描任务
    
    启动后台扫描线程，扫描热点板块中符合布林带收缩条件的股票。
    
    Request Body (JSON):
        sectors (int, optional): 扫描板块数量，默认5，范围1-20
        min_days (int, optional): 最小收缩天数，默认3，范围1-10
        period (int, optional): 布林带周期，默认20，范围10-60
        
    Returns:
        JSON: {
            success: bool,
            message: str,
            scan_id: int (成功时)
        }
    """
    global scan_status
    
    if scan_status['is_scanning']:
        return jsonify({'success': False, 'error': '扫描正在进行中'})
    
    data = request.json or {}
    
    # 参数验证和默认值
    top_sectors = data.get('sectors', 5)
    min_days = data.get('min_days', 3)
    period = data.get('period', 20)
    
    # 参数范围验证
    top_sectors = max(1, min(20, int(top_sectors)))
    min_days = max(1, min(10, int(min_days)))
    period = max(10, min(60, int(period)))
    
    logger.info(f"开始扫描: sectors={top_sectors}, min_days={min_days}, period={period}")
    
    # 创建数据库记录
    params = {
        'sectors': top_sectors,
        'min_days': min_days,
        'period': period
    }
    scan_id = db.create_scan_record(params)
    
    # 重置状态
    scan_status = {
        'is_scanning': True,
        'scan_id': scan_id,
        'progress': 0,
        'current_sector': '准备中...',
        'error': None,
        'cancelled': False
    }
    
    # 在后台线程执行扫描
    import sys
    print(f"🚀 启动扫描线程: scan_id={scan_id}", flush=True)
    sys.stdout.flush()
    thread = threading.Thread(
        target=run_scan,
        args=(scan_id, top_sectors, min_days, period)
    )
    thread.daemon = True
    thread.start()
    print(f"✅ 扫描线程已启动", flush=True)
    sys.stdout.flush()
    
    return jsonify({'success': True, 'message': '扫描已开始', 'scan_id': scan_id})


@app.route('/api/scan/cancel', methods=['POST'])
def cancel_scan():
    """取消当前扫描"""
    global scan_status
    
    if not scan_status['is_scanning']:
        return jsonify({'success': False, 'error': '没有正在进行的扫描'})
    
    scan_status['cancelled'] = True
    scan_status['current_sector'] = '正在取消...'
    
    return jsonify({'success': True, 'message': '正在取消扫描'})


def analyze_single_stock(strategy, stock_info, precache_kline=True):
    """分析单只股票（用于并发）
    
    Args:
        strategy: 策略实例
        stock_info: 股票信息字典
        precache_kline: 是否预缓存K线数据（默认True）
    """
    # 随机延迟 0.05-0.15 秒，错开请求时间避免API限流
    time.sleep(random.uniform(0.05, 0.15))
    
    try:
        code = stock_info['code']
        name = stock_info['name']
        result = strategy.analyze_stock(code, name, return_df=precache_kline)
        
        if result:
            # 如果返回了df，提取并缓存K线数据
            df = None
            if isinstance(result, tuple):
                result, df = result
            
            # 添加板块信息
            result['sector_name'] = stock_info.get('sector_name', '')
            result['sector_change'] = stock_info.get('sector_change', 0)
            
            # 添加标签信息
            result['is_leader'] = stock_info.get('is_leader', False)
            result['leader_rank'] = stock_info.get('leader_rank', 0)
            result['market_cap'] = stock_info.get('market_cap', 0)
            
            # 生成标签列表（不含emoji，由前端添加图标）
            tags = []
            
            # 评级标签 (最重要)
            grade = result.get('grade', 'C')
            if grade == 'S':
                tags.append("S级")
            elif grade == 'A':
                tags.append("A级")
            
            # 中军标签
            if result['is_leader']:
                tags.append(f"中军#{result['leader_rank']}")
            
            # CMF 资金流标签
            if result.get('cmf_strong_bullish'):
                tags.append("强势流入")
            elif result.get('cmf_bullish') and result.get('cmf_rising'):
                tags.append("资金流入")
            elif result.get('cmf_bullish'):
                tags.append("资金净流入")
            
            # RSV 标签
            if result.get('rsv_recovering'):
                tags.append("超卖回升")
            elif result.get('rsv_golden'):
                rsv_val = result.get('rsv', 50)
                if rsv_val >= 65:
                    tags.append("RSV强势")
                else:
                    tags.append("RSV健康")
            
            # 趋势标签
            if result.get('ma_full_bullish'):
                tags.append("多头排列")
            elif result.get('ma_bullish'):
                tags.append("短多")
            
            # MACD标签
            if result.get('macd_golden') and result.get('macd_hist_positive'):
                tags.append("MACD强势")
            elif result.get('macd_golden'):
                tags.append("MACD金叉")
            
            # 量能标签
            if result.get('is_volume_price_up'):
                tags.append("量价齐升")
            elif result.get('is_volume_up'):
                tags.append("放量")
            
            # 波动率标签
            if result.get('low_volatility'):
                tags.append("低波蓄势")
            
            # 人气标签（根据换手率）
            turnover = result.get('turnover', 0)
            if 3 <= turnover <= 10:
                tags.append("人气旺")
            elif turnover > 10:
                tags.append("超人气")
            elif 1 <= turnover < 3:
                tags.append("有关注")
            
            # 其他标签
            if result.get('pct_change', 0) >= 5:
                tags.append("先锋")
            
            result['tags'] = tags
            
            # 如果有df，预缓存K线数据
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
    """从DataFrame准备K线数据（供缓存使用）"""
    try:
        # 移除包含NaN的行
        df = df.dropna(subset=['bb_upper', 'bb_lower', 'bb_middle', 'width_ma_short', 'width_ma_long'])
        
        # 取最近60天数据
        df = df.tail(60)
        
        if len(df) == 0:
            return None
        
        # 转换为列表，处理可能的NaN值
        def safe_list(series):
            return [None if pd.isna(x) else float(x) for x in series]
        
        # 日期转字符串
        def date_to_str(d):
            if hasattr(d, 'strftime'):
                return d.strftime('%Y-%m-%d')
            return str(d)
        
        # 生成蜡烛图数据 (Lightweight Charts格式)
        candles = []
        for _, row in df.iterrows():
            candles.append({
                'time': date_to_str(row['date']),
                'open': float(row['open']) if pd.notna(row['open']) else None,
                'high': float(row['high']) if pd.notna(row['high']) else None,
                'low': float(row['low']) if pd.notna(row['low']) else None,
                'close': float(row['close']) if pd.notna(row['close']) else None,
            })
        
        # 生成成交量数据（红涨绿跌，与蜡烛图一致）
        volume_data = []
        for _, row in df.iterrows():
            color = '#ef5350' if row['close'] >= row['open'] else '#26a69a'
            volume_data.append({
                'time': date_to_str(row['date']),
                'value': float(row['volume']) if pd.notna(row['volume']) else 0,
                'color': color
            })
        
        # 布林带数据
        bb_upper_data = [{'time': date_to_str(row['date']), 'value': float(row['bb_upper'])} for _, row in df.iterrows() if pd.notna(row['bb_upper'])]
        bb_middle_data = [{'time': date_to_str(row['date']), 'value': float(row['bb_middle'])} for _, row in df.iterrows() if pd.notna(row['bb_middle'])]
        bb_lower_data = [{'time': date_to_str(row['date']), 'value': float(row['bb_lower'])} for _, row in df.iterrows() if pd.notna(row['bb_lower'])]
        
        # CMF 数据
        cmf_data = safe_list(df['cmf']) if 'cmf' in df.columns else []
        
        # 涨跌幅数据
        pct_change_data = safe_list(df['pct_change']) if 'pct_change' in df.columns else []
        
        # 最新价格信息
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
        }
    except Exception as e:
        print(f"[ERROR] prepare_kline_data 失败: {e}")
        return None


# ==================== 并发控制工具 ====================
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 全局信号量，控制 API 请求频率
api_semaphore = threading.Semaphore(3)  # 最多3个并发请求


def fetch_with_rate_limit(func, delay=0.3):
    """带限流的请求包装器"""
    with api_semaphore:
        time.sleep(delay)
        return func()


def run_scan(scan_id: int, top_sectors: int, min_days: int, period: int):
    """
    高效扫描任务（使用同花顺数据源）
    
    数据流程：
    1. 同花顺行业排行 → 获取热点板块
    2. 同花顺行业成分股 → 爬取成分股列表
    3. 新浪K线接口 → 获取K线数据
    4. pandas向量化 → 计算技术指标
    
    优化策略：
    1. 成分股缓存：当日有效，避免重复爬取
    2. K线缓存：当日有效，大幅减少API调用
    3. 并发获取：5线程并发获取K线
    """
    global scan_status
    
    # 导入同花顺爬虫
    from utils.ths_crawler import (
        get_ths_industry_list, 
        fetch_ths_industry_stocks,
        get_stock_kline_sina
    )
    
    try:
        start_time = time.time()
        print(f"🚀 开始扫描(THS数据源): scan_id={scan_id}, sectors={top_sectors}, min_days={min_days}, period={period}")
        
        strategy = BollingerSqueezeStrategy(
            period=period,
            min_squeeze_days=min_days
        )
        
        # ========== 1. 获取热点板块（同花顺）==========
        print("📊 获取同花顺热点板块...")
        scan_status['current_sector'] = '获取热点板块...'
        
        df = retry_request(get_ths_industry_list, max_retries=3, delay=1.0)
        
        if df is None or len(df) == 0:
            raise Exception('无法获取热点板块数据')
        
        # 取前N个热点板块（DataFrame 已包含代码）
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
        
        # ========== 2. 获取成分股（优先缓存，爬虫获取）==========
        print(f"\n📥 获取 {len(hot_sectors_list)} 个板块的成分股...")
        scan_status['current_sector'] = '获取成分股...'
        scan_status['progress'] = 10
        
        # 先查缓存
        cached_sectors = db.get_all_sector_stocks_cache(sector_names)
        print(f"  📦 缓存命中: {len(cached_sectors)}/{len(sector_names)} 个板块")
        
        # 需要爬取的板块
        sectors_to_fetch = [s for s in hot_sectors_list if s['name'] not in cached_sectors]
        
        all_sector_stocks = dict(cached_sectors)  # 从缓存开始
        
        if sectors_to_fetch:
            print(f"  🌐 需要爬取: {len(sectors_to_fetch)} 个板块")
            
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
                        # 按市值排序
                        stocks.sort(key=lambda x: x.get('market_cap', 0), reverse=True)
                        # 保存到缓存
                        db.save_sector_stocks_cache(sector_name, stocks)
                        all_sector_stocks[sector_name] = stocks
                        print(f"  ✅ {sector_name}: {len(stocks)} 只")
                    else:
                        print(f"  ⚠️ {sector_name}: 无成分股数据")
                        
                except Exception as e:
                    print(f"  ❌ {sector_name}: {e}")
        
        # 合并去重，添加板块信息
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
        print(f"📊 成分股: {len(stock_codes)} 只（去重后）\n")
        
        # ========== 3. 获取K线数据（新浪接口，优先缓存）==========
        print(f"📈 获取K线数据(新浪接口)...")
        scan_status['current_sector'] = '获取K线数据...'
        scan_status['progress'] = 25
        
        # 批量查缓存
        cached_klines = db.get_kline_cache_batch(stock_codes)
        print(f"  📦 K线缓存命中: {len(cached_klines)}/{len(stock_codes)}")
        
        # 需要获取的股票
        codes_to_fetch = [c for c in stock_codes if c not in cached_klines]
        
        kline_data = dict(cached_klines)  # 从缓存开始
        
        if codes_to_fetch:
            print(f"  🌐 需要获取: {len(codes_to_fetch)} 只股票K线")
            
            def fetch_kline(code):
                try:
                    # 使用新浪接口
                    kline_df = get_stock_kline_sina(code, days=120)
                    if kline_df is not None and len(kline_df) >= period + 10:
                        return (code, kline_df)
                    return (code, None)
                except:
                    return (code, None)
            
            # 并发获取K线（5线程）
            fetched_count = 0
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for code in codes_to_fetch:
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
                        
                        # 更新进度
                        if fetched_count % 50 == 0:
                            progress = 25 + int(fetched_count / len(codes_to_fetch) * 30)
                            scan_status['progress'] = min(55, progress)
                            print(f"  📊 K线进度: {fetched_count}/{len(codes_to_fetch)}")
            
            print(f"  ✅ K线获取完成: {fetched_count}/{len(codes_to_fetch)}")
        
        # ========== 4. 批量计算指标并筛选 ==========
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
                # 如果是缓存的dict，跳过（已经是分析结果）
                if isinstance(df, dict):
                    # 缓存的是原始K线数据，需要转换
                    continue
                
                # 计算指标
                df = strategy.calculate_bollinger_bands(df)
                df = strategy.calculate_squeeze_signal(df)
                df = strategy.calculate_volume_signal(df)
                df = strategy.calculate_trend_indicators(df)
                df = strategy.calculate_composite_score(df)
                
                latest = df.iloc[-1]
                
                # 筛选
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
                        'turnover': round(float(latest.get('turnover', 0)), 2),
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
                    }
                    
                    # 生成标签
                    tags = []
                    if result['grade'] in ['S', 'A']:
                        tags.append(f"{result['grade']}级")
                    if result['is_leader']:
                        tags.append(f"中军#{result['leader_rank']}")
                    if result.get('cmf_bullish'):
                        tags.append("资金流入")
                    if result.get('is_volume_price_up'):
                        tags.append("量价齐升")
                    result['tags'] = tags
                    
                    analyzed_results.append(result)
                
                # 更新进度
                if (idx + 1) % 100 == 0:
                    progress = 60 + int((idx + 1) / total * 30)
                    scan_status['progress'] = min(90, progress)
                    
            except Exception:
                continue
        
        print(f"📈 分析完成，符合条件: {len(analyzed_results)} 只")
        
        # ========== 5. 保存结果 ==========
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
        scan_status['is_scanning'] = False


@app.route('/api/scan/status')
def get_scan_status():
    """
    获取当前扫描状态
    
    返回当前扫描任务的实时状态信息。
    
    Returns:
        JSON: {
            is_scanning: bool,      # 是否正在扫描
            scan_id: int,           # 当前扫描ID
            progress: int,          # 进度百分比 (0-100)
            current_sector: str,    # 当前扫描的板块
            error: str,             # 错误信息（如有）
            cancelled: bool         # 是否已取消
        }
    """
    return jsonify({
        'is_scanning': scan_status['is_scanning'],
        'scan_id': scan_status.get('scan_id'),
        'progress': scan_status['progress'],
        'current_sector': scan_status['current_sector'],
        'error': scan_status['error'],
        'cancelled': scan_status.get('cancelled', False)
    })


@app.route('/api/scan/results')
def get_scan_results():
    """
    获取扫描结果
    
    返回指定扫描或最新完成扫描的结果数据。
    
    Query Parameters:
        scan_id (int, optional): 指定扫描ID，不传则返回最新完成的扫描
        
    Returns:
        JSON: {
            success: bool,
            scan_id: int,
            results: {板块名: {change: float, stocks: [...]}},
            hot_sectors: [{name, change}, ...],
            last_update: str
        }
    """
    # 从请求参数获取 scan_id，如果没有则获取最新的
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


@app.route('/api/scan/history')
def get_scan_history():
    """
    获取历史扫描记录列表
    
    Query Parameters:
        limit (int, optional): 返回数量限制，默认20
        
    Returns:
        JSON: {success: bool, data: [...]}
    """
    limit = request.args.get('limit', 20, type=int)
    limit = max(1, min(100, limit))  # 限制在 1-100 之间
    records = db.get_scan_list(limit=limit)
    return jsonify({
        'success': True,
        'data': records
    })


@app.route('/api/scan/<int:scan_id>', methods=['GET'])
def get_scan_detail(scan_id: int):
    """
    获取指定扫描的详细结果
    
    Args:
        scan_id: 扫描记录ID
        
    Returns:
        JSON: {success: bool, data: {...}}
    """
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


@app.route('/api/scan/<int:scan_id>', methods=['DELETE'])
def delete_scan(scan_id: int):
    """删除指定扫描记录"""
    # 检查是否正在扫描中
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


@app.route('/api/scan/clear', methods=['DELETE'])
def clear_all_scans():
    """清空所有扫描记录"""
    if scan_status['is_scanning']:
        return jsonify({
            'success': False,
            'error': '有扫描正在进行中，请稍后再试'
        }), 400
    
    count = db.delete_all_scans()
    return jsonify({
        'success': True,
        'message': f'已清空 {count} 条记录'
    })


# 全局请求限流器
last_api_request_time = 0
API_REQUEST_INTERVAL = 1.0  # 最小请求间隔（秒）

@app.route('/api/stock/<code>')
def get_stock_detail(code: str):
    """
    获取单只股票详情（使用新浪接口）
    
    返回指定股票的K线数据和技术指标。优先使用缓存数据。
    
    Args:
        code: 股票代码（6位数字）
        
    Returns:
        JSON: {
            success: bool,
            data: {candles, volumes, bb_*, cmf, ...},
            cached: bool,  # 是否来自缓存
            error: str (仅失败时)
        }
        
    Note:
        - 缓存有效期为当日
        - 两次API请求间隔至少1秒（限流保护）
    """
    global last_api_request_time
    
    from utils.ths_crawler import get_stock_kline_sina
    
    # 参数验证
    if not code or not code.isdigit() or len(code) != 6:
        return jsonify({'success': False, 'error': '无效的股票代码'})
    
    try:
        # 先检查缓存（当日有效）
        cached_data = db.get_kline_cache(code)
        if cached_data:
            logger.info(f"[CACHE HIT] 股票 {code} 使用缓存数据")
            return jsonify({'success': True, 'data': cached_data, 'cached': True})
        
        logger.info(f"[CACHE MISS] 股票 {code} 从新浪API获取数据")
        
        # 全局限流：确保两次API调用之间至少间隔 1 秒
        current_time = time.time()
        time_since_last = current_time - last_api_request_time
        if time_since_last < API_REQUEST_INTERVAL:
            time.sleep(API_REQUEST_INTERVAL - time_since_last)
        
        last_api_request_time = time.time()
        
        # 使用新浪接口获取K线（已包含重试）
        df = get_stock_kline_sina(code, days=120)
        
        if df is None or df.empty:
            return jsonify({'success': False, 'error': '数据获取失败，请稍后重试'})
        
        strategy = BollingerSqueezeStrategy()
        df = strategy.calculate_bollinger_bands(df)
        df = strategy.calculate_squeeze_signal(df)
        df = strategy.calculate_trend_indicators(df)  # 包含 CMF 计算
        
        # 使用公共函数准备K线数据
        data = prepare_kline_data(df)
        
        if data is None:
            return jsonify({'success': False, 'error': '数据处理失败'})
        
        # 保存到缓存
        db.save_kline_cache(code, data)
        logger.info(f"[CACHE SAVE] 股票 {code} 数据已缓存")
        
        return jsonify({'success': True, 'data': data, 'cached': False})
        
    except Exception as e:
        logger.error(f"获取股票 {code} 详情失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/cache/stats')
def get_cache_stats():
    """获取缓存统计信息"""
    try:
        stats = db.get_kline_cache_stats()
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/cache/clear', methods=['DELETE'])
def clear_cache():
    """清理过期缓存（非当日）"""
    try:
        count = db.delete_expired_kline_cache()
        return jsonify({
            'success': True,
            'message': f'已清理 {count} 条过期缓存'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== 自选股 API ====================

@app.route('/api/watchlist')
def get_watchlist():
    """获取自选列表"""
    try:
        stocks = db.get_watchlist()
        return jsonify({'success': True, 'data': stocks})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/watchlist/add', methods=['POST'])
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


@app.route('/api/watchlist/remove', methods=['POST'])
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


@app.route('/api/watchlist/check/<code>')
def check_watchlist(code: str):
    """检查股票是否在自选中"""
    try:
        in_watchlist = db.is_in_watchlist(code)
        return jsonify({'success': True, 'in_watchlist': in_watchlist})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/watchlist/clear', methods=['DELETE'])
def clear_watchlist():
    """清空自选列表"""
    try:
        count = db.clear_watchlist()
        return jsonify({
            'success': True,
            'message': f'已清空 {count} 只自选股'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== AI 分析接口 ====================

@app.route('/api/ai/config', methods=['GET'])
def get_ai_config():
    """获取 AI 配置状态"""
    ai_service = get_ai_service()
    return jsonify({
        'success': True,
        'configured': ai_service.is_configured()
    })


@app.route('/api/ai/config', methods=['POST'])
def set_ai_config():
    """设置 AI API Key"""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '')
        
        if not api_key:
            return jsonify({'success': False, 'error': '请提供 API Key'})
        
        # 重新初始化 AI 服务
        ai_service = get_ai_service(api_key)
        
        return jsonify({
            'success': True,
            'configured': ai_service.is_configured()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/ai/analyze', methods=['POST'])
def ai_analyze():
    """AI 分析股票"""
    try:
        ai_service = get_ai_service()
        
        if not ai_service.is_configured():
            return jsonify({
                'success': False,
                'error': 'AI 服务未配置'
            })
        
        # 获取最新的扫描结果
        latest_scan = db.get_latest_scan()
        
        if not latest_scan:
            return jsonify({
                'success': False,
                'error': '没有可分析的扫描数据，请先执行扫描'
            })
        
        # 将板块结果展平为股票列表
        # results 结构: {'板块名': {'change': float, 'stocks': [...]}, ...}
        results_dict = latest_scan.get('results', {})
        all_stocks = []
        
        for sector_name, sector_data in results_dict.items():
            if isinstance(sector_data, dict):
                stocks = sector_data.get('stocks', [])
                for stock in stocks:
                    if isinstance(stock, dict):
                        stock['sector'] = sector_name  # 添加板块信息
                        all_stocks.append(stock)
        
        if not all_stocks:
            return jsonify({
                'success': False,
                'error': '扫描结果为空，请重新执行扫描'
            })
        
        scan_data = {
            'results': all_stocks,
            'scan_time': latest_scan.get('scan_time', '')
        }
        
        # 获取当前时间
        current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')
        
        # 执行 AI 分析
        result = ai_service.analyze_stocks(scan_data, current_time)
        
        # 保存报告到数据库
        if result.get('success'):
            scan_id = latest_scan.get('id') if latest_scan else None
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


# ==================== AI 报告管理接口 ====================

@app.route('/api/ai/reports')
def get_ai_reports():
    """获取 AI 报告列表"""
    try:
        limit = request.args.get('limit', 20, type=int)
        reports = db.get_ai_reports(limit)
        
        # 简化返回数据（列表不返回完整分析内容）
        for report in reports:
            if report.get('analysis'):
                # 只返回前100字作为预览
                report['preview'] = report['analysis'][:100] + '...' if len(report['analysis']) > 100 else report['analysis']
                del report['analysis']
        
        return jsonify({'success': True, 'data': reports})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/ai/reports/<int:report_id>')
def get_ai_report(report_id: int):
    """获取单个 AI 报告详情"""
    try:
        report = db.get_ai_report(report_id)
        if report:
            return jsonify({'success': True, 'data': report})
        return jsonify({'success': False, 'error': '报告不存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/ai/reports/<int:report_id>', methods=['DELETE'])
def delete_ai_report(report_id: int):
    """删除 AI 报告"""
    try:
        if db.delete_ai_report(report_id):
            return jsonify({'success': True, 'message': '删除成功'})
        return jsonify({'success': False, 'error': '报告不存在'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/ai/reports/clear', methods=['DELETE'])
def clear_ai_reports():
    """清空所有 AI 报告"""
    try:
        count = db.delete_all_ai_reports()
        return jsonify({'success': True, 'message': f'已删除 {count} 条报告'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)
