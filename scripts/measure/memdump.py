#!/usr/bin/env python3
"""memdump.py: Chromium の memory-infra(Tracing の disabled-by-default-memory-infra)で、全プロセスのアロケータ別メモリを取る。
ブラウザ全体の CDP 接続(/json/version の webSocketDebuggerUrl)で Tracing.start → Tracing.requestMemoryDump → Tracing.end。
戻り値: {pid: {'type': プロセス名, 'allocators': {名前: MiB}}}。名前は第 1 階層(malloc、partition_alloc、v8、blink_gc、skia、gpu、
media、cc、discardable、shared_memory など)と、主要な第 2 階層(partition_alloc/partitions/*、media/* など)。
単体実行: memdump.py [port] で JSON を表示(実行中のブラウザに対して)。"""
import json, sys, time, urllib.request
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from cdp import WS

MIB = 1048576
SUB = ('partition_alloc/partitions/', 'media/', 'gpu/', 'skia/', 'cc/', 'v8/main/heap/', 'blink_gc/main/heap/', 'malloc/partitions/', 'discardable/', 'web_cache/', 'font_caches/')

def _size(attrs, key='size'):
    a = attrs.get(key)
    if not a: return None
    v = a.get('value')
    return int(v, 16) if isinstance(v, str) else v

def memdump(port=9222, timeout=60):
    ver = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version', timeout=5))
    ws = WS(ver['webSocketDebuggerUrl']); mid = [0]
    def call(method, **params):
        mid[0] += 1; i = mid[0]; ws.send(json.dumps({'id': i, 'method': method, 'params': params})); evs = []
        while True:
            m = json.loads(ws.recv())
            if m.get('id') == i:
                if 'error' in m: raise RuntimeError(f"{method}: {m['error']}")
                return m.get('result', {}), evs
            evs.append(m)
    call('Tracing.start', traceConfig={'includedCategories': ['disabled-by-default-memory-infra'], 'excludedCategories': ['*'],
                                       'memoryDumpConfig': {'triggers': []}}, transferMode='ReturnAsStream')
    time.sleep(1)
    r, _ = call('Tracing.requestMemoryDump', deterministic=False, levelOfDetail='detailed')
    _, evs = call('Tracing.end')
    t0 = time.time(); stream = None
    for m in evs:
        if m.get('method') == 'Tracing.tracingComplete': stream = m['params'].get('stream')
    while stream is None and time.time() - t0 < timeout:
        m = json.loads(ws.recv())
        if m.get('method') == 'Tracing.tracingComplete': stream = m['params'].get('stream')
    data = ''
    while True:
        rr, _ = call('IO.read', handle=stream, size=1 << 20); data += rr.get('data', '')
        if rr.get('eof'): break
    call('IO.close', handle=stream)
    try: ws.s.close()
    except OSError: pass
    tr = json.loads(data); ev = tr['traceEvents'] if isinstance(tr, dict) else tr
    names = {}; out = {}
    for e in ev:
        if e.get('ph') == 'M' and e.get('name') == 'process_name': names[e['pid']] = e['args'].get('name')
        if e.get('ph') == 'M' and e.get('name') == 'process_labels': names.setdefault(e['pid'], e['args'].get('labels'))
    for e in ev:
        if e.get('ph') != 'v': continue
        alloc = (((e.get('args') or {}).get('dumps') or {}).get('allocators')) or {}
        d = out.setdefault(e['pid'], {'type': None, 'allocators': {}})
        for name, v in alloc.items():
            if '/' in name and not any(name.startswith(s) and name.count('/') == s.count('/') for s in SUB): continue
            sz = _size(v.get('attrs', {}))
            if sz: d['allocators'][name] = round(sz / MIB, 1)
    for pid, d in out.items(): d['type'] = names.get(pid)
    return {'ok': r.get('success'), 'processes': out}

def summarize(dump, top=12):
    """プロセス種別ごとに第 1 階層のアロケータを合算(MiB)。"""
    agg = {}
    for pid, d in dump['processes'].items():
        t = (d['type'] or '?').split(' ')[0]
        for k, v in d['allocators'].items():
            if '/' in k: continue
            a = agg.setdefault(t, {}); a[k] = round(a.get(k, 0) + v, 1)
    return {t: dict(sorted(a.items(), key=lambda x: -x[1])[:top]) for t, a in agg.items()}

if __name__ == '__main__':
    d = memdump(int(sys.argv[1]) if len(sys.argv) > 1 else 9222)
    print(json.dumps(summarize(d), ensure_ascii=False, indent=1))
    print(json.dumps(d, ensure_ascii=False)[:4000])
