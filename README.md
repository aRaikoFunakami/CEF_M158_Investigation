# CEF 158 のフットプリントと RAM の削減調査

CEF(Chromium Embedded Framework)8127 ブランチ / Chromium 158.0.8127.18 を、ローエンドの機器(TV など)に組み込むことを想定して、ROM(配布物のサイズ)と RAM の使用量をどこまで減らせるかを調べたときのパッチ、ビルド設定、計測スクリプト、計測結果です。

記事: (Qiita に公開後にリンクを追加)

## 結果

| 環境 | 構成 | strip 後の実行ファイル | 配布物(ja + en-US) |
|---|---|---|---|
| x64 | CEF 既定(E1) | 299.6MB | 377.5MB |
| x64 | 削減後(F4b-dist) | 191.2MB(−36.2%) | 206.6MB(−45.3%) |
| arm64 | CEF 既定(G0) | 275.1MB | 366.3MB |
| arm64 | 削減後(G2-dist) | 186.7MB(−32.1%) | 219.6MB(−40.0%) |
| arm64 | 削減後、SwiftShader なし(G2-tv) | 186.7MB(−32.1%) | 196.0MB(−46.5%) |

YouTube 再生中の RAM(arm64、全プロセスの PSS、S/W デコード):

| 動画 | CEF 既定(G0) | 削減後(G2-tv)+ `--single-process --no-zygote --enable-low-end-device-mode` |
|---|---|---|
| H.264 1080p60 | 1,045.5MiB | 684.4MiB(−35%) |
| AV1 4K60 | 1,509.5MiB | 1,005.5MiB(−33%) |

## 対象のソース

| 対象 | 版 |
|---|---|
| CEF | https://github.com/chromiumembedded/cef 8127 ブランチ、コミット `6ee3fb965001f3fab9fbce1f07b447f3254745ae` |
| Chromium | タグ `158.0.8127.18`(コミット `6449d9f9a6906edff724b7b220199b3fde4615c`) |

## ディレクトリ

```
patches/chromium/e3b-final-clean.patch  タグ 158.0.8127.18 からの差分。CEF 自身のパッチ(patcher.py が当てるもの)と第 1 期(E3b)の変更を含む
patches/chromium/f4b.patch              e3b-final-clean.patch を当てた状態からの差分。第 2 期の最終形(F4b)
patches/chromium/g2.patch               arm64 の G2 で足した 2 ファイル(enable_media_remoting=false を通すため)
patches/cef/f4b-cef.patch               CEF 6ee3fb965 からの差分(F4b)
patches/new-files/                      パッチに含まれない新規ファイル(chromium/ と cef/ の下に、置く場所のパスで配置)
patches/chromium/{e3b,f3a,f3b,f4a}.patch, patches/cef/{f3a,f3b,f4a}-cef.patch
                                        途中の段階のパッチ(参考)
patches/content_shell/                  比較に使った content_shell(Chromium 159.0.8143.0)の削減パッチ(参考)
args/                                   各構成の args.gn(E1〜F4b は x64、G0〜G2-tv は arm64)
scripts/build/fpbuild.py                停止検知つきのビルドラッパー(300 秒進まなければ止めて再実行)
scripts/measure/                        計測スクリプト(サイズ、起動直後の RAM、YouTube 再生中の RAM、動作確認)
scripts/patch/pakstrip.py               resources.pak を許可したリソースだけで作り直す
scripts/patch/g2_patch.py               g2.patch を当てるスクリプト
data/x64, data/arm64                    計測結果(JSON)。data/arm64/ytmem-summary.tsv は YouTube 計測の要約
docs/                                   調査の記録(docs/milestones/M0〜M21、ROM 削減の一覧、削除した機能の一覧、起動時 RAM)
docs/images/                            記事の図
```

## 構成

| 名前 | 内容 | args |
|---|---|---|
| E1 | CEF 既定のリリースビルド | `args/E1.args.gn` |
| E2 / E3a | GN 引数を追加 | `args/E2.args.gn`、`args/E3a.args.gn` |
| E3b | Blink のモジュール 41 個を削除 | `args/E3b.args.gn` |
| F1a〜F4b | RELR、WebUI の登録削除、Alloy スタイル専用、PDF・印刷・プラグイン・拡張機能の削除、`-Os` | `args/F1a.args.gn` 〜 `args/F4b.args.gn` |
| F4b-dist | F4b の配布物を整理し、ICU を軽量版に差し替え(ビルドは F4b と同じ) | `args/F4b.args.gn` |
| G0 | CEF 既定の arm64 | `args/G0.args.gn` |
| G1 / G2 | F4b の arm64 / G1 + Cobalt 由来の GN 引数 4 個 | `args/G1.args.gn`、`args/G2.args.gn` |
| G2-dist / G2-tv | G2 の配布物を整理 / さらに SwiftShader 一式を除去(ビルドは G2 と同じ) | `args/G2.args.gn` |

## 再現手順(F4b / G2)

確認済みなのは、3 つのパッチがタグと CEF のコミットに順に当たること(作業ツリーに触れない一時インデックスで `git apply --check`)までです。新しいツリーでこの手順を最初から通してビルドしたことはありません。

1. ソースを取得する。Chromium は全履歴を取らない。

```bash
git clone https://github.com/chromiumembedded/cef.git chromium/src/cef
git -C chromium/src/cef checkout 6ee3fb965001f3fab9fbce1f07b447f3254745ae
# chromium/src にタグ 158.0.8127.18 だけを取得し、.gclient を書いて依存を取得する
git -C chromium/src fetch --depth=1 https://chromium.googlesource.com/chromium/src.git refs/tags/158.0.8127.18
git -C chromium/src checkout FETCH_HEAD
gclient sync --no-history --nohooks -j 4
```

2. フック(CEF のパッチ適用を含む)を実行する前に、パッチと新規ファイルを当てる。CEF の `tools/patcher.py` は、すでに当たっているパッチを `git apply --reverse --check` で判定して飛ばす。

```bash
REPO=/path/to/CEF_M158_Investigation
cd chromium/src
git apply $REPO/patches/chromium/e3b-final-clean.patch
git apply $REPO/patches/chromium/f4b.patch
git -C cef apply $REPO/patches/cef/f4b-cef.patch
cp -R $REPO/patches/new-files/chromium/. .
cp -R $REPO/patches/new-files/cef/. cef/
gclient runhooks
# CEF のプロジェクト生成(この中で tools/patcher.py が動く)。Linux では use_sysroot=true が必要だった
(cd cef && GN_DEFINES="use_sysroot=true" GN_OUT_CONFIGS=Release_GN_x64 ./cef_create_projects.sh)
```

3. args.gn を置いてビルドする。

```bash
mkdir -p out/F4b && cp $REPO/args/F4b.args.gn out/F4b/args.gn
gn gen out/F4b
python3 $REPO/scripts/build/fpbuild.py . out/F4b cefsimple --log build.log
```

4. `resources.pak` を作り直し、配布物を整理する(`scripts/patch/pakstrip.py`、`docs/milestones/M10-F4-merged-summary.md`)。

arm64(G2)は、手順 2 のあとに `patches/chromium/g2.patch` を当て、`args/G2.args.gn` でビルドする。arm64 の sysroot は `build/linux/sysroot_scripts/install-sysroot.py --arch=arm64` で入れる。

## UPX で圧縮する場合(arm64、G2-tv)

`libcef.so` は、そのままでは UPX で圧縮すると読み込み時に落ちる。次の 2 つを入れてから圧縮する(`docs/milestones/M22-arm64-upx.md`)。

1. `patches/chromium/upx-noifunc.patch`(または `scripts/patch/upx_noifunc_patch.py`)で、PartitionAlloc の IFUNC を普通の関数に置き換える
2. `libcef.so` のリンクに `-Wl,--no-rosegment` を足す(調査では out/G1/obj/cef/libcef.ninja の ldflags を手で書き換えた)

その後 `strip` してから `upx libcef.so cefsimple`(UPX 5.3.0、既定のオプション)。配布物 196.0MB → 95.3MB。回収できない RAM は増える(H.264 1080p 再生中、起動フラグなし 598.3 → 1,366.2MiB、3 フラグ 537.7 → 679.0MiB)。

## 計測の前提

- 計測はコンテナ(Apple の `container`)上で、GPU デバイスなし、Xvfb、SwiftShader で行った。動画のデコードは CPU(dav1d / FFmpeg)。
- x64 の計測は Rosetta 上で、回収できない RAM が arm64 より約 235MiB 大きく出る。RAM の絶対値は arm64 の値を使う。
- 計測スクリプトはコンテナ内の `/root/fp` に置いて使う前提のパスになっている。

## ライセンス

パッチは Chromium と CEF のソースへの変更で、それぞれのライセンス(BSD)に従う。
