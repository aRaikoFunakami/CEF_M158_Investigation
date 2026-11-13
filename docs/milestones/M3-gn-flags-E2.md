# M3: GN フラグ削減 E2(パッチなし)

完了: 2026-11-11 20:40 JST(メモリは logs/146 の測り直し後に追記)。ログ: logs/141〜146。

## ビルド

- 引数: E1 + 17 フラグ(`logs/results/E2-args.gn`)。Chromium 編 B で `chrome` に通ったものと同じ。
- `out/E2`、ninja、2 時間 25 分(58,855 ステップ、停止 0 回、エラー 0 件)。17 フラグは生成・コンパイル・リンクすべて通過。

```
use_cups=false  enable_vr=false  enable_openxr=false  enable_remoting=false
use_on_device_model_service=false  webnn_use_tflite=false  webnn_use_litert=false
use_perfetto_trace_processor=false  enable_libaom=false
rtc_include_dav1d_in_internal_decoder_factory=false  use_kerberos=false
enable_paint_preview=false  generate_about_credits=false
dawn_enable_vulkan_validation_layers=false  use_dawn=false  skia_use_dawn=false
chrome_wide_echo_cancellation_supported=false
```

## サイズ

| 項目 | E1 | E2 | 差 |
|---|---|---|---|
| strip 後の本体(`libcef.so` + `cefsimple`) | 299.6MB | **291.6MB** | −8.0MB |
| text / data | 285.3 / 14.3 | 277.5 / 14.1 | |
| 配布物合計(ja + en-US) | 377.5MB | **342.0MB** | −35.5MB |
| 配布物合計(全ロケール) | 428.0MB | 392.5MB | −35.5MB |

- 配布物の差の大半は `libVkLayer_khronos_validation.so`(27.3MB)が出力されなくなったこと。
- 本体の −8.0MB の内訳(シンボル): rust −1.1、dawn −0.4、tflite −0.4、名前空間なし −0.6 など。`use_dawn=false` でも tint(3.0MB)は残った。
- Chromium 編の A → B(−8.3MB、配布物 −36.3MB)とほぼ同じ効き方。

## 動作確認

7 項目すべて合格(機能検出、Service Worker、WebSocket、MP4、MSE、EME ClearKey、YouTube 1080p)。スクリーンショット: `logs/screenshots/E2-func-*.png`。

## GN フラグの通過 / 不通過(logs/145、E2 の引数に 1 つずつ追加して `gn gen`)

通過(E3a に入れる):
`is_cfi=false`、`ozone_platform_wayland=false`、`use_gtk=false`、`use_libpci=false`、`use_vaapi=false`、`rtc_use_pipewire=false`、`enable_jxl_decoder=false`、`media_use_iamf_tools=false`、`enable_reporting=false`、`enable_device_bound_sessions=false`、`enable_compute_pressure=false`、`enable_chrome_notifications=false`、`enable_message_center=false`、`enable_backup_ref_ptr_feature_flag=false`、`include_transport_security_state_preload_list=false`、`enable_vectorized_html_scanning=false`、`enable_session_service=false`、`enable_hangout_services_extension=false`、`enable_offline_pages=false`、`enable_bound_session_credentials=false`

通過するが入れない: `enable_library_cdms=false`(Widevine が使えなくなる)。

不通過(アサーションまたは依存の未解決):

| フラグ | 止めたもの |
|---|---|
| `enable_widevine=false` | `//cef/BUILD.gn` の `assert(enable_widevine)` |
| `enable_pdf=false`、`enable_printing=false`、`enable_print_preview=false` | `//cef/BUILD.gn` の `assert(enable_print_preview)` |
| `enable_extensions=false` | `//ui/webui` の `assert(enable_extensions_core)` |
| `enable_plugins=false` | `//pdf` の assert |
| `enable_guest_view=false` | `//extensions` の assert |
| `safe_browsing_mode=0`、`enable_captive_portal_detection=false`、`enable_background_contents=false`、`enable_webui_certificate_viewer=false` | `//chrome` の依存が未解決 |
| `enable_mdns=false`、`enable_service_discovery=false`、`enable_screen_ai_service=false`、`enable_speech_service=false`、`enable_lens_desktop=false`、`enable_compose=false`、`enable_supervised_users=false`、`enable_on_device_translation=false`、`enable_perfetto_trace_processor=false` | `//chrome` 各所の assert |
| `use_gio=false` | GTK が GIO を要求(`use_gtk=false` と同時なら未確認) |

存在しない(158 では引数として定義されていない): `enable_glic`、`enable_nacl`、`enable_ppapi`、`enable_spellcheck`、`enable_basic_printing`、`enable_media_router`、`enable_devtools_frontend`、`enable_dice_support`、`enable_click_to_call`、`enable_feed_v2`、`enable_webui_tab_strip`、`enable_rust_png`、`use_browser_spellchecker`。

コーデック関係(AV1、HLS、MPEG-2 TS)は必要なので試していない。

## 分かったこと

- CEF でも GN フラグだけでは本体は 3% 弱しか減らない。大物(PDF、印刷、拡張機能、Safe Browsing)は `//chrome` と `//cef` のアサーションで守られている。
- 生成段階では `//chrome/test` のターゲットが原因で落ちるフラグが多い(`cefsimple` のビルドには不要なターゲット)。パッチで assert やテスト依存を外せば通る可能性があるが、それは E3 の範囲。

## 計画への反映

- E3 は 2 段に分ける。
  - E3a: パッチなしのまま、上記の通過フラグ 20 個(CFI 無効を含む)を追加。Chromium 編では CFI 無効化が最も効いた(icall のジャンプテーブルが不要コードを生かす)。
  - E3b: E3a に Chromium 編 D1〜D3c のパッチ(Blink モジュール削除)を移植。46 ファイル中 39 はそのまま当たる(logs/144)。
- メモリ計測は `--type=zygote` のプロセスも数える(CEF ではレンダラ / GPU の cmdline が zygote のまま)。

## 追記: メモリ(logs/146、全プロセスの PSS 合計、3 回の中央値、MB)

| 構成 | about:blank | YouTube トップ | 1080p 再生中 |
|---|---|---|---|
| E1 | 589.5 | 1,493.0 | 1,973.0 |
| E2 | 564.9 | 1,420.7 | 1,813.9 |
| 差 | −24.6 | −72.3 | −159.1 |

- プロセス数は 9〜10(ブラウザ、NetworkService、AudioService、zygote 系 7)。
- 再生中の値は回ごとのばらつきが大きい(E1: 1,870〜2,001、E2: 1,784〜1,877)。再生中の差 159MB のうち、構成の違いによる分は blank / トップの差(25〜72MB)程度とみるのが安全。
- about:blank の内訳(E1): file 218.5MB(バイナリのマップ分)、anon 369.0MB。E2 は file が 6MB 減。
- ソフトウェア描画(SwiftShader)と Rosetta 上の値。絶対値ではなく構成間の差を見る。
