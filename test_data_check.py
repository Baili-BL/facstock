#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试钧哥天下无双的数据获取部分
"""
import os
import sys
sys.path.insert(0, '/Users/kevin/Desktop/facSstock')

from datetime import datetime
import database as db

def test_scan_data():
    """测试扫描数据"""
    print("=" * 70)
    print("📊 测试1: 扫描数据检查")
    print("=" * 70)
    
    try:
        latest_scan = db.get_latest_scan()
        if not latest_scan:
            print("❌ 没有扫描数据")
            return False
        
        print(f"✅ 获取到扫描数据")
        print(f"  扫描时间: {latest_scan.get('scan_time', 'N/A')}")
        
        results_dict = latest_scan.get('results', {})
        print(f"  板块数量: {len(results_dict)}")
        
        all_stocks = []
        for sector_name, sector_data in results_dict.items():
            if isinstance(sector_data, dict):
                stocks = sector_data.get('stocks', [])
                for stock in stocks:
                    if isinstance(stock, dict):
                        stock['sector'] = sector_name
                        all_stocks.append(stock)
        
        print(f"  股票总数: {len(all_stocks)}")
        
        if all_stocks:
            # 检查前几只股票
            print(f"\n前5只股票:")
            for i, s in enumerate(all_stocks[:5], 1):
                print(f"  [{i}] {s.get('name', 'N/A')}（{s.get('code', 'N/A')}）")
                print(f"       板块: {s.get('sector', 'N/A')}")
                print(f"       评分: {s.get('total_score', 'N/A')} | 等级: {s.get('grade', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 扫描数据获取失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_news_data():
    """测试新闻数据"""
    print("\n" + "=" * 70)
    print("📰 测试2: 新闻数据检查")
    print("=" * 70)
    
    try:
        from ai_service import fetch_market_news, fetch_junge_enhanced_news
        
        print("获取钧哥增强新闻...")
        news = fetch_junge_enhanced_news()
        print(f"✅ 获取到新闻，长度: {len(news)} 字")
        print(f"\n新闻预览（500字）:")
        print("-" * 70)
        print(news[:500])
        print("-" * 70)
        
        return True
        
    except Exception as e:
        print(f"❌ 新闻获取失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_agent_prompt():
    """测试 Agent Prompt 构建"""
    print("\n" + "=" * 70)
    print("🤖 测试3: Agent Prompt 构建")
    print("=" * 70)
    
    try:
        from utils.llm.agents import get_agent_registry
        from ai_service import fetch_junge_enhanced_news
        
        registry = get_agent_registry()
        jun_agent = registry.get('jun')
        
        if not jun_agent:
            print("❌ 未找到 jun agent")
            return False
        
        print(f"✅ 找到 Agent: {jun_agent['name']}")
        print(f"   Tagline: {jun_agent['tagline']}")
        print(f"   策略类型: {jun_agent['adviseType']}")
        
        # 获取扫描数据
        latest_scan = db.get_latest_scan()
        if latest_scan:
            results_dict = latest_scan.get('results', {})
            all_stocks = []
            for sector_name, sector_data in results_dict.items():
                if isinstance(sector_data, dict):
                    for stock in sector_data.get('stocks', []):
                        if isinstance(stock, dict):
                            stock['sector'] = sector_name
                            all_stocks.append(stock)
            
            # 格式化扫描数据
            main_board = [s for s in all_stocks if str(s.get('code', '')).startswith(('60', '00'))]
            main_board.sort(key=lambda x: x.get('total_score', 0), reverse=True)
            
            print(f"\n✅ 扫描数据: {len(all_stocks)}只股票, 主板: {len(main_board)}只")
            print(f"\n主板前5只:")
            for i, s in enumerate(main_board[:5], 1):
                print(f"  [{i}] {s.get('name', 'N/A')}（{s.get('code', 'N/A')}）")
        
        return True
        
    except Exception as e:
        print(f"❌ Agent Prompt 构建失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print(f"\n⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    results = []
    
    results.append(("扫描数据", test_scan_data()))
    results.append(("新闻数据", test_news_data()))
    results.append(("Agent Prompt", test_agent_prompt()))
    
    print("\n" + "=" * 70)
    print("📋 测试总结")
    print("=" * 70)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status} {name}")
