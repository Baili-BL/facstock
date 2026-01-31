#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库操作单元测试
==================

测试数据库 CRUD 操作的正确性，包括：
- 扫描记录管理
- K线缓存
- 边界条件

需求: 6.1, 6.2, 6.3, 6.5, 6.6

注意: 测试需要 MySQL 数据库连接
可通过环境变量配置测试数据库:
- MYSQL_HOST: 数据库主机 (默认 localhost)
- MYSQL_PORT: 端口 (默认 3306)
- MYSQL_USER: 用户名 (默认 root)
- MYSQL_PASSWORD: 密码 (默认空)
- MYSQL_DATABASE: 数据库名 (默认 stock_scanner_test)
"""

import pytest
import os
import json
from datetime import datetime, timedelta

# 设置测试数据库名
os.environ.setdefault('MYSQL_DATABASE', 'stock_scanner_test')

import database as db


@pytest.fixture(scope='function')
def test_db():
    """创建测试数据库并清理数据"""
    # 初始化数据库
    db.init_db()
    
    # 清理所有数据
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM kline_cache')
        cursor.execute('DELETE FROM sector_stocks_cache')
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
        cursor.execute('DELETE FROM sector_stocks_cache')
        cursor.execute('DELETE FROM scan_results')
        cursor.execute('DELETE FROM ai_reports')
        cursor.execute('DELETE FROM watchlist')
        cursor.execute('DELETE FROM scan_records')
        conn.commit()


class TestScanRecordManagement:
    """扫描记录管理测试"""
    
    def test_create_scan_record(self, test_db):
        """测试创建扫描记录"""
        params = {'sectors': 5, 'min_days': 3, 'period': 20}
        scan_id = test_db.create_scan_record(params)
        
        assert scan_id is not None
        assert scan_id > 0
    
    def test_create_scan_record_without_params(self, test_db):
        """测试不带参数创建扫描记录"""
        scan_id = test_db.create_scan_record()
        
        assert scan_id is not None
        assert scan_id > 0
    
    def test_update_scan_progress(self, test_db):
        """测试更新扫描进度"""
        scan_id = test_db.create_scan_record()
        
        result = test_db.update_scan_progress(scan_id, 50, "测试板块")
        
        assert result is True
        
        # 验证更新
        detail = test_db.get_scan_detail(scan_id)
        assert detail['progress'] == 50
        assert detail['current_sector'] == "测试板块"
    
    def test_update_scan_progress_clamps_value(self, test_db):
        """测试进度值被限制在 0-100 范围内"""
        scan_id = test_db.create_scan_record()
        
        # 测试超过 100
        test_db.update_scan_progress(scan_id, 150, "测试")
        detail = test_db.get_scan_detail(scan_id)
        assert detail['progress'] == 100
        
        # 测试小于 0
        test_db.update_scan_progress(scan_id, -10, "测试")
        detail = test_db.get_scan_detail(scan_id)
        assert detail['progress'] == 0
    
    def test_update_scan_status_completed(self, test_db):
        """测试更新扫描状态为完成"""
        scan_id = test_db.create_scan_record()
        
        result = test_db.update_scan_status(scan_id, 'completed')
        
        assert result is True
        
        detail = test_db.get_scan_detail(scan_id)
        assert detail['status'] == 'completed'
        assert detail['progress'] == 100
    
    def test_update_scan_status_error(self, test_db):
        """测试更新扫描状态为错误"""
        scan_id = test_db.create_scan_record()
        
        result = test_db.update_scan_status(scan_id, 'error', '测试错误信息')
        
        assert result is True
        
        detail = test_db.get_scan_detail(scan_id)
        assert detail['status'] == 'error'
        assert detail['error'] == '测试错误信息'
    
    def test_update_scan_status_invalid(self, test_db):
        """测试无效状态值抛出异常"""
        scan_id = test_db.create_scan_record()
        
        with pytest.raises(ValueError):
            test_db.update_scan_status(scan_id, 'invalid_status')
    
    def test_save_hot_sectors(self, test_db):
        """测试保存热点板块"""
        scan_id = test_db.create_scan_record()
        hot_sectors = [
            {'name': '半导体', 'change': 5.2},
            {'name': '新能源', 'change': 3.1}
        ]
        
        result = test_db.save_hot_sectors(scan_id, hot_sectors)
        
        assert result is True
        
        detail = test_db.get_scan_detail(scan_id)
        assert len(detail['hot_sectors']) == 2
        assert detail['hot_sectors'][0]['name'] == '半导体'
    
    def test_save_sector_result(self, test_db):
        """测试保存板块扫描结果"""
        scan_id = test_db.create_scan_record()
        stocks = [
            {'code': '000001', 'name': '平安银行', 'total_score': 75},
            {'code': '000002', 'name': '万科A', 'total_score': 60}
        ]
        
        result = test_db.save_sector_result(scan_id, '银行', 2.5, stocks)
        
        # 验证数据已保存
        detail = test_db.get_scan_detail(scan_id)
        assert '银行' in detail['results']
        assert detail['results']['银行']['change'] == 2.5
        assert len(detail['results']['银行']['stocks']) == 2
    
    def test_get_scan_list(self, test_db):
        """测试获取扫描记录列表"""
        # 创建多条记录
        for i in range(5):
            test_db.create_scan_record({'index': i})
        
        records = test_db.get_scan_list(limit=3)
        
        assert len(records) == 3
    
    def test_get_scan_detail_not_found(self, test_db):
        """测试获取不存在的扫描记录"""
        detail = test_db.get_scan_detail(99999)
        
        assert detail is None
    
    def test_get_latest_scan(self, test_db):
        """测试获取最新完成的扫描"""
        # 创建并完成一个扫描
        scan_id = test_db.create_scan_record()
        test_db.update_scan_status(scan_id, 'completed')
        
        latest = test_db.get_latest_scan()
        
        assert latest is not None
        assert latest['id'] == scan_id
    
    def test_get_latest_scan_no_completed(self, test_db):
        """测试没有完成的扫描时返回 None"""
        # 创建但不完成
        test_db.create_scan_record()
        
        latest = test_db.get_latest_scan()
        
        assert latest is None
    
    def test_delete_scan(self, test_db):
        """测试删除扫描记录"""
        scan_id = test_db.create_scan_record()
        
        result = test_db.delete_scan(scan_id)
        
        assert result is True
        assert test_db.get_scan_detail(scan_id) is None
    
    def test_delete_scan_not_found(self, test_db):
        """测试删除不存在的扫描记录"""
        result = test_db.delete_scan(99999)
        
        assert result is False


class TestKlineCache:
    """K线缓存测试"""
    
    def test_save_and_get_kline_cache(self, test_db):
        """测试保存和获取K线缓存"""
        data = {
            'candles': [{'time': '2024-01-01', 'close': 10.0}],
            'volumes': [{'time': '2024-01-01', 'value': 1000}]
        }
        
        result = test_db.save_kline_cache('000001', data)
        assert result is True
        
        cached = test_db.get_kline_cache('000001')
        assert cached is not None
        assert cached['candles'][0]['close'] == 10.0
    
    def test_save_kline_cache_empty_code(self, test_db):
        """测试空股票代码抛出异常"""
        with pytest.raises(ValueError):
            test_db.save_kline_cache('', {'data': 'test'})
    
    def test_save_kline_cache_empty_data(self, test_db):
        """测试空数据抛出异常"""
        with pytest.raises(ValueError):
            test_db.save_kline_cache('000001', {})
    
    def test_get_kline_cache_not_found(self, test_db):
        """测试获取不存在的缓存"""
        cached = test_db.get_kline_cache('999999')
        
        assert cached is None
    
    def test_get_kline_cache_empty_code(self, test_db):
        """测试空股票代码返回 None"""
        cached = test_db.get_kline_cache('')
        
        assert cached is None
    
    def test_kline_cache_overwrites_existing(self, test_db):
        """测试缓存会覆盖已存在的数据"""
        test_db.save_kline_cache('000001', {'version': 1})
        test_db.save_kline_cache('000001', {'version': 2})
        
        cached = test_db.get_kline_cache('000001')
        assert cached['version'] == 2
    
    def test_delete_expired_kline_cache(self, test_db):
        """测试删除过期缓存"""
        # 保存一条缓存
        test_db.save_kline_cache('000001', {'data': 'test'})
        
        # 删除过期缓存
        count = test_db.delete_expired_kline_cache()
        
        # 当日缓存不会被删除
        assert count >= 0
    
    def test_get_kline_cache_stats(self, test_db):
        """测试获取缓存统计"""
        test_db.save_kline_cache('000001', {'data': 'test1'})
        test_db.save_kline_cache('000002', {'data': 'test2'})
        
        stats = test_db.get_kline_cache_stats()
        
        assert stats['today_cache'] == 2
        assert stats['total_cache'] == 2
    
    def test_get_kline_cache_batch(self, test_db):
        """测试批量获取K线缓存"""
        test_db.save_kline_cache('000001', {'data': 'test1'})
        test_db.save_kline_cache('000002', {'data': 'test2'})
        
        result = test_db.get_kline_cache_batch(['000001', '000002', '000003'])
        
        assert len(result) == 2
        assert '000001' in result
        assert '000002' in result


class TestSectorStocksCache:
    """板块成分股缓存测试"""
    
    def test_save_and_get_sector_stocks_cache(self, test_db):
        """测试保存和获取成分股缓存"""
        stocks = [
            {'code': '000001', 'name': '平安银行'},
            {'code': '000002', 'name': '万科A'}
        ]
        
        result = test_db.save_sector_stocks_cache('银行', stocks)
        assert result is True
        
        cached = test_db.get_sector_stocks_cache('银行')
        assert cached is not None
        assert len(cached) == 2
    
    def test_get_all_sector_stocks_cache(self, test_db):
        """测试批量获取成分股缓存"""
        test_db.save_sector_stocks_cache('银行', [{'code': '000001'}])
        test_db.save_sector_stocks_cache('科技', [{'code': '000002'}])
        
        result = test_db.get_all_sector_stocks_cache(['银行', '科技', '医药'])
        
        assert len(result) == 2
        assert '银行' in result
        assert '科技' in result


class TestWatchlist:
    """自选股测试"""
    
    def test_add_to_watchlist(self, test_db):
        """测试添加自选股"""
        result = test_db.add_to_watchlist('000001', '平安银行', '银行', '测试备注')
        assert result is True
        
        stocks = test_db.get_watchlist()
        assert len(stocks) == 1
        assert stocks[0]['code'] == '000001'
    
    def test_remove_from_watchlist(self, test_db):
        """测试移除自选股"""
        test_db.add_to_watchlist('000001', '平安银行')
        
        result = test_db.remove_from_watchlist('000001')
        assert result is True
        
        stocks = test_db.get_watchlist()
        assert len(stocks) == 0
    
    def test_is_in_watchlist(self, test_db):
        """测试检查是否在自选"""
        test_db.add_to_watchlist('000001', '平安银行')
        
        assert test_db.is_in_watchlist('000001') is True
        assert test_db.is_in_watchlist('000002') is False


class TestAIReports:
    """AI报告测试"""
    
    def test_save_ai_report(self, test_db):
        """测试保存AI报告"""
        report_id = test_db.save_ai_report(
            analysis='测试分析内容',
            model='gpt-4',
            tokens_used=100
        )
        
        assert report_id > 0
    
    def test_get_ai_reports(self, test_db):
        """测试获取AI报告列表"""
        test_db.save_ai_report(analysis='报告1')
        test_db.save_ai_report(analysis='报告2')
        
        reports = test_db.get_ai_reports(limit=10)
        assert len(reports) == 2
    
    def test_delete_ai_report(self, test_db):
        """测试删除AI报告"""
        report_id = test_db.save_ai_report(analysis='测试')
        
        result = test_db.delete_ai_report(report_id)
        assert result is True
        
        report = test_db.get_ai_report(report_id)
        assert report is None


class TestDatabaseEdgeCases:
    """数据库边界情况测试"""
    
    def test_chinese_characters_in_data(self, test_db):
        """测试中文字符的存储和读取"""
        scan_id = test_db.create_scan_record()
        hot_sectors = [{'name': '半导体芯片', 'change': 5.0}]
        
        test_db.save_hot_sectors(scan_id, hot_sectors)
        
        detail = test_db.get_scan_detail(scan_id)
        assert detail['hot_sectors'][0]['name'] == '半导体芯片'
    
    def test_special_characters_in_data(self, test_db):
        """测试特殊字符的存储和读取"""
        data = {'note': '测试 "引号" 和 \'单引号\' 以及 \n 换行'}
        
        test_db.save_kline_cache('000001', data)
        
        cached = test_db.get_kline_cache('000001')
        assert '引号' in cached['note']
    
    def test_large_data_storage(self, test_db):
        """测试大数据量存储"""
        # 创建包含 100 条记录的数据
        candles = [{'time': f'2024-01-{i:02d}', 'close': float(i)} for i in range(1, 100)]
        data = {'candles': candles}
        
        test_db.save_kline_cache('000001', data)
        
        cached = test_db.get_kline_cache('000001')
        assert len(cached['candles']) == 99
