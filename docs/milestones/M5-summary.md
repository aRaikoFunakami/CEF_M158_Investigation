# M5: CEF 編の総まとめ

作成: 2026-11-12 02:30 JST、確定: 03:45 JST(E3c の結果を反映。最終構成は E3b)

## 条件

- CEF 8127 ブランチ(`6ee3fb965`)+ Chromium 158.0.8127.18。Chrome ランタイム、Alloy スタイル(`cefsimple --use-alloy-style`)。
- Linux x64、`is_official_build=true`、シンボルなし、`proprietary_codecs=true`、`ffmpeg_branding="Chrome"`、Widevine 有効(CDM は非同梱)。
- ビルド環境: Apple Container(ubuntu 24.04 amd64、Rosetta、24 CPU / 64GB)。ninja(`use_siso=false`)+ 停止検知ラッパー。
- 計測: strip 後の `libcef.so` + `cefsimple`、配布物(pak、ロケール、ICU、V8 スナップショット、ANGLE / SwiftShader、crashpad ハンドラ)、全プロセスの PSS 合計(3 回の中央値)。
- 合格条件: 機能検出、Service Worker、WebSocket、MP4、MSE、EME(ClearKey)、YouTube 1080p の 7 項目。

## 結果

| 構成 | 内容 | strip 後 | 配布物 ja + en | PSS blank | PSS YouTube トップ | PSS 1080p 再生中 | 動作確認 |
|---|---|---|---|---|---|---|---|
| E1 | CEF 既定のリリース | 299.6MB | 377.5MB | 588.0MB | 1,487.9MB | 1,976.4MB | 7/7 |
| E2 | + GN フラグ 17 個 | 291.6MB | 342.0MB | 565.0MB | 1,407.6MB | 1,890.5MB | 7/7 |
| E3a | + GN フラグ 17 個(CFI 無効を含む) | 273.5MB | 323.5MB | 537.9MB | 1,375.5MB | 1,826.7MB | 7/7 |
| E3b | + Blink モジュール 41 個の削除パッチ | 261.6MB | 311.5MB | 529.2MB | 1,337.5MB | 1,813.5MB | 7/7 |
| (参考)E3c | E3b + `enable_mdns` / `enable_service_discovery` / `use_gio` を無効化 | 261.5MB | 311.4MB | 未計測 | 未計測 | 未計測 | 7/7 |
| E1 → E3b | | −38.0MB(−12.7%) | −66.0MB(−17.5%) | −58.8MB(−10.0%) | −150.4MB(−10.1%) | −162.9MB(−8.2%) | |

- 配布物の減少 66MB のうち 27MB は本体以外で、ほぼすべてが Vulkan 検証レイヤ `libVkLayer_khronos_validation.so`(27.3MB)。E2 の `dawn_enable_vulkan_validation_layers=false` で同梱されなくなった。
- E3c は 90 分の全体再ビルドで −0.1MB。不採用(logs/162)。
- Widevine CDM(21MB)は配布物に含まれない。初回起動時にコンポーネント更新でプロファイルへ取得され、再起動後に有効になる。
- メモリは SwiftShader(ソフトウェア描画)+ Rosetta 上の値。実機の GPU 描画では絶対値が大きく変わる。構成間の差として読む。

## Chromium 編との対比(strip 後)

| 段階 | Chromium 編(159) | CEF 編(158) |
|---|---|---|
| 基準 | A `chrome` 309.8MB | E1 299.6MB |
| GN フラグのみ | B `chrome` 301.5MB | E2 291.6MB / E3a 273.5MB |
| `content_shell` に替える | A' 211.9MB / C 203.9MB | (不可) |
| Blink モジュール削除まで | D3c 160.4MB | E3b 261.6MB |

- CEF の基準は `chrome` より 10MB 小さい(CEF 既定で BackupRefPtr と PartitionAlloc-as-malloc が無効、など)。
- Chromium 編で最も効いたのは「`chrome` をやめて `content_shell` にする」(−98MB)。CEF は Chrome ランタイムのみになったので、この手が使えない。
- E3b と D3c の差 約 100MB が `//chrome` 層の重さ。Alloy スタイルは Chrome の UI を表示しないだけで、コードはすべてリンクされる。

## 切れたもの / 切れなかったもの

切れたもの:

- GN フラグ 34 個(E2 の 17 + E3a の 17)。CUPS、VR / OpenXR、リモーティング、オンデバイスモデル、WebNN(TFLite / LiteRT)、libaom、Kerberos、Paint Preview、クレジットページ、Dawn、CFI、Wayland、GTK、VA-API、PipeWire、JPEG XL、IAMF、Reporting API、HSTS プリロードリストなど。
- Blink モジュール 41 個(WebRTC、MediaStream、MediaRecorder、Bluetooth、USB、HID、Serial、NFC、決済、通知、プッシュ、WebXR、センサー、Web MIDI、音声認識、FedCM など)。Chromium 編のパッチが、reject 7 ファイルの手当てとスタブ 1 個で移植できた。

切れなかったもの(GN フラグでは不可):

| 対象 | 止めているもの |
|---|---|
| PDF、印刷、印刷プレビュー | `//cef/BUILD.gn` の `assert(enable_print_preview)`、CEF が無条件に依存 |
| 拡張機能、プラグイン、GuestView | `//ui/webui`、`//pdf`、`//extensions` の assert |
| Widevine | `//cef/BUILD.gn` の `assert(enable_widevine)`(今回は必要なので外す対象でもない) |
| Safe Browsing | `//chrome/browser` 各所の依存が未解決になる |
| 通知、メッセージセンター、セッション復元 | コンパイル不可、または起動時に異常終了 |
| キャプティブポータル、証明書ビューア、ペアレンタルコントロール、Lens、Compose、スクリーン AI、音声サービス、オンデバイス翻訳 | `//chrome` の assert / 依存 |

残っている大物(E3b のシンボル内訳、text + data 252.5MB): `//chrome` 層 37.4MB、blink 33.2MB、v8 26.2MB、base 10.0MB、content 8.3MB、rust 5.5MB、mojo 5.1MB、extensions 4.9MB、autofill 3.1MB、tint 3.0MB、net 3.0MB、perfetto 2.5MB、dawn 1.6MB。

## 途中で分かったこと(Qiita 用のメモ)

1. **siso の停止**: この環境では siso がときどき停止する(子プロセスがゾンビのまま回収されない)。止まった siso 本体が CPU を使い続けるので、CPU 時間で見る検知は騙される。ninja(`use_siso=false`)に切り替えて回避。根本原因は未特定。
2. **Rosetta 上のプロセス照合**: CEF のプロセスは `/proc/<pid>/exe` が `/run/rosetta/rosetta` を指す。`argv[0]` で照合しないと kill も計測もできない。
3. **CEF の子プロセス**: zygote から fork したレンダラ / GPU は cmdline が `--type=zygote` のまま。PSS 集計で zygote を除外すると大半が漏れる。
4. **コーデック**: CEF の公式配布バイナリと違い、`proprietary_codecs=true` + `ffmpeg_branding="Chrome"` でビルドすれば H.264 / AAC が入る。削減フラグでコーデックを落としていないことは実機で確認した(AV1 1080p60 を再生)。
5. **フラグの 4 段階**: `gn gen` 通過 → コンパイル通過 → 起動 → 動作確認は別物。E3a では 20 個中 3 個が後段で落ちた。
6. **YouTube の間欠エラー**: "Something went wrong" が構成に関係なく出る(Chromium 編の `content_shell` でも)。止まった回はメモリが 50〜100MB 低く出るので、再生中であることを確認してから数える必要がある。
7. **一過性の Rosetta エラー**: `rosetta error: no code fragment associated with the given arm pc` でビルドのアクションが落ちることがある。再実行で通る。

8. **増分ビルドの罠**: モジュールを削るパッチは、増分ビルドだと `gen/` に残った古い生成ヘッダで通ってしまう。Chromium 編のクリーンビルドで発覚し、5 ファイルを追加修正した(`tools/fp/clean_fix.py`、`logs/patches/e3b-final-clean.patch`)。サイズと動作確認の結果は変わらない。

## 限界と残る余地

- CEF で 260MB を大きく割るには、`//chrome` 層と `//cef` 本体の書き換えが必要(PDF / 印刷 / 拡張機能の assert と依存を外す、Safe Browsing を外す、WebUI ページ群を外すなど)。CEF の標準パッチと衝突し、CEF のバージョン更新のたびに追従が要る。
- フットプリントが最優先なら、CEF ではなく content 層に直接載せる(Chromium 編 D3c の 160MB、Cobalt と同じ発想)ほうが 100MB 小さい。CEF を選ぶ理由は API の安定性と組み込みやすさになる。
- 未実施: E0(158 の `content_shell`、バージョン差の確認用)、フラグ別の寄与の切り分け、ARM 実機 / GPU 描画でのメモリ。
