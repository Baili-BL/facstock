#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL 数据库模块 - 扫描结果存储
支持 MySQL 5.7+
"""

import pymysql
import json
import os
from datetime import datetime, timedelta, date
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


def init_db(max_retries: int = 10, retry_delay: int = 3):
    """初始化数据库表（带重试机制，适配 Docker 环境）"""
    import time
    
    # 先创建数据库（如果不存在）
    config_no_db = DB_CONFIG.copy()
    db_name = config_no_db.pop('database')
    
    # 重试连接（Docker 环境下 DNS 可能需要时间）
    conn = None
    last_error = None
    for attempt in range(max_retries):
        try:
            conn = pymysql.connect(**config_no_db)
            break
        except Exception as e:
            last_error = e
            print(f"[DB] 连接数据库失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    
    if conn is None:
        raise Exception(f"无法连接数据库，已重试 {max_retries} 次: {last_error}")
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

        # 股票基本信息表（支持模糊搜索）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stocks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                code VARCHAR(10) NOT NULL UNIQUE,
                name VARCHAR(50) NOT NULL,
                pinyin VARCHAR(100),
                pinyin_abbr VARCHAR(20),
                market_type ENUM('sh', 'sz', 'bj') DEFAULT 'sz',
                sector VARCHAR(100),
                updatetime DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_name (name),
                INDEX idx_pinyin (pinyin),
                INDEX idx_pinyin_abbr (pinyin_abbr),
                INDEX idx_code (code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')

        # Agent 分析历史（按 Agent + 日期唯一，历史锁定，当天可更新）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_analysis_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                agent_id VARCHAR(30) NOT NULL,
                report_date DATE NOT NULL,
                scan_id INT,
                holdings_snapshot_json LONGTEXT NOT NULL COMMENT '分析时的持仓快照JSON',
                analysis_result_json LONGTEXT NOT NULL COMMENT 'AI分析结果JSON（含持仓对比结论）',
                raw_response_text LONGTEXT COMMENT 'AI原始返回文本',
                stance VARCHAR(20),
                confidence INT DEFAULT 0,
                tokens_used INT DEFAULT 0,
                model VARCHAR(50) DEFAULT 'deepseek-chat',
                report_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uk_agent_date (agent_id, report_date),
                INDEX idx_report_date (report_date DESC),
                INDEX idx_report_time (report_time DESC),
                FOREIGN KEY (scan_id) REFERENCES scan_records(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS holdings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                stock_code VARCHAR(10) NOT NULL,
                stock_name VARCHAR(50) NOT NULL,
                sector VARCHAR(100) DEFAULT '',
                position_ratio DECIMAL(5,2) DEFAULT 0,
                avg_cost DECIMAL(10,3) DEFAULT 0,
                current_price DECIMAL(10,3) DEFAULT 0,
                profit_loss_pct DECIMAL(10,2) DEFAULT 0,
                profit_loss_amount DECIMAL(12,2) DEFAULT 0,
                hold_days INT DEFAULT 0,
                position_type VARCHAR(20) DEFAULT 'long',
                remark TEXT,
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_code (stock_code),
                INDEX idx_update_time (update_time DESC)
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


# ==================== 股票搜索相关函数 ====================

def search_stocks(keyword: str, limit: int = 20) -> List[Dict]:
    """
    模糊搜索股票（支持代码、名称、拼音首字母）
    
    Args:
        keyword: 搜索关键词（支持股票代码、名称、拼音、拼音首字母）
        limit: 返回数量限制，默认20
        
    Returns:
        [{code, name, pinyin, pinyin_abbr, market_type, sector}, ...]
    """
    if not keyword or len(keyword.strip()) == 0:
        return []
    
    keyword = keyword.strip()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 优先精确匹配代码，再模糊匹配
        like_pattern = f'%{keyword}%'
        cursor.execute('''
            SELECT code, name, pinyin, pinyin_abbr, market_type, sector
            FROM stocks
            WHERE code = %s
               OR name LIKE %s
               OR pinyin LIKE %s
               OR pinyin_abbr LIKE %s
            ORDER BY
                CASE WHEN code = %s THEN 0
                     WHEN code LIKE %s THEN 1
                     WHEN pinyin_abbr = %s THEN 2
                     WHEN pinyin_abbr LIKE %s THEN 3
                     WHEN name LIKE %s THEN 4
                     ELSE 5 END,
                code ASC
            LIMIT %s
        ''', (keyword, like_pattern, like_pattern, like_pattern,
              keyword, f'{keyword}%', keyword.lower(), f'{keyword.lower()}%',
              f'{keyword}%', limit))
        
        return list(cursor.fetchall())


def get_all_stocks_count() -> int:
    """获取股票总数"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as cnt FROM stocks')
        return cursor.fetchone()['cnt']


def get_all_stocks_for_sync() -> List[Dict]:
    """获取所有股票数据（用于同步）"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT code, name, pinyin, pinyin_abbr, market_type, sector, updatetime
            FROM stocks ORDER BY code
        ''')
        return list(cursor.fetchall())


def upsert_stock(code: str, name: str, pinyin: str = None,
                 pinyin_abbr: str = None, market_type: str = None,
                 sector: str = None) -> bool:
    """新增或更新股票信息"""
    import pypinyin
    try:
        if pinyin is None:
            pinyin = ''.join(
                i[0] for i in pypinyin.pinyin(name, style=pypinyin.Style.NORMAL)
            )
        if pinyin_abbr is None:
            pinyin_abbr = ''.join(
                i[0][0] if i[0] else '' 
                for i in pypinyin.pinyin(name, style=pypinyin.Style.TONE3)
            ).lower()
    except Exception:
        pinyin = ''
        pinyin_abbr = ''
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO stocks (code, name, pinyin, pinyin_abbr, market_type, sector, updatetime)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                pinyin = VALUES(pinyin),
                pinyin_abbr = VALUES(pinyin_abbr),
                market_type = COALESCE(VALUES(market_type), market_type),
                sector = VALUES(sector),
                updatetime = VALUES(updatetime)
        ''', (code, name, pinyin, pinyin_abbr, market_type, sector,
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        return True


def upsert_stocks_batch(stocks_data: List[Dict]) -> int:
    """
    批量新增或更新股票信息
    
    Args:
        stocks_data: [{code, name, pinyin, pinyin_abbr, market_type, sector}, ...]
        
    Returns:
        成功处理的条数
    """
    import pypinyin
    saved = 0
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def ensure_pinyin(item):
        name = item.get('name', '')
        if not item.get('pinyin'):
            item['pinyin'] = ''.join(
                i[0] for i in pypinyin.pinyin(name, style=pypinyin.Style.NORMAL)
            )
        if not item.get('pinyin_abbr'):
            item['pinyin_abbr'] = ''.join(
                i[0][0] if i[0] else ''
                for i in pypinyin.pinyin(name, style=pypinyin.Style.TONE3)
            ).lower()
        return item
    
    with get_connection() as conn:
        cursor = conn.cursor()
        for item in stocks_data:
            try:
                item = ensure_pinyin(item)
                cursor.execute('''
                    INSERT INTO stocks (code, name, pinyin, pinyin_abbr, market_type, sector, updatetime)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        pinyin = VALUES(pinyin),
                        pinyin_abbr = VALUES(pinyin_abbr),
                        market_type = COALESCE(VALUES(market_type), market_type),
                        sector = VALUES(sector),
                        updatetime = VALUES(updatetime)
                ''', (item['code'], item['name'], item.get('pinyin', ''),
                      item.get('pinyin_abbr', ''), item.get('market_type'),
                      item.get('sector'), now_str))
                saved += 1
            except Exception:
                continue
        conn.commit()
        return saved


def get_stock_sectors_by_codes(codes: List[str]) -> Dict[str, str]:
    """
    按股票代码批量查询已入库的行业（所属板块）名称。
    仅返回 sector 非空的记录；code 为 stocks 表中的 6 位代码。
    """
    if not codes:
        return {}
    seen: List[str] = []
    for c in codes:
        c = str(c).strip()
        if c and c not in seen:
            seen.append(c)
    if not seen:
        return {}
    with get_connection() as conn:
        cursor = conn.cursor()
        ph = ','.join(['%s'] * len(seen))
        cursor.execute(
            f'''
            SELECT code, sector FROM stocks
            WHERE code IN ({ph})
              AND sector IS NOT NULL AND TRIM(sector) != ''
            ''',
            seen,
        )
        return {row['code']: row['sector'] for row in cursor.fetchall()}


# ==================== 新闻缓存 ====================

def init_news_cache_table():
    """初始化新闻缓存表"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news_cache (
                id INT AUTO_INCREMENT PRIMARY KEY,
                news_date DATE NOT NULL,
                source VARCHAR(50) NOT NULL,
                title VARCHAR(500) NOT NULL,
                content TEXT,
                time_str VARCHAR(50) DEFAULT '',
                url VARCHAR(1000) DEFAULT '',
                news_hash VARCHAR(64) NOT NULL,
                fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uk_hash_date (news_hash, news_date),
                INDEX idx_news_date (news_date),
                INDEX idx_source (source)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')


def _compute_news_hash(title: str, content: str = "") -> str:
    """计算新闻摘要hash用于去重"""
    import hashlib
    text = f"{title[:80]}|{content[:200]}".encode("utf-8")
    return hashlib.sha256(text).hexdigest()[:32]


def _parse_news_date(time_str: str) -> Optional[date]:
    """
    从新闻的 time 字段解析出实际日期。
    支持 Unix 时间戳（字符串）和 'YYYY-MM-DD HH:MM:SS' 两种格式。
    """
    t = str(time_str).strip()
    if not t:
        return None
    try:
        if t.isdigit():
            # Unix 时间戳（秒）
            return datetime.fromtimestamp(int(t)).date()
        else:
            # 'YYYY-MM-DD HH:MM:SS' 格式
            return datetime.strptime(t[:19], '%Y-%m-%d %H:%M:%S').date()
    except Exception:
        return None


def save_news_items(news_list: List[Dict]) -> int:
    """
    批量保存新闻到缓存（按新闻本身的 time 字段解析日期，实现去重）
    返回实际新增条数
    """
    saved = 0
    # 按日期分组，同一天合并一次连接
    by_date: Dict[date, List[Dict]] = {}
    for item in news_list:
        news_date = _parse_news_date(item.get("time") or "")
        if news_date is None:
            news_date = date.today()
        by_date.setdefault(news_date, []).append(item)

    for news_date, items in by_date.items():
        with get_connection() as conn:
            cursor = conn.cursor()
            for item in items:
                title = (item.get("title") or "")[:500]
                content = (item.get("content") or "")[:2000]
                source = (item.get("source") or "")[:50]
                time_str = (item.get("time") or "")[:50]
                url = (item.get("url") or "")[:1000]
                news_hash = _compute_news_hash(title, content)

                try:
                    cursor.execute('''
                        INSERT IGNORE INTO news_cache
                        (news_date, source, title, content, time_str, url, news_hash)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ''', (news_date, source, title, content, time_str, url, news_hash))
                    if cursor.rowcount > 0:
                        saved += 1
                except Exception:
                    continue
    return saved


def get_cached_news(days: int = 1) -> List[Dict]:
    """
    获取最近N天的缓存新闻（按 time_str 排序）
    days=1 表示查今天、days=2 表示今天+昨天，以此类推
    """
    if days <= 0:
        days = 1
    with get_connection() as conn:
        cursor = conn.cursor()
        # news_date 存的是新闻本身的日期（从 time 解析），不是入库日期
        cursor.execute('''
            SELECT source, title, content, time_str, url, news_date
            FROM news_cache
            WHERE news_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            ORDER BY
                CASE WHEN time_str REGEXP '^[0-9]+$' THEN CAST(time_str AS UNSIGNED) ELSE 0 END DESC,
                news_date DESC
        ''', (days - 1,))
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append({
                "title": row["title"],
                "content": row["content"] or "",
                "time": row["time_str"] or "",
                "source": row["source"],
                "url": row["url"] or "",
            })
        return result


def delete_expired_news_cache(keep_days: int = 30) -> int:
    """删除过期新闻缓存（默认保留30天）"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'DELETE FROM news_cache WHERE news_date < DATE_SUB(CURDATE(), INTERVAL %s DAY)',
            (keep_days,)
        )
        return cursor.rowcount


# ─────────────────────────────────────────────────────────────────────────────
# 持仓数据管理
# ─────────────────────────────────────────────────────────────────────────────

def upsert_holding(code: str, name: str, sector: str = '', avg_cost: float = 0,
                   current_price: float = 0, position_ratio: float = 0,
                   profit_loss_pct: float = 0, profit_loss_amount: float = 0,
                   hold_days: int = 0, position_type: str = 'long',
                   remark: str = '') -> bool:
    """新增或更新一条持仓记录（code 唯一）"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO holdings
                (stock_code, stock_name, sector, avg_cost, current_price,
                 position_ratio, profit_loss_pct, profit_loss_amount,
                 hold_days, position_type, remark)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                stock_name = VALUES(stock_name),
                sector = VALUES(sector),
                avg_cost = VALUES(avg_cost),
                current_price = VALUES(current_price),
                position_ratio = VALUES(position_ratio),
                profit_loss_pct = VALUES(profit_loss_pct),
                profit_loss_amount = VALUES(profit_loss_amount),
                hold_days = VALUES(hold_days),
                position_type = VALUES(position_type),
                remark = VALUES(remark)
        ''', (code, name, sector, avg_cost, current_price,
              position_ratio, profit_loss_pct, profit_loss_amount,
              hold_days, position_type, remark))
        return cursor.rowcount > 0


def get_all_holdings() -> List[Dict]:
    """获取所有持仓，按更新时间倒序"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT stock_code, stock_name, sector,
                   position_ratio, avg_cost, current_price,
                   profit_loss_pct, profit_loss_amount,
                   hold_days, position_type, remark,
                   update_time
            FROM holdings
            ORDER BY update_time DESC
        ''')
        rows = cursor.fetchall()
        # DictCursor 已返回 dict，禁止 dict(zip(cols, row))（会把列名当值）
        return [dict(r) if isinstance(r, dict) else dict(zip([d[0] for d in cursor.description], r)) for r in rows]


def delete_holding(code: str) -> bool:
    """删除一条持仓"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM holdings WHERE stock_code = %s', (code,))
        return cursor.rowcount > 0


def upsert_holdings_batch(holdings_list: List[Dict]) -> int:
    """批量新增或更新持仓（原子操作）"""
    count = 0
    for h in holdings_list:
        ok = upsert_holding(
            code=h.get('code', ''),
            name=h.get('name', ''),
            sector=h.get('sector', ''),
            avg_cost=float(h.get('avgCost', 0)),
            current_price=float(h.get('currentPrice', 0)),
            position_ratio=float(h.get('positionRatio', 0)),
            profit_loss_pct=float(h.get('profitLossPct', 0)),
            profit_loss_amount=float(h.get('profitLossAmount', 0)),
            hold_days=int(h.get('holdDays', 0)),
            position_type=h.get('positionType', 'long'),
            remark=h.get('remark', ''),
        )
        if ok:
            count += 1
    return count


# ─────────────────────────────────────────────────────────────────────────────
# Agent 分析历史（按 Agent + 日期唯一，历史锁定，当天可覆盖）
# ─────────────────────────────────────────────────────────────────────────────

def _snapshot_float(v, default: float = 0.0) -> float:
    if v is None or v == '':
        return default
    if isinstance(v, (int, float)):
        return float(v)
    try:
        s = str(v).strip().rstrip('%').replace('+', '').replace(',', '')
        return float(s)
    except (TypeError, ValueError):
        return default


def snapshot_rows_from_db_holdings(rows: List[Dict]) -> List[Dict]:
    """将 holdings 表行规范为历史快照字段（与前端 AgentHoldings 一致）"""
    out: List[Dict] = []
    for h in rows or []:
        code = h.get('stock_code') or h.get('code') or ''
        if not code:
            continue
        out.append({
            'stock_code': str(code),
            'stock_name': str(h.get('stock_name') or h.get('name') or ''),
            'sector': str(h.get('sector') or ''),
            'current_price': _snapshot_float(h.get('current_price') or h.get('price')),
            'profit_loss_pct': _snapshot_float(h.get('profit_loss_pct') or h.get('changePct')),
            'source': 'holdings',
        })
    return out


def snapshot_rows_from_recommended_stocks(stocks: List[Dict]) -> List[Dict]:
    """将 AI recommendedStocks 规范为历史快照（无真实持仓时的展示用）"""
    out: List[Dict] = []
    for s in stocks or []:
        code = s.get('code') or ''
        if not code:
            continue
        out.append({
            'stock_code': str(code),
            'stock_name': str(s.get('name') or ''),
            'sector': str(s.get('sector') or ''),
            'current_price': _snapshot_float(s.get('price')),
            'profit_loss_pct': _snapshot_float(s.get('changePct')),
            'source': 'recommended',
        })
    return out


def build_analysis_holdings_snapshot(
    db_holdings: List[Dict],
    analysis_result: Any = None,
) -> List[Dict]:
    """
    写入 agent_analysis_history 的快照：优先真实持仓；若为空则用分析结果中的推荐股，
    避免持仓页在「未维护 holdings 表」时始终 0 条。
    analysis_result 可为扁平 dict（含 recommendedStocks），或 app 保存的 { structured, raw_text }。
    """
    snap = snapshot_rows_from_db_holdings(db_holdings)
    if snap:
        return snap
    rec: List[Dict] = []
    if isinstance(analysis_result, dict):
        if isinstance(analysis_result.get('recommendedStocks'), list):
            rec = analysis_result['recommendedStocks']
        st = analysis_result.get('structured')
        if isinstance(st, dict) and isinstance(st.get('recommendedStocks'), list):
            rec = st['recommendedStocks']
    return snapshot_rows_from_recommended_stocks(rec)


def save_agent_analysis_history(
    agent_id: str,
    report_date: str,
    holdings_snapshot: List[Dict],
    analysis_result: Dict,
    raw_response: str = '',
    stance: str = '',
    confidence: int = 0,
    tokens_used: int = 0,
    model: str = 'deepseek-chat',
    scan_id: int = None,
) -> int:
    """
    保存 Agent 分析历史记录。

    - agent_id + report_date 联合唯一：历史日期锁定，当天可覆盖更新
    - holdings_snapshot：分析时持仓数据的完整快照（JSON）
    - analysis_result：AI 返回的结构化分析结果（JSON）
    """
    import json as _json
    local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO agent_analysis_history
                (agent_id, report_date, scan_id, holdings_snapshot_json,
                 analysis_result_json, raw_response_text, stance,
                 confidence, tokens_used, model, report_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                scan_id = VALUES(scan_id),
                holdings_snapshot_json = VALUES(holdings_snapshot_json),
                analysis_result_json = VALUES(analysis_result_json),
                raw_response_text = VALUES(raw_response_text),
                stance = VALUES(stance),
                confidence = VALUES(confidence),
                tokens_used = VALUES(tokens_used),
                model = VALUES(model),
                report_time = VALUES(report_time)
        ''', (
            agent_id,
            report_date,
            scan_id,
            _json.dumps(holdings_snapshot, ensure_ascii=False),
            _json.dumps(analysis_result, ensure_ascii=False),
            raw_response,
            stance,
            confidence,
            tokens_used,
            model,
            local_time,
        ))
        return cursor.lastrowid


def get_agent_analysis_history(
    agent_id: str,
    start_date: str = None,
    end_date: str = None,
    limit: int = 30,
) -> List[Dict]:
    """
    查询 Agent 分析历史，支持按日期范围过滤。
    默认返回最近 limit 条。
    """
    import json as _json

    with get_connection() as conn:
        cursor = conn.cursor()
        sql = '''
            SELECT id, agent_id, report_date, scan_id,
                   holdings_snapshot_json, analysis_result_json,
                   raw_response_text, stance, confidence,
                   tokens_used, model, report_time
            FROM agent_analysis_history
            WHERE agent_id = %s
        '''
        args = [agent_id]

        if start_date:
            sql += ' AND report_date >= %s'
            args.append(start_date)
        if end_date:
            sql += ' AND report_date <= %s'
            args.append(end_date)

        sql += ' ORDER BY report_date DESC, report_time DESC LIMIT %s'
        args.append(limit)

        cursor.execute(sql, tuple(args))
        result = []
        for row in cursor.fetchall():
            # cursorclass=DictCursor 已返回 dict，直接使用
            d = dict(row) if not isinstance(row, dict) else row
            d['holdings_snapshot'] = _json.loads((d.pop('holdings_snapshot_json') or '[]')) if d.get('holdings_snapshot_json') else []
            d['analysis_result']   = _json.loads((d.pop('analysis_result_json')   or '{}')) if d.get('analysis_result_json')  else {}
            rd = d.get('report_date')
            if hasattr(rd, 'isoformat'):
                d['report_date'] = rd.isoformat()
            rt = d.get('report_time')
            if isinstance(rt, datetime):
                d['report_time'] = rt.strftime('%Y-%m-%d %H:%M:%S')
            result.append(d)
        return result


def get_latest_agent_analysis(agent_id: str) -> Optional[Dict]:
    """获取某 Agent 最新一次分析（含持仓快照和分析结果）"""
    import json as _json

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, agent_id, report_date, scan_id,
                   holdings_snapshot_json, analysis_result_json,
                   raw_response_text, stance, confidence,
                   tokens_used, model, report_time
            FROM agent_analysis_history
            WHERE agent_id = %s
            ORDER BY report_date DESC, report_time DESC
            LIMIT 1
        ''', (agent_id,))
        row = cursor.fetchone()
        if not row:
            return None
        # cursorclass=DictCursor 已返回 dict，直接使用
        d = dict(row) if not isinstance(row, dict) else row
        d['holdings_snapshot'] = _json.loads(d.pop('holdings_snapshot_json') or '[]') if d.get('holdings_snapshot_json') else []
        d['analysis_result']   = _json.loads(d.pop('analysis_result_json') or '{}')   if d.get('analysis_result_json')  else {}
        rd = d.get('report_date')
        if hasattr(rd, 'isoformat'):
            d['report_date'] = rd.isoformat()
        rt = d.get('report_time')
        if isinstance(rt, datetime):
            d['report_time'] = rt.strftime('%Y-%m-%d %H:%M:%S')
        return d


# 初始化新闻缓存表
try:
    init_news_cache_table()
except Exception as e:
    print(f"[WARN] 新闻缓存表初始化失败: {e}")

# 启动时清理过期缓存（保留30天）
try:
    deleted = delete_expired_news_cache(keep_days=30)
    if deleted > 0:
        print(f"🧹 清理过期新闻缓存: 删除了{deleted}条")
except Exception as e:
    print(f"[WARN] 清理过期新闻缓存失败: {e}")

# 初始化数据库
init_db()
