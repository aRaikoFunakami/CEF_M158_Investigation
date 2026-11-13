#!/usr/bin/env python3
"""起動時の RAM 消費を計測する(コンテナ内で実行)。

  startram.py <name> <binary> [--runs N] [--wait SEC] [--url URL]

方法は https://qiita.com/rairaii/items/d5a5c3da56dbc7063a19 に合わせる(UPX 圧縮は対象外):
  1. 回収できない RAM = anon + shmem。cgroup v2 の memory.stat から読む(専用 cgroup /sys/fs/cgroup/fpmeas が
     使える場合)。使えない場合は全プロセスの smaps_rollup の Pss_Anon + Pss_Shmem の合計で代用する。
  2. ファイル由来(回収できる)= 全プロセスの Pss_File の合計。1 と足したものが「ファイル込み」の値。
  3. 実行ファイル本体(libcef.so / content_shell / chrome)のマッピングの RSS / PSS を /proc/*/smaps から合算。
     権限別(r-x = コード、r-- = 読み取り専用データ、rw- = 書き込みデータ)にも分ける。
  4. プロセス一覧(PID、PPID、--type、PSS)とプロセス数。
起動後 --wait 秒(既定 30)待ってから読む。--runs 回(既定 3)繰り返し、中央値を出す。
結果は /root/fp/results/<name>-startram.json。単位は MiB(記事に合わせる。他の表の MB = 10^6 とは違う)。
"""
import sys, os, json, time, statistics, argparse, glob, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure

CG = '/sys/fs/cgroup/fpmeas'

def cg_ok(): return os.path.exists(CG + '/memory.stat')

def cg_stat():
    d = {}
    for l in open(CG + '/memory.stat'):
        k, v = l.split()
        if k in ('anon', 'shmem', 'file', 'file_mapped', 'kernel', 'sock'): d[k] = round(int(v) / 1048576, 1)
    d['current'] = round(int(open(CG + '/memory.current').read()) / 1048576, 1)
    return d

def binary_maps(pids, names):
    """names に一致するファイルのマッピングを全プロセスで合算(MiB)。"""
    tot = {'rss': 0, 'pss': 0, 'size': 0}; perm = {}
    for pid in pids:
        try: lines = open(f'/proc/{pid}/smaps').read().splitlines()
        except OSError: continue
        t = False; p = ''
        for l in lines:
            m = re.match(r'^[0-9a-f]+-[0-9a-f]+ (\S+) \S+ \S+ \S+\s*(.*)$', l)
            if m:
                t = os.path.basename(m.group(2)) in names; p = m.group(1)[:3]
                continue
            if not t: continue
            f = l.split()
            if f[0] in ('Rss:', 'Pss:', 'Size:'):
                k = f[0][:-1].lower(); tot[k] += int(f[1])
                perm.setdefault(p, {'rss': 0, 'pss': 0, 'size': 0})[k] += int(f[1])
    r = {k: round(v / 1024, 1) for k, v in tot.items()}
    r['by_perm'] = {p: {k: round(v / 1024, 1) for k, v in d.items()} for p, d in sorted(perm.items())}
    return r

def proc_table(pids):
    rows = []
    for pid in sorted(pids):
        try:
            cmd = re.split(rb'[\0 ]', open(f'/proc/{pid}/cmdline', 'rb').read())  # setproctitle 対策(logs/416)
            st = open(f'/proc/{pid}/stat').read().rsplit(')', 1)[1].split()
            d = {}
            for l in open(f'/proc/{pid}/smaps_rollup'):
                f = l.split()
                if len(f) >= 3 and f[-1] == 'kB': d[f[0].rstrip(':')] = int(f[1])
        except OSError: continue
        typ = 'browser'
        for a in cmd:
            if a.startswith(b'--type='): typ = a[7:].decode()
            if a.startswith(b'--utility-sub-type='): typ = 'utility:' + a[19:].decode().split('.')[-1]
        rows.append({'pid': pid, 'ppid': int(st[1]), 'type': typ, 'rss': round(d.get('Rss', 0) / 1024, 1), 'pss': round(d.get('Pss', 0) / 1024, 1),
                     'pss_anon': round(d.get('Pss_Anon', 0) / 1024, 1), 'pss_file': round(d.get('Pss_File', 0) / 1024, 1),
                     'pss_shmem': round(d.get('Pss_Shmem', 0) / 1024, 1)})
    return rows

def one(binary, url, wait, names):
    measure.kill(binary); time.sleep(1)
    use_cg = cg_ok()
    if use_cg:
        # 計測用 cgroup が空になるのを待つ(前回の匿名ページが解放されるまで)
        for _ in range(20):
            if not open(CG + '/cgroup.procs').read().strip(): break
            time.sleep(0.5)
        base = cg_stat()
        open(CG + '/cgroup.procs', 'w').write(str(os.getpid()))
    p, c = measure.launch(binary, url)
    if use_cg: open('/sys/fs/cgroup/cgroup.procs' if not os.path.exists('/sys/fs/cgroup/main') else '/sys/fs/cgroup/main/cgroup.procs', 'w').write(str(os.getpid()))
    time.sleep(wait)
    pids = measure.procs(binary)
    rows = proc_table(pids)
    r = {'procs': len(rows), 'table': rows}
    for k in ('rss', 'pss', 'pss_anon', 'pss_file', 'pss_shmem'): r['sum_' + k] = round(sum(x[k] for x in rows), 1)
    r['unreclaimable_smaps'] = round(r['sum_pss_anon'] + r['sum_pss_shmem'], 1)
    if use_cg:
        s = cg_stat(); r['cgroup'] = s; r['cgroup_base'] = base
        r['unreclaimable_cgroup'] = round(s['anon'] + s['shmem'] - base['anon'] - base['shmem'], 1)
    r['unreclaimable'] = r.get('unreclaimable_cgroup', r['unreclaimable_smaps'])
    r['with_file'] = round(r['unreclaimable'] + r['sum_pss_file'], 1)
    r['binary_maps'] = binary_maps(pids, names)
    try: c.close()
    except Exception: pass
    measure.kill(binary)
    return r

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name'); ap.add_argument('binary'); ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--wait', type=int, default=30); ap.add_argument('--url', default='http://127.0.0.1:8000/caps.html')
    a = ap.parse_args()
    base = os.path.basename(a.binary)
    names = {base, 'libcef.so'} if base in measure.CEF_APPS else {base}
    runs = [one(a.binary, a.url, a.wait, names) for _ in range(a.runs)]
    med = lambda f: round(statistics.median(f(r) for r in runs), 1)
    out = {'name': a.name, 'binary': a.binary, 'url': a.url, 'wait': a.wait, 'cgroup': cg_ok(), 'unit': 'MiB',
           'median': {'procs': med(lambda r: r['procs']), 'unreclaimable': med(lambda r: r['unreclaimable']),
                      'unreclaimable_smaps': med(lambda r: r['unreclaimable_smaps']),
                      'pss_file': med(lambda r: r['sum_pss_file']), 'with_file': med(lambda r: r['with_file']),
                      'sum_rss': med(lambda r: r['sum_rss']), 'sum_pss': med(lambda r: r['sum_pss']),
                      'binary_rss': med(lambda r: r['binary_maps']['rss']), 'binary_pss': med(lambda r: r['binary_maps']['pss'])},
           'runs': runs}
    json.dump(out, open(f'{measure.RES}/{a.name}-startram.json', 'w'), indent=1, ensure_ascii=False)
    m = out['median']
    print(f"{a.name}: procs={m['procs']} 回収不可(anon+shmem)={m['unreclaimable']} (smaps {m['unreclaimable_smaps']}) Pss_File={m['pss_file']} "
          f"ファイル込み={m['with_file']} RSS合計={m['sum_rss']} PSS合計={m['sum_pss']} 本体 RSS={m['binary_rss']} PSS={m['binary_pss']} MiB cgroup={out['cgroup']}")
    r = runs[len(runs) // 2]
    print('  本体マッピング(権限別): ' + ', '.join(f"{p} size={d['size']} rss={d['rss']} pss={d['pss']}" for p, d in r['binary_maps']['by_perm'].items()))
    for x in r['table']: print(f"  pid={x['pid']} ppid={x['ppid']} {x['type']:28s} rss={x['rss']:7.1f} pss={x['pss']:7.1f} anon={x['pss_anon']:6.1f} file={x['pss_file']:6.1f} shmem={x['pss_shmem']:5.1f}")

if __name__ == '__main__': main()
