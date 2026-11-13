# 削減したもの一覧

作成: 2026-11-12。サイズの効果は `rom-size-reduction.md` を参照。ここは「何を外したか」の一覧。

出典: 各構成の `args.gn`(`logs/results/*-args.gn`、`/root/fp/builds/*/args.gn`)、パッチ(`logs/patches/d3c-clean.patch`、`logs/patches/e3b-final-clean.patch`)、配布物の内訳(`logs/results/*-size.json`)。

構成の記号: B = `chrome` + GN フラグ、C = `content_shell` + GN フラグ、D1〜D3c = `content_shell` + パッチ、E2 / E3a / E3b = CEF。

## 1. GN フラグで無効化したもの

すべて `=false`。○ = その構成で適用、× = 試したが通らなかった、− = 対象外または未試行。

### 1.1 基本の削減フラグ(B / C / D / E2 に共通)

| # | フラグ | 外したもの | TV 用途で不要な理由 | B・C | D | CEF |
|---|---|---|---|---|---|---|
| 1 | `use_cups` | CUPS 印刷バックエンド | 印刷しない | ○ | ○ | E2 |
| 2 | `enable_vr` | WebXR のデバイス層 | VR / AR 機器を使わない | ○ | ○ | E2 |
| 3 | `enable_openxr` | OpenXR ランタイム連携 | 同上 | ○ | ○ | E2 |
| 4 | `enable_remoting` | Chrome リモートデスクトップ | 使わない | ○ | ○ | E2 |
| 5 | `use_on_device_model_service` | オンデバイス AI モデルのサービス | 使わない | ○ | ○ | E2 |
| 6 | `webnn_use_tflite` | WebNN の TFLite バックエンド | WebNN を使わない | ○ | ○ | E2 |
| 7 | `webnn_use_litert` | WebNN の LiteRT バックエンド | 同上 | ○ | D3b〜 | E2 |
| 8 | `use_perfetto_trace_processor` | トレース解析エンジン | 開発用 | ○ | ○ | E2 |
| 9 | `enable_libaom` | AV1 エンコーダ(libaom) | 再生のみ。AV1 デコード(dav1d)は残る | ○ | ○ | E2 |
| 10 | `rtc_include_dav1d_in_internal_decoder_factory` | WebRTC 内蔵の AV1 デコーダ登録 | WebRTC を使わない。`<video>` の AV1 再生には影響しない | ○ | ○ | E2 |
| 11 | `use_qt5` | Qt5 テーマ連携(`libqt5_shim.so`) | デスクトップ統合は不要 | ○ | ○ | E1 既定 |
| 12 | `use_qt6` | Qt6 テーマ連携(`libqt6_shim.so`) | 同上 | ○ | ○ | E1 既定 |
| 13 | `use_kerberos` | Kerberos 認証 | 企業内認証を使わない | ○ | ○ | E2 |
| 14 | `enable_paint_preview` | Paint Preview(ページの描画キャプチャ) | 使わない | ○ | ○ | E2 |
| 15 | `generate_about_credits` | `about:credits` のライセンス一覧ページ | ライセンス表示は別途用意する前提 | ○ | ○ | E2 |
| 16 | `dawn_enable_vulkan_validation_layers` | Vulkan 検証レイヤ(`libVkLayer_khronos_validation.so`) | 開発用 | ○ | ○ | E2 |
| 17 | `use_dawn` | Dawn(WebGPU の実装) | WebGPU 不要 | ○ | ○ | E2 |
| 18 | `skia_use_dawn` | Skia の Dawn(Graphite)バックエンド | 同上 | ○ | ○ | E2 |
| 19 | `chrome_wide_echo_cancellation_supported` | マイク入力の全体エコーキャンセル | マイク入力を使わない | ○ | D3b〜 | E2 |

### 1.2 `content_shell` のパッチ構成で追加したもの(D1〜)と CEF の追加分(E3a)

| # | フラグ | 外したもの | TV 用途で不要な理由 | D | CEF |
|---|---|---|---|---|---|
| 20 | `enable_media_remoting` | Media Remoting(Cast への映像転送) | 送信側にならない | ○ | − |
| 21 | `enable_media_remoting_rpc` | 同 RPC 層 | 同上 | ○ | − |
| 22 | `enable_browser_speech_service` | ブラウザ側の音声認識サービス | 使わない | ○ | − |
| 23 | `use_bluez` | BlueZ(Bluetooth) | Web Bluetooth を使わない | ○ | − |
| 24 | `enable_mdns` | mDNS / DNS-SD | ローカル機器探索を使わない | ○ | E3c のみ(効果なし、不採用) |
| 25 | `ozone_platform_wayland` | Wayland バックエンド | 実験環境は X11 / ヘッドレス | ○ | E3a |
| 26 | `use_gtk` | GTK 連携(ファイルダイアログ、テーマ) | 不要 | ○ | E3a |
| 27 | `use_gio` | GIO / GSettings 連携 | 不要 | ○ | E3c のみ(不採用) |
| 28 | `use_libpci` | libpci による GPU 情報取得 | 不要 | ○ | E3a |
| 29 | `use_vaapi` | VA-API ハードウェアデコード | x64 デスクトップ向け。TV の SoC では別経路 | ○ | E3a |
| 30 | `rtc_use_pipewire` | PipeWire(画面キャプチャ) | 画面共有しない | ○ | E3a |
| 31 | `enable_library_cdms` | ライブラリ CDM(Widevine CDM のロード機構) | Chromium 編は ClearKey で検証。**製品で Widevine を使うなら残す** | ○ | −(CEF は Widevine 有効のまま) |
| 32 | `enable_jxl_decoder` | JPEG XL デコーダ | 配信で使わない | ○ | E3a |
| 33 | `media_use_iamf_tools` | IAMF(没入型オーディオ)デコード | 使わない | ○ | E3a |
| 34 | `enable_reporting` | Reporting API / NEL | 不要 | ○ | E3a |
| 35 | `enable_device_bound_sessions` | Device Bound Session Credentials | 不要 | ○ | E3a |
| 36 | `enable_compute_pressure` | Compute Pressure API | 不要 | ○ | E3a |
| 37 | `enable_chrome_notifications` | 通知(ブラウザ側) | 通知を出さない | ○ | ×(起動時に異常終了) |
| 38 | `enable_message_center` | メッセージセンター | 同上 | ○ | ×(コンパイル不可) |
| 39 | `enable_backup_ref_ptr_support` | BackupRefPtr(use-after-free 緩和) | Cobalt にならった。**セキュリティ緩和策を外す** | ○ | E1 既定 |
| 40 | `enable_backup_ref_ptr_feature_flag` | 同 機能フラグ | 同上 | ○ | E3a |
| 41 | `include_transport_security_state_preload_list` | HSTS プリロードリスト | Cobalt にならった。**初回接続の HTTPS 強制がなくなる** | ○ | E3a |
| 42 | `enable_vectorized_html_scanning` | HTML スキャンの SIMD 実装 | Cobalt にならった | ○ | E3a |
| 43 | `is_cfi` | CFI(制御フロー保護) | ARM の TV 向けでは元々無効。**x64 ではセキュリティ機能を外す** | D3c | E3a |
| 44 | `enable_hangout_services_extension` | Hangouts 用の内蔵拡張機能 | 不要 | − | E3a |
| 45 | `enable_offline_pages` | オフラインページ | 不要 | − | E3a |
| 46 | `enable_bound_session_credentials` | Bound Session Credentials | 不要 | − | E3a |

- 適用数: B・C 19 個、D3c 43 個、E2 17 個(E1 既定に Qt 2 個を含むため)、E3a・E3b 34 個。
- CEF の既定(E1)には `enable_background_mode`、`enable_backup_ref_ptr_support`、`use_partition_alloc_as_malloc`、`use_qt5`、`use_qt6` の無効化が最初から入っている。

### 1.3 外そうとして外せなかったフラグ

| フラグ | 対象 | 結果 |
|---|---|---|
| `enable_pdf`、`enable_printing`、`enable_print_preview` | PDF、印刷 | `chrome` / CEF で `gn gen` 不通過(assert、無条件の依存) |
| `enable_extensions`、`enable_plugins`、`enable_guest_view` | 拡張機能、プラグイン | 同上 |
| `safe_browsing_mode=0` | Safe Browsing | `//chrome/browser` の依存が未解決 |
| `enable_captive_portal_detection`、`enable_supervised_users`、`enable_screen_ai_service`、`enable_speech_service`、`enable_lens_desktop`、`enable_compose`、`enable_on_device_translation`、`enable_perfetto_trace_processor`、`enable_background_contents`、`enable_webui_certificate_viewer` | 各機能 | `//chrome` の assert / 依存 |
| `enable_session_service` | セッション復元 | CEF でコンパイル不可 |
| `build_tflite_with_xnnpack` | XNNPACK | リンク不可(LiteRT が必須としている) |

## 2. パッチで削除したもの

Chromium 編 D3c と CEF 編 E3b で同じ内容(CEF は `content/shell` の分を除く)。

### 2.1 Blink モジュール(41 個。`modules/BUILD.gn` の `sub_modules` から削除、IDL 585 個)

| # | モジュール | 使えなくなる Web API | IDL 数 | 段階 |
|---|---|---|---|---|
| 1 | `ai` | 組み込み AI(LanguageModel、Summarizer、Translator など) | 12 | D2 |
| 2 | `app_banner` | `beforeinstallprompt`(PWA のインストール) | 4 | D2 |
| 3 | `background_fetch` | Background Fetch | 10 | D2 |
| 4 | `background_sync` | Background Sync / Periodic Sync | 9 | D2 |
| 5 | `badging` | Badging API | 2 | D2 |
| 6 | `battery` | Battery Status | 2 | D2 |
| 7 | `bluetooth` | Web Bluetooth | 20 | D2 |
| 8 | `contacts_picker` | Contact Picker | 5 | D2 |
| 9 | `content_index` | Content Index | 7 | D2 |
| 10 | `credentialmanagement` | Credential Management、WebAuthn、FedCM、WebOTP、Digital Credentials | 63 | D2 |
| 11 | `direct_sockets` | Direct Sockets(TCP / UDP) | 7 | D2 |
| 12 | `eyedropper` | EyeDropper | 3 | D2 |
| 13 | `font_access` | Local Font Access | 3 | D2 |
| 14 | `handwriting` | Handwriting Recognition | 11 | D2 |
| 15 | `hid` | WebHID | 12 | D2 |
| 16 | `idle` | Idle Detection | 2 | D2 |
| 17 | `installedapp` | `getInstalledRelatedApps()` | 2 | D2 |
| 18 | `managed_device` | Managed Device API | 2 | D2 |
| 19 | `ml` | WebNN | 10 | D2 |
| 20 | `nfc` | Web NFC | 10 | D2 |
| 21 | `notifications` | Notifications | 9 | D2 |
| 22 | `payments` | Payment Request、Payment Handler | 41 | D2 |
| 23 | `payments/goods` | Digital Goods | (上に含む) | D2 |
| 24 | `push_messaging` | Push API | 11 | D2 |
| 25 | `sensor` | Generic Sensor(加速度、ジャイロ、照度など) | 18 | D2 |
| 26 | `serial` | Web Serial | 10 | D2 |
| 27 | `shapedetection` | Shape Detection(バーコード、顔、文字) | 9 | D2 |
| 28 | `smart_card` | Smart Card API | 6 | D2 |
| 29 | `speech` | Web Speech(音声認識、音声合成) | 20 | D2 |
| 30 | `wake_lock` | Screen Wake Lock | 4 | D2 |
| 31 | `webmidi` | Web MIDI | 12 | D2 |
| 32 | `webshare` | Web Share | 2 | D2 |
| 33 | `webusb` | WebUSB | 19 | D2 |
| 34 | `xr` | WebXR Device API | 81 | D2 |
| 35 | `mediastream` | `getUserMedia`、`getDisplayMedia`、MediaStream、MediaStreamTrack | 42 | D3c |
| 36 | `peerconnection` | WebRTC(RTCPeerConnection、RTCDataChannel、Encoded Transform) | 81 | D3c |
| 37 | `webrtc` | WebRTC の音声デバイス層 | 3 | D3c |
| 38 | `mediarecorder` | MediaRecorder | 4 | D3c |
| 39 | `imagecapture` | ImageCapture | 6 | D3c |
| 40 | `mediacapturefromelement` | `captureStream()`(canvas / video) | 3 | D3c |
| 41 | `breakout_box` | MediaStreamTrackProcessor / Generator | 5 | D3c |

- これまでのまとめで「49 個」と書いていたのは誤りで、正しくは 41 個(`payments/goods` を別に数えて)。各文書を訂正した。
- TV 用途で不要とした理由: カメラ、マイク、センサー、USB / Bluetooth などの周辺機器、決済、通知、PWA インストール、WebRTC 通話はどれも動画配信の視聴に使わない。
- 注意: `wake_lock` を外したので Screen Wake Lock API は使えない(動画再生中のスリープ抑止はブラウザ内部の別経路)。`credentialmanagement` を外したのでパスキー(WebAuthn)でのログインはできない。

### 2.2 残したモジュールから削った API / 機能

| 対象 | 削ったもの | 理由 |
|---|---|---|
| Web Audio(`AudioContext`) | `createMediaStreamSource()`、`createMediaStreamDestination()`、MediaStreamAudioSourceNode / DestinationNode(IDL 3 個) | MediaStream に依存 |
| Web Audio(出力) | WebRTC エコーキャンセル用の出力デバイス通知 | WebRTC に依存 |
| `HTMLMediaElement.srcObject` | `MediaStream` を受け付けない(`MediaSourceHandle` のみ) | MediaStream に依存 |
| Media Capabilities | `type: "webrtc"` と `type: "record"` は常に unsupported | WebRTC / MediaRecorder に依存 |
| `requestVideoFrameCallback` | WebXR の没入セッション中の連携 | WebXR に依存 |
| WebGL | `makeXRCompatible()` の XR 連携 | WebXR に依存 |
| Service Worker | Background Fetch、Background Sync、Content Index、通知、決済、プッシュの各イベント配送(届いたら拒否で応答) | 対応モジュールを削除。Service Worker 本体(fetch、Cache API)は残る |
| 構造化複製(`postMessage`) | MediaStreamTrack、RTCCertificate、RTCDataChannel、RTCEncodedAudio / VideoFrame、CropTarget、RestrictionTarget、Shape Detection の型の転送 | 対応モジュールを削除 |
| レンダラの初期化 | AppBanner、PeerConnectionTracker、UserMedia、プッシュ、音声合成、WebNN イントロスペクションの登録 | 同上 |

### 2.3 プロセス / サービス側

| 対象 | 削ったもの | 段階 |
|---|---|---|
| GPU プロセス | WebNN コンテキストプロバイダの生成 | D3a |
| ユーティリティプロセス | OnDeviceModel サービスの登録とサンドボックス前処理 | D3a / D3b |
| ユーティリティプロセス | VideoCapture サービスの登録(カメラ入力) | D3a |
| レンダラ(content) | MediaStream 用プレーヤー(`WebMediaPlayerMS`)の生成、MediaStream デバイス監視 | D3c |

### 2.4 `content_shell` 側(Chromium 編のみ、D1)

| 対象 | 削ったもの |
|---|---|
| ルート `BUILD.gn` | `content_shell` だけを参照する最小構成に置換(CEF は `//cef:cefsimple` のみ) |
| `content/shell` | Web テスト(レイアウトテスト)対応、テスト用 `internals` の注入 |
| `content/shell` | toolkit-views の UI |
| `content_shell.pak` | DevTools フロントエンド(7.4MB → 2.5MB)。リモートデバッグは外部のフロントエンドから接続する |
| `content/shell`(レンダラ) | FedCM の IdP サインイン状態スロットル |

### 2.5 CEF 編だけの追加

| 対象 | 内容 |
|---|---|
| `modules/exported/fp_stubs.cc` | `blink::SetIdpSigninStatus` の空スタブ(`//chrome` のレンダラが参照するため) |

## 3. 配布物から消えたファイル / 小さくなったファイル

| ファイル | 変化 | 構成 | 原因 |
|---|---|---|---|
| `libVkLayer_khronos_validation.so` | 27.8MB → なし(CEF は 27.3MB → なし) | B、C、E2 以降 | `dawn_enable_vulkan_validation_layers=false` |
| `libqt5_shim.so`、`libqt6_shim.so` | 各 0.04MB → なし | B | `use_qt5` / `use_qt6` |
| `content_shell.pak` | 7.4MB → 2.5MB | D1 以降 | DevTools フロントエンドを除外 |
| `resources.pak` | 26.25MB → 26.09MB(CEF 25.78 → 25.62) | B、E2 | クレジットページなど |
| `libvk_swiftshader.so` | 6.43MB → 6.13MB(CEF 6.01 → 5.75) | D3c、E3a 以降 | CFI 無効 |
| `chrome_crashpad_handler` | 2.45MB → 2.19MB | E3a 以降 | CFI 無効 |
| ロケール pak | 220 個 51.9MB → ja + en-US 1.5MB | 配布時の選択 | `chrome` / CEF のみ |

## 4. 残したもの(方針上、削っていない)

- 動画再生: `<video>`、MSE、EME(ClearKey。CEF は Widevine も)、H.264 / AAC / VP8 / VP9 / AV1 / Opus / Vorbis / MP3 / FLAC、MPEG-2 TS、WebCodecs、Web Audio(MediaStream 連携以外)。
- 通信とストレージ: fetch、WebSocket、WebTransport、Service Worker、Cache API、IndexedDB、localStorage。
- そのほか: WebAssembly、WebGL(SwiftShader)、WebCrypto、DevTools バックエンド(リモートデバッグ)。
- 削除済みの API をページが呼ぶと `undefined` になる。機能検出をしていないページは例外で止まる可能性がある(YouTube の 1080p 再生と動作確認 7 項目では問題なし)。

## 5. CEF 第 2 期(F 系列)で削ったもの(2026-11-12 追記)

第 1 期(E3b)に追加した分。最終構成は F4b / F4b-dist。詳細は `logs/cef-milestones/M7`〜`M10`、パッチは `logs/patches/f4b.patch`、`f4b-cef.patch`、args は `logs/results/F4b-args.gn`。

### 5.1 GN フラグ(25 個)

| フラグ | 値 | 消えるもの |
|---|---|---|
| `fp_use_relr_relocations`(パッチで追加した引数) | true | 再配置テーブル `.rela.dyn` 25.8MB → `.relr.dyn` 0.2MB |
| `optimize_for_size` | true | (機能は消えない。`-O2` → `-Os`) |
| `enable_pdf` | false | PDF ビューア、PDFium(5.0MB)、PDF 用の拡張 API、`pdf_resources` |
| `enable_print_preview` | false | 印刷プレビュー(WebUI とダイアログ) |
| `enable_printing` | false | 印刷全体(`window.print()`、PrintToPDF、印刷用のユーティリティプロセス、print compositor) |
| `enable_plugins` | false | プラグイン(`<embed>` / `<object>` のプラグイン機構、プラグインのプレースホルダ) |
| `enable_extensions`(連動で `enable_extensions_core`) | false | 拡張機能の仕組み全体(`chrome.*` API、`chrome-extension://`、コンポーネント拡張機能、拡張機能用のレンダラプロセス、Web Store 連携) |
| `enable_platform_apps` | false | Chrome アプリ(`--app-id`、`--load-apps`、アプリウィンドウ) |
| `enable_hosted_apps` | false | ホステッドアプリ |
| `use_bluez` | false | BlueZ / Floss の D-Bus クライアント(Bluetooth のバックエンド) |
| `media_use_openh264` | false | OpenH264(H.264 のソフトウェアエンコーダ。デコードは FFmpeg なので影響なし) |
| `safe_browsing_use_unrar` | false | unrar(ダウンロードした RAR の中身検査) |
| `angle_has_frame_capture` | false | ANGLE のフレームキャプチャ(デバッグ用) |
| `enable_gwp_asan` | false | GWP-ASan(サンプリング式のメモリ破壊検出) |
| `enable_webui_bookmarks` | false | ブックマーク管理の WebUI |
| `enable_webui_contextual_tasks_composebox` | false | コンテキストタスクの WebUI 部品 |
| `enable_webui_generate_code_cache` | false | WebUI の V8 コードキャッシュ(`resources.pak` の 2.8MB) |
| `enable_glic_internal_resources` | false | Glic(Gemini 連携)の内部リソース |
| `structured_metrics_enabled` | false | Structured Metrics |
| `choice_screen_in_chrome` | false | 検索エンジン選択画面 |
| `headless_enable_commands` | false | ヘッドレスモードのコマンド(`--screenshot` など) |
| `enable_memory_coordinator_internals` | false | メモリコーディネータの内部ページ |
| `glslang_enable_hlsl` | false | glslang の HLSL 対応 |
| `build_tflite_with_xnnpack` | false | XNNPACK(TFLite の CPU 高速化、1.4MB) |
| `produce_v8_compile_hints` | false | V8 のコンパイルヒント収集 |

F2 では `pdf_enable_xfa=false` も入れていた(PDFium の XFA、1.6MB)。F4a では PDF ごと外したので指定していない。

### 5.2 試して通らなかったフラグ(第 2 期)

| フラグ(= false) | 落ちた段階 | 原因 |
|---|---|---|
| `enable_gpu_channel_media_capture` | リンク | V4L2 キャプチャ側が `VideoCaptureGpuChannelHost` を参照 |
| `enable_media_remoting` | リンク | `CastRemotingConnector` の参照が 2 ファイルに残る |
| `enable_pdf_translation` | リンク | `content_translate_driver.cc` の参照 |
| `enable_pdf_ink2`、`enable_pdf_save_to_drive` | TypeScript | PDF ビューアが tsc / eslint で落ちる |
| `enable_browser_speech_service` | コンパイル | `#error` |
| `enterprise_proxy`、`enterprise_content_analysis`、`enterprise_local_content_analysis` | コンパイル | 未ガードの参照 |
| `safe_browsing_mode=0`、`enable_captive_portal_detection`、`enable_background_contents`、`enable_webui_certificate_viewer` | `gn gen` | テストターゲット(`browser_tests`)の依存だけが未解決。パッチは未着手 |
| `enable_webui_history`、`enable_webui_ntp`、`enable_lens_desktop`、`enable_compose`、`enable_on_device_translation`、`enable_screen_ai_service`、`enable_speech_service`、`enable_supervised_users`、`build_with_model_execution`、`use_dbus`、`enterprise_data_controls`、`enterprise_watermark`、`enterprise_cache_encryption`、`chrome_root_store_cert_management_ui`、`enable_guest_contents` | `gn gen` | `assert` |

### 5.3 パッチで削ったもの

| 対象 | ファイル | 内容 | 使えなくなるもの |
|---|---|---|---|
| Dawn / tint | `content/utility/utility_main.cc` | `on_device_model::PreSandboxInit()` の呼び出しを削除 | なし(WebGPU は第 1 期で無効化済み。残っていた 5.7MB が落ちる) |
| `chrome://` の WebUI | `chrome_browser_main.cc`、`chrome_content_browser_client_receiver_bindings.cc` | WebUI の一括登録と Mojo バインダ登録の呼び出し 5 行を削除 | `chrome://settings`、`chrome://history`、`chrome://version`、`chrome://flags` など `//chrome` の全 WebUI |
| BlueZ | `chrome_browser_main_linux.cc`、`bluetooth_metrics_provider.cc` | 初期化 / 終了 / メトリクスの 3 箇所を削除 | Bluetooth |
| Chrome スタイル | `browser_window_factory.cc`、CEF の `browser_view_impl.cc`、`widget.cc`、`toolbar_view_impl.cc` | ウィンドウ生成 4 箇所をスタブ化 | Chrome スタイルの CEF ブラウザ(Alloy スタイル専用になる) |
| 拡張機能 / アプリ | Chromium 約 320 ファイル(.cc 173、.h 40、BUILD.gn 128 など。F3a 分と合わせて 342)、CEF 13 ファイル + スタブ 1 | buildflag のガード追加、GN の依存の条件分岐。拡張機能専用の UI ソース 45 個は GN から除外 | 5.1 のとおり。アプリメニューの「拡張機能」は残るが押しても何も起きない |
| PDF / 印刷 / プラグイン | Chromium 21 ファイル、CEF 9 ファイル + スタブ 1 | buildflag のガード追加、`//cef/BUILD.gn` の `assert(enable_print_preview)` の削除と条件分岐 | 5.1 のとおり。`CefBrowserHost::Print()` は何もしない、`PrintToPDF()` は失敗を返す |
| RELR | `build/config/compiler/BUILD.gn` | GN 引数とリンクオプションの追加 | |

### 5.4 配布物から外したもの(F4a-dist)

| ファイル | サイズ | 外した理由 | 影響 |
|---|---|---|---|
| `resources.pak` の中身 | 25.6 → 0.9MB | `chrome://` WebUI のリソース、DevTools フロントエンド(4.8MB)、起動演出の音声(4.8MB)、WebUI 共有部品 | `chrome://` ページ、`devtools://` の UI |
| `icudtl.dat` | 10.8 → 5.2MB | cast 用データに差し替え | 日本語の単語分割が 1 文字単位 |
| `chrome_crashpad_handler` | 2.1MB | クラッシュレポートを送らない | クラッシュダンプが残らない |
| `chrome_200_percent.pak` | 0.93MB | HiDPI(2 倍)用の UI 画像 | 2 倍スケールの表示 |
| `snapshot_blob.bin` | 0.36MB | `v8_context_snapshot.bin` を使うので読まれない | なし |
| `libVkICD_mock_icd.so` | 0.63MB | テスト用の Vulkan ドライバ | なし |

### 5.5 第 2 期でも残したもの

- コーデック(H.264 / AAC / VP9 / AV1 / Opus、FFmpeg、libvpx、dav1d)、Widevine(`enable_widevine`、`enable_library_cdms`)、MSE / EME、Service Worker、WebSocket、WebGL(ANGLE)、SwiftShader、WebAssembly、DevTools のバックエンド(リモートデバッグ)。
- GuestView(`enable_guest_view`)。拡張機能なしの構成では glic などの WebUI が依存するため見送り。
- autofill、sync、パスワード管理、Safe Browsing、ポリシー、翻訳などの `//chrome` / `//components` の機能(合計 約 48MB)。buildflag がないか、参照が密で外せなかった。

## 6. CEF 第 3 期(arm64、G2)で追加で削ったもの(2026-11-13 追記)

Cobalt(Chromium ベースの YouTube 用ブラウザ)の `common.gn` から、未適用で TV ブラウザに使えるものを適用した(M13)。

| GN 引数(すべて false) | 中身 | 連動して false | 影響 |
|---|---|---|---|
| `enable_media_remoting`、`enable_media_remoting_rpc` | Cast ミラーリング中に動画だけ受信機で再生する仕組み | | タブのミラーリング自体は残る |
| `enable_hls_demuxer` | `<video src="*.m3u8">` を Chromium 自身で再生する HLS | `enable_mse_mpeg2ts_stream_parser` | HLS は hls.js などで MSE に流す必要がある。MSE の MPEG2-TS も使えない(fMP4 に変換する) |
| `enable_hevc_parser_and_hw_decoder` | HEVC のパーサと H/W デコーダ連携 | `enable_platform_hevc` | H/W の HEVC を使う実機なら残す |

- パッチ(`tools/fp/g2_patch.py`): `chrome/browser/media/router/mojo/media_router_desktop.cc`、`chrome/browser/media/cast_mirroring_service_host.cc` の `CastRemotingConnector` の参照を `BUILDFLAG(ENABLE_MEDIA_REMOTING)` で囲む。
- 配布物(G2-tv): SwiftShader 一式(`libvk_swiftshader.so`、`vk_swiftshader_icd.json`、`libvulkan.so.1`)。GPU のない環境では WebGL が使えなくなり、合成はソフトウェア(CPU)になる。動画の再生とページの表示はできる。
- 適用しなかったもの: `angle_enable_vulkan=false`(SwiftShader が使えなくなる)、コーデックの削除(ソフトウェアデコードで再生しているため)、`enable_screen_capture`(158 に存在しない)。
