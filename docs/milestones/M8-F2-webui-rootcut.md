# M8: F2 WebUI の根切りと `resources.pak` の絞り込み

作成: 2026-11-12 14:55 JST。ログ: logs/183〜185、187、189〜196。

## 結果

| | E3b(第 1 期) | F1a | **F2** | F2b1(Alloy 専用化) |
|---|---|---|---|---|
| strip 後(`libcef.so` + `cefsimple`) | 261.6MB | 229.5MB | **219.1MB** | 218.5MB |
| `resources.pak` | 25.6MB | 25.6MB | **2.2MB** | 2.2MB |
| 配布物(ja + en-US) | 311.5MB | 279.1MB | **245.2MB** | 244.6MB |
| E3b 比(配布物) | | −32.4MB | **−66.3MB(−21.3%)** | −66.9MB |
| 動作確認 | 7/7 | 7/7 | 7/7 | 7/7 |
| 起動時 RAM: 回収不可 | 412.0MiB | 409.0MiB | 404.1MiB | (未計測) |
| 起動時 RAM: `Pss_File` | 197.7MiB | 173.2MiB | 170.4MiB | (未計測) |

F1a → F2 の内訳(実行ファイル −10.4MB、`resources.pak` −23.4MB):

- 追加フラグ 17 個(F1b)と WebUI 登録の削除(F2a)を同じビルドで入れたので、実行ファイルの −10.4MB は両者の合計。マップで見ると `chrome/browser/ui/webui` が 3.2 → 0.7MB、`device`(Bluetooth)が 1.96 → 0.74MB、`third_party/pdfium`(XFA)が 5.0 → 3.4MB、`xnnpack` 1.3MB が消滅、`openh264` 0.4MB が消滅。
- `resources.pak`: ビルド出力は 25.6 → 22.0MB(WebUI のコードキャッシュ生成を止めた分)。そこから `pakstrip.py` で 2.2MB。

保存先: `/root/fp/builds/F2`、`/root/fp/builds/F2b1`。スクリーンショット: `logs/screenshots/F2-func-*.png`、`F2-nav-*.png`、`F2b1-func-*.png`。

## 1. `resources.pak` の絞り込み(`tools/fp/pakstrip.py`)

`resources.pak` 25.6MB の中身を、生成元の grd ファイル別に集計した(`tools/fp/pakinfo.py`、logs/184)。

| 生成元 | MB | 中身 |
|---|---|---|
| `chrome/browser/browser_resources.grd` | 5.0 | うち 4.8MB が**起動演出の音声**(`IDR_INTRO_SOUND_*`、FLAC 6 本) |
| DevTools フロントエンド | 4.8 | `devtools://` の UI |
| WebUI のコードキャッシュ | 2.8 | V8 のコンパイル済みキャッシュ |
| 各 WebUI(設定、新しいタブ、intro、パスワード、履歴など約 200 種) | 約 11 | `chrome://` ページの HTML / JS / CSS |
| Web ページの表示に要るもの(Blink、エラーページ、content、net、CEF) | 1 未満 | |

- 方法: 配布物を作る段階で、残す grd を正規表現の許可リストで選び、`.pak` を作り直す。GN のパッチではないので再ビルドなしで試せる。
- 2 つのモード:
  - `--with-pdf`: PDF ビューアと印刷プレビュー、それらが使う `chrome://resources` の共有部品(Polymer、Lit、cr_elements)を残す。E3c のビルドで 3.6MB、F2 で 2.2MB。
  - 最小: それも落とす。E3c のビルドで **0.9MB**。PDF を buildflag で外した構成(F3a 以降)向け。
- どちらも E3c のバイナリと組み合わせて動作確認 7/7(logs/185)。
- 落としたことで使えなくなるもの: `chrome://` の全ページ、`devtools://` のフロントエンド(リモートデバッグのプロトコル自体は使える。動作確認は CDP 経由で行っている)。

## 2. WebUI 登録の削除(`tools/fp/f2_patch.py`、2 ファイル 5 行)

- `chrome_browser_main.cc` の `RegisterChromeWebUIConfigs()` / `RegisterChromeUntrustedWebUIConfigs()` の呼び出しを削除。
- `chrome_content_browser_client_receiver_bindings.cc` の `PopulateChromeWebUIFrameBinders()`、`PopulateTrustedChromeWebUIFrameInterfaceBrokers()`、`PopulateUntrustedChromeWebUIFrameInterfaceBrokers()` の呼び出しを削除。
- 登録関数の定義は残るが、呼び出し元がなくなるのでリンカの GC で各 WebUI のコントローラ、ハンドラ、Mojo バインダが落ちる。
- 確認(logs/193): `chrome://version`、`chrome://settings`、`chrome://history`、`chrome://gpu` を開くと CEF のエラーページ(`ERR_INVALID_URL` / `ERR_FAILED`)になり、プロセスは落ちない。その後の通常ページも表示できる。

## 3. 追加フラグ(F1b)

`gn gen` を通った 26 個を一度に入れ、通らなかったものを落としていった。ビルド 5 回。

| フラグ(= false) | 結果 | 原因 |
|---|---|---|
| `use_bluez` | 採用(パッチ 2 ファイル) | chrome 側が BlueZ の初期化 / 終了 / メトリクスを無条件に呼ぶ。`use_bluez` は `device/bluetooth/BUILD.gn` 内の引数で `//chrome` から見えない |
| `media_use_openh264`、`safe_browsing_use_unrar`、`angle_has_frame_capture`、`enable_gwp_asan`、`enable_webui_bookmarks`、`enable_webui_contextual_tasks_composebox`、`enable_webui_generate_code_cache`、`enable_glic_internal_resources`、`structured_metrics_enabled`、`choice_screen_in_chrome`、`headless_enable_commands`、`enable_memory_coordinator_internals`、`glslang_enable_hlsl`、`build_tflite_with_xnnpack`、`produce_v8_compile_hints`、`pdf_enable_xfa` | 採用(パッチなし) | |
| `enable_gpu_channel_media_capture` | 不採用 | include 漏れ(コンパイル)を直しても、V4L2 キャプチャ側の参照がリンクで残る |
| `enable_media_remoting` | 不採用 | `CastRemotingConnector` の参照が 2 ファイルに残る(リンク) |
| `enable_pdf_translation` | 不採用 | `content_translate_driver.cc` の参照が残る(リンク) |
| `enable_pdf_ink2`、`enable_pdf_save_to_drive` | 不採用 | PDF ビューアの TypeScript が tsc(未使用関数)、eslint(require-await)で落ちる |
| `enable_browser_speech_service` | 不採用 | `#error "No speech recognition service factory on this platform."` |
| `enterprise_proxy` | 不採用 | `PrefProxyConfigTrackerImpl` のコンストラクタ不一致 |
| `enterprise_content_analysis`、`enterprise_local_content_analysis` | 不採用 | `download_bubble_*` の 9 箇所が未ガード |

不採用の 8 個はどれも「上流のガード漏れ」で、パッチを書けば通せる。効果が小さい見込み(各 1MB 未満)なので深追いしなかった。

## 4. Alloy スタイル専用化(F2b1、`tools/fp/f2b_patch.py`、4 ファイル)

Chrome スタイル(ブラウザ UI つき)のウィンドウを作る 4 箇所をスタブ化した。

- `chrome/browser/ui/views/frame/browser_window_factory.cc`: `BrowserWindow::CreateBrowserWindow()` を `NOTREACHED()` に。
- `cef/libcef/browser/views/browser_view_impl.cc`: `new ChromeBrowserView` を削除。
- `cef/libcef/browser/views/widget.cc`: `new ChromeBrowserWidget` を削除。
- `cef/libcef/browser/chrome/views/toolbar_view_impl.cc`: `new CefToolbarViewView` を削除。

結果は **−0.6MB だけ**(219.1 → 218.5MB)。`chrome/browser/ui/views` は 5.12 → 4.79MB。動作確認は 7/7。

`--why-live` で理由を見ると(logs/195)、`TabStrip` や `BrowserView` はウィンドウ生成以外にも数千箇所から参照されている(例: 自動入力のポップアップ → 設定ページを開く → `Navigate()` → `Browser::Create`)。UI クラスは「作る場所」を 1 つ潰しても、メンバ関数を直接呼ぶコードがあちこちに残る。

## 分かったこと

1. 配布物の 8% は `chrome://` ページのリソースだった。TV 向けには丸ごと不要で、後処理だけで落とせる。コードを 1 行も変えなくても −22MB。
2. 一括登録箇所を切る「根切り」は、WebUI のように登録が 1 箇所に集まっていて、他から直接参照されない機能にはよく効く(`chrome/browser/ui/webui` のコードが 3.2 → 0.7MB)。
3. `//chrome` の UI、autofill、sync、パスワード管理のように相互参照が密な機能には、点の切断は効かない。buildflag で面ごと外す(ライン B)か、全体に効く手段(最適化レベル)が要る。
4. 上流で検証されていないフラグの組み合わせは、`gn gen` を通ってもコンパイルやリンクで落ちる。26 個中 8 個が落ちた。

## 次

- `optimize_for_size=true`(`-Os`)を F3a と合わせてクリーンビルド(M10 の F4a、logs/198)。
