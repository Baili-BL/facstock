#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL 数据库模块 - 扫描结果存储
支持 MySQL 5.7+
"""

import pymysql
import json
import math
import os
import pandas as pd
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from contextlib import contextmanager


def _safe_json_dumps(obj) -> str:
    """JSON 序列化，兼容 NaN/Infinity 及 pandas 特有类型。"""
    def _fallback(v):
        if isinstance(v, float):
            if math.isnan(v) or math.isinf(v):
                return None
            return v
        # pandas Timestamp / Timedelta → ISO 字符串
        if hasattr(v, 'isoformat'):
            return v.isoformat()
        # np.floating / np.integer → Python 原生
        if hasattr(v, 'item'):
            return v.item()
        return None
    return json.dumps(obj, ensure_ascii=False, default=_fallback)

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

        # 原始K线缓存表（仅OHLCV，供TradingView图表使用，当日有效）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kline_raw_cache (
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

        # 迁移：agent_analysis_history 表缺失列（历史遗留）
        _migrate_agent_analysis_history_cols(cursor)

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

        # 迁移：scan_records 缓存 DeepSeek 扫描小结（避免每次进入页面重复调用模型）
        cursor.execute('''
            SELECT COUNT(*) AS c FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'scan_records'
              AND COLUMN_NAME = 'ai_summary_json'
        ''')
        if cursor.fetchone()['c'] == 0:
            cursor.execute(
                'ALTER TABLE scan_records ADD COLUMN ai_summary_json LONGTEXT NULL, '
                'ADD COLUMN ai_summary_time DATETIME NULL'
            )

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bollinger_alert_rules (
                id INT AUTO_INCREMENT PRIMARY KEY,
                rule_name VARCHAR(200) NOT NULL DEFAULT '布林带收缩突破',
                scan_id INT NULL COMMENT '可选：关联历史扫描记录',
                webhook_url VARCHAR(768) NOT NULL DEFAULT '',
                metric VARCHAR(50) NOT NULL DEFAULT 'bb_width_pct',
                cond_op VARCHAR(30) NOT NULL DEFAULT 'gt',
                threshold VARCHAR(64) NOT NULL DEFAULT '',
                frequency VARCHAR(20) NOT NULL DEFAULT 'once',
                enabled TINYINT(1) NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_scan_id (scan_id),
                INDEX idx_enabled (enabled),
                FOREIGN KEY (scan_id) REFERENCES scan_records(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')

        # 任务管理表（类 Cursor/Claude Code 任务系统）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                subject VARCHAR(255) NOT NULL COMMENT '任务标题',
                description TEXT COMMENT '任务详细描述',
                status ENUM('pending', 'in_progress', 'completed', 'deleted') NOT NULL DEFAULT 'pending',
                owner VARCHAR(100) COMMENT '任务负责人',
                active_form VARCHAR(255) COMMENT '进行中显示的动画文字',
                priority INT DEFAULT 0 COMMENT '优先级，数字越大优先级越高',
                metadata JSON COMMENT '扩展数据（JSON）',
                blocked_by TEXT COMMENT '依赖任务ID，逗号分隔',
                blocks TEXT COMMENT '被阻塞的任务ID，逗号分隔',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                started_at DATETIME COMMENT '开始时间',
                completed_at DATETIME COMMENT '完成时间',
                INDEX idx_status (status),
                INDEX idx_owner (owner),
                INDEX idx_priority (priority),
                INDEX idx_created_at (created_at DESC)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')

        # 飞书推送配置表（只保留一条主配置）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS push_config (
                id INT AUTO_INCREMENT PRIMARY KEY,
                webhook_url VARCHAR(768) NOT NULL DEFAULT '',
                enabled TINYINT(1) NOT NULL DEFAULT 1,
                agent_ids_json TEXT NOT NULL COMMENT 'JSON数组 ["beijing","qiao",...]',
                top_stocks_per_agent INT NOT NULL DEFAULT 3,
                consensus_top_n INT NOT NULL DEFAULT 5,
                analysis_max_workers INT NOT NULL DEFAULT 2,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')

        # 飞书推送时段表（4个固定时段，可启用/禁用）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS push_slots (
                id INT AUTO_INCREMENT PRIMARY KEY,
                slot_key VARCHAR(10) NOT NULL UNIQUE COMMENT '0900/1230/1430/2100',
                time_str VARCHAR(10) NOT NULL COMMENT '09:00',
                label VARCHAR(100) NOT NULL COMMENT '盘前策略会',
                template VARCHAR(20) NOT NULL DEFAULT 'blue' COMMENT 'blue/orange/red/indigo',
                enabled TINYINT(1) NOT NULL DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_enabled (enabled)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')

        # 飞书推送历史表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS push_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                generated_at DATETIME NOT NULL COMMENT '生成时间',
                slot_key VARCHAR(10) DEFAULT '' COMMENT '时段key',
                slot_label VARCHAR(100) DEFAULT '' COMMENT '时段标签',
                trigger_type VARCHAR(20) NOT NULL DEFAULT 'scheduled' COMMENT 'scheduled/manual',
                sent TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否发送成功',
                dry_run TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否仅预览',
                agent_count INT NOT NULL DEFAULT 0,
                success_count INT NOT NULL DEFAULT 0,
                failed_count INT NOT NULL DEFAULT 0,
                consensus_count INT NOT NULL DEFAULT 0,
                top_consensus_json TEXT COMMENT 'JSON数组，顶部共识股',
                digest_json LONGTEXT COMMENT '完整digest JSON',
                error_text TEXT COMMENT '错误信息',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_generated_at (generated_at DESC),
                INDEX idx_slot_key (slot_key),
                INDEX idx_sent (sent)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')

        # 初始化默认推送时段
        _init_default_push_slots(cursor)

        # 飞书推送配置变更日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS push_config_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                change_type VARCHAR(50) NOT NULL COMMENT 'webhook_update|agent_add|agent_remove|slot_update|param_update|enable_toggle',
                success TINYINT(1) NOT NULL DEFAULT 1,
                details_json TEXT COMMENT '变更详情JSON',
                summary VARCHAR(200) NOT NULL COMMENT '摘要描述',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_changed_at (changed_at DESC),
                INDEX idx_change_type (change_type)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')

        conn.commit()


def _init_default_push_slots(cursor):
    """初始化默认推送时段（如不存在）"""
    defaults = [
        {'key': '0900', 'time': '09:00', 'label': '盘前策略会', 'template': 'blue'},
        {'key': '1230', 'time': '12:30', 'label': '午间复盘',   'template': 'orange'},
        {'key': '1430', 'time': '14:30', 'label': '午后决策',   'template': 'red'},
        {'key': '2100', 'time': '21:00', 'label': '晚间复盘',   'template': 'indigo'},
    ]
    for d in defaults:
        cursor.execute('''
            INSERT IGNORE INTO push_slots (slot_key, time_str, label, template, enabled)
            VALUES (%s, %s, %s, %s, 1)
        ''', (d['key'], d['time'], d['label'], d['template']))


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
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), _safe_json_dumps(params or {})))
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
        ''', (_safe_json_dumps(hot_sectors), scan_id))
        return cursor.rowcount > 0


def save_sector_result(scan_id: int, sector_name: str, sector_change: float, stocks: List[Dict]) -> bool:
    """保存板块扫描结果"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO scan_results (scan_id, sector_name, sector_change, stocks_json)
            VALUES (%s, %s, %s, %s)
        ''', (scan_id, sector_name, sector_change, _safe_json_dumps(stocks)))
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

        if row['params_json']:
            try:
                record['params'] = json.loads(row['params_json'])
            except json.JSONDecodeError:
                record['params'] = {}
        else:
            record['params'] = {}
        
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


def get_scan_ai_summary(scan_id: int) -> Optional[Dict[str, Any]]:
    """读取已保存的 DeepSeek 扫描小结 JSON；附带 stored_at（生成/保存时间）。"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT ai_summary_json, ai_summary_time FROM scan_records WHERE id = %s',
            (scan_id,),
        )
        row = cursor.fetchone()
        if not row or not row.get('ai_summary_json'):
            return None
        try:
            data = json.loads(row['ai_summary_json'])
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(data, dict):
            return None
        if row.get('ai_summary_time'):
            data['stored_at'] = row['ai_summary_time'].strftime('%Y-%m-%d %H:%M:%S')
        return data


def save_scan_ai_summary(scan_id: int, payload: Dict[str, Any]) -> bool:
    """写入 DeepSeek 扫描小结（不含 stored_at 字段）。"""
    to_save = {k: v for k, v in payload.items() if k != 'stored_at'}
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE scan_records
            SET ai_summary_json = %s, ai_summary_time = NOW()
            WHERE id = %s
            ''',
            (_safe_json_dumps(to_save), scan_id),
        )
        return cursor.rowcount > 0


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


# ==================== 布林带飞书告警规则 ====================

def _alert_rule_row(row: Dict) -> Dict:
    if not row:
        return row
    return {
        'id': row['id'],
        'rule_name': row['rule_name'],
        'scan_id': row['scan_id'],
        'webhook_url': row['webhook_url'] or '',
        'metric': row['metric'],
        'cond_op': row['cond_op'],
        'threshold': row['threshold'] or '',
        'frequency': row['frequency'],
        'enabled': bool(row['enabled']),
        'created_at': row['created_at'].strftime('%Y-%m-%d %H:%M:%S') if row.get('created_at') else None,
        'updated_at': row['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if row.get('updated_at') else None,
    }


def list_bollinger_alert_rules(limit: int = 100) -> List[Dict]:
    """列出布林带告警规则（按更新时间倒序）"""
    limit = max(1, min(500, int(limit)))
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f'''
            SELECT r.id, r.rule_name, r.scan_id, r.webhook_url, r.metric, r.cond_op,
                   r.threshold, r.frequency, r.enabled, r.created_at, r.updated_at,
                   s.scan_time AS linked_scan_time
            FROM bollinger_alert_rules r
            LEFT JOIN scan_records s ON s.id = r.scan_id
            ORDER BY r.updated_at DESC
            LIMIT {limit}
            '''
        )
        out = []
        for row in cursor.fetchall():
            d = _alert_rule_row(row)
            lt = row.get('linked_scan_time')
            d['linked_scan_time'] = lt.strftime('%Y-%m-%d %H:%M:%S') if lt else None
            out.append(d)
        return out


def get_bollinger_alert_rule(rule_id: int) -> Optional[Dict]:
    """获取单条告警规则"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT r.id, r.rule_name, r.scan_id, r.webhook_url, r.metric, r.cond_op,
                   r.threshold, r.frequency, r.enabled, r.created_at, r.updated_at,
                   s.scan_time AS linked_scan_time
            FROM bollinger_alert_rules r
            LEFT JOIN scan_records s ON s.id = r.scan_id
            WHERE r.id = %s
            ''',
            (rule_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        d = _alert_rule_row(row)
        lt = row.get('linked_scan_time')
        d['linked_scan_time'] = lt.strftime('%Y-%m-%d %H:%M:%S') if lt else None
        return d


def create_bollinger_alert_rule(payload: Dict[str, Any]) -> int:
    """创建告警规则，返回新 id"""
    name = (payload.get('rule_name') or '布林带收缩突破').strip()[:200]
    scan_id = payload.get('scan_id')
    if scan_id is not None:
        try:
            scan_id = int(scan_id)
        except (TypeError, ValueError):
            scan_id = None
    webhook = (payload.get('webhook_url') or '').strip()[:768]
    metric = (payload.get('metric') or 'bb_width_pct').strip()[:50]
    cond_op = (payload.get('cond_op') or 'gt').strip()[:30]
    threshold = (payload.get('threshold') or '').strip()[:64]
    frequency = (payload.get('frequency') or 'once').strip()[:20]
    if frequency not in ('once', 'daily', 'weekly'):
        frequency = 'once'
    enabled = 1 if payload.get('enabled', True) else 0

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO bollinger_alert_rules
            (rule_name, scan_id, webhook_url, metric, cond_op, threshold, frequency, enabled)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''',
            (name, scan_id, webhook, metric, cond_op, threshold, frequency, enabled),
        )
        return cursor.lastrowid


def update_bollinger_alert_rule(rule_id: int, payload: Dict[str, Any]) -> bool:
    """更新告警规则"""
    cur = get_bollinger_alert_rule(rule_id)
    if not cur:
        return False

    name = payload.get('rule_name', cur['rule_name'])
    if name is not None:
        name = str(name).strip()[:200] or cur['rule_name']

    scan_id = payload.get('scan_id', cur['scan_id'])
    if scan_id is not None and scan_id != '':
        try:
            scan_id = int(scan_id)
        except (TypeError, ValueError):
            scan_id = cur['scan_id']
    else:
        scan_id = None

    webhook = payload.get('webhook_url', cur['webhook_url'])
    if webhook is not None:
        webhook = str(webhook).strip()[:768]
    else:
        webhook = cur['webhook_url']

    metric = (payload.get('metric') or cur['metric']).strip()[:50]
    cond_op = (payload.get('cond_op') or cur['cond_op']).strip()[:30]
    threshold = payload.get('threshold', cur['threshold'])
    if threshold is not None:
        threshold = str(threshold).strip()[:64]
    else:
        threshold = ''

    frequency = (payload.get('frequency') or cur['frequency']).strip()[:20]
    if frequency not in ('once', 'daily', 'weekly'):
        frequency = cur['frequency']

    if 'enabled' in payload:
        enabled = 1 if payload.get('enabled') else 0
    else:
        enabled = 1 if cur['enabled'] else 0

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            UPDATE bollinger_alert_rules SET
                rule_name=%s, scan_id=%s, webhook_url=%s, metric=%s, cond_op=%s,
                threshold=%s, frequency=%s, enabled=%s
            WHERE id=%s
            ''',
            (name, scan_id, webhook, metric, cond_op, threshold, frequency, enabled, rule_id),
        )
        return cursor.rowcount > 0


def delete_bollinger_alert_rule(rule_id: int) -> bool:
    """删除告警规则"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM bollinger_alert_rules WHERE id = %s', (rule_id,))
        return cursor.rowcount > 0


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
            ''', (sector_name, today, _safe_json_dumps(stocks)))
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


def clear_all_cache() -> Dict:
    """清空所有缓存数据，返回清空的数量"""
    results = {}
    with get_connection() as conn:
        cursor = conn.cursor()
        # 清空成分股缓存
        cursor.execute('DELETE FROM sector_stocks_cache')
        results['sector_stocks'] = cursor.rowcount
        # 清空K线缓存
        cursor.execute('DELETE FROM kline_cache')
        results['kline'] = cursor.rowcount
        # 清空K线原始缓存
        cursor.execute('DELETE FROM kline_raw_cache')
        results['kline_raw'] = cursor.rowcount
        # 清空行业板块缓存（如果有的话）
        try:
            cursor.execute('DELETE FROM industry_board_cache')
            results['industry_board'] = cursor.rowcount
        except:
            results['industry_board'] = 0
    return results


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
            ''', (stock_code, today, _safe_json_dumps(data)))
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
                ''', (stock_code, today, _safe_json_dumps(data)))
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


def _cell_value(v):
    """将 DataFrame cell 值转成 JSON 安全的 Python 原生类型。"""
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if hasattr(v, 'item'):
        return v.item()
    if hasattr(v, 'isoformat'):
        return v.isoformat()[:10]
    try:
        return float(v)
    except (TypeError, ValueError):
        return str(v)


def save_kline_raw_cache(stock_code: str, df) -> bool:
    """
    保存原始K线DataFrame到缓存（当日有效，仅OHLCV）。
    df: pandas.DataFrame 或 [{date,open,high,low,close,volume}, ...]
    """
    if not stock_code:
        return False

    cols = ['date', 'open', 'high', 'low', 'close', 'volume']

    if isinstance(df, pd.DataFrame):
        if df.empty:
            return False
        available = [c for c in cols if c in df.columns]
        # 必须包含 volume，否则图表没有成交量数据
        if len(available) < 6 or 'volume' not in available:
            return False
        out = []
        for _, row in df.iterrows():
            out.append({c: _cell_value(row[c]) for c in available})
    else:
        if not df:
            return False
        out = [{c: _cell_value(item.get(c)) for c in cols} for item in df]

    today = datetime.now().strftime('%Y-%m-%d')
    payload = {'bars': out, 'cols': cols[:len(out[0])] if out else cols}

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                REPLACE INTO kline_raw_cache (stock_code, cache_date, data_json)
                VALUES (%s, %s, %s)
            ''', (stock_code, today, _safe_json_dumps(payload)))
        return True
    except Exception:
        return False


def get_kline_raw_cache(stock_code: str) -> Optional[Dict]:
    """获取原始K线缓存（当日有效）。返回 {'bars': [...], 'cols': [...]}。"""
    if not stock_code:
        return None

    today = datetime.now().strftime('%Y-%m-%d')
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT data_json FROM kline_raw_cache
            WHERE stock_code = %s AND cache_date = %s
        ''', (stock_code, today))

        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row['data_json'])
            except Exception:
                return None
        return None


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
                remark = IF(holdings.remark IS NULL OR holdings.remark = '' OR holdings.remark NOT LIKE 'AI推荐(%%)',
                             VALUES(remark), holdings.remark)
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


def get_holdings_by_agent(agent_id: str) -> List[Dict]:
    """获取指定 agent 的持仓（通过 remark 字段过滤）"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT stock_code, stock_name, sector,
                   position_ratio, avg_cost, current_price,
                   profit_loss_pct, profit_loss_amount,
                   hold_days, position_type, remark,
                   update_time
            FROM holdings
            WHERE remark LIKE %s
            ORDER BY update_time DESC
        ''', (f'%({agent_id})%',))
        rows = cursor.fetchall()
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

def _migrate_agent_analysis_history_cols(cursor):
    """迁移 agent_analysis_history 表缺失列（历史遗留问题）"""
    cols = _get_table_columns(cursor, 'agent_analysis_history')
    for col, typ in [
        ('thinking_text', 'LONGTEXT'),
        ('remark',         'TEXT'),
    ]:
        if col not in cols:
            cursor.execute(f'ALTER TABLE agent_analysis_history ADD COLUMN {col} {typ} NULL')


def _get_table_columns(cursor, table_name: str) -> set:
    """获取表的所有列名（兼容历史迁移）"""
    cursor.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
        (table_name,)
    )
    return {row['COLUMN_NAME'] for row in cursor.fetchall()}


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
            'change_pct': _snapshot_float(h.get('profit_loss_pct') or h.get('changePct')),
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
            'change_pct': _snapshot_float(s.get('changePct')),
            'source': 'recommended',
        })
    return out


def save_recommended_stocks_as_holdings(
    agent_id: str,
    stocks: List[Dict],
    remark_template: str = 'AI推荐({agent_id})',
) -> int:
    """
    将 AI analysis 返回的 recommendedStocks 写入 holdings 表（若无真实持仓时的自动同步）。
    返回写入/更新的条数。
    """
    def _parse_float(v, default: float = 0.0) -> float:
        """解析带 % 的字符串，如 '20%' -> 20.0"""
        if v is None or v == '':
            return default
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().rstrip('%').replace(',', '')
        try:
            return float(s)
        except (TypeError, ValueError):
            return default

    remark_tpl = remark_template or 'AI推荐({agent_id})'
    remark = remark_tpl.replace('{agent_id}', agent_id)

    if not stocks:
        return 0

    count = 0
    # 在同一连接+事务中完成：清理旧推荐 → 写入新推荐
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM holdings WHERE remark = %s', (remark,))
        for s in stocks:
            code = str(s.get('code') or '').strip()
            name = str(s.get('name') or '').strip()
            if not code or not name:
                continue
            try:
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
                ''', (
                    code, name, str(s.get('sector') or ''),
                    _parse_float(s.get('price') or 0),
                    _parse_float(s.get('price') or 0),
                    _parse_float(s.get('positionRatio') or 0),
                    _parse_float(s.get('changePct') or 0),
                    0.0, 0, 'long', remark,
                ))
                if cursor.rowcount > 0:
                    count += 1
            except Exception:
                pass
    return count


def build_analysis_holdings_snapshot(
    db_holdings: List[Dict],
    analysis_result: Any = None,
) -> List[Dict]:
    """
    写入 agent_analysis_history 的快照：优先 AI 推荐股票；若为空则用 DB 持仓。
    与 app.py/junge_trader.py 的逻辑保持一致。
    """
    # 优先使用 AI 推荐股票
    rec: List[Dict] = []
    if isinstance(analysis_result, dict):
        if isinstance(analysis_result.get('recommendedStocks'), list):
            rec = analysis_result['recommendedStocks']
        st = analysis_result.get('structured')
        if isinstance(st, dict) and isinstance(st.get('recommendedStocks'), list):
            rec = st['recommendedStocks']
    if rec:
        return snapshot_rows_from_recommended_stocks(rec)
    # 兜底：使用 DB 持仓
    return snapshot_rows_from_db_holdings(db_holdings)


def save_agent_analysis_history(
    agent_id: str,
    report_date: str,
    holdings_snapshot: List[Dict],
    analysis_result: Dict,
    raw_response: str = '',
    thinking: str = '',
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
    import math as _math
    local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def _s(obj):
        return _json.dumps(obj, ensure_ascii=False, default=lambda v: (
            None if isinstance(v, float) and (_math.isnan(v) or _math.isinf(v)) else v
        ))

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO agent_analysis_history
                (agent_id, report_date, scan_id, holdings_snapshot_json,
                 analysis_result_json, raw_response_text, thinking_text,
                 stance, confidence, tokens_used, model, report_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                scan_id = VALUES(scan_id),
                holdings_snapshot_json = VALUES(holdings_snapshot_json),
                analysis_result_json = VALUES(analysis_result_json),
                raw_response_text = VALUES(raw_response_text),
                thinking_text = VALUES(thinking_text),
                stance = VALUES(stance),
                confidence = VALUES(confidence),
                tokens_used = VALUES(tokens_used),
                model = VALUES(model),
                report_time = VALUES(report_time)
        ''', (
            agent_id,
            report_date,
            scan_id,
            _s(holdings_snapshot),
            _s(analysis_result),
            raw_response,
            thinking,
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
        # 只查存在的列，兼容历史迁移前的数据
        cols = _get_table_columns(cursor, 'agent_analysis_history')
        sel_cols = []
        for c in ['id', 'agent_id', 'report_date', 'scan_id',
                  'holdings_snapshot_json', 'analysis_result_json',
                  'raw_response_text', 'thinking_text', 'stance', 'confidence',
                  'tokens_used', 'model', 'report_time']:
            if c in cols:
                sel_cols.append(c)
        if not sel_cols:
            return []

        sql = f"SELECT {', '.join(sel_cols)} FROM agent_analysis_history WHERE agent_id = %s"
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
            # thinking_text 直接保留在 d 中
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
        cols = _get_table_columns(cursor, 'agent_analysis_history')
        sel_cols = []
        for c in ['id', 'agent_id', 'report_date', 'scan_id',
                  'holdings_snapshot_json', 'analysis_result_json',
                  'raw_response_text', 'thinking_text', 'stance', 'confidence',
                  'tokens_used', 'model', 'report_time']:
            if c in cols:
                sel_cols.append(c)
        if not sel_cols:
            return None

        sql = (f"SELECT {', '.join(sel_cols)} FROM agent_analysis_history "
               f"WHERE agent_id = %s ORDER BY report_date DESC, report_time DESC LIMIT 1")
        cursor.execute(sql, (agent_id,))
        row = cursor.fetchone()
        if not row:
            return None
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


def get_today_agent_analysis(agent_id: str) -> Optional[Dict]:
    """获取某 Agent 今日分析记录（含持仓快照和分析结果），无则返回 None"""
    import json as _json
    today = datetime.now().strftime('%Y-%m-%d')

    with get_connection() as conn:
        cursor = conn.cursor()
        cols = _get_table_columns(cursor, 'agent_analysis_history')
        sel_cols = []
        for c in ['id', 'agent_id', 'report_date', 'scan_id',
                  'holdings_snapshot_json', 'analysis_result_json',
                  'raw_response_text', 'thinking_text', 'stance', 'confidence',
                  'tokens_used', 'model', 'report_time']:
            if c in cols:
                sel_cols.append(c)
        if not sel_cols:
            return None

        sql = (f"SELECT {', '.join(sel_cols)} FROM agent_analysis_history "
               f"WHERE agent_id = %s AND report_date = %s ORDER BY report_time DESC LIMIT 1")
        cursor.execute(sql, (agent_id, today))
        row = cursor.fetchone()
        if not row:
            return None
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


# ─────────────────────────────────────────────────────────────────────────────
# 任务管理函数（类 Cursor/Claude Code 任务系统）
# ─────────────────────────────────────────────────────────────────────────────

def _parse_datetime(v):
    """将 datetime/date/str 统一转为 ISO 字符串，None 返回 None"""
    if v is None:
        return None
    if hasattr(v, 'isoformat'):
        return v.isoformat()
    return str(v)


def list_tasks(status: str = None, owner: str = None, limit: int = 100) -> List[Dict]:
    """
    列出任务，支持按 status / owner 过滤。
    默认返回所有状态的任务，按 priority DESC, created_at DESC 排序。
    """
    import json as _json

    with get_connection() as conn:
        cursor = conn.cursor()
        sql = "SELECT * FROM tasks WHERE status != 'deleted'"
        args = []
        if status:
            sql += " AND status = %s"
            args.append(status)
        if owner:
            sql += " AND owner = %s"
            args.append(owner)
        sql += " ORDER BY priority DESC, created_at DESC LIMIT %s"
        args.append(limit)
        cursor.execute(sql, args)
        rows = cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row) if not isinstance(row, dict) else row
            # JSON 字段
            if d.get('metadata'):
                if isinstance(d['metadata'], str):
                    try:
                        d['metadata'] = _json.loads(d['metadata'])
                    except Exception:
                        d['metadata'] = {}
            # blocked_by / blocks 逗号分隔 → list
            d['blocked_by'] = [x for x in (d.get('blocked_by') or '').split(',') if x]
            d['blocks']     = [x for x in (d.get('blocks')     or '').split(',') if x]
            # 时间字段
            for field in ('created_at', 'updated_at', 'started_at', 'completed_at'):
                d[field] = _parse_datetime(d.get(field))
            result.append(d)
        return result


def get_task(task_id: int) -> Optional[Dict]:
    """根据 ID 获取单个任务"""
    import json as _json

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM tasks WHERE id = %s AND status != 'deleted'",
            (task_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row) if not isinstance(row, dict) else row
        if d.get('metadata'):
            if isinstance(d['metadata'], str):
                try:
                    d['metadata'] = _json.loads(d['metadata'])
                except Exception:
                    d['metadata'] = {}
        d['blocked_by'] = [x for x in (d.get('blocked_by') or '').split(',') if x]
        d['blocks']     = [x for x in (d.get('blocks')     or '').split(',') if x]
        for field in ('created_at', 'updated_at', 'started_at', 'completed_at'):
            d[field] = _parse_datetime(d.get(field))
        return d


def create_task(
    subject: str,
    description: str = '',
    owner: str = None,
    active_form: str = None,
    priority: int = 0,
    metadata: Dict = None,
    blocked_by: List[str] = None,
) -> int:
    """
    创建新任务，返回 task_id。
    blocked_by: 依赖的任务 ID 列表（字符串或整数）
    """
    import json as _json

    metadata_json = _json.dumps(metadata or {}, ensure_ascii=False) if metadata else None
    blocked_by_str = ','.join(str(x) for x in (blocked_by or []))
    # 维护 blocks 字段（被本任务阻塞的任务）
    blocks_str = ''

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tasks (subject, description, owner, active_form, priority, metadata, blocked_by, blocks)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (subject, description, owner, active_form, priority, metadata_json, blocked_by_str, blocks_str)
        )
        task_id = cursor.lastrowid

        # 更新 blocks 字段（让被依赖的任务记录本任务）
        if blocked_by:
            for dep_id in blocked_by:
                cursor.execute(
                    "UPDATE tasks SET blocks = CONCAT(IFNULL(blocks, ''), %s) WHERE id = %s AND status != 'deleted'",
                    (f',{dep_id}', int(dep_id))
                )
        return task_id


def update_task(
    task_id: int,
    subject: str = None,
    description: str = None,
    status: str = None,
    owner: str = None,
    active_form: str = None,
    priority: int = None,
    metadata: Dict = None,
    blocked_by: List[str] = None,
) -> bool:
    """
    更新任务字段，返回是否成功。
    status 变更时会自动设置 started_at / completed_at。
    """
    import json as _json

    fields = []
    args = []

    if subject is not None:
        fields.append("subject = %s")
        args.append(subject)
    if description is not None:
        fields.append("description = %s")
        args.append(description)
    if status is not None:
        fields.append("status = %s")
        args.append(status)
        # 自动时间戳
        if status == 'in_progress':
            fields.append("started_at = COALESCE(started_at, NOW())")
        elif status == 'completed':
            fields.append("completed_at = NOW()")
    if owner is not None:
        fields.append("owner = %s")
        args.append(owner)
    if active_form is not None:
        fields.append("active_form = %s")
        args.append(active_form)
    if priority is not None:
        fields.append("priority = %s")
        args.append(priority)
    if metadata is not None:
        fields.append("metadata = %s")
        args.append(_json.dumps(metadata, ensure_ascii=False))

    if not fields:
        return False

    # 处理 blocked_by 更新
    if blocked_by is not None:
        # 清除旧的 blocks 引用
        old_task = get_task(task_id)
        if old_task and old_task.get('blocked_by'):
            for dep_id in old_task['blocked_by']:
                cursor_select = None
                with get_connection() as conn:
                    c = conn.cursor()
                    c.execute(
                        "UPDATE tasks SET blocks = TRIM(BOTH ',' FROM REPLACE(CONCAT(',', blocks, ','), %s, ',')) WHERE id = %s",
                        (f',{dep_id},', int(dep_id))
                    )
        # 设置新的 blocked_by
        fields.append("blocked_by = %s")
        args.append(','.join(str(x) for x in blocked_by))
        # 更新被依赖任务的 blocks 字段
        with get_connection() as conn:
            c = conn.cursor()
            for dep_id in blocked_by:
                c.execute(
                    "UPDATE tasks SET blocks = CONCAT(IFNULL(blocks, ''), %s) WHERE id = %s AND status != 'deleted'",
                    (f',{dep_id}', int(dep_id))
                )

    args.append(task_id)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE tasks SET {', '.join(fields)} WHERE id = %s AND status != 'deleted'",
            args
        )
        return cursor.rowcount > 0


def delete_task(task_id: int) -> bool:
    """软删除任务（仅标记为 deleted）"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tasks SET status = 'deleted' WHERE id = %s",
            (task_id,)
        )
        return cursor.rowcount > 0


def get_task_summary() -> Dict:
    """
    获取任务统计摘要，用于 Dashboard 展示。
    返回 { total, pending, in_progress, completed }
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT status, COUNT(*) as count
            FROM tasks
            WHERE status != 'deleted'
            GROUP BY status
            """
        )
        rows = cursor.fetchall()
        result = {'total': 0, 'pending': 0, 'in_progress': 0, 'completed': 0}
        for row in rows:
            d = dict(row) if not isinstance(row, dict) else row
            s = d.get('status', '')
            c = d.get('count', 0)
            if s in result:
                result[s] = c
            result['total'] += c
        return result


# ─────────────────────────────────────────────────────────────────────────────
# 飞书推送配置 CRUD
# ─────────────────────────────────────────────────────────────────────────────

def get_push_config() -> Dict:
    """获取飞书推送主配置（只读第一条记录，不存在则返回默认）"""
    defaults = {
        'id': 0,
        'webhook_url': '',
        'enabled': True,
        'agent_ids': [],
        'top_stocks_per_agent': 3,
        'consensus_top_n': 5,
        'analysis_max_workers': 2,
    }
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM push_config ORDER BY id ASC LIMIT 1')
        row = cursor.fetchone()
        if not row:
            return defaults
        agent_ids = []
        if row.get('agent_ids_json'):
            try:
                agent_ids = json.loads(row['agent_ids_json'])
            except (json.JSONDecodeError, TypeError):
                pass
        return {
            'id': row['id'],
            'webhook_url': row.get('webhook_url') or '',
            'enabled': bool(row.get('enabled', 1)),
            'agent_ids': agent_ids,
            'top_stocks_per_agent': int(row.get('top_stocks_per_agent', 3)),
            'consensus_top_n': int(row.get('consensus_top_n', 5)),
            'analysis_max_workers': int(row.get('analysis_max_workers', 2)),
            'updated_at': _parse_datetime(row.get('updated_at')),
        }


def upsert_push_config(config: Dict) -> Dict:
    """
    创建或更新飞书推送配置。
    config 支持: webhook_url, enabled, agent_ids, top_stocks_per_agent,
                consensus_top_n, analysis_max_workers
    """
    # 先读取旧配置（用于变更对比）
    old = get_push_config()
    is_first_save = (old.get('id') or 0) == 0

    webhook = str(config.get('webhook_url') or '').strip()[:768]
    enabled = 1 if config.get('enabled') else 0
    agent_ids = config.get('agent_ids') or []
    if isinstance(agent_ids, (list, tuple)):
        agent_ids_json = json.dumps(agent_ids, ensure_ascii=False)
    else:
        agent_ids_json = '[]'
    top_stocks = max(1, min(10, int(config.get('top_stocks_per_agent', 3))))
    consensus_n = max(1, min(20, int(config.get('consensus_top_n', 5))))
    workers = max(1, min(8, int(config.get('analysis_max_workers', 2))))

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM push_config ORDER BY id ASC LIMIT 1 FOR UPDATE')
        row = cursor.fetchone()
        if row:
            cursor.execute('''
                UPDATE push_config
                SET webhook_url=%s, enabled=%s, agent_ids_json=%s,
                    top_stocks_per_agent=%s, consensus_top_n=%s, analysis_max_workers=%s
                WHERE id=%s
            ''', (webhook, enabled, agent_ids_json, top_stocks, consensus_n, workers, row['id']))
        else:
            cursor.execute('''
                INSERT INTO push_config
                    (webhook_url, enabled, agent_ids_json, top_stocks_per_agent, consensus_top_n, analysis_max_workers)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (webhook, enabled, agent_ids_json, top_stocks, consensus_n, workers))
        conn.commit()

    # ── 首次保存：记录初始化日志 ───────────────────────────────────────────
    if is_first_save:
        save_push_config_log({
            'change_type': 'webhook_update',
            'success': True,
            'details': {'type': 'initial_save', 'webhook_url': webhook},
            'summary': f'Webhook 地址已更新：由旧地址指向 {webhook[:40]}...',
        })

    # ── 记录变更日志 ──────────────────────────────────────────────────────────
    AGENT_NAMES = {
        'beijing': '北京炒家', 'qiao': '乔帮主', 'jia': '炒股养家',
        'jun': '钧哥天下无双', 'speed': '极速先锋', 'trend': '趋势追随者',
        'quant': '量化之翼', 'deepseek': '深度思考者',
    }

    # webhook 变更
    old_webhook = old.get('webhook_url') or ''
    if old_webhook != webhook:
        o = old_webhook[:40] + ('...' if len(old_webhook) > 40 else '')
        n = webhook[:40] + ('...' if len(webhook) > 40 else '')
        save_push_config_log({
            'change_type': 'webhook_update',
            'success': True,
            'details': {'old': old_webhook, 'new': webhook},
            'summary': f'Webhook 地址已更新：由 {o} → {n}',
        })

    # enabled 变更
    if bool(old.get('enabled')) != bool(enabled):
        save_push_config_log({
            'change_type': 'enable_toggle',
            'success': True,
            'details': {'old': bool(old.get('enabled')), 'new': bool(enabled)},
            'summary': f'推送开关已{"启用" if enabled else "停用"}',
        })

    # agent 变更
    old_agents = set(old.get('agent_ids') or [])
    new_agents_set = set(agent_ids)
    for a in (new_agents_set - old_agents):
        save_push_config_log({
            'change_type': 'agent_add',
            'success': True,
            'details': {'agent_id': a, 'agent_name': AGENT_NAMES.get(a, a)},
            'summary': f'新增了推送角色："{AGENT_NAMES.get(a, a)}"',
        })
    for a in (old_agents - new_agents_set):
        save_push_config_log({
            'change_type': 'agent_remove',
            'success': True,
            'details': {'agent_id': a, 'agent_name': AGENT_NAMES.get(a, a)},
            'summary': f'移除了推送角色："{AGENT_NAMES.get(a, a)}"',
        })

    # 并发数变更
    if int(old.get('analysis_max_workers', 0)) != workers:
        save_push_config_log({
            'change_type': 'param_update',
            'success': True,
            'details': {'param': 'analysis_max_workers', 'old': old.get('analysis_max_workers'), 'new': workers},
            'summary': f'修改了并发数，从 {old.get("analysis_max_workers")} 提高到 {workers}',
        })

    # 共识上限变更
    if int(old.get('consensus_top_n', 0)) != consensus_n:
        save_push_config_log({
            'change_type': 'param_update',
            'success': True,
            'details': {'param': 'consensus_top_n', 'old': old.get('consensus_top_n'), 'new': consensus_n},
            'summary': f'修改了共识股上限，从 {old.get("consensus_top_n")} 调整为 {consensus_n}',
        })

    # 每Agent推荐股上限变更
    if int(old.get('top_stocks_per_agent', 0)) != top_stocks:
        save_push_config_log({
            'change_type': 'param_update',
            'success': True,
            'details': {'param': 'top_stocks_per_agent', 'old': old.get('top_stocks_per_agent'), 'new': top_stocks},
            'summary': f'修改了每Agent推荐股，从 {old.get("top_stocks_per_agent")} 调整为 {top_stocks}',
        })

    return get_push_config()


def get_push_slots() -> List[Dict]:
    """获取所有推送时段配置"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM push_slots ORDER BY time_str ASC')
        return [
            {
                'key': r['slot_key'],
                'time': r['time_str'],
                'label': r['label'],
                'template': r['template'],
                'enabled': bool(r['enabled']),
            }
            for r in cursor.fetchall()
        ]


def update_push_slots(slot_updates: List[Dict]) -> List[Dict]:
    """
    批量更新推送时段。
    slot_updates: [{key: '0900', enabled: True/False, label: '...', time: '09:00'}, ...]
    """
    if not slot_updates:
        return get_push_slots()

    old_slots = {s['key']: s for s in get_push_slots()}

    with get_connection() as conn:
        cursor = conn.cursor()
        for s in slot_updates:
            k = str(s.get('key') or '').strip()
            if not k:
                continue
            enabled = 1 if s.get('enabled') else 0
            label = str(s.get('label') or '').strip()[:100]
            time_str = str(s.get('time') or '').strip()[:10]
            cursor.execute('''
                UPDATE push_slots
                SET enabled=%s, label=%s, time_str=%s
                WHERE slot_key=%s
            ''', (enabled, label, time_str, k))
        conn.commit()

    # 记录变更日志（新增时段 label 变更）
    for s in slot_updates:
        k = str(s.get('key') or '').strip()
        if not k:
            continue
        old_s = old_slots.get(k, {})
        new_label = str(s.get('label') or '').strip()
        old_label = old_s.get('label', '')
        new_enabled = bool(s.get('enabled'))
        old_enabled = bool(old_s.get('enabled', False))
        if new_label and new_label != old_label:
            save_push_config_log({
                'change_type': 'slot_update',
                'success': True,
                'details': {'slot_key': k, 'old_label': old_label, 'new_label': new_label, 'time': s.get('time', '')},
                'summary': f'更新了定时推送时段，新增了 "{new_label}"',
            })
        elif new_enabled != old_enabled and new_enabled:
            save_push_config_log({
                'change_type': 'slot_update',
                'success': True,
                'details': {'slot_key': k, 'label': old_label or new_label, 'time': s.get('time', '')},
                'summary': f'启用了定时推送时段 "{old_label or new_label}"',
            })

    return get_push_slots()


def save_push_history(record: Dict) -> int:
    """保存一条推送历史记录，返回新 id"""
    import math
    def _s(obj):
        return json.dumps(obj, ensure_ascii=False, default=lambda v: (
            None if isinstance(v, float) and (math.isnan(v) or math.isinf(v)) else v
        ))

    gen_at = record.get('generated_at') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(gen_at, datetime):
        gen_at = gen_at.strftime('%Y-%m-%d %H:%M:%S')

    top_cons = record.get('top_consensus') or []
    digest_json = _s(record.get('digest') or {})

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO push_history
                (generated_at, slot_key, slot_label, trigger_type, sent, dry_run,
                 agent_count, success_count, failed_count, consensus_count,
                 top_consensus_json, digest_json, error_text)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            gen_at,
            str(record.get('slot_key') or ''),
            str(record.get('slot_label') or ''),
            str(record.get('trigger_type') or 'scheduled'),
            1 if record.get('sent') else 0,
            1 if record.get('dry_run') else 0,
            int(record.get('agent_count') or 0),
            int(record.get('success_count') or 0),
            int(record.get('failed_count') or 0),
            int(record.get('consensus_count') or 0),
            json.dumps(top_cons, ensure_ascii=False),
            digest_json,
            str(record.get('error_text') or ''),
        ))
        conn.commit()
        return cursor.lastrowid


def get_push_history(limit: int = 30) -> List[Dict]:
    """获取推送历史记录"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM push_history
            ORDER BY generated_at DESC
            LIMIT %s
        ''', (limit,))
        return [
            {
                'id': r['id'],
                'generatedAt': _parse_datetime(r['generated_at']),
                'slotKey': r['slot_key'],
                'slotLabel': r['slot_label'],
                'triggerType': r['trigger_type'],
                'sent': bool(r['sent']),
                'dryRun': bool(r['dry_run']),
                'agentCount': r['agent_count'],
                'successCount': r['success_count'],
                'failedCount': r['failed_count'],
                'consensusCount': r['consensus_count'],
                'topConsensus': json.loads(r['top_consensus_json'] or '[]') if r.get('top_consensus_json') else [],
                'errorText': r['error_text'] or '',
            }
            for r in cursor.fetchall()
        ]


def save_push_config_log(log: Dict) -> int:
    """
    保存一条配置变更日志，返回新 id。
    log: {
        change_type: str,  # webhook_update | agent_add | agent_remove | slot_update | param_update | enable_toggle
        success: bool,
        details: dict,     # 变更详情
        summary: str,      # 摘要描述
    }
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO push_config_log (change_type, success, details_json, summary)
            VALUES (%s, %s, %s, %s)
        ''', (
            str(log.get('change_type') or 'unknown'),
            1 if log.get('success') else 0,
            json.dumps(log.get('details') or {}, ensure_ascii=False),
            str(log.get('summary') or '')[:200],
        ))
        conn.commit()
        return cursor.lastrowid


def get_push_config_logs(limit: int = 50) -> List[Dict]:
    """获取配置变更日志，分页"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM push_config_log
            ORDER BY changed_at DESC
            LIMIT %s
        ''', (limit,))
        rows = cursor.fetchall()
        return [
            {
                'id': r['id'],
                'changedAt': _parse_datetime(r['changed_at']),
                'changeType': r['change_type'],
                'success': bool(r['success']),
                'details': json.loads(r['details_json'] or '{}') if r.get('details_json') else {},
                'summary': r['summary'] or '',
            }
            for r in rows
        ]


def delete_push_config_log(log_id: int) -> bool:
    """删除指定日志"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM push_config_log WHERE id = %s', (log_id,))
        conn.commit()
        return cursor.rowcount > 0


# ─────────────────────────────────────────────────────────────────────────────
# 新闻缓存表初始化
# ─────────────────────────────────────────────────────────────────────────────

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
