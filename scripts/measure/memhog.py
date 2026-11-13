#!/usr/bin/env python3
"""memhog.py <MiB> : 指定量の匿名メモリを確保して全ページに書き込み、そのまま常駐する(空きメモリを減らす実験用)。
計測用 cgroup(fpmeas)の外で動かすこと(ブラウザの計測値に混ざらないように)。"""
import sys, time, mmap
n = int(sys.argv[1]) * 1048576
m = mmap.mmap(-1, n, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS)
for i in range(0, n, 4096): m[i] = 1
print(f'hog {n >> 20} MiB resident', flush=True)
while True: time.sleep(3600)
