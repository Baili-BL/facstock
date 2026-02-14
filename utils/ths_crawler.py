#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同花顺数据爬虫模块

数据源：
1. 行业板块排行: https://q.10jqka.com.cn/thshy/
2. 行业成分股: https://q.10jqka.com.cn/thshy/detail/code/{板块代码}/
3. K线数据: 使用 akshare 新浪接口
"""

import requests
from bs4 import BeautifulSoup
import akshare as ak
import pandas as pd
import time
import random
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta


# 请求头，模拟浏览器
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://q.10jqka.com.cn/thshy/',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

# THS 可用性标记：一旦检测到 403，本次进程内不再尝试 THS，直接走东方财富
_ths_available = True
_ths_fail_time = 0
_THS_COOLDOWN = 3600  # THS 被封后冷却 1 小时再重试


def _is_ths_available() -> bool:
    """检查 THS 是否可用（冷却期内不重试）"""
    global _ths_available, _ths_fail_time
    if _ths_available:
        return True
    # 冷却期过了，允许重试
    if time.time() - _ths_fail_time > _THS_COOLDOWN:
        _ths_available = True
        print("[THS] 冷却期结束，重新尝试同花顺接口")
        return True
    return False


def _mark_ths_unavailable():
    """标记 THS 不可用，进入冷却期"""
    global _ths_available, _ths_fail_time
    if _ths_available:
        print("[THS] 同花顺接口不可用(403)，切换到东方财富，冷却1小时")
    _ths_available = False
    _ths_fail_time = time.time()


def _get_industry_list_em() -> pd.DataFrame:
    """使用东方财富接口获取行业板块列表"""
    print("[EM] 使用东方财富行业板块接口...")
    try:
        df_em = ak.stock_board_industry_name_em()
    except Exception as e:
        print(f"[EM] ak.stock_board_industry_name_em() 调用失败: {e}")
        raise
    if df_em is None or df_em.empty:
        raise Exception("东方财富接口返回空数据")
    print(f"[EM] 原始数据列: {df_em.columns.tolist()}")
    df_result = pd.DataFrame({
        '序号': range(1, len(df_em) + 1),
        '板块': df_em['板块名称'],
        '代码': df_em['板块代码'],
        '涨跌幅': df_em['涨跌幅'].astype(float),
        '上涨家数': df_em['上涨家数'].astype(int),
        '下跌家数': df_em['下跌家数'].astype(int),
        '领涨股': df_em['领涨股票'],
        '领涨股-涨跌幅': df_em['领涨股票-涨跌幅'].astype(float),
    })
    df_result = df_result.sort_values(by='涨跌幅', ascending=False).reset_index(drop=True)
    print(f"[EM] 东方财富接口成功，{len(df_result)} 个行业")
    return df_result


def get_ths_industry_list() -> pd.DataFrame:
    """
    获取行业板块列表（按涨跌幅排序）
    
    优先使用同花顺，403 时自动切换东方财富并记住状态，
    冷却期内直接走东方财富，避免反复触发封禁。
    
    Returns:
        DataFrame: 包含 板块、代码、涨跌幅、领涨股 等信息
    """
    # 如果 THS 已被标记不可用，直接走东方财富
    if not _is_ths_available():
        print("[THS] 冷却期内，跳过同花顺，直接使用东方财富")
        return _get_industry_list_em()

    url = 'https://q.10jqka.com.cn/thshy/'
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = 'gbk'
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 查找行业列表表格
        table = soup.find('table', class_='m-table')
        if not table:
            raise Exception("未找到行业表格")
        
        industries = []
        rows = table.find_all('tr')[1:]  # 跳过表头
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 12:
                continue
            
            try:
                # 获取行业链接中的代码
                link = cells[1].find('a')
                href = link.get('href', '') if link else ''
                # 从 /thshy/detail/code/881101/ 提取代码
                code = ''
                if '/code/' in href:
                    code = href.split('/code/')[-1].rstrip('/')
                
                industry = {
                    '序号': _parse_int(cells[0].get_text(strip=True)),
                    '板块': cells[1].get_text(strip=True),
                    '代码': code,
                    '涨跌幅': _parse_float(cells[2].get_text(strip=True)),
                    '总成交量': _parse_float(cells[3].get_text(strip=True)),
                    '总成交额': _parse_float(cells[4].get_text(strip=True)),
                    '净流入': _parse_float(cells[5].get_text(strip=True)),
                    '上涨家数': _parse_int(cells[6].get_text(strip=True)),
                    '下跌家数': _parse_int(cells[7].get_text(strip=True)),
                    '领涨股': cells[9].get_text(strip=True),
                    '领涨股-最新价': _parse_float(cells[10].get_text(strip=True)),
                    '领涨股-涨跌幅': _parse_float(cells[11].get_text(strip=True)),
                }
                industries.append(industry)
            except Exception:
                continue
        
        df = pd.DataFrame(industries)
        df = df.sort_values(by='涨跌幅', ascending=False).reset_index(drop=True)
        return df
        
    except Exception as e:
        print(f"[ERROR] 爬取行业列表失败: {e}")
        # 任何 THS 请求失败都标记不可用（403、连接断开、超时等）
        _mark_ths_unavailable()
        # 降级使用东方财富接口
        em_error = None
        try:
            return _get_industry_list_em()
        except Exception as e2:
            em_error = e2
            print(f"[ERROR] 东方财富接口也失败: {e2}")
            import traceback
            traceback.print_exc()
        raise Exception(f"所有数据源均失败 - THS: {e} | 东方财富: {em_error}")


def get_ths_industry_code_map() -> Dict[str, str]:
    """
    获取同花顺行业名称到代码的映射
    
    Returns:
        Dict: {行业名称: 行业代码}
    """
    try:
        df = ak.stock_board_industry_name_ths()
        return dict(zip(df['name'], df['code']))
    except:
        # 如果 akshare 失败，从行业列表页面获取
        df = get_ths_industry_list()
        return dict(zip(df['板块'], df['代码']))


def _parse_int(s: str) -> int:
    """解析整数"""
    if not s or s == '--' or s == '-':
        return 0
    try:
        return int(s.replace(',', ''))
    except:
        return 0


def fetch_ths_industry_stocks(industry_code: str, industry_name: str = '') -> List[Dict]:
    """
    获取行业成分股
    
    优先同花顺爬虫，THS 不可用时直接走东方财富。
    
    Args:
        industry_code: 行业代码（THS 格式如 '881101' 或东方财富格式如 'BK0486'）
        industry_name: 行业名称（东方财富用名称查询）
        
    Returns:
        List[Dict]: 成分股列表
    """
    # THS 不可用时直接走东方财富
    if not _is_ths_available():
        return _fetch_industry_stocks_em(industry_name)

    url = f'https://q.10jqka.com.cn/thshy/detail/code/{industry_code}/'
    
    try:
        time.sleep(random.uniform(0.3, 0.8))
        
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = 'gbk'
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        table = soup.find('table', class_='m-table')
        if not table:
            print(f"[WARN] {industry_name}({industry_code}) 未找到股票表格")
            return _fetch_industry_stocks_em(industry_name)
        
        stocks = []
        rows = table.find_all('tr')[1:]
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 13:
                continue
            
            try:
                stock = {
                    'code': cells[1].get_text(strip=True),
                    'name': cells[2].get_text(strip=True),
                    'price': _parse_float(cells[3].get_text(strip=True)),
                    'change': _parse_float(cells[4].get_text(strip=True)),
                    'turnover': _parse_float(cells[7].get_text(strip=True)),
                    'volume_ratio': _parse_float(cells[8].get_text(strip=True)),
                    'market_cap': _parse_market_cap(cells[12].get_text(strip=True)),
                }
                stocks.append(stock)
            except Exception as e:
                continue
        
        return stocks
        
    except Exception as e:
        print(f"[ERROR] 爬取 {industry_name}({industry_code}) 失败: {e}")
        _mark_ths_unavailable()
        return _fetch_industry_stocks_em(industry_name)


def _parse_float(s: str) -> float:
    """解析浮点数，处理特殊字符"""
    if not s or s == '--' or s == '-':
        return 0.0
    try:
        return float(s.replace(',', '').replace('%', ''))
    except:
        return 0.0


def _fetch_industry_stocks_em(industry_name: str) -> List[Dict]:
    """
    使用东方财富接口获取行业成分股（降级方案）
    
    Args:
        industry_name: 行业名称（东方财富用名称查询）
        
    Returns:
        List[Dict]: 成分股列表，格式与同花顺爬虫一致
    """
    try:
        print(f"[FALLBACK] 使用东方财富接口获取 {industry_name} 成分股...")
        df = ak.stock_board_industry_cons_em(symbol=industry_name)
        
        if df is None or df.empty:
            print(f"[FALLBACK] 东方财富 {industry_name} 返回空数据")
            return []
        
        stocks = []
        for _, row in df.iterrows():
            code = str(row.get('代码', ''))
            if not code:
                continue
            stocks.append({
                'code': code,
                'name': row.get('名称', ''),
                'price': float(row.get('最新价', 0) or 0),
                'change': float(row.get('涨跌幅', 0) or 0),
                'turnover': float(row.get('换手率', 0) or 0),
                'volume_ratio': 0,
                'market_cap': float(row.get('总市值', 0) or 0) if '总市值' in df.columns else 0,
                # 东方财富额外数据（题材挖掘可用）
                'amount': float(row.get('成交额', 0) or 0),
                'amplitude': float(row.get('振幅', 0) or 0),
                'high': float(row.get('最高', 0) or 0),
                'low': float(row.get('最低', 0) or 0),
                'open': float(row.get('今开', 0) or 0),
                'prev_close': float(row.get('昨收', 0) or 0),
            })
        
        print(f"[FALLBACK] 东方财富 {industry_name}: {len(stocks)} 只")
        return stocks
        
    except Exception as e:
        print(f"[ERROR] 东方财富接口获取 {industry_name} 失败: {e}")
        return []


def _parse_market_cap(s: str) -> float:
    """解析市值，处理亿/万单位"""
    if not s or s == '--' or s == '-':
        return 0.0
    try:
        s = s.replace(',', '')
        if '亿' in s:
            return float(s.replace('亿', '')) * 100000000
        elif '万' in s:
            return float(s.replace('万', '')) * 10000
        else:
            return float(s)
    except:
        return 0.0


def get_stock_kline_sina(stock_code: str, days: int = 120) -> Optional[pd.DataFrame]:
    """
    获取股票K线数据（使用新浪接口，数据更及时）
    
    Args:
        stock_code: 股票代码（6位数字）
        days: 获取天数
        
    Returns:
        DataFrame: K线数据，包含 date, open, close, high, low, volume, pct_change
    """
    # 判断股票市场（沪市6开头，深市0/3开头）
    if stock_code.startswith('6'):
        symbol = f'sh{stock_code}'
    else:
        symbol = f'sz{stock_code}'
    
    # 优先使用新浪接口（数据及时且稳定）
    try:
        df = ak.stock_zh_a_daily(symbol=symbol, adjust='qfq')
        
        if df is None or df.empty:
            raise Exception("新浪接口返回空数据")
        
        # 统一列名
        df = df.rename(columns={
            'open': 'open',
            'close': 'close',
            'high': 'high',
            'low': 'low',
            'volume': 'volume',
        })
        
        # 确保 date 是字符串格式
        df['date'] = df['date'].astype(str)
        
        # 计算涨跌幅
        df['pct_change'] = df['close'].pct_change() * 100
        df['pct_change'] = df['pct_change'].fillna(0).round(2)
        
        # 添加 amount 和 turnover（如果没有）
        if 'amount' not in df.columns:
            df['amount'] = 0
        if 'turnover' not in df.columns:
            df['turnover'] = 0
        
        # 只返回最近 days 天
        if len(df) > days:
            df = df.tail(days).reset_index(drop=True)
        
        return df
        
    except Exception as e:
        print(f"[WARN] 新浪接口获取 {stock_code} 失败: {e}，尝试东方财富接口")
    
    # 降级使用东方财富接口（akshare）
    try:
        df = ak.stock_zh_a_hist(symbol=stock_code, period='daily', adjust='qfq')
        
        if df is None or df.empty:
            print(f"[WARN] 东方财富接口 {stock_code} 也返回空数据")
            return None
        
        df = df.rename(columns={
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
            '换手率': 'turnover',
            '涨跌幅': 'pct_change',
        })
        
        df['date'] = df['date'].astype(str)
        
        if 'pct_change' not in df.columns:
            df['pct_change'] = df['close'].pct_change() * 100
            df['pct_change'] = df['pct_change'].fillna(0).round(2)
        
        if 'amount' not in df.columns:
            df['amount'] = 0
        if 'turnover' not in df.columns:
            df['turnover'] = 0
        
        if len(df) > days:
            df = df.tail(days).reset_index(drop=True)
        
        return df
        
    except Exception as e2:
        print(f"[ERROR] 东方财富接口获取 {stock_code} K线也失败: {e2}")
        return None


def get_hot_industries_with_stocks(top_n: int = 5) -> List[Dict]:
    """
    获取热点行业及其成分股（完整流程）
    
    Args:
        top_n: 获取前N个热点行业
        
    Returns:
        List[Dict]: [{
            'name': 行业名称,
            'code': 行业代码,
            'change': 涨跌幅,
            'leader': 领涨股,
            'stocks': [成分股列表]
        }, ...]
    """
    # 1. 获取行业排行
    print("📊 获取同花顺行业排行...")
    df = get_ths_industry_list()
    
    if df is None or df.empty:
        raise Exception("无法获取行业列表")
    
    # 2. 获取行业代码映射
    code_map = get_ths_industry_code_map()
    
    # 3. 取前N个热点行业
    hot_industries = []
    for _, row in df.head(top_n).iterrows():
        industry_name = row['板块']
        industry_code = code_map.get(industry_name, '')
        
        if not industry_code:
            print(f"[WARN] 未找到 {industry_name} 的代码")
            continue
        
        industry_info = {
            'name': industry_name,
            'code': industry_code,
            'change': _parse_float(str(row['涨跌幅'])),
            'leader': row.get('领涨股', ''),
            'leader_change': _parse_float(str(row.get('领涨股-涨跌幅', 0))),
            'net_inflow': row.get('净流入', 0),
            'stocks': []
        }
        
        # 4. 获取成分股
        print(f"  📥 获取 {industry_name}({industry_code}) 成分股...")
        stocks = fetch_ths_industry_stocks(industry_code, industry_name)
        industry_info['stocks'] = stocks
        print(f"  ✅ {industry_name}: {len(stocks)} 只股票")
        
        hot_industries.append(industry_info)
    
    return hot_industries


if __name__ == '__main__':
    # 测试
    print("=== 测试同花顺爬虫 ===\n")
    
    # 测试获取行业列表
    print("1. 获取行业排行:")
    df = get_ths_industry_list()
    print(df.head(5))
    print()
    
    # 测试获取行业代码
    print("2. 获取行业代码映射:")
    code_map = get_ths_industry_code_map()
    for name, code in list(code_map.items())[:5]:
        print(f"  {name}: {code}")
    print()
    
    # 测试爬取成分股
    print("3. 爬取种植业与林业成分股:")
    stocks = fetch_ths_industry_stocks('881101', '种植业与林业')
    for s in stocks[:5]:
        print(f"  {s['code']} {s['name']} 涨跌幅:{s['change']}%")
    print(f"  共 {len(stocks)} 只")
