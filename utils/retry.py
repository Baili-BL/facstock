#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重试工具模块
============

提供网络请求重试功能，处理各种网络异常情况。
"""

import time
from typing import Callable, TypeVar, Optional, Any

T = TypeVar('T')


def retry_request(
    func: Callable[[], T],
    max_retries: int = 5,
    delay: float = 1.0,
    silent: bool = False
) -> Optional[T]:
    """
    重试装饰器，用于处理网络请求失败的情况
    
    Args:
        func: 要执行的函数（无参数，返回结果）
        max_retries: 最大重试次数，默认5次
        delay: 基础重试间隔（秒），默认1.0秒
        silent: 是否静默模式（失败不抛异常，返回None），默认False
    
    Returns:
        函数执行结果，如果全部失败：
        - silent=True 时返回 None
        - silent=False 时抛出最后一个异常
    
    Raises:
        Exception: 当 silent=False 且所有重试都失败时，抛出最后捕获的异常
    
    Example:
        >>> def fetch_data():
        ...     return requests.get('https://api.example.com/data').json()
        >>> 
        >>> # 基本用法
        >>> result = retry_request(fetch_data)
        >>> 
        >>> # 自定义重试参数
        >>> result = retry_request(fetch_data, max_retries=3, delay=2.0)
        >>> 
        >>> # 静默模式（失败返回None）
        >>> result = retry_request(fetch_data, silent=True)
    
    Note:
        - 网络连接类错误（ConnectionError, Timeout等）会使用更长的递增延迟
        - 其他错误使用标准递增延迟
        - 延迟计算公式：delay * (attempt + 1) * multiplier
          - 网络错误 multiplier = 2
          - 其他错误 multiplier = 1
    """
    import requests
    
    last_exception: Optional[Exception] = None
    
    for attempt in range(max_retries):
        try:
            return func()
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
            ConnectionResetError,
            ConnectionAbortedError
        ) as e:
            # 网络连接类错误，等待更长时间后重试
            last_exception = e
            if attempt < max_retries - 1:
                wait_time = delay * (attempt + 1) * 2  # 更长的递增延迟
                time.sleep(wait_time)
        except Exception as e:
            # 其他错误
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))
    
    # 所有重试都失败
    if silent:
        return None
    if last_exception:
        raise last_exception
    return None
