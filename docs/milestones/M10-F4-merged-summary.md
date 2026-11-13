# M10: F4 統合ビルドと第 2 期のまとめ

作成: 2026-11-12 18:25 JST、19:35 に F4b を追記。ログ: logs/197、198、300〜311。**最終構成は F4b / F4b-dist**(末尾の「F4b」の章)。前半は F4a(F3a まで)の記録。

## F4a の構成

`/root/cef/chromium/src`、`gn clean` からのクリーンビルド。

- F1: RELR 再配置(`fp_use_relr_relocations=true`)、Dawn の参照除去、追加フラグ 16 個(F2 の 17 個から `pdf_enable_xfa` を除いたもの。PDF ごと外すので不要)、BlueZ の参照除去
- F2: `chrome://` WebUI の登録削除、Alloy スタイル専用化、`resources.pak` の絞り込み(最小モード)
- F3a: `enable_pdf` / `enable_print_preview` / `enable_printing` / `enable_plugins` = false(ライン B のパッチを合流)
- `optimize_for_size=true`(`-Os`。Cast / Android / Fuchsia の既定。Linux デスクトップは既定 false)

第 2 期のパッチ全体: Chromium 28 ファイル(+134 / −51)、CEF 12 ファイル(+121 / −33)、新規 1 ファイル。`logs/patches/f4a.patch`、`f4a-cef.patch`、`f4a-cef-new-print_settings_stub.cc`。args は `logs/results/F4a-args.gn`。

## 結果

| | E1(CEF 既定) | E3b(第 1 期の最小) | **F4a** | **F4a-dist**(配布物トリム) |
|---|---|---|---|---|
| strip 後(`libcef.so` + `cefsimple`) | 299.6MB | 261.6MB | **200.6MB** | 200.6MB |
| 配布物(ja + en-US) | 377.5MB | 311.5MB | **225.0MB** | **216.2MB** |
| E3b 比(配布物) | | | −86.5MB(−27.8%) | −95.3MB(−30.6%) |
| E1 比(配布物) | | −66.0MB(−17.5%) | −152.5MB(−40.4%) | −161.3MB(−42.7%) |
| 動作確認 7 項目 | 7/7 | 7/7 | 7/7(YouTube 1 回目) | 7/7 |
| i18n 確認 | | | OK | OK(単語分割のみ 1 文字単位) |
| 起動時 RAM: 回収不可(anon + shmem) | 451.8MiB | 412.0MiB | 404.1MiB | 404.2MiB |
| 起動時 RAM: `Pss_File` | 231.8MiB | 197.7MiB | 159.8MiB | 159.6MiB |
| 起動時 RAM: 本体 PSS | 253.4MiB | 229.6MiB | 184.4MiB | 184.4MiB |
| PSS blank | 588.0MB | 529.2MB | 487.7MB | |
| PSS YouTube トップ | 1,487.9MB | 1,337.5MB | 1,304.9MB | |
| PSS 1080p 再生中 | 1,976.4MB | 1,813.5MB | 1,772.0MB(有効 3 / 試行 11) | |

- F4a-dist は F4a の配布物から次を外したもの(logs/300、303。バイナリは同じ): `chrome_200_percent.pak`(0.93MB、HiDPI 2 倍用)、`snapshot_blob.bin`(0.36MB、`v8_context_snapshot.bin` を使うので読まれない)、`chrome_crashpad_handler`(2.1MB、クラッシュレポート用)、`libVkICD_mock_icd.so`(テスト用)。`icudtl.dat` を cast 用(5.2MB)に差し替え。
- 保存先: `/root/fp/builds/F4a`、`/root/fp/builds/F4a-dist`。スクリーンショット: `logs/screenshots/F4a-*.png`、`F4a-dist-*.png`。

## 段階別の効果(CEF 第 2 期)

| 段階 | 内容 | strip 後 | 差 | 配布物 | 差 |
|---|---|---|---|---|---|
| E3b | 第 1 期の最小 | 261.6 | | 311.5 | |
| F1a | RELR 再配置 + Dawn の参照除去 | 229.5 | −32.0 | 279.1 | −32.4 |
| F2 | 追加フラグ 17 個 + BlueZ + WebUI 登録削除 + `resources.pak` 絞り込み(PDF 部品あり) | 219.1 | −10.4 | 245.2 | −33.9 |
| F2b1 | Alloy スタイル専用化 | 218.5 | −0.6 | 244.6 | −0.6 |
| F4a | F3a(PDF / 印刷 / プラグイン)+ `-Os` + `resources.pak` 最小 | 200.6 | −17.9 | 225.0 | −19.6 |
| F4a-dist | 配布物トリム + ICU 軽量版 | 200.6 | 0 | 216.2 | −8.8 |

項目別(効果の大きい順。重なりがあるので合計は一致しない):

| # | 項目 | 効果 | 手段 | 代償 |
|---|---|---|---|---|
| 1 | RELR 形式の再配置 | −25.6MB | リンクオプション(GN 引数を 1 個追加) | glibc 2.36 以降が必要 |
| 2 | `resources.pak` の絞り込み | −24.7MB(25.6 → 0.9) | 配布時の後処理(`pakstrip.py`)+ コードキャッシュ生成の停止 | `chrome://` ページと DevTools フロントエンドが使えない |
| 3 | `optimize_for_size=true` | 約 −10MB(推定) | GN フラグ | 速度(未計測)。全体再ビルド |
| 4 | PDF / 印刷プレビュー / 印刷 / プラグイン | −8.2MB(E3b 上での実測、F3a) | buildflag + パッチ(Chromium 21 ファイル、CEF 9 ファイル) | PDF 表示と印刷ができない |
| 5 | Dawn / tint | −5.7MB | 3 行の削除 | なし(WebGPU は元々無効) |
| 6 | ICU データを cast 用に | −5.6MB | 配布時の差し替え | 日本語の単語分割が 1 文字単位になる |
| 7 | 追加フラグ 17 個 + WebUI 登録削除 + BlueZ | 約 −10MB(F1a → F2 の実行ファイル差) | GN フラグ + パッチ 4 ファイル | Bluetooth、OpenH264 エンコード、XFA など |
| 8 | 配布物トリム(200% pak、snapshot_blob、crashpad、テスト用 ICD) | −3.2MB | 配布時の削除 | HiDPI 表示、クラッシュレポート |
| 9 | Alloy スタイル専用化 | −0.6MB | パッチ 4 ファイル | Chrome スタイルが使えない |

- #3 の「約 −10MB」は、F2b1(218.5)から F3a の効果(−8.2。E3b 上での値)を引いた 210.3 と F4a(200.6)の差。F3a と `-Os` を同じビルドに入れたので、単独の値は測っていない。
- #1 と #5 は F1a で同時に入れた。内訳はセクションサイズとマップから出した。

## クリーンビルドで分かったこと(logs/198、301、302)

- 53,447 ステップ。134 分(並列ビルドと重なった)+ 続き 41 分 + 3 分。停止検知の発動 0 回。
- 失敗 2 件。
  1. DevTools フロントエンドの tsc が SIGSEGV(Rosetta 上で既知の一過性の失敗)。再実行で通った。
  2. **F3a パッチのガード漏れ**: `browser_user_education_service.cc` が `pdf_document_helper.h` を無条件に include していた(同じ include が 2 箇所にあり、1 つ目が `#if` の外)。ライン B のツリーは増分ビルドで、古い `pdf.mojom.h` が `gen/` に残っていたので通っていた。`tools/fp/f4_fix.py` で 1 行削除。
- 第 1 期と同じ罠(「削除パッチは増分ビルドでは古い生成物に助けられて通ることがある」)を、今回はクリーンビルドを工程に入れていたので拾えた。

## 起動時 RAM の読み方

- 回収不可(anon + shmem)は E3b 412.0 → F4a 404.1MiB で **8MiB しか減らない**。バイナリを 61MB 削っても、ヒープとして確保される量はほとんど変わらない。
- 減ったのはファイル由来(197.7 → 159.8MiB、−37.9)。再配置テーブルを読まなくなった分(約 −24.5)と、コードが小さくなった分。
- 実機でメモリが足りないときに効くのは「回収不可」のほうなので、RAM を減らしたいなら別の手段が要る(プロセス数、V8 のヒープ設定、レンダラの上限など。今回は対象外)。

## 断念 / 未検証

- `//chrome` の点の根切り(autofill、sync、パスワード管理、Chrome スタイル UI など)は、参照が密で 1 点では切れない。Alloy 専用化で −0.6MB しか出なかったので打ち切った(M8)。
- 追加フラグのうち 8 個は上流のガード漏れで通らなかった(M8 の表)。
- `optimize_for_size` の速度への影響は測っていない(YouTube 1080p のソフトウェアデコード再生は通る)。
- RELR は glibc 2.36 未満では起動しない。ターゲットの libc を確認すること。
- x64 + Rosetta 上の値。ARM の実機では絶対値が変わる。
- 拡張機能 / GuestView(F3b)はライン B で作業中。

## Chromium 編への横展開(logs/199)

RELR は `content_shell` にも効く: D3c-cfi 174.5 → 161.7MB(−12.8MB)、動作確認 7/7。`logs/worklog-footprint.md` 参照。`optimize_for_size` は Chromium 編では未試行。

## F4b: 拡張機能の除去を合流(最終構成、logs/304〜311)

F4a に、ライン B の F3b(`enable_extensions=false`、`enable_platform_apps=false`、`enable_hosted_apps=false`。連動して `enable_extensions_core=false`)を合流させた。

### 結果

| | E1(CEF 既定) | E3b(第 1 期) | F4a | **F4b** | **F4b-dist** |
|---|---|---|---|---|---|
| strip 後(`libcef.so` + `cefsimple`) | 299.6MB | 261.6MB | 200.6MB | **191.2MB** | 191.2MB |
| 配布物(ja + en-US) | 377.5MB | 311.5MB | 225.0MB | **215.4MB** | **206.6MB** |
| E1 比(配布物) | | −17.5% | −40.4% | −162.1MB(−42.9%) | **−170.9MB(−45.3%)** |
| E3b 比(配布物) | | | −27.8% | −96.1MB(−30.9%) | −104.9MB(−33.7%) |
| `resources.pak` | 25.6MB | 25.6MB | 0.9MB | 0.8MB | 0.8MB |
| 動作確認 7 項目 | 7/7 | 7/7 | 7/7 | 7/7(YouTube 1 回目) | 7/7 |
| プロセス数(起動 30 秒後) | 9 | 9 | 9 | **8** | 8 |
| 起動時 RAM: 回収不可(anon + shmem) | 451.8MiB | 412.0MiB | 404.1MiB | **364.0MiB** | 365.7MiB |
| 起動時 RAM: `Pss_File` | 231.8MiB | 197.7MiB | 159.8MiB | 151.5MiB | 151.4MiB |
| 起動時 RAM: 本体 PSS | 253.4MiB | 229.6MiB | 184.4MiB | 173.2MiB | 173.2MiB |
| PSS blank | 588.0MB | 529.2MB | 487.7MB | **430.7MB** | |
| PSS YouTube トップ | 1,487.9MB | 1,337.5MB | 1,304.9MB | 1,265.6MB | |
| PSS 1080p 再生中 | 1,976.4MB | 1,813.5MB | 1,772.0MB | 1,718.5MB(有効 3 / 試行 5) | |

- F4a → F4b: 実行ファイル −9.4MB、配布物 −9.6MB。ライン B 単独の実測(F3a → F3b で −11.0MB、`-O2`)より少し小さいのは、`-Os` と RELR で元が縮んでいるため。
- **拡張機能を外すと RAM が大きく減る**: 回収不可 404.1 → 364.0MiB(−40MiB)。E3b では内蔵のコンポーネント拡張機能(`chrome-extension://admccjkmockfdflocgggjfgdacdodkdf/background.js`)の Service Worker 用にレンダラが 1 個常駐していた(PSS 約 45MiB)。拡張機能がなくなるとこのプロセスが起動しない(logs/311 で DevTools のターゲット一覧とプロセス一覧を比較)。
- ネガティブテスト(`tools/fp/f3_negtest.py`、logs/309): `navigator.pdfViewerEnabled` = false、`navigator.plugins.length` = 0、`chrome.runtime` = undefined。`window.print()`、`<embed type="application/pdf">`、PDF への遷移を実行しても落ちず、その後の通常ページも表示できる。
- `libcef.so` 内の文字列: `pdfium` 0 個、`ExtensionRegistry` 0 個(E3b は 154 個)。
- ライン B の保存物(F3a、F3b)は自分でも動作確認し直した(どちらも 7/7、サイズも報告どおり。logs/309)。
- 保存先: `/root/fp/builds/F4b`、`F4b-dist`。パッチ: `logs/patches/f4b.patch`(Chromium 348 ファイル、+3,871 / −935)、`f4b-cef.patch`(CEF 16 ファイル、+211 / −54)、新規 2 ファイル(`f3b-new-extensions_manager_no_extensions.cc`、`f4a-cef-new-print_settings_stub.cc`)。args: `logs/results/F4b-args.gn`。

### 合流の手順と失敗

1. `/root/cef` で F3a を逆適用 → F3b(基準点からの累積)を適用。どちらも `git apply --check` を通ってから実施(logs/304、305)。F1 / F2 のパッチと同じファイルに触る箇所もあったが衝突なし。
2. 古い生成物の掃除(logs/306): フラグ変更後に `ninja -t targets all` に出てこない `gen/` 以下のファイルのうち、拡張機能 / GuestView / PDF / 印刷に関係するもの 1,614 個を削除。
   - **失敗**: パス名に `extensions` を含む DevTools フロントエンドの副生成物(`models/extensions/bundle-tsconfig.ref.json` など 20 個)まで消し、ninja が「作り方が分からない」で停止した。「`ninja -t targets` に出ない = 古い」とは限らない(出力として宣言されていない副生成物がある)。`gen/third_party/devtools-frontend` を丸ごと消して作り直させた(logs/307)。
3. logs/307 は DevTools の tsc が SIGSEGV(一過性)。logs/308 で「SIGSEGV だけなら続きから再実行」のループを入れて 1 回で成功(3,109 ステップ、17 分)。
4. 最終確認として `gn clean` からのクリーンビルドを実行(logs/310): **51,361 ステップ、128 分、失敗 0、停止検知 0 回、1 回で完走**。strip 後 191.2MB、配布物 215.4MB(増分ビルドの F4b と同じ)。動作確認 7/7、ネガティブテスト OK。保存先 `/root/fp/builds/F4b-clean`。パッチ一式(`f4b.patch`、`f4b-cef.patch`、新規 2 ファイル)と `F4b-args.gn` は、クリーンな状態から通ることを確認済み。

### 拡張機能の除去で変わる挙動(ライン B の報告から。`logs/cef-milestones/M9-F3b-extensions.md`)

- `chrome.*` 拡張 API、`chrome-extension://` スキーム、コンポーネント拡張機能、`--app=URL` / `--app-id` / `--load-apps` が使えない。
- `enable_guest_view=false` は見送り(拡張機能なしの構成では glic と contextual_tasks の WebUI が GuestView に切り替わる。効果は 0.1MB)。
- 動かして確かめたのは Alloy スタイルの `cefsimple` でページを開く経路。右クリックメニュー、ダウンロード、DevTools ウィンドウなど、スタブにした UI 経路は未検証。
- フラグを true に戻した側(拡張機能あり)のビルドは未確認(構文チェックのみ)。
