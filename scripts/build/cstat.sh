#!/bin/bash
# 使い方: tools/cstat.sh        コンテナ内の fpbuild.py の状態(毎分更新)と停止検知の履歴を表示する。
container exec chrome-build bash -c 'date -u "+now %F %T UTC"; for f in /root/fp/*.status; do [ -f "$f" ] && echo "$(basename $f): $(cat $f)"; done; cat /root/fp/*.stalls 2>/dev/null; uptime'
