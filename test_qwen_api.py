#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 qwen3.6-plus responses API 调用（使用 app.py 中的格式）
"""
import sys
sys.path.insert(0, '/Users/kevin/Desktop/facSstock')

import os
import json
import urllib.request

def test_qwen_api():
    """测试 qwen3.6-plus responses API"""
    print("=" * 70)
    print("🔬 测试 qwen3.6-plus responses API")
    print("=" * 70)
    
    api_key = os.environ.get('DASHSCOPE_API_KEY', '') or 'sk-9bc00f8ae2d84e71b002b7ae82fd3188'
    print(f"API Key: {api_key[:15]}...")
    
    system_prompt = "你是一位专业的A股财经分析师【钧哥天下无双】，专注于题材炒作和事件驱动选股。"
    user_prompt = """今天是2026年4月12日。

请简要分析今日A股市场，重点关注：
1. 今日最重要的题材/板块
2. 推荐的龙头股标的

请用50字以内回答。"""
    
    print("\n发送请求到 qwen3.6-plus (responses API)...")
    
    # 使用 app.py 中相同的格式
    payload = json.dumps({
        "model": "qwen3.6-plus",
        "instructions": system_prompt,
        "input": user_prompt,
        "temperature": 0.4,
        "max_output_tokens": 500,
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/responses",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method='POST',
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            print(f"\n✅ API 调用成功!")
            print(f"响应数据: {json.dumps(data, ensure_ascii=False, indent=2)[:800]}")
            
            # 解析响应
            result = data.get('output', {}).get('text', '')
            
            if result:
                print(f"\n📝 解析结果:")
                print(result)
            else:
                print(f"\n⚠️ 响应为空")
            
            return True
            
    except urllib.error.HTTPError as e:
        print(f"\n❌ HTTP 错误: {e.code} - {e.reason}")
        error_body = e.read().decode('utf-8')
        print(f"响应内容: {error_body}")
        return False
    except Exception as e:
        print(f"\n❌ 调用失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    test_qwen_api()
