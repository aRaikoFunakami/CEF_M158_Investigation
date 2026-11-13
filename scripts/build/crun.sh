#!/bin/bash
# 使い方: tools/crun.sh logs/NN-name.sh
# ホスト側のスクリプトをコンテナ chrome-build 内で実行し、出力を同名の .log に保存する。
s="$1"; l="${s%.sh}.log"
{ echo "### $(date '+%F %T') $s"; container exec -i chrome-build bash -l < "$s" 2>&1; echo "### rc=$? $(date '+%F %T')"; } | tee "$l"
