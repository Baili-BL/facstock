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


def get_ths_industry_list() -> pd.DataFrame:
    """
    爬取同花顺行业板块列表（按涨跌幅排序）
    
    数据源: https://q.10jqka.com.cn/thshy/
    
    Returns:
        DataFrame: 包含 板块、代码、涨跌幅、领涨股 等信息
    """
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
                
                # 表头: 序号, 板块, 涨跌幅(%), 总成交量, 总成交额, 净流入, 上涨家数, 下跌家数, 均价, 领涨股, 最新价, 涨跌幅(%)
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
        # 按涨跌幅降序排序
        df = df.sort_values(by='涨跌幅', ascending=False).reset_index(drop=True)
        return df
        
    except Exception as e:
        print(f"[ERROR] 爬取行业列表失败: {e}")
        # 降级使用 akshare
        try:
            df = ak.stock_board_industry_summary_ths()
            code_map = get_ths_industry_code_map()
            df['代码'] = df['板块'].map(code_map)
            return df
        except:
            raise e


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
    爬取同花顺行业成分股
    
    Args:
        industry_code: 行业代码，如 '881101'
        industry_name: 行业名称（用于日志）
        
    Returns:
        List[Dict]: 成分股列表，每个元素包含 code, name, price, change 等
    """
    url = f'https://q.10jqka.com.cn/thshy/detail/code/{industry_code}/'
    
    try:
        # 随机延迟，避免被封
        time.sleep(random.uniform(0.3, 0.8))
        
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = 'gbk'  # 同花顺页面编码
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 查找股票表格
        table = soup.find('table', class_='m-table')
        if not table:
            print(f"[WARN] {industry_name}({industry_code}) 未找到股票表格")
            return []
        
        stocks = []
        rows = table.find_all('tr')[1:]  # 跳过表头
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 12:
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
        return []


def _parse_float(s: str) -> float:
    """解析浮点数，处理特殊字符"""
    if not s or s == '--' or s == '-':
        return 0.0
    try:
        return float(s.replace(',', '').replace('%', ''))
    except:
        return 0.0


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
    爬取同花顺K线数据（替代新浪接口）
    
    数据源: https://d.10jqka.com.cn/v6/line/hs_{code}/01/last.js
    
    Args:
        stock_code: 股票代码（6位数字）
        days: 获取天数（同花顺接口返回约140条，足够使用）
        
    Returns:
        DataFrame: K线数据，包含 date, open, close, high, low, volume, pct_change
    """
    try:
        # 同花顺日K线接口
        url = f'https://d.10jqka.com.cn/v6/line/hs_{stock_code}/01/last.js'
        
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        
        # 解析 JSONP 格式: quotebridge_v6_line_hs_xxx_01_last({...})
        import re
        import json
        
        match = re.search(r'\((\{.*\})\)', resp.text)
        if not match:
            print(f"[WARN] {stock_code} K线数据格式错误")
            return None
        
        data = json.loads(match.group(1))
        raw_data = data.get('data', '')
        
        if not raw_data:
            return None
        
        # 解析K线数据
        # 格式: 日期,开盘,最高,最低,收盘,成交量,成交额,涨跌幅,...
        lines = raw_data.split(';')
        
        records = []
        prev_close = None
        
        for line in lines:
            parts = line.split(',')
            if len(parts) < 7:
                continue
            
            try:
                date_str = parts[0]
                open_price = float(parts[1])
                high = float(parts[2])
                low = float(parts[3])
                close = float(parts[4])
                volume = float(parts[5])
                amount = float(parts[6].replace('.00', ''))
                
                # 计算涨跌幅
                pct_change = 0.0
                if prev_close and prev_close > 0:
                    pct_change = round((close - prev_close) / prev_close * 100, 2)
                prev_close = close
                
                # 计算换手率（如果有流通股数据）
                turnover = 0.0
                if len(parts) > 9 and parts[9]:
                    try:
                        turnover = float(parts[7].replace(',', '')) if parts[7] else 0.0
                    except:
                        pass
                
                records.append({
                    'date': f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}',
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'close': close,
                    'volume': volume,
                    'amount': amount,
                    'pct_change': pct_change,
                    'turnover': turnover,
                })
            except Exception:
                continue
        
        if not records:
            return None
        
        df = pd.DataFrame(records)
        
        # 只返回最近 days 天的数据
        if len(df) > days:
            df = df.tail(days).reset_index(drop=True)
        
        return df
        
    except Exception as e:
        print(f"[ERROR] 获取 {stock_code} K线失败: {e}")
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
