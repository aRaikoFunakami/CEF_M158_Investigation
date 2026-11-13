# M13: G2 = G1 + Cobalt の ROM 削減ノウハウのうち未適用のもの

作成: 2026-11-13 05:15 JST。ログ: logs/414、415、420〜422。

## 何を足したか

添付資料(Cobalt 27 のメモリ調整、`cobalt/build/configs/common.gn` など)の ROM 向け設定を、第 1・2 期で適用済みのものと突き合わせた(対応表は M11)。未適用で TV ブラウザに使えるものは次の 4 引数だけだった(logs/414 で 158 に存在すること、現在値がすべて true であることを確認)。

| GN 引数 | 中身 | 連動して false になるもの |
|---|---|---|
| `enable_media_remoting` / `enable_media_remoting_rpc` | Cast ミラーリング中に動画だけを受信機で再生する仕組み | |
| `enable_hls_demuxer` | `<video src="*.m3u8">` を Chromium 自身で再生する HLS 実装 | `enable_mse_mpeg2ts_stream_parser`(MSE の MPEG2-TS) |
| `enable_hevc_parser_and_hw_decoder` | HEVC のパーサとハードウェアデコーダ連携 | `enable_platform_hevc` |

- `enable_media_remoting=false` は第 2 期(logs/191)でリンクに失敗して見送っていた。`chrome/browser/media` の 2 ファイルが無条件に `CastRemotingConnector` を参照していたためで、`tools/fp/g2_patch.py` で `BUILDFLAG(ENABLE_MEDIA_REMOTING)` のガードを足して通した。
- HLS: YouTube は MSE で再生するので使わない。ハイブリッドキャストや HbbTV のアプリが HLS を使う場合は、hls.js などで MSE に流し込む必要がある。MSE の MPEG2-TS も消えるので、hls.js 側で fMP4 に変換する(hls.js は既定で変換する)。
- HEVC: Linux のソフトウェアデコードでは元々 HEVC を扱わない(caps で `hevc: false`)。TV 実機でハードウェアデコーダを使うなら残す。

適用しなかったもの:

- `angle_enable_vulkan=false`: 実験環境では ANGLE → Vulkan → SwiftShader の経路で描画しているので外せない。map から見積もった寄与は ANGLE の Vulkan バックエンド約 1.1MB(logs/420)。GL ES ドライバを持つ TV 実機なら外せる。
- `enable_screen_capture`: 158 には存在しない引数。
- コーデック削除(`enable_dav1d_decoder=false` など): Cobalt はハードウェアデコーダ前提だが、この実験はソフトウェアデコードで YouTube(AV1)を再生しているので外せない。
- `v8_use_external_startup_data=false`、Evergreen の mmap / LZ4 圧縮: 配布形態が違うので対象外。
- 実行時フラグ(`--single-process`、`--enable-low-end-device-mode` ほか)は ROM には効かない。M15 で RAM への効果を測る。

## ビルド(logs/415)

`out/G1` の増分ビルド(G1 の成果物は保存済み)。8,878 ステップ、失敗 0、54 分。

## サイズ

| | strip 後(`libcef.so` + `cefsimple`) | 配布物(ja + en-US) |
|---|---|---|
| G1 | 187.2MB | 229.1MB |
| G2 | **186.7MB**(−0.5) | 228.6MB |
| G2-dist(F4b-dist と同じトリム + ICU 軽量版) | 186.7MB | **219.6MB** |
| G2-tv(G2-dist − SwiftShader 一式) | 186.7MB | **196.0MB** |

- 4 引数の効果は −0.5MB。map の差は `media/formats` −0.16、`media/filters` −0.09、`media/parsers` −0.04、`media/remoting` −0.03MB(logs/420)。Cobalt がこれらを外すのは ROM よりも、HLS や TS を扱わない端末で攻撃面とコードを減らす意味が大きいと思われる。第 1・2 期でより大きな機能を外し終えていたので、残っていたのは小物だけだった。
- G2-dist のトリム内容: `chrome_200_percent.pak`、`snapshot_blob.bin`、`chrome_crashpad_handler`、テスト用 ICD(`libVkICD_mock_icd.so`)を外し、`icudtl.dat` を cast 用(5.2MB)に差し替え。
- G2-tv は SwiftShader(arm64 では LLVM 入りで 22.8MB、M12 参照)と `vk_swiftshader_icd.json`、`libvulkan.so.1` も外したもの。GPU のある実機を想定した形で、この実験環境(GPU なし)では WebGL が使えずソフトウェア描画になる。

## 動作確認(logs/422)

arm64 ネイティブ、8 CPU、8GB。G0 のビルドと並行。

| | 7 項目 | i18n | 否定確認 | WebGL | YouTube 1080p60 の 10 秒間のコマ落ち |
|---|---|---|---|---|---|
| G2 | 7/7 | OK | OK | あり | 688 / 2,212 フレーム |
| G2-dist | 7/7 | 日本語の単語分割だけ 1 文字単位(ICU 軽量版。x64 と同じ) | OK | あり | — |
| G2-tv | 7/7 | 同上 | OK | **なし** | **0** / 2,222 フレーム |

- G2-tv では GPU プロセスが ANGLE の Vulkan 初期化に失敗し(`Internal Vulkan error (-3)`)、Chromium はソフトウェア合成(Skia の CPU 描画)に切り替わる。WebGL / WebGL2 は使えなくなるが、動画再生とページ表示は通る。
- **SwiftShader 経由の描画は重い**。同じ CPU 数でも、SwiftShader で GPU を模擬する経路(G2)はコマ落ちが 3 割に達し、ソフトウェア合成(G2-tv)は 0 だった。SwiftShader は GL ES の命令を 1 つずつ Vulkan → CPU で実行するので、動画フレームの合成だけならソフトウェア合成のほうが軽い。RAM の計測(M14、M15)は SwiftShader ありの構成で行うので、CPU 依存の項目(コマ落ち)はこの分だけ実機より悪く出る。

起動時 RAM(caps.html、30 秒後、3 回の中央値、MiB):

| | 回収不可 | ファイル由来 | 本体 RSS / PSS | プロセス数 |
|---|---|---|---|---|
| G1 | 128.7 | 159.2 | 441.8 / 173.6 | 8 |
| G2 | 129.2 | 159.5 | 440.9 / 173.9 | 8 |
| G2-dist | 128.8 | 159.4 | 441.4 / 173.9 | 8 |
| G2-tv | **101.8** | **141.0** | 430.3 / 168.8 | 8 |

- G1 → G2 → G2-dist はほぼ同じ(ROM の差が 0.5MB と小さく、配布物トリムは起動時に読まないファイルが中心)。
- G2-tv は回収不可が −27MiB、ファイル由来が −18MiB。GPU プロセスで SwiftShader(LLVM の JIT とシェーダのキャッシュ、Vulkan の作業領域)を持たなくなった分。

### arm64 の ROM の到達点

| | strip 後 | 配布物(ja + en-US) |
|---|---|---|
| G2(本体の最小) | 186.7MB | 228.6MB |
| G2-dist(x64 の F4b-dist と同じ形) | 186.7MB | **219.6MB** |
| G2-tv(GPU のある実機向け) | 186.7MB | **196.0MB** |

G0(削減前)との比較は G0 のビルド完了後に追記する。
