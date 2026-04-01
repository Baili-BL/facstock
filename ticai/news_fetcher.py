# 财经新闻抓取模块
# 支持多数据源：新浪财经、同花顺、东方财富

import json as _json
import time
import re
import requests
from datetime import datetime, date, time as dt_time
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import akshare as ak
except ImportError:
    ak = None

# 请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

# 缓存
_news_cache = {}
_cache_time = {}
NEWS_CACHE_TTL = 180  # 3分钟缓存（内存缓存，用于单次会话内快速返回）
DB_CACHE_TTL = 30 * 60  # 30分钟（数据库缓存TTL）

# 重大利好关键词
POSITIVE_KEYWORDS = [
    # 政策利好
    "国务院", "发改委", "工信部", "央行", "证监会", "财政部",
    "政策支持", "扶持", "补贴", "减税", "降费", "利好",
    "战略", "规划", "意见", "通知", "指导",
    # 行业利好
    "突破", "首发", "首创", "领先", "第一", "龙头",
    "订单", "中标", "签约", "合作", "战略协议",
    "业绩预增", "净利润增长", "营收增长", "超预期",
    "涨价", "提价", "供不应求", "产能紧张",
    # 资金利好
    "增持", "回购", "举牌", "入股", "并购", "重组",
    "北向资金", "外资买入", "机构调研",
]

# 重大利空关键词
NEGATIVE_KEYWORDS = [
    "下跌", "暴跌", "大跌", "跳水", "崩盘",
    "减持", "清仓", "抛售", "套现",
    "亏损", "下滑", "下降", "业绩变脸",
    "处罚", "罚款", "违规", "调查", "立案",
    "退市", "ST", "*ST", "风险警示",
    "诉讼", "仲裁", "纠纷",
]

# 股票名称常见后缀（用于清洗）
STOCK_NAME_SUFFIXES = ["股份", "科技", "电子", "集团", "新材", "智能", "信息", "网络", "软件", "医药", "生物", "能源", "电气", "机械", "材料"]


def _get_cached(key):
    if key in _news_cache and time.time() - _cache_time.get(key, 0) < NEWS_CACHE_TTL:
        return _news_cache[key]
    return None


def _set_cache(key, value):
    _news_cache[key] = value
    _cache_time[key] = time.time()


# ============ 多源新闻获取 ============

def fetch_jinshi_news(limit: int = 30) -> List[Dict]:
    """
    金十数据「市场快讯」（与官网首页 tab 一致，channel=-8200）。
    注意：须使用 /get_flash_list（非 /v1/…），并带 x-app-id，否则易 502 或空数据。
    """
    news_list: List[Dict] = []
    seen_keys: set = set()
    cap = min(50, max(1, limit))

    def _extract_flash_items(resp: dict) -> List[dict]:
        """兼容官网 get_flash_list 与旧版 v1 包一层 data 的结构。"""
        if not isinstance(resp, dict):
            return []
        if resp.get("status") == 200:
            raw = resp.get("data")
            if isinstance(raw, list):
                return raw
            if isinstance(raw, dict) and isinstance(raw.get("data"), list):
                return raw["data"]
        raw = resp.get("data")
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict) and isinstance(raw.get("data"), list):
            return raw["data"]
        return []

    try:
        from curl_cffi import requests as cr

        s = cr.Session()
        s.headers.update(
            {
                "User-Agent": HEADERS["User-Agent"],
                "Referer": "https://www.jin10.com/",
                "Origin": "https://www.jin10.com",
                "Accept": "application/json, text/plain, */*",
                "x-app-id": "bVBF4FyRTn5NJF5n",
                "x-version": "1.0.0",
            }
        )
        params = {"channel": "-8200", "limit": str(cap), "max_time": ""}
        r = s.get(
            "https://flash-api.jin10.com/get_flash_list",
            params=params,
            impersonate="chrome110",
            timeout=12,
        )
        items: List[dict] = []
        if r.status_code == 200:
            try:
                items = _extract_flash_items(r.json())
            except Exception:
                items = []
        if not items:
            r2 = s.get(
                "https://flash-api.jin10.com/v1/get_flash_list",
                params=params,
                impersonate="chrome110",
                timeout=12,
            )
            if r2.status_code == 200:
                try:
                    items = _extract_flash_items(r2.json())
                except Exception:
                    items = []

        for item in items:
            if len(news_list) >= limit:
                break
            inner = item.get("data") if isinstance(item.get("data"), dict) else {}
            title_txt = str(inner.get("title", "") or "").strip()
            content_txt = str(inner.get("content", "") or "").strip()
            if not title_txt and content_txt:
                title_txt = content_txt[:100]
            if not title_txt:
                continue
            key = title_txt[:40].strip()
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)

            ts = ""
            tstr = item.get("time", "")
            if isinstance(tstr, str) and len(tstr) >= 19:
                try:
                    ts = str(
                        int(datetime.strptime(tstr[:19], "%Y-%m-%d %H:%M:%S").timestamp())
                    )
                except Exception:
                    ts = ""
            link = str(inner.get("link") or inner.get("source_link") or "").strip()
            fid = item.get("id", "")
            if not link and fid:
                link = f"https://flash.jin10.com/detail/{fid}"

            news_list.append(
                {
                    "title": title_txt[:200],
                    "content": content_txt[:1200] or title_txt[:200],
                    "time": ts,
                    "source": "金十数据",
                    "url": link,
                }
            )
    except Exception as e:
        print(f"金十数据获取失败: {e}")
    return news_list


def fetch_akshare_news(limit: int = 30) -> List[Dict]:
    """
    akshare 快讯聚合（3个来源均通过 curl_cffi 避免风控拦截）：
    1. 东方财富全球快讯（ak.stock_info_global_em）
    2. 富途牛牛快讯（ak.stock_info_global_futu）
    3. 新浪7x24快讯（ak.stock_info_global_sina）
    """
    news_list: List[Dict] = []
    if ak is None:
        return news_list

    seen_keys: set = set()

    def add_unique(item: Dict) -> bool:
        key = (item.get("title") or "")[:40].strip()
        if not key or key in seen_keys:
            return False
        seen_keys.add(key)
        news_list.append(item)
        return True

    # ── 东方财富全球快讯 ───────────────────────────────────────────────
    try:
        df_em = ak.stock_info_global_em()
        if df_em is not None and not df_em.empty:
            for _, row in df_em.iterrows():
                pub_time = row.get("发布时间", "")
                if hasattr(pub_time, "strftime"):
                    ts = str(int(pub_time.timestamp()))
                elif isinstance(pub_time, str) and pub_time:
                    try:
                        ts = str(int(datetime.strptime(pub_time[:19], "%Y-%m-%d %H:%M:%S").timestamp()))
                    except Exception:
                        ts = ""
                else:
                    ts = ""
                add_unique({
                    "title": str(row.get("标题", "") or ""),
                    "content": str(row.get("摘要", "") or ""),
                    "time": ts,
                    "source": "东财",
                    "url": str(row.get("链接", "") or ""),
                })
    except Exception as e:
        print(f"akshare stock_info_global_em 获取失败: {e}")

    # ── 富途牛牛快讯 ────────────────────────────────────────────────
    try:
        df_futu = ak.stock_info_global_futu()
        if df_futu is not None and not df_futu.empty:
            for _, row in df_futu.iterrows():
                pub_time = row.get("发布时间", "")
                if hasattr(pub_time, "strftime"):
                    ts = str(int(pub_time.timestamp()))
                elif isinstance(pub_time, str) and pub_time:
                    try:
                        ts = str(int(datetime.strptime(pub_time[:19], "%Y-%m-%d %H:%M:%S").timestamp()))
                    except Exception:
                        ts = ""
                else:
                    ts = ""
                title = str(row.get("标题", "") or "")
                content = str(row.get("内容", "") or "")
                if not title:
                    title = content[:80]
                add_unique({
                    "title": title,
                    "content": content,
                    "time": ts,
                    "source": "东财",
                    "url": str(row.get("链接", "") or ""),
                })
    except Exception as e:
        print(f"akshare stock_info_global_futu 获取失败: {e}")

    # ── 新浪7x24快讯 ────────────────────────────────────────────────
    try:
        df_sina = ak.stock_info_global_sina()
        if df_sina is not None and not df_sina.empty:
            for _, row in df_sina.iterrows():
                pub_time = row.get("时间", "")
                if hasattr(pub_time, "strftime"):
                    ts = str(int(pub_time.timestamp()))
                elif isinstance(pub_time, str) and pub_time:
                    try:
                        ts = str(int(datetime.strptime(pub_time[:19], "%Y-%m-%d %H:%M:%S").timestamp()))
                    except Exception:
                        ts = ""
                else:
                    ts = ""
                content = str(row.get("内容", "") or "")
                add_unique({
                    "title": content[:80],
                    "content": content,
                    "time": ts,
                    "source": "东财",
                    "url": "",
                })
    except Exception as e:
        print(f"akshare stock_info_global_sina 获取失败: {e}")

    return news_list


def fetch_sina_news(limit: int = 30) -> List[Dict]:
    """新浪财经"""
    news_list = []
    try:
        url = 'https://feed.mix.sina.com.cn/api/roll/get'
        params = {'pageid': '153', 'lid': '2516', 'num': str(limit), 'page': '1'}
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get('result', {}).get('data', [])[:limit]:
                news_list.append({
                    "title": item.get('title', ''),
                    "content": item.get('intro', '') or item.get('title', ''),
                    "time": item.get('ctime', ''),
                    "source": "新浪"
                })
    except Exception as e:
        print(f"新浪财经获取失败: {e}")
    return news_list


def fetch_ths_news(limit: int = 30) -> List[Dict]:
    """同花顺"""
    news_list = []
    try:
        url = 'https://news.10jqka.com.cn/tapp/news/push/stock/'
        params = {'page': '1', 'tag': '', 'track': 'website', 'pagesize': str(limit)}
        resp = requests.get(url, headers={**HEADERS, 'Referer': 'https://news.10jqka.com.cn/'}, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get('data', {}).get('list', [])[:limit]:
                news_list.append({
                    "title": item.get('title', ''),
                    "content": item.get('digest', '') or item.get('title', ''),
                    "time": item.get('ctime', ''),
                    "source": "同花顺"
                })
    except Exception as e:
        print(f"同花顺获取失败: {e}")
    return news_list


def _row_stock_news_em_to_item(row) -> Dict:
    """akshare stock_news_em 单行 → 统一字典，来源固定东财。"""
    pub_time = row.get("发布时间", "")
    if isinstance(pub_time, (datetime, dt_time)):
        ts = int(pub_time.timestamp()) if hasattr(pub_time, "timestamp") else 0
        time_str = str(ts)
    elif hasattr(pub_time, "timestamp"):
        time_str = str(int(pub_time.timestamp()))
    elif isinstance(pub_time, str) and pub_time:
        try:
            time_str = str(int(datetime.strptime(pub_time[:19], "%Y-%m-%d %H:%M:%S").timestamp()))
        except Exception:
            time_str = ""
    else:
        time_str = ""
    return {
        "title": str(row.get("新闻标题", "") or ""),
        "content": str(row.get("新闻内容", "") or ""),
        "time": time_str,
        "source": "东财",
        "url": str(row.get("新闻链接", "") or ""),
    }


def fetch_eastmoney_news(limit: int = 30) -> List[Dict]:
    """
    东方财富个股资讯：多代码轮询 ak.stock_news_em（内部 curl_cffi，易通过风控）。
    单代码仅约 10 条/次，需多只标的凑够 limit；与前端「东财」Tab 一致。
    """
    news_list: List[Dict] = []
    if ak is None:
        return news_list
    symbols = ["603777", "000001", "600519", "300750", "601318", "688981", "300059"]
    seen_title: set = set()
    for sym in symbols:
        if len(news_list) >= limit:
            break
        try:
            df = ak.stock_news_em(symbol=sym)
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                if len(news_list) >= limit:
                    break
                item = _row_stock_news_em_to_item(row)
                key = (item.get("title") or "")[:40].strip()
                if not key or key in seen_title:
                    continue
                seen_title.add(key)
                news_list.append(item)
        except Exception as e:
            print(f"东财 stock_news_em({sym}) 失败: {e}")
    return news_list


def fetch_xueqiu_news(limit: int = 30) -> List[Dict]:
    """
    雪球精选资讯：curl_cffi 维持会话通过风控，
    使用 public_timeline_by_category.json（category=106），避免 news.json 的 400016 错误。
    """
    news_list: List[Dict] = []
    seen_keys: set = set()
    try:
        from curl_cffi import requests as cr
        s = cr.Session()
        s.headers["User-Agent"] = HEADERS["User-Agent"]
        s.headers["Referer"] = "https://xueqiu.com/"
        r = s.get(
            "https://xueqiu.com/v4/statuses/public_timeline_by_category.json",
            params={"since_id": -1, "max_id": -1, "count": min(limit, 20), "category": 106},
            impersonate="chrome110",
            timeout=10,
        )
        if r.status_code == 200:
            d = r.json()
            for raw_item in (d.get("list") or [])[:limit]:
                try:
                    inner = _json.loads(raw_item.get("data", "{}"))
                except Exception:
                    inner = {}
                title = inner.get("title", "") or ""
                description = inner.get("description", "") or ""
                post_id = inner.get("id", "")
                created = inner.get("created_at", 0)
                ts = str(int(created / 1000)) if isinstance(created, (int, float)) else ""
                key = title[:40].strip()
                if not key or key in seen_keys:
                    continue
                seen_keys.add(key)
                news_list.append({
                    "title": title,
                    "content": description,
                    "time": ts,
                    "source": "雪球",
                    "url": f"https://xueqiu.com/{post_id}" if post_id else "",
                })
    except Exception as e:
        print(f"雪球直采获取失败: {e}")
    return news_list


def fetch_cls_news_cn(limit: int = 30) -> List[Dict]:
    """财联社快讯（nodeapi/telegraphList，每次取3页共60条）"""
    news_list = []
    try:
        # page 参数必须递增才能翻页；每页 20 条
        for page in range(1, 4):
            url = (
                'https://www.cls.cn/nodeapi/telegraphList'
                '?app=CLS&os=web&sv=7.8.5&width=750'
                f'&type=102&page={page}&size=20'
            )
            resp = requests.get(url, headers={**HEADERS, 'Referer': 'https://www.cls.cn/'}, timeout=10)
            if resp.status_code != 200:
                break
            data = resp.json()
            roll = data.get('data', {}).get('roll_data', []) if isinstance(data.get('data'), dict) else []
            if not roll:
                break
            for item in roll:
                ctime = item.get('ctime', 0)
                content_raw = str(item.get('content', '') or '')
                title_raw = str(item.get('title', '') or '').strip()
                # 去掉【标题】财联社X月X日电， 前缀
                content_clean = re.sub(r'^【[^】]+】财联社\d+月\d+日电[，,、]?', '', content_raw)
                title_clean = re.sub(r'^【[^】]+】', '', title_raw).strip()
                # title 为空时用 content 代替
                if not title_clean and content_clean:
                    title_clean = content_clean[:80]
                if not title_clean:
                    continue
                # cls.cn 的 author 字段大多为空，统一用「财联社」作为来源标识
                news_list.append({
                    "title": title_clean[:150],
                    "content": content_clean[:300],
                    "time": str(int(ctime)) if ctime else '',
                    "source": "财联社",
                })
            if len(news_list) >= limit:
                break
    except Exception as e:
        print(f"财联社 fetch_cls_news_cn 获取失败: {e}")
    return news_list


def fetch_cls_akshare_news(limit: int = 30) -> List[Dict]:
    """akshare 财联社快讯（ak.stock_info_global_cls，来源标注为财联社）"""
    news_list = []
    if ak is None:
        return news_list
    try:
        df = ak.stock_info_global_cls(symbol="全部")
        if df is not None and not df.empty:
            for _, row in df.head(limit).iterrows():
                # 列名：标题 / 内容 / 发布日期 / 发布时间
                # 发布时间 是 datetime.time 对象，发布日期 是 date 对象
                pub_date = row.get('发布日期', None)
                pub_time = row.get('发布时间', None)
                if pub_date is not None and pub_time is not None:
                    try:
                        dt = datetime.combine(pub_date, pub_time)
                        ts = str(int(dt.timestamp()))
                    except Exception:
                        ts = ''
                elif isinstance(pub_time, str) and pub_time:
                    try:
                        ts = str(int(datetime.strptime(pub_time, '%H:%M:%S').timestamp()))
                    except Exception:
                        ts = ''
                else:
                    ts = ''
                title_val = str(row.get('标题', '') or '')
                content_val = str(row.get('内容', '') or '')
                news_list.append({
                    "title": title_val,
                    "content": content_val,
                    "time": ts,
                    "source": "财联社",
                })
    except Exception as e:
        print(f"akshare stock_info_global_cls 获取失败: {e}")
    return news_list


def fetch_all_news(limit_per_source: int = 30, force: bool = False) -> List[Dict]:
    """
    并发获取多源新闻（8个平台）
    策略：
    1. 非 force：优先从数据库读取近 7 日已入库新闻，命中则直接返回（含昨日等历史）
    2. 否则并发抓取各平台，去重后回存数据库，再返回
    force=True：跳过 DB 短路与本条内存缓存，强制重新抓取并写库。
    """
    if force:
        key = f"all_news_{limit_per_source}"
        _news_cache.pop(key, None)
        _cache_time.pop(key, None)

    # ── 1. 查数据库缓存（近 7 日，含昨日；force 时跳过以便真正拉新） ───────
    if not force:
        try:
            import database
            cached = database.get_cached_news(days=7)
            if cached:
                # 按时间排序
                def parse_time(item):
                    t = str(item.get('time') or '')
                    if t.isdigit():
                        return int(t)
                    try:
                        return int(datetime.strptime(t, '%Y-%m-%d %H:%M:%S').timestamp())
                    except Exception:
                        return 0
                cached.sort(key=parse_time, reverse=True)
                _set_cache(f"all_news_{limit_per_source}", cached)
                print(f"📰 新闻聚合完成: 共{len(cached)}条 (来自数据库缓存)")
                return cached
        except Exception as e:
            print(f"[WARN] 数据库缓存读取失败: {e}")

    # ── 2. 无缓存或 force，并发抓取 ─────────────────────────────────────
    all_news = []

    # 并发获取8个平台（含两路财联社 + 金十数据）
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(fetch_akshare_news, limit_per_source): "akshare",
            executor.submit(fetch_sina_news, limit_per_source): "新浪",
            executor.submit(fetch_ths_news, limit_per_source): "同花顺",
            executor.submit(fetch_eastmoney_news, limit_per_source): "东财",
            executor.submit(fetch_cls_news_cn, limit_per_source): "财联社(cls直采)",
            executor.submit(fetch_cls_akshare_news, limit_per_source): "财联社(akshare)",
            executor.submit(fetch_xueqiu_news, limit_per_source): "雪球",
            executor.submit(fetch_jinshi_news, limit_per_source): "金十数据",
        }

        # 不设 as_completed 总超时：慢源（akshare/外网）常 >20s，否则会抛
        # TimeoutError「N (of M) futures unfinished」导致整接口失败。
        for future in as_completed(futures):
            source = futures[future]
            try:
                news = future.result()
                if news:
                    all_news.extend(news)
                    print(f"  {source}: {len(news)}条")
                else:
                    print(f"  {source}: 无数据")
            except Exception as e:
                print(f"  {source}获取失败: {e}")

    # ── 3. 去重 & 排序 ─────────────────────────────────────────────────
    seen_titles = set()
    unique_news = []
    for news_item in all_news:
        title = news_item.get('title', '')[:40].strip()
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_news.append(news_item)

    # 按时间倒序（兼容 Unix 时间戳字符串 和 'YYYY-MM-DD HH:MM:SS' 字符串）
    def parse_time(item):
        t = str(item.get('time') or '')
        if t.isdigit():
            return int(t)
        try:
            from datetime import datetime
            return int(datetime.strptime(t, '%Y-%m-%d %H:%M:%S').timestamp())
        except Exception:
            return 0

    unique_news.sort(key=parse_time, reverse=True)

    if unique_news:
        _set_cache(f"all_news_{limit_per_source}", unique_news)
        # ── 4. 回存数据库（去重写入） ─────────────────────────────────
        try:
            import database
            saved = database.save_news_items(unique_news)
            print(f"📰 新闻聚合完成: 共{len(unique_news)}条 (去重后), 新增入库{saved}条")
        except Exception as e:
            print(f"[WARN] 新闻入库失败: {e}")
            print(f"📰 新闻聚合完成: 共{len(unique_news)}条 (去重后)")

    return unique_news


def fetch_cls_news(limit: int = 50) -> List[Dict]:
    """
    获取财经新闻（多源聚合）
    """
    return fetch_all_news(limit // 2)  # 每个源取一半


def analyze_news_sentiment(news_list: List[Dict]) -> Dict:
    """
    分析新闻整体情绪
    """
    if not news_list:
        return {"sentiment": "neutral", "score": 50, "positive_count": 0, "negative_count": 0}
    
    positive_count = 0
    negative_count = 0
    
    for news in news_list:
        content = news.get("content", "") + news.get("title", "")
        
        has_positive = any(kw in content for kw in POSITIVE_KEYWORDS)
        has_negative = any(kw in content for kw in NEGATIVE_KEYWORDS)
        
        if has_positive:
            positive_count += 1
        if has_negative:
            negative_count += 1
    
    # 计算情绪分数 (0-100)
    total = positive_count + negative_count
    if total == 0:
        score = 50
    else:
        score = int(50 + (positive_count - negative_count) / total * 50)
    score = max(0, min(100, score))
    
    if score >= 65:
        sentiment = "positive"
    elif score <= 35:
        sentiment = "negative"
    else:
        sentiment = "neutral"
    
    return {
        "sentiment": sentiment,
        "score": score,
        "positive_count": positive_count,
        "negative_count": negative_count,
    }


def extract_theme_keywords(theme_name: str, stocks: List[Dict] = None) -> List[str]:
    """
    动态提取题材关键词，无需手动维护映射表
    
    策略：
    1. 题材名称本身
    2. 智能拆分题材名（如"卫星互联网"→"卫星互联网"、"卫星"、"互联网"）
    3. 成分股名称（去除常见后缀）
    """
    keywords = []
    
    # 1. 题材名称本身（最高优先级）
    keywords.append(theme_name)
    
    # 2. 智能拆分题材名
    if len(theme_name) >= 4:
        common_roots = ["互联", "智能", "新能", "半导", "芯片", "机器", "卫星", "低空", "量子", "生物", "医药", "军工", "消费", "金融"]
        
        for i in range(2, len(theme_name) - 1):
            part1 = theme_name[:i]
            part2 = theme_name[i:]
            
            if len(part1) >= 2 and len(part2) >= 2:
                if part1 in common_roots or part2 in common_roots or len(part1) >= 3 or len(part2) >= 3:
                    keywords.append(part1)
                    keywords.append(part2)
    
    # 3. 从成分股名称提取关键词
    if stocks:
        for stock in stocks[:8]:
            stock_name = stock.get("name", "")
            if not stock_name or len(stock_name) < 2:
                continue
            
            clean_name = stock_name
            for suffix in STOCK_NAME_SUFFIXES:
                if clean_name.endswith(suffix):
                    clean_name = clean_name[:-len(suffix)]
                    break
            
            if len(clean_name) >= 2:
                keywords.append(clean_name)
            
            if len(stock_name) >= 3:
                keywords.append(stock_name)
    
    keywords = list(set(keywords))
    keywords.sort(key=len, reverse=True)
    
    return keywords


def find_theme_related_news(theme_name: str, news_list: List[Dict], stocks: List[Dict] = None) -> List[Dict]:
    """
    查找与特定题材相关的新闻
    使用动态提取的关键词进行匹配
    """
    related_news = []
    
    # 动态提取关键词
    keywords = extract_theme_keywords(theme_name, stocks)
    
    # 搜索新闻
    for news in news_list:
        content = news.get("content", "") + news.get("title", "")
        matched_keyword = None
        
        for kw in keywords:
            # 要求关键词长度至少3个字符，避免误匹配
            if len(kw) >= 3 and kw in content:
                matched_keyword = kw
                break
            # 对于2个字的关键词，要求是题材名本身
            elif len(kw) == 2 and kw == theme_name and kw in content:
                matched_keyword = kw
                break
        
        if matched_keyword:
            # 判断是利好还是利空
            is_positive = any(pk in content for pk in POSITIVE_KEYWORDS)
            is_negative = any(nk in content for nk in NEGATIVE_KEYWORDS)
            
            related_news.append({
                "content": content[:100],
                "time": news.get("time", 0),
                "is_positive": is_positive,
                "is_negative": is_negative,
                "matched_keyword": matched_keyword,
            })
    
    return related_news[:5]  # 最多返回5条


def evaluate_theme_news_factor(theme_name: str, news_list: List[Dict] = None, stocks: List[Dict] = None) -> Dict:
    """
    评估题材的消息面因子
    返回消息面评分和相关新闻
    
    参数:
        theme_name: 题材名称
        news_list: 新闻列表（可选，不传则自动获取）
        stocks: 题材内的股票列表（用于匹配新闻）
    """
    if news_list is None:
        news_list = fetch_cls_news(50)
    
    related_news = find_theme_related_news(theme_name, news_list, stocks)
    
    if not related_news:
        return {
            "score": 50,
            "level": "中性",
            "level_color": "#95a5a6",
            "news_count": 0,
            "positive_news": 0,
            "negative_news": 0,
            "latest_news": [],
            "summary": "暂无相关消息",
        }
    
    positive_news = sum(1 for n in related_news if n.get("is_positive"))
    negative_news = sum(1 for n in related_news if n.get("is_negative"))
    
    # 计算消息面分数
    score = 50
    if positive_news > negative_news:
        score = 50 + min((positive_news - negative_news) * 15, 40)
    elif negative_news > positive_news:
        score = 50 - min((negative_news - positive_news) * 15, 40)
    
    # 判断消息面级别
    if score >= 70:
        level = "利好"
        level_color = "#2ecc71"
    elif score <= 30:
        level = "利空"
        level_color = "#e74c3c"
    else:
        level = "中性"
        level_color = "#95a5a6"
    
    # 生成摘要
    if positive_news > 0 and negative_news == 0:
        summary = f"近期有{positive_news}条利好消息"
    elif negative_news > 0 and positive_news == 0:
        summary = f"近期有{negative_news}条利空消息"
    elif positive_news > 0 and negative_news > 0:
        summary = f"利好{positive_news}条，利空{negative_news}条"
    else:
        summary = f"有{len(related_news)}条相关消息"
    
    return {
        "score": score,
        "level": level,
        "level_color": level_color,
        "news_count": len(related_news),
        "positive_news": positive_news,
        "negative_news": negative_news,
        "latest_news": [n["content"] for n in related_news[:3]],
        "matched_keywords": list(set(n["matched_keyword"] for n in related_news)),
        "summary": summary,
    }


def get_market_news_summary() -> Dict:
    """
    获取市场整体消息面摘要
    """
    news_list = fetch_cls_news(50)
    sentiment = analyze_news_sentiment(news_list)
    
    return {
        "total_news": len(news_list),
        "sentiment": sentiment["sentiment"],
        "sentiment_score": sentiment["score"],
        "positive_count": sentiment["positive_count"],
        "negative_count": sentiment["negative_count"],
        "important_positive": sentiment.get("important_positive", []),
        "important_negative": sentiment.get("important_negative", []),
    }
