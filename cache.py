#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一缓存层
- 优先使用 Redis（跨进程、跨 worker 共享）
- Redis 不可用时自动降级为进程内 dict（TTL 精确，不影响功能）
- 业务层只需调用 get / set / invalidate，不关心底层实现
"""

import json
import time
import logging
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)

# ─── 底层驱动 ────────────────────────────────────────────────────────────────

_redis: Any = None
_redis_available: bool = False

def _init_redis():
    """延迟初始化 Redis，失败时静默降级。"""
    global _redis, _redis_available
    if _redis is not None:
        return _redis_available

    try:
        import redis
        # 从环境变量读取配置，支持 docker compose 注入
        host = os.environ.get('REDIS_HOST', 'localhost')
        port = int(os.environ.get('REDIS_PORT', 6379))
        password = os.environ.get('REDIS_PASSWORD', None)
        db = int(os.environ.get('REDIS_DB', 0))

        _redis = redis.Redis(
            host=host, port=port, password=password or None, db=db,
            socket_connect_timeout=2,
            socket_timeout=3,
            decode_responses=True,
        )
        _redis.ping()
        _redis_available = True
        logger.info('[Cache] Redis connected: %s:%d', host, port)
    except Exception as e:
        _redis = None
        _redis_available = False
        logger.info('[Cache] Redis unavailable (%s), falling back to in-process dict', e)
    return _redis_available


# ─── 进程内 dict 降级缓存 ─────────────────────────────────────────────────────

_mem: dict[str, tuple[Any, float]] = {}   # key → (value, expire_ts)


def _mem_get(key: str) -> Optional[Any]:
    """内存缓存读取，过期返回 None。"""
    entry = _mem.get(key)
    if entry is None:
        return None
    value, expire_ts = entry
    if time.time() > expire_ts:
        _mem.pop(key, None)
        return None
    return value


def _mem_set(key: str, value: Any, ttl: int):
    """内存缓存写入，TTL 秒。"""
    _mem[key] = (value, time.time() + ttl)


def _mem_invalidate(prefix: Optional[str] = None):
    """内存缓存清除。prefix=None 时清全部。"""
    global _mem
    if prefix is None:
        _mem = {}
    else:
        _mem = {k: v for k, v in _mem.items() if not k.startswith(prefix)}


# ─── 统一缓存 API ─────────────────────────────────────────────────────────────

import os

def get(key: str) -> Optional[Any]:
    """
    读取缓存。
    - Redis 可用 → Redis GET
    - 降级 → 进程内 dict
    """
    _init_redis()

    if _redis_available:
        try:
            raw = _redis.get(key)
            if raw is not None:
                return json.loads(raw)
        except Exception as e:
            logger.warning('[Cache] Redis GET %s failed: %s', key, e)

    return _mem_get(key)


def set(key: str, value: Any, ttl: int = 60):
    """
    写入缓存。
    - Redis 可用 → SETEX
    - 降级 → 进程内 dict
    """
    _init_redis()

    payload = json.dumps(value, ensure_ascii=False)

    if _redis_available:
        try:
            _redis.setex(key, ttl, payload)
            return
        except Exception as e:
            logger.warning('[Cache] Redis SET %s failed: %s', key, e)

    _mem_set(key, value, ttl)


def invalidate(prefix: Optional[str] = None):
    """
    清除缓存。
    - prefix=None → 清全部
    - prefix='abc/' → 清所有以 'abc/' 开头的 key
    """
    _init_redis()

    if _redis_available:
        try:
            if prefix is None:
                _redis.flushdb()
            else:
                cursor = 0
                while True:
                    cursor, keys = _redis.scan(cursor, match=f'{prefix}*', count=200)
                    if keys:
                        _redis.delete(*keys)
                    if cursor == 0:
                        break
            return
        except Exception as e:
            logger.warning('[Cache] Redis invalidate(%s) failed: %s', prefix, e)

    _mem_invalidate(prefix)


def cached(key: str, ttl: int = 60, fetch_fn: Optional[Callable[[], Any]] = None):
    """
    读-通模式：命中缓存直接返回；未命中则调用 fetch_fn，将结果写入缓存后返回。

    用法示例：
        data = cached('market/overview', ttl=15, fetch_fn=get_market_overview)

    等价于：
        data = get('market/overview')
        if data is None:
            data = get_market_overview()
            set('market/overview', data, ttl=15)
    """
    data = get(key)
    if data is not None:
        return data
    if fetch_fn is not None:
        data = fetch_fn()
        set(key, data, ttl)
    return data


# ─── 路由装饰器（简化 market_routes / strategy_routes） ───────────────────────

def route_cached(blueprint, rule: str, key: str, ttl: int = 60):
    """
    Flask 路由装饰器：自动为 endpoint 加上 Redis 缓存。

    用法：
        @route_cached(market_bp, '/api/market/overview', 'market/overview', ttl=15)
        def api_market_overview():
            data = get_market_overview()
            return jsonify({'success': True, 'data': data})

    装饰器内部已处理：
    - 从 Redis / dict 读缓存
    - 缓存未命中时执行原函数
    - 将结果写入缓存后返回 JSON
    - 异常 → 降级执行原函数（不写缓存）
    """
    from flask import jsonify

    def decorator(fn):
        import functools

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # 先读缓存
            hit = get(key)
            if hit is not None:
                return jsonify({'success': True, 'data': hit})

            # 未命中，执行原函数
            try:
                result = fn(*args, **kwargs)
                # 正常返回 Flask Response 时才缓存（排除重定向等）
                if hasattr(result, 'get_json'):
                    payload = result.get_json()
                    if isinstance(payload, dict) and payload.get('success'):
                        set(key, payload.get('data'), ttl)
                return result
            except Exception as e:
                # 出错降级：不走缓存，直接抛
                logger.warning('[Cache] route_cached(%s) error, bypass: %s', key, e)
                raise

        # 注册路由（让 blueprint 自动收集）
        blueprint.add_url_rule(rule, view_func=wrapper, methods=['GET'])
        return fn

    return decorator
