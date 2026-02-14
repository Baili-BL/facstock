"""
收益跟踪模块 - 每日更新推荐股票的实盘收益
"""
import requests
from datetime import datetime, date, timedelta
from typing import List, Dict
from ticai.database import get_stocks_for_tracking, save_performance, get_connection
from ticai.config import REQUEST_TIMEOUT

_price_cache = {}


def get_batch_prices(stock_codes: List[str]) -> Dict[str, float]:
    """批量获取股票价格"""
    if not stock_codes:
        return {}
    prices = {}
    try:
        secids = []
        for code in stock_codes:
            market = "1" if code.startswith(("6", "9")) else "0"
            secids.append(f"{market}.{code}")

        url = "http://push2.eastmoney.com/api/qt/ulist/get"
        params = {"fltt": "2", "secids": ",".join(secids), "fields": "f2,f12"}
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        data = resp.json()

        if data.get("data") and data["data"].get("diff"):
            for item in data["data"]["diff"]:
                code = item.get("f12", "")
                price = item.get("f2", 0)
                if code and price and price != "-":
                    prices[code] = float(price)
    except Exception as e:
        print(f"批量获取价格失败: {e}")
    return prices


def is_trading_day(check_date: date = None) -> bool:
    if check_date is None:
        check_date = date.today()
    return check_date.weekday() < 5


def get_trading_days_between(start_date: date, end_date: date) -> int:
    if end_date <= start_date:
        return 0
    trading_days = 0
    current = start_date + timedelta(days=1)
    while current <= end_date:
        if is_trading_day(current):
            trading_days += 1
        current += timedelta(days=1)
    return trading_days


def update_all_performance():
    """更新所有需要跟踪的股票收益"""
    print("\n📊 开始更新题材收益跟踪...")
    today = date.today()

    if not is_trading_day(today):
        print("⚠️ 今天不是交易日，跳过更新")
        return

    stocks = get_stocks_for_tracking(days_ago=5)
    if not stocks:
        print("ℹ️ 没有需要跟踪的股票")
        return

    stock_codes = list(set(s['stock_code'] for s in stocks))
    prices = get_batch_prices(stock_codes)

    updated = 0
    for stock in stocks:
        code = stock['stock_code']
        report_date = stock['report_date']
        if isinstance(report_date, str):
            report_date = datetime.strptime(report_date, "%Y-%m-%d").date()

        days_held = get_trading_days_between(report_date, today)
        if days_held < 1:
            continue

        current_price = prices.get(code, 0)
        if current_price <= 0:
            continue

        recommend_price = stock['recommend_price']
        if recommend_price <= 0:
            continue

        return_pct = round((current_price - recommend_price) / recommend_price * 100, 2)
        save_performance(stock['id'], today, days_held, current_price, return_pct)
        updated += 1

    print(f"✅ 收益更新完成，共更新 {updated} 条记录")


def get_today_performance_report() -> Dict:
    """生成今日收益报告"""
    from database import get_connection as main_conn
    with main_conn() as conn:
        cursor = conn.cursor()
        today = date.today()

        cursor.execute('''
            SELECT p.*, rs.stock_code, rs.stock_name, rs.theme_name,
                   rs.role, rs.recommend_price, r.report_date
            FROM ticai_performance p
            JOIN ticai_recommended_stocks rs ON p.stock_id = rs.id
            JOIN ticai_reports r ON rs.report_id = r.id
            WHERE p.track_date = %s
            ORDER BY p.return_pct DESC
        ''', (today,))

        rows = [dict(r) for r in cursor.fetchall()]

        report = {"date": str(today), "summary": {}, "details": rows}
        by_days = {}
        for row in rows:
            dh = row['days_held']
            by_days.setdefault(dh, {"total": 0, "win": 0, "count": 0})
            by_days[dh]["count"] += 1
            by_days[dh]["total"] += row['return_pct']
            if row['return_pct'] > 0:
                by_days[dh]["win"] += 1

        for dh, d in by_days.items():
            report["summary"][f"T+{dh}"] = {
                "count": d["count"],
                "avg_return": round(d["total"] / d["count"], 2) if d["count"] else 0,
                "win_rate": round(d["win"] / d["count"] * 100, 1) if d["count"] else 0,
            }
        return report


def start_performance_scheduler():
    """启动收益更新定时任务"""
    try:
        import schedule
        import threading
        import time

        def run():
            schedule.every().day.at("15:30").do(update_all_performance)
            print("📅 题材收益跟踪定时任务已启动（每天15:30）")
            while True:
                schedule.run_pending()
                time.sleep(60)

        threading.Thread(target=run, daemon=True).start()
    except ImportError:
        print("⚠️ schedule模块未安装，定时任务无法启动")
