# M21: CEF と Cobalt shell の機能差分、//chrome 層がどれだけ残っているか

作成: 2026-11-13(ユーザー指示: Cobalt 27.lts のソースを取得して Cobalt 専用 shell の API を調べ、CEF との差分を表にして抜けを 1 つずつ確認する。そのうえで、多数の機能を削ったのに CEF + //chrome が約 100MB 残る理由と、そこから約 100MB 削れるかを調べる)。

ログ: logs/455〜462。Cobalt の先行調査: https://github.com/aRaikoFunakami/Cobalt_27_LTS_Investigation(`cobalt-inv/Cobalt_27_LTS_Investigation`)。

## 0. 結論

1. **Cobalt shell は「API を持たない YouTube 専用アプリ」、CEF は「汎用の埋め込み API」**。Cobalt には CEF の `include/` に当たる公開 C/C++ API がない。アプリが使える面は、Starboard(プラットフォーム移植)、コマンドラインと feature フラグ、JS 向けの独自 API(`window.h5vcc.*` など 13 種)だけ。ダウンロード、ファイル選択、権限、通知、HTTP 認証、クライアント証明書、JS ダイアログ、コンテキストメニュー、オフスクリーン描画は、どれも「なし」(`nullptr` か空の実装)。
2. **CEF + //chrome 層で残っているのは約 45〜55MB で、約 100MB ではない**。G2(arm64、strip 後 186.7MB)と Cobalt(x64、108.8MB)の差は 77.9MB。そのうち //chrome 層と CEF 本体が約 45〜55MB、残りの約 25〜30MB は Cobalt が //chrome 以外で削っているもの(デコーダを別の .so に分離、ANGLE の Vulkan バックエンド、tflite、Blink のバインディング除外など)。
3. **CEF のままでは約 100MB は削れない**。libcef は //chrome の中核クラス(`ChromeMainDelegate`、`ChromeContentBrowserClient`、`Profile` など)を継承して動くので、//chrome 層を丸ごとは外せない。CEF のまま追加で削れる見込みは **約 15〜25MB**(推定、未検証)。Cobalt 並み(約 110MB)にするには、CEF をやめて content 層の上に専用の shell を作る(Cobalt と同じ方式)必要がある。

## 1. 調べた対象

| 項目 | 値 |
|---|---|
| Cobalt | youtube/cobalt タグ `27.lts.13`(commit 03973ab2、Chromium 138.0.7204.311)。`cobalt/` と `third_party/blink/renderer/modules/cobalt/` だけを `--depth 1 --filter=blob:none --sparse` で取得(logs/455、`cobalt-inv/cobalt-src`) |
| CEF | 8127(Chromium 158.0.8127.18)、素のソースはコンテナの `/root/cef2/chromium/src/cef`。縮小ビルドのパッチは `logs/patches/f4b-cef.patch`、`f4b.patch` |
| 縮小ビルド | G2(arm64、F4b 相当 + Cobalt 由来の 4 引数)。マップは `/root/fp/libcef-G2.map` |

## 2. 機能の差分表

凡例: ○ = 使える、△ = 一部 / 条件つき、× = 使えない、? = 未確認。「CEF 縮小」は G2 / F4b(Alloy スタイル専用、PDF・印刷・拡張機能・WebUI などを削除済み)。

### 2-1. 埋め込みの仕組み

| 機能分類 | CEF(API) | CEF 既定 | CEF 縮小 | Cobalt shell | 根拠 |
|---|---|---|---|---|---|
| 公開 C/C++ 埋め込み API | `include/` 88 ヘッダ + views 21 + wrapper 12 | ○ | ○ | **×**(`include/` も EXPORT もない。成果物は実行ファイルのみ) | logs/459、logs/460、cobalt/BUILD.gn:95-112 |
| 起動 / プロセスモデル | cef_app、cef_browser_process_handler、cef_render_process_handler、cef_command_line、cef_process_util | ○ | ○ | △ `main` → `SbRunStarboardMain`。設定はコマンドラインのみ | cobalt/app/cobalt.cc:19-20 |
| プラットフォームのイベント | (OS のウィンドウ / イベントを CEF が処理) | ○ | ○ | ○ Starboard の `SbEventHandle`(Start、Blur、Focus、Conceal、Freeze、Stop、Input、ディープリンク、LowMemory など) | cobalt/app/sb_event_handle.cc、app_event_delegate.cc:219-272 |
| ブラウザ(ウィンドウ)の生成 | cef_browser(CreateBrowser)、cef_client、cef_life_span_handler | ○ | △ Alloy スタイルのみ。`runtime_style` を明示しないと Chrome スタイル扱いで落ちる | △ `Shell` を作るだけ。タブの概念なし | cef: browser_host_create.cc:170-178、cobalt/shell/browser/shell.h:136 |
| Views フレームワーク | views/*.h(21 個) | ○ | △ Alloy スタイルのみ | × | logs/459 |
| Chrome スタイル UI(タブ、ツールバー、メニュー) | cef_command_handler(OnChromeCommand など) | ○ | × | × | f4b-cef.patch:465-485 |
| オフスクリーン描画(OSR) | cef_render_handler、cef_accessibility_handler、SendXxxEvent | ○ | ○ | ×(描画は Starboard の SbWindow へ) | logs/460(`windowless`、`OffScreen` は 0 件)、cobalt_content_browser_client.cc:774 |
| ポップアップ / 新しいウィンドウ | cef_life_span_handler(OnBeforePopup) | ○ | ○ | △ 新しい Shell を作る。止める仕組みも UI もない | shell.cc:865-891,947-1003 |
| ネイティブ ↔ JS(汎用) | cef_v8、cef_dom、cef_process_message、cef_shared_memory_region、cef_shared_process_message_builder、wrapper/cef_message_router | ○ | ○ | △ 汎用の口はない。`H5vccPlatformService`(名前で引く汎用のバイト列チャネル)が近い。追加はソースの fork で mojom + IDL を足す | h5vcc_platform_service.mojom:22-53 |
| ネイティブ ↔ JS(固定機能) | — | — | — | ○ `window.h5vcc.*` 11 種 + DialServer + onScreenKeyboard(3 章) | logs/460 |
| タスク / スレッド / ユーティリティ | cef_task、cef_thread、cef_waitable_event、cef_parser、cef_xml_reader、cef_zip_reader、cef_stream、cef_file_util、cef_path_util、cef_i18n_util、cef_image、cef_values、cef_registration、cef_id_mappers、cef_string_visitor、cef_callback、cef_base | ○ | ○ | ×(アプリに公開する API がない) | logs/459 |

### 2-2. ナビゲーションとページの扱い

| 機能分類 | CEF(API) | CEF 既定 | CEF 縮小 | Cobalt shell | 根拠 |
|---|---|---|---|---|---|
| ナビゲーション / ロードの通知 | cef_load_handler、cef_frame、cef_frame_handler、cef_navigation_entry、cef_display_handler、cef_focus_handler | ○ | ○ | △ 内部で処理(アプリへの通知 API なし)。HTTPS と CSP を強制(gold では既定 ON) | cobalt_content_browser_client.cc:411-417、cobalt_secure_navigation_throttle.cc |
| リクエストの横取り / 独自スキーム | cef_request_handler、cef_resource_request_handler、cef_resource_handler、cef_response_filter、cef_scheme、cef_urlrequest、cef_request、cef_response | ○ | ○(`chrome-extension://` を除く) | △ 固定。`h5vcc-embedded://`(埋め込みリソース)だけ | shell_content_browser_client.cc:702-770 |
| オリジンのホワイトリスト | cef_origin_whitelist | ○ | ○ | × | |
| JS ダイアログ(alert など) | cef_jsdialog_handler | ○ | ○ | ×(表示を抑止) | shell_javascript_dialog_manager.cc:43,51(logs/461 で確認) |
| beforeunload | cef_jsdialog_handler | ○ | ○ | △ 常に続行 | shell_javascript_dialog_manager.cc:55-76 |
| コンテキストメニュー | cef_context_menu_handler、cef_menu_model(_delegate) | ○ | ○ | ×(空の実装) | shell_web_contents_view_delegate_views.cc:36-38(logs/461) |
| キーボード / 入力 | cef_keyboard_handler、cef_input_handler、cef_input_event_utils | ○ | ○ | △ Starboard の入力イベントのみ | app_event_delegate.cc |
| IME / オンスクリーンキーボード | CefBrowserHost::Ime*(OSR 用) | ○ | ?(GTK なしでのウィンドウモードは未確認) | △ `window.onScreenKeyboard`(tvOS のみ既定 ON) | on_screen_keyboard.mojom:38-65、cobalt.gni:33 |
| ドラッグ&ドロップ | cef_drag_handler、cef_drag_data | ○ | ○(OSR)/ ? | × | |
| ページ内検索 | cef_find_handler(Find) | ○ | ○ | ×(`FindReply` の実装 0 件) | logs/460 |
| ズーム | CefBrowserHost::SetZoomLevel | ○ | ○ | ×(`CreateZoomLevelDelegate` が nullptr) | logs/460 |
| 全画面 / ポインタロック | cef_display_handler(OnFullscreenModeChange) | ○ | ○ | ○ | shell.cc:1005-1058 |
| エラーページ | cef_load_handler(OnLoadError) | ○ | ○ | ○ 400〜599 で表示 | shell_content_browser_client.cc:669-671 |
| `chrome://` ページ | (LoadURL) | ○ | ×(登録とリソースを削除) | ×(スキームはあるが WebUI なし) | rom-size-reduction.md 6 章 |
| 印刷 | cef_print_handler、cef_print_settings、Print | ○ | × | × | f4b-cef.patch:416-461、linux_common.gn:53 |
| PDF 出力 / PDF 表示 | PrintToPDF、cef_pdf_print_callback | ○ | ×(常に失敗を返す) | × | f4b-cef.patch:584-596、logs/460(`PrintToPDF` 0 件) |
| プラグイン | (`<embed>`) | △ | × | ×(`enable_ppapi=false`) | linux_common.gn:93 |
| 拡張機能 | (8127 では API 自体なし) | △(内部のみ) | × | × | logs/459(extension ヘッダなし)、shell_browser_context.cc(`GetGuestManager` nullptr) |
| スペルチェック | ReplaceMisspelling、AddWordToDictionary | ○ | ?(chrome の spellcheck は残存) | × | logs/460(`Spellcheck` 0 件) |
| 自動入力 / パスワード | (内部機能。API なし) | ○ | △ コードは残る(削れない、5 章) | × | logs/460(`Autofill` 0 件) |

### 2-3. ネットワーク、ストレージ、権限

| 機能分類 | CEF(API) | CEF 既定 | CEF 縮小 | Cobalt shell | 根拠 |
|---|---|---|---|---|---|
| Cookie | cef_cookie(CefCookieManager) | ○ | ○ | △ 永続化のみ。サードパーティ Cookie は固定でブロック。API なし | cobalt_content_browser_client.cc:505(logs/461) |
| リクエストコンテキスト / 設定 | cef_request_context、cef_request_context_handler、cef_preference | ○ | ○(実体は chrome の Profile / PrefService) | △ BrowserContext は 1 つ、パーティションも既定の 1 つ | cobalt_content_browser_client.cc:482-492 |
| ストレージ / キャッシュの設定 | CefSettings(cache_path など) | ○ | ○ | ○ HTTP キャッシュ、コードキャッシュ 5MB、クォータを固定値で設定 | cobalt_content_browser_client.cc:350-376 |
| 閲覧データの削除 | CefRequestContext::ClearHttpAuthCredentials など | ○ | ○ | ×(`GetBrowsingDataRemoverDelegate` が nullptr) | logs/460 |
| ダウンロード | cef_download_handler、cef_download_item、StartDownload | ○ | ○ | ×(`GetDownloadManagerDelegate` が nullptr) | shell_browser_context.cc:102-103 |
| ファイル選択 | cef_dialog_handler、RunFileDialog | ○ | △ 独自ハンドラは可。既定 UI は ? | ×(content の既定で即キャンセル) | logs/460(`RunFileChooser` 0 件)、content の既定 web_contents_delegate.cc:256-260(logs/461) |
| 権限 | cef_permission_handler | ○ | △ 残っている権限のみ | ×(`GetPermissionControllerDelegate` が nullptr) | shell_browser_context.cc:133-134 |
| マイク / カメラ | OnRequestMediaAccessPermission | ○ | ×(getUserMedia を Blink から削除) | △ 音声キャプチャのみ | shell.cc:1173-1214(logs/461) |
| 位置情報 | (権限経由) | ○ | △ | × | shell_content_browser_client.cc:340-341 |
| 通知 / プッシュ通知 | (Web API) | ○ | ×(削除) | ×(nullptr) | shell_browser_context.cc:114-120 |
| Background Sync / Fetch | (Web API) | ○ | ○ | ×(nullptr) | shell_browser_context.cc:142-147 |
| HTTP 認証 | cef_auth_callback(GetAuthCredentials) | ○ | ○ | ×(`CreateLoginDelegate` が nullptr) | shell_content_browser_client.cc:511-529 |
| 証明書 | cef_ssl_info、cef_ssl_status、cef_x509_certificate、OnCertificateError、OnSelectClientCertificate | ○ | ○ | ×(クライアント証明書を選ばない。例外の許可なし) | shell_content_browser_client.cc:411-424 |
| プロキシ | CefRequestContext の proxy 設定、コマンドライン | ○ | ○ | △ `--proxy-server`。**gold では無効** | cobalt_content_browser_client.cc:566-569(logs/461) |
| User-Agent | CefSettings.user_agent | ○ | ○ | △ 固定。上書きは official 以外のみ | cobalt_content_browser_client.cc:452-466(logs/461) |
| HTTP サーバ | cef_server | ○ | ○ | × | |
| Origin Trials | (内部) | ○ | ○ | ×(nullptr) | logs/460 |

### 2-4. メディア、開発支援、その他

| 機能分類 | CEF(API) | CEF 既定 | CEF 縮小 | Cobalt shell | 根拠 |
|---|---|---|---|---|---|
| メディア再生 / MSE | (Web API) | ○ | ○ | ○ Starboard 経由。MSE の拡張(`writeHead` など) | source_buffer_extensions.idl |
| EME / DRM | (Widevine CDM を後から取得) | ○ | ○ | ○ Widevine、`com.youtube.widevine.l3`、プラットフォーム DRM(Starboard) | cobalt_content_renderer_client.cc:299-357 |
| 動画の重ね合わせ(パンチアウト) | — | — | — | ○ `VideoGeometrySetter`(動画の位置を Starboard に渡す) | video_geometry_setter.mojom:53-57 |
| 音声の取得 | cef_audio_handler | ○ | ○(見込み) | × | |
| 音声ミュート | SetAudioMuted | ○ | ○ | × | |
| Picture-in-Picture | (Web API) | ○ | ○ | △ Android のみ | shell.cc:1148-1163 |
| メディアルーター(Cast) | cef_media_router | ○ | ?(chrome の Cast / DIAL 探索を使う) | ×(受け手側の DIAL サーバは tvOS のみ) | cobalt.gni:37 |
| DevTools の UI | ShowDevTools | ○ | ×(フロントエンドを削除) | × | devtools_window_runner.cc:22(logs/462) |
| DevTools のプロトコル | ExecuteDevToolsMethod、cef_devtools_message_observer、remote_debugging_port | ○ | ○ | △ 開発ビルドのみ(gold は nullptr) | cobalt_content_browser_client.cc:402-409(logs/461) |
| トレース | cef_trace | ○ | ○ | ? | |
| クラッシュレポート | cef_crash_util | ○ | ×(ハンドラを配布物から除去) | ○ crashpad + `h5vcc.crashLog` | shell_content_browser_client.cc:314-337 |
| タスクマネージャ | cef_task_manager | ○ | ? | × | |
| コンポーネント更新 | cef_component_updater | ○ | ○ | △ Evergreen の自己更新(`h5vcc.updater`) | cobalt/updater/ |
| リソースバンドル | cef_resource_bundle、cef_resource_bundle_handler | ○ | △(resources.pak を 0.9MB に削減) | △ `cobalt_shell.pak` | |
| 無応答の検知 | cef_unresponsive_process_callback | ○ | ○ | ○ HangWatcher(アプリに API はない) | features.cc:42-72 |
| アクセシビリティ | cef_accessibility_handler | ○ | ○ | △ TTS の on/off 通知のみ | h5vcc_accessibility.mojom |
| メトリクス | — | — | — | ○ UMA を JS に渡す(送信はアプリ) | cobalt_metrics_log_uploader.h:31-41 |
| ライフサイクル(TV 向け) | — | — | — | ○ freeze / resume、スプラッシュ画面、アプリ終了(`h5vcc.system.exit`) | cobalt_lifecycle.mojom、h5vcc_system.mojom:49-52 |
| ディープリンク | (アプリ側で処理) | — | — | ○ `h5vcc.runtime` | h5vcc_runtime.mojom |
| 実験設定(Finch 相当) | — | — | — | ○ `h5vcc.experiments` | h5vcc_experiments.mojom:29-36 |
| メモリの計測 / 低メモリ通知 | — | — | — | ○ `CobaltPerformance`、`h5vcc.memory` | performance.mojom、h5vcc_memory.mojom |

### 2-5. ページから見える Web API(ビルドで外したもの)

| Web API | CEF 縮小 | Cobalt |
|---|---|---|
| WebRTC、getUserMedia、MediaRecorder | × | ×(getUserMedia は音声のみ) |
| Bluetooth、USB、HID、Serial、NFC | × | × |
| WebXR、WebGPU、WebNN、built-in AI | × | × |
| Payments、Notifications、Push | × | ×(API は残るが委譲先なし) |
| Privacy Sandbox(Topics、Shared Storage、FedCM など) | ○(残っている) | × |
| WebGL | ○(SwiftShader あり)/ G2-tv は × | ○(ANGLE の GLES) |
| WebAssembly | ○ | ○ |

## 3. Cobalt の JS 向け独自 API(全 19 mojom、25 IDL)

| JS からの入口 | mojom | 内容 |
|---|---|---|
| `h5vcc.crashLog` | crash_annotator | クラッシュ時の注釈 |
| `h5vcc.accessibility` | h5vcc_accessibility | TTS の状態 |
| `h5vcc.experiments` | h5vcc_experiments | 実験設定の適用 |
| `h5vcc.memory` | h5vcc_memory | 低メモリ通知 |
| `h5vcc.metrics` | h5vcc_metrics | UMA ヒストグラムの受け取り |
| `h5vcc.nativeStability` | h5vcc_native_stability | ネイティブのクラッシュ報告(Evergreen / AndroidTV) |
| `H5vccPlatformService` | h5vcc_platform_service | 名前で引く汎用チャネル(プラットフォーム独自機能) |
| `h5vcc.runtime` | h5vcc_runtime | ディープリンク |
| `h5vcc.settings` | h5vcc_settings(2 つ) | 設定値の変更 |
| `h5vcc.storage` | h5vcc_storage | crashpad の DB 削除、書き込み試験 |
| `h5vcc.system` | h5vcc_system | 広告 ID、端末名、画面サイズ、終了、スプラッシュを消す |
| `h5vcc.updater` | h5vcc_updater | 自己更新のチャネル |
| `DialServer` | in_app_dial | アプリ内 DIAL サーバ(tvOS) |
| `window.onScreenKeyboard` | on_screen_keyboard | オンスクリーンキーボード |
| (内部) | cobalt_lifecycle、performance、platform_window_provider、video_geometry_setter | ライフサイクル、メモリ計測、SbWindow、動画の重ね合わせ |
| (Blink の拡張) | — | `MediaKeys.getMetrics()`、`SourceBuffer.writeHead` など |

## 4. 抜けのチェック(1 つずつ確認した方法と結果)

| 確認したこと | 方法 | 結果 |
|---|---|---|
| CEF の公開ヘッダが全部表にあるか | `include/*.h` 88 個、`views/` 21 個、`wrapper/` 12 個を列挙して照合(logs/459) | 88 個すべてを 2 章のどれかの行に割り当てた。`cef_base.h`(基盤)、`cef_sandbox_mac/win.h`、`cef_application_mac.h`(Linux 対象外)は「ユーティリティ」「起動」に含めた。views の delegate 系と wrapper の Windows 用は個別の行にしていない |
| 8127 に拡張機能 API があるか | `include/` を grep | なし(上流で削除済み) |
| Cobalt の mojom が全部表にあるか | `find cobalt -name '*.mojom'` 19 個(logs/460) | チェックで `video_geometry_setter.mojom`(動画の重ね合わせ)が抜けていたので追加した。残り 18 個は 3 章に記載 |
| Cobalt の Blink IDL が全部表にあるか | `modules/cobalt` の IDL 25 個(logs/460) | すべて 3 章の入口に対応(イベント型の IDL は各モジュールに含めた) |
| Cobalt の BrowserContext で nullptr を返す委譲 | `return nullptr` の前の関数名を列挙(logs/460) | 14 個。表になかった **ズーム、閲覧データの削除、Origin Trials** を追加した。ストレージ通知と SpecialStoragePolicy、Accept-Language の削減は TV で差が出ないので表には入れていない |
| CEF にあって Cobalt にない機能の有無 | 18 個のキーワードを `cobalt/` 全体で grep(logs/460) | RunFileChooser、Spellcheck、Autofill、PrintToPDF、windowless / OffScreen、FindReply、ShowRepostFormWarningDialog は 0 件。表の「×」と一致。**ページ内検索**が表になかったので追加した |
| サブエージェントが書いた根拠の正しさ | 主な行をファイルで抜き取り確認(Cobalt: logs/461 の 10 項目、CEF: logs/462 の 6 項目) | JS ダイアログの抑止、空のコンテキストメニュー、gold での DevTools 無効、プロキシは gold で無効、サードパーティ Cookie のブロック、HTTPS 強制、音声だけのメディアアクセス、CEF の既定スタイルが Chrome、//chrome のサブクラス、Profile の生成、DevToolsWindow、PDF の失敗返却を確認。食い違いはなかった |
| content の既定動作に頼る項目 | `RunFileChooser` は content の既定を確認(即キャンセル) | 権限の委譲先が nullptr のときの各 Web API の挙動、Service Worker の挙動は **未確認**(content のソースは読んでいない) |

## 5. //chrome 層がどれだけ残っているか

### 5-1. G2(arm64)の `.text` のディレクトリ別(logs/457、マップから集計)

| ディレクトリ | `.text` | Cobalt で対応するもの |
|---|---|---|
| v8 | 25.70 | 残す(Cobalt にもある) |
| components(viz を除く) | 20.95 | 大半は //chrome のブラウザ機能(autofill 3.1、password_manager、sync、omnibox、optimization_guide、safe_browsing、policy、history、segmentation など) |
| blink(core、bindings、modules、platform、その他) | 33.49 | 残す(Cobalt はバインディングとモジュールをさらに除外) |
| **chrome** | **17.52** | **Cobalt にはない**(ui 約 7、web_applications 1.3、glic 1.0、devtools 0.5、actor 0.5 など) |
| content | 9.51 | 残す |
| skia、net、services、ui、cc、gpu、media、base | 計 約 24 | 残す |
| angle | 3.99 | Cobalt は 0.6(Vulkan バックエンドなし) |
| ffmpeg、libvpx、dav1d | 3.05 | Cobalt は本体ではなく `libstarboard.so`(7.0MB、別ファイル)に持つ |
| tflite、perfetto | 2.86 | Cobalt は tflite なし |
| cef | 1.91 | Cobalt にはない |
| その他 third_party(icu、boringssl、rust、harfbuzz など) | 約 15 | 大半は残す。cld_3、ced、hunspell、sentencepiece、federated_compute、openscreen、zucchini などは //chrome 由来 |
| 合計 | 160.27 | Cobalt(x64)の `.text` は 82.3 |

x64 の F4b でもほぼ同じ(logs/457b、`.text` 163.2MB、chrome 17.7、components 21.9)。

### 5-2. //chrome 層の大きさの見積もり(2 通り)

| 方法 | 見積もり |
|---|---|
| A. マップの積み上げ: `obj/chrome` 17.5 + `obj/cef` 1.9 + ブラウザ機能の components 約 18 + //chrome 由来の third_party 約 4 = `.text` 約 41MB。`.rodata` などを同じ割合で足す | **約 47MB** |
| B. 同じ削減をした content_shell との差: Chromium 編の D3c(content_shell、x64)160.4MB に、F4b で使っている RELR(実測 −12.8)と `-Os`(推定 約 −10)を当てると約 138MB。F4b 191.2MB との差 | **約 53MB**(推定) |

- **//chrome 層 + CEF 本体で約 45〜55MB**。Cobalt の調査で分かっている「//chrome 層 −114.6MB」は、上流の `chrome`(何も削っていない、`-O2`、CFI あり)と content_shell の差。こちらは第 1・2 期で PDF、印刷、拡張機能、WebUI、Chrome スタイル専用部分などを外し終えているので、残りは約半分になっている。
- 試して使えなかった方法(記録): content_shell の `gn desc --all` の依存一覧に入るかどうかで分ける方法(logs/458、458b)。content_shell の依存閉包には `components/permissions` → `browsing_data` → `autofill` のような経路で autofill なども入るため、「依存にある」と「実際にリンクされる」が一致せず、//chrome 層を小さく見積もってしまう。content_shell を実際にビルドしないと、この方法では測れない。

### 5-3. G2 と Cobalt の差 77.9MB の内訳(推定)

| 要因 | 大きさ | CEF のままで削れるか |
|---|---|---|
| //chrome 層 + CEF 本体 | 約 45〜55MB | 一部だけ(5-4) |
| ANGLE の Vulkan バックエンド | 約 3.4MB | 削れる(`angle_enable_vulkan=false`)。ただし SwiftShader と両立しない(GPU のある実機向け) |
| デコーダ(ffmpeg、libvpx、dav1d)を本体に持つ | 約 3MB | 削れない(S/W デコードに必要)。Cobalt も別ファイルで 7.0MB 持っている |
| tflite | 約 1.5MB | 削れる見込み(`build_with_tflite_lib=false`、未検証) |
| Blink のバインディング除外、V8 / ICU / コンパイラ設定、arm64 と x64 の違いなど | 残り 約 15〜25MB | 一部(Cobalt のパッチの移植が必要)。計測方法の違い(Cobalt は DWARF、こちらはマップ)とアーキテクチャの違いもここに入る |

- 未確認の要因: こちらのビルドは `chrome_pgo_phase=2`(Linux の official build の既定で PGO が有効)、Cobalt は 0。PGO がサイズに与える影響は測っていない。

### 5-4. なぜ //chrome 層が CEF では削りきれないのか

- **CEF は //chrome の上に作られている**。8127 では Alloy ランタイムがなくなり、Chrome ランタイムだけになった。libcef は次の //chrome のクラスを継承して動く(logs/462): `ChromeMainDelegate`、`ChromeContentBrowserClient`、`ChromeContentRendererClient`、`ChromeContentClient`、`ChromeBrowserMainExtraParts`。`CefRequestContext` の実体は chrome の `Profile`(`ProfileManager::CreateProfileAsync`)。libcef の 76 ファイルが `chrome/` を 172 回 include している。
- **//chrome のブラウザ機能は、中央の登録箇所からまとめて参照される**。`ChromeContentBrowserClient`、Profile の KeyedService の一括登録、タブヘルパの一括取り付けなどが autofill、sync、パスワード管理、omnibox などを直接参照する。buildflag がないので GN では外せず、個別の機能を消すパッチでは参照が残ってリンクされる(M8 の「点の根切りでは落ちない」)。
- **Alloy スタイル専用にしても −0.6MB だった**(F2b1)。Chrome スタイルの UI のコードは、chrome 本体のクラスから参照されるので残る。

### 5-5. 約 100MB 削れるか

**削れない**。理由:

1. 残っている //chrome 層 + CEF は約 45〜55MB しかない。全部消しても約 100MB にはならない。
2. CEF のままでは、そのうちの一部しか消せない(5-4)。

CEF のままで狙える追加の削減(すべて推定、未検証):

| 案 | 見込み | 代償 |
|---|---|---|
| Chrome スタイルの UI(`chrome/browser/ui` 約 7MB)を、Browser ウィンドウの生成元から切る | −3〜6MB | パッチが大きい。CEF の Views API も一部使えなくなる |
| Profile の KeyedService 一括登録から、autofill、sync、パスワード、omnibox、history、bookmarks、optimization_guide、segmentation などを外す | −5〜15MB | 起動時に参照するコードが多く、パッチの規模と追従の負担が大きい。CEF の動作確認がやり直し |
| `build_with_tflite_lib=false`、`angle_enable_vulkan=false`(GPU 実機向け) | −4〜5MB | WebGL は GPU 前提になる |
| 合計 | **約 −15〜25MB**(186.7 → 約 160〜170MB) | |

**Cobalt 並み(約 110MB)にするには、CEF をやめて content 層の上に専用の shell を作る**しかない。Cobalt shell の機能(2 章)を見ると、TV の YouTube 専用アプリに必要なのは content の機能とライフサイクル程度で、CEF の API の大半(ダウンロード、ダイアログ、権限 UI、OSR、Views、印刷など)は使っていない。ただし CEF の API で作られている既存のアプリ側のコードは使えなくなり、作り直しになる。

## 6. 未確認のこと

- content_shell を同じツリー・同じ引数でビルドしたときの実サイズ(5-2 の B は推定)。ビルドすれば //chrome 層の大きさを実測できる(数時間)。
- 5-5 の各案の実際の効果。
- PGO(`chrome_pgo_phase=2`)のサイズへの影響。
- content の既定動作(委譲先が nullptr のときの Web API の挙動)。
