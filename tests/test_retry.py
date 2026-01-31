#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
retry_request 单元测试
======================

测试重试机制的正确性，包括：
- 重试次数
- 递增延迟
- 静默模式
- 异常处理

需求: 1.5, 2.5, 3.4, 8.4
"""

import pytest
import time
from unittest.mock import Mock, patch
import requests

from utils.retry import retry_request


class TestRetryRequest:
    """retry_request 函数测试"""
    
    def test_success_on_first_try(self):
        """测试首次成功的情况"""
        mock_func = Mock(return_value="success")
        
        result = retry_request(mock_func, max_retries=3)
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    def test_success_after_retries(self):
        """测试重试后成功的情况"""
        mock_func = Mock(side_effect=[
            requests.exceptions.ConnectionError("连接失败"),
            requests.exceptions.ConnectionError("连接失败"),
            "success"
        ])
        
        result = retry_request(mock_func, max_retries=5, delay=0.01)
        
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_max_retries_exceeded(self):
        """测试超过最大重试次数后抛出异常"""
        mock_func = Mock(side_effect=requests.exceptions.ConnectionError("连接失败"))
        
        with pytest.raises(requests.exceptions.ConnectionError):
            retry_request(mock_func, max_retries=3, delay=0.01)
        
        assert mock_func.call_count == 3
    
    def test_silent_mode_returns_none(self):
        """测试静默模式下失败返回 None"""
        mock_func = Mock(side_effect=requests.exceptions.ConnectionError("连接失败"))
        
        result = retry_request(mock_func, max_retries=3, delay=0.01, silent=True)
        
        assert result is None
        assert mock_func.call_count == 3
    
    def test_handles_timeout_error(self):
        """测试处理超时错误"""
        mock_func = Mock(side_effect=[
            requests.exceptions.Timeout("超时"),
            "success"
        ])
        
        result = retry_request(mock_func, max_retries=3, delay=0.01)
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    def test_handles_chunked_encoding_error(self):
        """测试处理分块编码错误"""
        mock_func = Mock(side_effect=[
            requests.exceptions.ChunkedEncodingError("编码错误"),
            "success"
        ])
        
        result = retry_request(mock_func, max_retries=3, delay=0.01)
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    def test_handles_connection_reset_error(self):
        """测试处理连接重置错误"""
        mock_func = Mock(side_effect=[
            ConnectionResetError("连接重置"),
            "success"
        ])
        
        result = retry_request(mock_func, max_retries=3, delay=0.01)
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    def test_handles_generic_exception(self):
        """测试处理通用异常"""
        mock_func = Mock(side_effect=[
            ValueError("值错误"),
            "success"
        ])
        
        result = retry_request(mock_func, max_retries=3, delay=0.01)
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    def test_delay_between_retries(self):
        """测试重试之间有延迟"""
        mock_func = Mock(side_effect=[
            requests.exceptions.ConnectionError("连接失败"),
            "success"
        ])
        
        start_time = time.time()
        result = retry_request(mock_func, max_retries=3, delay=0.1)
        elapsed_time = time.time() - start_time
        
        assert result == "success"
        # 网络错误使用 delay * (attempt + 1) * 2 = 0.1 * 1 * 2 = 0.2 秒
        assert elapsed_time >= 0.15  # 允许一些误差
    
    def test_incremental_delay_for_network_errors(self):
        """测试网络错误使用递增延迟"""
        call_times = []
        
        def track_time():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise requests.exceptions.ConnectionError("连接失败")
            return "success"
        
        result = retry_request(track_time, max_retries=5, delay=0.05)
        
        assert result == "success"
        assert len(call_times) == 3
        
        # 第一次重试延迟: 0.05 * 1 * 2 = 0.1
        # 第二次重试延迟: 0.05 * 2 * 2 = 0.2
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        
        assert delay1 >= 0.08  # 允许误差
        assert delay2 >= 0.15  # 第二次延迟应该更长
    
    def test_returns_none_when_no_exception_and_silent(self):
        """测试无异常但函数返回 None 时的行为"""
        mock_func = Mock(return_value=None)
        
        result = retry_request(mock_func, max_retries=3, silent=True)
        
        assert result is None
        assert mock_func.call_count == 1  # 成功返回，不重试


class TestRetryRequestEdgeCases:
    """retry_request 边界情况测试"""
    
    def test_max_retries_one(self):
        """测试 max_retries=1 的情况"""
        mock_func = Mock(side_effect=requests.exceptions.ConnectionError("连接失败"))
        
        with pytest.raises(requests.exceptions.ConnectionError):
            retry_request(mock_func, max_retries=1, delay=0.01)
        
        assert mock_func.call_count == 1
    
    def test_zero_delay(self):
        """测试 delay=0 的情况"""
        mock_func = Mock(side_effect=[
            requests.exceptions.ConnectionError("连接失败"),
            "success"
        ])
        
        result = retry_request(mock_func, max_retries=3, delay=0)
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    def test_preserves_exception_type(self):
        """测试保留原始异常类型"""
        mock_func = Mock(side_effect=ValueError("自定义错误"))
        
        with pytest.raises(ValueError) as exc_info:
            retry_request(mock_func, max_retries=2, delay=0.01)
        
        assert "自定义错误" in str(exc_info.value)
