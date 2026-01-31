#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL 数据库模块 - 扫描结果存储
支持 MySQL 5.7+
"""

import pymysql
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# MySQL 数据库配置（可通过环境变量覆盖）
DB_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', 'localhost'),
    'port': int(os.environ.get('MYSQL_PORT', 3306)),
    'user': os.environ.get('MYSQL_USER', 'root'),
    'password': os.environ.get('MYSQL_PASSWORD', ''),
    'database': os.environ.get('MYSQL_DATABASE', 'stock_scanner'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit': False
}


def get_db_config() -> Dict:
    """获取数据库配置"""
    return DB_CONFIG.copy()


@contextmanager
def get_connection():
    """获取数据库连接的上下文管理器"""
    conn = pymysql.connect(**DB_CONFIG)
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
    # 先创建数据库（如果不存在）
    config_no_db = DB_CONFIG.copy()
    db_name = config_no_db.pop('database')
    
    conn = pymysql.connect(**config_no_db)
    try:
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
    finally:
        conn.close()
    
    # 创建表
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 扫描记录主表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_records (
                id INT AUTO_INCREMENT PRIMARY KEY,
                scan_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(20) DEFAULT 'scanning',
                progress INT DEFAULT 0,
                current_sector VARCHAR(100) DEFAULT '',
                hot_sectors_json LONGTEXT,
                error TEXT,
                params_json TEXT,
                INDEX idx_scan_time (scan_time DESC)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        
        # 扫描结果表（按板块存储）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_results (
                id INT AUTO_INCREMENT PRIMARY KEY,
                scan_id INT NOT NULL,
                sector_name VARCHAR(100) NOT NULL,
                sector_change DECIMAL(10,2),
                stocks_json LONGTEXT,
                INDEX idx_scan_id (scan_id),
                FOREIGN KEY (scan_id) REFERENCES scan_records(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        
        # 板块成分股缓存表（sector_name 为主键，每日更新）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sector_stocks_cache (
                sector_name VARCHAR(100) PRIMARY KEY,
                cache_date DATE NOT NULL,
                stocks_json LONGTEXT NOT NULL,
                INDEX idx_cache_date (cache_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        
        # K线数据缓存表（stock_code 为主键，当日有效）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kline_cache (
                stock_code VARCHAR(20) PRIMARY KEY,
                cache_date DATE NOT NULL,
                data_json LONGTEXT NOT NULL,
                INDEX idx_cache_date (cache_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        
        # 自选股表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                id INT AUTO_INCREMENT PRIMARY KEY,
                stock_code VARCHAR(20) NOT NULL UNIQUE,
                stock_name VARCHAR(50) NOT NULL,
                sector_name VARCHAR(100),
                add_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                note TEXT,
                INDEX idx_stock_code (stock_code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        
        # AI分析报告表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_reports (
                id INT AUTO_INCREMENT PRIMARY KEY,
                scan_id INT,
                report_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                model VARCHAR(50),
                tokens_used INT DEFAULT 0,
                news_data LONGTEXT,
                scan_data_summary LONGTEXT,
                analysis LONGTEXT NOT NULL,
                INDEX idx_report_time (report_time DESC),
                FOREIGN KEY (scan_id) REFERENCES scan_records(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        
        conn.commit()


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
            VALUES (%s, 'scanning', %s)
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), json.dumps(params or {})))
        return cursor.lastrowid


def update_scan_progress(scan_id: int, progress: int, current_sector: str) -> bool:
    """更新扫描进度"""
    progress = max(0, min(100, progress))
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE scan_records 
            SET progress = %s, current_sector = %s
            WHERE id = %s
        ''', (progress, current_sector, scan_id))
        return cursor.rowcount > 0


def update_scan_status(scan_id: int, status: str, error: str = None) -> bool:
    """更新扫描状态"""
    valid_statuses = {'scanning', 'completed', 'error', 'cancelled'}
    if status not in valid_statuses:
        raise ValueError(f"无效的状态值: {status}")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        if error:
            cursor.execute('''
                UPDATE scan_records 
                SET status = %s, error = %s, progress = 100
                WHERE id = %s
            ''', (status, error, scan_id))
        else:
            cursor.execute('''
                UPDATE scan_records 
                SET status = %s, progress = 100, current_sector = '扫描完成'
                WHERE id = %s
            ''', (status, scan_id))
        return cursor.rowcount > 0


def save_hot_sectors(scan_id: int, hot_sectors: List[Dict]) -> bool:
    """保存热点板块信息"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE scan_records 
            SET hot_sectors_json = %s
            WHERE id = %s
        ''', (json.dumps(hot_sectors, ensure_ascii=False), scan_id))
        return cursor.rowcount > 0


def save_sector_result(scan_id: int, sector_name: str, sector_change: float, stocks: List[Dict]) -> bool:
    """保存板块扫描结果"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO scan_results (scan_id, sector_name, sector_change, stocks_json)
            VALUES (%s, %s, %s, %s)
        ''', (scan_id, sector_name, sector_change, json.dumps(stocks, ensure_ascii=False)))
        return True


def get_scan_list(limit: int = 20) -> List[Dict]:
    """获取扫描记录列表"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # MySQL 5.7 不支持 json_array_length，使用子查询
        cursor.execute('''
            SELECT r.id, r.scan_time, r.status, r.progress, r.current_sector, 
                   r.hot_sectors_json, r.error, r.params_json,
                   (SELECT COUNT(*) FROM scan_results WHERE scan_id = r.id) as sector_count
            FROM scan_records r
            ORDER BY r.scan_time DESC
            LIMIT %s
        ''', (limit,))
        
        records = []
        for row in cursor.fetchall():
            record = {
                'id': row['id'],
                'scan_time': row['scan_time'].strftime('%Y-%m-%d %H:%M:%S') if row['scan_time'] else None,
                'status': row['status'],
                'progress': row['progress'],
                'current_sector': row['current_sector'],
                'error': row['error'],
                'sector_count': row['sector_count'] or 0,
                'stock_count': 0,
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
            
            # 计算股票数量
            cursor.execute('''
                SELECT stocks_json FROM scan_results WHERE scan_id = %s
            ''', (row['id'],))
            for sr in cursor.fetchall():
                if sr['stocks_json']:
                    try:
                        stocks = json.loads(sr['stocks_json'])
                        record['stock_count'] += len(stocks)
                    except:
                        pass
                
            records.append(record)
            
        return records


def get_scan_detail(scan_id: int) -> Optional[Dict]:
    """获取单次扫描的详细结果"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, scan_time, status, progress, current_sector, 
                   hot_sectors_json, error, params_json
            FROM scan_records
            WHERE id = %s
        ''', (scan_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
            
        record = {
            'id': row['id'],
            'scan_time': row['scan_time'].strftime('%Y-%m-%d %H:%M:%S') if row['scan_time'] else None,
            'status': row['status'],
            'progress': row['progress'],
            'current_sector': row['current_sector'],
            'error': row['error'],
        }
        
        if row['hot_sectors_json']:
            try:
                record['hot_sectors'] = json.loads(row['hot_sectors_json'])
            except json.JSONDecodeError:
                record['hot_sectors'] = []
        else:
            record['hot_sectors'] = []
        
        cursor.execute('''
            SELECT sector_name, sector_change, stocks_json
            FROM scan_results
            WHERE scan_id = %s
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
                'change': float(result_row['sector_change']) if result_row['sector_change'] else 0,
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
            WHERE id = %s
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
    """删除指定扫描记录"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM scan_results WHERE scan_id = %s', (scan_id,))
        cursor.execute('DELETE FROM scan_records WHERE id = %s', (scan_id,))
        return cursor.rowcount > 0


def delete_all_scans() -> int:
    """删除所有扫描记录"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM scan_results')
        cursor.execute('DELETE FROM scan_records')
        return cursor.rowcount


# ==================== 板块成分股缓存 ====================

def save_sector_stocks_cache(sector_name: str, stocks: List[Dict]) -> bool:
    """保存板块成分股到缓存（当日有效）"""
    if not sector_name or not stocks:
        return False
    
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                REPLACE INTO sector_stocks_cache (sector_name, cache_date, stocks_json)
                VALUES (%s, %s, %s)
            ''', (sector_name, today, json.dumps(stocks, ensure_ascii=False)))
            return True
    except Exception:
        return False


def get_sector_stocks_cache(sector_name: str) -> Optional[List[Dict]]:
    """获取板块成分股缓存（仅当日有效）"""
    if not sector_name:
        return None
    
    today = datetime.now().strftime('%Y-%m-%d')
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT stocks_json FROM sector_stocks_cache
            WHERE sector_name = %s AND cache_date = %s
        ''', (sector_name, today))
        
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row['stocks_json'])
            except:
                return None
        return None


def get_all_sector_stocks_cache(sector_names: List[str]) -> Dict[str, List[Dict]]:
    """批量获取多个板块的成分股缓存"""
    if not sector_names:
        return {}
    
    today = datetime.now().strftime('%Y-%m-%d')
    result = {}
    
    with get_connection() as conn:
        cursor = conn.cursor()
        placeholders = ','.join(['%s'] * len(sector_names))
        cursor.execute(f'''
            SELECT sector_name, stocks_json FROM sector_stocks_cache
            WHERE sector_name IN ({placeholders}) AND cache_date = %s
        ''', (*sector_names, today))
        
        for row in cursor.fetchall():
            try:
                result[row['sector_name']] = json.loads(row['stocks_json'])
            except:
                continue
    
    return result


def clear_sector_stocks_cache() -> int:
    """清空成分股缓存"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM sector_stocks_cache')
        return cursor.rowcount


# ==================== K线缓存相关函数 ====================

def save_kline_cache(stock_code: str, data: Dict) -> bool:
    """保存K线数据到缓存（当日有效）"""
    if not stock_code:
        raise ValueError("stock_code 不能为空")
    if not data:
        raise ValueError("data 不能为空")
    
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                REPLACE INTO kline_cache (stock_code, cache_date, data_json)
                VALUES (%s, %s, %s)
            ''', (stock_code, today, json.dumps(data, ensure_ascii=False)))
            return True
    except Exception:
        return False


def save_kline_cache_batch(kline_data_list: List[tuple]) -> int:
    """批量保存K线数据 [(stock_code, data), ...]"""
    if not kline_data_list:
        return 0
    
    today = datetime.now().strftime('%Y-%m-%d')
    saved = 0
    
    with get_connection() as conn:
        cursor = conn.cursor()
        for stock_code, data in kline_data_list:
            try:
                cursor.execute('''
                    REPLACE INTO kline_cache (stock_code, cache_date, data_json)
                    VALUES (%s, %s, %s)
                ''', (stock_code, today, json.dumps(data, ensure_ascii=False)))
                saved += 1
            except:
                continue
        conn.commit()
    
    return saved


def get_kline_cache(stock_code: str) -> Optional[Dict]:
    """获取K线缓存数据（仅当日有效）"""
    if not stock_code:
        return None
    
    today = datetime.now().strftime('%Y-%m-%d')
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT data_json FROM kline_cache
            WHERE stock_code = %s AND cache_date = %s
        ''', (stock_code, today))
        
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row['data_json'])
            except:
                return None
        return None


def get_kline_cache_batch(stock_codes: List[str]) -> Dict[str, Dict]:
    """批量获取K线缓存"""
    if not stock_codes:
        return {}
    
    today = datetime.now().strftime('%Y-%m-%d')
    result = {}
    
    with get_connection() as conn:
        cursor = conn.cursor()
        placeholders = ','.join(['%s'] * len(stock_codes))
        cursor.execute(f'''
            SELECT stock_code, data_json FROM kline_cache
            WHERE stock_code IN ({placeholders}) AND cache_date = %s
        ''', (*stock_codes, today))
        
        for row in cursor.fetchall():
            try:
                result[row['stock_code']] = json.loads(row['data_json'])
            except:
                continue
    
    return result


def delete_expired_kline_cache() -> int:
    """删除过期的K线缓存（非当日）"""
    today = datetime.now().strftime('%Y-%m-%d')
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM kline_cache WHERE cache_date < %s', (today,))
        return cursor.rowcount


def get_kline_cache_stats() -> Dict:
    """获取K线缓存统计信息"""
    today = datetime.now().strftime('%Y-%m-%d')
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as count FROM kline_cache WHERE cache_date = %s', (today,))
        today_count = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as total FROM kline_cache')
        total_count = cursor.fetchone()['total']
        
        return {
            'today_cache': today_count,
            'total_cache': total_count
        }


# ==================== 自选股相关函数 ====================

def add_to_watchlist(stock_code: str, stock_name: str, sector_name: str = None, note: str = None) -> bool:
    """添加股票到自选列表"""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO watchlist (stock_code, stock_name, sector_name, add_time, note)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    stock_name = VALUES(stock_name),
                    sector_name = VALUES(sector_name),
                    add_time = VALUES(add_time),
                    note = VALUES(note)
            ''', (stock_code, stock_name, sector_name, 
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), note))
            return True
        except Exception:
            return False


def remove_from_watchlist(stock_code: str) -> bool:
    """从自选列表移除股票"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM watchlist WHERE stock_code = %s', (stock_code,))
        return cursor.rowcount > 0


def get_watchlist() -> List[Dict]:
    """获取自选列表"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT stock_code, stock_name, sector_name, add_time, note
            FROM watchlist
            ORDER BY add_time DESC
        ''')
        
        stocks = []
        for row in cursor.fetchall():
            add_time = row['add_time']
            if isinstance(add_time, datetime):
                add_time = add_time.strftime('%Y-%m-%d %H:%M:%S')
            stocks.append({
                'code': row['stock_code'],
                'name': row['stock_name'],
                'sector': row['sector_name'],
                'add_time': add_time,
                'note': row['note']
            })
        return stocks


def is_in_watchlist(stock_code: str) -> bool:
    """检查股票是否在自选列表中"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM watchlist WHERE stock_code = %s', (stock_code,))
        return cursor.fetchone() is not None


def clear_watchlist() -> int:
    """清空自选列表"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM watchlist')
        return cursor.rowcount


# ==================== AI 报告管理 ====================

def save_ai_report(analysis: str, model: str = None, tokens_used: int = 0, 
                   scan_id: int = None, news_data: str = None, scan_data_summary: str = None) -> int:
    """保存 AI 分析报告"""
    local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ai_reports (scan_id, report_time, model, tokens_used, news_data, scan_data_summary, analysis)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (scan_id, local_time, model, tokens_used, news_data, scan_data_summary, analysis))
        return cursor.lastrowid


def get_ai_reports(limit: int = 20) -> List[Dict]:
    """获取 AI 报告列表"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, scan_id, report_time, model, tokens_used, 
                   news_data, scan_data_summary, analysis
            FROM ai_reports
            ORDER BY report_time DESC
            LIMIT %s
        ''', (limit,))
        
        reports = []
        for row in cursor.fetchall():
            report_time = row['report_time']
            if isinstance(report_time, datetime):
                report_time = report_time.strftime('%Y-%m-%d %H:%M:%S')
            reports.append({
                'id': row['id'],
                'scan_id': row['scan_id'],
                'report_time': report_time,
                'model': row['model'],
                'tokens_used': row['tokens_used'],
                'news_data': row['news_data'],
                'scan_data_summary': row['scan_data_summary'],
                'analysis': row['analysis']
            })
        return reports


def get_ai_report(report_id: int) -> Optional[Dict]:
    """获取单个 AI 报告详情"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, scan_id, report_time, model, tokens_used,
                   news_data, scan_data_summary, analysis
            FROM ai_reports
            WHERE id = %s
        ''', (report_id,))
        
        row = cursor.fetchone()
        if row:
            report_time = row['report_time']
            if isinstance(report_time, datetime):
                report_time = report_time.strftime('%Y-%m-%d %H:%M:%S')
            return {
                'id': row['id'],
                'scan_id': row['scan_id'],
                'report_time': report_time,
                'model': row['model'],
                'tokens_used': row['tokens_used'],
                'news_data': row['news_data'],
                'scan_data_summary': row['scan_data_summary'],
                'analysis': row['analysis']
            }
        return None


def delete_ai_report(report_id: int) -> bool:
    """删除 AI 报告"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM ai_reports WHERE id = %s', (report_id,))
        return cursor.rowcount > 0


def delete_all_ai_reports() -> int:
    """删除所有 AI 报告"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM ai_reports')
        return cursor.rowcount


# 初始化数据库
init_db()
