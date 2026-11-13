#!/usr/bin/env python3
"""pagecheck.py <name> <binary> <page...> : テストページを開いて window.__result を取り、スクリーンショットを保存する。
measure.py func の 7 項目とは別の、追加確認用(i18n.html など)。結果は <結果dir>/<name>-page-<page>.json。"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure
name, binary, pages = sys.argv[1], sys.argv[2], sys.argv[3:]
os.makedirs(measure.SHOTS, exist_ok=True)
p, c = measure.launch(binary)
try:
    for page in pages:
        c.navigate(f'http://localhost:8000/{page}.html'); t0 = time.time(); r = None
        while time.time() - t0 < 30:
            time.sleep(2); r = c.eval('window.__result || null', await_promise=False)
            if r: break
        time.sleep(1); c.screenshot(f'{measure.SHOTS}/{name}-page-{page}.png')
        json.dump({'name': name, 'page': page, 'result': r}, open(f'{measure.RES}/{name}-page-{page}.json', 'w'), ensure_ascii=False, indent=1)
        print(page, json.dumps(r, ensure_ascii=False))
finally:
    measure.kill(binary)
