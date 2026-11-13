#!/usr/bin/env python3
"""mapsect.py <lld map> <出力セクション名> <分類用の接頭辞...>
lld のマップを読み、指定した出力セクション(例 .text)に入った入力セクションの大きさを、パスの接頭辞ごとに合計する(MB = 10^6)。
接頭辞は先に一致したものに数える。どれにも一致しなければ「その他」。M21 で Cobalt の DWARF による .text の内訳と比べるために追加。"""
import sys, re, collections
mp, sect, prefixes = sys.argv[1], sys.argv[2], sys.argv[3:]
line_re = re.compile(r'^\s*([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)\s+(\d+)\s(\s*)(.*)$')
agg = collections.Counter(); cur = None; tot = 0
with open(mp, errors='replace') as f:
    next(f)
    for line in f:
        m = line_re.match(line)
        if not m: continue
        size, indent, rest = int(m.group(3), 16), len(m.group(5)), m.group(6)
        if indent == 0: cur = rest; continue
        if cur != sect or indent != 8 or ':(' not in rest: continue
        path = rest.rsplit(':(', 1)[0]; tot += size
        for p in prefixes:
            if path.startswith(p): agg[p] += size; break
        else: agg['その他'] += size
print(f'# {sect} total {tot/1e6:.2f} MB')
for k, v in agg.most_common(): print(f'{v/1e6:8.2f}  {k}')
