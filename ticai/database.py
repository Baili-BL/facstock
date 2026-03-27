"""
题材挖掘数据库模块 - 使用主项目的 MySQL 连接
"""
import json
from datetime import datetime, date
from typing import List, Dict, Optional
from database import get_connection, get_db_config
import pymysql


def _safe_float(val) -> float:
    """安全转换为 float"""
    if val is None or val == '' or val == '-':
        return 0.0
    try:
        s = str(val).replace(',', '').replace('亿', '').replace('万', '')
        return float(s)
    except:
        return 0.0


def init_ticai_tables():
    """初始化题材挖掘相关表"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticai_reports (
                id INT AUTO_INCREMENT PRIMARY KEY,
                report_date DATE NOT NULL UNIQUE,
                market_change DOUBLE DEFAULT 0,
                themes_count INT DEFAULT 0,
                stocks_count INT DEFAULT 0,
                theme_extras TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_report_date (report_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticai_recommended_stocks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                report_id INT NOT NULL,
                theme_name VARCHAR(100) NOT NULL,
                stock_code VARCHAR(20) NOT NULL,
                stock_name VARCHAR(50) NOT NULL,
                recommend_price DOUBLE DEFAULT 0,
                change_pct DOUBLE DEFAULT 0,
                score INT DEFAULT 0,
                role VARCHAR(20),
                role_reason VARCHAR(100),
                `signal` VARCHAR(100),
                volume_level VARCHAR(20),
                strength VARCHAR(20),
                is_weak_to_strong TINYINT DEFAULT 0,
                is_front_runner TINYINT DEFAULT 0,
                front_runner_tags TEXT,
                market_cap DOUBLE DEFAULT 0,
                amount DOUBLE DEFAULT 0,
                turnover_rate DOUBLE DEFAULT 0,
                open_change DOUBLE DEFAULT 0,
                is_buyable TINYINT DEFAULT 1,
                unbuyable_reason VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_report_id (report_id),
                INDEX idx_stock_code (stock_code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ticai_performance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                stock_id INT NOT NULL,
                track_date DATE NOT NULL,
                days_held INT NOT NULL,
                current_price DOUBLE DEFAULT 0,
                return_pct DOUBLE DEFAULT 0,
                is_trading_day TINYINT DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uk_stock_date (stock_id, track_date),
                INDEX idx_stock_id (stock_id),
                INDEX idx_track_date (track_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')

    print("✅ 题材挖掘数据库表初始化完成")


def save_report(report_date: date, market_change: float, themes_data: Dict) -> int:
    """保存每日推荐报表（含主题级 emotion / quality / news 分析）"""
    themes_count = len(themes_data)
    stocks_count = sum(len(t.get("stocks", [])) for t in themes_data.values())

    # 提取主题级分析字段，存入 theme_extras JSON（完整重建所需字段）
    theme_extras = {}
    for theme_name, theme_data in themes_data.items():
        theme_extras[theme_name] = {
            "info": theme_data.get("info", {}),
            "history": theme_data.get("history", {}),
            "hot_score": theme_data.get("hot_score", 0),
            "market_change": theme_data.get("market_change", 0),
            "emotion": theme_data.get("emotion", {}),
            "quality": theme_data.get("quality", {}),
            "news": theme_data.get("news", {}),
        }

    with get_connection() as conn:
        cursor = conn.cursor()

        # 查找是否已有当日报表
        cursor.execute('SELECT id FROM ticai_reports WHERE report_date = %s', (report_date,))
        row = cursor.fetchone()

        if row:
            report_id = row['id']
            cursor.execute(
                'UPDATE ticai_reports SET market_change=%s, themes_count=%s, stocks_count=%s, theme_extras=%s WHERE id=%s',
                (market_change, themes_count, stocks_count, json.dumps(theme_extras, ensure_ascii=False), report_id)
            )
            cursor.execute('DELETE FROM ticai_recommended_stocks WHERE report_id = %s', (report_id,))
        else:
            cursor.execute(
                'INSERT INTO ticai_reports (report_date, market_change, themes_count, stocks_count, theme_extras) VALUES (%s, %s, %s, %s, %s)',
                (report_date, market_change, themes_count, stocks_count, json.dumps(theme_extras, ensure_ascii=False))
            )
            report_id = cursor.lastrowid

        # 保存推荐股票
        for theme_name, theme_data in themes_data.items():
            for stock in theme_data.get("stocks", []):
                price_str = stock.get("price", "0")
                try:
                    price = float(price_str) if price_str and price_str != "-" else 0
                except:
                    price = 0

                change_pct = stock.get("change_pct_num", 0) or 0
                turnover_str = stock.get("turnover_rate", "0%")
                try:
                    turnover = float(turnover_str.replace("%", "")) if turnover_str else 0
                except:
                    turnover = 0

                open_change = stock.get("open_change", 0) or 0
                is_buyable = 1
                unbuyable_reason = ""

                if open_change >= 9.5:
                    is_buyable, unbuyable_reason = 0, "一字涨停"
                elif open_change >= 7 and change_pct >= 9.9:
                    is_buyable, unbuyable_reason = 0, "竞价涨停"
                elif open_change >= 5 and change_pct >= 9.9:
                    is_buyable, unbuyable_reason = 0, "高开秒板"

                cursor.execute('''
                    INSERT INTO ticai_recommended_stocks (
                        report_id, theme_name, stock_code, stock_name,
                        recommend_price, change_pct, score, role, role_reason,
                        `signal`, volume_level, strength, is_weak_to_strong,
                        is_front_runner, front_runner_tags, market_cap, amount, turnover_rate,
                        open_change, is_buyable, unbuyable_reason
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ''', (
                    report_id, theme_name,
                    stock.get("code", ""), stock.get("name", ""),
                    price, change_pct, stock.get("score", 0),
                    stock.get("role", ""), stock.get("role_reason", ""),
                    stock.get("signal", ""), stock.get("volume_level", ""),
                    stock.get("strength", ""),
                    1 if stock.get("is_weak_to_strong") else 0,
                    1 if stock.get("is_front_runner") else 0,
                    json.dumps(stock.get("front_runner_tags", []), ensure_ascii=False),
                    _safe_float(stock.get("market_cap", 0)),
                    _safe_float(stock.get("amount", 0)),
                    turnover, open_change, is_buyable, unbuyable_reason
                ))

        print(f"✅ 报表保存成功: {report_date}, {themes_count}个题材, {stocks_count}只股票")
        return report_id


def get_report_by_date(report_date: date) -> Optional[Dict]:
    """获取指定日期的报表（含主题级 emotion/quality/news 重建）"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ticai_reports WHERE report_date = %s', (report_date,))
        row = cursor.fetchone()
        if not row:
            return None

        report = dict(row)

        # 读取主题级分析 JSON
        theme_extras = {}
        if report.get('theme_extras'):
            try:
                theme_extras = json.loads(report['theme_extras'])
            except Exception:
                theme_extras = {}

        cursor.execute(
            'SELECT * FROM ticai_recommended_stocks WHERE report_id = %s ORDER BY theme_name, score DESC',
            (report['id'],)
        )
        stocks = [dict(r) for r in cursor.fetchall()]

        # 按主题分组，并将 theme_extras 注入每个主题
        themes = {}
        for stock in stocks:
            tn = stock['theme_name']
            if tn not in themes:
                extra = theme_extras.get(tn, {})
                themes[tn] = {
                    "info": extra.get("info", {"change_pct": report.get('market_change', 0), "up_count": 0, "down_count": 0}),
                    "history": extra.get("history", {}),
                    "hot_score": extra.get("hot_score", 0),
                    "market_change": extra.get("market_change", report.get('market_change', 0)),
                    "emotion": extra.get("emotion", {}),
                    "quality": extra.get("quality", {}),
                    "news": extra.get("news", {}),
                    "stocks": [],
                }
            themes[tn]["stocks"].append(stock)

        report['themes'] = themes
        report['stocks'] = stocks
        return report


def get_recent_reports(limit: int = 30) -> List[Dict]:
    """获取最近的报表列表"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ticai_reports ORDER BY report_date DESC LIMIT %s', (limit,))
        return [dict(row) for row in cursor.fetchall()]


def get_stocks_for_tracking(days_ago: int = 5, only_buyable: bool = True) -> List[Dict]:
    """获取需要跟踪收益的股票"""
    with get_connection() as conn:
        cursor = conn.cursor()
        buyable_filter = "AND rs.is_buyable = 1" if only_buyable else ""
        cursor.execute(f'''
            SELECT rs.*, r.report_date
            FROM ticai_recommended_stocks rs
            JOIN ticai_reports r ON rs.report_id = r.id
            WHERE r.report_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
              {buyable_filter}
            ORDER BY r.report_date DESC
        ''', (days_ago,))
        return [dict(row) for row in cursor.fetchall()]


def save_performance(stock_id: int, track_date: date, days_held: int,
                     current_price: float, return_pct: float, is_trading_day: bool = True):
    """保存收益跟踪记录"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            REPLACE INTO ticai_performance
            (stock_id, track_date, days_held, current_price, return_pct, is_trading_day)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (stock_id, track_date, days_held, current_price, return_pct, 1 if is_trading_day else 0))


def get_stock_history(stock_code: str, limit: int = 10) -> List[Dict]:
    """获取某只股票的历史推荐记录"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT rs.*, r.report_date
            FROM ticai_recommended_stocks rs
            JOIN ticai_reports r ON rs.report_id = r.id
            WHERE rs.stock_code = %s
            ORDER BY r.report_date DESC LIMIT %s
        ''', (stock_code, limit))
        return [dict(row) for row in cursor.fetchall()]


def get_performance_summary(days: int = 30, only_buyable: bool = True) -> Dict:
    """获取收益统计摘要"""
    with get_connection() as conn:
        cursor = conn.cursor()

        summary = {
            "total_stocks": 0, "buyable_stocks": 0, "unbuyable_stocks": 0,
            "win_count": 0, "win_rate": 0, "avg_return": 0,
            "by_days": {}, "by_role": {}, "best_stocks": [], "worst_stocks": [],
        }

        buyable_filter = "AND rs.is_buyable = 1" if only_buyable else ""
        cursor.execute(f'''
            SELECT rs.*, r.report_date,
                   p.days_held, p.return_pct, p.current_price, p.track_date
            FROM ticai_recommended_stocks rs
            JOIN ticai_reports r ON rs.report_id = r.id
            LEFT JOIN ticai_performance p ON rs.id = p.stock_id
            WHERE r.report_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            {buyable_filter}
            ORDER BY rs.id, p.days_held
        ''', (days,))

        rows = cursor.fetchall()
        stock_returns = {}
        stock_info = {}

        for row in rows:
            row = dict(row)
            sid = row['id']
            if sid not in stock_info:
                stock_info[sid] = row
                stock_returns[sid] = {}
            if row.get('days_held') is not None:
                stock_returns[sid][row['days_held']] = row['return_pct']

        summary["total_stocks"] = len(stock_info)

        for dh in [1, 2, 3, 5]:
            returns = [sr.get(dh, 0) for sr in stock_returns.values() if dh in sr]
            if returns:
                summary["by_days"][f"T+{dh}"] = {
                    "count": len(returns),
                    "avg_return": round(sum(returns) / len(returns), 2),
                    "win_rate": round(len([r for r in returns if r > 0]) / len(returns) * 100, 1),
                }

        # 按角色统计
        role_returns = {}
        for sid, info in stock_info.items():
            role = info.get('role', '跟风') or '跟风'
            role_returns.setdefault(role, [])
            if 1 in stock_returns[sid]:
                role_returns[role].append(stock_returns[sid][1])
        for role, rets in role_returns.items():
            if rets:
                summary["by_role"][role] = {
                    "count": len(rets),
                    "avg_return": round(sum(rets) / len(rets), 2),
                    "win_rate": round(len([r for r in rets if r > 0]) / len(rets) * 100, 1),
                }

        # T+1 总体
        t1 = [sr.get(1, 0) for sr in stock_returns.values() if 1 in sr]
        if t1:
            summary["win_count"] = len([r for r in t1 if r > 0])
            summary["win_rate"] = round(summary["win_count"] / len(t1) * 100, 1)
            summary["avg_return"] = round(sum(t1) / len(t1), 2)

        # 最佳/最差
        stock_t1 = []
        for sid, info in stock_info.items():
            if 1 in stock_returns[sid]:
                stock_t1.append({
                    "code": info['stock_code'], "name": info['stock_name'],
                    "theme": info['theme_name'], "role": info.get('role', ''),
                    "recommend_price": info['recommend_price'],
                    "return_pct": stock_returns[sid][1],
                    "report_date": str(info['report_date']),
                })
        stock_t1.sort(key=lambda x: x['return_pct'], reverse=True)
        summary["best_stocks"] = stock_t1[:5]
        summary["worst_stocks"] = stock_t1[-5:][::-1] if len(stock_t1) >= 5 else stock_t1[::-1]

        return summary


# ==================== 新闻缓存 ====================

def init_news_table():
    """初始化新闻缓存表"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cached_news (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(500) NOT NULL,
                content TEXT,
                time VARCHAR(50),
                source VARCHAR(50),
                url VARCHAR(1000),
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uk_title (title(200)),
                INDEX idx_cached_at (cached_at),
                INDEX idx_source (source)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')


def save_news_items(news_list: List[Dict]) -> int:
    """保存新闻到数据库缓存（去重插入）"""
    if not news_list:
        return 0
    saved = 0
    with get_connection() as conn:
        cursor = conn.cursor()
        for item in news_list:
            try:
                cursor.execute('''
                    INSERT IGNORE INTO cached_news (title, content, time, source, url)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (
                    item.get('title', ''),
                    item.get('content', ''),
                    item.get('time', ''),
                    item.get('source', ''),
                    item.get('url', ''),
                ))
                saved += cursor.rowcount
            except Exception:
                pass
    return saved


def get_cached_news(days: int = 1) -> List[Dict]:
    """从数据库缓存读取最近 N 天的新闻"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT title, content, time, source, url, cached_at
            FROM cached_news
            WHERE cached_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
            ORDER BY time DESC
            LIMIT 500
        ''', (days,))
        return [dict(row) for row in cursor.fetchall()]


# 确保新闻表已初始化
try:
    init_news_table()
except Exception as e:
    print(f"[WARN] 新闻表初始化失败: {e}")
