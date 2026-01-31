#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 端点单元测试
================

测试 Flask API 端点的正确性，包括：
- 热点板块接口
- 扫描任务接口
- 股票详情接口
- 参数验证

需求: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
"""

import pytest
import json
import os
import tempfile
from unittest.mock import patch, Mock, MagicMock
import pandas as pd

# 设置测试环境
os.environ['TESTING'] = 'true'

import database as db
from app import app


@pytest.fixture
def client():
    """创建 Flask 测试客户端"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def test_db():
    """创建测试数据库（使用 MySQL）"""
    # 设置测试数据库名
    os.environ['MYSQL_DATABASE'] = 'stock_scanner_test'
    
    # 重新加载数据库配置
    db.DB_CONFIG['database'] = 'stock_scanner_test'
    
    # 初始化数据库
    db.init_db()
    
    # 清理所有数据
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM kline_cache')
        cursor.execute('DELETE FROM scan_results')
        cursor.execute('DELETE FROM ai_reports')
        cursor.execute('DELETE FROM watchlist')
        cursor.execute('DELETE FROM scan_records')
        conn.commit()
    
    yield db
    
    # 测试后清理
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM kline_cache')
        cursor.execute('DELETE FROM scan_results')
        cursor.execute('DELETE FROM ai_reports')
        cursor.execute('DELETE FROM watchlist')
        cursor.execute('DELETE FROM scan_records')
        conn.commit()


class TestHotSectorsAPI:
    """热点板块接口测试"""
    
    @patch('app.retry_request')
    def test_get_hot_sectors_success(self, mock_retry, client):
        """测试成功获取热点板块"""
        mock_df = pd.DataFrame({
            '板块名称': ['半导体', '新能源', '银行'],
            '涨跌幅': [5.2, 3.1, 2.0],
            '领涨股票': ['中芯国际', '宁德时代', '招商银行'],
            '领涨股票-涨跌幅': [10.0, 8.5, 5.0]
        })
        mock_retry.return_value = mock_df
        
        response = client.get('/api/hot-sectors')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['success'] is True
        assert len(data['data']) == 3
        assert data['data'][0]['name'] == '半导体'
        assert data['data'][0]['change'] == 5.2
    
    @patch('app.retry_request')
    def test_get_hot_sectors_with_limit(self, mock_retry, client):
        """测试带 limit 参数获取热点板块"""
        mock_df = pd.DataFrame({
            '板块名称': ['半导体', '新能源', '银行', '医药', '科技'],
            '涨跌幅': [5.2, 3.1, 2.0, 1.5, 1.0],
            '领涨股票': ['A', 'B', 'C', 'D', 'E'],
            '领涨股票-涨跌幅': [10.0, 8.5, 5.0, 4.0, 3.0]
        })
        mock_retry.return_value = mock_df
        
        response = client.get('/api/hot-sectors?limit=2')
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert len(data['data']) == 2
    
    @patch('app.retry_request')
    def test_get_hot_sectors_limit_clamped(self, mock_retry, client):
        """测试 limit 参数被限制在有效范围"""
        mock_df = pd.DataFrame({
            '板块名称': ['半导体'],
            '涨跌幅': [5.2],
            '领涨股票': ['中芯国际'],
            '领涨股票-涨跌幅': [10.0]
        })
        mock_retry.return_value = mock_df
        
        # 测试超过最大值
        response = client.get('/api/hot-sectors?limit=100')
        assert response.status_code == 200
        
        # 测试小于最小值
        response = client.get('/api/hot-sectors?limit=0')
        assert response.status_code == 200
    
    @patch('app.retry_request')
    def test_get_hot_sectors_empty_data(self, mock_retry, client):
        """测试空数据返回错误"""
        mock_retry.return_value = pd.DataFrame()
        
        response = client.get('/api/hot-sectors')
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert 'error' in data
    
    @patch('app.retry_request')
    def test_get_hot_sectors_exception(self, mock_retry, client):
        """测试异常处理"""
        mock_retry.side_effect = Exception("网络错误")
        
        response = client.get('/api/hot-sectors')
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert '网络错误' in data['error']


class TestScanAPI:
    """扫描任务接口测试"""
    
    def test_start_scan_success(self, client, test_db):
        """测试启动扫描"""
        # 重置扫描状态
        import app as app_module
        app_module.scan_status = {
            'is_scanning': False,
            'scan_id': None,
            'progress': 0,
            'current_sector': '',
            'error': None,
            'cancelled': False
        }
        
        with patch.object(app_module.threading, 'Thread') as mock_thread:
            mock_thread_instance = Mock()
            mock_thread.return_value = mock_thread_instance
            
            response = client.post('/api/scan/start',
                                   data=json.dumps({'sectors': 3, 'min_days': 2}),
                                   content_type='application/json')
            data = json.loads(response.data)
            
            assert response.status_code == 200
            assert data['success'] is True
            assert 'scan_id' in data
    
    def test_start_scan_already_running(self, client):
        """测试扫描进行中时无法启动新扫描"""
        import app as app_module
        app_module.scan_status['is_scanning'] = True
        
        response = client.post('/api/scan/start',
                               data=json.dumps({}),
                               content_type='application/json')
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert '正在进行中' in data['error']
        
        # 恢复状态
        app_module.scan_status['is_scanning'] = False
    
    def test_start_scan_parameter_validation(self, client, test_db):
        """测试参数验证和默认值"""
        import app as app_module
        app_module.scan_status = {
            'is_scanning': False,
            'scan_id': None,
            'progress': 0,
            'current_sector': '',
            'error': None,
            'cancelled': False
        }
        
        with patch.object(app_module.threading, 'Thread') as mock_thread:
            mock_thread_instance = Mock()
            mock_thread.return_value = mock_thread_instance
            
            # 测试超出范围的参数会被限制
            response = client.post('/api/scan/start',
                                   data=json.dumps({'sectors': 100, 'min_days': 50, 'period': 200}),
                                   content_type='application/json')
            data = json.loads(response.data)
            
            assert data['success'] is True
    
    def test_get_scan_status(self, client):
        """测试获取扫描状态"""
        import app as app_module
        app_module.scan_status = {
            'is_scanning': True,
            'scan_id': 1,
            'progress': 50,
            'current_sector': '半导体',
            'error': None,
            'cancelled': False
        }
        
        response = client.get('/api/scan/status')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['is_scanning'] is True
        assert data['progress'] == 50
        assert data['current_sector'] == '半导体'
        
        # 恢复状态
        app_module.scan_status['is_scanning'] = False
    
    def test_cancel_scan_success(self, client):
        """测试取消扫描"""
        import app as app_module
        app_module.scan_status = {
            'is_scanning': True,
            'scan_id': 1,
            'progress': 50,
            'current_sector': '半导体',
            'error': None,
            'cancelled': False
        }
        
        response = client.post('/api/scan/cancel')
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert app_module.scan_status['cancelled'] is True
        
        # 恢复状态
        app_module.scan_status['is_scanning'] = False
        app_module.scan_status['cancelled'] = False
    
    def test_cancel_scan_not_running(self, client):
        """测试没有扫描时取消失败"""
        import app as app_module
        app_module.scan_status['is_scanning'] = False
        
        response = client.post('/api/scan/cancel')
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert '没有正在进行的扫描' in data['error']
    
    def test_get_scan_results_empty(self, client, test_db):
        """测试获取空扫描结果"""
        response = client.get('/api/scan/results')
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['results'] == {}
        assert data['hot_sectors'] == []
    
    def test_get_scan_results_with_data(self, client, test_db):
        """测试获取有数据的扫描结果"""
        # 创建测试数据
        scan_id = test_db.create_scan_record({'sectors': 5})
        test_db.save_hot_sectors(scan_id, [{'name': '半导体', 'change': 5.0}])
        test_db.save_sector_result(scan_id, '半导体', 5.0, [
            {'code': '000001', 'name': '测试股票', 'total_score': 80}
        ])
        test_db.update_scan_status(scan_id, 'completed')
        
        response = client.get('/api/scan/results')
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['scan_id'] == scan_id
        assert '半导体' in data['results']
    
    def test_get_scan_history(self, client, test_db):
        """测试获取扫描历史"""
        # 创建多条记录
        for i in range(3):
            test_db.create_scan_record({'index': i})
        
        response = client.get('/api/scan/history?limit=2')
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert len(data['data']) == 2
    
    def test_get_scan_detail_not_found(self, client, test_db):
        """测试获取不存在的扫描详情"""
        response = client.get('/api/scan/99999')
        data = json.loads(response.data)
        
        assert response.status_code == 404
        assert data['success'] is False
    
    def test_delete_scan_success(self, client, test_db):
        """测试删除扫描记录"""
        scan_id = test_db.create_scan_record()
        
        response = client.delete(f'/api/scan/{scan_id}')
        data = json.loads(response.data)
        
        assert data['success'] is True
    
    def test_delete_scan_running(self, client, test_db):
        """测试无法删除正在进行的扫描"""
        import app as app_module
        scan_id = test_db.create_scan_record()
        app_module.scan_status = {
            'is_scanning': True,
            'scan_id': scan_id,
            'progress': 50,
            'current_sector': '测试',
            'error': None,
            'cancelled': False
        }
        
        response = client.delete(f'/api/scan/{scan_id}')
        data = json.loads(response.data)
        
        assert response.status_code == 400
        assert data['success'] is False
        
        # 恢复状态
        app_module.scan_status['is_scanning'] = False


class TestStockDetailAPI:
    """股票详情接口测试"""
    
    def test_get_stock_detail_invalid_code(self, client):
        """测试无效股票代码"""
        # 空代码
        response = client.get('/api/stock/')
        assert response.status_code == 404
        
        # 非数字代码
        response = client.get('/api/stock/abcdef')
        data = json.loads(response.data)
        assert data['success'] is False
        assert '无效的股票代码' in data['error']
        
        # 长度不对
        response = client.get('/api/stock/12345')
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_get_stock_detail_from_cache(self, client, test_db):
        """测试从缓存获取股票详情"""
        # 预存缓存数据
        cache_data = {
            'candles': [{'time': '2024-01-01', 'close': 10.0}],
            'volumes': [{'time': '2024-01-01', 'value': 1000}]
        }
        test_db.save_kline_cache('000001', cache_data)
        
        response = client.get('/api/stock/000001')
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['cached'] is True
        assert data['data']['candles'][0]['close'] == 10.0


class TestCacheAPI:
    """缓存接口测试"""
    
    def test_get_cache_stats(self, client, test_db):
        """测试获取缓存统计"""
        test_db.save_kline_cache('000001', {'data': 'test1'})
        test_db.save_kline_cache('000002', {'data': 'test2'})
        
        response = client.get('/api/cache/stats')
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['data']['total_cache'] == 2
    
    def test_clear_cache(self, client, test_db):
        """测试清理缓存"""
        response = client.delete('/api/cache/clear')
        data = json.loads(response.data)
        
        assert data['success'] is True


class TestWatchlistAPI:
    """自选股接口测试"""
    
    def test_get_watchlist_empty(self, client, test_db):
        """测试获取空自选列表"""
        response = client.get('/api/watchlist')
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['data'] == []
    
    def test_add_to_watchlist(self, client, test_db):
        """测试添加自选股"""
        response = client.post('/api/watchlist/add',
                               data=json.dumps({'code': '000001', 'name': '平安银行'}),
                               content_type='application/json')
        data = json.loads(response.data)
        
        assert data['success'] is True
    
    def test_add_to_watchlist_missing_params(self, client, test_db):
        """测试缺少参数时添加失败"""
        response = client.post('/api/watchlist/add',
                               data=json.dumps({'code': '000001'}),
                               content_type='application/json')
        data = json.loads(response.data)
        
        assert data['success'] is False
        assert '缺少' in data['error']
    
    def test_remove_from_watchlist(self, client, test_db):
        """测试移除自选股"""
        # 先添加
        test_db.add_to_watchlist('000001', '平安银行')
        
        response = client.post('/api/watchlist/remove',
                               data=json.dumps({'code': '000001'}),
                               content_type='application/json')
        data = json.loads(response.data)
        
        assert data['success'] is True
    
    def test_check_watchlist(self, client, test_db):
        """测试检查自选状态"""
        test_db.add_to_watchlist('000001', '平安银行')
        
        response = client.get('/api/watchlist/check/000001')
        data = json.loads(response.data)
        
        assert data['success'] is True
        assert data['in_watchlist'] is True
        
        response = client.get('/api/watchlist/check/000002')
        data = json.loads(response.data)
        
        assert data['in_watchlist'] is False


class TestIndexRoute:
    """主页路由测试"""
    
    def test_index_returns_html(self, client):
        """测试主页返回 HTML"""
        response = client.get('/')
        
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data
