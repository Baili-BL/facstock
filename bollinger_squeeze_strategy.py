#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
布林带收缩策略 - 热点板块筛选器
================================

策略逻辑：
1. 计算布林带上轨与下轨之间的距离（带宽）
2. 计算带宽的5日均值和10日均值
3. 当5日均值 < 10日均值时，表示布林带正在收缩
4. 连续收缩的股票为潜在突破标的

作者: AI Assistant
日期: 2026-01-18
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from tqdm import tqdm
from tabulate import tabulate

try:
    import akshare as ak
except ImportError:
    print("请先安装 akshare: pip install akshare")
    exit(1)


class BollingerSqueezeStrategy:
    """布林带收缩策略"""
    
    def __init__(
        self,
        period: int = 20,           # 布林带周期
        std_dev: float = 2.0,       # 标准差倍数
        ma_short: int = 5,          # 带宽短期均线
        ma_long: int = 10,          # 带宽长期均线
        min_squeeze_days: int = 3,  # 最小连续收缩天数
        volume_ma: int = 5,         # 成交量均线周期
        volume_ratio: float = 1.2,  # 放量倍数阈值
    ):
        """
        初始化策略参数
        
        Args:
            period: 布林带计算周期，默认20
            std_dev: 标准差倍数，默认2.0
            ma_short: 带宽短期均线周期，默认5
            ma_long: 带宽长期均线周期，默认10
            min_squeeze_days: 最小连续收缩天数，默认3
            volume_ma: 成交量均线周期，默认5
            volume_ratio: 放量倍数阈值，默认1.2（当日量/均量 > 1.2为放量）
        """
        self.period = period
        self.std_dev = std_dev
        self.ma_short = ma_short
        self.ma_long = ma_long
        self.min_squeeze_days = min_squeeze_days
        self.volume_ma = volume_ma
        self.volume_ratio = volume_ratio
        
    def calculate_bollinger_bands(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算布林带指标
        
        Args:
            df: 包含 'close' 列的DataFrame
            
        Returns:
            添加了布林带指标的DataFrame
        """
        df = df.copy()
        
        # 中轨 = N日移动平均线
        df['bb_middle'] = df['close'].rolling(window=self.period).mean()
        
        # 标准差
        df['bb_std'] = df['close'].rolling(window=self.period).std()
        
        # 上轨 = 中轨 + K * 标准差
        df['bb_upper'] = df['bb_middle'] + self.std_dev * df['bb_std']
        
        # 下轨 = 中轨 - K * 标准差
        df['bb_lower'] = df['bb_middle'] - self.std_dev * df['bb_std']
        
        # 带宽 = 上轨 - 下轨
        df['bb_width'] = df['bb_upper'] - df['bb_lower']
        
        # 带宽百分比 = (上轨 - 下轨) / 收盘价 * 100
        df['bb_width_pct'] = (df['bb_width'] / df['close']) * 100
        
        return df
    
    def calculate_squeeze_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算布林带收缩信号
        
        Args:
            df: 已计算布林带的DataFrame
            
        Returns:
            添加了收缩信号的DataFrame
        """
        df = df.copy()
        
        # 带宽的5日均值
        df['width_ma_short'] = df['bb_width_pct'].rolling(window=self.ma_short).mean()
        
        # 带宽的10日均值  
        df['width_ma_long'] = df['bb_width_pct'].rolling(window=self.ma_long).mean()
        
        # 收缩信号: 5日均值 < 10日均值
        df['is_squeezing'] = df['width_ma_short'] < df['width_ma_long']
        
        # 计算连续收缩天数
        df['squeeze_streak'] = 0
        streak = 0
        for i in range(len(df)):
            if df['is_squeezing'].iloc[i]:
                streak += 1
            else:
                streak = 0
            df.iloc[i, df.columns.get_loc('squeeze_streak')] = streak
            
        return df
    
    def calculate_volume_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算量能指标
        
        Args:
            df: 包含 'volume', 'close' 列的DataFrame
            
        Returns:
            添加了量能指标的DataFrame
        """
        df = df.copy()
        
        # 成交量均线
        df['volume_ma'] = df['volume'].rolling(window=self.volume_ma).mean()
        
        # 量比 = 当日成交量 / N日平均成交量
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        # 放量信号: 量比 > 阈值
        df['is_volume_up'] = df['volume_ratio'] > self.volume_ratio
        
        # 价格上涨: 收盘价 > 昨日收盘价
        df['is_price_up'] = df['close'] > df['close'].shift(1)
        
        # 量价齐升: 放量 + 价格上涨
        df['is_volume_price_up'] = df['is_volume_up'] & df['is_price_up']
        
        return df
    
    def calculate_trend_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算趋势和动量指标（提高胜率）
        
        包含：MA多头排列、MACD、RSI、ATR分位、价格位置
        """
        df = df.copy()
        
        # ===== 1. 均线系统 =====
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma10'] = df['close'].rolling(window=10).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma60'] = df['close'].rolling(window=60).mean()
        
        # MA多头排列: MA5 > MA10 > MA20
        df['ma_bullish'] = (df['ma5'] > df['ma10']) & (df['ma10'] > df['ma20'])
        
        # MA完全多头: MA5 > MA10 > MA20 > MA60
        df['ma_full_bullish'] = df['ma_bullish'] & (df['ma20'] > df['ma60'])
        
        # 价格站上MA20
        df['above_ma20'] = df['close'] > df['ma20']
        
        # MA20斜率 = (今日MA20 - 5日前MA20) / 5日前MA20 / 5 * 100 (百分比/日)
        df['ma20_slope'] = (df['ma20'] - df['ma20'].shift(5)) / df['ma20'].shift(5) / 5 * 100
        
        # 平稳上行: 斜率 > 0 且 < 0.05
        df['ma20_gentle_up'] = (df['ma20_slope'] > 0) & (df['ma20_slope'] < 0.05)
        
        # ===== 2. 价格位置 =====
        # 价格在布林带中轨上方
        df['above_bb_middle'] = df['close'] > df['bb_middle']
        
        # 价格在布林带位置 (0=下轨, 0.5=中轨, 1=上轨)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # ===== 3. MACD指标 =====
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd_dif'] = exp1 - exp2
        df['macd_dea'] = df['macd_dif'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = (df['macd_dif'] - df['macd_dea']) * 2
        
        # MACD金叉: DIF > DEA
        df['macd_golden'] = df['macd_dif'] > df['macd_dea']
        
        # MACD柱状图转正
        df['macd_hist_positive'] = df['macd_hist'] > 0
        
        # MACD即将金叉: DIF < DEA 但差距在缩小
        df['macd_converging'] = (df['macd_dif'] < df['macd_dea']) & \
                                 (df['macd_dif'] - df['macd_dea'] > df['macd_dif'].shift(1) - df['macd_dea'].shift(1))
        
        # ===== 4. RSI指标 =====
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # RSI中性区间 (40-60)
        df['rsi_neutral'] = (df['rsi'] >= 40) & (df['rsi'] <= 60)
        
        # RSI不超买 (<70)
        df['rsi_not_overbought'] = df['rsi'] < 70
        
        # ===== 5. ATR波动率 =====
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=14).mean()
        
        # ATR百分比
        df['atr_pct'] = df['atr'] / df['close'] * 100
        
        # ATR在近60日的分位数 (越低说明波动越小)
        df['atr_percentile'] = df['atr_pct'].rolling(window=60).apply(
            lambda x: (x.iloc[-1] <= x).sum() / len(x) * 100 if len(x) > 0 else 50,
            raw=False
        )
        
        # 波动率处于低位 (30%分位以下)
        df['low_volatility'] = df['atr_percentile'] < 30
        
        return df
    
    def calculate_composite_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算综合评分（满分100分）
        
        评分维度（收窄+人气权重较高）：
        - 收窄得分 (30分): 收缩天数、带宽收窄程度、低波动率 ⭐核心指标
        - 趋势得分 (20分): MA排列、站上均线
        - 人气得分 (15分): 换手率、市场关注度 🔥新增
        - 动量得分 (15分): MACD状态、RSI区间
        - 位置得分 (10分): 布林带位置、中轨上方
        - 量能得分 (10分): 放量、量价配合
        """
        df = df.copy()
        
        # ===== 收窄得分 (30分) ⭐核心指标 =====
        squeeze_score = 0
        # 连续收缩天数得分 (每天+3分，最高15分)
        squeeze_days_bonus = df['squeeze_streak'].clip(0, 5) * 3
        squeeze_score += squeeze_days_bonus
        # 带宽收窄程度 (收缩比越小得分越高，最高10分)
        squeeze_ratio = df['width_ma_short'] / df['width_ma_long']
        squeeze_ratio_score = squeeze_ratio.apply(
            lambda x: 10 if x < 0.8 else (7 if x < 0.9 else (4 if x < 0.95 else 0)) if pd.notna(x) else 0
        )
        squeeze_score += squeeze_ratio_score
        # 低波动率 +5分
        squeeze_score += df['low_volatility'].astype(int) * 5
        df['squeeze_score'] = squeeze_score.clip(0, 30)
        
        # ===== 趋势得分 (20分) =====
        trend_score = 0
        # MA多头排列 +10分
        trend_score += df['ma_bullish'].astype(int) * 10
        # 完全多头 额外+4分
        trend_score += df['ma_full_bullish'].astype(int) * 4
        # 站上MA20 +6分
        trend_score += df['above_ma20'].astype(int) * 6
        df['trend_score'] = trend_score.clip(0, 20)
        
        # ===== 人气得分 (15分) 🔥新增 =====
        popularity_score = 0
        # 换手率评分 (3%-10%最佳得15分，1%-3%或10%-15%得8分，其他得0分)
        if 'turnover' in df.columns:
            turnover_score = df['turnover'].apply(
                lambda x: 15 if 3 <= x <= 10 else (10 if 2 <= x <= 15 else (5 if 1 <= x <= 20 else 0)) if pd.notna(x) else 0
            )
            popularity_score += turnover_score
        df['popularity_score'] = popularity_score.clip(0, 15)
        
        # ===== 动量得分 (15分) =====
        momentum_score = 0
        # MACD金叉 +6分
        momentum_score += df['macd_golden'].astype(int) * 6
        # MACD柱状图为正 +3分
        momentum_score += df['macd_hist_positive'].astype(int) * 3
        # MACD即将金叉 +3分
        momentum_score += df['macd_converging'].astype(int) * 3
        # RSI在中性区间 +3分
        momentum_score += df['rsi_neutral'].astype(int) * 3
        df['momentum_score'] = momentum_score.clip(0, 15)
        
        # ===== 位置得分 (10分) =====
        position_score = 0
        # 价格在中轨上方 +5分
        position_score += df['above_bb_middle'].astype(int) * 5
        # 布林带位置得分 (0.4-0.7最佳，得5分)
        bb_pos_score = df['bb_position'].apply(
            lambda x: 5 if 0.4 <= x <= 0.7 else (3 if 0.3 <= x <= 0.8 else 0) if pd.notna(x) else 0
        )
        position_score += bb_pos_score
        df['position_score'] = position_score.clip(0, 10)
        
        # ===== 量能得分 (10分) =====
        volume_score = 0
        # 量价齐升 +10分
        volume_score += df['is_volume_price_up'].astype(int) * 10
        # 仅放量 +5分
        volume_score += (~df['is_volume_price_up'] & df['is_volume_up']).astype(int) * 5
        df['volume_score'] = volume_score.clip(0, 10)
        
        # ===== 综合得分 =====
        df['total_score'] = (
            df['squeeze_score'] +     # 收窄30分
            df['trend_score'] +       # 趋势20分
            df['popularity_score'] +  # 人气15分 🔥
            df['momentum_score'] +    # 动量15分
            df['position_score'] +    # 位置10分
            df['volume_score']        # 量能10分
        ).clip(0, 100)
        
        # 评级
        df['grade'] = df['total_score'].apply(
            lambda x: 'S' if x >= 75 else 'A' if x >= 60 else 'B' if x >= 45 else 'C'
        )
        
        # 连续放量天数
        df['volume_up_streak'] = 0
        streak = 0
        for i in range(len(df)):
            if df['is_volume_up'].iloc[i]:
                streak += 1
            else:
                streak = 0
            df.iloc[i, df.columns.get_loc('volume_up_streak')] = streak
        
        return df
    
    def analyze_stock(self, stock_code: str, stock_name: str = "") -> Optional[Dict]:
        """
        分析单只股票的布林带收缩情况
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            
        Returns:
            分析结果字典，如果不符合条件返回None
        """
        try:
            # 获取股票历史数据 (最近60个交易日)
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=(datetime.now() - timedelta(days=120)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d"),
                adjust="qfq"  # 前复权
            )
            
            if df is None or len(df) < self.period + self.ma_long:
                return None
                
            # 重命名列
            df = df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '涨跌幅': 'pct_change',
                '涨跌额': 'change',
                '换手率': 'turnover'
            })
            
            # 计算布林带
            df = self.calculate_bollinger_bands(df)
            
            # 计算收缩信号
            df = self.calculate_squeeze_signal(df)
            
            # 计算量能指标
            df = self.calculate_volume_signal(df)
            
            # 计算趋势和动量指标
            df = self.calculate_trend_indicators(df)
            
            # 计算综合评分
            df = self.calculate_composite_score(df)
            
            # 获取最新数据
            latest = df.iloc[-1]
            
            # 检查是否满足收缩条件
            if latest['squeeze_streak'] >= self.min_squeeze_days:
                return {
                    'code': stock_code,
                    'name': stock_name,
                    'close': round(latest['close'], 2),
                    'bb_upper': round(latest['bb_upper'], 2),
                    'bb_lower': round(latest['bb_lower'], 2),
                    'bb_width_pct': round(latest['bb_width_pct'], 2),
                    'width_ma5': round(latest['width_ma_short'], 2),
                    'width_ma10': round(latest['width_ma_long'], 2),
                    'squeeze_days': int(latest['squeeze_streak']),
                    'squeeze_ratio': round(latest['width_ma_short'] / latest['width_ma_long'] * 100, 1),
                    'pct_change': round(latest.get('pct_change', 0), 2) if 'pct_change' in latest else 0,
                    'turnover': round(latest.get('turnover', 0), 2) if 'turnover' in latest else 0,
                    # 量能指标
                    'volume_ratio': round(latest['volume_ratio'], 2) if not pd.isna(latest['volume_ratio']) else 0,
                    'is_volume_up': bool(latest['is_volume_up']),
                    'is_price_up': bool(latest['is_price_up']),
                    'is_volume_price_up': bool(latest['is_volume_price_up']),
                    'volume_up_streak': int(latest['volume_up_streak']),
                    # 趋势指标
                    'ma_bullish': bool(latest['ma_bullish']) if pd.notna(latest['ma_bullish']) else False,
                    'ma_full_bullish': bool(latest['ma_full_bullish']) if pd.notna(latest['ma_full_bullish']) else False,
                    'above_ma20': bool(latest['above_ma20']) if pd.notna(latest['above_ma20']) else False,
                    'ma20_slope': round(latest['ma20_slope'], 4) if pd.notna(latest['ma20_slope']) else 0,
                    'ma20_gentle_up': bool(latest['ma20_gentle_up']) if pd.notna(latest['ma20_gentle_up']) else False,
                    'above_bb_middle': bool(latest['above_bb_middle']) if pd.notna(latest['above_bb_middle']) else False,
                    'bb_position': round(latest['bb_position'] * 100, 1) if pd.notna(latest['bb_position']) else 50,
                    # MACD指标
                    'macd_golden': bool(latest['macd_golden']) if pd.notna(latest['macd_golden']) else False,
                    'macd_hist_positive': bool(latest['macd_hist_positive']) if pd.notna(latest['macd_hist_positive']) else False,
                    # RSI
                    'rsi': round(latest['rsi'], 1) if pd.notna(latest['rsi']) else 50,
                    'rsi_neutral': bool(latest['rsi_neutral']) if pd.notna(latest['rsi_neutral']) else False,
                    # ATR波动率
                    'atr_percentile': round(latest['atr_percentile'], 1) if pd.notna(latest['atr_percentile']) else 50,
                    'low_volatility': bool(latest['low_volatility']) if pd.notna(latest['low_volatility']) else False,
                    # 综合评分
                    'squeeze_score': int(latest['squeeze_score']) if pd.notna(latest['squeeze_score']) else 0,
                    'trend_score': int(latest['trend_score']) if pd.notna(latest['trend_score']) else 0,
                    'popularity_score': int(latest['popularity_score']) if pd.notna(latest['popularity_score']) else 0,
                    'momentum_score': int(latest['momentum_score']) if pd.notna(latest['momentum_score']) else 0,
                    'position_score': int(latest['position_score']) if pd.notna(latest['position_score']) else 0,
                    'volume_score': int(latest['volume_score']) if pd.notna(latest['volume_score']) else 0,
                    'total_score': int(latest['total_score']) if pd.notna(latest['total_score']) else 0,
                    'grade': latest['grade'] if pd.notna(latest['grade']) else 'C',
                }
            
            return None
            
        except Exception as e:
            # 打印错误信息以便调试
            print(f"[ERROR] 分析股票 {stock_code} 出错: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None


class HotSectorScanner:
    """热点板块扫描器"""
    
    def __init__(self, strategy: BollingerSqueezeStrategy):
        self.strategy = strategy
        
    def get_hot_sectors(self, top_n: int = 10) -> pd.DataFrame:
        """
        获取热点板块
        
        Args:
            top_n: 返回前N个热点板块
            
        Returns:
            热点板块DataFrame
        """
        try:
            # 获取板块涨幅排名
            df = ak.stock_board_industry_name_em()
            if df is not None and len(df) > 0:
                # 按涨跌幅排序
                df = df.sort_values(by='涨跌幅', ascending=False)
                return df.head(top_n)
        except Exception as e:
            print(f"获取热点板块失败: {e}")
            
        return pd.DataFrame()
    
    def get_sector_stocks(self, sector_name: str) -> List[Dict]:
        """
        获取板块成分股（含市值等信息）
        
        Args:
            sector_name: 板块名称
            
        Returns:
            成分股列表 [{'code': ..., 'name': ..., 'market_cap': ..., ...}, ...]
        """
        try:
            df = ak.stock_board_industry_cons_em(symbol=sector_name)
            if df is not None and len(df) > 0:
                stocks = []
                for _, row in df.iterrows():
                    stock_info = {
                        'code': row['代码'],
                        'name': row['名称'],
                        'market_cap': row.get('总市值', 0) or 0,
                        'circulating_cap': row.get('流通市值', 0) or 0,
                        'sector_change': row.get('涨跌幅', 0) or 0,
                    }
                    stocks.append(stock_info)
                
                # 按市值排序，标记中军（前3名）
                stocks_sorted = sorted(stocks, key=lambda x: x['market_cap'], reverse=True)
                for i, stock in enumerate(stocks_sorted):
                    if i < 3:
                        stock['is_leader'] = True  # 中军标记
                        stock['leader_rank'] = i + 1
                    else:
                        stock['is_leader'] = False
                        stock['leader_rank'] = 0
                
                return stocks
        except Exception as e:
            pass
            
        return []
    
    def scan_hot_sectors(self, top_sectors: int = 5, progress: bool = True) -> Dict[str, List[Dict]]:
        """
        扫描热点板块中的布林带收缩股票
        
        Args:
            top_sectors: 扫描前N个热点板块
            progress: 是否显示进度条
            
        Returns:
            {板块名称: [股票分析结果, ...], ...}
        """
        results = {}
        
        print("\n" + "=" * 60)
        print("🔥 布林带收缩策略 - 热点板块扫描")
        print("=" * 60)
        
        # 获取热点板块
        hot_sectors = self.get_hot_sectors(top_sectors)
        if hot_sectors.empty:
            print("❌ 无法获取热点板块数据")
            return results
            
        print(f"\n📊 今日热点板块 TOP {top_sectors}:")
        print("-" * 40)
        for idx, row in hot_sectors.iterrows():
            print(f"  {row['板块名称']}: {row['涨跌幅']:+.2f}%")
        print()
        
        # 遍历热点板块
        for _, sector in hot_sectors.iterrows():
            sector_name = sector['板块名称']
            print(f"\n🔍 扫描板块: {sector_name}")
            
            # 获取成分股
            stocks = self.get_sector_stocks(sector_name)
            if not stocks:
                print(f"  ⚠️ 无法获取 {sector_name} 成分股")
                continue
                
            sector_results = []
            
            # 扫描成分股
            iterator = tqdm(stocks, desc=f"  分析中", leave=False) if progress else stocks
            for stock_info in iterator:
                code = stock_info['code']
                name = stock_info['name']
                result = self.strategy.analyze_stock(code, name)
                if result:
                    # 添加标签信息
                    result['is_leader'] = stock_info.get('is_leader', False)
                    result['leader_rank'] = stock_info.get('leader_rank', 0)
                    result['market_cap'] = stock_info.get('market_cap', 0)
                    
                    # 生成标签列表
                    tags = []
                    if result['is_leader']:
                        tags.append(f"中军#{result['leader_rank']}")
                    if result.get('is_volume_price_up'):
                        tags.append("量价齐升")
                    elif result.get('is_volume_up'):
                        tags.append("放量")
                    if result.get('pct_change', 0) >= 5:
                        tags.append("先锋")
                    if result.get('turnover', 0) >= 10:
                        tags.append("人气")
                    # MA20平稳上行: 斜率 > 0 且 < 0.05
                    if result.get('ma20_gentle_up'):
                        tags.append("平稳上行")
                    result['tags'] = tags
                    
                    sector_results.append(result)
                    
            if sector_results:
                # 按综合评分从高到低排序
                sector_results.sort(key=lambda x: x.get('total_score', 0), reverse=True)
                results[sector_name] = sector_results
                print(f"  ✅ 发现 {len(sector_results)} 只收缩股票")
            else:
                print(f"  ⭕ 未发现符合条件的股票")
                
        return results
    
    def print_results(self, results: Dict[str, List[Dict]]):
        """打印扫描结果"""
        
        print("\n" + "=" * 80)
        print("📈 布林带收缩股票筛选结果")
        print("=" * 80)
        
        if not results:
            print("\n❌ 未找到符合条件的股票")
            return
            
        total_stocks = sum(len(v) for v in results.values())
        print(f"\n共找到 {total_stocks} 只符合条件的股票\n")
        
        for sector_name, stocks in results.items():
            print(f"\n【{sector_name}】- {len(stocks)} 只")
            print("-" * 80)
            
            # 准备表格数据
            table_data = []
            for stock in stocks:
                table_data.append([
                    stock['code'],
                    stock['name'],
                    f"{stock['close']:.2f}",
                    f"{stock['bb_width_pct']:.1f}%",
                    f"{stock['width_ma5']:.1f}%",
                    f"{stock['width_ma10']:.1f}%",
                    f"{stock['squeeze_ratio']:.1f}%",
                    stock['squeeze_days'],
                    f"{stock['pct_change']:+.2f}%",
                ])
                
            headers = ['代码', '名称', '收盘价', '带宽%', 'MA5', 'MA10', '收缩比', '收缩天数', '涨跌幅']
            print(tabulate(table_data, headers=headers, tablefmt='simple'))
            
        # 打印策略说明
        print("\n" + "-" * 80)
        print("📝 策略说明:")
        print(f"   • 布林带周期: {self.strategy.period}日")
        print(f"   • 标准差倍数: {self.strategy.std_dev}")
        print(f"   • 带宽MA短期: {self.strategy.ma_short}日")
        print(f"   • 带宽MA长期: {self.strategy.ma_long}日")
        print(f"   • 最小收缩天数: {self.strategy.min_squeeze_days}天")
        print("   • 收缩信号: MA5 < MA10 (短期带宽均值 < 长期带宽均值)")
        print("   • 收缩比: MA5/MA10 * 100% (越小表示收缩越明显)")
        print("-" * 80)


def scan_all_stocks(strategy: BollingerSqueezeStrategy, limit: int = None) -> List[Dict]:
    """
    扫描全市场A股
    
    Args:
        strategy: 策略实例
        limit: 限制扫描数量（用于测试）
        
    Returns:
        符合条件的股票列表
    """
    print("\n" + "=" * 60)
    print("🔍 布林带收缩策略 - 全市场扫描")
    print("=" * 60)
    
    try:
        # 获取A股列表
        stock_list = ak.stock_zh_a_spot_em()
        if stock_list is None or stock_list.empty:
            print("❌ 无法获取股票列表")
            return []
            
        stocks = list(zip(stock_list['代码'].tolist(), stock_list['名称'].tolist()))
        
        if limit:
            stocks = stocks[:limit]
            
        print(f"📊 共 {len(stocks)} 只股票待扫描\n")
        
        results = []
        for code, name in tqdm(stocks, desc="扫描进度"):
            result = strategy.analyze_stock(code, name)
            if result:
                results.append(result)
                
        # 按综合评分从高到低排序
        results.sort(key=lambda x: x.get('total_score', 0), reverse=True)
        
        return results
        
    except Exception as e:
        print(f"❌ 扫描失败: {e}")
        return []


def print_all_results(results: List[Dict], strategy: BollingerSqueezeStrategy):
    """打印全市场扫描结果"""
    
    print("\n" + "=" * 80)
    print("📈 布林带收缩股票筛选结果 - 全市场")
    print("=" * 80)
    
    if not results:
        print("\n❌ 未找到符合条件的股票")
        return
        
    print(f"\n共找到 {len(results)} 只符合条件的股票\n")
    print("-" * 80)
    
    # 准备表格数据
    table_data = []
    for stock in results[:50]:  # 只显示前50只
        table_data.append([
            stock['code'],
            stock['name'],
            f"{stock['close']:.2f}",
            f"{stock['bb_width_pct']:.1f}%",
            f"{stock['width_ma5']:.1f}%",
            f"{stock['width_ma10']:.1f}%",
            f"{stock['squeeze_ratio']:.1f}%",
            stock['squeeze_days'],
            f"{stock['pct_change']:+.2f}%",
        ])
        
    headers = ['代码', '名称', '收盘价', '带宽%', 'MA5', 'MA10', '收缩比', '收缩天数', '涨跌幅']
    print(tabulate(table_data, headers=headers, tablefmt='simple'))
    
    if len(results) > 50:
        print(f"\n... 还有 {len(results) - 50} 只股票未显示")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='布林带收缩策略 - 股票筛选器')
    parser.add_argument('--mode', type=str, default='hot', choices=['hot', 'all'],
                        help='扫描模式: hot=热点板块, all=全市场')
    parser.add_argument('--sectors', type=int, default=5,
                        help='热点板块数量 (默认: 5)')
    parser.add_argument('--period', type=int, default=20,
                        help='布林带周期 (默认: 20)')
    parser.add_argument('--std', type=float, default=2.0,
                        help='标准差倍数 (默认: 2.0)')
    parser.add_argument('--ma-short', type=int, default=5,
                        help='带宽短期均线 (默认: 5)')
    parser.add_argument('--ma-long', type=int, default=10,
                        help='带宽长期均线 (默认: 10)')
    parser.add_argument('--min-days', type=int, default=3,
                        help='最小连续收缩天数 (默认: 3)')
    parser.add_argument('--limit', type=int, default=None,
                        help='限制扫描数量（测试用）')
    
    args = parser.parse_args()
    
    # 创建策略实例
    strategy = BollingerSqueezeStrategy(
        period=args.period,
        std_dev=args.std,
        ma_short=args.ma_short,
        ma_long=args.ma_long,
        min_squeeze_days=args.min_days,
    )
    
    print("\n" + "🎯" * 30)
    print("       布林带收缩策略 - 股票筛选器")
    print("🎯" * 30)
    print(f"\n⏰ 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if args.mode == 'hot':
        # 热点板块扫描
        scanner = HotSectorScanner(strategy)
        results = scanner.scan_hot_sectors(top_sectors=args.sectors)
        scanner.print_results(results)
    else:
        # 全市场扫描
        results = scan_all_stocks(strategy, limit=args.limit)
        print_all_results(results, strategy)
        
    print("\n✅ 扫描完成!")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    main()
