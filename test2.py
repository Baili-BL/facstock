#!/usr/bin/env python3
import urllib.request, json, re

url = "http://127.0.0.1:5002/api/agents/analyze/jun/stream"
data = json.dumps({}).encode("utf-8")
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

with urllib.request.urlopen(req, timeout=120) as resp:
    buf = b""
    for chunk in resp:
        buf += chunk
        text = buf.decode("utf-8", errors="replace")
        while "\n\n" in text:
            line, text = text.split("\n\n", 1)
            if line.startswith("data: "):
                try:
                    d = json.loads(line[6:])
                    if d.get("type") == "done":
                        a = d.get("analysis", "")
                        cleaned = re.sub(r'```json\s*\n?[\s\S]*?\n?```', '', a).strip()
                        print(f"analysis len={len(a)}, cleaned len={len(cleaned)}")
                        print("cleaned:", cleaned[:500])
                        s = d.get("structured", {})
                        print("structured keys:", list(s.keys()))
                        print("stance:", s.get("stance"))
                        print("confidence:", s.get("confidence"))
                        print("stocks:", len(s.get("recommendedStocks", [])))
                        break
                except: pass
