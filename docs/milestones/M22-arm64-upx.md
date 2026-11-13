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

## 追補(2026-11-14 07:10〜07:40 JST、logs/510〜513)

ユーザーの質問(フラグで増え方が違う理由、参考記事との差、ROM の比較、使うべきか、GPU を使う場合の対策)に答えるための追加計測とソース調査。

- logs/510: memfd:upx の inode をプロセスごとに数えた。起動フラグなしは 8 プロセス中、execve で起動した 4 つ(ブラウザ、zygote 2 つ、ネットワークサービス)がそれぞれ自分の展開コピーを持ち、GPU・レンダラ 2・ストレージは zygote から fork されて共有。cgroup の shmem は +613.4MiB(4 個)、3 フラグは +153.3MiB(1 個)。1 コピー約 153MiB。anon は 3 フラグで 37.0 → 35.9MiB(増えない)。
- 参考記事(Chromium 156、arm64、1 タブ)は +1,124MiB / +283MiB。execve の数は同じ 4 で、1 コピーが約 282MiB(コード memfd 約 238 + 読み取り専用データの匿名メモリ約 45)。今回の 1 コピーが小さいのは、コードのセグメントが 166.7MiB と小さいことと、`--no-rosegment` で読み取り専用データも memfd に入り匿名メモリに二重に載らないこと。
- logs/511: `readelf` での事前確認。元の削減版は LOAD が R / R E / RW / RW、IRELATIVE 3。UPX 用に直したものは R E / RW / RW、IRELATIVE 0。RELR はどちらもあり。
- logs/512: `--in-process-gpu --no-unsandboxed-zygote --enable-features=NetworkServiceInProcess2 --disable-gpu` で execve 2、5 プロセス、動作確認 7/7。回収できない RAM 76.0 → 382.9MiB(+307、コピー 2 個)。UPX なしでも 102.1 → 76.0MiB に減る。
- logs/513: 同じ配布物(ja、en-US の性別違いを含むロケール、合計 194.6MB)を squashfs に入れたサイズ: xz 1MiB ブロック 60.7MB、zstd 19 1MiB 69.5MB、gzip 128KiB 85.6MB、lz4hc 1MiB 94.0MB。RAM と起動時間は未計測。
- GPU のソース調査(Chromium 158.0.8127.18): プロセス内の GPU は `GpuInit::InitializeInProcess()`(gpu_init.cc:1086)で初期化し、GL の初期化に失敗しても戻るだけで、ブラウザ側の描画方式の切り替え(gpu_data_manager_impl_private.cc:1635)は GPU プロセスの起動し直しなのでできない。ブロックリストに当たると SwiftShader に切り替える(gpu_util.cc:973)が、`--use-gl` の明示か `--disable-software-rasterizer` で止まる。X11 は ANGLE のみ、Wayland は ANGLE の GL / GLES / SwiftShader / Vulkan、DRM は ANGLE と SwiftShader。ANGLE は libcef.so に静的リンク(use_static_angle=true)。GPU プロセスはサンドボックスなしの zygote から fork(gpu_process_host.cc:466)。
- 記事: UPX の章を「圧縮する手順(readelf で確認する 2 点)」「起動しないときの切り分け」「フラグで増え方が 4 倍違う理由(図 11)」「参考記事より増え方が小さい理由(図 12)」「execve を減らす(図 14)」「使うべきか(所見と根拠)」に書き直し、ROM の内訳(図 13)を追加。「実機で GPU を使う場合」を RAM の章に追加。図は tools/figs_upx2.py で生成。

### 所見の見直し(2026-11-14 08:05 JST、ユーザー指摘)

- 指摘: 「UPX が候補に残るのは」は一方的。ROM と RAM のどちらを優先するかで使い分ける所見のほうがよい。実行コードのページを RAM から削らないといけないほど厳しい状態は、いつ OOM が起きてもおかしくないので、余裕を見る必要がある。
- 既存の値から、ファイル由来の RAM も含めた増加を計算: 3 フラグ 起動直後 196.4 → 235.6(+39)、再生中 702.9 → 710.9(+8)。2 execve 起動直後 216.7 → 409.4(+193)。フラグなし 起動直後 243.5 → 742.5(+499)、再生中 765.6 → 1,398.7(+633)。
- 記事の「UPX を使うべきか」を、2 通りの見方の表、RAM の余裕の考え方(上限の試験: 回収不可 + 約 100MB で強制終了の条件あり、+約 200MB で全条件再生)、機器の条件ごとの使い分けの表に書き直した。

### CEF 既定との比較を追加(2026-11-14 08:00 JST、logs/514、ユーザー指摘「UPX の章に ROM 削減前の素の CEF との比較がない」)

- logs/514: G0 の起動直後(3 回の中央値)。なし 158.9MiB(PSS 387.2、既存の logs/428 は 160.5 / 387.6)、2 execve(--disable-gpu)88.0MiB(PSS 289.1、5 プロセス、動作確認 7/7)、3 フラグ(--disable-gpu)65.7MiB(PSS 266.1、ファイル由来 208.2)。
- 再生中(H.264 1080p)の G0 は M18 の値(なし: PSS 1,045.5、回収不可 790.0、ファイル 255.8 / 3 フラグ: 912.2、661.9、251.4。G0 は SwiftShader で描画)。
- 削減版 + UPX + 3 フラグを CEF 既定 + 3 フラグと比べると、再生中の回収不可 661.9 → 679.0(+17)、ファイル込み 913.3 → 710.9(−202)、ROM 366.3 → 95.3MB(26%)。起動直後は 65.7 → 210.0(+144)。
- 記事: UPX 章の ROM、起動直後、再生中、execve の表と、結果の要約に CEF 既定を追加。「CEF 既定と比べると」の小節を追加。図 10(再生中)と図 14(execve)に CEF 既定を追加。
