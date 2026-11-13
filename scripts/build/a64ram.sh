#!/bin/bash
# arm64 編 RAM 計測の 1 条件(ホストで実行): コンテナ(CPU 数、メモリ)を起動し、ytmem.py を「ビルド:名前:追加引数」ごとに実行する。
#   tools/a64ram.sh <条件名> <CPU> <メモリ> <runs> <hogMiB|0> "<build>|<label>|<args>[|<ytmem のオプション>]" ...
# ytmem は --warm(温めたプロファイルを毎回コピー、logs/426)で動かす。
# hogMiB > 0 のときは計測前に memhog.py で匿名メモリを確保して常駐させ、空きメモリを減らす(計測 cgroup の外)。
H=/Users/raiko/work/chromium; cond=$1; cpus=$2; mem=$3; runs=$4; hog=$5; shift 5
builds=$(for v in "$@"; do echo "${v%%|*}"; done | sort -u | tr '\n' ' ')
inner=$H/a64/.tmp-a64ram-$$.sh
{ echo 'cd /root/fp'
  [ "$hog" != 0 ] && echo "nohup python3 tools/memhog.py $hog > /root/fp/memhog.log 2>&1 & sleep 20; cat /root/fp/memhog.log; free -m | sed -n 2p"
  for v in "$@"; do b=${v%%|*}; r=${v#*|}; l=${r%%|*}; a=${r#*|}; o=''
    case "$a" in *'|'*) o=${a#*|}; a=${a%%|*};; esac   # 4 つ目の欄は ytmem.py への追加オプション(--limit など、M17)
    echo "echo '## $cond $l build=$b args=$a' \$(date -u +%T)"
    echo "python3 tools/ytmem.py '$cond-$l' /root/fp/builds/$b/cefsimple --runs $runs --warm $o --args='$a' 2>&1 | grep -E '^run|^ENV|^SUMMARY|Error|error' | cut -c1-2500"
  done
  [ "$hog" != 0 ] && echo "free -m | sed -n 2p; pkill -f memhog.py"
} > $inner
cat $inner | sed 's/^/# inner: /'
$H/tools/a64exp.sh $cond $cpus $mem $inner $builds
rm -f $inner
