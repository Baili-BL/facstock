#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查数据库中的历史分析记录
"""
import os
import sys
sys.path.insert(0, '/Users/kevin/Desktop/facSstock')

import database as db

def check_history():
    """检查历史分析记录"""
    print("=" * 70)
    print("📋 检查数据库中的历史分析记录")
    print("=" * 70)
    
    try:
        # 使用 database 模块的 get_agent_analysis_history 函数
        records = db.get_agent_analysis_history('jun', limit=10)
        
        if not records:
            print("❌ 没有历史分析记录")
            return False
        
        print(f"✅ 找到 {len(records)} 条历史记录\n")
        
        for i, rec in enumerate(records, 1):
            print(f"--- 记录 #{i} ---")
            print(f"  ID: {rec['id']}")
            print(f"  Agent: {rec['agent_id']}")
            print(f"  日期: {rec['report_date']}")
            print(f"  立场: {rec['stance']}")
            print(f"  信心: {rec['confidence']}")
            
            # 解析分析结果
            analysis_result = rec.get('analysis_result', {})
            if isinstance(analysis_result, dict):
                recommended = analysis_result.get('recommendedStocks', [])
                if recommended:
                    print(f"  推荐股票 ({len(recommended)}只):")
                    for stock in recommended[:5]:
                        if isinstance(stock, dict):
                            print(f"    - {stock.get('name', 'N/A')}（{stock.get('code', 'N/A')}）")
                            print(f"      板块: {stock.get('sector', 'N/A')}")
                            signal = stock.get('signal', 'N/A')
                            print(f"      信号: {signal[:60]}..." if len(str(signal)) > 60 else f"      信号: {signal}")
                        else:
                            print(f"    - {stock}")
                else:
                    print(f"  推荐股票: 无")
                
                # 显示市场简评
                commentary = analysis_result.get('marketCommentary', '')
                if commentary:
                    print(f"  市场简评: {commentary}")
            else:
                print(f"  分析结果格式异常: {type(analysis_result)}")
            
            # 原始响应预览
            raw = rec.get('raw_response_text', '')
            if raw:
                # 检查是否包含龙头股份或宁德时代
                has_loudan = '龙头股份' in raw
                has_ningde = '宁德时代' in raw
                if has_loudan or has_ningde:
                    print(f"  ⚠️ 发现固定股票: 龙头股份={has_loudan}, 宁德时代={has_ningde}")
                print(f"  原始响应（300字）: {raw[:300]}...")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_scan_data():
    """检查最新扫描数据"""
    print("\n" + "=" * 70)
    print("📊 检查最新扫描数据")
    print("=" * 70)
    
    try:
        latest_scan = db.get_latest_scan()
        if not latest_scan:
            print("❌ 没有扫描数据")
            return False
        
        print(f"扫描时间: {latest_scan.get('scan_time', 'N/A')}")
        
        results = latest_scan.get('results', {})
        
        # 统计主板股票
        main_board = []
        for sector_name, sector_data in results.items():
            if isinstance(sector_data, dict):
                for stock in sector_data.get('stocks', []):
                    if isinstance(stock, dict):
                        code = stock.get('code', '')
                        if code.startswith(('60', '00')):
                            main_board.append(stock)
        
        print(f"总股票数: {sum(len(s.get('stocks', [])) for s in results.values() if isinstance(s, dict))}")
        print(f"主板股票数: {len(main_board)}")
        
        if main_board:
            print(f"\n主板股票列表:")
            for s in main_board:
                print(f"  - {s.get('name', 'N/A')}（{s.get('code', 'N/A')}）")
                print(f"    板块: {s.get('sector', 'N/A')} | 评分: {s.get('total_score', 0)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    check_history()
    check_scan_data()
