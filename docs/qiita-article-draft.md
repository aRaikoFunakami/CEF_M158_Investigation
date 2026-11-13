---
title: CEF 158 をローエンド機向けに削る: ROM と RAM はどこまで減らせるか
tags: CEF Chromium 組み込み メモリ削減 Linux
---

# はじめに

## CEF とは

CEF(Chromium Embedded Framework)は、Chrome のもとになっているオープンソースのブラウザ Chromium を、ほかのアプリケーションに組み込むためのフレームワークです。プロジェクトの README は、用途として次を挙げています。

- 既存のネイティブアプリに Web ブラウザの部品を埋め込む
- UI を Web 技術で作る、薄いネイティブアプリ(シェル)を作る
- 独自の描画系を持つアプリで、Web ページを画面に出さずに描画し、その画像をアプリ側で使う(オフスクリーン描画)
- Web アプリの自動テストのホストにする

同じ README は、Chromium プロジェクトが主に Chrome の開発を対象にしているのに対し、CEF は組み込み用途を対象にしていると説明しています。CEF は Chromium に C / C++ の API(`include/` 以下のヘッダ)をかぶせ、ウィンドウの生成、ページ遷移の通知、JavaScript とネイティブコードのやり取り、通信の横取り、オフスクリーン描画などをアプリから扱えるようにしています。TV やセットトップボックスのように、自社のアプリの中で Web コンテンツを表示したい機器では、この API が必要になります。

## Chromium の層の構造

Chromium のソースは、役割ごとの層に分かれています。この記事に出てくる層は次のとおりです。

| 層 | ソースの場所 | 役割 |
|---|---|---|
| Blink、V8 など | `third_party/blink`、`v8` など | Blink は HTML と CSS を処理して画面を組み立てる部分(レンダリングエンジン)、V8 は JavaScript の実行エンジン。ほかにネットワーク、描画、動画の再生などの部品がある |
| content 層 | `content/` | ブラウザの土台。ページごとにプロセスを分けて動かす仕組みや、ページ遷移の管理を受け持つ |
| //chrome 層 | `chrome/` | Chrome のブラウザ機能。設定やブックマークを持つプロファイル、自動入力、同期、拡張機能、PDF ビューア、印刷、タブやツールバーなどの UI |

Chromium のブラウザは複数のプロセスで動きます。画面とタブを管理するブラウザプロセス、ページを処理するレンダラプロセス、描画を受け持つ GPU プロセス、ネットワークなどのユーティリティプロセスです。

`content_shell` は、content 層だけで作られた最小のブラウザで、Chromium のソースに含まれています(主にテスト用)。

## CEF が大きくなった理由

CEF は長く、content 層の上に直接載っていて、//chrome 層は使っていませんでした。CEF のコミット履歴では、この構成が次のように変わっています。

| 日付 | コミット | 内容 |
|---|---|---|
| 2020-06-24 | `117499421` | 「Chrome ランタイム」(//chrome 層の上で動く方式)の初期対応 |
| 2020-06-28 | `84f3ff2af` | 従来の方式を「Alloy ランタイム」と改名 |
| 2024-04-17 | `dca0435d2` | Chrome ランタイムの上で、Alloy スタイル(後述)のブラウザとウィンドウに対応 |
| 2024-06-25 | `a461a8972` | Alloy ランタイムの起動経路を削除。CEF の 6613 ブランチ(Chromium 128)以降に含まれる |

![CEF の構成](https://raw.githubusercontent.com/aRaikoFunakami/CEF_M158_Investigation/main/docs/images/fig1-cef-architecture.png)

その結果、現在の CEF は必ず //chrome 層の上で動きます。CEF 本体(`libcef.so`)は、`ChromeMainDelegate`、`ChromeContentBrowserClient`、`ChromeContentRendererClient` など //chrome のクラスを継承して作られています。設定や Cookie を保持する単位も Chrome のプロファイル(`Profile`)です。CEF 本体の 76 ファイルが `chrome/` 以下のヘッダを計 172 回 include しています。こうして、自動入力、同期、パスワード管理、拡張機能、PDF ビューア、印刷、ブラウザの UI など、組み込み用途で使わない機能もまとめてリンクされます。

## Alloy スタイルと Chrome スタイル

現在の CEF では、ウィンドウ(ブラウザ)ごとに 2 つのスタイルのどちらかを選びます。CEF のヘッダ `include/internal/cef_types_runtime.h` の説明は次のとおりです。

| スタイル | 内容 |
|---|---|
| Chrome スタイル | Chrome の UI とブラウザ機能をそのまま持つ(タブ、ツールバー、メニューなど) |
| Alloy スタイル | 既定のブラウザ機能は少ないが、アプリ向けのコールバックが多く、オフスクリーン描画に対応する |

どちらのスタイルも Chrome ランタイムの上で動きます。オフスクリーン描画は常に Alloy スタイルです。今回は、組み込み用途に近い Alloy スタイルを対象にしました。CEF に付属するサンプルアプリ `cefsimple` を `--use-alloy-style` で起動して、サイズと動作を確かめています。

## 調査の目的

ローエンドの機器(TV など)に組み込んで Web 閲覧に使えるように、CEF の最新リリース版の ROM(機器に載せるファイルのサイズ)と RAM の使用量を、どこまで、どの方法で減らせるかを調べました。条件は、Chrome のブラウザ機能を外しても、CEF の API と YouTube の再生が動くことです。

# 結果

以降、CEF に何も手を加えずにビルドしたものを「CEF 既定」、後述の削減をすべて入れたものを「削減版」と呼びます。

## ROM

| CPU | 構成 | 実行ファイル | 配布物 |
|---|---|---|---|
| x64 | CEF 既定 | 299.6MB | 377.5MB |
| x64 | 削減版 | 191.2MB(−36.2%) | 206.6MB(−45.3%) |
| arm64 | CEF 既定 | 275.1MB | 366.3MB |
| arm64 | 削減版 | 186.7MB(−32.1%) | 219.6MB(−40.0%) |
| arm64 | 削減版、SwiftShader なし | 186.7MB(−32.1%) | 196.0MB(−46.5%) |

- 削減の作業は、調べやすい x64(PC)で進め、最後に同じ変更を TV の SoC に多い arm64 に当てました。
- 実行ファイルは `libcef.so` と `cefsimple` の合計で、デバッグ用のシンボルを取り除いた(strip した)サイズです。
- 配布物は、実行ファイルに、実行時に読むデータとライブラリを足した合計です。主なものは、画像や HTML などのリソースをまとめた `.pak` ファイル、文字列処理と国際化のライブラリ ICU のデータ、V8 の起動用データ、OpenGL ES の呼び出しを各 GPU の API に変換する ANGLE です。ロケールは ja と en-US だけを数えています(全 220 ロケールでは +50.5MB)。動画の DRM(Widevine)の復号モジュール(約 21MB、初回起動時に取得)は含みません。
- SwiftShader は、GPU の処理を CPU で行うソフトウェア実装です。GPU のない環境で画面を描くために CEF に同梱されています。GPU のある機器では要らないので、外した場合の値も示しました。

![ROM の推移](https://raw.githubusercontent.com/aRaikoFunakami/CEF_M158_Investigation/main/docs/images/fig2-rom-x64.png)

## RAM(arm64)

RAM の値は 2 種類を使っています。詳しくは「計測方法」に書きました。

- **PSS**: プロセスが使っているメモリのうち、ほかのプロセスと共有している分を按分して数えた量。全プロセスの合計を使った
- **回収できない RAM**: メモリが足りなくなってもカーネルが捨てられない分(プログラムが確保したメモリなど)。実行ファイルを読み込んだ分のように、捨てても読み直せる分(ファイル由来の RAM)は含まない

起動直後(ローカルのテストページを開いて 30 秒後、3 回の中央値):

| 構成 | 回収できない RAM | ファイル由来の RAM |
|---|---|---|
| CEF 既定 | 160.5MiB | 228.7MiB |
| 削減版 | 128.8MiB(−19.8%) | 159.4MiB(−30.3%) |
| 削減版、SwiftShader なし | 101.8MiB(−36.6%) | 141.0MiB(−38.3%) |

YouTube の動画を再生している間(全プロセスの PSS、最後まで再生できた 2 回の中央値):

| 動画 | CEF 既定 | CEF 既定 + 起動フラグ | 削減版 | 削減版 + 起動フラグ |
|---|---|---|---|---|
| H.264 1080p60 | 1,045.5MiB | 912.2MiB(−13%) | 759.3MiB(−27%) | **684.4MiB(−35%)** |
| AV1 4K60 | 1,509.5MiB | 1,348.7MiB(−11%) | 1,131.9MiB(−25%) | **1,005.5MiB(−33%)** |

この表の削減版は SwiftShader なしのものです。起動フラグは次の 3 つで、ビルドを変えずに起動時の指定だけで使えます。

| 起動フラグ | 内容 |
|---|---|
| `--single-process` | ブラウザ、レンダラ、GPU などをすべて 1 つのプロセスで動かす |
| `--no-zygote` | 子プロセスを作るための待機プロセス(zygote)を使わない |
| `--enable-low-end-device-mode` | 低メモリ端末モード。動画の先読み量や JavaScript のメモリ上限などを小さくする |

![動画再生中の RAM](https://raw.githubusercontent.com/aRaikoFunakami/CEF_M158_Investigation/main/docs/images/fig3-ram-video.png)

ブラウザが使えるメモリに上限をかけ、120 秒間再生できるかを確かめた結果(起動フラグあり):

| 動画 | CEF 既定 | 削減版 |
|---|---|---|
| H.264 1080p60 | 880MiB で再生できた(780MiB では強制終了) | 640MiB で再生できた |
| AV1 4K60 | 1,320MiB で再生できた | 980MiB で再生できた |

これは「この上限で再生できた」という確認で、再生できる最小値ではありません。上限はブラウザだけに割り当てた量で、機器の搭載 RAM ではありません。

RAM の値は、動画のデコードも描画も CPU で行う環境での測定です(「計測方法」を参照)。ハードウェアデコーダのある機器では、デコード済みのフレームがドライバ側に置かれるので、ブラウザ側の値はこれより小さくなる見込みです(未計測)。

# 調査対象

| 対象 | 版 | 入手元 |
|---|---|---|
| CEF | 8127 ブランチ、コミット `6ee3fb965`("Update to Chromium version 158.0.8127.18"、2026-11-10) | https://github.com/chromiumembedded/cef |
| Chromium | 158.0.8127.18(タグ、コミット `6449d9f9a6`) | https://chromium.googlesource.com/chromium/src |
| 比較用の Chromium | 159.0.8143.0(`content_shell` と `chrome` の比較に使用) | 同上 |

CEF のブランチ番号は、対応する Chromium のブランチ番号と同じです。調査を始めた 2026-11-10 の時点で、CEF の 8127 ブランチ(Chromium 158)は Beta、Stable は 8078 ブランチ(Chromium 156)でした。Chromium 159 に対応した CEF はまだなかったので、8127 を使いました。

CEF の取得用スクリプト `automate-git.py` を既定の設定で使うと、Chromium の全履歴を取りにいきます。そこで次の手順に分けて取得しました。

1. Chromium のタグ `158.0.8127.18` だけを `git fetch --depth=1` で取得する
2. 依存リポジトリの取得ツール gclient の設定ファイル(`.gclient`)に、`--no-chromium-history` 相当の設定を書き、`gclient sync --no-history --nohooks` を実行する
3. `gclient runhooks` を実行する
4. CEF の `cef_create_projects.sh` を実行する。この中で CEF 自身のパッチが Chromium のソースに当たる(474 ファイル)

Linux では、ビルド用の OS イメージ(sysroot)を使う設定 `use_sysroot=true` にしないと、ビルドがホストの `libpipewire-0.3` を要求して失敗しました。

# 調査環境

| 項目 | 内容 |
|---|---|
| ホスト | Mac Studio(Apple M3 Ultra、32 コア、256GB) |
| ビルド | Apple の `container` コマンドで動かす amd64 の Ubuntu 24.04(Apple の x64 変換レイヤ Rosetta で実行、24 CPU / 64GB)。arm64 版は同じコンテナでのクロスコンパイル |
| x64 の計測 | ビルドと同じ amd64 コンテナ(Rosetta 上) |
| arm64 の計測 | arm64 のネイティブコンテナ。8 CPU / 8GB を基準に、CPU 数とメモリ量を変えて計測 |
| 画面 | 仮想ディスプレイ Xvfb(1920x1080)。GPU はなく、描画は SwiftShader |

ビルド設定は、配布用のリリースビルド(`is_official_build=true`)、シンボルなし、H.264 と AAC を有効(`proprietary_codecs=true`、`ffmpeg_branding="Chrome"`)です。DRM(Widevine)の対応も残しています。

ビルドツールには ninja を使いました。Chromium の既定のビルドツール siso は、このコンテナ上で子プロセスの終了待ちのまま止まることが 3 回あったためです。ビルドは、進捗が 300 秒止まったら強制終了して再実行するラッパー(`fpbuild.py`)で流しました。フルビルドの時間は、x64 の CEF 既定で 2 時間 26 分(59,810 ステップ)、arm64 の削減版で 4 時間 58 分(83,874 ステップ)でした。

# 計測方法

## ROM

`measure.py size` で、strip 後の実行ファイルと配布物の合計を測りました。単位は MB(10^6 バイト)です。

## RAM

RAM の単位は MiB(1024^2 バイト)です。

| 値 | 測り方 |
|---|---|
| PSS | 全プロセスの `/proc/<pid>/smaps_rollup` の PSS を合計した |
| 回収できない RAM | Linux でプロセスのグループごとにリソースを数えて制限する仕組み(cgroup)を使った。ブラウザを専用の cgroup に入れて起動し、`memory.stat` の anon(プログラムが確保したメモリ)と shmem(共有メモリ)の合計を読んだ |
| ファイル由来の RAM | 全プロセスの `Pss_File`(実行ファイルなどを読み込んだページ) |

起動直後の RAM は `startram.py` で、ローカルのテストページを開いて 30 秒後に測りました。

YouTube の再生中の RAM は `ytmem.py` で、Big Buck Bunny 60fps(https://www.youtube.com/watch?v=aqz-KE-bpKQ)を 120 秒再生し、10 秒ごとに測りました。条件は次のとおりです。

- YouTube を 1 回開いたあとのプロファイル(キャッシュは削除し、Cookie などは残す)を毎回コピーして起動した。新しいプロファイルでは、YouTube が再生の途中で "Something went wrong" を出す回が約半数あったため
- 再生開始から 60 秒以降の値の中央値を 1 回の値とし、最後まで再生が進んだ回の中央値を構成の値とした
- 動画の形式(コーデック)は、ページが読み込まれる前に、ブラウザの対応状況を答える JavaScript の関数(`MediaSource.isTypeSupported` など)を差し替えて選ばせた。H.264 は、AV1 / VP9 / HEVC を「非対応」と答えさせる。AV1 の 4K は、`navigator.mediaCapabilities.decodingInfo` に「AV1 は省電力で再生できる」と答えさせる(何もしないと YouTube は 4K に VP9 を選ぶ)
- メモリの上限は、cgroup の `memory.max` でブラウザの全プロセスにかけた(スワップなし)

この環境の制約で、RAM の絶対値は実機より大きく出ます。

- 動画のデコードは CPU で行っている(AV1 は dav1d、H.264 は FFmpeg)。コンテナに GPU デバイスがないため。デコード済みのフレーム(1080p で約 134〜140MiB、4K で約 410〜540MiB)がブラウザ側のメモリに載る
- 描画も CPU(SwiftShader)で行っている
- x64 の値は Rosetta 上の測定で、回収できない RAM が arm64 より約 235MiB 大きく出た(変換済みのコードが匿名メモリに載るため)。x64 の RAM は構成間の差だけを見て、記事の RAM の数値は arm64 の値を使った

構成間の差は、この環境でも比較できます。

## 動作の確認

各構成で次の 7 項目を確認しました(`measure.py func`)。すべての構成が 7 項目とも通っています。

| 項目 | 確認方法 |
|---|---|
| 機能の検出 | テストページで主な Web API の有無を判定 |
| Service Worker(ページの裏で動き、通信を横取りできるスクリプト) | 登録と通信の横取り |
| WebSocket | ローカルのエコーサーバとの送受信 |
| MP4 | H.264 + AAC の動画の再生 |
| MSE(JavaScript から動画のデータを少しずつ渡して再生する仕組み。YouTube が使う) | 動画プレーヤ Shaka Player によるストリーミング再生 |
| EME(暗号化された動画を再生する仕組み) | 鍵を平文で渡す方式(Clear Key)の暗号化動画の再生 |
| YouTube | 1080p で再生が進むこと |

外した機能(印刷、PDF、プラグイン、拡張機能の API)を呼んでも落ちないことも、別のテストで確認しました。

# ROM の削り方

## 削減の手段

削減には次の 3 つの手段を使いました。

| 手段 | 内容 |
|---|---|
| GN 引数 | Chromium のビルド設定ツール GN に渡す設定(`args.gn` に書く)。機能ごとに on / off できるものがある |
| パッチ | ソースの変更。GN 引数がない機能や、GN 引数を false にするとビルドが通らない機能に使った |
| 配布時の処理 | ビルド後に、配布物のファイルを削ったり差し替えたりする |

## 効果の大きい順

値は配布物の削減量で、段階どうしの差から求めています。

| 削減の内容 | 手段 | 効果 | 失うもの |
|---|---|---|---|
| Vulkan(GPU の API)の検証レイヤを同梱しない | GN 引数 `dawn_enable_vulkan_validation_layers=false` | −27.3MB | 開発用のデバッグ機能 |
| 再配置テーブルを RELR 形式にする | リンカオプション `-Wl,-z,pack-relative-relocs` を足すパッチ | −25.6MB | なし(実行環境に glibc 2.36 以降が必要) |
| `resources.pak` を絞り込む | 配布時の処理(`pakstrip.py`) | −24.7MB(25.6 → 0.9MB) | `chrome://` の全ページ、開発者ツール(DevTools)の画面、起動演出の音声 |
| CFI(関数呼び出しの不正な書き換えを検出する仕組み)を無効にする | GN 引数 `is_cfi=false` | 約 −14MB | 攻撃への耐性の一部。arm64 では既定で無効 |
| Blink のモジュールを 41 個外す | パッチ | −12.0MB | WebRTC、カメラとマイク、Bluetooth、USB、決済、通知、プッシュ通知、VR / AR、センサーなどの Web API |
| サイズ優先の最適化 | GN 引数 `optimize_for_size=true`(コンパイラの `-Os`) | 約 −10MB(推定) | 速度への影響は未計測 |
| `chrome://` のページの登録をやめる | パッチ(呼び出し 5 行の削除) | 約 −10MB(GN 引数 17 個の追加と合わせた値) | `chrome://settings` などの全ページ |
| 拡張機能を外す | GN 引数 + パッチ(Chromium 342 ファイル、CEF 13 ファイル) | −9.4MB | `chrome.*` の拡張機能 API、`chrome-extension://` |
| PDF、印刷プレビュー、印刷、プラグインを外す | GN 引数 + パッチ(Chromium 21 ファイル、CEF 9 ファイル) | −8.5MB | PDF の表示、`window.print()`、CEF の PDF 出力 API |
| GN 引数で機能を外す(2 回、計 34 個) | GN 引数 | 実行ファイルで −8.0MB と約 −4MB | プリンタ(CUPS)、VR、リモート操作、機械学習の Web API、Kerberos 認証、Wayland、GTK、ハードウェア動画デコードの API(VA-API)など |
| WebGPU の実装(Dawn)への参照を消す | パッチ 3 行 | −5.7MB | なし |
| ICU のデータを軽量版に差し替える | 配布時の処理 | −5.6MB(10.8 → 5.2MB) | 日本語の単語の区切りが 1 文字単位になる(ダブルクリックでの単語選択など) |
| 配布物を整理する | 配布時の処理 | −3.2MB | 高解像度画面用の画像、クラッシュレポートの送信 |
| Alloy スタイル専用にする | パッチ 4 ファイル | −0.6MB | Chrome スタイルのウィンドウ |

「推定」と書いた値は、ほかの変更と同時に入れたため単独では測っていないものです。CFI の値は、同じ変更を `content_shell`(Chromium 159)に当てたときの実測です。効果には重なりがあるので、合計は全体の削減量と一致しません。

## 段階ごとのサイズ

実際に入れた順番と、その時点の配布物のサイズです(x64)。

| 段階 | 変更 | 配布物 | 前の段階との差 |
|---|---|---|---|
| CEF 既定 | | 377.5MB | |
| 手順 1 | GN 引数 17 個(Vulkan の検証レイヤなど) | 342.0MB | −35.5MB |
| 手順 2 | GN 引数 17 個(CFI 無効など) | 323.5MB | −18.5MB |
| 手順 3 | Blink のモジュールを 41 個外す | 311.5MB | −12.0MB |
| 手順 4 | RELR、Dawn への参照の削除 | 279.1MB | −32.4MB |
| 手順 5 | GN 引数 17 個、`chrome://` のページの登録をやめる、`resources.pak` の絞り込み | 245.2MB | −33.9MB |
| 手順 6 | Alloy スタイル専用 | 244.6MB | −0.6MB |
| 手順 7 | PDF と印刷とプラグインを外す、`-Os`、`resources.pak` を最小に | 225.0MB | −19.6MB |
| 手順 8 | 拡張機能を外す | 215.4MB | −9.6MB |
| 手順 9(削減版) | 配布物の整理、ICU の軽量版 | 206.6MB | −8.8MB |

手順 8 までの変更は、ビルド結果を全部消してからのビルド(クリーンビルド、51,361 ステップ、128 分)でも同じサイズになりました。

## GN 引数で外す

最初の手段は GN 引数です。ただし //chrome 層の主な機能(PDF、印刷、拡張機能など)は、GN 引数を false にしただけでは止まります。//chrome や CEF のコードに「この機能は必須」という検査(`assert`)や、条件なしの依存があるためです。また、GN の設定生成(`gn gen`)が通っても、コンパイル、起動、動作確認で失敗する引数がありました(例: `enable_chrome_notifications=false` は起動時の内部検査で落ちる)。最終的な設定は、リポジトリの `args/F4b.args.gn` にあります。

## RELR 形式の再配置

共有ライブラリには、読み込まれたアドレスに合わせて書き換える場所の一覧(再配置テーブル)があります。`libcef.so` では、この一覧(`.rela.dyn`)が 25.8MB ありました。RELR は、この一覧を詰めて持つ形式です。手順 4 で `.rela.dyn` の 25.8MB が `.relr.dyn` の 0.2MB になりました。Chromium の Linux 向けビルドにはこの設定がないので、GN 引数を足すパッチを書きました。

```diff:build/config/compiler/BUILD.gn
+declare_args() {
+  fp_use_relr_relocations = false
+}
@@ config("linker") {
+  if (fp_use_relr_relocations && is_linux && use_lld) {
+    ldflags += [ "-Wl,-z,pack-relative-relocs" ]
+  }
```

最初は `--pack-dyn-relocs=relr` を使いましたが、出力に glibc 向けの印(`GLIBC_ABI_DT_RELR`)が付かず、ビルドの途中で作るツール(`protoc`)が起動しませんでした。`-z pack-relative-relocs` に変えて解決しています。

## 一括登録の呼び出しを消す(`chrome://` のページ)

`chrome://settings` などの、ブラウザが内蔵している Web ページ(WebUI)は、`chrome_browser_main.cc` の 2 つの関数でまとめて登録されています。この呼び出しを消すと、各ページのコードがどこからも参照されなくなり、リンカが取り除きます。

```diff:chrome/browser/chrome_browser_main.cc
-  RegisterChromeWebUIConfigs();
-  RegisterChromeUntrustedWebUIConfigs();
+  // FP: chrome:// の WebUI は登録しない(TV 向け最小構成)。
```

同じ考え方で、これらのページとブラウザの間の通信(Chromium のプロセス間通信 Mojo)の登録 3 か所も消しました。ページの HTML や画像は `resources.pak` に残るので、許可したリソースだけで pak を作り直すスクリプト `pakstrip.py` を合わせて使いました。`resources.pak` の 25.6MB のうち 4.8MB は、起動演出の音声(FLAC 6 本)でした。

## Blink のモジュールを外す

Blink の Web API はモジュール単位で分かれています。`third_party/blink/renderer/modules/BUILD.gn` の依存からモジュールを外し、それを参照している箇所を消すパッチ(46 ファイル)を書きました。

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

この 3 つには GN 引数(`enable_pdf`、`enable_printing`、`enable_extensions` など)がありますが、false にすると //chrome と CEF のコードがコンパイルできなくなります。参照している箇所を条件コンパイル(`#if BUILDFLAG(...)`)で囲むパッチを書きました。拡張機能は参照箇所が多く、Chromium 側で 342 ファイルを変更しています(PDF と印刷の分を含む)。

拡張機能を外すと、起動直後の回収できない RAM も x64 で 40MiB 減りました。CEF 既定では、内蔵の拡張機能のためにレンダラプロセス(PSS 約 45MiB)が 1 つ常駐していたためです。

## arm64

x64 用のパッチと GN 引数は、`target_cpu="arm64"` を足すだけで arm64 にもそのまま通りました。arm64 の実行ファイルは x64 より 4MB 小さく、配布物は 13.7MB 大きくなりました。差のほとんどは SwiftShader です。SwiftShader は、arm64 では軽量のコード生成器(Subzero)を使えず、汎用のコンパイラ基盤 LLVM 10 を丸ごとリンクします(`third_party/swiftshader/src/Reactor/reactor.gni:13`)。そのため `libvk_swiftshader.so` は、x64 の 5.4MB に対して 22.8MB(strip 前)になります。GPU のある機器では SwiftShader は要らないので、一式を配布物から外した場合も測りました(−23.6MB)。

arm64 版では、YouTube の TV 向けアプリ Cobalt のビルド設定から 4 つの GN 引数(`enable_media_remoting`、`enable_media_remoting_rpc`、`enable_hls_demuxer`、`enable_hevc_parser_and_hw_decoder` をすべて false)も採り入れました。効果は −0.5MB でした。

## 削れなかったもの

//chrome 層と CEF 本体は、削減版でも約 45〜55MB 残っています。2 通りの方法で見積もりました。

| 方法 | 見積もり |
|---|---|
| リンク時に出力したマップファイル(どのソースのコードが何バイト入ったかの一覧)で、`chrome/`(17.5MB)、CEF 本体(1.9MB)、//chrome から使われる `components/`(約 18MB)と `third_party/`(約 4MB)を積み上げる(arm64 の削減版) | 約 47MB |
| 同じ削減を入れた `content_shell`(Chromium 159、x64、160.4MB)に、RELR(実測 −12.8MB)と `-Os`(推定 約 −10MB)を当てた見込み(約 138MB)と、x64 の削減版の実行ファイル(191.2MB)の差 | 約 53MB(推定) |

残っているのは、自動入力(`components/autofill` だけで 3.1MB)、パスワード管理、同期、アドレスバーの補完、危険なサイトの警告(Safe Browsing)、企業向けのポリシー、履歴、Chrome スタイルの UI などです。外せなかった理由は次のとおりです。

- CEF は //chrome のクラスを継承して動くので、//chrome 層そのものは外せない
- これらの機能は、//chrome の中央の登録箇所(プロファイルごとのサービスの一括登録など)から直接参照されている。機能ごとの GN 引数がなく、個々の参照を消すパッチでは別の参照が残ってリンクされる
- Alloy スタイル専用にしても −0.6MB だった。Chrome スタイルの UI のクラスは、生成する箇所以外にも数千か所から参照されている

比較として、同じ Chromium で `chrome` を `content_shell` に替えると、実行ファイルは 309.8MB から 211.9MB(−97.9MB)になりました。CEF は //chrome 層を前提に作られているので、この方法を使えません。

# RAM の削り方

## 起動直後

起動直後の RAM(arm64、テストページを開いて 30 秒後):

| 構成 | プロセス数 | 回収できない RAM | ファイル由来の RAM | CEF 本体の PSS |
|---|---|---|---|---|
| CEF 既定 | 8 | 160.5MiB | 228.7MiB | 239.3MiB |
| 削減版 | 8 | 128.8MiB | 159.4MiB | 173.9MiB |
| 削減版、SwiftShader なし | 8 | 101.8MiB | 141.0MiB | 168.8MiB |

x64 での段階ごとの測定では、手順 3 から手順 7 までで実行ファイルを 61MB 減らしても、回収できない RAM は −8MiB でした。この区間で減ったのは主にファイル由来の RAM です(RELR で約 −24.5MiB)。続く手順 8(拡張機能を外す)では、回収できない RAM が −40MiB 減りました。

## 動画の再生中

AV1 1080p60 を再生しているときの値です(arm64、8 CPU / 8GB、PSS、最後まで再生できた 3 回の中央値)。この表の削減版は、arm64 版の最後の 2 つの変更(Cobalt 由来の GN 引数 4 個と配布物の整理)を入れる前の段階で測りました。

| 構成 | 低メモリ端末モード | 再生中の PSS | レンダラプロセス | GPU プロセス | 動画の先読み量 |
|---|---|---|---|---|---|
| CEF 既定 | オフ | 1,060.7MiB | 523.2MiB | 279.3MiB | 170.6 秒分 |
| CEF 既定 | オン | 1,008.3MiB | 498.3MiB | 242.6MiB | 70.1 秒分 |
| 削減版 | オフ | 907.4MiB | 488.6MiB | 236.9MiB | 170.6 秒分 |
| 削減版 | オン | 883.6MiB | 482.7MiB | 208.0MiB | 70.2 秒分 |

動画の先読み量は、MSE でブラウザが保持している動画データの秒数です。

項目ごとの効果は次のとおりでした。

| 項目 | 効果 | 内容 |
|---|---|---|
| ROM の削減 | −153MiB(−14.5%) | ファイル由来 −75MiB、プログラムが確保したメモリ −83MiB |
| 低メモリ端末モード | −24〜−54MiB | 動画の先読みが 170 秒分から 70 秒分に、JavaScript のメモリ上限が 4,132MiB から 259MiB になる |
| `--single-process --no-zygote` | −34MiB | 全部を 1 プロセスにまとめ、プロセスごとに必要な分がなくなる(低メモリ端末モードを含むフラグ一式に足したときの差) |
| CPU 数(2 → 16) | +39MiB | CPU 数に合わせてスレッドが増える |
| 搭載メモリ量(2GB〜8GB) | ほぼ変わらない | |

低メモリ端末モードは、搭載メモリが 2048MB 以下だと自動で有効になります(Linux の既定)。2GB を割り当てたコンテナはカーネルが報告するメモリ量(MemTotal)が 2,101MiB で、自動では有効になりませんでした。1.9GB(MemTotal 1,959MiB)では自動で有効になりました。

`--single-process` を使うと、ページの処理が落ちたときにブラウザごと落ち、プロセスを分けて守る仕組み(サンドボックス)もなくなります。

## 4K と 1080p の差

AV1 4K60 は H.264 1080p60 より +320〜460MiB 多く必要でした。増えた分のほとんどは、デコード済みのフレームと動画の先読みのデータです(Chromium のメモリ計測機能 memory-infra で見たメディア関連のメモリが、1080p の約 134MiB から 4K の約 410〜540MiB)。1080p どうしでは、AV1 と H.264 で RAM の差はほとんどありませんでした(CEF 既定で −15MiB)。

## メモリの上限をかけたとき

Chromium は cgroup の上限を見ていません。上限に近づいても自分からメモリを手放さず、カーネルがファイル由来のページを捨て、それでも足りなければブラウザを強制終了します。そのため上限を変えても動作は変わらず、再生できるかどうかだけが変わります。

上限に数えられるのは、回収できない RAM のほかに、捨てきれないファイル由来のページ(約 100〜130MiB)とカーネルの分(約 10MiB)です。制限なしで測った回収できない RAM の最大値に約 100MB を足した上限では、CEF 既定(H.264 1080p、780MiB)が読み込み中に強制終了されました。約 200MB を足した上限では、どの条件でも再生できました。

## SwiftShader なしで `--single-process` を使う条件

SwiftShader を外した削減版は、計測ツールが付けていた SwiftShader 用の起動フラグ(`--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader`)と `--single-process` を一緒に使うと、起動直後に落ちました。

- 通常のマルチプロセスでは、GPU プロセスが初期化に失敗すると、ブラウザが GPU を使わない描画方式に切り替えて GPU プロセスを作り直す
- `--single-process` では GPU の処理はスレッドなので作り直せない。描画方式は起動時に SwiftShader を使う方式に決まり、初期化に失敗したまま描画の準備(`gl::init::CreateGLContext`)が呼ばれて落ちる(デバッガ gdb でスタックを確認)

SwiftShader 用の 3 つのフラグを付けずに `--disable-gpu` を付けると起動し、YouTube も再生できました。ビルドの変更は要りません。

# パッチとソースコード

パッチ、GN 引数、計測用のスクリプト、計測結果は次のリポジトリにあります。

https://github.com/aRaikoFunakami/CEF_M158_Investigation

| パス | 内容 |
|---|---|
| `patches/chromium/e3b-final-clean.patch` | タグ `158.0.8127.18` からの差分。CEF 自身のパッチと手順 1〜3 の変更を含む(517 ファイル) |
| `patches/chromium/f4b.patch` | 上の状態からの差分。手順 4〜8 の変更(348 ファイル) |
| `patches/cef/f4b-cef.patch` | CEF のコミット `6ee3fb965` からの差分(16 ファイル) |
| `patches/chromium/g2.patch` | arm64 版で足した GN 引数 `enable_media_remoting=false` を通すための 2 ファイル |
| `patches/new-files/` | パッチに含まれない新規ファイル 3 つ |
| `args/` | 各段階の `args.gn` |
| `scripts/measure/` | 計測用のスクリプト(サイズ、起動直後の RAM、YouTube の再生中の RAM、動作確認) |
| `scripts/patch/pakstrip.py` | `resources.pak` の作り直し |
| `data/` | 計測結果(JSON、TSV) |
| `docs/` | 調査の記録 |

リポジトリの中では、各段階を調査中の名前で呼んでいます。対応は次のとおりです。

| 記事での名前 | リポジトリでの名前 |
|---|---|
| x64 の CEF 既定 | E1 |
| x64 の手順 1、2、3 | E2、E3a、E3b |
| x64 の手順 4、5、6、7、8 | F1a、F2、F2b1、F4a、F4b |
| x64 の削減版(手順 9) | F4b-dist |
| arm64 の CEF 既定 | G0 |
| arm64 の削減版(Cobalt 由来の GN 引数と配布物の整理を入れる前) | G1 |
| arm64 の削減版 | G2-dist |
| arm64 の削減版、SwiftShader なし | G2-tv |

3 つのパッチは、タグと CEF のコミットに順に当たることを確認しています(作業中のソースに触れない一時インデックスでの `git apply --check`)。手順は README に書きました。ただし、新しいソースツリーでこの手順を最初から通してビルドしたことはありません。

# 未確認のこと

- ハードウェアデコーダのある実機での RAM
- TV 向けの YouTube(`youtube.com/tv`)での計測。今回は PC 向けのページで測った
- 4K の VP9、720p 以下の解像度
- メモリの上限の境界(再生できる最小値)
- 再生中の PSS が同じ条件で約 180MiB 違う回がある原因(JavaScript のメモリが 80〜89MiB の回と 105〜121MiB の回に分かれる)
- `-Os` の速度への影響
- Chromium の Linux 向けリリースビルドで既定で有効になっている、実行時のプロファイルを使う最適化(PGO、`chrome_pgo_phase=2`)がサイズに与える影響
- //chrome 層をさらに外すパッチの効果(CEF のままで −15〜25MB の見込み)

# Appendix: 途中で起きた問題

最終結果に至るまでに起きた問題と、その対処です。

## ビルド

| 問題 | 原因と対処 |
|---|---|
| siso が止まる | 子プロセスが終了したまま回収されず(ゾンビ)、siso が待ち続けた。3 回発生し、CEF 既定のビルドでは 3 時間 45 分止まっていた。原因は特定できていない。ninja に切り替え、停止を検知して再実行するラッパーを作った |
| 停止の検知を見逃す | 止まった siso 本体が空回りで CPU を使い、検知ラッパーが「進んでいる」と判定した。「コンパイラやリンカのプロセスが動いたか」で判定するように変えた |
| `automate-git.py` が全履歴を取りにいく | 約 2,550 万オブジェクト、48GB を受信して 1 時間 54 分で打ち切った。タグだけの浅い取得に分けた |
| `gn gen` が通っても使えない GN 引数 | コンパイルでエラー、リンクで未定義参照、起動時に内部検査で落ちるものがあった。手順 5 では 26 個を一度に入れて 8 個が通らず、ビルドを 5 回やり直した |
| 差分ビルドでは通ったパッチがクリーンビルドで落ちる | 古い自動生成のヘッダが残っていたため。クリーンビルドで確かめ、足りない include などを直した |
| GN 引数の効果がない | `enable_mdns` など 3 つを false にして 90 分の再ビルドをしたが −0.1MB だった。不採用 |
| Rosetta 上の一時的な異常終了 | 開発者ツールのビルド中に TypeScript のコンパイラ(`tsc`)がセグメンテーション違反で落ちることがあった。再実行で通る |

## 計測

| 問題 | 原因と対処 |
|---|---|
| YouTube が "Something went wrong" で止まる | すべての構成と `content_shell` でも起きた。原因は特定できていない。止まった回は PSS が低く出るので、最後まで再生が進んだ回だけを数え、YouTube を開いたあとのプロファイルを使うようにした |
| Rosetta 上でブラウザのプロセスを見つけられない | `/proc/<pid>/exe` が Rosetta 本体を指していた。起動時のコマンド名(`argv[0]`)で照合した |
| H.264 を選ばせる設定が効かない | ブラウザを外から操作する仕組み(Chrome DevTools Protocol)の `Page.addScriptToEvaluateOnNewDocument` は、先に `Page.enable` を呼ばないとスクリプトを注入しない(登録は成功を返す)。`Page.enable` を足した |
| 4K で AV1 が選ばれない | VP9 を「非対応」にすると H.264 1080p に落ちた。YouTube の「AV1 を優先する」設定(localStorage)だけでは VP9 のままだった。`mediaCapabilities` で「AV1 は省電力で再生できる」と答えさせると AV1 になった |
| 上限つきの計測で再生後に強制終了される | 最後に取っていたメモリの内訳のダンプ自体がメモリを使っていた。上限つきのときはダンプを取らないようにした |
| cgroup の最大使用量(`memory.peak`)が使えない | このカーネルでは書き込みでリセットできず、前の条件の最大値が残った。10 秒おきの値から最大値を取った |
| SwiftShader なしで `--single-process` を使うと起動しない | 当初「ブラウザは起動するがページが作られない」と記録したが、実際はブラウザごと落ちていた。原因と対処は本文のとおり |
