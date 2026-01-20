#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
布林带收缩策略 - Flask Web 应用
"""

from flask import Flask, render_template, jsonify, request
from bollinger_squeeze_strategy import BollingerSqueezeStrategy, HotSectorScanner
import akshare as ak
import pandas as pd
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

# 全局变量存储扫描状态和结果
scan_status = {
    'is_scanning': False,
    'progress': 0,
    'current_sector': '',
    'results': {},
    'hot_sectors': [],
    'last_update': None,
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
        df = ak.stock_board_industry_name_em()
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
    
    # 重置状态
    scan_status = {
        'is_scanning': True,
        'progress': 0,
        'current_sector': '准备中...',
        'results': {},
        'hot_sectors': [],
        'last_update': None,
        'error': None
    }
    
    # 在后台线程执行扫描
    thread = threading.Thread(
        target=run_scan,
        args=(top_sectors, min_days, period)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'message': '扫描已开始'})


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


def run_scan(top_sectors: int, min_days: int, period: int):
    """执行扫描任务（并发版本）"""
    global scan_status
    
    # 并发线程数
    MAX_WORKERS = 10
    
    try:
        print(f"[DEBUG] 开始扫描: top_sectors={top_sectors}, min_days={min_days}, period={period}")
        
        strategy = BollingerSqueezeStrategy(
            period=period,
            min_squeeze_days=min_days
        )
        
        # 获取热点板块
        try:
            print("[DEBUG] 正在获取热点板块...")
            df = ak.stock_board_industry_name_em()
            print(f"[DEBUG] 获取到板块数据: {len(df) if df is not None else 0} 条")
            
            if df is not None and len(df) > 0:
                df = df.sort_values(by='涨跌幅', ascending=False)
                hot_sectors_df = df.head(top_sectors)
                
                scan_status['hot_sectors'] = [
                    {'name': row['板块名称'], 'change': round(row['涨跌幅'], 2)}
                    for _, row in hot_sectors_df.iterrows()
                ]
                print(f"[DEBUG] 热点板块: {[s['name'] for s in scan_status['hot_sectors']]}")
            else:
                scan_status['error'] = '无法获取热点板块'
                scan_status['is_scanning'] = False
                print("[DEBUG] 无法获取热点板块数据")
                return
        except Exception as e:
            scan_status['error'] = f'获取热点板块失败: {str(e)}'
            scan_status['is_scanning'] = False
            print(f"[DEBUG] 获取热点板块异常: {e}")
            return
        
        total_sectors = len(scan_status['hot_sectors'])
        
        for i, sector in enumerate(scan_status['hot_sectors']):
            sector_name = sector['name']
            scan_status['current_sector'] = f"{sector_name} (并发分析中...)"
            scan_status['progress'] = int((i / total_sectors) * 100)
            
            print(f"[DEBUG] 扫描板块 {i+1}/{total_sectors}: {sector_name}")
            
            try:
                # 获取成分股（含市值信息）
                stocks_df = ak.stock_board_industry_cons_em(symbol=sector_name)
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
                    scan_status['results'][sector_name] = {
                        'change': sector['change'],
                        'stocks': sector_results
                    }
                    
            except Exception as e:
                print(f"[DEBUG] 板块 {sector_name} 扫描异常: {e}")
                continue
        
        scan_status['progress'] = 100
        scan_status['current_sector'] = '扫描完成'
        scan_status['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception as e:
        scan_status['error'] = str(e)
    finally:
        scan_status['is_scanning'] = False


@app.route('/api/scan/status')
def get_scan_status():
    """获取扫描状态"""
    return jsonify({
        'is_scanning': scan_status['is_scanning'],
        'progress': scan_status['progress'],
        'current_sector': scan_status['current_sector'],
        'error': scan_status['error']
    })


@app.route('/api/scan/results')
def get_scan_results():
    """获取扫描结果"""
    return jsonify({
        'success': True,
        'results': scan_status['results'],
        'hot_sectors': scan_status['hot_sectors'],
        'last_update': scan_status['last_update']
    })


@app.route('/api/stock/<code>')
def get_stock_detail(code: str):
    """获取单只股票详情"""
    try:
        from datetime import timedelta
        
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=(datetime.now() - timedelta(days=120)).strftime("%Y%m%d"),
            end_date=datetime.now().strftime("%Y%m%d"),
            adjust="qfq"
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
