# M7: F1 リンク設定と追加フラグ

作成: 2026-11-12 12:10 JST。ログ: logs/180〜182、186、188。F1b(追加フラグ 26 個)は M8 の F2 と同じビルドで試す(logs/187)。

## F1a: RELR 再配置 + Dawn の参照除去

### 変更(`tools/fp/f1_patch.py`、2 ファイル)

1. `build/config/compiler/BUILD.gn`: GN 引数 `fp_use_relr_relocations`(既定 false)を追加。true のとき Linux のリンクに `-Wl,-z,pack-relative-relocs` を付ける。
2. `content/utility/utility_main.cc`: `on_device_model::PreSandboxInit()` の呼び出し 3 行を削除。

`args.gn` に `fp_use_relr_relocations=true` を追加。

### なぜ効くか

- **RELR**: 位置独立な共有ライブラリは、ロード時に書き換えるアドレスの一覧(再配置テーブル)を持つ。従来形式(`.rela.dyn`)は 1 件 24 バイトで、`libcef.so` には約 107 万件、25.8MB あった。RELR 形式(`.relr.dyn`)は「連続したアドレスをビットマップで表す」圧縮形式で、同じ内容が 0.2MB になる。ChromeOS と Android の Chrome は以前から使っているが、Linux デスクトップ版のビルド設定では有効になっていない。
- **Dawn**: `use_on_device_model_service=false`(E2 で設定済み)でも、ユーティリティプロセスの起動処理に `on_device_model::PreSandboxInit()` の呼び出しが残っていた。この関数が Dawn(WebGPU の実装)のインスタンスを作るので、`use_dawn=false` にしていても Dawn 本体と tint(シェーダコンパイラ)がリンクされ続けていた。リンカの `--why-live` で参照元をたどって特定した(logs/180)。

### 結果(logs/182、188)

| | E3b(第 1 期の最小) | F1a | 差 |
|---|---|---|---|
| strip 後(`libcef.so` + `cefsimple`) | 261.6MB | **229.5MB** | −32.0MB(−12.2%) |
| うち `.rela.dyn` + `.relr.dyn` | 25.8MB | 0.2MB | −25.6MB |
| うち Dawn / tint / SPIR-V | 5.8MB | 0.09MB | −5.7MB |
| 配布物(ja + en-US) | 311.5MB | **279.1MB** | −32.4MB |
| 動作確認 | 7/7 | 7/7(YouTube は 1 回目) | |
| 起動時 RAM: 回収不可(anon + shmem) | 412.0MiB | 409.0MiB | −3.0 |
| 起動時 RAM: ファイル由来(`Pss_File`) | 197.7MiB | 173.2MiB | **−24.5** |
| 起動時 RAM: 本体 RSS / PSS | 656.7 / 229.6MiB | 553.1 / 202.3MiB | −103.6 / −27.3 |

- ファイル由来の RAM が 24.5MiB 減った。従来形式では、ロードのたびに各プロセスが再配置テーブル 25.8MB を全部読む(9 プロセスで共有されるので PSS では 1 回分)。RELR ではそれがなくなる。
- 回収不可はほぼ変わらない。再配置で書き換えられるページ(`.data.rel.ro` 11.7MB)の量は形式を変えても同じ。
- 実行ファイル: `/root/fp/builds/F1a/`。スクリーンショット: `logs/screenshots/F1a-func-*.png`、`F1a-page-i18n.png`。

### 失敗と注意

1. **リンクオプションの選び方**(logs/180、182 try1): 最初は `-Wl,--pack-dyn-relocs=relr` を使い、リンクは通ってサイズも減った。しかしビルド途中で使うホストツール(`protoc`、`nasm`)が `DT_RELR without GLIBC_ABI_DT_RELR dependency` で起動に失敗した。glibc は、`GLIBC_ABI_DT_RELR` というバージョン依存の印がない RELR バイナリをロードしない(古い glibc で黙って壊れるのを防ぐ仕組み)。`-Wl,-z,pack-relative-relocs` はその印も付ける。**logs/180 の「235.1MB」は起動確認をしていない値**で、そのバイナリは動かなかったはずである。
2. **再ビルドの範囲**(logs/182): リンクフラグを全体の config に入れたので、ホストツールも再リンクされ、その出力(生成コード)が作り直されて約 13,700 ステップの再ビルドになった(並列ビルドと重なり 84 分)。`libcef.so` だけに付ければリンク 1 回(2 分)で済む。最終形では `libcef` ターゲットだけに付ける形に直す予定。
3. **実行環境の条件**: RELR は glibc 2.36 以降(2022 年 8 月)が必要。musl は 1.2.4 以降。それより古い libc の組み込み Linux では起動しない。採用前にターゲットの libc を確認すること。
4. ビルドを止めるときに `pkill -f` のパターンが自分自身のシェルに一致して途中で落ち、ninja が 2 本同時に走った(logs/182 try2)。`ps` で PID を確認してから止めるようにした。

## 追加フラグの調査(logs/181)

候補 58 個を E3c の `args.gn` に 1 個ずつ足して `gn gen` だけ通した。

- 通過 33 個。ただし `enable_spellcheck` は 158 に存在しない引数(gn は警告だけ出して通す)なので除外。
- 第 1 期で起動時に落ちた `enable_chrome_notifications`、コンパイルが通らなかった `enable_session_service`、`enable_message_center` は除外。
- 音声出力や入力に関わる `use_alsa`、`use_pulseaudio`、`use_udev`、HLS(`enable_hls_demuxer`)は残す。
- 全体の再コンパイルになる `optional_trace_events_enabled`、`enable_trace_logging` は後回し(M10 のクリーンビルドで試すか判断する)。
- 残り 26 個を F1b として logs/187 でビルド中: `use_bluez`、`media_use_openh264`、`safe_browsing_use_unrar`、`angle_has_frame_capture`、`enable_gwp_asan`、`enable_webui_bookmarks`、`enable_webui_contextual_tasks_composebox`、`enable_webui_generate_code_cache`、`enable_glic_internal_resources`、`enable_pdf_translation`、`enable_browser_speech_service`、`enable_media_remoting`、`enable_gpu_channel_media_capture`、`enterprise_content_analysis`、`enterprise_local_content_analysis`、`enterprise_proxy`、`structured_metrics_enabled`、`choice_screen_in_chrome`、`headless_enable_commands`、`enable_memory_coordinator_internals`、`glslang_enable_hlsl`、`build_tflite_with_xnnpack`、`produce_v8_compile_hints`、`pdf_enable_xfa`、`enable_pdf_ink2`、`enable_pdf_save_to_drive`(すべて false)。
- `gn gen` で落ちた 25 個のうち、`safe_browsing_mode=0`、`enable_captive_portal_detection`、`enable_background_contents`、`enable_webui_certificate_viewer` は、ビルド対象外のテストターゲット(`browser_tests`)の依存が解決できないだけ。パッチで通せる見込みがある。

## ICU データの軽量版(logs/186、ビルド不要の試行)

`icudtl.dat` は 10.8MB。`third_party/icu` には用途別のデータが同梱されている。配布物の `icudtl.dat` を差し替え、`tools/fp/site/i18n.html`(Intl の日付 / 数値 / 相対時刻 / リスト / 地域名、照合、分かち書き、Shift_JIS / EUC-JP / ISO-2022-JP / GBK / EUC-KR / Big5 のデコード、正規化、IDN)を開いて確認した。

| データ | サイズ | 結果 |
|---|---|---|
| `common`(現在) | 10.8MB | 全項目 OK |
| `chromecast_video` | 6.9MB | ページ評価中に落ちる。不可 |
| `cast` | 5.2MB | 1 項目を除き OK |
| `flutter_desktop` | 1.8MB | 起動しない。不可 |

- `cast` で変わるのは**日本語の単語分割**だけ。`Intl.Segmenter('ja', {granularity: 'word'})` が「今日|は|良い|天気|です|ね」ではなく 1 文字ずつに分かれる(CJK の辞書が入っていない)。ダブルクリックでの単語選択も同じ影響を受けるはず。日付、数値、和暦、文字コード変換、行の折り返しは同じ結果。
- 効果は −5.6MB。単語分割を使わない TV 向けなら採用できる。M10 の最終構成で「採用した場合」と「しない場合」を分けて示す。

## 起動時 RAM(第 1 期までの全構成)

`logs/startup-ram.md` にまとめた(logs/178)。
