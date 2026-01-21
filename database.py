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
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scan_results_scan_id ON scan_results(scan_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scan_records_scan_time ON scan_records(scan_time DESC)')


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
    删除指定扫描记录及其结果
    
    Args:
        scan_id: 扫描记录ID
        
    Returns:
        是否删除成功
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 先删除关联的结果
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
        
        # 删除所有结果
        cursor.execute('DELETE FROM scan_results')
        
        # 删除所有扫描记录
        cursor.execute('DELETE FROM scan_records')
        
        return cursor.rowcount


# 初始化数据库
init_db()
