#!/bin/bash
# arm64 編: 1 つの実験条件(CPU 数、メモリ量)でコンテナを起動し、コンテナ内スクリプトを実行して片付ける(ホストで実行)。
#   tools/a64exp.sh <条件名> <CPU 数> <メモリ> <コンテナ内スクリプト> <ビルド名...>
# コンテナ内スクリプトには環境変数 COND(条件名)を渡す。結果 JSON はホストの a64/fp/results/ に出る。
H=/Users/raiko/work/chromium; cond=$1; cpus=$2; mem=$3; scr=$4; shift 4
name=a64-$(echo $cond | tr -c 'a-zA-Z0-9-\n' '-' | cut -c1-40)
echo "### $(date '+%F %T') cond=$cond cpus=$cpus mem=$mem builds=$*"
$H/tools/a64run.sh up $name $cpus $mem "$@" || { echo "UP FAILED"; exit 1; }
container exec $name bash -c 'echo "lscpu: $(lscpu | grep -E "^CPU\(s\)|Model name" | tr -s " " | tr "\n" " ")"; free -m | sed -n 2p'
{ echo "export COND='$cond'"; cat $scr; } > $H/a64/.tmp-a64exp-$$.sh
container exec -i $name bash -l < $H/a64/.tmp-a64exp-$$.sh; rc=$?; rm -f $H/a64/.tmp-a64exp-$$.sh
mkdir -p $H/logs/screenshots; container exec $name bash -c 'cd /root/fp && ls results/shots/*.png 2>/dev/null | wc -l'
$H/tools/a64run.sh down $name
echo "### $(date '+%F %T') rc=$rc"
