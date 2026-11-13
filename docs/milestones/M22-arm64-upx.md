# M22: ROM 最小構成(arm64、SwiftShader なし)を UPX で圧縮したときの RAM

作成: 2026-11-13 23:50 JST(ユーザー指示「ROM を最も削減したバージョンに UPX を使って RAM 消費を確認せよ」。参考 https://qiita.com/rairaii/items/d5a5c3da56dbc7063a19)。
ログ: logs/464〜484。パッチ: `logs/patches/upx-noifunc.patch`(`tools/fp/upx_noifunc_patch.py`)。

## 結論

- `libcef.so` は、そのままでは UPX(4.2.2、5.0.2、5.3.0 のどれでも)で圧縮すると読み込み時に SIGSEGV で起動しない。原因は 2 つ: (1) lld の既定の `--rosegment`(読み取り専用データを実行コードと別のセグメントに置く)、(2) IFUNC(PartitionAlloc の MTE 用 3 つ)。RELR は関係ない。
- `-Wl,--no-rosegment` でリンクし直し、IFUNC を普通の関数に置き換えると、UPX 5.3.0 で圧縮して起動し、動作確認 7/7。libcef.so 186.2 → 86.0MB、配布物 196.0 → 95.3MB(−51.4%)。この 2 つの変更だけでは RAM は変わらない。
- 回収できない RAM は増える。起動直後: フラグなし 102.1 → 715.4MiB(+613)、3 フラグ 56.7 → 210.0MiB(+153)。H.264 1080p 再生中: フラグなし 598.3 → 1,366.2MiB(+768)、3 フラグ 537.7 → 679.0MiB(+141)。
- 展開したコードは memfd(shmem)に置かれ、カーネルは捨てられない。別々に起動されたプロセスはそれぞれ memfd を持ち、zygote の子は共有する。参考記事(実行ファイルの圧縮)と同じ仕組み。

## 切り分けの経過

| ログ | 内容 | 結果 |
|---|---|---|
| 464、464b | apt の UPX 4.2.2。strip 前を圧縮していたので strip 後でやり直し | 186.2 → 95.2MB |
| 465、466 | 起動 | libcef.so を圧縮すると SIGSEGV。cefsimple だけなら起動 |
| 467 | `--android-shlib` | SIGSEGV |
| 468 | UPX 5.0.2(GitHub、ユーザー許可) | 186.2 → 86.0MB、SIGSEGV |
| 469〜470c | RELR の有無、G0(RELR なし)、システムのライブラリ、実行ファイル | G0 の libcef.so / libEGL.so も SIGSEGV。実行ファイル(ls、python)は動く |
| 471 | x64 での確認 | ユーザーの指示で中止 |
| 472 | UPX 5.3.0(最新、ユーザー指示) | SIGSEGV |
| 473、473b | システムのライブラリ(GNU ld) | 圧縮しても dlopen でき、SQL も動く |
| 474、475 | libEGL.so を 4 通りリンクし直し | `--no-rosegment` で動く。RELR は無関係 |
| 476、477、479 | libcef.so を `--no-rosegment` でリンク(65 秒) | まだ SIGSEGV。gdb で IFUNC の選択関数の呼び出し中と判明 |
| 480 | IFUNC の調査 | PartitionAlloc の ResolveGetAccessFlags、ResolveRemaskPointer、ResolveTagMemoryRandomly |
| 481、481b | IFUNC を置き換え(tagging.cc、page_allocator_internals_posix.cc。各 125 秒) | IRELATIVE 0 |
| 482 | UPX 5.3.0 で圧縮 | 起動した |
| 483 | 動作確認と起動直後の RAM | 7/7。上の数値 |
| 484 | H.264 1080p 再生中の RAM(有効 2 回) | 上の数値。コマ落ち 0 |

## 注意

- 圧縮前の比較対象は、`--no-rosegment` と IFUNC 置き換えを入れた G2-tv-ni-strip(元の G2-tv と RAM はほぼ同じ: 起動直後 101.8 / 102.1MiB、再生中 PSS 759.3 / 757.7MiB)。
- PSS では UPX の影響が見えにくい(3 フラグで −12.5MiB)。cgroup の回収できない RAM には触っていないページも含めて memfd 全体が入る。
- メモリの上限をかけた再生の確認はしていない。
- obj/cef/libcef.ninja の ldflags を手で書き換えた(次の `gn gen` で元に戻る)。out/G1 の libcef.so は IFUNC 置き換え + `--no-rosegment` の状態になっている(G2 は a64/fp/builds/G2 と /root/fp/builds/G2 に保存済み)。PartitionAlloc の 2 ファイルの変更はツリーに残っている。
