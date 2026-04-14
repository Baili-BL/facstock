#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取最新的真实扫描股票数据，用于更新前端演示数据
"""
import sys
sys.path.insert(0, '/Users/kevin/Desktop/facSstock')

import database as db
import json

def get_latest_stocks():
    """获取最新扫描数据中的股票"""
    latest_scan = db.get_latest_scan()
    if not latest_scan:
        print("❌ 没有扫描数据")
        return []
    
    results = latest_scan.get('results', {})
    all_stocks = []
    
    for sector_name, sector_data in results.items():
        if isinstance(sector_data, dict):
            for stock in sector_data.get('stocks', []):
                if isinstance(stock, dict):
                    stock['sector'] = sector_name
                    all_stocks.append(stock)
    
    return all_stocks

def format_for_vue(all_stocks):
    """格式化为 Vue 演示数据"""
    # 按评分排序
    sorted_stocks = sorted(all_stocks, key=lambda x: x.get('total_score', 0), reverse=True)
    
    # 主板优先
    main_board = [s for s in sorted_stocks if str(s.get('code', '')).startswith(('60', '00'))]
    other = [s for s in sorted_stocks if not str(s.get('code', '')).startswith(('60', '00'))]
    
    selected = (main_board + other)[:5]  # 取前5只
    
    lines = []
    for i, s in enumerate(selected, 1):
        code = s.get('code', '')
        name = s.get('name', '')
        sector = s.get('sector', '')
        score = s.get('total_score', 0)
        grade = s.get('grade', 'C')
        change_pct = s.get('change_pct', 0) or 0
        code_suffix = '.SH' if code.startswith('6') else '.SZ'
        
        lines.append(f"      {{ name: '{name}', code: '{code}{code_suffix}', role: '{grade}级关注', reason: '{sector}板块，评分{score}，{change_pct:+.2f}%', chg_pct: {change_pct} }}")
    
    return "[\n" + ",\n".join(lines) + "\n    ]"

if __name__ == '__main__':
    all_stocks = get_latest_stocks()
    if all_stocks:
        print("最新扫描股票数据:")
        print("-" * 50)
        for s in all_stocks:
            print(f"  {s.get('name')}（{s.get('code')}）- {s.get('sector')} - 评分{s.get('total_score', 0)}")
        print()
        print("=" * 50)
        print("Vue 演示数据格式:")
        print("=" * 50)
        print(format_for_vue(all_stocks))
    else:
        print("没有扫描数据")
