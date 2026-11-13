#!/usr/bin/env python3
"""ytanalyze.py <results-dir> <name>... : ytmem.py の結果を、二峰性(logs/427)を分けて集計する(ホストで実行)。
各回の「再生開始 60 秒以降」の標本の中央値を、その回の値とする。
- 全体: 有効回の中央値
- 低い側 / 高い側: レンダラの V8 ヒープ(memory-infra)が THRESH(既定 100MiB)未満 / 以上の回に分けた中央値と回数。
  高い側は V8 ヒープが 25〜35MiB 多く、SwiftShader 経路ではレンダラ PSS が約 180MiB 大きい(YouTube 側の状態の違い。logs/427、424)。
  レンダラ PSS で分けると、ソフトウェア合成(G2-tv)ではレンダラ自身がラスタするので常に大きく、誤判定する。
- 内訳(memory-infra、最後に 1 回): レンダラの media / v8 / malloc / partition_alloc、GPU プロセスの gpu、全プロセス合計
- MSE のバッファ総量(秒)、コマ落ち率、スレッド数(記録があれば)、jsHeap 上限、deviceMemory
単位 MiB。--md で Markdown の表、既定は 1 行 1 条件のテキスト。"""
import sys, os, json, statistics, glob
THRESH = float(os.environ.get('THRESH', 100))   # レンダラの V8 ヒープ(memory-infra の v8、MiB)

def med(v):
    v = [x for x in v if x is not None]
    return round(statistics.median(v), 1) if v else None

def per_run(r):
    late = [s for s in r['timeline'] if s['t'] >= 60] or r['timeline']
    g = lambda f: med([f(s) for s in late])
    bt = lambda k: (lambda s: (s['pss']['by_type'].get(k) or {}).get('pss'))
    ms = r.get('memdump_summary') or {}
    R = ms.get('Renderer', {}); G = ms.get('GPU', {})
    last = late[-1]
    return {'pss': g(lambda s: s['pss']['pss']), 'unrec': g(lambda s: (s.get('cg') or {}).get('unreclaimable')),
            'peak': (r['timeline'][-1].get('cg') or {}).get('peak'),
            'renderer': g(bt('renderer')), 'gpu': g(bt('gpu-process')), 'browser': g(bt('browser')),
            'media': R.get('media'), 'v8': R.get('v8'), 'malloc': R.get('malloc'), 'pa': R.get('partition_alloc'), 'gpu_alloc': G.get('gpu'),
            'buf_total': last['player'].get('buffered_total_s'), 'buf_ahead': g(lambda s: s['player'].get('buffered_ahead_s')),
            'dropped': (last['player'].get('dropped') or 0) / max(1, last['player'].get('total') or 1),
            'threads': last.get('threads'), 'jsHeapLimit': last['player'].get('jsHeapLimitMiB'), 'devMem': last['player'].get('deviceMemory'),
            'hwc': last['player'].get('hardwareConcurrency'), 'events': r.get('cg_events'), 'crashes': r.get('crashes')}

def analyze(path):
    d = json.load(open(path)); runs = [per_run(r) for r in d['runs'] if r.get('playing')]
    fails = [r for r in d['runs'] if not r.get('playing')]
    lo = [x for x in runs if (x['v8'] or 0) < THRESH]; hi = [x for x in runs if (x['v8'] or 0) >= THRESH]
    out = {'name': d['name'], 'build': d['binary'].split('/')[-2], 'nproc': d['env']['nproc'], 'memtotal': round(d['env']['memtotal_kib'] / 1024),
           'args': d['env'].get('extra_args') or '-', 'limit': d['env'].get('limit_mib'), 'valid': len(runs), 'tried': len(d['runs']),
           'blank': med([r['blank']['pss']['pss'] for r in d['runs'] if r.get('playing') and r.get('blank')]),
           'pss_all': med([x['pss'] for x in runs]), 'pss_lo': med([x['pss'] for x in lo]), 'n_lo': len(lo),
           'pss_hi': med([x['pss'] for x in hi]), 'n_hi': len(hi)}
    for k in ('unrec', 'peak', 'renderer', 'gpu', 'browser', 'media', 'v8', 'malloc', 'pa', 'gpu_alloc', 'buf_total', 'buf_ahead', 'jsHeapLimit', 'devMem', 'hwc'):
        out[k] = med([x[k] for x in (lo or runs)])   # 内訳は低い側(なければ全体)の中央値
    out['dropped'] = med([x['dropped'] * 100 for x in runs])
    th = [x['threads'] for x in runs if x['threads']]
    if th: out['threads'] = {k: med([t.get(k) for t in th]) for k in th[0]}
    out['oom_kill'] = sum(((r.get('cg_events') or {}).get('oom_kill', 0)) for r in d['runs'])
    out['fail_reasons'] = [{'events': r.get('cg_events'), 'crashes': r.get('crashes'), 'err': r.get('error'),
                            'last_ct': (r['timeline'][-1]['player'].get('currentTime') if r.get('timeline') else None)} for r in fails]
    return out

COLS = [('name', '条件'), ('build', 'ビルド'), ('nproc', 'nproc'), ('memtotal', 'MemTotal'), ('limit', '上限'), ('args', '引数'), ('valid', '有効'),
        ('blank', '再生前'), ('pss_all', '再生中(全)'), ('pss_lo', '低い側'), ('n_lo', 'n'), ('pss_hi', '高い側'), ('n_hi', 'n'),
        ('unrec', '回収不可'), ('renderer', 'renderer'), ('gpu', 'gpu'), ('browser', 'browser'), ('media', 'media'), ('v8', 'v8'),
        ('malloc', 'malloc'), ('pa', 'PA'), ('buf_total', 'MSE秒'), ('dropped', 'コマ落ち%'), ('jsHeapLimit', 'jsHeap上限'), ('devMem', 'devMem'), ('oom_kill', 'OOM')]

def main():
    d = sys.argv[1]; names = [a for a in sys.argv[2:] if not a.startswith('--')]
    files = []
    for n in names: files += sorted(glob.glob(f'{d}/{n}-ytmem.json'))
    rows = [analyze(f) for f in files]
    if '--json' in sys.argv: print(json.dumps(rows, ensure_ascii=False, indent=1)); return
    print('| ' + ' | '.join(c[1] for c in COLS) + ' |'); print('|' + '---|' * len(COLS))
    for r in rows: print('| ' + ' | '.join('' if r.get(k) is None else str(r.get(k)) for k, _ in COLS) + ' |')
    for r in rows:
        if r.get('threads'): print(f"threads {r['name']}: {r['threads']}")
        if r['fail_reasons']: print(f"fails {r['name']}: {json.dumps(r['fail_reasons'], ensure_ascii=False)[:600]}")

if __name__ == '__main__': main()
