#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
布林带收缩策略 - Flask Web 应用
"""

from flask import Flask, render_template, jsonify, request
from bollinger_squeeze_strategy import BollingerSqueezeStrategy, HotSectorScanner, retry_request
import akshare as ak
import pandas as pd
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入数据库模块
import database as db

app = Flask(__name__)

# 全局变量存储当前扫描状态（用于实时进度查询）
scan_status = {
    'is_scanning': False,
    'scan_id': None,
    'progress': 0,
    'current_sector': '',
    'error': None
}


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/hot-sectors')
def get_hot_sectors():
    """获取热点板块列表"""
    try:
        df = retry_request(ak.stock_board_industry_name_em, max_retries=3, delay=1.0)
        if df is not None and len(df) > 0:
            df = df.sort_values(by='涨跌幅', ascending=False)
            sectors = []
            for _, row in df.head(20).iterrows():
                sectors.append({
                    'name': row['板块名称'],
                    'change': round(row['涨跌幅'], 2),
                    'leader': row.get('领涨股票', ''),
                    'leader_change': round(row.get('领涨股票-涨跌幅', 0), 2)
                })
            return jsonify({'success': True, 'data': sectors})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
    return jsonify({'success': False, 'error': '无法获取数据'})


@app.route('/api/scan/start', methods=['POST'])
def start_scan():
    """开始扫描"""
    global scan_status
    
    if scan_status['is_scanning']:
        return jsonify({'success': False, 'error': '扫描正在进行中'})
    
    data = request.json or {}
    top_sectors = data.get('sectors', 5)
    min_days = data.get('min_days', 3)
    period = data.get('period', 20)
    
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
        'error': None
    }
    
    # 在后台线程执行扫描
    thread = threading.Thread(
        target=run_scan,
        args=(scan_id, top_sectors, min_days, period)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'message': '扫描已开始', 'scan_id': scan_id})


def analyze_single_stock(strategy, stock_info):
    """分析单只股票（用于并发）"""
    try:
        code = stock_info['code']
        name = stock_info['name']
        result = strategy.analyze_stock(code, name)
        if result:
            # print(f"[DEBUG] 股票 {code} {name} 符合条件")
            # 添加标签信息
            result['is_leader'] = stock_info.get('is_leader', False)
            result['leader_rank'] = stock_info.get('leader_rank', 0)
            result['market_cap'] = stock_info.get('market_cap', 0)
            
            # 生成标签列表
            tags = []
            
            # 评级标签 (最重要)
            grade = result.get('grade', 'C')
            if grade == 'S':
                tags.append("⭐S级")
            elif grade == 'A':
                tags.append("🅰️A级")
            
            # 中军标签
            if result['is_leader']:
                tags.append(f"中军#{result['leader_rank']}")
            
            # CMF 资金流标签 💰
            if result.get('cmf_strong_bullish'):
                tags.append("💰强势流入")
            elif result.get('cmf_bullish') and result.get('cmf_rising'):
                tags.append("💰资金流入")
            elif result.get('cmf_bullish'):
                tags.append("资金净流入")
            
            # RSV 标签
            if result.get('rsv_recovering'):
                tags.append("🔄超卖回升")
            elif result.get('rsv_golden'):
                rsv_val = result.get('rsv', 50)
                if rsv_val >= 65:
                    tags.append(f"RSV强势")
                else:
                    tags.append(f"RSV健康")
            
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
                tags.append("🔥人气旺")
            elif turnover > 10:
                tags.append("⚡超人气")
            elif 1 <= turnover < 3:
                tags.append("📊有关注")
            
            # 其他标签
            if result.get('pct_change', 0) >= 5:
                tags.append("先锋")
            
            result['tags'] = tags
            
            return result
    except Exception:
        pass
    return None


def run_scan(scan_id: int, top_sectors: int, min_days: int, period: int):
    """执行扫描任务（并发版本），结果保存到数据库"""
    global scan_status
    
    # 并发线程数
    MAX_WORKERS = 10
    
    # 用于临时存储热点板块信息
    hot_sectors_list = []
    
    try:
        print(f"[DEBUG] 开始扫描: scan_id={scan_id}, top_sectors={top_sectors}, min_days={min_days}, period={period}")
        
        strategy = BollingerSqueezeStrategy(
            period=period,
            min_squeeze_days=min_days
        )
        
        # 获取热点板块
        try:
            print("[DEBUG] 正在获取热点板块...")
            df = retry_request(ak.stock_board_industry_name_em, max_retries=3, delay=1.0)
            print(f"[DEBUG] 获取到板块数据: {len(df) if df is not None else 0} 条")
            
            if df is not None and len(df) > 0:
                df = df.sort_values(by='涨跌幅', ascending=False)
                hot_sectors_df = df.head(top_sectors)
                
                hot_sectors_list = [
                    {'name': row['板块名称'], 'change': round(row['涨跌幅'], 2)}
                    for _, row in hot_sectors_df.iterrows()
                ]
                
                # 保存热点板块到数据库
                db.save_hot_sectors(scan_id, hot_sectors_list)
                
                print(f"[DEBUG] 热点板块: {[s['name'] for s in hot_sectors_list]}")
            else:
                error_msg = '无法获取热点板块'
                scan_status['error'] = error_msg
                scan_status['is_scanning'] = False
                db.update_scan_status(scan_id, 'error', error_msg)
                print("[DEBUG] 无法获取热点板块数据")
                return
        except Exception as e:
            error_msg = f'获取热点板块失败: {str(e)}'
            scan_status['error'] = error_msg
            scan_status['is_scanning'] = False
            db.update_scan_status(scan_id, 'error', error_msg)
            print(f"[DEBUG] 获取热点板块异常: {e}")
            return
        
        total_sectors = len(hot_sectors_list)
        
        for i, sector in enumerate(hot_sectors_list):
            sector_name = sector['name']
            progress = int((i / total_sectors) * 100)
            
            scan_status['current_sector'] = f"{sector_name} (并发分析中...)"
            scan_status['progress'] = progress
            
            # 更新数据库进度
            db.update_scan_progress(scan_id, progress, scan_status['current_sector'])
            
            print(f"[DEBUG] 扫描板块 {i+1}/{total_sectors}: {sector_name}")
            
            try:
                # 获取成分股（含市值信息），带重试机制
                stocks_df = retry_request(
                    lambda sn=sector_name: ak.stock_board_industry_cons_em(symbol=sn),
                    max_retries=3,
                    delay=1.0
                )
                if stocks_df is None or stocks_df.empty:
                    print(f"[DEBUG] 板块 {sector_name} 无成分股数据")
                    continue
                
                print(f"[DEBUG] 板块 {sector_name} 有 {len(stocks_df)} 只成分股")
                
                # 构建股票信息列表
                stocks = []
                for _, row in stocks_df.iterrows():
                    stock_info = {
                        'code': row['代码'],
                        'name': row['名称'],
                        'market_cap': row.get('总市值', 0) or 0,
                    }
                    stocks.append(stock_info)
                
                # 按市值排序，标记中军（前3名）
                stocks_sorted = sorted(stocks, key=lambda x: x['market_cap'], reverse=True)
                for idx, stock in enumerate(stocks_sorted):
                    stock['is_leader'] = idx < 3
                    stock['leader_rank'] = idx + 1 if idx < 3 else 0
                
                # 使用线程池并发分析股票
                sector_results = []
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    # 提交所有任务
                    future_to_stock = {
                        executor.submit(analyze_single_stock, strategy, stock_info): stock_info
                        for stock_info in stocks
                    }
                    
                    # 收集结果
                    completed = 0
                    total_stocks = len(stocks)
                    for future in as_completed(future_to_stock):
                        completed += 1
                        # 更新进度显示
                        sector_progress = int((i + completed / total_stocks) / total_sectors * 100)
                        scan_status['progress'] = min(sector_progress, 99)
                        scan_status['current_sector'] = f"{sector_name} ({completed}/{total_stocks})"
                        
                        result = future.result()
                        if result:
                            sector_results.append(result)
                
                print(f"[DEBUG] 板块 {sector_name} 分析完成，符合条件: {len(sector_results)} 只")
                
                if sector_results:
                    # 按综合评分从高到低排序
                    sector_results.sort(key=lambda x: x.get('total_score', 0), reverse=True)
                    
                    # 保存到数据库
                    db.save_sector_result(scan_id, sector_name, sector['change'], sector_results)
                    
            except Exception as e:
                print(f"[DEBUG] 板块 {sector_name} 扫描异常: {e}")
                continue
        
        scan_status['progress'] = 100
        scan_status['current_sector'] = '扫描完成'
        
        # 更新数据库状态为完成
        db.update_scan_status(scan_id, 'completed')
        
    except Exception as e:
        scan_status['error'] = str(e)
        db.update_scan_status(scan_id, 'error', str(e))
    finally:
        scan_status['is_scanning'] = False


@app.route('/api/scan/status')
def get_scan_status():
    """获取扫描状态"""
    return jsonify({
        'is_scanning': scan_status['is_scanning'],
        'scan_id': scan_status.get('scan_id'),
        'progress': scan_status['progress'],
        'current_sector': scan_status['current_sector'],
        'error': scan_status['error']
    })


@app.route('/api/scan/results')
def get_scan_results():
    """获取扫描结果（最新一次完成的扫描）"""
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
    """获取历史扫描记录列表"""
    limit = request.args.get('limit', 20, type=int)
    records = db.get_scan_list(limit=limit)
    return jsonify({
        'success': True,
        'data': records
    })


@app.route('/api/scan/<int:scan_id>', methods=['GET'])
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


@app.route('/api/stock/<code>')
def get_stock_detail(code: str):
    """获取单只股票详情"""
    try:
        from datetime import timedelta
        
        # 带重试机制获取股票历史数据
        df = retry_request(
            lambda: ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=(datetime.now() - timedelta(days=120)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d"),
                adjust="qfq"
            ),
            max_retries=3,
            delay=0.5
        )
        
        if df is None or df.empty:
            return jsonify({'success': False, 'error': '无法获取数据'})
        
        # 重命名列
        df = df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '涨跌幅': 'pct_change'
        })
        
        strategy = BollingerSqueezeStrategy()
        df = strategy.calculate_bollinger_bands(df)
        df = strategy.calculate_squeeze_signal(df)
        
        # 移除包含NaN的行（布林带计算前期数据）
        df = df.dropna(subset=['bb_upper', 'bb_lower', 'bb_middle', 'width_ma_short', 'width_ma_long'])
        
        # 取最近60天数据
        df = df.tail(60)
        
        # 转换为列表，处理可能的NaN值
        def safe_list(series):
            return [None if pd.isna(x) else float(x) for x in series]
        
        # 生成蜡烛图数据 (Lightweight Charts格式)
        candles = []
        for _, row in df.iterrows():
            candles.append({
                'time': row['date'],
                'open': float(row['open']) if pd.notna(row['open']) else None,
                'high': float(row['high']) if pd.notna(row['high']) else None,
                'low': float(row['low']) if pd.notna(row['low']) else None,
                'close': float(row['close']) if pd.notna(row['close']) else None,
            })
        
        # 生成成交量数据（红涨绿跌，与蜡烛图一致）
        volume_data = []
        for _, row in df.iterrows():
            # 涨：close >= open -> 红色，跌：close < open -> 绿色
            color = '#ef5350' if row['close'] >= row['open'] else '#26a69a'
            volume_data.append({
                'time': row['date'],
                'value': float(row['volume']) if pd.notna(row['volume']) else 0,
                'color': color
            })
        
        # 布林带数据
        bb_upper_data = [{'time': row['date'], 'value': float(row['bb_upper'])} for _, row in df.iterrows() if pd.notna(row['bb_upper'])]
        bb_middle_data = [{'time': row['date'], 'value': float(row['bb_middle'])} for _, row in df.iterrows() if pd.notna(row['bb_middle'])]
        bb_lower_data = [{'time': row['date'], 'value': float(row['bb_lower'])} for _, row in df.iterrows() if pd.notna(row['bb_lower'])]
        
        data = {
            'candles': candles,
            'volumes': volume_data,
            'bb_upper': bb_upper_data,
            'bb_middle': bb_middle_data,
            'bb_lower': bb_lower_data,
            'bb_width': safe_list(df['bb_width_pct']),
            'width_ma5': safe_list(df['width_ma_short']),
            'width_ma10': safe_list(df['width_ma_long']),
            'dates': df['date'].astype(str).tolist(),
        }
        
        return jsonify({'success': True, 'data': data})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
