"""
题材获取模块 - 复用布林带项目的同花顺数据源
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


def _get_cached(key):
    if key in _cache and time.time() - _cache_time.get(key, 0) < CACHE_TTL:
        return _cache[key]
    return None


def _set_cache(key, value):
    _cache[key] = value
    _cache_time[key] = time.time()


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


def fetch_theme_history(theme_code: str) -> dict:
    """获取板块历史数据（简化版，基于同花顺数据）"""
    return {
        "days": [],
        "continuous_up": 0,
        "continuous_inflow": 0,
        "total_change_3d": 0,
        "total_inflow_3d": 0,
        "is_hot": False,
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
        history = fetch_theme_history(code)

        score = 0
        score += t.get("change_pct", 0) * 5
        score += min(t.get("up_count", 0), 50)

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
