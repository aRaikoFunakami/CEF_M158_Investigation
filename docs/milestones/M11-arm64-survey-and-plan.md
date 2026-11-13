# M11: arm64 編の調査と計画(CEF 第 3 期)

作成: 2026-11-12 23:25 JST。ログ: logs/400〜410。

## きっかけ(2026-11-12 のユーザー指示)

1. arm64 向けにクロスコンパイルし、CEF だけに集中して、ここまでやった削減を適用して ROM サイズをどこまで減らせるか確認する。Chromium(`content_shell`)はこれ以上追わない。
2. ROM 削減が終わったら、https://www.youtube.com/watch?v=aqz-KE-bpKQ を再生し、削減前と削減後で RAM 消費を比べる。RAM 消費が CPU の数や残りメモリ量に依存するのか、挙動とソースコードを調べて確認する。`--enable-low-end-device-mode` の ON / OFF での RAM の違いも確認する。全ログを Qiita 用に残す。
3. Chromium ベースの Cobalt(YouTube の TV 向けブラウザ)のメモリ削減ノウハウ(添付 PDF「Cobalt 27 メモリチューニング一覧」)のうち、まだ取り組んでいないものがあれば適用を検討する。

## 環境(logs/400〜404)

- ホスト: Apple M3 Ultra、32 コア、256GB。
- **ビルド**: これまでと同じ amd64 コンテナ(`chrome-build`、Rosetta、24 CPU / 64GB)で `target_cpu="arm64"` のクロスコンパイル。arm64 用 sysroot(Debian bullseye、235MB)を `build/linux/sysroot_scripts/install-sysroot.py --arch=arm64` で導入。clang には aarch64 用のランタイムが同梱されている。Rust の標準ライブラリはソースからビルドされるので追加不要。
- **実行**: arm64 ネイティブのコンテナ(Apple Container、`--arch arm64`)。Rosetta を通さないので、x64 編より実機に近い値になる。イメージ `fp-a64-runtime:1`(`a64/runtime-image/Dockerfile`、Ubuntu 24.04 + Xvfb / openbox / 実行時ライブラリ / フォント)。
- 起動ごとに CPU 数とメモリ量を変えられる(`tools/a64run.sh up <名前> <CPU 数> <メモリ>`)。Apple Container はコンテナごとに軽量 VM を作るので、`/proc/meminfo` の MemTotal と `nproc` がそのまま変わる(Chromium が見る値も変わる)。
  - 注意: `-c 4` で起動すると `nproc` が 5 になった(logs/404 の試行)。CPU 数の実験では `nproc` の実測値を記録する。
- 成果物はホストの `a64/fp/builds/` 経由で渡し、コンテナのローカルディスクにコピーしてから起動する(マウント越しだとファイル由来のページの扱いが変わりうるため)。

## ビルドの構成

| 名前 | ソース | args | 位置づけ |
|---|---|---|---|
| G0 | `/root/cef2`(CEF のパッチだけ。logs/400 で復元。CEF の patcher で 117 個適用) | E1 と同じ + `target_cpu="arm64"` | arm64 の削減前(CEF 既定) |
| G1 | `/root/cef`(第 1・2 期の全パッチ = F4b のソース) | F4b と同じ + `target_cpu="arm64"` | 第 2 期までの削減をそのまま arm64 に適用 |
| G2 以降 | G1 + Cobalt 由来の追加項目 | | M13 で決める |

- 両方とも `gn gen` は通過(logs/401)。G1 83,874 ステップ、G0 97,046 ステップ。並行で流し、G0 は nice 10。
- arm64 の既定値で x64 と違うもの: `arm_control_flow_integrity="standard"`(BTI / PAC。x64 の CFI に当たるが別物で、arm64 でも既定で有効)。G0 / G1 とも既定のまま。
- x64 で効いた CFI 無効化(`is_cfi=false`)は arm64 では元々無効なので効果なし。

## 計測方法の追加(logs/410)

`tools/fp/ytmem.py`: YouTube(上記 URL)を再生し、再生開始から 120 秒まで 10 秒ごとに標本を取る。

- 全プロセスの PSS(anon / file / shmem)、プロセス種別ごとの PSS。
- 専用 cgroup の anon + shmem(回収できない RAM)、`memory.peak`(ピーク)。
- YouTube プレーヤの詳細統計(`getStatsForNerds()`): コーデック、解像度、バッファ量。`<video>.buffered` から先読み秒数。
- `performance.memory.jsHeapSizeLimit`(V8 のヒープ上限)、`navigator.deviceMemory`、`navigator.hardwareConcurrency`。
- 再生 60 秒以降の標本の中央値を「再生中」の値とする。有効な回(実際に再生が進んでいた回)が 3 回集まるまで繰り返す。
- 試行(x64 の F4b、1 回、40 秒): コーデックは **AV1(av01.0.09M.08)1080p60 + Opus**。再生中 PSS 1,505MiB、cgroup の回収不可 1,336MiB、先読み 19.6 秒。

## 調査: RAM 消費は何に依存するか(ソース、logs/405〜409)

### 1. 低メモリ端末モード(`--enable-low-end-device-mode`)

判定(`base/system/sys_info.cc`):

- `--enable-low-end-device-mode` があれば低メモリ端末。`--disable-low-end-device-mode` があれば違う。
- どちらもなければ、**物理メモリが閾値以下なら自動で低メモリ端末**になる。閾値は Linux デスクトップで **2048MB**(`base/features.cc`。Android と iOS は 1024MB)。**2GB 以下の TV ではフラグなしで自動的に ON になる。**
- フラグで ON にすると、`SysInfo::AmountOfTotalPhysicalMemory()` が **512MB に見せかけられる**(`kSimulatedMemoryForEnableLowEndDeviceMode`)。物理メモリ量から決まる値(下の 2)も全部 512MB 相当になる。

ON で変わるもの(Linux で効くもの。Android 専用の分岐は除く):

| 箇所 | 通常 | 低メモリ端末 |
|---|---|---|
| MSE のバッファ上限(`media/base/demuxer_memory_limit_default.cc`) | 映像 150MB + 音声 12MB | 映像 30MB + 音声 2MB |
| V8 | | `--optimize-for-size`(`content/renderer/render_process_impl.cc`) |
| 画像デコードキャッシュ(`cc/tiles/image_decode_cache_utils.cc`) | 128MB(4GiB 以上は 256MB) | 32MB |
| Skia のリソースキャッシュ(`gpu/config/skia_limits.cc`) | 96MB(4GiB 以上は 256MB) | 48MB、グリフキャッシュも縮小 |
| discardable メモリの上限 | 512MB | 64MB(1/8) |
| ステージングバッファ | 32MB | 8MB |
| GPU のプログラムキャッシュ | 6MB(デスクトップ) | 128KB |
| MSAA のサンプル数 | 8(高 DPI 以外) | 4 |
| 合成 | | `translateZ(0)` など「自明な 3D 変換」を合成レイヤにしない |
| メディア | | 非表示のメディアプレーヤを積極的に解放する |

### 2. 物理メモリ量(起動時に一度だけ読む)

| 箇所 | 依存のしかた |
|---|---|
| V8 のヒープ上限(`gin/isolate_holder.cc` → `ResourceConstraints::ConfigureDefaults`) | 旧世代は物理メモリの 1/2(64bit、上限 4GB)、新世代も物理メモリから決まる |
| 画像デコードキャッシュ | 4GiB 以上で 128 → 256MB |
| Skia のリソースキャッシュ | 4GiB 以上で 96 → 256MB |
| レンダラプロセス数の上限 | 物理メモリ / 2 / 85MB(3〜82 の範囲)。タブ 1 枚なら影響なし |
| 低メモリ端末の自動判定 | 2048MB 以下で ON |

### 3. 空きメモリ量(実行中の変化)

- **Linux では、Chromium は空きメモリの減少に反応しない**。システムのメモリ逼迫を判定する部品(`SystemMemoryPressureEvaluator::CreateDefaultSystemEvaluator`)は Linux では `nullptr`。Mac / Windows / Fuchsia にしかない。
- chrome 層には freedesktop の low-memory-monitor(D-Bus)を使う判定があるが、機能 `LinuxLowMemoryMonitor` は既定で無効で、デーモンも要る。
- Cobalt はこれを自前の `EnableCobaltMemoryPressureEvaluator`(匿名 RSS が予算の 85% / 95% で MODERATE / CRITICAL を通知)で補っている。PDF の 3 ページ目。
- つまり、空きメモリが少なくても多くても、起動後の動作は変わらない見込み。変わるのは起動時の「総物理メモリ量」だけ。

### 4. CPU の数

| 箇所 | 依存のしかた |
|---|---|
| スレッドプール(`base/task/thread_pool/thread_pool_instance.cc`) | フォアグラウンドのワーカー数 = max(3, CPU 数 − 1)。V8 のワーカー数もこれに従う(`gin/v8_platform.cc`) |
| ラスタスレッド(`content/browser/gpu/compositor_util.cc`) | CPU 数 / 2(Linux)。Cobalt の Android 版は `--num-raster-threads=2` に固定 |
| 動画デコードスレッド(`media/base/video_decoder.cc`) | min(コーデックの希望数, CPU 数)。AV1(dav1d)は 1080p で frame_threads × (tile_threads + 1)。VP9 は 1080p で 4。`--video-threads=N` で上書きできる |

- スレッドが増えると、スタックやスレッドごとのアロケータのキャッシュの分だけ RAM が増える。dav1d はフレーム並列で同時に複数フレームを持つので、デコード用のバッファも増える可能性がある。

### 調査から立てた仮説(M14、M15 で検証)

1. 削減前(G0)と削減後(G1)で、再生中の RAM の差は起動時の差(拡張機能のプロセスなど)と同程度で、動画の RAM 自体は変わらない。
2. `--enable-low-end-device-mode` で再生中の RAM が大きく減る(MSE のバッファ上限 162 → 32MB、V8、各キャッシュ)。YouTube の先読み秒数も減る。
3. 総メモリ量: 2GB 以下で自動的に低メモリ端末になり RAM が下がる。2GB 超〜4GB 未満と 4GB 以上でも、キャッシュ上限の分だけ差が出うる。
4. 空きメモリ量(他のプロセスが使っている量)では変わらない。
5. CPU 数: スレッド数とデコーダの並列度に応じて RAM が増える。

## 計画

| # | マイルストーン | 内容 |
|---|---|---|
| M11 | 調査と計画 | このファイル |
| M12 | arm64 ビルド G0 / G1 | サイズ、マップ。x64 との比較 |
| M13 | Cobalt の未着手項目 | ROM: `enable_hls_demuxer`、`enable_hevc_parser_and_hw_decoder`、`enable_media_remoting(_rpc)`(パッチ)、`angle_enable_vulkan`(SwiftShader と両立しないので見積もりのみ)など。実行時: Cobalt の起動時既定フラグ一式を RAM で評価 |
| M14 | arm64 動作確認と RAM(削減前後、低メモリ端末モード) | G0 / G1 × low-end OFF / ON。動作確認 7 項目、スクリーンショット、起動時 RAM、YouTube 再生中の時系列 |
| M15 | CPU 数・メモリ量の依存 | G1 で CPU 数(2 / 4 / 8 / 16)、総メモリ(2 / 3 / 4 / 8GB)、空きメモリ(メモリを占有するプロセスを並走)を変えて YouTube を計測 |
| M16 | まとめ | 一覧、Qiita 向けの材料 |

## Cobalt の資料との対応(未着手の候補)

資料と、資料が参照する Cobalt のソース(`cobalt/build/configs/common.gn`、`cobalt/app/cobalt_switch_defaults_starboard.cc`)を読んだ(web から取得)。

### ROM(ビルド設定)

| Cobalt の設定 | ここまでの状態 | 方針 |
|---|---|---|
| `include_transport_security_state_preload_list=false` | 適用済み(第 1 期) | |
| `icu_use_data_file=true` | 既定で true | |
| `enable_remoting`、`enable_vr` / `openxr`、`use_dawn`、`webnn_use_tflite`、`build_tflite_with_xnnpack`、`generate_about_credits`、`rtc_include_dav1d_in_internal_decoder_factory`、`enable_backup_ref_ptr_*`、`enable_vectorized_html_scanning`、`enable_libaom`、`media_use_openh264` | 適用済み | |
| `enable_media_remoting` / `_rpc=false` | 第 2 期で試してリンクで失敗(`CastRemotingConnector` の参照が残る) | パッチを書いて再挑戦 |
| `enable_hls_demuxer=false` | 未適用(第 2 期では HLS を残した) | YouTube と HbbTV / Hybridcast は MPEG-DASH なので外す |
| `enable_hevc_parser_and_hw_decoder=false` | 未適用 | Linux の Chromium は HEVC をソフトウェアでデコードしない。ハードウェアデコード(VA-API)は外し済みなので外す |
| `angle_enable_vulkan=false` | 未適用 | SwiftShader(ANGLE の Vulkan バックエンド経由)と両立しない。実験に SwiftShader が要るので、効果はマップから見積もるだけにする |
| `enable_screen_capture=false` | Chromium 158 では GN 引数ではない | MediaStream 系は第 1 期で削除済み |
| `media_use_ffmpeg=false`、`media_use_libvpx=false`、`enable_dav1d_decoder=false` | 未適用 | Cobalt はデコードを Starboard(端末側)に任せている。こちらはソフトウェアデコードが要るので外さない(コーデックは残す方針) |
| `v8_use_external_startup_data=false` | 未適用 | V8 のスナップショットを本体に埋め込むだけで合計サイズは変わらない。対象外 |
| Evergreen の mmap 読み込み、LZ4 圧縮 | 対象外 | Cobalt の配布形式(Evergreen)固有。圧縮は UPX と同じ扱い(不要と指示あり) |

### RAM(起動時の既定フラグ。Starboard 版)

`--single-process`、`--no-zygote`、`--enable-low-end-device-mode`、`--disable-rgba-4444-textures`、`--hide-scrollbars`、`--js-flags=--no-decommit-pooled-pages --no-concurrent-marking`、`--enable-features=SmallerInterestArea,ReclaimPrepaintTilesWhenIdle,ReclaimOldPrepaintTiles,...`、`--gpu-rasterization-msaa-sample-count=4`。Android 版は `--num-raster-threads=2`。

→ M14 / M15 で「Cobalt の既定フラグ一式」として RAM を比較する(個別の寄与は低メモリ端末モードと単一プロセスを中心に切り分ける)。

## リスク

- クロスコンパイルで、x64 では通っていたパッチが arm64 固有のコードで通らない可能性(例: arm64 だけで使われるソース)。
- CEF の Chrome ランタイムでの `--single-process` は非サポート。落ちたら記録する。
- arm64 の Linux 向け Widevine CDM は配布されていない。EME の確認は ClearKey で行う(x64 と同じ)。
- ネイティブ arm64 でも、実機の TV(GPU、ハードウェアデコーダ、少ない CPU)とは条件が違う。SwiftShader の描画とソフトウェアデコードの分、RAM と CPU は実機より大きく出る。
