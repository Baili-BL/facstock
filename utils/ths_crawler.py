#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同花顺数据爬虫模块

数据源（K 线优先级）：
1. 新浪（akshare → stock_zh_a_daily）
2. 东方财富（akshare → stock_zh_a_hist）
3. 腾讯证券（akshare → stock_zh_a_hist_tx）
4. 东财备用（push2.eastmoney.com，不同节点）

每个数据源独立可用性标记 + 冷却期，避免反复撞已封接口。
"""

import time
import random
import os
import contextlib
import requests
import pandas as pd
import akshare as ak
from typing import List, Dict, Optional, Tuple


# ──────────────────────────── 代理绕过 ──────────────────────────────────

@contextlib.contextmanager
def _no_http_proxy_env():
    """临时清除环境变量中的代理（含 SOCKS），避免无效代理导致 403/连接中断。"""
    keys = (
        'HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy',
        'ALL_PROXY', 'all_proxy', 'SOCKS_PROXY', 'socks_proxy',
        'SOCKS5_PROXY', 'socks5_proxy',
    )
    saved = {k: os.environ.pop(k) for k in keys if k in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)


@contextlib.contextmanager
def _requests_no_proxy():
    """让 requests Session 跳过系统代理（trust_env=False）。"""
    import requests.sessions as _rsess
    _orig = _rsess.Session
    def _no_proxy_session(*args, **kwargs):
        s = _orig(*args, **kwargs)
        s.trust_env = False
        return s
    _rsess.Session = _no_proxy_session  # type: ignore[assignment]
    requests.Session = _no_proxy_session  # type: ignore[assignment]
    try:
        yield
    finally:
        _rsess.Session = _orig  # type: ignore[assignment]
        requests.Session = _orig  # type: ignore[assignment]

# ──────────────────────────── 全局可用性标记 ────────────────────────────

_SOURCES = {
    'sina':    {'available': True,  'fail_time': 0, 'cooldown': 300},
    'em':      {'available': True,  'fail_time': 0, 'cooldown': 300},
    'tx':      {'available': True,  'fail_time': 0, 'cooldown': 300},
    'baidu':   {'available': True,  'fail_time': 0, 'cooldown': 600},
}


def _src_available(name: str) -> bool:
    s = _SOURCES[name]
    if s['available']:
        return True
    if time.time() - s['fail_time'] > s['cooldown']:
        s['available'] = True
        print(f"[{name.upper()}] 冷却期结束，重新尝试")
        return True
    return False


def _mark_src_fail(name: str):
    s = _SOURCES[name]
    if s['available']:
        s['available'] = False
        s['fail_time'] = time.time()
        print(f"[{name.upper()}] 接口不可用，进入冷却 {s['cooldown']}s")


# ──────────────────────────── 统一列规范化 ───────────────────────────────

_REQUIRED_COLS = ['date', 'open', 'high', 'low', 'close', 'volume']
_OUTPUT_COLS  = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'turnover', 'pct_change']


def _normalize_kline_df(df: pd.DataFrame, days: int) -> Optional[pd.DataFrame]:
    """
    各数据源返回的 DataFrame 统一规范化：
    - 只保留 _OUTPUT_COLS
    - date → str 'YYYY-MM-DD'
    - 所有数值列 float，NaN → 0
    - 按日期升序
    - 截取最近 days 条
    """
    if df is None or df.empty:
        return None

    # 只取需要的列，缺失的补 0
    for col in _OUTPUT_COLS:
        if col not in df.columns:
            df[col] = 0.0

    df = df[_OUTPUT_COLS].copy()

    # 日期转字符串
    if 'date' in df.columns:
        df['date'] = df['date'].astype(str).str[:10]
        # 过滤无效日期
        df = df[df['date'].str.match(r'^\d{4}-\d{2}-\d{2}$', na=False)]

    # 数值列 NaN → 0，Inf → 0
    num_cols = [c for c in _OUTPUT_COLS if c != 'date']
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        df[col] = df[col].replace([float('inf'), float('-inf')], 0.0)

    # pct_change 兜底
    if df['close'].notna().sum() > 1:
        df['pct_change'] = df['close'].pct_change().fillna(0.0).round(4)

    df = df.reset_index(drop=True)

    if len(df) == 0:
        return None

    if len(df) > days:
        df = df.tail(days).reset_index(drop=True)

    return df


# ──────────────────────────── 数据源实现 ────────────────────────────

def _fetch_sina(stock_code: str, days: int) -> Optional[pd.DataFrame]:
    """新浪日线（akshare stock_zh_a_daily）"""
    if not _src_available('sina'):
        return None
    try:
        symbol = f'sh{stock_code}' if stock_code.startswith('6') else f'sz{stock_code}'
        with _no_http_proxy_env(), _requests_no_proxy():
            df = ak.stock_zh_a_daily(symbol=symbol, adjust='qfq')
        df = df.rename(columns={
            'open': 'open', 'close': 'close', 'high': 'high',
            'low': 'low', 'volume': 'volume',
        })
        df = _normalize_kline_df(df, days)
        if df is None or df.empty:
            raise ValueError("空数据")
        print(f"[SINA] {stock_code} 获取成功 {len(df)} 条")
        return df
    except Exception as e:
        print(f"[SINA] {stock_code} 失败: {e}")
        _mark_src_fail('sina')
        return None


def _fetch_em(stock_code: str, days: int) -> Optional[pd.DataFrame]:
    """东方财富日线（akshare stock_zh_a_hist）"""
    if not _src_available('em'):
        return None
    try:
        with _no_http_proxy_env(), _requests_no_proxy():
            df = ak.stock_zh_a_hist(
                symbol=stock_code, period='daily', adjust='qfq',
                start_date='20100101', end_date='20500101',
            )
            if df is None or df.empty:
                raise ValueError("空数据")
            df = df.rename(columns={
                '日期': 'date', '开盘': 'open', '收盘': 'close',
                '最高': 'high', '最低': 'low', '成交量': 'volume',
                '成交额': 'amount', '换手率': 'turnover',
                '涨跌幅': 'pct_change',
            })
            df = _normalize_kline_df(df, days)
            if df is None or df.empty:
                raise ValueError("空数据")
            print(f"[EM] {stock_code} 获取成功 {len(df)} 条")
            return df
    except Exception as e:
        print(f"[EM] {stock_code} 失败: {e}")
        _mark_src_fail('em')
        return None


def _fetch_tx(stock_code: str, days: int) -> Optional[pd.DataFrame]:
    """腾讯证券日线（akshare stock_zh_a_hist_tx）"""
    if not _src_available('tx'):
        return None
    try:
        symbol = f'sh{stock_code}' if stock_code.startswith('6') else f'sz{stock_code}'
        with _no_http_proxy_env(), _requests_no_proxy():
            df = ak.stock_zh_a_hist_tx(
                symbol=symbol,
                start_date='20100101', end_date='20500101',
                adjust='qfq',
            )
            if df is None or df.empty:
                raise ValueError("空数据")
            df = df.rename(columns={
                '日期': 'date', '开盘': 'open', '收盘': 'close',
                '最高': 'high', '最低': 'low', '成交量': 'volume',
            })
            df = _normalize_kline_df(df, days)
            if df is None or df.empty:
                raise ValueError("空数据")
            print(f"[TX] {stock_code} 获取成功 {len(df)} 条")
            return df
    except Exception as e:
        print(f"[TX] {stock_code} 失败: {e}")
        _mark_src_fail('tx')
        return None


def _fetch_em2(stock_code: str, days: int) -> Optional[pd.DataFrame]:
    """
    东方财富备选接口（push2.eastmoney.com，与 stock_zh_a_hist 不同节点）
    格式: secid=1.600519（沪）或 0.000001（深）
    """
    if not _src_available('baidu'):
        return None
    try:
        # 判断沪/深：6开头=沪(1)，0/3开头=深(0)
        market = '1' if stock_code.startswith('6') else '0'
        url = 'https://push2.eastmoney.com/api/qt/stock/kline/get'
        params = {
            'secid': f'{market}.{stock_code}',
            'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
            'klt': '101',   # 日线
            'fqt': '1',    # 前复权
            'end': '20500101',
            'lmt': str(days),
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        json_data = r.json()
        klines = (json_data.get('data', {}) or {}).get('klines', []) or []
        if not klines:
            raise ValueError("空数据")
        rows = []
        for line in klines:
            parts = line.split(',')
            if len(parts) < 6:
                continue
            rows.append({
                'date':     parts[0],
                'open':     float(parts[1]),
                'close':    float(parts[2]),
                'high':     float(parts[3]),
                'low':      float(parts[4]),
                'volume':   float(parts[5]) if parts[5] else 0.0,
                'amount':   float(parts[6]) if len(parts) > 6 and parts[6] else 0.0,
                'turnover': 0.0,
                'pct_change': 0.0,
            })
        df = pd.DataFrame(rows)
        if df.empty:
            raise ValueError("空数据")
        # pct_change
        if 'close' in df.columns:
            df['pct_change'] = df['close'].pct_change().fillna(0).round(2)
        print(f"[EM2] {stock_code} 获取成功 {len(df)} 条")
        return df
    except Exception as e:
        print(f"[EM2] {stock_code} 失败: {e}")
        _mark_src_fail('baidu')
        return None


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


def _fetch_industry_stocks_em(industry_name: str) -> List[Dict]:
    """
    使用东方财富接口获取行业成分股（降级方案）
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


def fetch_ths_industry_stocks(industry_code: str, industry_name: str = '') -> List[Dict]:
    """
    获取行业成分股。优先同花顺爬虫，THS 不可用时直接走东方财富。
    """
    if not _is_ths_available():
        return _fetch_industry_stocks_em(industry_name)

    url = f'https://q.10jqka.com.cn/thshy/detail/code/{industry_code}/'

    try:
        time.sleep(random.uniform(0.3, 0.8))
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = 'gbk'

        from bs4 import BeautifulSoup
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
            except Exception:
                continue
        return stocks

    except Exception as e:
        print(f"[ERROR] 爬取 {industry_name}({industry_code}) 失败: {e}")
        _mark_ths_unavailable()
        return _fetch_industry_stocks_em(industry_name)


# ──────────────────────────── 统一入口 ────────────────────────────

def get_stock_kline_sina(
    stock_code: str,
    days: int = 120,
    *,
    max_rounds: int = 3,
    retry_interval: float = 3.0,
) -> Optional[pd.DataFrame]:
    """
    获取 A 股日线数据，按优先级尝试：
    新浪 → 东方财富 → 腾讯证券 → 东财备用

    Args:
        stock_code: 6 位股票代码
        days: 返回最近天数
        max_rounds: 所有源均失败时重试轮数
        retry_interval: 轮次间等待秒数

    Returns:
        DataFrame（含 date/open/high/low/close/volume/pct_change）或 None
    """
    stock_code = str(stock_code).strip()
    if not stock_code.isdigit() or len(stock_code) != 6:
        print(f"[KLINE] 无效代码: {stock_code}")
        return None

    sources = [
        ('新浪',   _fetch_sina),
        ('东方财富', _fetch_em),
        ('腾讯',   _fetch_tx),
        ('东财备用', _fetch_em2),
    ]

    for round_idx in range(max_rounds):
        for name, fetcher in sources:
            df = fetcher(stock_code, days)
            if df is not None and len(df) > 0:
                if round_idx > 0:
                    print(f"[KLINE] {stock_code} 第 {round_idx + 1} 轮重试成功（{name}）")
                return df
            print(f"[KLINE] {stock_code} 数据源 {name} 不可用，尝试下一个…")

        if round_idx < max_rounds - 1:
            print(f"[KLINE] {stock_code} 第 {round_idx + 1} 轮全部失败，{retry_interval}s 后重试…")
            time.sleep(retry_interval)

    print(f"[KLINE] {stock_code} 共 {max_rounds} 轮均失败，返回 None")
    return None


# ──────────────────────────── 以下为原有代码（保留） ────────────────────────────

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
    cols = {
        '序号': range(1, len(df_em) + 1),
        '板块': df_em['板块名称'],
        '代码': df_em['板块代码'],
        '涨跌幅': df_em['涨跌幅'].astype(float),
        '上涨家数': df_em['上涨家数'].astype(int),
        '下跌家数': df_em['下跌家数'].astype(int),
        '领涨股': df_em['领涨股票'],
        '领涨股-涨跌幅': df_em['领涨股票-涨跌幅'].astype(float),
    }
    if '成交额' in df_em.columns:
        cols['成交额'] = df_em['成交额'].astype(float)
    df = pd.DataFrame(cols)
    return df


def get_industry_list() -> pd.DataFrame:
    """获取行业板块列表，优先 THS，降级东方财富"""
    if _is_ths_available():
        return _get_ths_industry_list()

    print("[INDUSTRY] THS 不可用，切换东方财富接口")
    return _get_industry_list_em()


# 兼容旧调用名（定义在用它的函数之后，所以用此别名指向同名函数）
def get_ths_industry_list() -> pd.DataFrame:
    """同 get_industry_list，保留旧名兼容"""
    return get_industry_list()


def _get_ths_industry_list() -> pd.DataFrame:
    """使用 THS 接口获取行业板块列表"""
    if not _is_ths_available():
        return _get_industry_list_em()

    url = 'https://q.10jqka.com.cn/thshy/'

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        resp.encoding = 'gbk'

        from bs4 import BeautifulSoup
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
        code_map = {}
        for _, row in df.iterrows():
            name = str(row.get('板块名称', '')).strip()
            code = str(row.get('板块代码', '')).strip()
            if name and code:
                code_map[name] = code
        return code_map
    except Exception as e:
        print(f"[WARN] 获取 THS 行业代码映射失败: {e}")
        return {}


def _parse_int(s):
    try:
        return int(s.replace(',', ''))
    except:
        return 0


def _parse_float(s):
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


def get_hot_industries_with_stocks(top_n: int = 5) -> List[Dict]:
    """
    获取热点行业及其成分股（完整流程）

    Args:
        top_n: 获取前N个热点行业

    Returns:
        List[Dict]: [{
            'name': 行业名称,
            'code': 行业代码,
            'pct_change': 涨跌幅,
            'stocks': [{'code': '001257', 'name': 'XX股', 'pct_change': 2.5}, ...]
        }, ...]
    """
    # 获取所有行业
    industry_df = get_industry_list()
    if industry_df is None or industry_df.empty:
        raise Exception("获取行业列表失败")

    industry_df = industry_df.sort_values(by='涨跌幅', ascending=False)
    top_industries = industry_df.head(top_n)

    result = []
    for _, industry in top_industries.iterrows():
        try:
            industry_name = industry['板块']
            industry_code = industry['代码']
            pct_change = industry['涨跌幅']

            # 获取成分股
            stocks = get_industry_stocks(industry_name)

            result.append({
                'name': industry_name,
                'code': industry_code,
                'pct_change': pct_change,
                'stocks': stocks[:20],  # 每个行业最多20只成分股
            })
        except Exception as e:
            print(f"[WARN] 处理行业 {industry['板块']} 失败: {e}")
            continue

    return result


def get_industry_stocks(industry_name: str) -> List[Dict]:
    """
    获取指定行业的成分股

    Args:
        industry_name: 行业名称

    Returns:
        List[Dict]: 成分股列表
    """
    try:
        df = ak.stock_board_industry_cons_em(symbol=industry_name)
        if df is None or df.empty:
            return []

        stocks = []
        for _, row in df.iterrows():
            try:
                stock = {
                    'code': str(row.get('代码', '')).strip(),
                    'name': str(row.get('名称', '')).strip(),
                    'pct_change': float(row.get('涨跌幅', 0) or 0),
                }
                if stock['code']:
                    stocks.append(stock)
            except Exception:
                continue

        # 按涨跌幅排序
        stocks.sort(key=lambda x: x['pct_change'], reverse=True)
        return stocks

    except Exception as e:
        print(f"[WARN] 获取行业 {industry_name} 成分股失败: {e}")
        return []
