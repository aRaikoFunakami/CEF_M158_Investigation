# M9 / F3a: PDF、印刷プレビュー、印刷、プラグインを buildflag で削除

作成: 2026-11-12 12:55 JST。ログ: logs/200〜229、234。ツリー: `/root/cef2/chromium/src`、`out/F3`。

## 結果

| | E3b(基準) | F3a | 差 |
|---|---|---|---|
| 実行ファイル(strip 後、`cefsimple` + `libcef.so`) | 261.6MB | **253.4MB** | −8.2MB |
| うち text | 248.8MB | 240.8MB | −8.0MB |
| 配布物(ja + en) | 311.5MB | **303.0MB** | −8.5MB |
| `resources.pak` | 25.62MB | 25.35MB | −0.28MB |
| 動作確認 7 項目 | 7/7 | **7/7**(YouTube 1080p は 1 回目で成功) | |
| 起動時 RAM 回収不可(anon + shmem、3 回の中央値) | 412.0MiB | **405.7MiB** | −6.3MiB |
| 起動時 `Pss_File` | 197.7MiB | 196.6MiB | −1.1MiB |
| 本体 PSS | 229.6MiB | 225.1MiB | −4.5MiB |

数値の出典: `/root/fp/results/F3a-size.json`、`F3a-func.json`、`F3a-startram.json`(logs/229)。E3b は `E3b-size.json`、`E3b-startram.json`。
事前調査(M6)の見込みは PDF 5.6 + 印刷 1.0 + プラグイン 0.2 = 6.8MB。実測は −8.2MB で見込みより大きい。

保存先: `/root/fp/builds/F3a`。スクリーンショット: `logs/screenshots/F3a-func-*.png`。

## 入れたフラグ

```
enable_pdf=false
enable_print_preview=false
enable_printing=false
enable_plugins=false
```

連動: `enable_basic_print_dialog`、`enable_oop_printing`、`enable_pdf_ink2` などは宣言側の既定で false になる(個別には指定していない。生成ヘッダで 0 を確認、logs/236)。

## `gn gen` で出たエラーと直し方(logs/201〜213、開始から通過まで 4 分)

| 種類 | 件数 | 直し方 |
|---|---|---|
| `//cef/BUILD.gn` の `assert(enable_print_preview)` | 1 | 削除し、印刷 / PDF / プラグインの deps と sources を `if (enable_printing)` / `if (enable_pdf)` / `if (enable_plugins)` に移動。`pdf_resources.h`(`cef_pack_resources.h` の入力)も条件つきに |
| `assert(enable_*)` のある BUILD.gn を、別の BUILD.gn のリスト要素が読み込ませる | 12 | 要素をリストから抜き、直後に `if (cond) { deps += [ ... ] }` を入れる(`tools/fp/gnguard.py` で自動) |
| Unresolved dependencies(`if (enable_printing)` の中で定義されるターゲットへの無条件参照) | 8 | 同上(自動) |
| 自動で直せなかった形 | 2 | `browser_web_contents_delegate` の `//components/printing/browser`(手動で行指定)、`enterprise/data_protection` の `print_utils_unittest.cc`(条件式に `enable_printing &&` を追加) |

Chromium 側で触った BUILD.gn は 14 ファイル。大半はテスト用ターゲット(`chrome/test`、`*_test_utils`)で、`cefsimple` のビルドには入らないが、GN は読み込んだ BUILD.gn を全部評価するので直さないと `gn gen` が通らない。

## コンパイル / リンクエラーと直し方

| ビルド | ログ | 所要 | 失敗 | 内容 |
|---|---|---|---|---|
| 0 回目 | logs/215 | 即終了 | | GN に書いた `print_settings_stub.cc` を作る前に投入した |
| 1 回目 | logs/219 | 6,736 秒(112 分)、8,956 ステップ | コンパイル 6 ファイル | 下の表 |
| 2 回目 | logs/225 | 3 分 | コンパイル 2 ファイル | 1 回目の修正の誤り 1(`contents` の宣言まで `#if` に入れた)、未使用関数 1(`-Werror,-Wunused-function`) |
| 3 回目 | logs/227 | 9 分 | リンク 1(未定義シンボル 2 個) | `browser_web_contents_delegate.cc` の `printing::PrintCompositeClient`(GN の deps だけ条件つきにしてソースが無条件だった) |
| 4 回目 | logs/228 | 5 分 | 0 | 成功 |

停止検知(fpbuild)の発動は 0 回。

1 回目の 6 ファイル(`tools/fp/f3a_fix1.py`):

| ファイル | 原因 | 直し方 |
|---|---|---|
| `chrome/browser/about_flags.cc` | `glic-pdf-summarize` が `ENABLE_PDF` 内で宣言される `features::kPdfGlicSummarize` を使う | `#if !IS_ANDROID && ENABLE_PDF` |
| `chrome/browser/renderer_context_menu/render_view_context_menu.cc` | `prefs::kPrintingEnabled` は `ENABLE_PRINTING` のときだけ定義 | `IsPrintPreviewEnabled()` を印刷なしでは false |
| `chrome/browser/ui/views/user_education/browser_user_education_service.cc` | PDF の IPH 2 件(Glic 要約、Searchify)が無条件。include は `ENABLE_PDF_INK2` 条件だった | 2 件と include を `ENABLE_PDF` に。BUILD.gn の dep も `enable_pdf` に |
| `chrome/browser/ui/read_anything/read_anything_entry_point_controller.cc` | `GetPdf()` の戻り値型 `pdf::PDFDocumentHelper*` が `#if` の外 | `GetPdf()` と呼び出し 2 箇所を `ENABLE_PDF` に |
| `chrome/browser/ui/webui/side_panel/read_anything/read_anything_untrusted_page_handler.cc` | `chrome_pdf::features`、`pdf_frame_util` が無条件 | PDF 判定ヘルパーを PDF なしでは「PDF でない」に |
| `cef/libcef/browser/alloy/alloy_browser_host_impl.cc` | `chrome::kChromeUIPrintHost` は `ENABLE_PRINT_PREVIEW` のときだけ定義 | 許可ホスト一覧の該当行を `#if` |

CEF 本体(`tools/fp/f3a_cef_fix.py`、ビルド前に修正): `alloy_browser_host_impl.cc`、`browser_context.h`、`browser_guest_util.cc`、`browser_platform_delegate.cc`、`chrome_browser_main_extra_parts_cef.{h,cc}`、`print_util.cc`、`chrome_content_renderer_client_cef.cc`。

### スタブにした箇所と理由

- `cef/libcef/browser/print_settings_stub.cc`(新規): `CefPrintSettings::Create()` が nullptr を返す。公開 API で `libcef_dll` のラッパーが参照するため定義が必要だが、`enable_printing=false` では `//printing`(`printing::PrintSettings`)自体がビルドできない(`printing/BUILD.gn` が assert)。
- `print_util.cc`: `Print()` は何もしない。`PrintToPDF()` はコールバックに失敗を返す。CEF の公開 API(`CefBrowserHost::Print` / `PrintToPDF`)は残るが機能しない。

## 触ったファイル

- Chromium: 21 ファイル、+111 / −33 行(BUILD.gn 14、C++ 7)。`logs/patches/f3a.patch`(687 行)。
- CEF: 9 ファイル、+109 / −25 行、新規 1(`print_settings_stub.cc`)。`logs/patches/f3a-cef.patch`(404 行)、`logs/patches/f3a-cef-new-print_settings_stub.cc`。
- 入れ子のリポジトリ(`third_party/pdfium` など)は触っていない。
- 基準: `/root/fp/base-sha_root_cef2_chromium_src.txt`(847f5575、第 1 期のパッチ適用後)、CEF は HEAD。
- 修正スクリプト: `tools/fp/gnguard.py`、`tools/fp/gngen.py`、`tools/fp/f3a_cef_fix.py`、`tools/fp/f3a_fix1.py`。

## 削れたことの確認(logs/234、`tools/fp/f3_negtest.py`)

- `navigator.pdfViewerEnabled` = false、`navigator.plugins.length` = 0、`navigator.mimeTypes.length` = 0。
- `window.print()` は例外なく戻り、プロセスは落ちない。`<embed type="application/pdf">` の追加、PDF の data URL への遷移でも落ちない。その後 `caps.html` は pass。
- `libcef.so` 内の文字列 `pdfium`: E3c 3,370 個 → F3a 0 個。`PrintPreview`: 533 → 10。

## 失敗と反省

1. `gnguard.py` の最初の版が機能そのもののディレクトリ(`components/printing/browser`)を自動修正した。読み込ませた側を直すべきなので `git checkout` で戻し、機能ディレクトリの拒否リストを足した(logs/207、208)。
2. GN に新規ファイルを書いたのに、ファイルを作る前にビルドを投入した(logs/215)。数分後の status 確認で気づいた。
3. ビルド 1 回目の修正で変数宣言まで `#if` に入れた(logs/226)。ビルド 2 回目の開始後に直したため反映されず、1 回分(3 分)無駄にした。
4. GN の deps だけ条件つきにしてソースを見なかった箇所がリンクで落ちた(ビルド 3 回目)。GN で dep を外したら、同じディレクトリのソースの include も同時に確認するべきだった。

## 未検証 / 残った課題

- 連動フラグは生成された buildflag ヘッダで確認済み(logs/236): `ENABLE_BASIC_PRINT_DIALOG`、`ENABLE_OOP_PRINTING`、`ENABLE_OOP_PRINTING_NO_OOP_BASIC_PRINT_DIALOG`、`ENABLE_PDF_INK2`、`ENABLE_PDF_SAVE_TO_DRIVE` はすべて 0。
- クリーンビルドでは確認していない(`out/F3` は E3c からの増分)。M10 の統合時に確認が要る。
- `--use-alloy-style` 以外(Chrome スタイル)での起動、右クリックメニューの「印刷」項目の見え方は未確認。
- PDF へ遷移したときの挙動(ダウンロードになるのか、空白表示か)は「落ちない」ことしか見ていない。
- `chrome://print` などの WebUI を直接開いたときの挙動は未確認。
