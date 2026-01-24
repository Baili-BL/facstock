#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite 数据库模块 - 扫描结果存储
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# 数据库文件路径
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DB_PATH = os.path.join(DB_DIR, 'stock.db')


def get_db_path() -> str:
    """获取数据库路径，确保目录存在"""
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
    return DB_PATH


@contextmanager
def get_connection():
    """获取数据库连接的上下文管理器"""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """初始化数据库表"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 扫描记录主表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'scanning',
                progress INTEGER DEFAULT 0,
                current_sector TEXT DEFAULT '',
                hot_sectors_json TEXT,
                error TEXT,
                params_json TEXT
            )
        ''')
        
        # 扫描结果表（按板块存储）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER NOT NULL,
                sector_name TEXT NOT NULL,
                sector_change REAL,
                stocks_json TEXT,
                FOREIGN KEY (scan_id) REFERENCES scan_records(id) ON DELETE CASCADE
            )
        ''')
        
        # K线数据缓存表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kline_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                scan_id INTEGER,
                cache_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                data_json TEXT NOT NULL,
                FOREIGN KEY (scan_id) REFERENCES scan_records(id) ON DELETE CASCADE
            )
        ''')
        
        # 自选股表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL UNIQUE,
                stock_name TEXT NOT NULL,
                sector_name TEXT,
                add_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                note TEXT
            )
        ''')
        
        # AI分析报告表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER,
                report_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                model TEXT,
                tokens_used INTEGER DEFAULT 0,
                news_data TEXT,
                scan_data_summary TEXT,
                analysis TEXT NOT NULL,
                FOREIGN KEY (scan_id) REFERENCES scan_records(id) ON DELETE SET NULL
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scan_results_scan_id ON scan_results(scan_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scan_records_scan_time ON scan_records(scan_time DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_kline_cache_stock_code ON kline_cache(stock_code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_kline_cache_scan_id ON kline_cache(scan_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_watchlist_stock_code ON watchlist(stock_code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_reports_time ON ai_reports(report_time DESC)')


def create_scan_record(params: Dict = None) -> int:
    """
    创建新的扫描记录
    
    Args:
        params: 扫描参数字典
        
    Returns:
        新创建的扫描记录ID
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO scan_records (scan_time, status, params_json)
            VALUES (?, 'scanning', ?)
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), json.dumps(params or {})))
        return cursor.lastrowid


def update_scan_progress(scan_id: int, progress: int, current_sector: str):
    """更新扫描进度"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE scan_records 
            SET progress = ?, current_sector = ?
            WHERE id = ?
        ''', (progress, current_sector, scan_id))


def update_scan_status(scan_id: int, status: str, error: str = None):
    """
    更新扫描状态
    
    Args:
        scan_id: 扫描记录ID
        status: 状态 (scanning/completed/error)
        error: 错误信息
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        if error:
            cursor.execute('''
                UPDATE scan_records 
                SET status = ?, error = ?, progress = 100
                WHERE id = ?
            ''', (status, error, scan_id))
        else:
            cursor.execute('''
                UPDATE scan_records 
                SET status = ?, progress = 100, current_sector = '扫描完成'
                WHERE id = ?
            ''', (status, scan_id))


def save_hot_sectors(scan_id: int, hot_sectors: List[Dict]):
    """保存热点板块信息"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE scan_records 
            SET hot_sectors_json = ?
            WHERE id = ?
        ''', (json.dumps(hot_sectors, ensure_ascii=False), scan_id))


def save_sector_result(scan_id: int, sector_name: str, sector_change: float, stocks: List[Dict]):
    """
    保存板块扫描结果
    
    Args:
        scan_id: 扫描记录ID
        sector_name: 板块名称
        sector_change: 板块涨跌幅
        stocks: 股票列表
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO scan_results (scan_id, sector_name, sector_change, stocks_json)
            VALUES (?, ?, ?, ?)
        ''', (scan_id, sector_name, sector_change, json.dumps(stocks, ensure_ascii=False)))


def get_scan_list(limit: int = 20) -> List[Dict]:
    """
    获取扫描记录列表
    
    Args:
        limit: 返回记录数量限制
        
    Returns:
        扫描记录列表
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.id, r.scan_time, r.status, r.progress, r.current_sector, 
                   r.hot_sectors_json, r.error, r.params_json,
                   COUNT(s.id) as sector_count,
                   SUM(
                       CASE 
                           WHEN s.stocks_json IS NOT NULL 
                           THEN json_array_length(s.stocks_json) 
                           ELSE 0 
                       END
                   ) as stock_count
            FROM scan_records r
            LEFT JOIN scan_results s ON r.id = s.scan_id
            GROUP BY r.id
            ORDER BY r.scan_time DESC
            LIMIT ?
        ''', (limit,))
        
        records = []
        for row in cursor.fetchall():
            record = {
                'id': row['id'],
                'scan_time': row['scan_time'],
                'status': row['status'],
                'progress': row['progress'],
                'current_sector': row['current_sector'],
                'error': row['error'],
                'sector_count': row['sector_count'] or 0,
                'stock_count': row['stock_count'] or 0,
            }
            
            # 解析热点板块
            if row['hot_sectors_json']:
                try:
                    record['hot_sectors'] = json.loads(row['hot_sectors_json'])
                except json.JSONDecodeError:
                    record['hot_sectors'] = []
            else:
                record['hot_sectors'] = []
            
            # 解析参数
            if row['params_json']:
                try:
                    record['params'] = json.loads(row['params_json'])
                except json.JSONDecodeError:
                    record['params'] = {}
            else:
                record['params'] = {}
                
            records.append(record)
            
        return records


def get_scan_detail(scan_id: int) -> Optional[Dict]:
    """
    获取单次扫描的详细结果
    
    Args:
        scan_id: 扫描记录ID
        
    Returns:
        扫描详情，包含所有板块结果
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 获取扫描记录
        cursor.execute('''
            SELECT id, scan_time, status, progress, current_sector, 
                   hot_sectors_json, error, params_json
            FROM scan_records
            WHERE id = ?
        ''', (scan_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
            
        record = {
            'id': row['id'],
            'scan_time': row['scan_time'],
            'status': row['status'],
            'progress': row['progress'],
            'current_sector': row['current_sector'],
            'error': row['error'],
        }
        
        # 解析热点板块
        if row['hot_sectors_json']:
            try:
                record['hot_sectors'] = json.loads(row['hot_sectors_json'])
            except json.JSONDecodeError:
                record['hot_sectors'] = []
        else:
            record['hot_sectors'] = []
        
        # 获取扫描结果
        cursor.execute('''
            SELECT sector_name, sector_change, stocks_json
            FROM scan_results
            WHERE scan_id = ?
        ''', (scan_id,))
        
        results = {}
        for result_row in cursor.fetchall():
            stocks = []
            if result_row['stocks_json']:
                try:
                    stocks = json.loads(result_row['stocks_json'])
                except json.JSONDecodeError:
                    stocks = []
            
            results[result_row['sector_name']] = {
                'change': result_row['sector_change'],
                'stocks': stocks
            }
        
        record['results'] = results
        return record


def get_latest_scan() -> Optional[Dict]:
    """获取最新一次完成的扫描结果"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id FROM scan_records 
            WHERE status = 'completed'
            ORDER BY scan_time DESC 
            LIMIT 1
        ''')
        row = cursor.fetchone()
        if row:
            return get_scan_detail(row['id'])
        return None


def get_current_scan_status(scan_id: int) -> Optional[Dict]:
    """获取指定扫描的当前状态"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, status, progress, current_sector, error
            FROM scan_records
            WHERE id = ?
        ''', (scan_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
            
        return {
            'id': row['id'],
            'is_scanning': row['status'] == 'scanning',
            'status': row['status'],
            'progress': row['progress'],
            'current_sector': row['current_sector'],
            'error': row['error']
        }


def delete_scan(scan_id: int) -> bool:
    """
    删除指定扫描记录及其结果和关联的K线缓存
    
    Args:
        scan_id: 扫描记录ID
        
    Returns:
        是否删除成功
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 先删除关联的K线缓存
        cursor.execute('DELETE FROM kline_cache WHERE scan_id = ?', (scan_id,))
        
        # 删除关联的结果
        cursor.execute('DELETE FROM scan_results WHERE scan_id = ?', (scan_id,))
        
        # 再删除扫描记录
        cursor.execute('DELETE FROM scan_records WHERE id = ?', (scan_id,))
        
        return cursor.rowcount > 0


def delete_all_scans() -> int:
    """
    删除所有扫描记录
    
    Returns:
        删除的记录数量
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 删除所有K线缓存
        cursor.execute('DELETE FROM kline_cache')
        
        # 删除所有结果
        cursor.execute('DELETE FROM scan_results')
        
        # 删除所有扫描记录
        cursor.execute('DELETE FROM scan_records')
        
        return cursor.rowcount


# ==================== K线缓存相关函数 ====================

def save_kline_cache(stock_code: str, data: Dict, scan_id: int = None):
    """
    保存K线数据到缓存
    
    Args:
        stock_code: 股票代码
        data: K线数据字典
        scan_id: 关联的扫描ID（可选）
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 如果已存在相同股票代码的缓存，先删除（保持最新）
        cursor.execute('DELETE FROM kline_cache WHERE stock_code = ?', (stock_code,))
        
        # 插入新缓存
        cursor.execute('''
            INSERT INTO kline_cache (stock_code, scan_id, cache_time, data_json)
            VALUES (?, ?, ?, ?)
        ''', (stock_code, scan_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
              json.dumps(data, ensure_ascii=False)))


def get_kline_cache(stock_code: str, max_age_hours: int = 24) -> Optional[Dict]:
    """
    获取K线缓存数据
    
    Args:
        stock_code: 股票代码
        max_age_hours: 缓存最大有效时间（小时），默认24小时
        
    Returns:
        缓存的K线数据，如果不存在或已过期则返回None
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 获取缓存，检查时间有效性
        cursor.execute('''
            SELECT data_json, cache_time
            FROM kline_cache
            WHERE stock_code = ?
            ORDER BY cache_time DESC
            LIMIT 1
        ''', (stock_code,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        # 检查缓存是否过期
        cache_time = datetime.strptime(row['cache_time'], '%Y-%m-%d %H:%M:%S')
        age_hours = (datetime.now() - cache_time).total_seconds() / 3600
        
        if age_hours > max_age_hours:
            return None
        
        try:
            return json.loads(row['data_json'])
        except json.JSONDecodeError:
            return None


def delete_kline_cache_by_scan(scan_id: int) -> int:
    """
    删除指定扫描关联的K线缓存
    
    Args:
        scan_id: 扫描记录ID
        
    Returns:
        删除的记录数量
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM kline_cache WHERE scan_id = ?', (scan_id,))
        return cursor.rowcount


def delete_expired_kline_cache(max_age_hours: int = 72) -> int:
    """
    删除过期的K线缓存
    
    Args:
        max_age_hours: 超过多少小时算过期，默认72小时
        
    Returns:
        删除的记录数量
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cutoff_time = datetime.now()
        cursor.execute('''
            DELETE FROM kline_cache 
            WHERE datetime(cache_time) < datetime(?, '-' || ? || ' hours')
        ''', (cutoff_time.strftime('%Y-%m-%d %H:%M:%S'), max_age_hours))
        return cursor.rowcount


def get_kline_cache_stats() -> Dict:
    """
    获取K线缓存统计信息
    
    Returns:
        统计信息字典
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as count FROM kline_cache')
        count = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(DISTINCT stock_code) as unique_stocks FROM kline_cache')
        unique_stocks = cursor.fetchone()['unique_stocks']
        
        return {
            'total_cache': count,
            'unique_stocks': unique_stocks
        }


# ==================== 自选股相关函数 ====================

def add_to_watchlist(stock_code: str, stock_name: str, sector_name: str = None, note: str = None) -> bool:
    """
    添加股票到自选列表
    
    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        sector_name: 所属板块
        note: 备注
        
    Returns:
        是否添加成功
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO watchlist (stock_code, stock_name, sector_name, add_time, note)
                VALUES (?, ?, ?, ?, ?)
            ''', (stock_code, stock_name, sector_name, 
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), note))
            return True
        except Exception:
            return False


def remove_from_watchlist(stock_code: str) -> bool:
    """
    从自选列表移除股票
    
    Args:
        stock_code: 股票代码
        
    Returns:
        是否移除成功
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM watchlist WHERE stock_code = ?', (stock_code,))
        return cursor.rowcount > 0


def get_watchlist() -> List[Dict]:
    """
    获取自选列表
    
    Returns:
        自选股票列表
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT stock_code, stock_name, sector_name, add_time, note
            FROM watchlist
            ORDER BY add_time DESC
        ''')
        
        stocks = []
        for row in cursor.fetchall():
            stocks.append({
                'code': row['stock_code'],
                'name': row['stock_name'],
                'sector': row['sector_name'],
                'add_time': row['add_time'],
                'note': row['note']
            })
        return stocks


def is_in_watchlist(stock_code: str) -> bool:
    """
    检查股票是否在自选列表中
    
    Args:
        stock_code: 股票代码
        
    Returns:
        是否在自选列表中
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM watchlist WHERE stock_code = ?', (stock_code,))
        return cursor.fetchone() is not None


def clear_watchlist() -> int:
    """
    清空自选列表
    
    Returns:
        删除的记录数量
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM watchlist')
        return cursor.rowcount


# ==================== AI 报告管理 ====================

def save_ai_report(analysis: str, model: str = None, tokens_used: int = 0, 
                   scan_id: int = None, news_data: str = None, scan_data_summary: str = None) -> int:
    """
    保存 AI 分析报告
    
    Args:
        analysis: AI 分析内容
        model: 使用的模型
        tokens_used: 使用的 token 数量
        scan_id: 关联的扫描记录 ID
        news_data: 新闻数据摘要
        scan_data_summary: 扫描数据摘要
        
    Returns:
        报告 ID
    """
    from datetime import datetime
    local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ai_reports (scan_id, report_time, model, tokens_used, news_data, scan_data_summary, analysis)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (scan_id, local_time, model, tokens_used, news_data, scan_data_summary, analysis))
        return cursor.lastrowid


def get_ai_reports(limit: int = 20) -> List[Dict]:
    """
    获取 AI 报告列表
    
    Args:
        limit: 返回数量限制
        
    Returns:
        报告列表
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, scan_id, report_time, model, tokens_used, 
                   news_data, scan_data_summary, analysis
            FROM ai_reports
            ORDER BY report_time DESC
            LIMIT ?
        ''', (limit,))
        
        reports = []
        for row in cursor.fetchall():
            reports.append({
                'id': row['id'],
                'scan_id': row['scan_id'],
                'report_time': row['report_time'],
                'model': row['model'],
                'tokens_used': row['tokens_used'],
                'news_data': row['news_data'],
                'scan_data_summary': row['scan_data_summary'],
                'analysis': row['analysis']
            })
        return reports


def get_ai_report(report_id: int) -> Optional[Dict]:
    """
    获取单个 AI 报告详情
    
    Args:
        report_id: 报告 ID
        
    Returns:
        报告详情
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, scan_id, report_time, model, tokens_used,
                   news_data, scan_data_summary, analysis
            FROM ai_reports
            WHERE id = ?
        ''', (report_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                'id': row['id'],
                'scan_id': row['scan_id'],
                'report_time': row['report_time'],
                'model': row['model'],
                'tokens_used': row['tokens_used'],
                'news_data': row['news_data'],
                'scan_data_summary': row['scan_data_summary'],
                'analysis': row['analysis']
            }
        return None


def delete_ai_report(report_id: int) -> bool:
    """
    删除 AI 报告
    
    Args:
        report_id: 报告 ID
        
    Returns:
        是否删除成功
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM ai_reports WHERE id = ?', (report_id,))
        return cursor.rowcount > 0


def delete_all_ai_reports() -> int:
    """
    删除所有 AI 报告
    
    Returns:
        删除的数量
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM ai_reports')
        return cursor.rowcount


# 初始化数据库
init_db()
