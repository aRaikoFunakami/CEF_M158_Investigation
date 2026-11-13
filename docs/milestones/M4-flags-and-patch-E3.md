# M4: 追加フラグ(E3a)と Blink モジュール削除パッチ(E3b)

完了: 2026-11-12 03:45 JST(logs/146〜162)。最終構成は E3b。E3c(おまけのフラグ 3 個)は効果 −0.1MB で不採用。

## 結果

| 構成 | 内容 | strip 後 | text / data | 配布物 ja + en | 配布物 全ロケール | 動作確認 |
|---|---|---|---|---|---|---|
| E1 | CEF 既定のリリース | 299.6MB | 285.3 / 14.3 | 377.5MB | 428.0MB | 7/7 |
| E2 | E1 + GN フラグ 17 個 | 291.6MB | 277.5 / 14.1 | 342.0MB | 392.5MB | 7/7 |
| E3a | E2 + GN フラグ 17 個(CFI 無効を含む)、パッチなし | 273.5MB | 260.2 / 13.3 | 323.5MB | 373.9MB | 7/7 |
| E3b | E3a + Blink モジュール 41 個の削除パッチ + 最小ルート | **261.6MB** | 248.8 / 12.8 | **311.5MB** | 362.0MB | 7/7 |

- strip 後は `libcef.so` + `cefsimple`。E1 → E3b で −38.0MB(−12.7%)。配布物(ja + en)は −66.0MB(−17.5%)。
- 動作確認 7 項目: 機能検出、Service Worker、WebSocket、MP4、MSE、EME(ClearKey)、YouTube 1080p。スクリーンショットは `logs/screenshots/E3a-*.png`、`E3b-*.png`。
- コーデックは全構成で同じ: H.264 / AAC / VP8 / VP9 / AV1 / Opus / Vorbis / MP3 / FLAC / MPEG-2 TS 可。YouTube は AV1 + Opus の 1080p60 を選ぶ。Widevine は CDM 取得後の再起動で有効(E1 と同じ挙動)。

### メモリ(全プロセスの PSS 合計、MB、logs/161)

| 構成 | about:blank | YouTube トップ | 1080p 再生中(再生を確認できた 3 回の中央値) | 再生点の有効回 / 試行 |
|---|---|---|---|---|
| E1 | 588.0 | 1,487.9 | 1,976.4 | 3 / 4 |
| E2 | 565.0 | 1,407.6 | 1,890.5 | 3 / 6 |
| E3a | 537.9 | 1,375.5 | 1,826.7 | 3 / 4 |
| E3b | 529.2 | 1,337.5 | 1,813.5 | 3 / 9 |

- E1 → E3b: blank −58.8MB(−10%)、トップ −150.4MB(−10%)、再生中 −162.9MB(−8%)。
- blank の内訳(E3b): file 191.4MB(E1 218.6)、anon 335.8MB(E1 367.5)。
- SwiftShader + Rosetta 上の値。絶対値ではなく構成間の差を見る。
- logs/146 までの「再生中」の値は、再生が止まっていた回が混じっていたので破棄(下の「YouTube の間欠エラー」)。

### シンボル内訳(text + data、MB)

| 区分 | E1 | E3a | E3b |
|---|---|---|---|
| 名前空間なしの C++(主に `//chrome` 層) | 41.2 | 38.9 | 37.4 |
| blink | 40.1 | 38.1 | 33.2 |
| v8 | 26.8 | 26.2 | 26.2 |
| base | 11.5 | 10.2 | 10.0 |
| rust | 8.6 | 5.5 | 5.5 |
| content | 8.3 | 8.3 | 8.3 |
| mojo | 5.8 | 5.6 | 5.1 |
| extensions | 4.8 | 4.9 | 4.9 |
| webrtc | 3.9 | 3.8 | (上位から消えた) |
| autofill | 3.1 | 3.1 | 3.1 |

## E3a: 追加フラグ

logs/145 で `gn gen` を通った 20 個のうち、最終的に使えたのは 17 個。

採用(17): `is_cfi`、`ozone_platform_wayland`、`use_gtk`、`use_libpci`、`use_vaapi`、`rtc_use_pipewire`、`enable_jxl_decoder`、`media_use_iamf_tools`、`enable_reporting`、`enable_device_bound_sessions`、`enable_compute_pressure`、`enable_backup_ref_ptr_feature_flag`、`include_transport_security_state_preload_list`、`enable_vectorized_html_scanning`、`enable_hangout_services_extension`、`enable_offline_pages`、`enable_bound_session_credentials`(すべて `=false`)。

脱落(3):

| フラグ | 段階 | 症状 |
|---|---|---|
| `enable_message_center=false` | コンパイル | `ui/message_center/dummy_message_center.cc` が「Android / Fuchsia 専用」の `#error`(logs/146) |
| `enable_session_service=false` | コンパイル | `application_lifetime_desktop.cc` の未使用関数(-Werror)、`profile_manager.cc` の不完全型(logs/147) |
| `enable_chrome_notifications=false` | 起動 | `notification_platform_bridge_delegator.cc` の `Check failed: message_center_bridge_` → SIGSEGV(logs/153) |

教訓: `gn gen` 通過 → コンパイル通過 → 起動 → 動作確認、の 4 段階は別物。デスクトップ Linux で普段オフにされないフラグは、どこかの段階で落ちる。

E2 → E3a の −18.1MB の大半は CFI 無効化とみられる(Chromium 編でも最も効いた)。フラグ別の寄与は切り分けていない。

## E3b: Blink モジュール削除パッチの移植

- 元: Chromium 編 D3c のパッチ(159、`content_shell` 向け、46 ファイル)。
- CEF ツリー(158 + CEF パッチ)には 39 ファイルがそのまま当たり、7 ファイルが reject。
  - `generated_in_modules.gni`、`idl_in_modules.gni`、`modules/BUILD.gn`: 削除行を完全一致で消す方式で解決(`tools/fp/e3b_fix.py`)。
  - `media_capabilities.cc`、`content/utility/services.cc`: 158 の形に合わせて同じ削除。
  - ルート `BUILD.gn`: `//cef:cefsimple` だけの最小構成に置き換え。
  - `content/shell/app/shell_main_delegate.cc`: `content_shell` 専用なので放置。
- ビルド: コンパイルエラー 0。リンクで未定義シンボル 1 個(`blink::SetIdpSigninStatus`、FedCM。`chrome/renderer/url_loader_throttle_provider_impl.cc` が参照)→ `modules/exported/fp_stubs.cc` に空のスタブを置いて解決。
- パッチ: `logs/patches/e3b.patch`(移植分)、`logs/results/e3b-final.patch`(スタブを含むツリー全体の差分。CEF 標準パッチの差分も含む)。
- 削除したモジュール(41。全件は `removed-items.md`): ai、app_banner、background_fetch、background_sync、badging、battery、bluetooth、breakout_box、contacts_picker、content_index、credentialmanagement、direct_sockets、eyedropper、font_access、handwriting、hid、idle、imagecapture、managed_device、mediacapturefromelement、mediarecorder、mediastream、ml、nfc、notifications、payments、peerconnection、push_messaging、sensor、serial、shapedetection、smart_card、speech、wake_lock、webmidi、webrtc、webshare、webusb、xr ほか。
- 効果: −11.9MB(blink −4.9MB、webrtc −3.8MB 相当、`//chrome` 層 −1.5MB ほか)。

`//chrome` 層は Blink モジュールをほとんど直接参照していない(ブラウザ側は mojo インターフェース越し)。そのため Chromium 編のレンダラ側パッチは、ほぼそのまま CEF に持ち込める。

### 最小ルートでのフラグ再試験(logs/152、160)

ルートを `cefsimple` だけにしても、大物のフラグは通らない。`//cef` や `//chrome` の本体から直接 assert / 依存に届くため。

- 引き続き不通過: `enable_pdf`、`enable_printing`、`enable_print_preview`、`enable_extensions`、`enable_plugins`、`enable_guest_view`、`safe_browsing_mode=0`、`enable_captive_portal_detection`、`enable_supervised_users`、`enable_screen_ai_service`、`enable_speech_service`、`enable_lens_desktop`、`enable_compose`、`enable_on_device_translation`、`enable_perfetto_trace_processor`、`enable_background_contents`、`enable_webui_certificate_viewer`。
- 新たに `gn gen` 通過: `enable_mdns=false`、`enable_service_discovery=false`、`use_gio=false` → E3c として試験(logs/162)。

### E3c の結果(logs/162)

| 構成 | strip 後 | text / data | 配布物 ja + en | 配布物 全ロケール | 動作確認 |
|---|---|---|---|---|---|
| E3b | 261.6MB | 248.8 / 12.8 | 311.5MB | 362.0MB | 7/7 |
| E3c(E3b + 3 フラグ) | 261.5MB | 248.7 / 12.8 | 311.4MB | 361.9MB | 7/7(YouTube は 1 回目で再生) |

- ビルドは 25,477 ステップ、90 分(停止 0 回)。`use_gio` が広い設定に効くため、ほぼ全体の再コンパイルになった。
- 効果は −0.1MB。90 分の再ビルドに見合わないので **不採用**(最終構成は E3b)。メモリ、コーデック、シンボル内訳は測っていない。
- 反省: 効果の見込みが小さいフラグで全体再ビルドを流した。先に `gn desc` / `gn refs` で影響範囲を見るべきだった。
- `out/E3` は E3c の状態のまま。E3b の引数は `logs/results/E3b-args.gn`、バイナリは `/root/fp/builds/E3b`。

### クリーンビルド対応(logs/164〜166、2026-11-12 追記)

- Chromium 編のクリーンビルド(logs/164)で、移植元のパッチが古い生成ヘッダ(`gen/` の残骸)に依存していると判明。E3b も `out/E3` の増分ビルドだったので同じ不備があった。
- 検証: `out/E3/gen/.../bindings/modules/v8/` から、ninja の出力に含まれないファイル 1,782 個(3,589 個中)を削除 → `tools/fp/clean_fix.py` を適用 → 再ビルド(3 分、失敗 0)。
- 結果(E3c の引数のまま): strip 後 261.5MB(修正前と同じ)、動作確認 7 項目合格。修正はサイズに影響しない。
- 修正後のツリー全体の差分: `logs/patches/e3b-final-clean.patch`。記事にはこちらを使う。
- 完全なクリーンビルド(`gn clean` から約 3 時間)は CEF 側では行っていない。

## YouTube の間欠エラー(計測方法の変更)

- 症状: 再生開始時、または再生 40 秒付近で "Something went wrong. Refresh or try again later."。`playabilityStatus` は OK、`video.error` なし。
- E1、E2、E3a、E3b、および Chromium 編 D2(`content_shell`、159)のすべてで出る(logs/157、159)。構成にも CEF にも依存しない。
- `--disable-component-update` を付けても出る(logs/158)。Widevine CDM の取得は無関係。
- 原因は未特定。YouTube 側の制限とみている(短時間に新規プロファイルで繰り返し開いている)。
- 止まった回は PSS が 50〜100MB 低く出る。logs/146 までの「再生中」の中央値には止まった回が混じっていた。
- 対策(`tools/fp/measure.py`): メモリは再生点で `readyState >= 3`、再生中、`currentTime > 5` を確認し、有効な回が 3 回集まるまで繰り返す(最大 12 回)。止まった回は `yt_play_stopped` として残し、中央値から除く。動作確認は YouTube を最大 4 回開き直し、試行回数を記録する。

## Chromium 編との対比(strip 後)

| | Chromium 編 | CEF 編 |
|---|---|---|
| 基準(`chrome` / CEF 既定) | A 309.8MB | E1 299.6MB |
| GN フラグのみ | B(`chrome`) | E2 291.6MB、E3a 273.5MB |
| Blink モジュール削除まで | D3c 160.4MB(`content_shell`) | E3b 261.6MB |

差の約 100MB は `//chrome` 層(ブラウザ UI、拡張機能、PDF、印刷、同期、自動入力、Safe Browsing など)。CEF は Chrome ランタイムのみになったため、`content_shell` に替えて一気に落とす手が使えない。Alloy スタイルでも UI のコードはリンクされたまま。

## 計画への反映

- M4 は E3b で完了とする(E3c は通ったが −0.1MB のため差し替えない)。
- M5: メモリは logs/161 で E1〜E3b を測定済み。残りは総まとめ(Chromium 編との対比、限界、残る削減余地)。
- さらに減らすなら `//chrome` 層と `//cef` 自身への書き換えが必要(PDF / 印刷 / 拡張機能の assert を外す、Safe Browsing を外すなど)。CEF 本体の改造になり、工数は E3b の比ではない。
