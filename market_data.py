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
import os
import time
import pandas as pd
import requests
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


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


# 缓存相关
_cache = {}
_cache_timeout = 300  # 5分钟缓存


def _get_cached(key: str) -> Optional[any]:
    """获取缓存数据"""
    if key in _cache:
        data, timestamp = _cache[key]
        if datetime.now().timestamp() - timestamp < _cache_timeout:
            return data
    return None


def _set_cached(key: str, data: any):
    """设置缓存数据"""
    _cache[key] = (data, datetime.now().timestamp())


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


def get_market_overview() -> List[Dict]:
    """
    获取大盘指数概览（上证、深证、创业板、科创板等）
    使用 stock_zh_index_spot_sina 获取实时指数数据（新浪，数据源稳定）
    """
    cached = _get_cached('market_overview')
    if isinstance(cached, list) and len(cached) > 0:
        return cached

    result = []
    try:
        df = _get_ak().stock_zh_index_spot_sina()
        if df is None or df.empty:
            return []

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

        for code, name in needed.items():
            rows = df[df['代码'] == code]
            if rows.empty:
                continue
            r = rows.iloc[0]
            result.append({
                'name': name,
                'code': code,
                'price': _safe_float(r.get('最新价')),
                'change': _safe_float(r.get('涨跌幅')),
                'change_amount': _safe_float(r.get('涨跌额')),
                'volume': _safe_float(r.get('成交量')),
                'amount': _safe_float(r.get('成交额')),
                'high': _safe_float(r.get('最高')),
                'low': _safe_float(r.get('最低')),
                'open': _safe_float(r.get('今开')),
                'prev_close': _safe_float(r.get('昨收')),
            })

        # 获取上涨/下跌家数（从东方财富市场概况）
        try:
            with _ak_eastmoney_direct():
                df_em = _get_ak().stock_zh_a_spot_em()
            if df_em is not None and not df_em.empty:
                total = len(df_em)
                up = int((df_em['涨跌幅'] > 0).sum())
                down = int((df_em['涨跌幅'] < 0).sum())
                flat = total - up - down
                sh = next((x for x in result if x['name'] == '上证指数'), None)
                if sh:
                    sh['up_count'] = up
                    sh['down_count'] = down
                    sh['flat_count'] = flat
        except Exception:
            pass

    except Exception as e:
        logger.warning(f"获取大盘指数失败: {e}")

    _set_cached('market_overview', result)
    return result


def get_money_flow() -> Dict:
    """
    获取市场资金流向（北向资金、主力净流入等）
    使用沪深港通资金流向数据
    """
    cached = _get_cached('money_flow')
    if cached:
        return cached

    result = {
        'north_money': {},
        'sector_flow': [],
        'time': datetime.now().strftime('%H:%M'),
    }

    try:
        with _ak_eastmoney_direct():
            df = _get_ak().stock_hsgt_fund_flow_summary_em()
        if df is not None and not df.empty:
            hgt_net = 0.0
            sgt_net = 0.0
            north_total = 0.0
            for _, row in df.iterrows():
                net_inflow = _safe_float(row.get('成交净买额'))
                if row.get('板块') == '沪股通':
                    hgt_net += net_inflow
                    north_total += net_inflow
                elif row.get('板块') == '深股通':
                    sgt_net += net_inflow
                    north_total += net_inflow
            result['hgt_net_inflow'] = round(hgt_net, 2)
            result['sgt_net_inflow'] = round(sgt_net, 2)
            result['north_money'] = {
                'north_net_inflow': round(north_total, 2),
                'north_net_buy': round(north_total, 2),
                'date': str(df.iloc[-1].get('交易日', '')),
            }
    except Exception as e:
        logger.warning(f"北向资金获取失败: {e}")

    _set_cached('money_flow', result)
    return result


def get_limit_up_data() -> Dict:
    """
    获取涨跌停数据
    涨停池: stock_zt_pool_em
    跌停池: stock_zt_pool_dtgc_em（大跌股，含跌停）
    """
    cached = _get_cached('limit_up')
    if cached:
        return cached

    today = datetime.now().strftime('%Y%m%d')
    result = {
        'limit_up_count': 0,
        'limit_down_count': 0,
        'limit_up_stocks': [],
        'time': datetime.now().strftime('%H:%M'),
    }

    try:
        with _ak_eastmoney_direct():
            up_df = _get_ak().stock_zt_pool_em(date=today)
        if up_df is not None and not up_df.empty:
            result['limit_up_count'] = len(up_df)
            for _, row in up_df.head(10).iterrows():
                result['limit_up_stocks'].append({
                    'name': str(row.get('名称', '')),
                    'code': str(row.get('代码', '')),
                    'change': _safe_float(row.get('涨跌幅')),
                    'reason': str(row.get('涨停统计', '')),
                })
    except Exception as e:
        logger.warning(f"涨停池获取失败: {e}")

    try:
        with _ak_eastmoney_direct():
            down_df = _get_ak().stock_zt_pool_dtgc_em(date=today)
        if down_df is not None and not down_df.empty:
            # 大跌股中过滤出跌停（涨跌幅 <= -9.9）
            limit_down = down_df[down_df['涨跌幅'] <= -9.9]
            result['limit_down_count'] = len(limit_down)
    except Exception as e:
        logger.warning(f"大跌股池获取失败: {e}")

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
        _set_cached('market_snapshot', out)

    # ── 立即返回新浪数据 ──────────────────────────────────────────────
    if out['top_gainers']:
        return out

    # ── 方案二：东方财富 EM（后台异步，下次请求时生效）────────────
    # EM 需要 ~11 秒，直接在后台获取，不阻塞返回
    _fetch_em_snapshot()
    return out


def _fetch_em_snapshot():
    """东方财富全量快照（后台异步，写入 Redis 缓存，下次生效）"""
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
            with _ak_eastmoney_direct():
                df = _get_ak().stock_zh_a_spot_em()
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

            # 写内存缓存（EM 涨跌家数/成交额等与新浪合并展示）
            _set_cached('market_snapshot', out)
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


def _fetch_spot_em_dataframe() -> Optional[pd.DataFrame]:
    """全 A 现货（含所属行业），写入内存缓存（调用较慢，宜放后台线程）。"""
    try:
        with _ak_eastmoney_direct():
            df = _get_ak().stock_zh_a_spot_em()
    except Exception as e:
        logger.warning('stock_zh_a_spot_em 获取失败: %s', e)
        return None
    if df is None or df.empty:
        return None
    _spot_em_cache['df'] = df
    _spot_em_cache['ts'] = time.time()
    return df


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
    获取热点板块（同花顺数据源，已内置降级到东方财富）
    """
    cached = _get_cached('hot_sectors')
    if cached:
        return cached

    from utils.ths_crawler import get_ths_industry_list

    try:
        df = get_ths_industry_list()
        if df is None or df.empty:
            return []

        result = []
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

        _set_cached('hot_sectors', result)
        return result

    except Exception as e:
        logger.error(f"获取热点板块失败: {e}")
        return []


def get_hot_concept_sectors() -> List[Dict]:
    """
    东方财富概念板块排行（与行业板块结构对齐，便于前端同表展示）
    """
    cached = _get_cached('hot_concept_sectors')
    if isinstance(cached, list):
        return cached

    result: List[Dict] = []
    try:
        with _ak_eastmoney_direct():
            df = _get_ak().stock_board_concept_name_em()
        if df is None or df.empty:
            _set_cached('hot_concept_sectors', result)
            return result

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
    except Exception as e:
        logger.warning(f"概念板块获取失败: {e}")

    _set_cached('hot_concept_sectors', result)
    return result


def get_sector_main_fund_flow(sector_kind: str) -> List[Dict]:
    """
    板块主力净流入（单位：亿），东方财富 push2.eastmoney.com 直接请求。
    sector_kind: industry | concept | region → 行业资金流 / 概念资金流 / 地域资金流
    返回 6 条：净流入前三 + 净流出前三（柱状图用）。
    """
    sector_type_map = {
        'industry': '行业资金流',
        'concept': '概念资金流',
        'region': '地域资金流',
    }
    fs_map = {
        'industry': 'm:90+t:2',
        'concept': 'm:90+t:3+f:!50',
        'region': 'm:90+t:1',
    }
    sk = (sector_kind or 'industry').lower()
    st = sector_type_map.get(sk, '行业资金流')
    fs = fs_map.get(sk, 'm:90+t:2')
    cache_key = f'sector_main_fund_{sk}'
    cached = _get_cached(cache_key)
    if isinstance(cached, list):
        return cached

    result: List[Dict] = []
    try:
        import time as _time
        rt = int(_time.time() * 1000)
        url = (
            'https://push2.eastmoney.com/api/qt/clist/get'
            f'?pn=1&pz=100&po=1&np=1'
            f'&ut=b2884a393a59ad64002292a3e90d46a5'
            f'&fltt=2&invt=2&fid=f62'
            f'&fs={fs}'
            f'&fields=f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124'
            f'&rt={rt}'
        )
        # 使用 trust_env=False 的 Session 绕过系统代理
        session = requests.Session()
        session.trust_env = False
        resp = session.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Referer': 'https://data.eastmoney.com/bkzj/hy.html',
            'Accept': '*/*',
        }, timeout=15)
        session.close()
        resp.raise_for_status()
        data = resp.json()
        diff = (data.get('data') or {}).get('diff') or []
        if not diff:
            _set_cached(cache_key, result)
            return result

        rows = []
        for r in diff:
            net_yuan = float(r.get('f62') or 0)
            rows.append({
                'name': str(r.get('f14') or ''),
                'net_yi': round(net_yuan / 1e8, 2),
                'change': _safe_float(r.get('f3', 0)),
                '_net': net_yuan,
            })
        rows.sort(key=lambda x: x['_net'], reverse=True)
        n = len(rows)
        if n == 0:
            _set_cached(cache_key, result)
            return result

        def _pick(r) -> Dict:
            return {
                'name': r['name'],
                'net_yi': r['net_yi'],
                'change': r['change'],
            }

        if n <= 6:
            for r in rows:
                result.append(_pick(r))
        else:
            for r in rows[:3]:
                result.append(_pick(r))
            for r in rows[-3:]:
                result.append(_pick(r))
    except Exception as e:
        logger.warning(f'板块主力净流入获取失败: {e}')

    _set_cached(cache_key, result)
    return result


def compute_macro_sentiment() -> Dict:
    """
    综合市场量化指标 + 新闻情感，计算宏观情绪评分（0-100）。

    涨跌家数估算策略：
      - 优先使用 snapshot.up/down_count（东方财富数据，最准确）
      - 备选：使用上证指数涨跌幅估算涨跌家数比（EM 不可用时）
        +3% 以上 → 全市场普涨（约 80% 上涨）
        +1% ~ +3% → 多数上涨（约 60% 上涨）
        +0.5% ~ +1% → 略偏多（约 55% 上涨）
        -0.5% ~ +0.5% → 基本均衡（约 50% 上涨）
        -0.5% ~ -1% → 略偏空（约 45% 上涨）
        -1% ~ -3% → 多数下跌（约 40% 上涨）
        -3% 以下 → 全市场普跌（约 20% 上涨）
      - 公式: SENTIMENT_SCORE = 50 + (up_pct - 0.5) × 40 + (涨停-跌停)/10 + (北向>0?+8:-8) + (新闻分-50)/5
      - 上限 92，下限 38。
      - RISK_LEVEL: ≥62→MEDIUM, 48-61→MEDIUM-HIGH, <48→ELEVATED
    """
    try:
        snapshot = get_market_snapshot()
        flow = get_money_flow()
        limit = get_limit_up_data()
        overview = get_market_overview()

        # ── 1. 涨跌家数（优先 snapshot；备选用指数估算） ───────────────
        up   = int(snapshot.get('up_count', 0)   or 0)
        down = int(snapshot.get('down_count', 0) or 0)
        flat = int(snapshot.get('flat_count', 0)  or 0)

        if up == 0 and down == 0:
            # EM 不可用，通过指数涨跌幅估算涨跌家数比
            sh = next((x for x in overview if x.get('name') == '上证指数'), {})
            sh_chg = float(sh.get('change', 0) or 0)
            # 根据指数涨跌幅映射上涨比例
            up_ratio_map = [
                (3.0,  0.80),
                (1.0,  0.60),
                (0.5,  0.55),
                (-0.5, 0.50),
                (-1.0, 0.45),
                (-3.0, 0.40),
                (-99,  0.20),
            ]
            up_ratio = 0.5  # 默认
            for threshold, ratio in up_ratio_map:
                if sh_chg >= threshold:
                    up_ratio = ratio
                    break
            # A 股全市场约 5500 只，估算涨跌家数
            total_est = 5400
            up_est = int(total_est * up_ratio)
            down_est = total_est - up_est
            up = up_est
            down = down_est
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
            else f'上证指数跌 {abs(_fmt(sh_change))}%，'
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
