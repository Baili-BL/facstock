"""
题材获取模块 - 复用布林带项目的同花顺数据源 + 东方财富概念资金流
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.ths_crawler import (
    get_ths_industry_list,
    get_ths_industry_code_map,
    fetch_ths_industry_stocks,
)
from ticai.config import MAX_WORKERS, STOCKS_PER_THEME

# 缓存
_cache = {}
_cache_time = {}
CACHE_TTL = 300

EXCLUDE_KEYWORDS = [
    "连板", "一字板", "涨停", "跌停", "打板", "首板", "二板", "三板",
    "昨日", "今日", "反包", "炸板", "烂板", "换手板", "缩量板",
    "ST板块", "摘帽", "复牌", "新股", "次新", "破净", "破发",
]

# 概念板块名称→代码缓存（避免每次请求都重新拉取）
# 注：THS 行业板块名称与东方财富行业板块名称一致（如"有色金属"、"化学制药"），
# 故使用东方财富行业板块代码（m:90+t:2）
_em_code_map = {}
_em_code_map_time = 0
_EM_CODE_MAP_TTL = 3600  # 1小时刷新一次


def _get_cached(key):
    if key in _cache and time.time() - _cache_time.get(key, 0) < CACHE_TTL:
        return _cache[key]
    return None


def _set_cache(key, value):
    _cache[key] = value
    _cache_time[key] = time.time()


def _safe_float(val, default=0.0):
    """安全转换为浮点数"""
    if val is None or val == '':
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _fetch_em_code_map() -> dict:
    """
    获取东方财富行业板块名称→代码映射（m:90+t:2）。
    THS 行业板块名称与东方财富行业板块名称一致，故直接复用。
    """
    global _em_code_map, _em_code_map_time
    if _em_code_map and time.time() - _em_code_map_time < _EM_CODE_MAP_TTL:
        return _em_code_map

    import requests
    try:
        session = requests.Session()
        session.trust_env = False
        all_items = {}
        for pn in range(1, 6):
            url = "https://push2.eastmoney.com/api/qt/clist/get"
            params = {
                "pn": pn, "pz": 100, "po": 1, "np": 1,
                "fields": "f12,f14",
                "fid": "f62",
                "fs": "m:90+t:2",  # 行业板块
                "ut": "b2884a393a59ad64002292a3e90d46a5",
                "_": int(time.time() * 1000),
            }
            resp = session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            diff = (data.get('data') or {}).get('diff') or []
            if not diff:
                break
            for r in diff:
                if r.get('f14'):
                    all_items[r['f14']] = r['f12']
            total = (data.get('data') or {}).get('total', 0)
            if pn * 100 >= total:
                break
        session.close()
        _em_code_map = all_items
        _em_code_map_time = time.time()
        print(f"[INFO] 东方财富行业板块代码映射已加载: {len(_em_code_map)} 条")
        return _em_code_map
    except Exception as e:
        print(f"[WARN] 获取东方财富行业板块代码映射失败: {e}")
        return {}


def is_valid_theme(name: str) -> bool:
    if not name:
        return False
    for kw in EXCLUDE_KEYWORDS:
        if kw in name:
            return False
    return True


def fetch_hot_themes(limit=10) -> list:
    """获取热门板块列表（同花顺行业排行）"""
    cache_key = "hot_themes"
    cached = _get_cached(cache_key)
    if cached:
        return cached[:limit]

    try:
        df = get_ths_industry_list()
        if df is None or df.empty:
            return []

        themes = []
        for _, row in df.iterrows():
            name = row.get('板块', '')
            if not is_valid_theme(name):
                continue
            themes.append({
                "code": row.get('代码', ''),
                "name": name,
                "change_pct": float(row.get('涨跌幅', 0) or 0),
                "up_count": int(row.get('上涨家数', 0) or 0),
                "down_count": int(row.get('下跌家数', 0) or 0),
            })

        _set_cache(cache_key, themes)
        return themes[:limit]
    except Exception as e:
        print(f"获取热门板块失败: {e}")
        return []


def fetch_theme_stocks(theme_code: str, theme_name: str) -> list:
    """获取板块成分股（同花顺爬虫）"""
    cache_key = f"theme_stocks_{theme_code}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        raw_stocks = fetch_ths_industry_stocks(theme_code, theme_name)
        stocks = []
        for s in raw_stocks:
            code = s.get('code', '')
            if not code:
                continue
            stocks.append({
                "code": code,
                "name": s.get('name', ''),
                "price": s.get('price', 0),
                "change_pct": s.get('change', 0),
                "change_amt": 0,
                "volume": 0,
                "amount": s.get('amount', 0),
                "amplitude": s.get('amplitude', 0),
                "high": s.get('high', 0),
                "low": s.get('low', 0),
                "open": s.get('open', 0),
                "prev_close": s.get('prev_close', 0),
                "market_cap": s.get('market_cap', 0),
                "float_cap": 0,
                "theme": theme_name,
                "turnover": s.get('turnover', 0),
                "volume_ratio": s.get('volume_ratio', 0),
            })

        _set_cache(cache_key, stocks)
        return stocks
    except Exception as e:
        print(f"获取板块 {theme_name} 成分股失败: {e}")
        return []


def fetch_theme_history(theme_code: str, theme_name: str = '') -> dict:
    """
    获取板块历史资金流数据。
    先尝试概念板块历史资金流（东方财富 akshare），若匹配则返回完整数据；
    否则返回简化版。
    """
    if not theme_name:
        return {
            "days": [],
            "continuous_up": 0,
            "continuous_inflow": 0,
            "total_change_3d": 0,
            "total_inflow_3d": 0,
            "is_hot": False,
        }

    cache_key = f"theme_history_{theme_code}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    # 尝试用东方财富 stock_concept_fund_flow_hist 获取概念板块历史资金流
    history = _fetch_concept_history_em(theme_name)
    if history:
        _set_cache(cache_key, history)
        return history

    # 降级：返回简化数据
    result = {
        "days": [],
        "continuous_up": 0,
        "continuous_inflow": 0,
        "total_change_3d": 0,
        "total_inflow_3d": 0,
        "is_hot": False,
    }
    _set_cache(cache_key, result)
    return result


def _fetch_concept_history_em(theme_name: str) -> dict:
    """
    使用东方财富 API 获取行业板块历史资金流。
    板块历史资金流接口：https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get
    返回格式：[{date, net_inflow, net_pct, ...}, ...]
    """
    import requests

    # 获取行业板块代码映射（与东方财富行业板块名称一致）
    code_map = _fetch_em_code_map()
    bk_code = code_map.get(theme_name)
    if not bk_code:
        return {}

    try:
        session = requests.Session()
        session.trust_env = False
        rt = int(time.time() * 1000)
        url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
        params = {
            "lmt": "0",
            "klt": "101",
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            "secid": f"90.{bk_code}",
            "_": rt,
        }
        resp = session.get(url, params=params, timeout=10)
        session.close()
        resp.raise_for_status()
        data = resp.json()
        klines = (data.get('data') or {}).get('klines') or []
        if not klines:
            return {}
    except Exception as e:
        print(f"[WARN] 东方财富概念历史资金流获取失败 ({theme_name}): {e}")
        return {}

    # 解析 K 线数据
    # 格式: date, 主力净额, 小单净额, 中单净额, 大单净额, 超大单净额,
    #       主力净占比, 小单净占比, 中单净占比, 大单净占比, 超大单净占比,
    #       板块涨跌幅, 主力流入, 主力流出
    try:
        days = []
        for kline in klines:
            parts = kline.split(',')
            if len(parts) < 14:
                continue
            date_str = parts[0]
            main_net = _safe_float(parts[1])      # 主力净流入(元)
            main_ratio = _safe_float(parts[6])     # 主力净流入-净占比(%)
            # sector_change: 取 field 12（index 12），这是板块涨跌幅(%)
            # index 11 是板块收盘点位（数值很大，如 27634），不是涨跌幅
            sector_change = _safe_float(parts[12])
            main_in = _safe_float(parts[12])       # 主力流入(元)
            main_out = _safe_float(parts[13])       # 主力流出(元)

            days.append({
                'date': date_str,
                'main_net_yuan': main_net,
                'main_net_yi': round(main_net / 1e8, 4),
                'main_ratio': main_ratio,
                'sector_change': sector_change,
                'main_in_yi': round(main_in / 1e8, 4),
                'main_out_yi': round(main_out / 1e8, 4),
            })
    except Exception as e:
        print(f"[WARN] 解析概念历史资金流数据失败 ({theme_name}): {e}")
        return {}

    if not days:
        return {}

    # 计算连续上涨/流入
    n = len(days)
    continuous_up = 0
    continuous_inflow = 0

    # 从最近往前数连续上涨天数
    for i in range(n - 1, -1, -1):
        if days[i].get('sector_change', 0) > 0:
            continuous_up += 1
        else:
            break

    # 从最近往前数连续资金净流入天数
    for i in range(n - 1, -1, -1):
        if days[i].get('main_net_yuan', 0) > 0:
            continuous_inflow += 1
        else:
            break

    # 计算3日累计涨跌和累计净流入
    recent = days[-3:] if len(days) >= 3 else days
    total_change_3d = sum(d.get('sector_change', 0) for d in recent)
    total_inflow_3d = sum(d.get('main_net_yuan', 0) for d in recent)

    # 判断是否热门（连续2天以上净流入 + 累计涨幅 > 3%）
    is_hot = continuous_inflow >= 2 and total_change_3d > 3

    return {
        "days": days[-20:],  # 保留最近20天
        "continuous_up": continuous_up,
        "continuous_inflow": continuous_inflow,
        "total_change_3d": round(total_change_3d, 2),
        "total_inflow_3d": round(total_inflow_3d / 1e8, 2),  # 转为亿
        "is_hot": is_hot,
    }


def fetch_all_themes_with_stocks(theme_limit=8) -> dict:
    """并发获取所有热门板块及其股票"""
    themes = fetch_hot_themes(theme_limit + 5)
    if not themes:
        return {}

    result = {}

    # 并发获取成分股
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        stock_futures = {
            executor.submit(fetch_theme_stocks, t["code"], t["name"]): t
            for t in themes
        }

        stock_results = {}
        for future in as_completed(stock_futures):
            theme = stock_futures[future]
            try:
                stocks = future.result()
                stock_results[theme["code"]] = stocks
            except Exception as e:
                print(f"获取股票失败 {theme['name']}: {e}")
                stock_results[theme["code"]] = []

    # 组装结果，按涨跌幅排序
    theme_scores = []
    for t in themes:
        code = t["code"]
        name = t["name"]
        history = fetch_theme_history(code, name)

        score = 0
        score += t.get("change_pct", 0) * 5
        score += min(t.get("up_count", 0), 50)
        # 资金流入加分
        if history.get("continuous_inflow", 0) >= 2:
            score += history["continuous_inflow"] * 3
        if history.get("total_change_3d", 0) > 5:
            score += 10

        theme_scores.append((t, score, history))

    theme_scores.sort(key=lambda x: x[1], reverse=True)

    for t, score, history in theme_scores[:theme_limit]:
        code = t["code"]
        stocks = stock_results.get(code, [])

        result[t["name"]] = {
            "info": t,
            "stocks": stocks[:STOCKS_PER_THEME],
            "history": history,
            "hot_score": round(score, 1),
        }

    return result
