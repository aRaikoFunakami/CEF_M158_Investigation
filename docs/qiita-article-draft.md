---
title: CEF 158 をローエンド機向けに削る: ROM と RAM はどこまで減らせるか
tags: CEF Chromium 組み込み メモリ削減 Linux
---

# はじめに

## CEF とは

CEF(Chromium Embedded Framework)は、Chromium をほかのアプリケーションに組み込むためのフレームワークです。プロジェクトの README は、用途として次を挙げています。

- 既存のネイティブアプリに Web ブラウザの部品を埋め込む
- UI を Web 技術で作る、薄いネイティブアプリ(シェル)を作る
- 独自の描画系を持つアプリで、Web ページを画面外に描画する(オフスクリーン描画)
- Web アプリの自動テストのホストにする

同じ README は、Chromium プロジェクトが主に Chrome の開発を対象にしているのに対し、CEF は組み込み用途を対象にしていると説明しています。CEF は Chromium に C / C++ の API(`include/` 以下のヘッダ)をかぶせ、ウィンドウの生成、ページ遷移の通知、JavaScript とネイティブコードのやり取り、通信の横取り、オフスクリーン描画などをアプリから扱えるようにしています。TV やセットトップボックスのように、自社のアプリの中で Web コンテンツを表示したい機器では、この API が必要になります。

## CEF が大きくなった理由

CEF は長く、Chromium の content 層(プロセスの分割やページ遷移など、ブラウザの土台になる層)の上に直接載っていました。Chrome のブラウザ機能(//chrome 層)は使わない構成です。

CEF のコミット履歴では、この構成が次のように変わっています。

| 日付 | コミット | 内容 |
|---|---|---|
| 2020-06-24 | `117499421` | Chrome ランタイム(//chrome 層の上で動く方式)の初期対応 |
| 2020-06-28 | `84f3ff2af` | 従来の方式を「Alloy ランタイム」と改名 |
| 2024-04-17 | `dca0435d2` | Chrome ランタイムの上で Alloy スタイルのブラウザとウィンドウに対応 |
| 2024-06-25 | `a461a8972` | Alloy ランタイムの起動経路(Alloy bootstrap)を削除。CEF の 6613 ブランチ(Chromium 128)以降に含まれる |

![CEF の構成](https://raw.githubusercontent.com/aRaikoFunakami/CEF_M158_Investigation/main/docs/images/fig1-cef-architecture.png)

その結果、現在の CEF は必ず //chrome 層の上で動きます。CEF 本体(libcef)は `ChromeMainDelegate`、`ChromeContentBrowserClient`、`ChromeContentRendererClient` などの //chrome のクラスを継承して作られており、設定や Cookie を保持する単位も Chrome の `Profile` です。libcef の 76 ファイルが `chrome/` 以下のヘッダを計 172 回 include しています。//chrome 層には自動入力、同期、パスワード管理、拡張機能、PDF ビューア、印刷、ブラウザの UI などが入っていて、組み込み用途で使わない機能もまとめてリンクされます。

## Alloy スタイルと Chrome スタイル

現在の CEF には、ウィンドウ(ブラウザ)ごとに選ぶ 2 つのスタイルがあります。`include/internal/cef_types_runtime.h` の説明は次のとおりです。

| スタイル | 内容 |
|---|---|
| Chrome スタイル | Chrome の UI とブラウザ機能をそのまま持つ(タブ、ツールバー、メニューなど) |
| Alloy スタイル | 既定のブラウザ機能は少ないが、アプリ向けのコールバックが多く、オフスクリーン描画に対応する |

どちらのスタイルも Chrome ランタイムの上で動きます。オフスクリーン描画は常に Alloy スタイルです。今回は、組み込み用途に近い Alloy スタイル(サンプルアプリ `cefsimple` を `--use-alloy-style` で起動)を対象にしました。

## 調査の目的

ローエンドの機器(TV など)に組み込んで Web 閲覧に使えるように、CEF の最新リリース版の ROM(配布物のサイズ)と RAM の使用量を、どこまで、どの方法で減らせるかを調べました。Chrome のブラウザ機能を外しても CEF の API と YouTube の再生が動くこと、を条件にしています。

# 結果

## ROM

| 環境 | 構成 | strip 後の実行ファイル | 配布物 |
|---|---|---|---|
| x64 | CEF 既定(E1) | 299.6MB | 377.5MB |
| x64 | 削減後(F4b-dist) | 191.2MB(−36.2%) | 206.6MB(−45.3%) |
| arm64 | CEF 既定(G0) | 275.1MB | 366.3MB |
| arm64 | 削減後(G2-dist) | 186.7MB(−32.1%) | 219.6MB(−40.0%) |
| arm64 | 削減後、GPU 搭載機向け(G2-tv) | 186.7MB(−32.1%) | 196.0MB(−46.5%) |

- 実行ファイルは `libcef.so` と `cefsimple` を strip した合計です。
- 配布物は、実行ファイルに `.pak`、ICU データ、V8 の起動用データ、ANGLE などの同梱ライブラリを足した合計です。ロケールは ja と en-US だけを数えています(全 220 ロケールでは +50.5MB)。Widevine CDM(約 21MB、初回起動時に取得)は含みません。
- G2-tv は、ソフトウェアの GPU(SwiftShader)を配布物から外したものです。GPU のある機器を前提にしています。

![ROM の推移](https://raw.githubusercontent.com/aRaikoFunakami/CEF_M158_Investigation/main/docs/images/fig2-rom-x64.png)

## RAM(arm64)

起動直後(ローカルのテストページを開いて 30 秒後、3 回の中央値):

| 構成 | 回収できない RAM | ファイル由来の RAM |
|---|---|---|
| CEF 既定(G0) | 160.5MiB | 228.7MiB |
| 削減後(G2-tv) | 101.8MiB(−36.6%) | 141.0MiB(−38.3%) |

YouTube の動画を再生している間(全プロセスの PSS、有効 2 回の中央値):

| 動画 | CEF 既定(G0) | G0 + 起動フラグ | 削減後(G2-tv) | G2-tv + 起動フラグ |
|---|---|---|---|---|
| H.264 1080p60 | 1,045.5MiB | 912.2MiB(−13%) | 759.3MiB(−27%) | **684.4MiB(−35%)** |
| AV1 4K60 | 1,509.5MiB | 1,348.7MiB(−11%) | 1,131.9MiB(−25%) | **1,005.5MiB(−33%)** |

起動フラグは `--single-process --no-zygote --enable-low-end-device-mode` の 3 つです。

![動画再生中の RAM](https://raw.githubusercontent.com/aRaikoFunakami/CEF_M158_Investigation/main/docs/images/fig3-ram-video.png)

ブラウザが使えるメモリに上限をかけ、120 秒間再生できるかを確かめた結果(起動フラグあり):

| 動画 | CEF 既定(G0) | 削減後(G2-tv) |
|---|---|---|
| H.264 1080p60 | 880MiB で再生できた(780MiB では強制終了) | 640MiB で再生できた |
| AV1 4K60 | 1,320MiB で再生できた | 980MiB で再生できた |

これは「この上限で再生できた」という確認で、再生できる最小値ではありません。上限はブラウザだけに割り当てた量で、機器の搭載 RAM ではありません。

RAM の値は、動画のデコードも描画も CPU で行う環境での測定です(詳細は「計測方法」)。ハードウェアデコーダのある機器では、デコード済みのフレームがドライバ側に置かれるので、ブラウザ側の値はこれより小さくなる見込みです(未計測)。

# 調査対象

| 対象 | 版 | 入手元 |
|---|---|---|
| CEF | 8127 ブランチ、コミット `6ee3fb965`("Update to Chromium version 158.0.8127.18"、2026-11-10) | https://github.com/chromiumembedded/cef |
| Chromium | 158.0.8127.18(タグ、コミット `6449d9f9a6`) | https://chromium.googlesource.com/chromium/src |
| 比較用の Chromium | 159.0.8143.0(`content_shell` と `chrome` の比較に使用) | 同上 |

調査を始めた 2026-11-10 の時点で、CEF の 8127 ブランチは Beta、Stable は 8078(Chromium 156)でした。Chromium 159 に対応した CEF はまだなかったので、8127 を使いました。

ソースは、`automate-git.py` の既定の手順だと Chromium の全履歴を取りにいくため、次の手順に分けて取得しました。

1. Chromium のタグ `158.0.8127.18` だけを `git fetch --depth=1` で取得する
2. `.gclient` に `--no-chromium-history` 相当の設定を書き、`gclient sync --no-history --nohooks` を実行する
3. `gclient runhooks` を実行する
4. CEF の `cef_create_projects.sh` を実行する(CEF のパッチが Chromium に当たる。474 ファイル)

Linux では `use_sysroot=true` にしないと、ビルドがシステムの `libpipewire-0.3` を要求して失敗しました。

# 調査環境

| 項目 | 内容 |
|---|---|
| ホスト | Mac Studio(Apple M3 Ultra、32 コア、256GB) |
| ビルド | Apple の `container` で動かす amd64 の Ubuntu 24.04(Rosetta、24 CPU / 64GB)。arm64 版は同じコンテナで `target_cpu="arm64"` のクロスコンパイル |
| x64 の計測 | ビルドと同じ amd64 コンテナ(Rosetta 上) |
| arm64 の計測 | arm64 のネイティブコンテナ(8 CPU / 8GB を基準に、CPU 数とメモリ量を変えて計測) |
| 画面 | Xvfb(1920x1080)。GPU はなく、描画は SwiftShader(CPU で動く GPU 実装) |

ビルド設定は `is_official_build=true`(配布用のリリースビルド)、シンボルなし、`proprietary_codecs=true`、`ffmpeg_branding="Chrome"`(H.264 と AAC を有効)です。Widevine(DRM)の対応も残しています。

ビルドには ninja を使いました(args に `use_siso=false`)。Chromium の既定のビルドツール siso は、このコンテナ上で子プロセスの回収待ちのまま止まることが 3 回あったためです。ビルドは、進捗が 300 秒止まったら強制終了して再実行するラッパー(`fpbuild.py`)で流しました。フルビルドの時間は、x64 の CEF 既定で 2 時間 26 分(59,810 ステップ)、arm64 の削減後(G1)で 4 時間 58 分(83,874 ステップ)でした。

# 計測方法

## ROM

`tools/fp/measure.py size` で、strip 後の実行ファイルと配布物の合計を測りました。単位は MB(10^6 バイト)です。

## RAM

RAM の単位は MiB(1024^2 バイト)で、次の値を使いました。

| 値 | 意味 |
|---|---|
| PSS | プロセスが使っているメモリを、共有している他のプロセスと按分した量。全プロセスの `/proc/<pid>/smaps_rollup` を合計した |
| 回収できない RAM | ブラウザを専用の cgroup に入れて起動し、`memory.stat` の anon + shmem を読んだ量。カーネルが捨てて読み直すことのできないメモリ |
| ファイル由来の RAM | 実行ファイルなどを読み込んだページ(`Pss_File`)。メモリが足りなくなるとカーネルが捨てて読み直せる |

起動直後の RAM は `startram.py` で、ローカルのテストページ(`caps.html`)を開いて 30 秒後に測りました。

YouTube の再生中の RAM は `ytmem.py` で、Big Buck Bunny 60fps(https://www.youtube.com/watch?v=aqz-KE-bpKQ)を 120 秒再生し、10 秒ごとに測りました。条件は次のとおりです。

- YouTube を 1 回開いたあとのプロファイル(キャッシュは削除し、Cookie などは残す)を毎回コピーして起動した。新しいプロファイルでは、YouTube が再生の途中で "Something went wrong" を出す回が約半数あったため
- 再生開始から 60 秒以降の値の中央値を 1 回の値とし、最後まで再生が進んだ回(有効な回)の中央値を構成の値とした
- コーデックは、ページが読み込まれる前に JavaScript の判定関数(`MediaSource.isTypeSupported` など)を差し替えて選ばせた。H.264 は AV1 / VP9 / HEVC を「非対応」と答えさせる。AV1 の 4K は、`navigator.mediaCapabilities.decodingInfo` に「AV1 は省電力で再生できる」と答えさせる(何もしないと YouTube は 4K に VP9 を選ぶ)
- メモリの上限は cgroup の `memory.max` で、ブラウザの全プロセスにかけた(スワップなし)

この環境の制約で、RAM の絶対値は実機より大きく出ます。

- 動画のデコードは CPU で行っている(AV1 は dav1d、H.264 は FFmpeg)。コンテナに GPU デバイスがないため。デコード済みのフレーム(1080p で約 134〜140MiB、4K で約 410〜540MiB)がブラウザ側のメモリに載る
- 描画も CPU(SwiftShader)で行っている
- x64 の値は Rosetta 上の測定で、回収できない RAM が arm64 より約 235MiB 大きく出た。x64 の RAM は構成間の差だけを見て、記事の RAM の数値は arm64 の値を使った

構成間の差は、この環境でも比較できます。

## 動作の確認

各構成で次の 7 項目を確認しました(`measure.py func`)。すべての構成が 7 項目とも通っています。

| 項目 | 確認方法 |
|---|---|
| 機能の検出 | テストページで主な Web API の有無を判定 |
| Service Worker | 登録と通信の横取り |
| WebSocket | ローカルのエコーサーバとの送受信 |
| MP4 | H.264 + AAC の動画の再生 |
| MSE | Shaka Player によるストリーミング再生 |
| EME | Clear Key による暗号化動画の再生 |
| YouTube | 1080p で再生が進むこと |

外した機能(印刷、PDF、プラグイン、拡張機能の API)を呼んでも落ちないことも、別のテスト(`f3_negtest.py`)で確認しました。

# ROM の削り方

削減は x64 で 2 段階に分けて行い、最後に同じ変更を arm64 に当てました。下の表は、効果の大きい順に並べたものです。値は配布物の削減量で、構成どうしの差から求めています。

| 削減の内容 | 方法 | 効果 | 失うもの |
|---|---|---|---|
| Vulkan の検証レイヤを同梱しない | GN 引数 `dawn_enable_vulkan_validation_layers=false` | −27.3MB | 開発用の機能 |
| 再配置テーブルを RELR 形式にする | リンカオプション `-Wl,-z,pack-relative-relocs` | −25.6MB | なし(実行環境に glibc 2.36 以降が必要) |
| `resources.pak` を絞り込む | 配布時の後処理(`pakstrip.py`) | −24.7MB(25.6 → 0.9MB) | `chrome://` の全ページ、DevTools の画面、起動演出の音声(4.8MB) |
| サイズ優先の最適化 | GN 引数 `optimize_for_size=true`(`-Os`) | 約 −10MB(推定) | 速度への影響は未計測 |
| CFI を無効にする | GN 引数 `is_cfi=false` | 約 −14MB | 関数呼び出しの改ざん対策。arm64 では元々無効 |
| Blink のモジュールを 41 個外す | パッチ | −12.0MB | WebRTC、カメラとマイク、Bluetooth、USB、決済、通知、プッシュ通知、WebXR、センサーなど |
| 拡張機能を外す | GN 引数 + パッチ(Chromium 342 ファイル、CEF 13 ファイル) | −9.4MB | `chrome.*` 拡張 API、`chrome-extension://` |
| PDF、印刷プレビュー、印刷、プラグインを外す | GN 引数 + パッチ(Chromium 21 ファイル、CEF 9 ファイル) | −8.5MB | PDF の表示、`window.print()`、PrintToPDF |
| `chrome://` の WebUI の登録をやめる | パッチ(呼び出し 5 行の削除) | 約 −10MB(GN 引数 17 個の追加と合わせた値) | `chrome://` の全ページ |
| GN 引数で機能を外す(2 回、計 34 個) | args.gn | 実行ファイル −8.0MB と約 −4MB | CUPS、VR、リモート操作、WebNN、Kerberos、Wayland、GTK、VA-API など |
| Dawn(WebGPU)への参照を消す | パッチ 3 行 | −5.7MB | なし |
| ICU のデータを軽量版に差し替える | 配布時の差し替え | −5.6MB(10.8 → 5.2MB) | 日本語の単語分割が 1 文字単位になる |
| 配布物を整理する | 配布時の削除 | −3.2MB | 高解像度画面用の画像、クラッシュレポートの送信 |
| Alloy スタイル専用にする | パッチ 4 ファイル | −0.6MB | Chrome スタイルのウィンドウ |

推定と書いた値は、ほかの変更と同時に入れたため単独では測っていないものです。CFI の値は、同じ変更を content_shell(Chromium 159)に当てたときの実測です。効果には重なりがあるので、合計は全体の削減量と一致しません。

各段階の構成と変更点は次のとおりです(x64、配布物)。

| 構成 | 変更 | 配布物 | 前段との差 |
|---|---|---|---|
| E1 | CEF 既定 | 377.5MB | |
| E2 | GN 引数 17 個 | 342.0MB | −35.5MB |
| E3a | GN 引数 17 個(CFI 無効を含む) | 323.5MB | −18.5MB |
| E3b | Blink のモジュールを 41 個外す | 311.5MB | −12.0MB |
| F1a | RELR、Dawn への参照の削除 | 279.1MB | −32.4MB |
| F2 | GN 引数 17 個、WebUI の登録をやめる、`resources.pak` の絞り込み | 245.2MB | −33.9MB |
| F2b1 | Alloy スタイル専用 | 244.6MB | −0.6MB |
| F4a | PDF と印刷とプラグインを外す、`-Os`、`resources.pak` を最小に(クリーンビルド) | 225.0MB | −19.6MB |
| F4b | 拡張機能を外す | 215.4MB | −9.6MB |
| F4b-dist | 配布物の整理、ICU の軽量版 | 206.6MB | −8.8MB |

F4b は `gn clean` からのクリーンビルド(51,361 ステップ、128 分)でも同じサイズになりました。

## GN 引数で外す

GN 引数は、ビルド前に機能を on / off する設定です。ただし //chrome 層の主な機能(PDF、印刷、拡張機能など)は、GN 引数を false にしただけでは //chrome や //cef の `assert` や無条件の依存で止まります。また、`gn gen` が通っても、コンパイル、起動、動作確認で落ちる引数がありました(例: `enable_chrome_notifications=false` は起動時に `Check failed` で落ちる)。最終的な args は `args/F4b.args.gn` にあります。

## RELR 形式の再配置

共有ライブラリには、読み込み時にアドレスを書き換える場所の一覧(再配置テーブル)があります。`libcef.so` の `.rela.dyn` は 25.8MB ありました。RELR は、この一覧を詰めて持つ形式で、F1a で `.rela.dyn` が 25.8MB から `.relr.dyn` 0.2MB になりました。Chromium の Linux ビルドにはこの設定がないので、GN 引数を足すパッチを書きました。

```diff:build/config/compiler/BUILD.gn
+declare_args() {
+  fp_use_relr_relocations = false
+}
@@ config("linker") {
+  if (fp_use_relr_relocations && is_linux && use_lld) {
+    ldflags += [ "-Wl,-z,pack-relative-relocs" ]
+  }
```

最初に使った `--pack-dyn-relocs=relr` では、出力に `GLIBC_ABI_DT_RELR` の印が付かず、ビルドの途中で作るツール(`protoc`)が起動しませんでした。`-z pack-relative-relocs` に変えて解決しています。

## 一括登録の呼び出しを消す(WebUI)

`chrome://settings` などの WebUI は、`chrome_browser_main.cc` の 2 つの関数でまとめて登録されています。この呼び出しを消すと、各ページのコードがどこからも参照されなくなり、リンカが取り除きます。

```diff:chrome/browser/chrome_browser_main.cc
-  RegisterChromeWebUIConfigs();
-  RegisterChromeUntrustedWebUIConfigs();
+  // FP: chrome:// の WebUI は登録しない(TV 向け最小構成)。
```

同じ考え方で、WebUI 用の Mojo のバインダの登録 3 か所も消しました(`chrome_content_browser_client_receiver_bindings.cc`)。ページのリソースは `resources.pak` に残るので、許可した ID だけで pak を作り直す `pakstrip.py` を合わせて使いました。`resources.pak` の 25.6MB のうち、4.8MB は起動演出の音声(FLAC 6 本)でした。

## Blink のモジュールを外す

Blink(HTML と CSS を処理する部分)の Web API はモジュール単位で分かれています。`third_party/blink/renderer/modules/BUILD.gn` の依存から外し、参照している箇所を消すパッチ(`e3b.patch`、46 ファイル)を書きました。

```diff:third_party/blink/renderer/modules/BUILD.gn
     "//third_party/blink/renderer/modules/accessibility",
     "//third_party/blink/renderer/modules/ad_auction",
-    "//third_party/blink/renderer/modules/ai",
     "//third_party/blink/renderer/modules/animationworklet",
-    "//third_party/blink/renderer/modules/app_banner",
     "//third_party/blink/renderer/modules/audio_output_devices",
-    "//third_party/blink/renderer/modules/background_fetch",
-    "//third_party/blink/renderer/modules/background_sync",
```

外したモジュールの関数を呼んでいる箇所のために、空の実装を置くファイル(`fp_stubs.cc`)も追加しました。

## PDF、印刷、拡張機能を外す

この 3 つは GN 引数(`enable_pdf`、`enable_printing`、`enable_extensions` など)はあるものの、false にすると //chrome と //cef のコードがコンパイルできなくなります。参照している箇所を `#if BUILDFLAG(...)` で囲むパッチを書きました。拡張機能は参照が広く、Chromium 側で 342 ファイルを変更しています(PDF と印刷の分を含む)。

拡張機能を外すと、起動直後の回収できない RAM も x64 で 40MiB 減りました。CEF の既定では、内蔵の拡張機能のために Service Worker 用のレンダラ(PSS 約 45MiB)が 1 つ常駐していたためです。

## arm64

arm64 には、x64 用のパッチと args.gn がそのまま通りました(`target_cpu="arm64"` を足しただけ)。arm64 の strip 後のサイズは x64 より 4MB 小さく、配布物は 13.7MB 大きくなりました。差のほとんどは SwiftShader です。SwiftShader は arm64 では軽量の JIT(Subzero)が使えず、LLVM 10 を丸ごとリンクするため、`libvk_swiftshader.so` が x64 の 5.4MB に対して 22.8MB(strip 前)になります(`third_party/swiftshader/src/Reactor/reactor.gni:13`)。GPU のある機器ではこれを外せるので、G2-tv では SwiftShader 一式を配布物から外しました(−23.6MB)。

G2 では、YouTube の TV 向けアプリ Cobalt のビルド設定から 4 つの GN 引数(`enable_media_remoting`、`enable_media_remoting_rpc`、`enable_hls_demuxer`、`enable_hevc_parser_and_hw_decoder` をすべて false)を採り入れました。効果は −0.5MB でした。

## 削れなかったもの

`//chrome` 層と CEF 本体は、削減後も約 45〜55MB 残っています。2 通りの方法で見積もりました。

| 方法 | 見積もり |
|---|---|
| リンカのマップファイルで、`chrome/`(17.5MB)、CEF 本体(1.9MB)、//chrome から使われる `components/`(約 18MB)と `third_party/`(約 4MB)のコードを積み上げる(arm64 の G2) | 約 47MB |
| 同じ削減をした content_shell(Chromium 159、x64、160.4MB)に、RELR(実測 −12.8MB)と `-Os`(推定 約 −10MB)を当てた見込み(約 138MB)と、F4b(191.2MB)の差 | 約 53MB(推定) |

残っているのは、自動入力(`components/autofill` だけで 3.1MB)、パスワード管理、同期、アドレスバーの補完、Safe Browsing、ポリシー、履歴、Chrome スタイルの UI などです。外せなかった理由は次のとおりです。

- CEF は //chrome のクラスを継承して動くので、//chrome 層そのものは外せない
- これらの機能は、//chrome の中央の登録箇所(Profile ごとのサービスの一括登録など)から直接参照されている。機能ごとの GN 引数がなく、個別に参照を消すパッチでは参照が残ってリンクされる
- Alloy スタイル専用にしても −0.6MB だった。Chrome スタイルの UI のクラスは、生成箇所以外の数千箇所から参照されている

比較として、同じ Chromium で `chrome` を `content_shell`(content 層だけで作る最小のブラウザ)に替えると、実行ファイルは 309.8MB から 211.9MB(−97.9MB)になりました。CEF は API の都合でこの方法を使えません。

# RAM の削り方

## 起動直後

起動直後の RAM(arm64、caps.html を開いて 30 秒後):

| 構成 | プロセス数 | 回収できない RAM | ファイル由来の RAM | 本体の PSS |
|---|---|---|---|---|
| G0(CEF 既定) | 8 | 160.5MiB | 228.7MiB | 239.3MiB |
| G1(x64 の削減を全部適用) | 8 | 128.7MiB | 159.2MiB | 173.6MiB |
| G2-tv(SwiftShader なし) | 8 | 101.8MiB | 141.0MiB | 168.8MiB |

x64 での段階別の測定では、E3b → F4a で実行ファイルを 61MB 減らしても、回収できない RAM は −8MiB でした。この区間で減ったのは主にファイル由来の RAM です(RELR で約 −24.5MiB)。続く F4a → F4b(拡張機能を外す)では、回収できない RAM が −40MiB 減りました。

## 動画の再生中

AV1 1080p60 を再生しているときの値(arm64、8 CPU / 8GB、PSS、有効 3 回の中央値):

| 構成 | 低メモリ端末モード | 再生中の PSS | レンダラ | GPU プロセス | MSE のバッファ |
|---|---|---|---|---|---|
| G0 | オフ | 1,060.7MiB | 523.2MiB | 279.3MiB | 170.6 秒 |
| G0 | オン | 1,008.3MiB | 498.3MiB | 242.6MiB | 70.1 秒 |
| G1 | オフ | 907.4MiB | 488.6MiB | 236.9MiB | 170.6 秒 |
| G1 | オン | 883.6MiB | 482.7MiB | 208.0MiB | 70.2 秒 |

項目ごとの効果は次のとおりでした。

| 項目 | 効果 | 内容 |
|---|---|---|
| ROM の削減(G0 → G1) | −153MiB(−14.5%) | ファイル由来 −75MiB、匿名メモリ −83MiB |
| 低メモリ端末モード(`--enable-low-end-device-mode`) | −24〜−54MiB | MSE のバッファが 170 秒分から 70 秒分に、JavaScript のヒープの上限が 4,132MiB から 259MiB になる |
| `--single-process --no-zygote` | −34MiB | 全部を 1 プロセスにまとめ、プロセスごとに必要な分がなくなる(低メモリ端末モードを含む起動フラグ一式に足したときの差) |
| CPU 数(2 → 16) | +39MiB | スレッド数が増える |
| 搭載メモリ量(2GB〜8GB) | ほぼ変わらない | |

低メモリ端末モードは、搭載メモリが 2048MB 以下だと自動で有効になります(Linux の既定)。2GB のコンテナは MemTotal が 2,101MiB で、自動では有効になりませんでした。1.9GB(MemTotal 1,959MiB)では自動で有効になりました。

`--single-process` は、レンダラが落ちるとブラウザごと落ちること、サンドボックスがなくなることと引き換えです。

## 4K と 1080p の差

AV1 4K60 は H.264 1080p60 より +320〜460MiB 多く必要でした。増えた分のほとんどは、デコード済みのフレームと MSE のバッファ(memory-infra の `media` が 1080p の約 134MiB から 4K の約 410〜540MiB)です。1080p では、AV1 と H.264 で RAM の差はほとんどありませんでした(CEF 既定で −15MiB)。

## メモリの上限をかけたとき

Chromium は cgroup の上限を参照しません。上限に近づいても自分からメモリを手放さず、カーネルがファイル由来のページを捨て、それでも足りなければブラウザを強制終了します。そのため上限を細かく変えても動作は変わらず、再生できるかどうかだけが変わります。

上限に数えられるのは、回収できない RAM のほかに、捨てきれないファイル由来のページ(約 100〜130MiB)とカーネルの分(約 10MiB)です。制限なしで測った回収できない RAM の最大値に約 100MB を足した上限では、CEF 既定(H.264 1080p、780MiB)が読み込み中に強制終了されました。約 200MB を足した上限では、どの条件でも再生できました。

## SwiftShader のないビルドで `--single-process` を使う条件

G2-tv(SwiftShader なし)は、計測ツールが付けていた `--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader` と `--single-process` を一緒に使うと、起動直後に落ちました。

- 通常のマルチプロセスでは、GPU プロセスが初期化に失敗すると、ブラウザが別のモード(ソフトウェア合成)で GPU プロセスを作り直す
- `--single-process` では GPU はスレッドなので作り直せない。GPU のモードは起動時に SwiftShader を使うモードに決まり、GL の初期化に失敗したまま `gl::init::CreateGLContext` が呼ばれて SIGTRAP で落ちる(gdb でスタックを確認)

SwiftShader を指定する 3 つの引数を付けずに `--disable-gpu` を付けると起動し、YouTube も再生できました。ビルドの変更は要りません。

# パッチとソースコード

パッチ、args.gn、計測用のスクリプト、計測結果は次のリポジトリにあります。

https://github.com/aRaikoFunakami/CEF_M158_Investigation

| パス | 内容 |
|---|---|
| `patches/chromium/e3b-final-clean.patch` | タグ `158.0.8127.18` からの差分。CEF 自身のパッチと第 1 期(E3b)の変更を含む(517 ファイル) |
| `patches/chromium/f4b.patch` | 上の状態からの差分。第 2 期の最終形(348 ファイル) |
| `patches/cef/f4b-cef.patch` | CEF `6ee3fb965` への差分(16 ファイル) |
| `patches/chromium/g2.patch` | arm64 の G2 で足した 2 ファイル |
| `patches/new-files/` | パッチに含まれない新規ファイル 3 つ |
| `args/` | 各構成の args.gn |
| `scripts/measure/` | 計測用のスクリプト(サイズ、起動直後の RAM、YouTube の再生中の RAM、動作確認) |
| `scripts/patch/pakstrip.py` | `resources.pak` の作り直し |
| `data/` | 計測結果(JSON、TSV) |
| `docs/` | 調査の記録 |

3 つのパッチは、タグと CEF のコミットに順に当たることを確認しています(作業ツリーに触れない一時インデックスでの `git apply --check`)。手順は README に書きました。ただし、新しいツリーでこの手順を最初から通してビルドしたことはありません。

# 未確認のこと

- ハードウェアデコーダのある実機での RAM
- TV 向けの YouTube(`youtube.com/tv`)での計測。今回は PC 向けのページで測った
- 4K の VP9、720p 以下の解像度
- メモリの上限の境界(再生できる最小値)
- 再生中の PSS が同じ条件で約 180MiB 違う回がある原因(JavaScript のヒープが 80〜89MiB の回と 105〜121MiB の回に分かれる)
- `-Os` の速度への影響
- PGO(`chrome_pgo_phase=2`、Linux の配布用ビルドの既定)がサイズに与える影響
- //chrome 層をさらに外すパッチの効果(CEF のままで −15〜25MB の見込み)

# Appendix: 途中で起きた問題

最終結果に至るまでに起きた問題と、その対処です。

## ビルド

| 問題 | 原因と対処 |
|---|---|
| siso が止まる | 子プロセスがゾンビのまま回収されず、siso が待ち続けた。3 回発生し、CEF 既定のビルドでは 3 時間 45 分止まっていた。原因は特定できていない。ninja(`use_siso=false`)に切り替え、停止を検知して再実行するラッパーを作った |
| 停止の検知を見逃す | 止まった siso 本体が空回りで CPU を使い、検知ラッパーが「進んでいる」と判定した。「コンパイラやリンカのプロセスが動いたか」で判定するように変えた |
| `automate-git.py` が全履歴を取りにいく | 約 2,550 万オブジェクト、48GB を受信して 1 時間 54 分で打ち切った。タグだけの浅い取得に分けた |
| `gn gen` が通っても使えない GN 引数 | コンパイルで `#error`、リンクで未定義参照、起動時に `Check failed` で落ちるものがあった。F2 では 26 個を一度に入れて 8 個が落ち、ビルドを 5 回やり直した |
| 増分ビルドでは通ったパッチがクリーンビルドで落ちる | 古い生成ヘッダが残っていたため。クリーンビルドで確かめ、足りない include などを直した |
| GN 引数の効果がない | `enable_mdns` など 3 つを false にして 90 分の再ビルドをしたが −0.1MB だった。不採用 |
| Rosetta 上の一時的な異常終了 | DevTools のビルドで `tsc` が SIGSEGV で落ちることがあった。再実行で通る |

## 計測

| 問題 | 原因と対処 |
|---|---|
| YouTube が "Something went wrong" で止まる | すべての構成と content_shell でも起きた。原因は特定できていない。止まった回は PSS が低く出るので、最後まで再生が進んだ回だけを数え、YouTube を開いたあとのプロファイルを使うようにした |
| Rosetta 上でブラウザのプロセスを見つけられない | `/proc/<pid>/exe` が Rosetta 本体を指していた。`argv[0]` で照合した |
| H.264 を選ばせる設定が効かない | CDP の `Page.addScriptToEvaluateOnNewDocument` は、先に `Page.enable` を呼ばないとスクリプトを注入しない(登録は成功を返す)。`Page.enable` を足した |
| 4K で AV1 が選ばれない | VP9 を「非対応」にすると H.264 1080p に落ちた。YouTube の「AV1 を優先する」設定(localStorage)だけでは VP9 のままだった。`mediaCapabilities` で「AV1 は省電力で再生できる」と答えさせると AV1 になった |
| 上限つきの計測で再生後に強制終了される | 最後に取っていたメモリの内訳のダンプ自体がメモリを使っていた。上限つきのときはダンプを取らないようにした |
| `memory.peak` が使えない | このカーネルでは書き込みでリセットできず、前の条件の最大値が残った。10 秒おきの値から最大値を取った |
| G2-tv の `--single-process` が起動しない | 当初「ブラウザは起動するがページが作られない」と記録したが、実際はブラウザごと落ちていた。原因と対処は本文のとおり |
