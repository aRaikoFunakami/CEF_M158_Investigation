# M9 / F3b: 拡張機能、プラットフォームアプリ、ホステッドアプリを buildflag で削除

作成: 2026-11-12 18:40 JST。ログ: logs/230〜299、300b、301b、B302〜B390。ツリー: `/root/cef2/chromium/src`、`out/F3`。
時系列は `logs/worklog-cef-lineB.md`、サブ担当への指示書は `logs/lineB-f3b-subagent-brief.md`。

## 結果

`enable_extensions_core=false`(最終目標)まで切れた。`enable_guest_view=false` は切っていない(下の「境界」)。

| | E3b(基準) | F3a | **F3b** | F3a → F3b | E3b → F3b |
|---|---|---|---|---|---|
| 実行ファイル(strip 後) | 261.6MB | 253.4MB | **242.4MB** | −11.0MB | −19.2MB |
| うち text | 248.8MB | 240.8MB | 230.5MB | −10.3MB | −18.3MB |
| 配布物(ja + en) | 311.5MB | 303.0MB | **291.0MB** | −12.0MB | −20.5MB |
| `resources.pak` | 25.62MB | 25.35MB | 24.41MB | −0.94MB | −1.21MB |
| 動作確認 7 項目 | 7/7 | 7/7 | **7/7**(YouTube 1080p は 1 回目で成功) | | |
| 起動時 RAM 回収不可(anon + shmem、3 回の中央値) | 412.0MiB | 405.7MiB | **365.1MiB** | −40.6MiB | −46.9MiB |
| 起動時 `Pss_File` | 197.7MiB | 196.6MiB | 187.3MiB | −9.3MiB | −10.4MiB |
| 本体 PSS | 229.6MiB | 225.1MiB | 211.2MiB | −13.9MiB | −18.4MiB |
| プロセス数(起動 30 秒後) | 9 | 9 | 8 | −1 | −1 |

数値の出典: `/root/fp/results/F3b-size.json`、`F3b-func.json`、`F3b-startram.json`、`F3b-negtest.json`(logs/B390)。
事前調査(M6)の見込みは拡張機能 7.1MB。実測は −11.0MB で見込みより大きい。起動時 RAM の減り(−40.6MiB)はサイズの減りより大きく、プロセスが 1 個減っている。
どのプロセスが減ったか、RAM の内訳は調べていない(未検証)。

保存先: `/root/fp/builds/F3b`。スクリーンショット: `logs/screenshots/F3b-func-*.png`(8 枚)。

## 入れたフラグ(F3a の 4 個に追加)

```
enable_extensions=false
enable_platform_apps=false
enable_hosted_apps=false
```

`enable_extensions_core` は宣言側の既定(`enable_extensions || enable_desktop_android_extensions`)で false になる。後ろ 2 つも既定で連動するので、実質 1 フラグ。

## 境界: 切らなかったもの

- **`enable_guest_view=false` は入れていない**。Chromium 158 では、`enable_extensions_core=false` のとき glic と contextual_tasks の WebUI が
  `chrome/browser/resources/guest_view_shared`(slim webview、`assert(enable_guest_view)`)に切り替わる(logs/235、237)。
  GuestView まで切るには、依頼範囲外の glic / contextual_tasks の WebUI を外すか壊す必要がある。事前調査で GuestView は 0.1MB なので、切らない側に倒した。
  試したのは GN の段階まで(`gn gen` がその assert で止まるところ)で、ビルドは試していない。
  なお `libcef.so` 内の文字列 `GuestView` は F3a 649 個 → F3b 154 個に減っている(拡張機能側の GuestView 利用が消えたため)。
- `enable_webui_ntp` は true のまま。`ui/webui/webui_features.gni` の `assert(enable_extensions_core)`(NTP が実行時に `chrome.metricsPrivate` を使う)は外した。
  理由: `enable_webui_ntp=false` にすると NTP WebUI への無条件参照が連鎖し、別の機能削除になる(logs/232、233)。**これは assert を外しただけの箇所**で、
  新しいタブページは実行時に動かない可能性がある(未検証。CEF は NTP を表示しない)。

## 作業の流れと規模

| 段 | 内容 | ログ | 結果 |
|---|---|---|---|
| GN | `gnguard.py` の自動ループ + 手動 | 231〜243 | 自動 370 箇所超、BUILD.gn 145 ファイル。約 37 分で `gn gen` 通過 |
| 見積もり | 無条件 include の走査 | 241 | 機能ディレクトリ外の 275 ファイル(722 箇所) |
| ビルド 1 | `--keep-going` で実数取り | 244(62 分) | 失敗 200 オブジェクト。エラー 1,134 行中 997 行が拡張機能ヘッダの `static_assert(BUILDFLAG(ENABLE_EXTENSIONS_CORE))` |
| 第 1 層 | サブ担当 5 人が並列で修正(A ツールバー 45、B アプリ 32、C WebUI 33、D ブラウザ本体 53、E その他 UI 37 + cef) | 250〜299 | OK 155 / NG 0 / GN から外した 45 |
| ビルド 2 | | 301b(29 分) | コンパイルは全部通過。リンクで未定義シンボル 99 個(B302) |
| 第 2 層 | サブ担当 2 人(X: Web アプリ関連 53 個、Y: それ以外 46 個) | B310〜B347 | 定義側の復活、参照側の `#if`、スタブ 1 個 |
| ビルド 3〜5 | | B350、B352、B354 | 自分の編集ミス 1、残りの未定義 1 個を直してリンク成功 |
| 実行時 | 起動直後の CHECK 失敗 1 件 | B355〜B361 | `SupervisedUserMetricsService` の CHECK 条件に `ENABLE_EXTENSIONS_CORE` を追加 |
| 第 3 層 | クリーンビルドで落ちる TU(古い生成ヘッダへの依存)43 個を修正(サブ担当 1 人) | B363〜B380 | OK 35 / GN から外した 8 |
| ビルド 6 | 最終。古い生成物を退避した状態で成功、依存ログで残り 0 を確認 | B390 | 成功 |

ビルド回数: 6 回(1 回目 62 分、2 回目 29 分、3〜5 回目は各 3〜5 分、6 回目 2 分)+ 実行時修正の増分 1 回。停止検知(fpbuild)の発動は 0 回。
構文チェックは `tools/fp/f3b_cc.py`(ninja を動かさず `-fsyntax-only`)で行い、全体ビルドの回数を抑えた。

### エラーの種類と直し方

| 種類 | 規模 | 直し方 |
|---|---|---|
| 機能ディレクトリ外から拡張機能ヘッダを無条件 include(static_assert で停止) | 境界ファイル 131(ヘッダ 24、ソース 107)、196 行 | include と使用箇所を `#if BUILDFLAG(ENABLE_EXTENSIONS_CORE)` / `ENABLE_EXTENSIONS` / `ENABLE_PLATFORM_APPS` で囲む。`#else` は false / nullptr / 何もしない(Android 版の分岐が手本) |
| 拡張機能専用のソースが無条件にビルドされる | GN から外したオブジェクト 45 + 8 | BUILD.gn で `if (enable_extensions_core)` などに移し、参照元を `#if` |
| 上流の GN 条件が広すぎて、無関係なコードまで `if (enable_extensions)` の中 | `chrome/browser/ui/web_applications` の 20 ソース、JS モーダルダイアログ、`system_signals`、`managed_ui_handler` | 条件を `!is_android` などに直してビルドに戻す |
| 定義が機能ディレクトリにあるが拡張機能に依存しない | `SecurityDialogTracker`、`BrowserActionDragData` | 機能ディレクトリ外の BUILD.gn から同じ .cc をコンパイル(機能ディレクトリは無編集) |
| ヘッダに static_assert が無く、コンパイルは通るがリンクで未定義 | 参照側 23 ファイル | 参照側を `#if` |
| 前の構成の生成ヘッダが `out/` に残っていて通っていた | 43 TU | include も `#if` に入れる。settingsPrivate 専用の `generated_*_pref.cc` 7 個と `automation_manager_aura.cc` は GN から外す |
| 実行時の CHECK | 1 件 | CHECK の条件を合わせる |

## スタブ / 何もしない実装にした箇所(理由つき)

- `chrome/browser/web_applications/extensions_manager_no_extensions.cc`(新規): `web_app::ExtensionsManager` の拡張機能なし実装。問い合わせは false / 空、
  `OnExtensionSystemReady` は非同期でコールバック。理由: Web アプリ(PWA)本体が仮想インターフェースとして広く使っていて参照側を切り切れない。上流に Android 用の別実装は無い。
- `WebUIToolbarWebView` の拡張機能アクション 4 メソッド: mojo インターフェースの純粋仮想なので本体だけ空。
- `ToolbarView::GetExtensionsButton()` / `GetExtensionsContainerViews()`、`WebAppFrameToolbarView::GetExtensionsContainerViews()`: nullptr。`ToolbarButtonProvider` のインターフェースを変えないため。
- `chrome::ShowExtensions` / `ShowWebStore`、`ShowFeedbackPage`、`ShowFeedbackDisabledDialog`: 何もしない。呼び出し元が多く、文字列(`IDS_FEEDBACK_*`)と UI が feedbackPrivate API 前提のため。
- `PasswordManagerUI::CreatePageHandler()`: 何もしない(ハンドラが passwordsPrivate デリゲートのアダプタ)。
- dictation / indigo のコンポーネント拡張機能の読み込みとイベント送信、read_anything の音声パック 3 メソッド、`ChromeColorsService` のテーマ復元、
  `ProfileCustomizationSyncedThemeWaiter::Run()`(即 `kSyncCannotStart`)、`customize_chrome::MaybeDisableExtensionOverridingNtp()`。
- `--validate-crx` は false を返す。`BrowserWebContentsDelegate::GuestSaveFrame` は false。

## 挙動が変わる箇所(拡張機能なしのときだけ)

- **`--app=URL`、`--app-id`、`--load-apps`、`--load-and-launch-app`、`--install-chrome-app` が効かない**(実装が platform_apps 側)。
- chrome://password-manager、chrome://feedback は登録されたままだが中身は動かない(ページごと外すと担当外の修正が広がるため残した)。chrome://apps は Web アプリだけ。
- ツールバーの拡張機能ボタンと区切り線、アプリメニューの「拡張機能を管理」アクションが無い。アプリメニューの「拡張機能」サブメニューは残っているが押しても何も起きない。
- BackgroundContents(hosted app 用)を作らない。Safety Hub の拡張機能モジュール、設定ページの「拡張機能が制御」表示、拡張機能テレメトリ(Safe Browsing)が無い。
- 既定のアプリアイコンは `IDR_WEB_APP_DEFAULT_ICON` に置き換え。アプリアイコンのバッジ(blocked / paused)は付かない。
- IWA 削除後のストレージパーティションの掃除(起動時 GC)が予約されない。
- `chrome-extension://` を libcef が内部処理スキームとして扱わなくなる(`scheme_registration.cc`)。

## 触ったファイル

- Chromium: **342 ファイル、+3,848 / −917 行**(F3a の 21 ファイルを含む累積。内訳は .cc 173、.h 40、BUILD.gn 128、.gni 1)。新規 1(`extensions_manager_no_extensions.cc`)。
- CEF: 13 ファイル、+199 / −46 行(F3a の 9 ファイルを含む累積)。新規 1(F3a の `print_settings_stub.cc`)。
- パッチ(基準 847f5575 からの累積、F3a を含む): `logs/patches/f3b.patch`(17,205 行)、`logs/patches/f3b-cef.patch`(692 行)、
  新規ファイル `logs/patches/f3b-new-extensions_manager_no_extensions.cc`、一覧 `logs/patches/f3b-newfiles.txt`。
- 途中段階の差分(コンテナ内): `/root/fp/f3b-gnstage.patch`、`f3b-layer1.patch`、`f3b-layer2.patch`。F3a に戻すには `logs/patches/f3a*.patch`。
- 入れ子のリポジトリは触っていない。機能ディレクトリ(`extensions/`、`chrome/browser/extensions/` など)の中も編集していない。
- 道具: `tools/fp/gnguard.py`(GN 自動修正)、`f3b_scan.py`(規模見積もり)、`f3b_includers.py`(境界ファイル集計)、`f3b_cc.py`(構文チェック)、`f3b_gn.sh`、
  `trapbt.c` / `trapbt.sh`(gdb なしでクラッシュ箇所を特定)、`f3b_iter.sh`、`f3_negtest.py`。

## 確認したこと

- 動作確認 7/7、ネガティブテスト(`window.print()`、PDF、plugins、`chrome.runtime` が undefined)で落ちない(logs/B390)。
- `libcef.so` 内の文字列 `ExtensionRegistry`: F3a 154 個 → F3b 0 個。
- クリーンビルド相当: 古い生成物(`gen/extensions/*` の buildflags 以外など 21MB)を `/root/fp/f3b-stale-gen-bak` に退避した状態でビルドが通り、
  依存ログで「生成ルールの無い生成ヘッダ」に依存する cefsimple のオブジェクトが 0(logs/B390)。
- フラグ true 側(拡張機能あり): 変更した .cc 175 個を、args を一時的に F3a に戻して構文チェック。OK 165、NG 10(logs/B363)。
  NG の 10 個は `IDS_*` や mojom の enum が未定義というエラーで、`out/F3/gen` の生成物が拡張機能なしの状態だったことによるもの(方法の限界)。
  **この 10 個と、リンク、実行は true 側では未確認。**

## 失敗と反省

1. `enable_guest_view=false` と `enable_webui_ntp=false` を先に入れて連鎖に気づき、取り下げた(logs/232〜238)。フラグの連動関係を宣言側で先に読むべきだった。
2. `gnguard.py` の拒否リストに `chrome/test/`(機能ディレクトリではない)を入れてしまい 1 周無駄にした(logs/233、235)。
3. サブ担当 B が作業中に共有ツリーの `gn gen` を約 2 分半壊した(logs/268)。同時編集では GN の変更を直列にする仕組み(ロック)だけでは足りず、変更前の `gn gen` 確認が要る。
4. サブ担当が `/root/fp/tools/` に置いた補助スクリプトが、別の担当の `fp-sync.sh` で消える事故が 2 回(logs/275、295)。指示書に置き場所を書いていなかった。
5. 自分の機械的な挿入(「最後の `#include` の後ろに足す」)が `#if IS_CHROMEOS` の中に入り、ビルド 1 回分を無駄にした(logs/B350、B351)。
6. 増分ビルドの成功を「成功」と扱いかけた。`out/` に前の構成の生成ヘッダが残っていて、43 TU がそれに頼って通っていた(logs/B363〜B365)。
   buildflag を変えたら、生成ルールが消えた生成物を退避してから確認するべき。最初の確認(B363)は buildflags.h まで退避して判定が無効になり、やり直した(B364、B365)。
7. `trapbt` は 3 回作り直した(ハンドラが上書きされる、backtrace が 1 フレームしか取れない、シンボライザの引数)。

## 未検証 / 残った課題

- **本当のクリーンビルドはしていない**(退避と依存ログによる確認まで)。M10 の統合時に確認が要る。
- **フラグ true 側**は構文チェック 165/175 まで。パッチを上流相当の構成に当てて壊れないかは未確認。
- `chrome/browser/autofill/generated_find_and_fill_with_gemini_pref.cc` は拡張機能なしではコンパイルできないが、cefsimple に入らないので触っていない。テストターゲットも未対応(`all` はビルドできない)。
- `gn check` は通していない(機能ディレクトリの .cc を外の BUILD.gn からコンパイルしている 2 箇所が指摘される可能性)。
- 確認したのは Alloy スタイルの `cefsimple` でページを開く経路だけ。Chrome スタイル、右クリックメニュー、ダウンロード、DevTools、chrome:// ページ、
  サイドパネル、PWA のインストールなど、スタブにした UI 経路は実行していない。`SidePanelEntryId::kExtension` のキーが来ると CHECK に落ちる箇所がある(来ない前提)。
- pak に `IDR_WEB_APP_DEFAULT_ICON` が入っているかは GN の記述からの判断で、中身は見ていない(無ければ `chrome://app-icon/` で CHECK)。
- 起動時 RAM が 40MiB 減った理由(減った 1 プロセスが何か)は未調査。
- `/root/cef` 側(F1 / F2)との合流は未実施。WebUI の登録を外す F2 と、WebUI ハンドラを `#if` にした本パッチは同じファイルを触っている可能性が高い。
