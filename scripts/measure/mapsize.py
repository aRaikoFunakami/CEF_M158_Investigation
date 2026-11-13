#!/usr/bin/env python3
"""mapsize.py <lld map> [--depth N] [--top N] [--prefix P] [--grep RE]

lld のマップファイル(-Wl,-Map=)を読み、入力オブジェクトファイルのパスをディレクトリ単位で集計する。
出力は MB(10^6)。--prefix で特定ディレクトリ以下だけを 1 段深く見る。--grep はパスに対する正規表現。
ロードされるセクション(VMA != 0)だけを数える。"""
import sys, re, collections, argparse
ap = argparse.ArgumentParser()
ap.add_argument('map'); ap.add_argument('--depth', type=int, default=2); ap.add_argument('--top', type=int, default=80)
ap.add_argument('--prefix', default=''); ap.add_argument('--grep', default=''); ap.add_argument('--files', action='store_true')
a = ap.parse_args()
line_re = re.compile(r'^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+(\d+)\s(\s*)(.*)$')
agg = collections.Counter(); total = 0; outsec = {}
g = re.compile(a.grep) if a.grep else None
cache = a.map + '.objs.tsv'
import os
if not os.path.exists(cache):
    # 1 回目だけマップ全体を読み、オブジェクトファイル別の合計を TSV に保存する(650MB のマップを毎回読まないため)
    objs = collections.Counter(); cur_out = None
    with open(a.map, errors='replace') as f:
        next(f)
        for line in f:
            m = line_re.match(line)
            if not m: continue
            vma, size, indent, rest = int(m.group(1), 16), int(m.group(3), 16), len(m.group(5)), m.group(6)
            if indent == 0:
                cur_out = rest; outsec[cur_out] = size; continue
            if indent != 8 or ':(' not in rest: continue
            if vma == 0 or cur_out.startswith('.debug') or cur_out in ('.comment', '.symtab', '.strtab', '.shstrtab'): continue
            path = rest.rsplit(':(', 1)[0]
            if path.startswith('./'): path = path[2:]
            # ThinLTO のネイティブオブジェクトは "obj/dir/target/libcef.so.lto.name.o" という名前になる
            path = re.sub(r'[A-Za-z0-9_.]+\.lto\.', '', path)
            mm = re.match(r'(.*\.(?:a|rlib))\((.*?)( at \d+)?\)(\.o)?$', path)
            if mm: path = mm.group(1) + '/' + mm.group(2)
            objs[path] += size
    with open(cache, 'w') as f:
        f.write('#outsec\t' + '\t'.join(f'{k}={v}' for k, v in outsec.items()) + '\n')
        for k, v in objs.items(): f.write(f'{k}\t{v}\n')
with open(cache) as f:
    for line in f:
        if line.startswith('#outsec'):
            for kv in line.rstrip('\n').split('\t')[1:]:
                k, v = kv.rsplit('=', 1); outsec[k] = int(v)
            continue
        path, size = line.rstrip('\n').rsplit('\t', 1); size = int(size)
        if g and not g.search(path): continue
        if a.prefix and not path.startswith(a.prefix): continue
        total += size
        if a.files: key = path
        else:
            parts = path.split('/')
            d = a.depth + (len(a.prefix.strip('/').split('/')) if a.prefix else 0)
            key = '/'.join(parts[:min(d, max(1, len(parts) - 1))])
        agg[key] += size
print(f'# total {total/1e6:.2f} MB  (prefix={a.prefix!r} grep={a.grep!r} depth={a.depth})')
if not a.prefix and not a.grep:
    print('# output sections: ' + ', '.join(f'{k}={v/1e6:.1f}' for k, v in sorted(outsec.items(), key=lambda x: -x[1])[:12]))
for k, v in agg.most_common(a.top):
    print(f'{v/1e6:8.2f}  {k}')
