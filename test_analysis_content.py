#!/usr/bin/env python3
"""检查 analysis 完整内容"""
import urllib.request
import json

url = "http://127.0.0.1:5002/api/agents/analyze/jun/stream"
data = json.dumps({}).encode("utf-8")

req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        buffer = ""
        for chunk in resp:
            buffer += chunk.decode("utf-8")
            while "\n\n" in buffer:
                line, buffer = buffer.split("\n\n", 1)
                if line.startswith("data: "):
                    try:
                        d = json.loads(line[6:])
                        if d.get("type") == "done":
                            analysis = d.get("analysis", "")
                            print(f"=== analysis ({len(analysis)} chars) ===")
                            print(analysis)
                            print(f"\n=== structured ===")
                            print(json.dumps(d.get("structured"), ensure_ascii=False, indent=2))
                            return
                    except:
                        pass
except Exception as e:
    print(f"Error: {e}")
