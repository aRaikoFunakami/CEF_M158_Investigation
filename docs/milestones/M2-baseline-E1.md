# M2: 基準ビルド E1(CEF 既定のリリースビルド)

完了: 2026-11-11 18:05 JST。ログ: logs/125〜142。

## ビルド

| 項目 | 値 |
|---|---|
| ツリー | Chromium 158.0.8127.18 + CEF 8127(`6ee3fb965`) |
| 引数 | CEF 既定 + `is_official_build=true`、シンボルなし、`proprietary_codecs=true`、`ffmpeg_branding="Chrome"`、`use_sysroot=true`、`use_siso=false`(`logs/results/` の E1-args.gn) |
| ターゲット | `cefsimple`、`cefclient` |
| ビルドツール | ninja(siso は停止するため切り替え) |
| 所要 | 2 時間 26 分(59,810 ステップ、停止 0 回、エラー 0 件) |

### ビルドで起きたこと

- logs/125(siso): 開始 7 分で停止。停止検知(fpbuild)が 3 時間 45 分見逃した。siso 本体が停止中も空回りで CPU を使い、それを進捗と誤認したため。
- 対策: (1) fpbuild の進捗判定を「siso / ninja 以外の作業プロセスが動いたか」に変更(logs/128 で偽 siso を使って試験)。(2) siso をやめて ninja でビルド(`use_siso=false`)。
- siso が止まる根本原因(spawn-helper の子がゾンビのまま回収されない)は未特定。Chromium 編の A〜D は siso で完走しているので「ときどき止まる」。

## サイズ

| 項目 | E1(CEF、158) | 参考: A(`chrome`、159) |
|---|---|---|
| strip 後の本体 | **299.6MB**(`libcef.so` 298.8 + `cefsimple` 0.8) | 309.8MB |
| text / data | 285.3 / 14.3MB | 296.1 / 13.7MB |
| 配布物合計(ja + en-US) | **377.5MB** | 389.4MB |
| 配布物合計(全ロケール) | 428.0MB | 439.9MB |

配布物の内訳: `resources.pak` 25.8、`libVkLayer_khronos_validation.so` 27.3、`icudtl.dat` 10.8、`libvk_swiftshader.so` 6.0、`chrome_crashpad_handler` 2.5、ロケール全部 52.0(220 ファイル)。

CEF 既定は `chrome` より約 10MB 小さいだけで、`//chrome` 層をほぼ丸ごと含む。`content_shell`(A' 211.9MB)との差 約 88MB が「Chrome ランタイムの重さ」。

### `libcef.so` のシンボル内訳(合計 285.3MB、上位)

| 名前空間 | MB | 備考 |
|---|---|---|
| (名前空間なしの C++) | 41.2 | `//chrome` 層の `Browser`、`Profile` など。`content_shell` にはほぼ無い |
| blink | 40.1 | |
| v8 | 26.8 | |
| base | 11.5 | |
| rust | 8.6 | |
| content | 8.3 | |
| mojo | 5.8 | |
| extensions | 4.8 | CEF が無条件に依存 |
| net | 4.1 | |
| webrtc | 3.9 | |
| autofill | 3.1 | |
| tint + dawn | 4.9 | WebGPU(不要) |
| perfetto | 2.5 | |
| tflite + xnn | 2.9 | |
| optimization_guide / web_app / safe_browsing / glic | 1.0〜1.6 ずつ | |

## 動作確認(Alloy スタイル、`cefsimple --use-alloy-style`)

| 項目 | 結果 |
|---|---|
| 機能検出 | 合格 |
| Service Worker | 合格 |
| WebSocket | 合格 |
| MP4(H.264 + AAC) | 合格 |
| MSE | 合格 |
| EME(ClearKey) | 合格 |
| YouTube 1080p | 合格(AV1 + Opus、1920x1080@60、コマ落ち 0) |

スクリーンショット: `logs/screenshots/E1-func-*.png`。Chrome の UI(タブ、アドレスバー)は出ず、タイトルバーだけの窓になる。

### コーデックと DRM(ユーザー指示で確認、logs/135、140)

- ビルド引数の実効値: `proprietary_codecs=true`、`ffmpeg_branding="Chrome"`、`enable_widevine=true`、`enable_library_cdms=true`、`enable_av1_decoder=true`、`enable_dav1d_decoder=true`、`media_use_ffmpeg=true`、`media_use_libvpx=true`、`enable_mse_mpeg2ts_stream_parser=true`、`enable_hls_demuxer=true`。
- 実機: H.264(Main / High)、AAC(LC / HE)、VP8、VP9、AV1、Opus、Vorbis、MP3、FLAC、MPEG-2 TS(MSE)はすべて対応。HEVC、AC-3、E-AC-3 は非対応(`chrome` の Linux 版と同じ)。
- Widevine: CDM は同梱されない(`bundle_widevine_cdm=false`)。初回起動中にコンポーネント更新で取得され(4.10.3112.0、21MB、プロファイル内)、**再起動後に使える**(`com.widevine.alpha` で `MediaKeys` 作成まで確認)。初回起動中は `NotSupportedError`。
  - TV 向けでは CDM を同梱するか、初回起動後に再起動する運用が要る。配布物サイズに 21MB 加わる点に注意。
- 補足: CEF の配布バイナリ(公式ビルド)は H.264 / AAC を含まないが、今回は自前ビルドで有効にしている。

### 計測スクリプトの不具合(修正済み)

最初の 2 回は YouTube だけ不合格になった。原因は計測側にあった。

- この環境(Rosetta)では CEF プロセスの `/proc/<pid>/exe` が `/run/rosetta/rosetta` を指す。`measure.py` は exe でプロセスを特定していたため、CEF のプロセスを 1 つも見つけられなかった(kill できない、PSS も 0 になる)。
- その結果、前の試験のブラウザが残ったまま次が起動し、9222 番ポートを古いブラウザが握り続け、試験が古いブラウザに対して走っていた。
- 修正: `argv[0]` でも照合する。起動前にポートの解放を待つ。修正後は 7 項目すべて合格(logs/139)。
- 1 回目の不合格(古いブラウザが無い状態)の原因は確定していない。YouTube 側の一時的なエラーの可能性がある(Chromium 編 D3c でも 3 回中 1 回出た)。M5 のメモリ計測(3 回)で再度確認する。

## 計画への反映

- E2(M3)は `out/E2` に別ビルド。Chromium 編 B で `chrome` に通った 17 フラグは CEF でも `gn gen` を通過(36,840 ターゲット、E1 より 262 少ない)。logs/141 でビルド中。
- E3(M4)の狙い: 名前空間なしの 41MB(`//chrome` 層)、extensions 4.8MB、WebRTC 3.9MB、autofill 3.1MB、Dawn / Tint 4.9MB。CEF 側のアサーション(印刷プレビュー、Views、Widevine)と無条件依存(PDF、印刷、拡張機能)が壁になる。
- 以後のビルドはすべて ninja + fpbuild。
