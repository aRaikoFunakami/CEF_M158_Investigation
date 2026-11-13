#!/bin/bash
# arm64 編: arm64 ネイティブの実行用コンテナを作って計測環境を整える(ホストで実行)。
#   tools/a64run.sh up   <name> <cpus> <memory> <build...>   コンテナを作り、指定ビルドをローカルディスクへコピーし、計測環境を起動
#   tools/a64run.sh exec <name> <script>                     スクリプトをコンテナ内で実行(出力は標準出力)
#   tools/a64run.sh down <name>                              停止して削除
# ホストの a64/fp を /mnt/fp にマウントする。tools は毎回 tools/fp からコピーする。
# ビルドはマウント越しに動かすとファイル由来のページの扱いが変わりうるので、コンテナのローカルディスク(/root/fp/builds)へコピーして使う。
# 結果(results)はマウント先 /mnt/fp/results に直接書く(ホストの a64/fp/results)。
H=/Users/raiko/work/chromium
cmd=$1; name=$2
case $cmd in
up)
  cpus=$3; mem=$4; shift 4
  rm -rf $H/a64/fp/tools && cp -R $H/tools/fp $H/a64/fp/tools
  container run -d --name $name --arch arm64 -c $cpus -m $mem -v $H/a64/fp:/mnt/fp fp-a64-runtime:1 sleep infinity >/dev/null || exit 1
  container exec -i $name bash -s "$@" <<'IN'
set -e
mkdir -p /root/fp/builds; ln -sfn /mnt/fp/tools /root/fp/tools; ln -sfn /mnt/fp/results /root/fp/results
for b in "$@"; do cp -a /mnt/fp/builds/$b /root/fp/builds/$b; done
# 計測用 cgroup(logs/174 と同じ手順)
cd /sys/fs/cgroup; mkdir -p main fpmeas; for p in $(cat cgroup.procs); do echo $p > main/cgroup.procs 2>/dev/null || true; done; echo "+memory" > cgroup.subtree_control
source /root/fp/tools/env.sh >/dev/null 2>&1 || true
echo "== $(hostname) $(uname -m) nproc=$(nproc) $(grep MemTotal /proc/meminfo) builds=$(ls /root/fp/builds | tr '\n' ' ') cgroup=$(cat /sys/fs/cgroup/cgroup.subtree_control)"
IN
  ;;
exec) container exec -i $name bash -l < "$3" ;;
down) container stop $name >/dev/null 2>&1; container delete $name >/dev/null 2>&1; echo "down $name" ;;
esac
