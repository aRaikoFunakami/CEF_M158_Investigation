# ROM サイズ削減の一覧(調査結果)

作成: 2026-11-12(同日 18:30 に CEF 第 2 期の結果を 6 章として追記)。出典は `logs/chromium-summary.md`、`logs/cef-milestones/M4-flags-and-patch-E3.md`、`logs/cef-milestones/M5-summary.md`、`logs/results/*-size.json`。

## 前提

- ROM サイズ = 端末に載せる配布物の合計。実行ファイル(strip 後)+ pak + ICU データ + V8 スナップショット + ANGLE / SwiftShader などの同梱ライブラリ。
- Linux x64、`is_official_build=true`、シンボルなし、`proprietary_codecs=true`、`ffmpeg_branding="Chrome"`。単位は MB(10^6 バイト)。
- `chrome` と CEF の配布物はロケールを ja + en-US に絞った値。全ロケール(220 個)だと +50.5MB。`content_shell` はロケール pak を持たない。
- CEF の配布物に Widevine CDM(約 21MB)は含まない(初回起動時にプロファイルへ取得)。
- どの構成も動作確認 7 項目(機能検出、Service Worker、WebSocket、MP4、MSE、EME、YouTube 1080p)に合格。D3a と D3b は中間構成で未実施。
- x64 の値。ARM の TV 向けビルドでは絶対値が変わる(特に CFI は ARM では元々無効)。

## 1. 構成別の一覧

### Chromium 編(159.0.8143.0)

| 構成 | 内容 | 実行ファイル | 前段との差 | 配布物合計 | 前段との差 | A からの累計(配布物) |
|---|---|---|---|---|---|---|
| A | `chrome`、リリース既定 | 309.8 | | 389.4 | | |
| B | A + GN フラグ 19 個 | 301.5 | −8.3 | 353.1 | −36.3 | −36.3(−9.3%) |
| A' | `content_shell`、リリース既定 | 211.9 | −97.9(A 比) | 266.8 | −122.6(A 比) | −122.6(−31.5%) |
| C | A' + GN フラグ 19 個 | 203.9 | −8.0 | 230.9 | −35.9 | −158.5(−40.7%) |
| D1 | C + 追加 GN フラグ 23 個 + `content/shell` のパッチ | 192.4 | −11.5 | 214.6 | −16.3 | −174.8(−44.9%) |
| D2 | D1 + Blink モジュール第 1 群の削除 | 188.0 | −4.4 | 210.2 | −4.4 | −179.2(−46.0%) |
| D3a | D2 + WebNN / オンデバイスモデル / VideoCapture サービスの登録を削除 | 186.9 | −1.1 | 209.1 | −1.1 | −180.3(−46.3%) |
| D3b | D3a + `webnn_use_litert=false` ほか 1 フラグ | 185.8 | −1.1 | 208.0 | −1.1 | −181.4(−46.6%) |
| D3c | D3b + CFI 無効 + MediaStream / WebRTC 系モジュールの削除 | 160.4 | −25.4 | 182.3 | −25.7 | **−207.1(−53.2%)** |

- 参考: D3c-cfi(D3c のソースで CFI 有効)は実行ファイル 174.5、配布物 196.8。

### CEF 編(CEF 8127 + Chromium 158.0.8127.18、Chrome ランタイム、Alloy スタイル)

| 構成 | 内容 | 実行ファイル(`libcef.so` + `cefsimple`) | 前段との差 | 配布物合計 | 前段との差 | E1 からの累計(配布物) |
|---|---|---|---|---|---|---|
| E1 | CEF 既定のリリース | 299.6 | | 377.5 | | |
| E2 | E1 + GN フラグ 17 個 | 291.6 | −8.0 | 342.0 | −35.5 | −35.5(−9.4%) |
| E3a | E2 + GN フラグ 17 個(CFI 無効を含む) | 273.5 | −18.1 | 323.5 | −18.5 | −54.0(−14.3%) |
| E3b | E3a + Blink モジュール 41 個の削除パッチ | 261.6 | −11.9 | 311.5 | −12.0 | **−66.0(−17.5%)** |
| E3c | E3b + `enable_mdns` / `enable_service_discovery` / `use_gio` を無効化(不採用) | 261.5 | −0.1 | 311.4 | −0.1 | −66.1 |

## 2. 削減項目別の一覧(効果の大きい順)

| # | 削減項目 | 手段 | 効果(配布物) | 対象 | 根拠 | 代償 / 注意 |
|---|---|---|---|---|---|---|
| 1 | `chrome` をやめて `content_shell`(content 層)に載せる | 構成の変更 | −122.6 | Chromium | A → A' | ブラウザ UI、拡張機能、同期、Safe Browsing、PDF、印刷などが丸ごとなくなる。CEF では不可 |
| 2 | Vulkan 検証レイヤを同梱しない | GN: `dawn_enable_vulkan_validation_layers=false` | −27.3〜27.8 | 両方 | A → B、E1 → E2 の配布物差の大半 | 実行ファイルではなく同梱 `.so` の削減。開発用の機能 |
| 3 | CFI(制御フロー保護)を無効化 | GN: `is_cfi=false` | −14.1 | 両方 | D3c-cfi → D3c | セキュリティ機能を外す。ARM の TV 向けビルドでは元々無効なので効果なし |
| 4 | Blink モジュール削除(CEF、41 個) | パッチ | −12.0 | CEF | E3a → E3b | WebRTC、MediaStream、Bluetooth、USB、決済、通知、プッシュ、WebXR、センサーなどが使えなくなる。バージョン更新ごとに追従が必要 |
| 5 | MediaStream / WebRTC 系モジュールの削除 | パッチ | −11.3 | Chromium | D3b → D3c-cfi | getUserMedia、WebRTC、MediaRecorder が使えなくなる |
| 6 | 追加 GN フラグ 23 個 + `content/shell` のパッチ | GN + パッチ | −16.3(うち実行ファイル −11.5) | Chromium | C → D1 | Wayland、GTK、GIO、VA-API、PipeWire、JPEG XL、IAMF、Reporting API、通知、BackupRefPtr、HSTS プリロードなど。DevTools フロントエンドも pak から除外 |
| 7 | 基本の GN フラグ(実行ファイル分) | GN | −8.0〜8.3 | 両方 | A → B、A' → C、E1 → E2 | CUPS、VR / OpenXR、リモーティング、オンデバイスモデル、WebNN(TFLite)、libaom、Qt、Kerberos、BlueZ、Paint Preview、クレジット、Dawn(WebGPU) |
| 8 | Blink モジュール第 1 群の削除 | パッチ | −4.4 | Chromium | D1 → D2 | WebXR、WebUSB、HID、Serial、Bluetooth、Web MIDI、センサー、NFC、決済など |
| 9 | CEF の追加 GN フラグ(CFI 以外の 16 個) | GN | 約 −4 | CEF | E2 → E3a の −18.1 から CFI 分(Chromium 編の実測 14.1)を引いた推定 | フラグ別の寄与は未計測 |
| 10 | WebNN / オンデバイスモデル / VideoCapture サービスの登録削除 | パッチ | −1.1 | Chromium | D2 → D3a | |
| 11 | `webnn_use_litert=false`、`chrome_wide_echo_cancellation_supported=false` | GN | −1.1 | Chromium | D3a → D3b | |
| 12 | `enable_mdns`、`enable_service_discovery`、`use_gio` の無効化 | GN | −0.1 | CEF | E3b → E3c | 効果がないので不採用 |
| 13 | ロケールを ja + en-US に絞る | 配布時の選択 | −50.5 | `chrome`、CEF | 全ロケールとの差 | 一覧 1 の値はすでに適用済み。対応言語が減る |

- #3 と #5 は D3b → D3c の −25.4 を切り分けたもの(logs/164〜166)。
- #2 と #7 は同じ GN フラグ群の内訳。A → B の −36.3 = 実行ファイル −8.3 + 検証レイヤ −27.8 + pak などの差。

## 3. 削減できなかったもの

| 対象 | 状況 |
|---|---|
| PDF、印刷、印刷プレビュー | `chrome` / CEF では GN フラグで外せない(`//chrome` と `//cef` の assert、無条件の依存) |
| 拡張機能、プラグイン、GuestView | 同上 |
| Safe Browsing | `safe_browsing_mode=0` は `//chrome/browser` の依存が未解決になる |
| 通知、メッセージセンター、セッション復元(CEF) | コンパイル不可、または起動時に異常終了 |
| キャプティブポータル、ペアレンタルコントロール、Lens、Compose、スクリーン AI、音声サービス、オンデバイス翻訳 | `//chrome` の assert / 依存 |
| WebAssembly(約 4.8MB)、DevTools バックエンド(約 4.2MB)、perfetto(約 3.8MB) | 方針上残した(D3c の残り) |

- 上の 5 行は `content_shell` に替えれば `//chrome` 層ごと消える(#1)。CEF は Chrome ランタイムのみなのでこの手が使えず、E3b と D3c の差 約 129MB(配布物)が残る。

## 4. 最終値

| | 基準 | 最小構成 | 削減 |
|---|---|---|---|
| Chromium 編(配布物) | A 389.4 | D3c 182.3 | −207.1(−53.2%) |
| Chromium 編(実行ファイル) | A 309.8 | D3c 160.4 | −149.4(−48.2%) |
| CEF 編(配布物) | E1 377.5 | E3b 311.5 | −66.0(−17.5%) |
| CEF 編(実行ファイル) | E1 299.6 | E3b 261.6 | −38.0(−12.7%) |

## 5. 数値の注意

- D3c の値は、クリーンビルド対応の修正(`tools/fp/clean_fix.py`)を当てる前のバイナリのもの。修正は未使用の include とテスト用ソースだけで、CEF 側では修正前後でサイズが変わらないことを確認済み。CFI 無効でのクリーン再ビルドはしていない。
- #9 は推定値。CEF で CFI だけを切ったビルドは作っていない。
- SwiftShader(`libvk_swiftshader.so` 約 6.4MB)は実験のために残している。実機で GPU 描画を使うなら外せる。
- `icudtl.dat`(10.7MB)は手を付けていない。ロケールデータを絞れば減る余地がある(未調査)。

## 6. CEF 第 2 期(F 系列、2026-11-12 追記)

第 1 期(E3b)のあと、`//chrome` 層と `//cef` 本体、リンク設定、配布物まで踏み込んだ。詳細は `logs/cef-milestones/M6`〜`M10`。条件は 1 章と同じ(Linux x64、`is_official_build=true`、コーデックと Widevine は維持)。

### 構成別

| 構成 | 内容 | 実行ファイル | 前段との差 | 配布物合計 | 前段との差 | E1 からの累計(配布物) |
|---|---|---|---|---|---|---|
| E3b | 第 1 期の最小 | 261.6 | | 311.5 | | −66.0(−17.5%) |
| F1a | E3b + RELR 形式の再配置 + Dawn の参照除去 | 229.5 | −32.0 | 279.1 | −32.4 | −98.4(−26.1%) |
| F2 | F1a + 追加フラグ 17 個 + BlueZ 除去 + `chrome://` WebUI の登録削除 + `resources.pak` の絞り込み | 219.1 | −10.4 | 245.2 | −33.9 | −132.3(−35.0%) |
| F2b1 | F2 + Alloy スタイル専用化 | 218.5 | −0.6 | 244.6 | −0.6 | −132.9(−35.2%) |
| F4a | F2b1 + PDF / 印刷プレビュー / 印刷 / プラグイン除去(F3a)+ `optimize_for_size=true` + `resources.pak` 最小。クリーンビルド | 200.6 | −17.9 | 225.0 | −19.6 | −152.5(−40.4%) |
| F4a-dist | F4a の配布物トリム + ICU 軽量版(バイナリは同じ) | 200.6 | 0 | 216.2 | −8.8 | −161.3(−42.7%) |
| F4b | F4a + 拡張機能 / プラットフォームアプリ / ホステッドアプリ除去(F3b) | 191.2 | −9.4(F4a 比) | 215.4 | −9.6(F4a 比) | −162.1(−42.9%) |
| F4b-dist | F4b の配布物トリム + ICU 軽量版(バイナリは同じ)。**最終構成** | 191.2 | 0 | **206.6** | −8.8 | **−170.9(−45.3%)** |

- 参考: F3a 単独(E3b + PDF / 印刷プレビュー / 印刷 / プラグイン除去、別ツリー)は実行ファイル 253.4、配布物 303.0(E3b 比 −8.2 / −8.5)。F3b 単独(F3a + 拡張機能除去)は 242.4 / 291.0(F3a 比 −11.0 / −12.0)。
- どの構成も動作確認 7 項目に合格。F4a と F4b は `gn clean` からのクリーンビルドで確認済み(F4b は 51,361 ステップ、失敗 0)。

### 項目別(効果の大きい順)

| # | 削減項目 | 手段 | 効果 | 根拠 | 代償 / 注意 |
|---|---|---|---|---|---|
| 14 | 再配置テーブルを RELR 形式に | リンクオプション `-Wl,-z,pack-relative-relocs`(GN 引数を追加するパッチ 1 ファイル) | −25.6 | `.rela.dyn` 25.8 → `.relr.dyn` 0.2(F1a) | glibc 2.36 以降が必要。Chromium 編でも −12.8(D3c-cfi → 161.7、logs/199) |
| 15 | `resources.pak` の絞り込み | 配布時の後処理(`tools/fp/pakstrip.py`)+ `enable_webui_generate_code_cache=false` | −24.7(25.6 → 0.9) | F4a | `chrome://` の全ページ、DevTools フロントエンド、起動演出の音声(4.8)がなくなる |
| 16 | サイズ優先の最適化 | GN: `optimize_for_size=true`(`-Os`) | 約 −10(推定) | F2b1 − F3a の効果 → F4a | 速度は未計測。Cast / Android / Fuchsia の既定値 |
| 17 | PDF、印刷プレビュー、印刷、プラグイン | GN: `enable_pdf` / `enable_print_preview` / `enable_printing` / `enable_plugins` = false + パッチ(Chromium 21 ファイル、CEF 9 ファイル) | −8.2 | E3b → F3a | PDF 表示、`window.print()`、PrintToPDF が使えない |
| 17b | 拡張機能、プラットフォームアプリ、ホステッドアプリ | GN: `enable_extensions` / `enable_platform_apps` / `enable_hosted_apps` = false + パッチ(Chromium 342 ファイル、CEF 13 ファイル。F3a 分を含む累積) | −11.0(`-O2` 上)/ −9.4(`-Os` 上) | F3a → F3b、F4a → F4b | `chrome.*` 拡張 API、`chrome-extension://`、`--app=` が使えない。起動時の回収不可 RAM が −40MiB(常駐していた拡張機能用プロセスが消える) |
| 18 | Dawn / tint の参照除去 | パッチ 3 行(`content/utility/utility_main.cc`) | −5.7 | F1a のマップ | なし。`use_dawn=false` でも `on_device_model` の初期化が Dawn を参照していた |
| 19 | ICU データを cast 用に差し替え | 配布時の差し替え | −5.6(10.8 → 5.2) | F4a-dist | 日本語の単語分割(`Intl.Segmenter` の word、ダブルクリック選択)が 1 文字単位になる |
| 20 | 追加フラグ 17 個 + BlueZ + WebUI 登録削除 | GN + パッチ 4 ファイル | 約 −10 | F1a → F2 の実行ファイル差 | Bluetooth(BlueZ)、OpenH264 エンコーダ、unrar、XNNPACK、PDF の XFA、GWP-ASan など |
| 21 | 配布物トリム | 配布時の削除 | −3.2 | F4a → F4a-dist(ICU を除く) | `chrome_200_percent.pak`(HiDPI)、`snapshot_blob.bin`、`chrome_crashpad_handler`、テスト用 ICD |
| 22 | Alloy スタイル専用化 | パッチ 4 ファイル | −0.6 | F2 → F2b1 | Chrome スタイル(ブラウザ UI つき)が使えない。効果が小さい |

### 3 章「削減できなかったもの」の更新

| 対象 | 第 2 期の結果 |
|---|---|
| PDF、印刷、印刷プレビュー、プラグイン | **削除できた**(F3a、パッチ 30 ファイル)。第 1 期の「GN フラグで外せない」は「パッチを試していなかった」が正しい |
| 拡張機能、プラットフォームアプリ | **削除できた**(F3b / F4b、`enable_extensions_core=false` まで。パッチ 355 ファイル)|
| GuestView | 見送り(拡張機能なしの構成では glic などの WebUI が GuestView に依存する。効果 0.1MB) |
| Safe Browsing、キャプティブポータル | `gn gen` の失敗はテストターゲットの依存だけと判明(logs/181)。パッチは未着手 |
| 通知、セッション復元、メッセージセンター、音声サービス、enterprise 系 | 上流のガード漏れ。パッチは未着手 |
| autofill、sync、パスワード管理、Chrome スタイル UI(`//chrome` + `//components` で約 48MB 残る) | 点の根切りでは落ちない(M8)。buildflag がなく、面で外す手段がない |

### 最終値(CEF)

| | 基準(E1) | 第 1 期(E3b) | 第 2 期(F4b-dist) | E1 比 |
|---|---|---|---|---|
| 配布物 | 377.5 | 311.5 | **206.6** | −170.9(−45.3%) |
| 実行ファイル | 299.6 | 261.6 | **191.2** | −108.4(−36.2%) |

Chromium 編の最小(D3c 182.3)との差は、第 1 期の 129MB から 24MB まで縮んだ(F4b-dist は ICU 軽量版と RELR、`-Os` を使っており、D3c は使っていないので、同条件の比較ではない)。

## 7. CEF 第 3 期: arm64(G 系列、2026-11-13 追記)

第 2 期までの削減を arm64(`target_cpu="arm64"`、クロスコンパイル)にそのまま当てた。ソースの修正は不要だった。詳細は `logs/cef-milestones/M12`、`M13`。

| 構成 | 内容 | strip 後 | 配布物(ja + en-US) | G0 比 |
|---|---|---|---|---|
| G0 | CEF 既定(E1 と同じ args)の arm64 | 275.1MB | 366.3MB | — |
| G1 | 第 2 期の最終(F4b)の arm64 | 187.2MB | 229.1MB | −37.5% |
| G2 | G1 + Cobalt 由来の 4 引数(`enable_media_remoting` / `_rpc`、`enable_hls_demuxer`、`enable_hevc_parser_and_hw_decoder` = false)+ パッチ 2 ファイル | **186.7MB** | 228.6MB | −37.6% |
| G2-dist | G2 + F4b-dist と同じ配布物トリム + ICU 軽量版 | 186.7MB | **219.6MB** | **−40.0%** |
| G2-tv | G2-dist − SwiftShader 一式(GPU のある実機向け。WebGL はこの実験環境では使えない) | 186.7MB | **196.0MB** | **−46.5%** |

- 本体(strip 後)は x64 より小さい: x64 E1 299.6 / F4b 191.2MB に対し、arm64 G0 275.1 / G1 187.2MB。
- **arm64 では SwiftShader が x64 の 3 倍**(未 strip 22.8MB、strip 後 15.9MB。x64 は 5.4MB)。Subzero(軽量 JIT)が arm64 に対応しておらず、LLVM 10 のバックエンドが丸ごと入るため(`third_party/swiftshader/src/Reactor/reactor.gni:13`)。GPU のある実機では SwiftShader 一式を外せるので、arm64 ではこの効果が大きい(−23.6MB、G2-dist → G2-tv)。
- Cobalt の ROM 項目(G1 → G2)は −0.5MB。第 1・2 期で大きな機能を外し終えていたので、残っていたのは小物だけ。`angle_enable_vulkan=false` は SwiftShader と両立しないので適用せず、map からの見積もりは約 1.1MB。
- G0 の配布物には `libVkLayer_khronos_validation.so`(Vulkan の検証レイヤ、26.3MB)が含まれる。第 1 期で外したものと同じ。
