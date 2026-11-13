#!/usr/bin/env python3
"""pakinfo.py <resources.pak> <resources.pak.info> [--top N] : .pak の中身を生成元の grd 別に集計する(MB)。"""
import sys, os, collections
src = '/root/cef/chromium/src'
sys.path.insert(0, src + '/tools/grit')
from grit.format import data_pack
pak, info = sys.argv[1], sys.argv[2]
top = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 60
names = {}
for l in open(info):
    f = l.rstrip('\n').split(',')
    if len(f) >= 3 and f[1].isdigit(): names[int(f[1])] = (f[0], f[2])
d = data_pack.ReadDataPack(pak)
by = collections.Counter(); cnt = collections.Counter(); unk = 0
for i, b in d.resources.items():
    n = names.get(i)
    g = os.path.normpath(n[1]) if n else '(unknown)'
    g = g.replace('../../', '')
    by[g] += len(b); cnt[g] += 1
print(f'{pak}: {len(d.resources)} resources, {sum(by.values())/1e6:.2f} MB, file {os.path.getsize(pak)/1e6:.2f} MB')
for g, v in by.most_common(top): print(f'{v/1e6:8.3f} MB {cnt[g]:5d}  {g}')
