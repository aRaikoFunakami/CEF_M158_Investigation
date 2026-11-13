# M6: 追加削減の調査と計画(CEF 第 2 期)

作成: 2026-11-12 10:20 JST。ログ: logs/167〜178。

## きっかけ

2026-11-12 のユーザー指示: 「パッチ可としたのに PDF、印刷、印刷プレビュー、拡張機能、プラグイン、GuestView を削っていないのはなぜか」→「工数が大きくても、TV ブラウザに不要と想定できる機能を削って CEF で最小の ROM サイズを目指せ。調査してから挑戦。並列にできるものは並列に。CPU とストレージを確認しながら。全ログ、マイルストーンごとのまとめ、計画の更新、実行ファイルの保存、動作確認、起動時 RAM の記録(https://qiita.com/rairaii/items/d5a5c3da56dbc7063a19 の方法。UPX は不要)」。

第 1 期(M0〜M5)は GN フラグと Blink モジュール削除パッチの移植で止め、`//chrome` 層と `//cef` 本体には手を入れなかった。第 2 期はそこに踏み込む。

## 環境(logs/167)

- コンテナ: 25 CPU、メモリ 62GB、ディスク空き 297GB(504GB 中)。ビルド中のプロセスなし。
- ツリー: `/root/cef`(77GB、うち out 33GB)。保存済みビルド `/root/fp/builds/E1〜E3c-clean`。
- 並列作業用に `/root/cef2` へ複製(out は E3 だけ、約 55GB、logs/176)。複製後の空きは約 240GB の見込み。

## 調査 1: 何がどれだけ入っているか(logs/168、169、173、177)

`libcef.so`(E3c、strip 後 261.5MB)をマップファイルつきで再リンクし(`-Wl,-Map`、リンクは 2 分)、入力オブジェクトのパス別に集計した(`tools/fp/mapsize.py`)。名前空間別の集計(`tools/fp/nssize.py`、logs/168)は無名 32MB、`std` 17MB となり粗すぎて使えなかった。

出力セクション: `.text` 202.5MB、**`.rela.dyn` 25.8MB**、`.rodata` 19.4MB、`.data.rel.ro` 11.7MB。

| ディレクトリ | MB | 備考 |
|---|---|---|
| `third_party/blink` | 35.4 | 残す |
| リンカ内部(`.rela.dyn` など) | 33.8 | うち再配置テーブル 25.8 |
| `v8` | 28.6 | 残す |
| `chrome` | 28.4 | `chrome/browser/ui` 11.7、`extensions` 1.7、`web_applications` 1.5、`glic` 1.1 |
| `components` | 28.0 | `autofill` 3.5、`optimization_guide` 1.3、`safe_browsing` 1.2、`sync` 1.2、`policy` 1.1、`omnibox` 1.0、`password_manager` 0.9 |
| `content` | 10.6 | 残す |
| `third_party/pdfium` | 5.0 | PDF |
| `third_party/dawn` | 4.7 | `use_dawn=false` でも残っている(tint 2.8、dawn/native 1.8)。原因未調査 |
| `third_party/angle` | 4.7 | 残す(WebGL) |
| `extensions` | 4.1 | |
| `tflite` + `xnnpack` | 2.9 | |

機能名でパスを検索した合計(重複あり):

| 機能 | MB |
|---|---|
| 拡張機能(`extensions`) | 7.1 |
| Dawn / tint / SPIR-V | 5.8 |
| PDF(`pdf`、PDFium、ink) | 5.6 |
| autofill | 4.3 |
| WebUI | 4.1 |
| sync | 3.1 |
| web_app | 2.1 |
| password | 1.8 |
| tflite | 1.8 |
| Safe Browsing | 1.7 |
| optimization_guide | 1.4 |
| DevTools | 1.3 |
| glic | 1.2 |
| 印刷(`print`) | 1.0 |
| プラグイン | 0.2 |
| GuestView | 0.1 |

実行ファイル以外(E3b の配布物 311.5MB のうち約 50MB):

- `resources.pak` **25.6MB**。大半が WebUI のリソース(`dev_ui_resources` 5.5、`browser_resources` 5.1、コードキャッシュ 2.8、新しいタブ 0.9、設定 0.8 など)。
- `icudtl.dat` 10.8、`libvk_swiftshader.so` 5.8、`chrome_crashpad_handler` 2.2、`libVkICD_mock_icd.so` 0.65(テスト用で不要)。

### 分かったこと

1. ユーザーが挙げた 6 機能(PDF、印刷、印刷プレビュー、拡張機能、プラグイン、GuestView)は合計で **約 14MB**。拡張機能 7.1 と PDF 5.6 が大半で、プラグインと GuestView は 0.3MB しかない。
2. それより大きい「見落とし」が 2 つあった。
   - **再配置テーブル 25.8MB**。ChromeOS と Android は RELR 形式(`-Wl,--pack-dyn-relocs=relr`)で圧縮しているが、Linux では無効。glibc 2.36 以降が必要(このコンテナは 2.39)。リンクだけで試せる。
   - **`resources.pak` 25.6MB**。WebUI(`chrome://settings` など)を登録から外せば、コードと合わせて 20MB 規模で減る見込み。
3. `//chrome` + `//components` は合計 56MB だが、機能ごとに細かく散っている(0.1〜1MB が数百個)。一括登録箇所(「根」)を切ってリンカの GC に落とさせるのが効率的。

## 調査 2: 依存の形(logs/170〜172)

- CEF 本体(`cef/libcef`)の依存は薄い。`extensions/` の include は 6 個、`printing` 9 個、`components/pdf` 0 個、`chrome/browser/extensions` 0 個。`//cef/BUILD.gn` の `assert(enable_print_preview)` が止めているだけ。
- 重いのは `//chrome`。ただし buildflag のガードは整っている(Android 版 Chrome が PDF、プラグイン、拡張機能、印刷プレビューなしでビルドされるため)。ガードのあるファイル数: `ENABLE_EXTENSIONS_CORE` 1,228、`ENABLE_EXTENSIONS` 276、`ENABLE_PDF` 106、`ENABLE_PRINT_PREVIEW` 51、`ENABLE_PLUGINS` 43、`ENABLE_PRINTING` 38、`ENABLE_GUEST_VIEW` 30。
- ガードがないのは、デスクトップ専用のコード(`chrome/browser/ui/views` など)と、`if (!is_android)` で分岐している GN。ここが修正対象になる。
- 一括登録箇所: WebUI 154 個(`chrome_web_ui_configs.cc`)、KeyedService ファクトリ 453 個(`chrome_browser_main_extra_parts_profiles.cc`)、Mojo バインダ(`chrome_browser_interface_binders*.cc` 1,239 行)、拡張 API 関数(生成コード 1,705 行)。
- CEF のパッチは 119 個で 481 ファイルを触る。うち `chrome/browser/ui` が 87 ファイル。ここを大きく削ると CEF パッチとぶつかる。

## 起動時 RAM の計測方法(logs/174、175、178)

- `tools/fp/startram.py`。記事の方法に合わせ、回収できない RAM(`anon` + `shmem`)を cgroup v2 の `memory.stat` から読む。コンテナ内に専用 cgroup `/sys/fs/cgroup/fpmeas` を作った(既存プロセスを `/main` に移して memory コントローラを有効化)。
- あわせて全プロセスの `Pss_File`(回収できるファイル由来)、本体(`libcef.so` など)のマッピングの RSS / PSS(権限別)、プロセス一覧を記録する。
- 条件: ローカルページ `caps.html` を開いて 30 秒後。3 回の中央値。単位は MiB(記事と同じ)。
- 試行(E3b、1 回): 回収不可 411.6MiB(smaps の合算では 408.3 でほぼ一致)、`Pss_File` 203.4MiB、本体 RSS 656MiB / PSS 229.5MiB、9 プロセス。
- 注意: Rosetta 上の x64 なので、翻訳済みコードが匿名ページに載る分だけ実機より大きく出る可能性がある。構成間の比較用。

## 計画

構成名は F 系列とする(E3b の続き)。

| # | マイルストーン | 内容 | ツリー | 見込み |
|---|---|---|---|---|
| M6 | 調査と計画 | このファイル | | 完了 |
| M7 | F1: リンクとフラグ | RELR 再配置、tflite / BlueZ などの追加フラグ、Dawn が残る原因、不要な同梱ファイル | `/root/cef` | −25〜35MB |
| M8 | F2: 根切り | WebUI の登録と `resources.pak`、不要機能の KeyedService / バインダ登録を外す | `/root/cef` | −20〜30MB |
| M9 | F3: buildflag 無効化 | F3a: PDF、印刷プレビュー、印刷、プラグイン。F3b: 拡張機能、GuestView、プラットフォームアプリ | `/root/cef2` | −6〜14MB |
| M10 | F4: 統合と総まとめ | F1〜F3 を 1 本にまとめたクリーンビルド、サイズ、動作確認、PSS、起動時 RAM、一覧の更新 | | |

並列の方針:

- M7 と M8 は `out/E3` の増分ビルド(数ファイルのコンパイル + リンク 2 分)で回せる。`/root/cef` で自分が進める。
- M9 は buildflag を変えるので `//chrome` のほぼ全体が再コンパイルになる(1 回 1.5〜3 時間)。別ツリー `/root/cef2` に分け、修正ループをサブエージェントに任せる。
- 起動時 RAM の計測(既存 13 構成、logs/178)はビルドと並行して流す。ポート 9222 を使うので、動作確認とは同時に走らせない。
- フルビルドが 2 本同時に走らないようにする(CPU 25、ThinLTO のリンクはメモリを食う)。

各構成で必ずやること: `gn gen` → ビルド(`fpbuild.py`)→ `/root/fp/builds/Fn` に保存 → サイズ → 動作確認 7 項目 + スクリーンショット → 起動時 RAM → まとめに追記。

## リスク

- RELR は glibc 2.36 未満の環境では起動しない。組み込み Linux の libc 次第(musl は 1.2.4 以降で対応)。
- WebUI を外すと `chrome://` ページ(バージョン、GPU 情報など)が開けなくなる。CEF が内部で使う WebUI がないか確認が要る。
- 拡張機能の無効化は Alloy スタイルの内部(PDF ビューア、MIME ハンドラ)と絡む。F3b は途中で断念する可能性がある。その場合は切れた範囲と理由を残す。
- 削除パッチは最後にクリーンビルドで確認する(第 1 期の教訓)。
