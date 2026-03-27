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
日期: 2026-01-18
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from tqdm import tqdm
from tabulate import tabulate
import time
import logging

# 导入重试工具
from utils.retry import retry_request

# Lazy import of akshare to avoid py_mini_racer crash on import
def _get_ak():
    import akshare as _ak
    return _ak

# 配置日志
logger = logging.getLogger(__name__)


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
        
        计算布林带的中轨、上轨、下轨和带宽指标。
        
        Args:
            df: 包含 'close' 列的DataFrame，数据长度应 >= period
            
        Returns:
            添加了以下列的DataFrame:
            - bb_middle: 中轨（N日移动平均线）
            - bb_std: N日标准差
            - bb_upper: 上轨（中轨 + K * 标准差）
            - bb_lower: 下轨（中轨 - K * 标准差）
            - bb_width: 带宽（上轨 - 下轨）
            - bb_width_pct: 带宽百分比（带宽 / 收盘价 * 100）
            
        Raises:
            ValueError: 当 df 为空或不包含 'close' 列时
            
        Note:
            - 前 period-1 行的布林带值为 NaN（数据不足）
            - 布林带计算公式:
              - bb_middle = close 的 period 日移动平均
              - bb_upper = bb_middle + std_dev × 标准差
              - bb_lower = bb_middle - std_dev × 标准差
        """
        # 输入验证
        if df is None or len(df) == 0:
            raise ValueError("输入数据不能为空")
        
        if 'close' not in df.columns:
            raise ValueError("DataFrame 必须包含 'close' 列")
        
        df = df.copy()
        
        # 数据不足时记录警告
        if len(df) < self.period:
            logger.warning(f"数据长度 {len(df)} 小于布林带周期 {self.period}，结果将全为 NaN")
        
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
        
        计算带宽的短期和长期均值，判断是否处于收缩状态，并统计连续收缩天数。
        
        Args:
            df: 已计算布林带的DataFrame，必须包含 'bb_width_pct' 列
            
        Returns:
            添加了以下列的DataFrame:
            - width_ma_short: 带宽的短期均值（默认5日）
            - width_ma_long: 带宽的长期均值（默认10日）
            - is_squeezing: 是否处于收缩状态（短期均值 < 长期均值）
            - squeeze_streak: 连续收缩天数
            
        Raises:
            ValueError: 当 df 为空或不包含 'bb_width_pct' 列时
            
        Note:
            收缩信号判断: 当 width_ma_short < width_ma_long 时，表示布林带正在收缩
        """
        # 输入验证
        if df is None or len(df) == 0:
            raise ValueError("输入数据不能为空")
        
        if 'bb_width_pct' not in df.columns:
            raise ValueError("DataFrame 必须包含 'bb_width_pct' 列，请先调用 calculate_bollinger_bands")
        
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
        bb_range = df['bb_upper'] - df['bb_lower']
        bb_range = bb_range.replace(0, np.nan)
        df['bb_position'] = (df['close'] - df['bb_lower']) / bb_range
        
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
        
        # ===== 6. CMF 蔡金资金流量指标 (20周期) =====
        # Money Flow Multiplier = ((Close - Low) - (High - Close)) / (High - Low)
        # 当 High == Low 时避免除零
        mfm_denominator = df['high'] - df['low']
        mfm_denominator = mfm_denominator.replace(0, np.nan)
        df['mf_multiplier'] = ((df['close'] - df['low']) - (df['high'] - df['close'])) / mfm_denominator
        df['mf_multiplier'] = df['mf_multiplier'].fillna(0)
        
        # Money Flow Volume = Money Flow Multiplier * Volume
        df['mf_volume'] = df['mf_multiplier'] * df['volume']
        
        # CMF = Sum(Money Flow Volume, 20) / Sum(Volume, 20)
        cmf_period = 20
        df['cmf'] = df['mf_volume'].rolling(window=cmf_period).sum() / df['volume'].rolling(window=cmf_period).sum()
        
        # CMF 信号判断
        # CMF > 0.1 表示强势买入压力
        # CMF > 0 表示买入压力
        # CMF < -0.1 表示强势卖出压力
        df['cmf_bullish'] = df['cmf'] > 0  # 资金流入
        df['cmf_strong_bullish'] = df['cmf'] > 0.1  # 强势资金流入
        df['cmf_bearish'] = df['cmf'] < 0  # 资金流出
        
        # CMF 趋势：CMF 上升中
        df['cmf_rising'] = df['cmf'] > df['cmf'].shift(1)
        
        # ===== 7. RSV 原始随机值 (KDJ的K值前身，9周期) =====
        rsv_period = 9
        # RSV = (Close - Lowest Low) / (Highest High - Lowest Low) * 100
        lowest_low = df['low'].rolling(window=rsv_period).min()
        highest_high = df['high'].rolling(window=rsv_period).max()
        rsv_denominator = highest_high - lowest_low
        rsv_denominator = rsv_denominator.replace(0, np.nan)
        df['rsv'] = ((df['close'] - lowest_low) / rsv_denominator * 100).fillna(50)
        
        # RSV 信号判断
        # RSV > 80 超买区
        # RSV < 20 超卖区
        # 20 <= RSV <= 80 中性区
        df['rsv_overbought'] = df['rsv'] > 80
        df['rsv_oversold'] = df['rsv'] < 20
        df['rsv_neutral'] = (df['rsv'] >= 20) & (df['rsv'] <= 80)
        
        # RSV 黄金区间：50-80，表示强势但未超买
        df['rsv_golden'] = (df['rsv'] >= 50) & (df['rsv'] <= 80)
        
        # RSV 从超卖区回升（可能是买入信号）
        df['rsv_recovering'] = (df['rsv'] > 20) & (df['rsv'].shift(1) <= 20)
        
        return df
    
    def calculate_volume_profile(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算量能画像副图指标（基于通达信公式转写，已消除未来函数）
        
        包含：换手率(DBHS)、标准VOL、OBV能量潮、单笔量最大、
              连续放量信号(LXTP)、主力买卖盘、牛熊趋势信号
        
        原始公式来源：通达信副图指标
        未来函数处理：
        - ISLASTBAR → 移除（仅用于标注，不影响信号）
        - CURRBARSCOUNT → 改为在最后一行计算
        - BARSCOUNT(C) → 改为 expanding window
        - COUNT(...,0) / SUM(...,0) / HHV(...,0) → expanding window
        """
        df = df.copy()
        
        # ===== 基础数据准备 =====
        close = df['close']
        high = df['high']
        low = df['low']
        open_ = df['open']
        volume = df['volume']
        amount = df['amount'] if 'amount' in df.columns else close * volume
        turnover = df['turnover'] if 'turnover' in df.columns else None
        
        # 流通股本估算: capital = volume / (turnover% / 100)
        # turnover 是换手率百分比，如 5.0 表示 5%
        if turnover is not None:
            capital = (volume / (turnover / 100)).replace([np.inf, -np.inf], np.nan)
            # 用前值填充NaN
            capital = capital.ffill().bfill()
        else:
            capital = volume * 100  # 降级估算
        
        ltp = capital
        
        # ===== DBHS 换手率指标 =====
        # IF(CAPITAL<2000000, V/CAPITAL*100, V/LTP*100)
        # 由于 LTP:=CAPITAL，两个分支结果相同，简化为 V/CAPITAL*100
        df['vp_dbhs'] = (volume / capital * 100).replace([np.inf, -np.inf], np.nan).fillna(0)
        
        # ===== 标准VOL =====
        # IF(COUNT(V>LTP/1000,0)>0, LTP/1000, 0)
        # 使用 expanding window 替代 COUNT(...,0)
        vol_threshold = ltp / 1000
        exceed_flag = (volume > vol_threshold).astype(int)
        exceed_count = exceed_flag.expanding().sum()
        df['vp_std_vol'] = np.where(exceed_count > 0, ltp / 1000, 0)
        
        # ===== 涨跌颜色标记（用于前端柱状图着色）=====
        prev_close = close.shift(1)
        # 1=涨(红), -1=跌(绿), 0=平(白)
        df['vp_color'] = np.where(close > prev_close, 1, np.where(close < prev_close, -1, 0))
        
        # ===== 单笔量最大 (expanding max) =====
        # HHV(VOL,0) → expanding().max()
        df['vp_max_vol'] = volume.expanding().max()
        
        # ===== 单笔最大换手 =====
        # HHV(DBHS,240) → rolling(240).max()
        df['vp_max_dbhs'] = df['vp_dbhs'].rolling(window=min(240, len(df)), min_periods=1).max()
        
        # ===== OBV 能量潮 =====
        # VA:=IF(C>REF(C,1),V/10,-V/10)
        # OBV:SUM(IF(C=REF(C,1),0,VA),0)
        va = np.where(close > prev_close, volume / 10,
             np.where(close < prev_close, -volume / 10, 0))
        df['vp_obv'] = pd.Series(va, index=df.index).expanding().sum()
        
        # ===== 牛熊趋势信号 =====
        # 牛:=(EXPMA(C,500)-REF(EXPMA(C,500),1))/REF(EXPMA(C,500),1)*100
        ema500 = close.ewm(span=500, adjust=False).mean()
        ema500_prev = ema500.shift(1)
        bull = ((ema500 - ema500_prev) / ema500_prev * 100).fillna(0)
        
        # EXPMA(牛,120) 和 EXPMA(牛,200)
        bull_ema120 = bull.ewm(span=120, adjust=False).mean()
        bull_ema200 = bull.ewm(span=200, adjust=False).mean()
        
        # 牛市信号: CROSS(EXPMA(牛,120)-0.0004, EXPMA(牛,200))
        bull_line = bull_ema120 - 0.0004
        df['vp_bull_signal'] = (bull_line > bull_ema200) & (bull_line.shift(1) <= bull_ema200.shift(1))
        
        # 熊市信号: CROSS(EXPMA(牛,200), EXPMA(牛,120)-0.0004)
        df['vp_bear_signal'] = (bull_ema200 > bull_line) & (bull_ema200.shift(1) <= bull_line.shift(1))
        
        # ===== 突破历史最大量信号 =====
        # V>REF(单笔量最大,1) 且涨/跌/平
        prev_max_vol = df['vp_max_vol'].shift(1)
        vol_break = volume > prev_max_vol
        df['vp_vol_break_up'] = vol_break & (close > prev_close)    # 放量突破(红)
        df['vp_vol_break_down'] = vol_break & (close < prev_close)  # 放量突破(绿)
        df['vp_vol_break_flat'] = vol_break & (close == prev_close) # 放量突破(白)
        
        # ===== 超级放量信号（黄色）=====
        # V>REF(单笔量最大,1)*1.5 AND C>REF(C,1) AND DBHS>0.15
        df['vp_super_vol'] = (volume > prev_max_vol * 1.5) & \
                             (close > prev_close) & \
                             (df['vp_dbhs'] > 0.15)
        
        # ===== 连续放量信号 LXTP =====
        # LXTP:=((V>REF(VOL,1) AND DBHS>=0.1 AND REF(VOL,1)>REF(单笔量最大,2))
        #    OR (V>REF(单笔量最大,1) AND DBHS>=0.08 AND REF(VOL,2)>REF(单笔量最大,3)))
        #    AND C>REF(CLOSE,1)
        prev_vol1 = volume.shift(1)
        prev_vol2 = volume.shift(2)
        prev_max2 = df['vp_max_vol'].shift(2)
        prev_max3 = df['vp_max_vol'].shift(3)
        
        cond_a = (volume > prev_vol1) & (df['vp_dbhs'] >= 0.1) & (prev_vol1 > prev_max2)
        cond_b = (volume > prev_max_vol) & (df['vp_dbhs'] >= 0.08) & (prev_vol2 > prev_max3)
        df['vp_lxtp'] = (cond_a | cond_b) & (close > prev_close)
        
        # LXTP1 (宽松版)
        cond_a1 = (volume > prev_vol1 * 0.9) & (df['vp_dbhs'] >= 0.1) & (prev_vol1 > prev_max2)
        cond_b1 = (volume > prev_max_vol * 0.9) & (df['vp_dbhs'] >= 0.1) & (prev_vol2 > prev_max3)
        df['vp_lxtp1'] = (cond_a1 | cond_b1) & (close > prev_close)
        
        # ===== 主力买卖盘 =====
        # A1:=(V/C)/2
        a1 = (volume / close) / 2
        
        # 使用 expanding window 替代 BARSCOUNT(C)
        # A2: 大单买入累计 (A1>100 且涨)
        a2 = (np.where((a1 > 100) & (close > prev_close), a1, 0))
        df['vp_a2'] = pd.Series(a2, index=df.index).expanding().sum()
        
        # A3: 大单卖出累计 (A1>100 且跌)
        a3 = (np.where((a1 > 100) & (close < prev_close), a1, 0))
        df['vp_a3'] = pd.Series(a3, index=df.index).expanding().sum()
        
        # A4: 小单买入累计 (A1<100 且涨)
        a4 = (np.where((a1 < 100) & (close > prev_close), a1, 0))
        df['vp_a4'] = pd.Series(a4, index=df.index).expanding().sum()
        
        # A5: 小单卖出累计 (A1<100 且跌)
        a5 = (np.where((a1 < 100) & (close < prev_close), a1, 0))
        df['vp_a5'] = pd.Series(a5, index=df.index).expanding().sum()
        
        # A6 = A2+A3+A4+A5 (总量)
        a6 = df['vp_a2'] + df['vp_a3'] + df['vp_a4'] + df['vp_a5']
        
        # 主力买盘/卖盘
        df['vp_main_buy'] = df['vp_a2']
        df['vp_main_sell'] = df['vp_a3']
        
        # 主力买信号: CROSS(主力买盘, 主力卖盘) AND 量比>0.5
        # 量比: SUM(V,0)*240/MA(VOL,5)/BARSCOUNT(C)
        cum_vol = volume.expanding().sum()
        ma_vol5 = volume.rolling(window=5, min_periods=1).mean()
        bar_count = pd.Series(range(1, len(df) + 1), index=df.index, dtype=float)
        vol_ratio = cum_vol * 240 / ma_vol5 / bar_count
        vol_ratio = vol_ratio.replace([np.inf, -np.inf], np.nan).fillna(0)
        
        main_buy_cross = (df['vp_main_buy'] > df['vp_main_sell']) & \
                         (df['vp_main_buy'].shift(1) <= df['vp_main_sell'].shift(1))
        df['vp_main_buy_signal'] = main_buy_cross & (vol_ratio > 0.5)
        
        # ===== 均线交叉信号 =====
        # MA30:=EMA(C,30); 强弱:=EMA(C,900)
        # CROSS(MA30, 强弱) → 金叉信号
        ma30 = close.ewm(span=30, adjust=False).mean()
        strength = close.ewm(span=900, adjust=False).mean()
        df['vp_ma_golden'] = (ma30 > strength) & (ma30.shift(1) <= strength.shift(1))
        
        # ===== Q值（全成本均价偏离度）=====
        # 使用 expanding window 替代 BARSCOUNT(C)
        cum_amount = amount.expanding().sum()
        cum_vol_100 = (volume * 100).expanding().sum()
        avg_cost = cum_amount / cum_vol_100
        avg_cost = avg_cost.replace([np.inf, -np.inf], np.nan).ffill()
        
        q_ratio = close / avg_cost
        q_flag = (q_ratio >= 0.95) & (q_ratio <= 1.05)
        # Q2: 如果Q=0(不在区间内)用MA均价，否则用全成本均价
        ma_cost = close.expanding().mean()
        q2 = np.where(~q_flag, ma_cost, avg_cost)
        q2 = pd.Series(q2, index=df.index).replace([np.inf, -np.inf], np.nan).ffill()
        
        # 突破全成本均价信号: CROSS(C/Q2, 1.03)
        cost_ratio = close / q2
        cost_ratio = cost_ratio.replace([np.inf, -np.inf], np.nan).fillna(1)
        df['vp_cost_break'] = (cost_ratio > 1.03) & (cost_ratio.shift(1) <= 1.03)
        
        return df
    
    def calculate_composite_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算综合评分（满分100分）
        
        基于多个维度计算股票的综合评分，并生成评级。
        
        评分维度（总计100分）：
        - 收窄得分 (25分): 收缩天数、带宽收窄程度、低波动率 ⭐核心指标
        - 趋势得分 (18分): MA排列、站上均线
        - 资金流得分 (15分): CMF资金流向
        - 动量得分 (15分): MACD状态、RSI区间、RSV位置
        - 人气得分 (12分): 换手率、市场关注度
        - 位置得分 (8分): 布林带位置、中轨上方
        - 量能得分 (7分): 放量、量价配合
        
        Args:
            df: 已计算所有技术指标的DataFrame
            
        Returns:
            添加了以下列的DataFrame:
            - squeeze_score: 收窄得分 (0-25)
            - trend_score: 趋势得分 (0-18)
            - cmf_score: 资金流得分 (0-15)
            - momentum_score: 动量得分 (0-15)
            - popularity_score: 人气得分 (0-12)
            - position_score: 位置得分 (0-8)
            - volume_score: 量能得分 (0-7)
            - total_score: 综合得分 (0-100)
            - grade: 评级 (S/A/B/C)
            - volume_up_streak: 连续放量天数
            
        Note:
            评级映射规则:
            - S级: total_score >= 75
            - A级: 60 <= total_score < 75
            - B级: 45 <= total_score < 60
            - C级: total_score < 45
        """
        df = df.copy()
        
        # ===== 收窄得分 (25分) ⭐核心指标 =====
        squeeze_score = 0
        # 连续收缩天数得分 (每天+2.5分，最高12.5分)
        squeeze_days_bonus = df['squeeze_streak'].clip(0, 5) * 2.5
        squeeze_score += squeeze_days_bonus
        # 带宽收窄程度 (收缩比越小得分越高，最高8分)
        squeeze_ratio = df['width_ma_short'] / df['width_ma_long']
        squeeze_ratio_score = squeeze_ratio.apply(
            lambda x: 8 if x < 0.8 else (5 if x < 0.9 else (3 if x < 0.95 else 0)) if pd.notna(x) else 0
        )
        squeeze_score += squeeze_ratio_score
        # 低波动率 +4.5分
        squeeze_score += df['low_volatility'].astype(int) * 4.5
        df['squeeze_score'] = squeeze_score.clip(0, 25)
        
        # ===== 趋势得分 (18分) =====
        trend_score = 0
        # MA多头排列 +8分
        trend_score += df['ma_bullish'].astype(int) * 8
        # 完全多头 额外+4分
        trend_score += df['ma_full_bullish'].astype(int) * 4
        # 站上MA20 +6分
        trend_score += df['above_ma20'].astype(int) * 6
        df['trend_score'] = trend_score.clip(0, 18)
        
        # ===== 资金流得分 (15分) 💰CMF =====
        cmf_score = 0
        # CMF > 0 资金流入 +6分
        cmf_score += df['cmf_bullish'].astype(int) * 6
        # CMF > 0.1 强势资金流入 额外+4分
        cmf_score += df['cmf_strong_bullish'].astype(int) * 4
        # CMF 上升趋势 +5分
        cmf_score += df['cmf_rising'].astype(int) * 5
        df['cmf_score'] = cmf_score.clip(0, 15)
        
        # ===== 动量得分 (15分) =====
        momentum_score = 0
        # MACD金叉 +4分
        momentum_score += df['macd_golden'].astype(int) * 4
        # MACD柱状图为正 +2分
        momentum_score += df['macd_hist_positive'].astype(int) * 2
        # MACD即将金叉 +2分
        momentum_score += df['macd_converging'].astype(int) * 2
        # RSI在中性区间 +2分
        momentum_score += df['rsi_neutral'].astype(int) * 2
        # RSV黄金区间(50-80) +3分
        momentum_score += df['rsv_golden'].astype(int) * 3
        # RSV从超卖回升 +2分
        momentum_score += df['rsv_recovering'].astype(int) * 2
        df['momentum_score'] = momentum_score.clip(0, 15)
        
        # ===== 人气得分 (12分) =====
        popularity_score = 0
        # 换手率评分 (3%-10%最佳得12分，1%-3%或10%-15%得7分，其他得0分)
        if 'turnover' in df.columns:
            turnover_score = df['turnover'].apply(
                lambda x: 12 if 3 <= x <= 10 else (7 if 2 <= x <= 15 else (3 if 1 <= x <= 20 else 0)) if pd.notna(x) else 0
            )
            popularity_score += turnover_score
        df['popularity_score'] = popularity_score.clip(0, 12)
        
        # ===== 位置得分 (8分) =====
        position_score = 0
        # 价格在中轨上方 +4分
        position_score += df['above_bb_middle'].astype(int) * 4
        # 布林带位置得分 (0.4-0.7最佳，得4分)
        bb_pos_score = df['bb_position'].apply(
            lambda x: 4 if 0.4 <= x <= 0.7 else (2 if 0.3 <= x <= 0.8 else 0) if pd.notna(x) else 0
        )
        position_score += bb_pos_score
        df['position_score'] = position_score.clip(0, 8)
        
        # ===== 量能得分 (7分) =====
        volume_score = 0
        # 量价齐升 +7分
        volume_score += df['is_volume_price_up'].astype(int) * 7
        # 仅放量 +4分
        volume_score += (~df['is_volume_price_up'] & df['is_volume_up']).astype(int) * 4
        df['volume_score'] = volume_score.clip(0, 7)
        
        # ===== 综合得分 =====
        # 确保总分在 0-100 范围内
        df['total_score'] = (
            df['squeeze_score'] +     # 收窄25分
            df['trend_score'] +       # 趋势18分
            df['cmf_score'] +         # 资金流15分 💰
            df['momentum_score'] +    # 动量15分
            df['popularity_score'] +  # 人气12分
            df['position_score'] +    # 位置8分
            df['volume_score']        # 量能7分
        ).clip(0, 100)
        
        # 评级映射: S (>=75), A (>=60), B (>=45), C (<45)
        df['grade'] = df['total_score'].apply(
            lambda x: 'S' if x >= 75 else ('A' if x >= 60 else ('B' if x >= 45 else 'C'))
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
    
    def analyze_stock(self, stock_code: str, stock_name: str = "", return_df: bool = False):
        """
        分析单只股票的布林带收缩情况
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            return_df: 是否同时返回计算后的DataFrame（用于预缓存K线数据）
            
        Returns:
            如果 return_df=False: 分析结果字典，如果不符合条件返回None
            如果 return_df=True: (分析结果字典, DataFrame) 元组，如果不符合条件返回None
        """
        try:
            # 获取股票历史数据 (最近60个交易日)，带重试机制
            def fetch_data():
                return _get_ak().stock_zh_a_hist(
                    symbol=stock_code,
                    period="daily",
                    start_date=(datetime.now() - timedelta(days=120)).strftime("%Y%m%d"),
                    end_date=datetime.now().strftime("%Y%m%d"),
                    adjust="qfq"  # 前复权
                )
            
            df = retry_request(fetch_data, max_retries=5, delay=0.5, silent=True)
            
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
            
            # 计算量能画像副图指标
            df = self.calculate_volume_profile(df)
            
            # 计算综合评分
            df = self.calculate_composite_score(df)
            
            # 获取最新数据
            latest = df.iloc[-1]
            
            # 检查是否满足收缩条件
            if latest['squeeze_streak'] >= self.min_squeeze_days:
                result = {
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
                    'turnover': round(float(latest['turnover']), 2) if pd.notna(latest.get('turnover')) else 0,
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
                    # CMF 资金流量指标
                    'cmf': round(latest['cmf'], 3) if pd.notna(latest['cmf']) else 0,
                    'cmf_bullish': bool(latest['cmf_bullish']) if pd.notna(latest['cmf_bullish']) else False,
                    'cmf_strong_bullish': bool(latest['cmf_strong_bullish']) if pd.notna(latest['cmf_strong_bullish']) else False,
                    'cmf_rising': bool(latest['cmf_rising']) if pd.notna(latest['cmf_rising']) else False,
                    # RSV 原始随机值
                    'rsv': round(latest['rsv'], 1) if pd.notna(latest['rsv']) else 50,
                    'rsv_golden': bool(latest['rsv_golden']) if pd.notna(latest['rsv_golden']) else False,
                    'rsv_overbought': bool(latest['rsv_overbought']) if pd.notna(latest['rsv_overbought']) else False,
                    'rsv_oversold': bool(latest['rsv_oversold']) if pd.notna(latest['rsv_oversold']) else False,
                    'rsv_recovering': bool(latest['rsv_recovering']) if pd.notna(latest['rsv_recovering']) else False,
                    # 综合评分
                    'squeeze_score': int(latest['squeeze_score']) if pd.notna(latest['squeeze_score']) else 0,
                    'trend_score': int(latest['trend_score']) if pd.notna(latest['trend_score']) else 0,
                    'cmf_score': int(latest['cmf_score']) if pd.notna(latest['cmf_score']) else 0,
                    'popularity_score': int(latest['popularity_score']) if pd.notna(latest['popularity_score']) else 0,
                    'momentum_score': int(latest['momentum_score']) if pd.notna(latest['momentum_score']) else 0,
                    'position_score': int(latest['position_score']) if pd.notna(latest['position_score']) else 0,
                    'volume_score': int(latest['volume_score']) if pd.notna(latest['volume_score']) else 0,
                    'total_score': int(latest['total_score']) if pd.notna(latest['total_score']) else 0,
                    'grade': latest['grade'] if pd.notna(latest['grade']) else 'C',
                }
                
                # 根据参数决定返回格式
                if return_df:
                    return (result, df)
                return result
            
            return None
            
        except Exception as e:
            # 打印错误信息以便调试
            print(f"[ERROR] 分析股票 {stock_code} 出错: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None


class HotSectorScanner:
    """热点板块扫描器（使用同花顺数据源）
    
    负责协调整个扫描流程，包括获取板块数据、调度股票分析、管理并发。
    
    数据源：
    - 行业板块排行：同花顺 (https://q.10jqka.com.cn/thshy/)
    - 行业成分股：同花顺爬虫
    - K线数据：同花顺日K接口
    
    Attributes:
        strategy: 布林带收缩策略实例
    """
    
    def __init__(self, strategy: BollingerSqueezeStrategy):
        """
        初始化扫描器
        
        Args:
            strategy: 布林带收缩策略实例
        """
        self.strategy = strategy
        
    def get_hot_sectors(self, top_n: int = 10) -> pd.DataFrame:
        """
        获取热点板块列表（同花顺数据源）
        
        从同花顺获取行业板块数据，按涨跌幅降序排列后返回前N个热点板块。
        
        Args:
            top_n: 返回前N个热点板块，必须为正整数，默认10
            
        Returns:
            热点板块DataFrame，包含板块名称、涨跌幅、领涨股票等信息。
            如果获取失败返回空DataFrame。
            
        Raises:
            ValueError: 当 top_n 不是正整数时
            
        Example:
            >>> scanner = HotSectorScanner(strategy)
            >>> sectors = scanner.get_hot_sectors(top_n=5)
            >>> print(sectors['板块名称'].tolist())
        """
        # 参数验证
        if not isinstance(top_n, int) or top_n <= 0:
            raise ValueError(f"top_n 必须为正整数，当前值: {top_n}")
        
        try:
            from utils.ths_crawler import get_ths_industry_list
            
            logger.info(f"正在获取热点板块数据(THS)，top_n={top_n}")
            
            # 使用同花顺爬虫获取板块数据
            df = retry_request(get_ths_industry_list, max_retries=3, delay=1.0)
            
            if df is None or len(df) == 0:
                logger.warning("获取热点板块数据为空")
                return pd.DataFrame()
            
            # 重命名列以保持兼容性
            df = df.rename(columns={'板块': '板块名称'})
            result = df.head(top_n)
            
            logger.info(f"成功获取 {len(result)} 个热点板块")
            return result
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"获取热点板块失败: {e}")
            return pd.DataFrame()
    
    def get_sector_stocks(self, sector_name: str) -> List[Dict]:
        """
        获取板块成分股列表（同花顺数据源）
        
        获取指定板块的所有成分股，按总市值降序排列，并标记前3名为中军股票。
        
        Args:
            sector_name: 板块名称，不能为空
            
        Returns:
            成分股列表，每个元素包含:
            - code: 股票代码
            - name: 股票名称
            - market_cap: 总市值
            - is_leader: 是否为中军（市值前3名）
            - leader_rank: 中军排名（1-3，非中军为0）
            
            如果获取失败返回空列表。
            
        Raises:
            ValueError: 当 sector_name 为空时
        """
        from utils.ths_crawler import fetch_ths_industry_stocks, get_ths_industry_list
        
        # 参数验证
        if not sector_name or not isinstance(sector_name, str):
            raise ValueError(f"sector_name 必须为非空字符串，当前值: {sector_name}")
        
        try:
            logger.info(f"正在获取板块 '{sector_name}' 的成分股(THS)")
            
            # 从板块列表中查找代码
            df = get_ths_industry_list()
            # 兼容两种列名
            name_col = '板块名称' if '板块名称' in df.columns else '板块'
            row = df[df[name_col] == sector_name]
            sector_code = ''
            if len(row) > 0:
                sector_code = row.iloc[0].get('代码', '')
            
            if not sector_code:
                logger.warning(f"未找到板块 '{sector_name}' 的代码")
                return []
            
            # 使用同花顺爬虫获取成分股
            stocks = fetch_ths_industry_stocks(sector_code, sector_name)
            
            if not stocks:
                logger.warning(f"板块 '{sector_name}' 成分股数据为空")
                return []
            
            # 按市值降序排序
            stocks_sorted = sorted(stocks, key=lambda x: x.get('market_cap', 0), reverse=True)
            
            # 标记中军（市值前3名）
            for i, stock in enumerate(stocks_sorted):
                if i < 3:
                    stock['is_leader'] = True
                    stock['leader_rank'] = i + 1
                else:
                    stock['is_leader'] = False
                    stock['leader_rank'] = 0
            
            logger.info(f"板块 '{sector_name}' 共有 {len(stocks_sorted)} 只成分股")
            return stocks_sorted
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"获取板块 '{sector_name}' 成分股失败: {e}")
            return []
    
    def get_all_sector_stocks_concurrent(self, sector_names: List[str], max_workers: int = 5) -> Dict[str, List[Dict]]:
        """
        并发获取多个板块的成分股列表
        
        Args:
            sector_names: 板块名称列表
            max_workers: 最大并发数，默认5
            
        Returns:
            {板块名称: [成分股列表], ...}
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time
        import random
        
        results = {}
        
        def fetch_sector_stocks(sector_name: str) -> Tuple[str, List[Dict]]:
            """获取单个板块成分股（带随机延迟避免限流）"""
            time.sleep(random.uniform(0.1, 0.3))
            print(f"  📥 获取板块成分股: {sector_name}")
            stocks = self.get_sector_stocks(sector_name)
            print(f"  ✅ {sector_name}: {len(stocks)} 只成分股")
            return (sector_name, stocks)
        
        print(f"⚡ 并发获取 {len(sector_names)} 个板块成分股 (并发数: {max_workers})")
        logger.info(f"并发获取 {len(sector_names)} 个板块的成分股，max_workers={max_workers}")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_sector = {
                executor.submit(fetch_sector_stocks, name): name 
                for name in sector_names
            }
            
            for future in as_completed(future_to_sector):
                sector_name = future_to_sector[future]
                try:
                    name, stocks = future.result()
                    results[name] = stocks
                    logger.info(f"板块 '{name}' 获取到 {len(stocks)} 只成分股")
                except Exception as e:
                    print(f"  ❌ {sector_name}: 获取失败 - {e}")
                    logger.error(f"获取板块 '{sector_name}' 成分股失败: {e}")
                    results[sector_name] = []
        
        total_stocks = sum(len(s) for s in results.values())
        print(f"📊 成分股获取完成，共 {total_stocks} 只股票")
        
        return results
    
    def scan_hot_sectors(self, top_sectors: int = 5, progress: bool = True, concurrent_fetch: bool = True) -> Dict[str, List[Dict]]:
        """
        扫描热点板块中的布林带收缩股票
        
        Args:
            top_sectors: 扫描前N个热点板块
            progress: 是否显示进度条
            concurrent_fetch: 是否并发获取板块成分股列表（默认True）
            
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
        
        # 获取所有板块名称
        sector_names = hot_sectors['板块名称'].tolist()
        
        # 并发或串行获取所有板块的成分股
        if concurrent_fetch:
            all_sector_stocks = self.get_all_sector_stocks_concurrent(sector_names, max_workers=5)
        else:
            print("📥 串行获取板块成分股列表...")
            all_sector_stocks = {}
            for name in sector_names:
                print(f"  📥 获取: {name}")
                all_sector_stocks[name] = self.get_sector_stocks(name)
                print(f"  ✅ {name}: {len(all_sector_stocks[name])} 只成分股")
        
        # 遍历热点板块进行分析
        for _, sector in hot_sectors.iterrows():
            sector_name = sector['板块名称']
            print(f"\n🔍 扫描板块: {sector_name}")
            
            # 从预获取的数据中取成分股
            stocks = all_sector_stocks.get(sector_name, [])
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
        stock_list = _get_ak().stock_zh_a_spot_em()
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
