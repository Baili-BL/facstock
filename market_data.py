#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大盘数据模块 - 提供市场概览、资金流向、涨跌停等数据

数据源策略：
- 东方财富 eastmoney.com（部分接口可能需要代理）
- 同花顺 q.10jqka.com.cn（行业板块）
- 沪深港通数据（北向资金）
- 涨跌停池数据
"""

import contextlib
import concurrent.futures
import json
import os
import time
import pandas as pd
import requests
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

from cache import set as cache_layer_set

logger = logging.getLogger(__name__)

# 与 market_routes.SNAPSHOT_REDIS_KEY 保持一致（东财后台线程需回写 Redis，否则一直命中「仅新浪、涨跌家数为 0」的快照）
MARKET_SNAPSHOT_REDIS_KEY = 'market/snapshot/v2'


def _get_ak():
    """Lazy import of akshare to avoid py_mini_racer crash on import."""
    import akshare as _ak
    return _ak


@contextlib.contextmanager
def _no_http_proxy_env():
    """临时清除环境变量中的代理（含 SOCKS），减轻无效本地代理对东方财富请求的影响。"""
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
def _requests_session_no_proxy_env():
    """
    临时让 requests 的 Session 默认 trust_env=False，绕过系统/环境代理。
    requests.api.request 使用的是 sessions.Session()（非 requests.Session 名），必须改 sessions 模块里的类。
    """
    import requests.sessions as _rsess

    _orig = _rsess.Session

    def _Session_trust_env_off(*args, **kwargs):
        s = _orig(*args, **kwargs)
        s.trust_env = False
        return s

    _rsess.Session = _Session_trust_env_off  # type: ignore[assignment]
    requests.Session = _Session_trust_env_off  # type: ignore[assignment]
    try:
        yield
    finally:
        _rsess.Session = _orig  # type: ignore[assignment]
        requests.Session = _orig  # type: ignore[assignment]


def _is_proxy_related_error(exc: BaseException) -> bool:
    e: Optional[BaseException] = exc
    while e is not None:
        if isinstance(e, requests.exceptions.ProxyError):
            return True
        if 'proxy' in type(e).__name__.lower():
            return True
        e = e.__cause__ or e.__context__
    msg = str(exc).lower()
    return 'proxy' in msg or 'unable to connect to proxy' in msg


@contextlib.contextmanager
def _ak_eastmoney_direct():
    """东方财富 akshare 请求：绕过无效系统代理（与板块资金流一致）。"""
    with _no_http_proxy_env(), _requests_session_no_proxy_env():
        yield


@contextlib.contextmanager
def _ak_sina_direct():
    """新浪 akshare 请求：同样绕过无效系统代理。"""
    with _no_http_proxy_env(), _requests_session_no_proxy_env():
        yield


# 缓存相关
_cache = {}
_cache_timeout = 30  # 30秒，与 Redis TTL 保持一致
_cache_timeout_overrides = {
    'limit_up': 10,  # 涨跌停对比盘中需要更灵敏
}


def _get_cached(key: str) -> Optional[any]:
    """获取缓存数据"""
    if key in _cache:
        data, timestamp = _cache[key]
        ttl = _cache_timeout_overrides.get(key, _cache_timeout)
        if datetime.now().timestamp() - timestamp < ttl:
            return data
    return None


def _set_cached(key: str, data: any):
    """设置缓存数据"""
    _cache[key] = (data, datetime.now().timestamp())


# 历史数据持久化存储路径（使用绝对路径）
_THEME_HISTORY_DIR = '/Users/kevin/Desktop/facSstock/data/theme_history'


def _ensure_history_dir():
    """确保历史数据目录存在"""
    os.makedirs(_THEME_HISTORY_DIR, exist_ok=True)


def _get_theme_history_file(date: str) -> str:
    """获取指定日期的历史数据文件路径"""
    _ensure_history_dir()
    return os.path.join(_THEME_HISTORY_DIR, f'{date}.json')


def load_theme_history_by_date(date: str) -> Optional[Dict]:
    """从磁盘读取指定日期的历史题材数据"""
    filepath = _get_theme_history_file(date)
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f'读取历史题材数据失败 {date}: {e}')
        return None


def save_theme_history_by_date(date: str, data: Dict) -> bool:
    """保存指定日期的历史题材数据到磁盘"""
    filepath = _get_theme_history_file(date)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.warning(f'保存历史题材数据失败 {date}: {e}')
        return False


def _safe_float(val, default: float = 0.0) -> float:
    """安全转换为浮点数"""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _get_qwen_api_key() -> str:
    """获取 Qwen / DashScope API Key。"""
    return os.environ.get('DASHSCOPE_API_KEY', '') or os.environ.get('QWEN_API_KEY', '')


def _fetch_limit_counts_from_qwen() -> Optional[Tuple[int, int]]:
    """
    通过 Qwen 联网搜索获取同花顺口径的涨跌停家数。

    用户明确要求优先参考 Qwen（其背后已接同花顺数据），因此这里将其作为
    首页涨跌停家数的第一优先级。若返回不可解析或异常，则继续走后续兜底。
    """
    api_key = _get_qwen_api_key()
    if not api_key:
        return None

    try:
        import json
        import re
        import dashscope

        now = datetime.now()
        today = now.strftime('%Y年%m月%d日')
        hm = now.hour * 60 + now.minute
        is_weekday = now.weekday() < 5
        # 盘前看昨收；盘中/盘后看当前收盘或实时。
        use_live_prompt = is_weekday and hm >= (9 * 60 + 30)

        if use_live_prompt:
            user_prompt = (
                f'今天是{today}。当前A股涨跌停对比是多少？'
                '按同花顺实时口径，只回答类似 65:19 这种格式，不要解释。'
            )
        else:
            user_prompt = (
                f'今天是{today}。上一交易日A股涨跌停对比是多少？'
                '按同花顺 q.10jqka.com.cn 首页口径，只回答类似 63:15 这种格式，不要解释。'
            )

        messages = [
            {
                'role': 'system',
                'content': 'You are a helpful assistant.',
            },
            {
                'role': 'user',
                'content': user_prompt,
            },
        ]

        with _no_http_proxy_env():
            response = dashscope.Generation.call(
                api_key=api_key,
                model='qwen-plus',
                messages=messages,
                enable_search=True,
                result_format='message',
                temperature=0.0,
            )

        if getattr(response, 'status_code', None) != 200:
            logger.debug(f'Qwen 涨跌停家数获取失败: status={getattr(response, "status_code", None)}')
            return None

        content = ''
        try:
            content = response.output.choices[0].message.content or ''
        except Exception:
            content = str(response)

        # 优先解析 63:15 / 63：15 这类紧凑格式
        pair_match = re.search(r'(\d+)\s*[:：]\s*(\d+)', content)
        if pair_match:
            up_i = int(pair_match.group(1))
            down_i = int(pair_match.group(2))
            if 0 <= up_i <= 500 and 0 <= down_i <= 500:
                return up_i, down_i

        # 再兜底解析 JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                payload = json.loads(json_match.group(0))
                up = payload.get('limit_up_count')
                down = payload.get('limit_down_count')
                if up is not None and down is not None:
                    up_i = int(float(up))
                    down_i = int(float(down))
                    if 0 <= up_i <= 500 and 0 <= down_i <= 500:
                        return up_i, down_i
            except Exception:
                pass

        # 最后解析“XX只涨停、YY只跌停”
        text_match = re.search(r'(\d+)\s*只涨停[股票]*[、,， ]+(\d+)\s*只跌停', content)
        if text_match:
            up_i = int(text_match.group(1))
            down_i = int(text_match.group(2))
            if 0 <= up_i <= 500 and 0 <= down_i <= 500:
                return up_i, down_i

        logger.debug(f'Qwen 涨跌停家数解析失败: {content[:200]}')
        return None
    except Exception as e:
        logger.debug(f'Qwen 涨跌停家数获取异常: {e}')
        return None


def _extract_first_json_object(text: str) -> Optional[Dict]:
    """从模型输出中尽量提取首个 JSON 对象。"""
    if not text:
        return None

    import json
    import re

    text = str(text).strip()
    match = re.search(r'\{[\s\S]*\}', text)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _normalize_focus_topics(raw_topics) -> List[str]:
    """将模型输出的话题列表规范化为字符串数组。"""
    topics: List[str] = []
    if not isinstance(raw_topics, list):
        return topics

    for item in raw_topics:
        name = ''
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(
                item.get('name')
                or item.get('topic')
                or item.get('label')
                or item.get('板块')
                or ''
            ).strip()
        if name and name not in topics:
            topics.append(name)
    return topics[:5]


def _fallback_today_theme_summary(
    overview: List[Dict],
    snapshot: Dict,
    limit: Dict,
    sectors: List[Dict],
) -> Dict:
    """Qwen 不可用时，用本地盘面数据兜底生成『今日炒什么』。"""
    sh = next((x for x in overview if x.get('name') == '上证指数'), {})
    sh_change = float(sh.get('change', 0) or 0)
    up = int(snapshot.get('up_count', 0) or 0)
    down = int(snapshot.get('down_count', 0) or 0)
    flat = int(snapshot.get('flat_count', 0) or 0)
    limit_up = int(limit.get('limit_up_count', 0) or 0)
    limit_down = int(limit.get('limit_down_count', 0) or 0)

    focus_topics = []
    for row in sectors[:5]:
        name = str(row.get('name') or '').strip()
        if name and name not in focus_topics:
            focus_topics.append(name)

    if limit_up >= 50 and up > down:
        trade_bias = '进攻轮动'
    elif limit_down >= 12 or down > up * 1.1:
        trade_bias = '谨慎防守'
    elif limit_up >= 25:
        trade_bias = '结构轮动'
    elif focus_topics:
        trade_bias = '局部抱团'
    else:
        trade_bias = '防守观察'

    breadth_total = max(1, up + down + flat)
    breadth_bonus = ((up - down) / breadth_total) * 35
    score_raw = 52 + breadth_bonus + (limit_up - limit_down) * 0.8 + sh_change * 6
    theme_score = max(28, min(92, int(round(score_raw))))

    if focus_topics:
        topic_text = '、'.join(focus_topics[:3])
        summary_text = (
            f'今日资金主要围绕{topic_text}展开，'
            f'盘面呈现{trade_bias}特征。'
            f'当前上涨{up}家、下跌{down}家，涨停{limit_up}家、跌停{limit_down}家，'
            '更适合围绕高辨识度主线快进快出。'
        )
    else:
        summary_text = (
            f'今日盘面以{trade_bias}为主，'
            f'当前上涨{up}家、下跌{down}家，涨停{limit_up}家、跌停{limit_down}家。'
            '热点并不集中，更适合等待强主线进一步确认。'
        )

    return {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'summary_text': summary_text,
        'theme_score': theme_score,
        'trade_bias': trade_bias,
        'focus_topics': focus_topics[:5],
        'source': 'local-fallback',
    }


def compute_today_theme_summary() -> Dict:
    """
    首页专用：今日炒什么。

    优先结合本地盘面事实 + Qwen 联网搜索（参考同花顺/财经站点）生成主线摘要，
    失败时降级为本地盘面兜底摘要。
    """
    overview = get_market_overview() or []
    snapshot = get_market_snapshot() or {}
    limit = get_limit_up_data() or {}
    sectors = get_hot_sectors() or []
    fallback = _fallback_today_theme_summary(overview, snapshot, limit, sectors)

    api_key = _get_qwen_api_key()
    if not api_key:
        return fallback

    try:
        import dashscope

        sh = next((x for x in overview if x.get('name') == '上证指数'), {})
        sz = next((x for x in overview if x.get('name') == '深证成指'), {})
        cy = next((x for x in overview if x.get('name') == '创业板指'), {})

        up = int(snapshot.get('up_count', 0) or 0)
        down = int(snapshot.get('down_count', 0) or 0)
        flat = int(snapshot.get('flat_count', 0) or 0)
        limit_up = int(limit.get('limit_up_count', 0) or 0)
        limit_down = int(limit.get('limit_down_count', 0) or 0)

        sector_lines = []
        for idx, row in enumerate(sectors[:8], start=1):
            name = str(row.get('name') or '').strip()
            if not name:
                continue
            change = float(row.get('change', 0) or 0)
            leader = str(row.get('leader') or '').strip()
            leader_change = float(row.get('leader_change', 0) or 0)
            sector_lines.append(
                f'{idx}. {name} {change:+.2f}%'
                + (f'；领涨股 {leader} {leader_change:+.2f}%' if leader else '')
            )

        sector_block = '\n'.join(sector_lines) if sector_lines else '暂无可靠热门板块列表'
        today = datetime.now().strftime('%Y年%m月%d日')

        prompt = f"""今天是{today}。请结合下面给你的实时盘面事实，并联网搜索同花顺 q.10jqka.com.cn、权威财经媒体信息，总结一句首页用的『今日炒什么』。

【盘面事实】
上证指数：{float(sh.get('change', 0) or 0):+.2f}%
深证成指：{float(sz.get('change', 0) or 0):+.2f}%
创业板指：{float(cy.get('change', 0) or 0):+.2f}%
上涨家数：{up}
下跌家数：{down}
平盘家数：{flat}
涨停家数：{limit_up}
跌停家数：{limit_down}

【热门板块】
{sector_block}

请严格输出 JSON，不要 markdown，不要解释：
{{
  "summary_text": "60到100字，直接说明今天资金主要在炒什么、盘面是什么节奏",
  "theme_score": 0,
  "trade_bias": "进攻轮动/结构轮动/局部抱团/防守观察/谨慎防守",
  "focus_topics": ["题材1", "题材2", "题材3"]
}}

要求：
1. focus_topics 必须是板块/题材，不要股票名；
2. summary_text 要像交易首页摘要，不要空话；
3. theme_score 取 0-100 整数；
4. trade_bias 只能从给定选项里选；
5. 如果热点分散，也要明确写出“轮动”或“防守”。"""

        with _no_http_proxy_env():
            response = dashscope.Generation.call(
                api_key=api_key,
                model='qwen-plus',
                messages=[
                    {'role': 'system', 'content': '你是一位专业的A股盘面编辑，请用简洁准确的中文总结当日市场主线。'},
                    {'role': 'user', 'content': prompt},
                ],
                enable_search=True,
                result_format='message',
                temperature=0.2,
                max_tokens=1200,
            )

        if getattr(response, 'status_code', None) != 200:
            return fallback

        content = ''
        try:
            content = response.output.choices[0].message.content or ''
        except Exception:
            content = str(response)

        payload = _extract_first_json_object(content)
        if not payload:
            return fallback

        summary_text = str(payload.get('summary_text') or '').strip() or fallback['summary_text']
        raw_score = payload.get('theme_score', fallback['theme_score'])
        try:
            theme_score = int(round(float(raw_score)))
        except Exception:
            theme_score = int(fallback['theme_score'])
        theme_score = max(0, min(100, theme_score))

        trade_bias = str(payload.get('trade_bias') or '').strip() or str(fallback['trade_bias'])
        if trade_bias not in {'进攻轮动', '结构轮动', '局部抱团', '防守观察', '谨慎防守'}:
            trade_bias = str(fallback['trade_bias'])

        focus_topics = _normalize_focus_topics(payload.get('focus_topics')) or list(fallback['focus_topics'])

        return {
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'summary_text': summary_text,
            'theme_score': theme_score,
            'trade_bias': trade_bias,
            'focus_topics': focus_topics[:5],
            'source': 'Qwen+Search',
        }
    except Exception as e:
        logger.warning(f'compute_today_theme_summary fallback due to error: {e}')
        return fallback


def _recent_trade_days(limit: int = 5) -> List[str]:
    """最近 N 个交易日（简单按工作日回溯，不处理节假日）。"""
    days: List[str] = []
    cursor = datetime.now()
    while len(days) < max(1, limit):
        if cursor.weekday() < 5:
            days.append(cursor.strftime('%Y-%m-%d'))
        cursor -= timedelta(days=1)
    return days


def _normalize_theme_day_payload(raw_day: Dict, default_date: str) -> Dict:
    """规范化单日题材榜结构。"""
    date = str(raw_day.get('date') or default_date).strip()[:10] or default_date
    raw_themes = raw_day.get('themes')
    themes: List[Dict] = []
    if isinstance(raw_themes, list):
        for idx, item in enumerate(raw_themes[:8], start=1):
            if not isinstance(item, dict):
                continue
            name = str(item.get('name') or item.get('theme') or item.get('label') or '').strip()
            if not name:
                continue
            try:
                change = float(item.get('change', 0) or 0)
            except Exception:
                change = 0.0
            try:
                limit_up_count = int(float(item.get('limit_up_count', 0) or 0))
            except Exception:
                limit_up_count = 0
            try:
                leader_change = float(item.get('leader_change', 0) or 0)
            except Exception:
                leader_change = 0.0
            try:
                heat_value = float(item.get('heat_value', 0) or 0)
            except Exception:
                heat_value = 0.0
            themes.append({
                'rank': int(item.get('rank') or idx),
                'name': name,
                'change': round(change, 2),
                'limit_up_count': limit_up_count,
                'leader_name': str(item.get('leader_name') or item.get('leader') or '').strip(),
                'leader_change': round(leader_change, 2),
                'heat_value': round(heat_value, 1),
                'summary': str(item.get('summary') or item.get('desc') or '').strip()[:120],
                'detail_url': str(item.get('detail_url') or '').strip(),
            })
    return {'date': date, 'themes': themes}


def _fallback_today_theme_history(days: int = 5) -> Dict:
    """题材历史页兜底：仅保证今天有内容，其他交易日保留空列表。"""
    trade_days = _recent_trade_days(days)
    sectors = get_hot_sectors() or []
    today_summary = compute_today_theme_summary()

    today_themes = []
    for idx, row in enumerate(sectors[:6], start=1):
        name = str(row.get('name') or '').strip()
        if not name:
            continue
        try:
            change = float(row.get('change', 0) or 0)
        except Exception:
            change = 0.0
        try:
            leader_change = float(row.get('leader_change', 0) or 0)
        except Exception:
            leader_change = 0.0
        amount = float(row.get('amount', 0) or 0)
        heat_value = round(amount / 1e8, 1) if amount > 0 else max(1.0, round(abs(change) * 4 + (7 - idx), 1))
        today_themes.append({
            'rank': idx,
            'name': name,
            'change': round(change, 2),
            'limit_up_count': 0,
            'leader_name': str(row.get('leader') or '').strip(),
            'leader_change': round(leader_change, 2),
            'heat_value': heat_value,
            'summary': str(today_summary.get('summary_text') or '').strip()[:120],
            'detail_url': '',
        })

    history = []
    for idx, d in enumerate(trade_days):
        history.append({
            'date': d,
            'themes': today_themes if idx == 0 else [],
        })

    return {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'days': history,
        'source': 'local-fallback',
    }


def _build_today_theme_prompt(trade_days: List[str]) -> str:
    """构建今日题材榜的 prompt，只请求今天的最新数据"""
    today = trade_days[0] if trade_days else ''
    return f"""请联网搜索并整理 A股市场今日（{today}）『炒什么』的热门题材榜。

请参考同花顺热点板块/热榜风格，按下面 JSON 结构返回，不要 markdown，不要解释：
{{
  "date": "{today}",
  "themes": [
    {{
      "rank": 1,
      "name": "燃气轮机",
      "change": 1.83,
      "limit_up_count": 3,
      "leader_name": "福鞍股份",
      "leader_change": 10.03,
      "heat_value": 22.6,
      "summary": "一句话说明今天为什么在炒这个方向",
      "detail_url": ""
    }}
  ]
}}

要求：
1. 只返回今日（{today}）的热门题材；
2. 至少返回前 5 个、最多 8 个热门题材；
3. change / leader_change / heat_value 必须是数字，不要带百分号或"万"字；
4. summary 必须简短具体，适合手机端列表。"""


def _call_qwen_for_today_theme(api_key: str, trade_days: List[str]) -> Optional[Dict]:
    """调用 Qwen 联网搜索获取今日题材数据"""
    import dashscope

    prompt = _build_today_theme_prompt(trade_days)
    today = trade_days[0] if trade_days else ''

    try:
        with _no_http_proxy_env():
            response = dashscope.Generation.call(
                api_key=api_key,
                model='qwen-plus',
                messages=[
                    {'role': 'system', 'content': '你是一位A股题材榜编辑，请只输出合法 JSON。'},
                    {'role': 'user', 'content': prompt},
                ],
                enable_search=True,
                result_format='message',
                temperature=0.2,
                max_tokens=1500,
            )

        if getattr(response, 'status_code', None) != 200:
            logger.warning(f'Qwen API 返回错误状态码: {response.status_code}')
            return None

        content = response.output.choices[0].message.content or ''
        payload = _extract_first_json_object(content)

        if not isinstance(payload, dict):
            logger.warning('Qwen API 返回非 JSON 格式')
            return None

        item = _normalize_theme_day_payload(payload, today)
        return item

    except Exception as e:
        logger.warning(f'Qwen API 调用失败: {e}')
        return None


def compute_today_theme_history(days: int = 5) -> Dict:
    """
    最近交易日『今日炒什么』题材榜。
    策略：
    - 今日数据：优先调用 Qwen 联网搜索
    - 历史数据：从磁盘文件读取，避免重复调用 LLM
    - 每日数据：首次调用后保存到磁盘，供后续复用
    """
    days = max(1, min(int(days or 5), 5))
    trade_days = _recent_trade_days(days)
    today = trade_days[0] if trade_days else ''

    result_days = []
    today_data = None

    # 先尝试从磁盘加载历史数据
    for d in trade_days:
        if d == today:
            # 今天的实时获取
            continue
        stored = load_theme_history_by_date(d)
        if stored:
            result_days.append({'date': d, 'themes': stored.get('themes', [])})
        else:
            # 历史上没有存储过，回退到空
            result_days.append({'date': d, 'themes': []})

    # 尝试获取今天的数据
    api_key = _get_qwen_api_key()
    if api_key:
        today_result = _call_qwen_for_today_theme(api_key, trade_days)
        if today_result:
            today_data = today_result
            # 保存今天的数据到磁盘
            save_theme_history_by_date(today, today_data)
        else:
            today_data = _build_today_fallback_themes(trade_days)
    else:
        today_data = _build_today_fallback_themes(trade_days)

    result_days.insert(0, {'date': today, 'themes': today_data.get('themes', [])})

    return {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'days': result_days[:days],
        'source': 'Qwen+Search+File' if api_key else 'local-fallback',
    }


def _build_today_fallback_themes(trade_days: List[str]) -> Dict:
    """构建今日的兜底数据（使用盘面热点板块）"""
    today = trade_days[0] if trade_days else ''
    sectors = get_hot_sectors() or []
    today_summary = compute_today_theme_summary()

    themes = []
    for idx, row in enumerate(sectors[:6], start=1):
        name = str(row.get('name') or '').strip()
        if not name:
            continue
        try:
            change = float(row.get('change', 0) or 0)
        except Exception:
            change = 0.0
        try:
            leader_change = float(row.get('leader_change', 0) or 0)
        except Exception:
            leader_change = 0.0
        amount = float(row.get('amount', 0) or 0)
        heat_value = round(amount / 1e8, 1) if amount > 0 else max(1.0, round(abs(change) * 4 + (7 - idx), 1))
        themes.append({
            'rank': idx,
            'name': name,
            'change': round(change, 2),
            'limit_up_count': 0,
            'leader_name': str(row.get('leader') or '').strip(),
            'leader_change': round(leader_change, 2),
            'heat_value': heat_value,
            'summary': str(today_summary.get('summary_text') or '').strip()[:120],
            'detail_url': '',
        })

    return {'date': today, 'themes': themes}



def get_market_overview() -> List[Dict]:
    """
    获取大盘指数概览（上证、深证、创业板、科创板等）
    优先使用东方财富指数现货；新浪仅作兜底。
    """
    cached = _get_cached('market_overview')
    if isinstance(cached, list) and len(cached) > 0:
        return cached

    result = []
    ordered_needed = [
        ('000001', '上证指数'),
        ('399001', '深证成指'),
        ('399006', '创业板指'),
        ('000688', '科创50'),
        ('000300', '沪深300'),
        ('000016', '上证50'),
        ('000905', '中证500'),
        ('000852', '中证1000'),
    ]

    # ── 主数据源：东方财富指数现货（与其他模块口径保持一致）──────────────
    try:
        with _ak_eastmoney_direct():
            df = _get_ak().stock_zh_index_spot_em(symbol='沪深重要指数')

        if df is not None and not df.empty:
            lookup: Dict[str, Dict] = {}
            for _, row in df.iterrows():
                code = str(row.get('代码') or '').strip()
                if not code:
                    continue
                lookup[code.zfill(6)] = row.to_dict()

            for code, name in ordered_needed:
                row = lookup.get(code)
                if not row:
                    continue

                price = _safe_float(row.get('最新价') or row.get('最新') or row.get('收盘'))
                prev_close = _safe_float(row.get('昨收') or row.get('昨收盘') or row.get('前收盘'))
                open_price = _safe_float(row.get('今开') or row.get('开盘'))
                change = _safe_float(row.get('涨跌幅'))
                change_amount = _safe_float(
                    row.get('涨跌额') if row.get('涨跌额') is not None else price - prev_close
                )

                if not price and prev_close:
                    price = prev_close
                if not prev_close and price and change:
                    prev_close = price / (1 + change / 100.0)
                if not change and price and prev_close:
                    change = (price - prev_close) / prev_close * 100 if prev_close else 0.0
                if not change_amount and price and prev_close:
                    change_amount = price - prev_close

                result.append({
                    'name': name,
                    'code': code,
                    'price': round(price, 4),
                    'change': round(change, 2),
                    'change_amount': round(change_amount, 2),
                    'volume': _safe_float(row.get('成交量')),
                    'amount': _safe_float(row.get('成交额')),
                    'high': _safe_float(row.get('最高')),
                    'low': _safe_float(row.get('最低')),
                    'open': round(open_price, 4) if open_price else 0,
                    'prev_close': round(prev_close, 4) if prev_close else 0,
                })

        if len(result) >= 3:
            logger.info(f"大盘指数获取成功（东财）: {len(result)}条")
            _set_cached('market_overview', result)
            return result
    except Exception as e:
        logger.warning(f"大盘指数获取失败（东财）: {e}")

    # ── 兜底数据源：新浪指数接口──────────────────────────────────────────
    try:
        needed = {
            'sh000001': '上证指数',
            'sz399001': '深证成指',
            'sz399006': '创业板指',
            'sh000688': '科创50',
            'sh000300': '沪深300',
            'sh000016': '上证50',
            'sh000905': '中证500',
            'sh000852': '中证1000',
        }
        codes_str = ','.join(needed.keys())
        url = 'https://hq.sinajs.cn/list=' + codes_str
        from curl_cffi import requests as cr
        resp = cr.get(url, impersonate='chrome110',
                      headers={'Referer': 'https://finance.sina.com.cn'}, timeout=10)
        text = resp.text
        import re
        # 解析每个hq_str_xxx="data"格式
        pattern = r'hq_str_([a-z]+)(\d+)="([^"]+)"'
        matches = re.findall(pattern, text)
        for prefix, code, data_str in matches:
            key = f'{prefix}{code}'
            if key not in needed:
                continue
            parts = data_str.split(',')
            if len(parts) >= 6:
                name = needed[key]
                open_price = float(parts[1]) if parts[1] else 0
                prev_close = float(parts[2]) if len(parts) > 2 and parts[2] else 0
                price = float(parts[3]) if len(parts) > 3 and parts[3] else prev_close
                high = float(parts[4]) if len(parts) > 4 and parts[4] else 0
                low = float(parts[5]) if len(parts) > 5 and parts[5] else 0
                change = ((price - prev_close) / prev_close * 100) if prev_close else 0
                result.append({
                    'name': name,
                    'code': code,
                    'price': price,
                    'change': round(change, 2),
                    'change_amount': round(price - prev_close, 2),
                    'volume': 0,
                    'amount': 0,
                    'high': high,
                    'low': low,
                    'open': open_price,
                    'prev_close': prev_close,
                })
        if result:
            logger.info(f"大盘指数获取成功（新浪）: {len(result)}条")
    except Exception as e:
        logger.warning(f"大盘指数获取失败: {e}")

    _set_cached('market_overview', result)
    return result


def get_money_flow() -> Dict:
    """
    获取市场资金流向数据（北向资金 + 行业板块资金流）。
    北向资金：东方财富沪深港通接口，2024-08后数据可能缺失，降级到估算。
    板块资金流：优先使用同花顺行业板块数据（含净流入），东方财富作为备选。
    """
    cached = _get_cached('money_flow')
    if cached:
        return cached

    result: Dict = {
        'hgt_net_inflow': 0.0,
        'sgt_net_inflow': 0.0,
        'north_money': {
            'north_net_inflow': 0.0,
            'north_inflow': 0.0,
            'north_outflow': 0.0,
            'status': 'unavailable',
            'note': '北向数据暂不可用',
        },
        'sector_flow': [],
        'time': datetime.now().strftime('%H:%M'),
    }

    # ── 北向资金（东方财富沪深港通资金流向）───────────────────
    try:
        with _ak_eastmoney_direct():
            north_df = _get_ak().stock_hsgt_fund_flow_summary_em()
        if north_df is not None and not north_df.empty:
            inflow_total = 0.0
            outflow_total = 0.0
            up_count = 0
            down_count = 0
            for _, row in north_df.iterrows():
                net = _safe_float(row.get('成交净买额') or row.get('资金净流入') or 0)
                inflow_total += max(0, net)
                outflow_total += max(0, -net)
                up_count += int(pd.to_numeric(row.get('上涨数'), errors='coerce') or 0)
                down_count += int(pd.to_numeric(row.get('下跌数'), errors='coerce') or 0)
            total_net = inflow_total - outflow_total
            result['hgt_net_inflow'] = round(total_net, 2)
            result['north_money'] = {
                'north_net_inflow': round(total_net, 2),
                'north_inflow': round(inflow_total, 2),
                'north_outflow': round(outflow_total, 2),
                'status': 'ok',
                'note': '',
            }
            if up_count or down_count:
                result['breadth_from_north'] = {'up': up_count, 'down': down_count}
    except Exception as e:
        logger.debug(f'北向资金获取失败，降级估算: {e}')

    # ── 行业板块资金流（优先同花顺，备选东方财富）────────────────
    # 方法1：使用同花顺行业板块数据（含净流入字段）
    try:
        from utils.ths_crawler import get_ths_industry_list
        ths_df = get_ths_industry_list()
        if ths_df is not None and not ths_df.empty:
            # 同花顺数据已有净流入字段（单位：亿元）
            net_col = '净流入' if '净流入' in ths_df.columns else None
            chg_col = '涨跌幅' if '涨跌幅' in ths_df.columns else None
            name_col = '板块' if '板块' in ths_df.columns else None

            if net_col and name_col:
                # 按净流入排序（降序）
                ths_sorted = ths_df.sort_values(by=net_col, ascending=False).reset_index(drop=True)
                for _, row in ths_sorted.head(20).iterrows():
                    # 同花顺净流入单位已经是亿元
                    net_yi = _safe_float(row.get(net_col))
                    result['sector_flow'].append({
                        'name': str(row.get(name_col, '') or ''),
                        'net_yi': round(net_yi, 2),
                        'change': _safe_float(row.get(chg_col)) if chg_col else 0.0,
                    })
                logger.info(f'板块资金流获取成功（同花顺）: {len(result["sector_flow"])}条')
    except Exception as e:
        logger.debug(f'同花顺板块资金流获取失败: {e}')

    # 方法2：备选东方财富行业资金流（可能因网络封锁失败）
    if not result['sector_flow']:
        try:
            with _ak_eastmoney_direct():
                fund_df = _get_ak().stock_sector_fund_flow_rank(
                    indicator='今日', sector_type='行业资金流'
                )
            if fund_df is not None and not fund_df.empty:
                net_col = next((c for c in ('今日主力净流入-净额', '5日主力净流入-净额',
                    '10日主力净流入-净额') if c in fund_df.columns), None)
                chg_col = next((c for c in ('今日涨跌幅', '5日涨跌幅', '10日涨跌幅') if c in fund_df.columns), None)
                name_col = next((c for c in ('名称',) if c in fund_df.columns), None)
                if net_col:
                    fund_sorted = fund_df.sort_values(by=net_col, ascending=False).reset_index(drop=True)
                    for _, row in fund_sorted.head(20).iterrows():
                        net_yi = _safe_float(row.get(net_col)) / 1e8
                        result['sector_flow'].append({
                            'name': str(row.get(name_col, '') or '') if name_col else '',
                            'net_yi': round(net_yi, 2),
                            'change': _safe_float(row.get(chg_col)) if chg_col else 0.0,
                        })
                    logger.info(f'板块资金流获取成功（东方财富）: {len(result["sector_flow"])}条')
        except Exception as e:
            logger.debug(f'东方财富板块资金流获取失败: {e}')

    _set_cached('money_flow', result)
    return result


def get_limit_up_data() -> Dict:
    """
    获取涨跌停数据（家数 + Top10 个股列表）。

    优先级：东方财富涨停池（逐股统计，最准确）→ 同花顺 q首页
    → 同花顺温度计 → Qwen 联网搜索（最慢，仅兜底）。
    """
    cached = _get_cached('limit_up')
    if cached:
        return cached

    today = datetime.now().strftime('%Y%m%d')
    result = {
        'limit_up_count': 0,
        'limit_down_count': 0,
        'limit_up_stocks': [],
        'count_source': '',
        'time': datetime.now().strftime('%H:%M'),
    }

    # ── 东方财富涨停池（主数据源，逐股统计最准确） ─────────────────
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
    try:
        with _ak_eastmoney_direct():
            up_df = _get_ak().stock_zt_pool_em(date=today)
        if up_df is None or up_df.empty:
            # 盘后/非交易日 API 可能返回空，退回到最近交易日
            with _ak_eastmoney_direct():
                up_df = _get_ak().stock_zt_pool_em(date=yesterday)
        if up_df is not None and not up_df.empty:
            result['limit_up_count'] = len(up_df)
            result['count_source'] = '东方财富涨停池'
            for _, row in up_df.head(10).iterrows():
                result['limit_up_stocks'].append({
                    'name': str(row.get('名称', '')),
                    'code': str(row.get('代码', '')),
                    'change': _safe_float(row.get('涨跌幅')),
                    'reason': str(row.get('涨停统计', '')),
                })
    except Exception as e:
        logger.warning(f"东方财富涨停池获取失败: {e}")

    try:
        with _ak_eastmoney_direct():
            down_df = _get_ak().stock_zt_pool_dtgc_em(date=today)
        if down_df is None or down_df.empty:
            with _ak_eastmoney_direct():
                down_df = _get_ak().stock_zt_pool_dtgc_em(date=yesterday)
        if down_df is not None and not down_df.empty:
            result['limit_down_count'] = len(down_df)
    except Exception as e:
        logger.warning(f"东方财富跌停池获取失败: {e}")

    # ── 同花顺补充：东方财富可能不完整时用于交叉校准 ─────────────────
    if not result.get('limit_up_count') and not result.get('limit_down_count'):
        # 同花顺 q 首页 indexflash
        try:
            from curl_cffi import requests as cr
            import json
            import re

            with _no_http_proxy_env():
                resp = cr.get(
                    'https://q.10jqka.com.cn/api.php?t=indexflash&',
                    headers={
                        'Referer': 'https://q.10jqka.com.cn/',
                        'User-Agent': 'Mozilla/5.0',
                        'Accept': '*/*',
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    impersonate='chrome110',
                    timeout=15,
                )

            if resp.status_code == 200:
                text = (resp.text or '').strip()
                payload = None
                try:
                    payload = json.loads(text)
                except Exception:
                    cleaned = re.sub(r'^\s*\(|\)\s*;?\s*$', '', text)
                    payload = json.loads(cleaned)

                zdt_data = payload.get('zdt_data') or {}
                last_zdt = zdt_data.get('last_zdt') or {}
                ztzs = last_zdt.get('ztzs')
                dtzs = last_zdt.get('dtzs')
                if ztzs is not None and dtzs is not None:
                    if not result['limit_up_count']:
                        result['limit_up_count'] = int(float(ztzs))
                    if not result['limit_down_count']:
                        result['limit_down_count'] = int(float(dtzs))
                    result['count_source'] = result.get('count_source', '') or '同花顺 q首页'
        except Exception as e:
            logger.debug(f'同花顺 q 首页涨跌停家数获取失败: {e}')

    # ── 同花顺温度计兜底 ──────────────────────────────────────
    if not result.get('limit_up_count') and not result.get('limit_down_count'):
        try:
            from curl_cffi import requests as cr

            with _no_http_proxy_env():
                resp = cr.get(
                    'https://stock.10jqka.com.cn/wenduji/',
                    headers={
                        'Referer': 'https://stock.10jqka.com.cn/',
                        'User-Agent': 'Mozilla/5.0',
                    },
                    impersonate='chrome110',
                    timeout=15,
                )
            html = resp.content.decode('gbk', 'ignore')
            m = re.search(r'涨停家数：<i[^>]*>(\d+)</i>.*?跌停家数：<i[^>]*>(\d+)</i>', html, re.S)
            if m:
                result['limit_up_count'] = int(m.group(1))
                result['limit_down_count'] = int(m.group(2))
                result['count_source'] = '同花顺温度计'
        except Exception as e:
            logger.debug(f'同花顺涨跌停家数获取失败: {e}')

    # ── Qwen 联网搜索兜底（最慢，放在最后） ──────────────────────
    if not result.get('limit_up_count') and not result.get('limit_down_count'):
        qwen_counts = _fetch_limit_counts_from_qwen()
        if qwen_counts:
            result['limit_up_count'], result['limit_down_count'] = qwen_counts
            result['count_source'] = 'Qwen+同花顺'

    _set_cached('limit_up', result)
    return result


def get_turnover_rate() -> List:
    """
    获取换手率排行榜（活跃股票）
    使用 stock_zt_pool_strong_em（强势股池），包含换手率数据
    """
    cached = _get_cached('turnover_rate')
    if isinstance(cached, list):
        return cached

    result = []
    today = datetime.now().strftime('%Y%m%d')
    try:
        with _ak_eastmoney_direct():
            df = _get_ak().stock_zt_pool_strong_em(date=today)
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                code = str(row.get('代码', ''))
                name = str(row.get('名称', ''))
                if not code or code == 'None' or not name or name == 'None':
                    continue
                turnover = _safe_float(row.get('换手率', 0))
                if turnover <= 0:
                    continue
                result.append({
                    'name': name,
                    'code': code,
                    'turnover_rate': round(turnover, 2),
                    'price': _safe_float(row.get('最新价')),
                    'change': _safe_float(row.get('涨跌幅')),
                })
        result.sort(key=lambda x: x['turnover_rate'], reverse=True)
        result = result[:20]
    except Exception as e:
        logger.warning(f"换手率获取失败: {e}")

    _set_cached('turnover_rate', result)
    return result


def _apply_breadth_totals_from_spot_em_df(out: Dict, df: pd.DataFrame) -> bool:
    """从东财 A 股现货 DataFrame 写入涨跌家数；仅在 total_amount 仍为 0 时写入全市场成交额。"""
    if df is None or df.empty:
        return False
    ch_col = next((c for c in ('涨跌幅',) if c in df.columns), None)
    if not ch_col:
        return False
    s = pd.to_numeric(df[ch_col], errors='coerce').fillna(0)
    out['up_count'] = int((s > 0).sum())
    out['down_count'] = int((s < 0).sum())
    out['flat_count'] = int((s == 0).sum())
    amt_col = next((c for c in ('成交额',) if c in df.columns), None)
    if amt_col and not float(out.get('total_amount') or 0):
        out['total_amount'] = float(pd.to_numeric(df[amt_col], errors='coerce').sum())
    return True


def peek_market_snapshot_cache() -> Optional[Dict]:
    """返回进程内市场快照缓存（供路由层与 Redis 命中结果择优合并，不触发重新拉取）。"""
    c = _get_cached('market_snapshot')
    return c if isinstance(c, dict) else None


def get_market_snapshot() -> Dict:
    """
    A 股全市场快照：涨跌家数、总成交额、涨幅/跌幅/成交额/涨速榜（含行业）。

    数据获取策略（优先级）：
      1. 新浪接口（涨幅/跌幅/成交额排行，~3秒内完成）→ 优先同步获取，立即返回并缓存
      2. 新浪排行无行业：读 stocks 表 → 未命中则 akshare 个股接口并发补行业并写库；同时后台预热东财全现货
      3. 东方财富 EM（全量，含涨跌家数/成交额/行业）→ 后台异步写入缓存，下次请求生效

    这样首次请求约 3 秒内返回新浪排行；行业字段在数秒～十余秒内由 akshare 补全（视未命中数量）。
    若 EM 在后台成功获取，则下次请求时涨跌家数/成交额/行业数据也一并返回。
    """
    cached = _get_cached('market_snapshot')
    if isinstance(cached, dict):
        if snapshot_rankings_need_industry_enrich(cached):
            try:
                enrich_snapshot_industries(cached)
            except Exception as e:
                logger.warning('缓存快照行业补全失败: %s', e)
            _set_cached('market_snapshot', cached)
        return cached

    out: Dict = {
        'up_count': 0,
        'down_count': 0,
        'flat_count': 0,
        'total_amount': 0.0,
        'top_gainers': [],
        'top_losers': [],
        'top_by_amount': [],
        'fast_gainers': [],
        'time': datetime.now().strftime('%H:%M'),
        '_source': 'sina',
    }

    # ── 方案一：新浪排行（同步，~3秒内完成） ─────────────────────────────
    _fetch_sina_rankings(out)
    if out['top_gainers']:
        try:
            enrich_snapshot_industries(out)
        except Exception as e:
            logger.warning('排行行业补全失败（不影响主流程）: %s', e)
        # 新浪排行不带涨跌家数：若进程内已有东财现货缓存（如行业补全刚预热），同步补全
        if out.get('up_count', 0) == 0 and out.get('down_count', 0) == 0:
            if _spot_em_cache_warm():
                df = _spot_em_cache.get('df')
                if df is not None:
                    _apply_breadth_totals_from_spot_em_df(out, df)
        _set_cached('market_snapshot', out)

    # ── 立即返回新浪数据 ──────────────────────────────────────────────
    if out['top_gainers']:
        return out

    # ── 方案二：东方财富 EM（后台异步，下次请求时生效）────────────
    # EM 需要 ~11 秒，直接在后台获取，不阻塞返回
    _fetch_em_snapshot()
    return out


# ──────────────────────────── 全A现货多源 ────────────────────────────

def _fetch_spot_push2_dataframe() -> Optional[pd.DataFrame]:
    """东方财富 push2 快照（不同于 stock_zh_a_spot_em 的另一接口节点）。"""
    import requests as _req
    url = 'https://push2.eastmoney.com/api/qt/clist/get'
    params = {
        'pn': '1', 'pz': '5000',
        'po': '1', 'np': '1',
        'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
        'fltt': '2', 'invt': '2',
        'fid': 'f3',
        'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048',
        'fields': 'f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152',
    }
    r = _req.get(url, params=params, timeout=15)
    r.raise_for_status()
    json_data = r.json()
    rows = (json_data.get('data', {}) or {}).get('diff', []) or []
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df = df.rename(columns={
        'f12': '代码', 'f14': '名称',
        'f2': '最新价', 'f3': '涨跌幅',
        'f4': '涨跌额', 'f5': '成交量',
        'f6': '成交额', 'f15': '最高',
        'f16': '最低', 'f17': '今开',
        'f18': '昨收', 'f10': '换手率',
        'f8': '振幅',
    })
    return df


def _fetch_spot_em_dataframe() -> Optional[pd.DataFrame]:
    """
    全 A 现货（含所属行业），多源兜底：
    1. 东方财富 stock_zh_a_spot_em
    2. 新浪 stock_zh_a_spot
    3. 东财 push2
    """
    sources = [
        ('东方财富', _ak_eastmoney_direct, lambda: _get_ak().stock_zh_a_spot_em()),
        ('新浪',     _ak_sina_direct,      lambda: _get_ak().stock_zh_a_spot()),
        ('东财push2', _no_http_proxy_env,   _fetch_spot_push2_dataframe),
    ]
    for name, ctx_mgr, fetcher in sources:
        try:
            with ctx_mgr():
                df = fetcher()
        except Exception as e:
            logger.warning('[%s] 获取失败: %s', name, e)
            continue
        if df is not None and not df.empty:
            logger.info('[%s] 全A现货 %d 条', name, len(df))
            _spot_em_cache['df'] = df
            _spot_em_cache['ts'] = time.time()
            return df
        logger.warning('[%s] 返回空数据', name)
    logger.error('所有现货数据源均失败')
    return None


def _fetch_em_snapshot():
    """东方财富全量快照（后台异步）：写进程内缓存，并回写 Redis，避免接口长期命中「无涨跌家数」的新浪快照。"""
    out: Dict = {
        'up_count': 0,
        'down_count': 0,
        'flat_count': 0,
        'total_amount': 0.0,
        'top_gainers': [],
        'top_losers': [],
        'top_by_amount': [],
        'fast_gainers': [],
        'time': datetime.now().strftime('%H:%M'),
        '_source': 'em',
    }

    def _do_fetch():
        try:
            df = _fetch_spot_em_dataframe()
            if df is None or df.empty:
                return

            ch_col = next((c for c in ('涨跌幅',) if c in df.columns), None)
            amt_col = next((c for c in ('成交额',) if c in df.columns), None)
            spd_col = next((c for c in ('涨速',) if c in df.columns), ch_col)
            ind_col = next((c for c in ('所属行业', '行业') if c in df.columns), None)
            if not ind_col:
                for c in df.columns:
                    if '行业' in str(c):
                        ind_col = c
                        break
            code_col = next((c for c in ('代码',) if c in df.columns), None)
            name_col = next((c for c in ('名称',) if c in df.columns), None)
            price_col = next((c for c in ('最新价',) if c in df.columns), None)

            if ch_col:
                s = pd.to_numeric(df[ch_col], errors='coerce').fillna(0)
                out['up_count'] = int((s > 0).sum())
                out['down_count'] = int((s < 0).sum())
                out['flat_count'] = int((s == 0).sum())

            if amt_col:
                out['total_amount'] = float(pd.to_numeric(df[amt_col], errors='coerce').sum())

            def _pick(row):
                return {
                    'code': str(row.get(code_col, '')) if code_col else '',
                    'name': str(row.get(name_col, '')) if name_col else '',
                    'price': _safe_float(row.get(price_col)) if price_col else 0.0,
                    'change': _safe_float(row.get(ch_col)) if ch_col else 0.0,
                    'industry': str(row.get(ind_col, '') or '') if ind_col else '',
                    'speed': _safe_float(row.get(spd_col)) if spd_col else 0.0,
                }

            if ch_col:
                for _, row in df.nlargest(20, ch_col).iterrows():
                    out['top_gainers'].append(_pick(row))
                for _, row in df.nsmallest(15, ch_col).iterrows():
                    out['top_losers'].append(_pick(row))
            if amt_col:
                for _, row in df.nlargest(15, amt_col).iterrows():
                    out['top_by_amount'].append(_pick(row))
            if spd_col and spd_col != ch_col:
                for _, row in df.nlargest(15, spd_col).iterrows():
                    out['fast_gainers'].append(_pick(row))

            # 东财排行若未带出行业列，会覆盖掉新浪已补全的 industry；此处统一再补一层
            if snapshot_rankings_need_industry_enrich(out):
                try:
                    enrich_snapshot_industries(out)
                except Exception as e:
                    logger.warning('EM 快照行业补全失败: %s', e)

            # 写进程内缓存，并同步更新 Redis（与 Flask 路由层 SNAPSHOT key 一致）
            _set_cached('market_snapshot', out)
            try:
                cache_layer_set(MARKET_SNAPSHOT_REDIS_KEY, out, ttl=30)
            except Exception as e:
                logger.warning('市场快照写入 Redis 失败: %s', e)
        except Exception as e:
            logger.warning(f"东方财富快照后台获取失败: {e}")

    t = threading.Thread(target=_do_fetch, daemon=True)
    t.start()
    # 不 join：后台异步，不阻塞主流程


def _fetch_sina_rankings(out: Dict):
    """新浪排行榜（涨幅/跌幅/成交额，无涨跌家数）"""
    SINA_HEADERS = {
        'Referer': 'http://finance.sina.com.cn',
        'User-Agent': 'Mozilla/5.0',
    }
    SINA_BASE = 'http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'

    def _fetch_ranking(sort: str, asc: int, limit: int = 20) -> List[Dict]:
        try:
            resp = requests.get(
                SINA_BASE,
                params={'page': 1, 'num': limit, 'sort': sort, 'asc': asc, 'node': 'hs_a'},
                headers=SINA_HEADERS,
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            if not isinstance(data, list):
                return []
            return data
        except Exception as e:
            logger.warning(f"新浪排行获取失败 ({sort}): {e}")
            return []

    # 涨幅前20
    gainers = _fetch_ranking('changepercent', 0, 20)
    for s in gainers:
        code = str(s.get('code', '')).strip()
        out['top_gainers'].append({
            'code': code,
            'name': str(s.get('name', '')).strip(),
            'price': _safe_float(s.get('trade')),
            'change': _safe_float(s.get('changepercent')),
            'industry': '',
            'speed': 0.0,
        })

    # 跌幅前20
    losers = _fetch_ranking('changepercent', 1, 20)
    for s in losers:
        code = str(s.get('code', '')).strip()
        out['top_losers'].append({
            'code': code,
            'name': str(s.get('name', '')).strip(),
            'price': _safe_float(s.get('trade')),
            'change': _safe_float(s.get('changepercent')),
            'industry': '',
            'speed': 0.0,
        })

    # 成交额前20
    amounts = _fetch_ranking('amount', 0, 20)
    total = 0.0
    for s in amounts:
        code = str(s.get('code', '')).strip()
        amt = _safe_float(s.get('amount'))
        total += amt
        out['top_by_amount'].append({
            'code': code,
            'name': str(s.get('name', '')).strip(),
            'price': _safe_float(s.get('trade')),
            'change': _safe_float(s.get('changepercent')),
            'industry': '',
            'speed': 0.0,
        })
    # 新浪只能获取Top20，用 Top20 合计估算全市场成交额（乘数约12）
    if total > 0 and not out['total_amount']:
        out['total_amount'] = total * 12


# ── 股票代码 → 行业（东方财富「所属行业」），入库 stocks.sector 供排行展示与检索 ──
_spot_em_cache = {'df': None, 'ts': 0.0}


def _normalize_stock_code(code: str) -> str:
    """统一为不含市场前缀的代码（与 stocks.code、akshare 一致）。"""
    c = str(code or '').strip().lower()
    if not c:
        return ''
    for p in ('sh', 'sz', 'bj'):
        if c.startswith(p) and len(c) > len(p):
            c = c[len(p):]
            break
    return c


def _infer_market_type(code6: str) -> str:
    c = (code6 or '').strip()
    if not c:
        return 'sz'
    if c.startswith(('43', '83', '87', '88', '92')):
        return 'bj'
    if c.startswith('6'):
        return 'sh'
    return 'sz'



def _spot_em_cache_warm() -> bool:
    df = _spot_em_cache['df']
    if df is None:
        return False
    return time.time() - float(_spot_em_cache['ts']) < 120


def _warm_spot_em_cache_async():
    """后台拉全市场现货，供约 2 分钟内后续请求快速映射行业。"""
    def _run():
        try:
            _fetch_spot_em_dataframe()
        except Exception as e:
            logger.debug('后台预热 A 股现货失败: %s', e)

    threading.Thread(target=_run, daemon=True).start()


def _industry_map_from_spot_df(df: pd.DataFrame, want: set) -> Dict[str, Tuple[str, str]]:
    """want: 6 位代码集合 → {code: (name, industry)}"""
    code_c = next((c for c in ('代码',) if c in df.columns), None)
    ind_c = next((c for c in ('所属行业', '行业') if c in df.columns), None)
    name_c = next((c for c in ('名称',) if c in df.columns), None)
    if not code_c or not ind_c:
        return {}
    out: Dict[str, Tuple[str, str]] = {}
    for _, row in df.iterrows():
        cc = str(row.get(code_c, '') or '').strip()
        if cc not in want:
            continue
        ind = str(row.get(ind_c, '') or '').strip()
        if not ind:
            continue
        nm = str(row.get(name_c, '') or '').strip() if name_c else ''
        out[cc] = (nm, ind)
    return out


def _industry_from_individual_em(code6: str) -> Tuple[str, str]:
    """单票兜底：stock_individual_info_em → (行业, 简称)。"""
    try:
        with _ak_eastmoney_direct():
            df = _get_ak().stock_individual_info_em(symbol=code6)
    except Exception as e:
        logger.debug('stock_individual_info_em(%s) 失败: %s', code6, e)
        return '', ''
    if df is None or df.empty:
        return '', ''
    industry = ''
    name = ''
    for _, row in df.iterrows():
        item = str(row.get('item', '') or '').strip()
        val = str(row.get('value', '') or '').strip()
        if item == '行业':
            industry = val
        elif item in ('股票简称', '名称'):
            name = val
    return industry, name


def _parallel_individual_industries(codes: List[str]) -> Dict[str, Tuple[str, str]]:
    """多线程拉取 stock_individual_info_em，codes 建议 ≤40。"""
    out: Dict[str, Tuple[str, str]] = {}
    if not codes:
        return out

    def _one(c: str) -> Tuple[str, str, str]:
        ind, nm = _industry_from_individual_em(c)
        return c, ind, nm

    cap = codes[:40]
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            rows = list(ex.map(_one, cap))
        for c, ind, nm in rows:
            if ind:
                out[c] = (ind, nm)
    except Exception as e:
        logger.warning('并发拉取个股行业失败，改为串行: %s', e)
        for c in cap:
            ind, nm = _industry_from_individual_em(c)
            if ind:
                out[c] = (ind, nm)
            time.sleep(0.08)
    return out


def snapshot_rankings_need_industry_enrich(out: Dict) -> bool:
    """排行列表里是否存在「有代码但 industry 为空」的行（需补全）。"""
    keys = ('top_gainers', 'top_losers', 'top_by_amount', 'fast_gainers')
    for k in keys:
        for row in out.get(k) or []:
            code = str(row.get('code', '') or '').strip()
            if not code:
                continue
            ind = str(row.get('industry', '') or '').strip()
            if not ind:
                return True
    return False


def enrich_snapshot_industries(out: Dict) -> None:
    """
    为新浪排行各列表补充 industry 字段，并写入 stocks 表。
    顺序：读库 →（若现货缓存已预热）用全表映射 → 否则并发个股接口，并后台预热全表现货。
    """
    try:
        import database as db
    except Exception:
        db = None

    keys = ('top_gainers', 'top_losers', 'top_by_amount', 'fast_gainers')
    code_to_name: Dict[str, str] = {}
    for k in keys:
        for row in out.get(k) or []:
            c = _normalize_stock_code(row.get('code', ''))
            if len(c) < 4:
                continue
            nm = str(row.get('name', '') or '').strip()
            if nm:
                code_to_name[c] = nm
            elif c not in code_to_name:
                code_to_name[c] = ''
    codes = list(code_to_name.keys())
    if not codes:
        return

    merged: Dict[str, str] = {}
    if db is not None:
        try:
            merged = db.get_stock_sectors_by_codes(codes)
        except Exception as e:
            logger.debug('读取 stocks 行业缓存失败: %s', e)

    missing = [c for c in codes if not merged.get(c)]
    if missing:
        want = set(missing)
        if _spot_em_cache_warm():
            df = _spot_em_cache['df']
            if df is not None:
                got = _industry_map_from_spot_df(df, want)
                batch = []
                for c in missing:
                    if c not in got:
                        continue
                    nm, ind = got[c]
                    if not ind:
                        continue
                    merged[c] = ind
                    batch.append({
                        'code': c,
                        'name': nm or code_to_name.get(c) or c,
                        'market_type': _infer_market_type(c),
                        'sector': ind,
                    })
                if batch and db is not None:
                    try:
                        db.upsert_stocks_batch(batch)
                    except Exception as e:
                        logger.debug('写入 stocks 行业失败: %s', e)

        still = [c for c in missing if not merged.get(c)]
        if still:
            _warm_spot_em_cache_async()
            got2 = _parallel_individual_industries(still)
            batch2 = []
            for c, (ind, nm) in got2.items():
                merged[c] = ind
                batch2.append({
                    'code': c,
                    'name': nm or code_to_name.get(c) or c,
                    'market_type': _infer_market_type(c),
                    'sector': ind,
                })
            if batch2 and db is not None:
                try:
                    db.upsert_stocks_batch(batch2)
                except Exception as e:
                    logger.debug('写入 stocks 行业失败: %s', e)

    for k in keys:
        for row in out.get(k) or []:
            c = _normalize_stock_code(row.get('code', ''))
            if len(c) < 4:
                continue
            ind = merged.get(c)
            if ind:
                row['industry'] = ind


def _sector_row_amount(row) -> float:
    """行业行成交额（同花顺列名 总成交额，东方财富列名 成交额），用于前端热力图块面积。"""
    try:
        for k in ('总成交额', '成交额'):
            if k in row.index and pd.notna(row.get(k)):
                v = _safe_float(row[k])
                if v > 0:
                    return v
    except Exception:
        pass
    return 0.0


def get_hot_sectors() -> List:
    """
    获取热点板块。优先级:
    1. 同花顺 HTML 解析 (curl_cffi, 绕过IP封禁)
    2. 新浪概念板块 JS 数据 (curl_cffi, 含涨跌幅/净流入)
    3. 东方财富 akshare
    """
    cached = _get_cached('hot_sectors')
    if cached:
        return cached

    result = []

    # 方法1: 同花顺 HTML 解析 (curl_cffi 绕过 requests 的 IP 封禁)
    try:
        from curl_cffi import requests as cr
        THS_HEADERS = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://q.10jqka.com.cn/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        resp = cr.get('https://q.10jqka.com.cn/thshy/', headers=THS_HEADERS, impersonate='chrome110', timeout=15)
        if resp.status_code == 200:
            resp.encoding = 'gbk'
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')
            table = soup.find('table', class_='m-table')
            if table:
                rows = table.find_all('tr')[1:]
                industries = []
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) < 12:
                        continue
                    try:
                        link = cells[1].find('a')
                        href = link.get('href', '') if link else ''
                        code = ''
                        if '/code/' in href:
                            code = href.split('/code/')[-1].rstrip('/')
                        def _pf(t):
                            try:
                                return float(t.get_text(strip=True))
                            except:
                                return 0.0
                        def _pi(t):
                            try:
                                return int(t.get_text(strip=True))
                            except:
                                return 0
                        industries.append({
                            '板块': cells[1].get_text(strip=True),
                            '代码': code,
                            '涨跌幅': _pf(cells[2]),
                            '总成交额': _pf(cells[4]),
                            '上涨家数': _pi(cells[6]),
                            '下跌家数': _pi(cells[7]),
                            '领涨股': cells[9].get_text(strip=True),
                            '领涨股-涨跌幅': _pf(cells[11]),
                        })
                    except Exception:
                        continue
                if industries:
                    industries.sort(key=lambda x: x['涨跌幅'], reverse=True)
                    for _, row in enumerate(industries[:20]):
                        amt = row.get('总成交额', 0)
                        result.append({
                            'name': row['板块'],
                            'code': row.get('代码', ''),
                            'change': row['涨跌幅'],
                            'leader': row.get('领涨股', ''),
                            'leader_change': row.get('领涨股-涨跌幅', 0),
                            'heat_display': '--',
                            **({'amount': amt} if amt > 0 else {}),
                        })
                    logger.info(f'热点行业获取成功（同花顺 curl_cffi）: {len(result)}条')
                    _set_cached('hot_sectors', result)
                    return result
    except Exception as e:
        logger.debug(f'同花顺 curl_cffi 行业板块失败: {e}')

    # 方法2: 新浪板块 JS 数据（curl_cffi, 含净流入/涨跌幅）
    try:
        from curl_cffi import requests as cr
        url = 'https://vip.stock.finance.sina.com.cn/q/view/newFLJK.php?param=class'
        resp = cr.get(url, impersonate='chrome110', timeout=15)
        if resp.status_code == 200 and resp.text and '<html>' not in resp.text[:50]:
            import re, json as _json
            js_match = re.search(r'=\s*(\{".*"\})', resp.text, re.DOTALL)
            if js_match:
                try:
                    raw_data = _json.loads(js_match.group(1))
                    items = []
                    for key, val in raw_data.items():
                        parts = val.split(',')
                        name = parts[1].strip() if len(parts) > 1 else key
                        change = float(parts[-1]) if len(parts) > 1 else 0.0
                        amount = float(parts[7]) if len(parts) > 7 else 0.0
                        leader_code = parts[8] if len(parts) > 8 else ''
                        leader_chg = float(parts[9]) if len(parts) > 9 else 0.0
                        items.append({
                            'name': name, 'code': key, 'change': change,
                            'amount': amount, 'leader_code': leader_code,
                            'leader_chg': leader_chg,
                        })
                    items.sort(key=lambda x: x['change'], reverse=True)
                    for row in items[:20]:
                        amt = row.get('amount', 0)
                        result.append({
                            'name': row['name'],
                            'code': row['code'],
                            'change': row['change'],
                            'leader': row.get('leader_code', ''),
                            'leader_change': row.get('leader_chg', 0),
                            'heat_display': '--',
                            **({'amount': amt} if amt > 0 else {}),
                        })
                    logger.info(f'热点行业获取成功（新浪 curl_cffi）: {len(result)}条')
                    _set_cached('hot_sectors', result)
                    return result
                except Exception as e2:
                    logger.debug(f'新浪 JS 解析失败: {e2}')
    except Exception as e:
        logger.debug(f'新浪 curl_cffi 行业板块失败: {e}')

    # 方法3: 东方财富 akshare
    try:
        from utils.ths_crawler import get_ths_industry_list
        df = get_ths_industry_list()
        if df is not None and not df.empty:
            for _, row in df.head(20).iterrows():
                amt = _sector_row_amount(row)
                result.append({
                    'name': row['板块'],
                    'code': row.get('代码', ''),
                    'change': _safe_float(row['涨跌幅']),
                    'leader': row.get('领涨股', ''),
                    'leader_change': _safe_float(row.get('领涨股-涨跌幅', 0)),
                    'heat_display': '--',
                    **({'amount': amt} if amt > 0 else {}),
                })
            logger.info(f'热点行业获取成功（东方财富备用）: {len(result)}条')
            _set_cached('hot_sectors', result)
            return result
    except Exception as e:
        logger.error(f'获取热点板块失败: {e}')

    return result


def get_hot_concept_sectors() -> List[Dict]:
    """
    概念板块排行。
    优先使用新浪概念板块API（含涨跌幅），备选东方财富接口。
    """
    cached = _get_cached('hot_concept_sectors')
    if isinstance(cached, list):
        return cached

    result: List[Dict] = []

    # 方法1：优先使用新浪概念板块API（curl_cffi绕过IP限制）
    # 新浪返回 JS 变量格式: var S_Finance_bankuai_class = {"gn_hwqc":"gn_hwqc,华为汽车,97,31.171...,0.6864731,...",...}
    try:
        from curl_cffi import requests as cr
        SINA_HEADERS = {
            'Referer': 'https://finance.sina.com.cn',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        url = 'https://vip.stock.finance.sina.com.cn/q/view/newFLJK.php?param=class'
        resp = cr.get(url, headers=SINA_HEADERS, impersonate='chrome110', timeout=15)
        if resp.status_code == 200 and resp.text and '<html>' not in resp.text[:50]:
            import re, json as _json
            # 尝试解析 JS 变量格式: var S_Finance_bankuai_class = {...}
            # 数据格式: key,"code,name,count,...,turnover,change,amount,leader_code,leader_price,leader_chg,leader_chg_amt,leader_name"
            js_var_match = re.search(r'=\s*(\{.+})', resp.text, re.DOTALL)
            if js_var_match:
                try:
                    raw_data = _json.loads(js_var_match.group(1))
                    items = []
                    for key, val in list(raw_data.items())[:40]:
                        parts = val.split(',')
                        name = parts[1].strip() if len(parts) > 1 else key.strip()
                        # parts[4] = 板块涨跌幅, parts[10] = 领涨股涨跌幅, parts[12] = 领涨股名称
                        change = float(parts[4]) if len(parts) > 4 else 0.0
                        leader = parts[12].strip() if len(parts) > 12 else ''
                        leader_chg = float(parts[10]) if len(parts) > 10 else 0.0
                        # parts[7] = 成交额
                        amount = float(parts[7]) if len(parts) > 7 else 0.0
                        items.append({
                            'name': name, 'code': key.strip(),
                            'change': change, 'leader': leader,
                            'leader_change': leader_chg, 'amount': amount,
                        })
                    # 按涨跌幅排序
                    items.sort(key=lambda x: x['change'], reverse=True)
                    for row in items:
                        amt = row.get('amount', 0)
                        if amt >= 1e8:
                            heat_display = f"{amt / 1e8:.2f}亿"
                        elif amt >= 1e4:
                            heat_display = f"{amt / 1e4:.2f}万"
                        else:
                            heat_display = '--'
                        result.append({
                            'name': row['name'], 'code': row['code'],
                            'change': row['change'], 'leader': row['leader'],
                            'leader_change': row['leader_change'],
                            'heat_display': heat_display,
                        })
                    logger.info(f'概念板块获取成功（新浪curl_cffi JS解析）: {len(result)}条')
                    if result:
                        _set_cached('hot_concept_sectors', result)
                        return result
                except Exception:
                    pass
            # 备用: <li><a href="...">板块名</a></li>
            pattern = r'<li><a href="[^"]*">([^<]+)</a></li>'
            names = re.findall(pattern, resp.text)
            for name in names[:40]:
                result.append({
                    'name': name.strip(),
                    'code': '',
                    'change': 0.0,
                    'leader': '',
                    'leader_change': 0.0,
                    'heat_display': '--',
                })
            logger.info(f'概念板块获取成功（新浪curl_cffi li解析）: {len(result)}条')
            if result:
                _set_cached('hot_concept_sectors', result)
                return result
        else:
            logger.debug(f'新浪概念板块返回非数据内容，状态码: {resp.status_code}')
    except Exception as e:
        logger.debug(f'新浪概念板块获取失败: {e}')

    # 方法2：备选东方财富概念板块名称接口
    try:
        with _ak_eastmoney_direct():
            df = _get_ak().stock_board_concept_name_em()
        if df is not None and not df.empty:
            name_c = '板块名称' if '板块名称' in df.columns else '名称'
            code_c = '板块代码' if '板块代码' in df.columns else '代码'
            if '涨跌幅' in df.columns:
                df = df.sort_values(by='涨跌幅', ascending=False)

            for _, row in df.head(40).iterrows():
                heat_raw = 0.0
                for hk in ('成交额', '总市值', '换手率', '成交量'):
                    if hk in df.columns:
                        heat_raw = _safe_float(row.get(hk))
                        break
                if heat_raw >= 1e8:
                    heat_display = f"{heat_raw / 1e8:.2f}亿"
                elif heat_raw >= 1e4:
                    heat_display = f"{heat_raw / 1e4:.2f}万"
                elif heat_raw > 0:
                    heat_display = f"{heat_raw:.2f}"
                else:
                    heat_display = '--'

                result.append({
                    'name': str(row.get(name_c, '') or ''),
                    'code': str(row.get(code_c, '') or ''),
                    'change': _safe_float(row.get('涨跌幅')),
                    'leader': str(row.get('领涨股票', '') or row.get('领涨股', '') or ''),
                    'leader_change': _safe_float(row.get('领涨股票-涨跌幅', row.get('领涨股-涨跌幅', 0))),
                    'heat_display': heat_display,
                })
            _set_cached('hot_concept_sectors', result)
            return result
    except Exception as e:
        logger.debug(f'东方财富概念板块获取失败: {e}')

    # 方法3：备选同花顺概念板块爬虫
    try:
        from utils.ths_crawler import get_ths_concept_list
        ths_df = get_ths_concept_list()
        if ths_df is not None and not ths_df.empty:
            name_col = '板块' if '板块' in ths_df.columns else '名称'
            code_col = '代码' if '代码' in ths_df.columns else None
            chg_col = '涨跌幅' if '涨跌幅' in ths_df.columns else None
            leader_col = '领涨股' if '领涨股' in ths_df.columns else None
            leader_chg_col = '领涨股-涨跌幅' if '领涨股-涨跌幅' in ths_df.columns else None
            amount_col = '总成交额' if '总成交额' in ths_df.columns else '成交额' if '成交额' in ths_df.columns else None

            for _, row in ths_df.head(40).iterrows():
                heat_raw = _safe_float(row.get(amount_col)) if amount_col else 0.0
                if heat_raw >= 1e8:
                    heat_display = f"{heat_raw / 1e8:.2f}亿"
                elif heat_raw >= 1e4:
                    heat_display = f"{heat_raw / 1e4:.2f}万"
                elif heat_raw > 0:
                    heat_display = f"{heat_raw:.2f}"
                else:
                    heat_display = '--'

                result.append({
                    'name': str(row.get(name_col, '') or ''),
                    'code': str(row.get(code_col, '') or '') if code_col else '',
                    'change': _safe_float(row.get(chg_col)) if chg_col else 0.0,
                    'leader': str(row.get(leader_col, '') or '') if leader_col else '',
                    'leader_change': _safe_float(row.get(leader_chg_col)) if leader_chg_col else 0.0,
                    'heat_display': heat_display,
                })
            logger.info(f'概念板块获取成功（同花顺）: {len(result)}条')
    except Exception as e:
        logger.debug(f'同花顺概念板块获取失败: {e}')

    _set_cached('hot_concept_sectors', result)
    return result


def get_sector_main_fund_flow(sector_kind: str) -> List[Dict]:
    """
    板块主力净流入柱状图数据（亿）。
    优先使用同花顺行业板块数据（含净流入字段），备选东方财富资金流向接口。
    kind=industry 行业板块，concept 概念板块，region 地域板块。
    """
    sk = (sector_kind or 'industry').lower()
    sector_type_map = {'industry': '行业资金流', 'concept': '概念资金流', 'region': '地域资金流'}
    sector_type = sector_type_map.get(sk, '行业资金流')

    cache_key = f'sector_main_fund_{sk}'
    cached = _get_cached(cache_key)
    if isinstance(cached, list) and len(cached) > 0:
        return cached

    result: List[Dict] = []

    # 方法1：优先使用同花顺行业板块数据（含净流入）
    if sk in ('industry', 'concept'):
        try:
            from utils.ths_crawler import get_ths_industry_list, get_ths_concept_list
            if sk == 'industry':
                ths_df = get_ths_industry_list()
            else:
                ths_df = get_ths_concept_list()

            if ths_df is not None and not ths_df.empty:
                net_col = '净流入' if '净流入' in ths_df.columns else None
                chg_col = '涨跌幅' if '涨跌幅' in ths_df.columns else None
                name_col = '板块' if '板块' in ths_df.columns else None

                if net_col and name_col:
                    # 同花顺数据按净流入排序（降序），取前3和后3
                    ths_sorted = ths_df.sort_values(by=net_col, ascending=False).reset_index(drop=True)
                    for _, row in ths_sorted.head(3).iterrows():
                        net_yi = _safe_float(row.get(net_col))  # 同花顺单位已是亿元
                        result.append({
                            'name': str(row.get(name_col, '') or ''),
                            'net_yi': round(net_yi, 2),
                            'change': _safe_float(row.get(chg_col)) if chg_col else 0.0,
                        })
                    for _, row in ths_sorted.tail(3).iterrows():
                        net_yi = _safe_float(row.get(net_col))
                        result.append({
                            'name': str(row.get(name_col, '') or ''),
                            'net_yi': round(net_yi, 2),
                            'change': _safe_float(row.get(chg_col)) if chg_col else 0.0,
                        })
                    logger.info(f'板块资金流向获取成功（同花顺-{sk}）: {len(result)}条')
                    _set_cached(cache_key, result)
                    return result
        except Exception as e:
            logger.debug(f'同花顺板块资金流获取失败({sk}): {e}')

    # 方法2：备选东方财富行业资金流（可能因网络封锁失败）
    try:
        with _ak_eastmoney_direct():
            fund_df = _get_ak().stock_sector_fund_flow_rank(
                indicator='今日', sector_type=sector_type
            )
        if fund_df is None or fund_df.empty:
            raise ValueError('资金流向返回空')

        # 今日主力净流入-净额（单位元），名称，今日涨跌幅
        net_col = next((c for c in (
            '今日主力净流入-净额', '5日主力净流入-净额', '10日主力净流入-净额',
            '主力净流入-净额',
        ) if c in fund_df.columns), None)
        chg_col = next((c for c in (
            '今日涨跌幅', '5日涨跌幅', '10日涨跌幅', '涨跌幅',
        ) if c in fund_df.columns), None)
        name_col = next((c for c in ('名称',) if c in fund_df.columns), None)

        if not net_col:
            logger.warning('资金流向缺少主力净流入列，兜底用涨跌幅')
            if chg_col:
                fund_sorted = fund_df.sort_values(by=chg_col, ascending=False).reset_index(drop=True)
                for _, row in fund_sorted.head(3).iterrows():
                    result.append({
                        'name': str(row.get(name_col, '') or '') if name_col else '',
                        'net_yi': 0.0,
                        'change': _safe_float(row.get(chg_col)),
                    })
                for _, row in fund_sorted.tail(3).iterrows():
                    result.append({
                        'name': str(row.get(name_col, '') or '') if name_col else '',
                        'net_yi': 0.0,
                        'change': _safe_float(row.get(chg_col)),
                    })
            _set_cached(cache_key, result)
            return result

        fund_df = fund_df.sort_values(by=net_col, ascending=False).reset_index(drop=True)

        for _, row in fund_df.head(3).iterrows():
            net_yi = _safe_float(row.get(net_col)) / 1e8
            result.append({
                'name': str(row.get(name_col, '') or '') if name_col else '',
                'net_yi': round(net_yi, 2),
                'change': _safe_float(row.get(chg_col)) if chg_col else 0.0,
            })
        for _, row in fund_df.tail(3).iterrows():
            net_yi = _safe_float(row.get(net_col)) / 1e8
            result.append({
                'name': str(row.get(name_col, '') or '') if name_col else '',
                'net_yi': round(net_yi, 2),
                'change': _safe_float(row.get(chg_col)) if chg_col else 0.0,
            })

        logger.info(f'板块资金流向获取成功({sector_type}): {len(result)}条')
    except Exception as e:
        logger.warning(f'板块资金流向获取失败({sector_kind}): {e}')
        _set_cached(cache_key, result)
        return result

    _set_cached(cache_key, result)
    return result


def compute_macro_sentiment() -> Dict:
    """
    综合市场量化指标 + 新闻情感，计算宏观情绪评分（0-100）。

    涨跌家数估算策略：
      1. 优先使用 snapshot.up/down_count（东方财富 stock_zh_a_spot_em）
      2. 其次使用北向资金覆盖股的涨跌家数（stock_hsgt_fund_flow_summary_em）
      3. 最后用上证指数涨跌幅估算（作为兜底）

    评分公式: SENTIMENT_SCORE = 50 + (up_pct - 0.5) × 40 + limit_diff/10 + north_bonus + news_bonus
      上限 92，下限 38。
    """
    try:
        snapshot = get_market_snapshot()
        flow = get_money_flow()
        limit = get_limit_up_data()
        overview = get_market_overview()

        # ── 1. 涨跌家数（多级兜底） ────────────────────────────────
        up   = int(snapshot.get('up_count', 0)   or 0)
        down = int(snapshot.get('down_count', 0) or 0)
        flat = int(snapshot.get('flat_count', 0)  or 0)

        # 兜底1：北向资金覆盖股涨跌家数（来自 stock_hsgt_fund_flow_summary_em）
        if up == 0 and down == 0:
            north_breadth = flow.get('breadth_from_north')
            if north_breadth:
                up = int(north_breadth.get('up', 0))
                down = int(north_breadth.get('down', 0))

        # 兜底2：上证指数涨跌幅估算全市场涨跌家数
        if up == 0 and down == 0:
            sh = next((x for x in overview if x.get('name') == '上证指数'), {})
            sh_chg = float(sh.get('change', 0) or 0)
            up_ratio_map = [
                (3.0,  0.80),
                (1.0,  0.60),
                (0.5,  0.55),
                (-0.5, 0.50),
                (-1.0, 0.45),
                (-3.0, 0.40),
                (-99,  0.20),
            ]
            up_ratio = 0.5
            for threshold, ratio in up_ratio_map:
                if sh_chg >= threshold:
                    up_ratio = ratio
                    break
            total_est = 5400
            up = int(total_est * up_ratio)
            down = total_est - up
            flat = 0

        total = max(1, up + down + flat)
        up_pct   = up   / total
        down_pct = down / total

        # ── 2. 涨跌停 ────────────────────────────────────────────────
        limit_up   = int(limit.get('limit_up_count', 0)   or 0)
        limit_down = int(limit.get('limit_down_count', 0) or 0)
        limit_diff = limit_up - limit_down

        # ── 3. 北向资金 ──────────────────────────────────────────────
        north_net = float(
            flow.get('north_money', {})
               .get('north_net_inflow', 0)
        )
        north_bonus = 8 if north_net >= 0 else -8

        # ── 4. 新闻情感 ───────────────────────────────────────────────
        try:
            from ticai.news_fetcher import get_market_news_summary
            news_summary = get_market_news_summary()
            news_score = float(news_summary.get('sentiment_score', 50))
        except Exception:
            news_score = 50.0
        news_bonus = (news_score - 50) / 5

        # ── 5. 综合评分 ──────────────────────────────────────────────
        raw = 50 \
            + (up_pct - 0.5) * 40 \
            + limit_diff / 10 \
            + north_bonus \
            + news_bonus
        raw = max(38, min(92, raw))
        score = round(raw)

        # ── 6. 风险等级 ──────────────────────────────────────────────
        if score >= 62:
            risk_level = 'MEDIUM'
        elif score >= 48:
            risk_level = 'MEDIUM-HIGH'
        else:
            risk_level = 'ELEVATED'

        # ── 7. 市场广度描述 ──────────────────────────────────────────
        breadth_desc = (
            '市场普涨，赚钱效应较强'
            if up_pct > 0.6
            else '市场普跌，赚钱效应较弱'
            if down_pct > 0.6
            else '多空分化，结构性行情'
        )

        # ── 8. 资金面简述 ────────────────────────────────────────────
        if north_net >= 5e8:
            money_desc = '北向资金大幅净流入，外资积极'
        elif north_net >= 0:
            money_desc = '北向资金小幅净流入'
        elif north_net >= -5e8:
            money_desc = '北向资金小幅净流出'
        else:
            money_desc = '北向资金大幅净流出，外资偏谨慎'

        # ── 9. 生成摘要段落 ──────────────────────────────────────────
        tone_words = {
            'MEDIUM':       '中性偏多',
            'MEDIUM-HIGH':  '偏谨慎',
            'ELEVATED':     '谨慎防御',
        }
        tone = tone_words[risk_level]

        if up_pct > 0.55 and limit_up > 50:
            market_desc = '市场情绪高涨，涨停家数较多，短线做多氛围浓'
        elif down_pct > 0.55:
            market_desc = '市场情绪偏弱，赚钱效应不足，注意控制仓位'
        else:
            market_desc = breadth_desc + '，' + money_desc

        breadth_note = ''
        if snapshot.get('up_count', 0) == 0 and snapshot.get('down_count', 0) == 0:
            breadth_note = '（估算）'

        summary_text = (
            f'今日{tone}。'
            f'上涨 {up} 家{breadth_note} / 下跌 {down} 家{breadth_note}（涨停 {limit_up} / 跌停 {limit_down}）。'
            f'{market_desc}。'
            f'建议关注高股息蓝筹与业绩确定性品种。'
        )

        # ── 10. 上证指数涨跌（用于对比参考） ─────────────────────────
        sh = next((x for x in overview if x.get('name') == '上证指数'), {})
        sh_change = sh.get('change', 0)
        sh_desc = (
            f'上证指数涨 {_fmt(sh_change)}%，'
            if sh_change > 0.05
            else f'上证指数跌 {_fmt(abs(sh_change))}%，'
            if sh_change < -0.05
            else '上证指数基本持平，'
        ) if sh else ''

        return {
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'sentiment_score': score,
            'risk_level': risk_level,
            'summary_text': sh_desc + summary_text,
            'breadth': {
                'up': up, 'down': down, 'flat': flat,
                'up_pct': round(up_pct * 100, 1),
                'down_pct': round(down_pct * 100, 1),
            },
            'limit': {
                'up': limit_up,
                'down': limit_down,
                'diff': limit_diff,
            },
            'north_money': {
                'net': round(north_net, 2),
                'bonus': north_bonus,
            },
            'news_score': round(news_score, 1),
            'raw_score': round(raw, 2),
        }
    except Exception as e:
        logger.error(f'compute_macro_sentiment failed: {e}')
        return {
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'sentiment_score': 50,
            'risk_level': 'MEDIUM',
            'summary_text': '数据加载中，请稍后刷新',
            'breadth': {'up': 0, 'down': 0, 'flat': 0, 'up_pct': 0, 'down_pct': 0},
            'limit': {'up': 0, 'down': 0, 'diff': 0},
            'north_money': {'net': 0, 'bonus': 0},
            'news_score': 50,
            'raw_score': 50,
        }


def _fmt(v) -> str:
    if v is None:
        return '--'
    return f'{v:.2f}'


def get_ai_summary() -> Dict:
    """
    获取 AI 市场简报数据（为 AI 分析准备数据）
    """
    overview = get_market_overview()
    flow = get_money_flow()
    limit = get_limit_up_data()
    sectors = get_hot_sectors()

    summary = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'market_status': '交易中' if 9 <= datetime.now().hour < 15 else '已休市',
        'overview': overview,
        'summary': {
            'shanghai': overview[0] if overview else {},
            'limit_up': limit['limit_up_count'],
            'limit_down': limit['limit_down_count'],
            'north_money': flow.get('north_money', {}),
        },
        'top_sectors': sectors[:10] if sectors else [],
        'hot_sectors': [s for s in sectors if s['change'] > 0][:10] if sectors else [],
    }

    return summary
