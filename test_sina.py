#!/usr/bin/env python3
from curl_cffi import requests as cr
import re
import json

codes = ['sh000001', 'sz399001', 'sz399006', 'sh000688', 'sh000300']
codes_str = ','.join(codes)

resp = cr.get('https://hq.sinajs.cn/list', params={'list': codes_str}, 
               impersonate='chrome110', headers={'Referer': 'https://finance.sina.com.cn'}, timeout=10)
print('Status:', resp.status_code)
text = resp.text
print('Raw text:', repr(text[:300]))

# Try different patterns
patterns = [
    r'hq_str_([a-z0-9_,]+)="([^"]*)"',
    r'hq_str_([^=]+)="([^"]+)"',
    r'var ([^=]+)="([^"]+)"'
]
for p in patterns:
    matches = re.findall(p, text)
    if matches:
        print(f'Pattern {p[:30]}: {len(matches)} matches')
        for m in matches[:3]:
            print(f'  {m}')
