# M12: arm64 クロスビルド(G1 = 第 2 期の削減を全部適用)

作成: 2026-11-13 04:45 JST、07:30 に G0 を追記。ログ: logs/400〜403、411〜413、417、428。

## ビルド

- `/root/cef/chromium/src` の F4b(第 2 期の最終ソース、パッチ全部)に、`out/G1/args.gn` = F4b の args + `target_cpu="arm64"`。
- amd64 のビルドコンテナ(Rosetta、24 CPU)でクロスコンパイル。arm64 用の sysroot(`debian_bullseye_arm64-sysroot`)を追加しただけで、ソースの修正は不要だった。
- 83,874 ステップ、失敗 0、停止検知 0、4 時間 58 分(G0 のビルドと並行、logs/402)。

## G0(削減前の基準、logs/400、401、403、428)

- `/root/cef2` を CEF のパッチだけが当たった状態に戻し(logs/400)、E1(x64 の基準)と同じ args + `target_cpu="arm64"` でビルド。97,046 ステップ、失敗 0、8 時間 3 分(G1 と並行、nice 10)。
- 動作確認 7/7、i18n OK(logs/428)。

| | x64 E1 | arm64 G0 | arm64 G1 | G0 → G1 |
|---|---|---|---|---|
| strip 後(`libcef.so` + `cefsimple`) | 299.6MB | **275.1MB** | **187.2MB** | −87.9(−32.0%) |
| 配布物(ja + en-US) | 377.5MB | **366.3MB** | 229.1MB | −137.2(−37.5%) |
| `resources.pak` | — | 22.1MB | 0.8MB | |
| `libVkLayer_khronos_validation.so`(Vulkan の検証レイヤ) | — | 26.3MB | なし | |
| `libvk_swiftshader.so` | — | 24.0MB | 22.8MB | |

起動時 RAM(caps.html、30 秒後、3 回の中央値、MiB): G0 回収不可 160.5 / ファイル由来 228.7 / 本体 RSS 619.6・PSS 239.3、8 プロセス → G1 は 128.7 / 159.2 / 441.8・173.6(回収不可 −31.8、ファイル由来 −69.5)。

## サイズ(logs/402)

| | x64 F4b | arm64 G1 | 差 |
|---|---|---|---|
| strip 後(`libcef.so` + `cefsimple`) | 191.2MB | **187.2MB** | −4.0 |
| うち `.text` | — | 175.6MB(size の text 列) | |
| 再配置 | `.relr.dyn` 0.2MB | `.relr.dyn` 0.17MB、`.rela.dyn` 5KB | RELR は arm64 でも有効 |
| `libvk_swiftshader.so`(未 strip) | 5.4MB | **22.8MB**(strip 後 15.9MB) | +17.4 |
| 配布物(ja + en-US、ICU は通常版) | 215.4MB | 229.1MB | +13.7(ほぼ SwiftShader) |

- 本体は arm64 のほうが 4MB 小さい。AArch64 は命令長が 4 バイト固定で 1 命令あたりは x86-64 より大きいはずだが、全体では小さくなった。理由(レジスタ数、x64 側だけにある SIMD の多重実装など)は調べていない。
- map の内訳(logs/402 末尾): `third_party` 64.3、`v8` 26.9、`components` 25.3、`chrome` 18.7、`content` 9.7MB。x64 と同じ傾向。

### SwiftShader が arm64 では 3 倍になる理由(logs/417)

`third_party/swiftshader/src/Reactor/reactor.gni:13`:

```
supports_subzero = current_cpu != "arm64" && current_cpu != "mips64el" && ...
```

SwiftShader はシェーダを実行時に機械語へ変換する(Reactor)。x64 では軽量な JIT の Subzero を使うが、Subzero は arm64 に対応していないので、arm64 では LLVM 10 のバックエンド(`third_party/swiftshader/third_party/llvm-10.0`、中間オブジェクト 106MB)を丸ごとリンクする。そのため strip 後で約 10MB 増える。

TV の実機には GPU があり、SwiftShader(ソフトウェア描画の Vulkan)は使わない。実験用に残しているだけなので、実機向けの配布物では `libvk_swiftshader.so` + `vk_swiftshader_icd.json` + `libvulkan.so.1` の約 16.8MB(strip 後)をそのまま外せる。x64 で外せるのは約 6MB なので、**arm64 では SwiftShader を外す効果が大きい**。

## 動作確認(arm64 ネイティブ、8 CPU、8GB、logs/412、413)

実行は Apple Silicon 上の arm64 ネイティブのコンテナ(`fp-a64-runtime:1`、Rosetta を通らない)。

- 7 項目すべて合格(caps、Service Worker、WebSocket、MP4、MSE、EME(Clear Key)、YouTube 1080p)。YouTube は AV1(`av01.0.09M.08`)1080p60 + Opus。
- i18n ページ: 日本語の単語分割を含め全項目 OK(ICU は通常版)。
- 削除機能の否定確認: PDF ビューアなし、プラグイン 0、`chrome.runtime` なし、`print()` と `<embed>` と PDF への遷移でも落ちない。
- Widevine は `emeWidevine: false`(x64 と同じ。CDM はコンポーネント更新で取る構成で、テスト環境ではダウンロードしていない)。
- スクリーンショット: `a64/fp/results/shots/G1-func-*.png`(M16 で `logs/screenshots/` に移す)。

## 起動時 RAM(logs/412、caps.html を開いて 30 秒後、3 回の中央値、MiB)

| | x64 F4b(Rosetta) | arm64 G1(ネイティブ) |
|---|---|---|
| 回収不可(anon + shmem、cgroup) | 364.0 | **128.7** |
| ファイル由来(`Pss_File`) | 151.5 | 159.2 |
| 本体 RSS / PSS | 435.6 / 173.2 | 441.8 / 173.6 |
| プロセス数 | 8 | 8 |

- ファイル由来と本体のマッピングは x64 とほぼ同じ。**回収不可だけが 235MiB 少ない**。第 1 期から注意書きしていた「Rosetta の翻訳済みコードが匿名ページに載る分」が実際にこの規模だったことになる。x64 編の回収不可の絶対値は実機より大きく出ており、構成間の差だけが意味を持つ。
- 注意: logs/412 の時点では、arm64 ネイティブでプロセス種別の判定が誤っていた(後述)。合計値には影響しない。

## 計測ツールの修正(logs/416、418、419)

1. **プロセス種別**: arm64 ネイティブでは子プロセスが `setproctitle` で `/proc/<pid>/cmdline` を空白区切りの 1 文字列に書き換える。NUL 区切りだけを見ていたため、全プロセスが `browser` になっていた。`measure.py`、`startram.py` を NUL と空白の両方で区切るように修正。Rosetta 上ではこの書き換えが見えていなかった。
2. **ytmem.py の起動引数**: `--args "--enable-low-end-device-mode"` は argparse がオプションとみなして失敗する。`--args=...` の形で渡す。
3. **YouTube の一時エラー**: 短時間に新しいプロファイルで何度も開くと「Something went wrong」で再生が始まらない(logs/418 で 6 回連続)。`measure.py func` と同じく同じブラウザで最大 4 回開き直し、再生開始を確認した時点を t=0 にした(logs/419 で 1 回目で成功)。

試運転(G1、8 CPU、8GB、低メモリ端末モード OFF、ビルドと並行、logs/419): 再生中 PSS 1180MiB(レンダラ 744、GPU 208、ブラウザ 166、ネットワーク 41)、回収不可 999MiB、先読み 40 秒、コマ落ち 40%(CPU の取り合いのため。本計測はビルド終了後)。
