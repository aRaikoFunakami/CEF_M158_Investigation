# M17: 使えるメモリを制限したときに YouTube を再生できるか(arm64)

作成: 2026-11-13 14:10 JST(2026-11-13 07:50 のユーザー指示。13:00 に「--single-process --no-zygote --enable-low-end-device-mode を全部付けて試す」に方針変更)。
ログ: logs/430、435、436、437、439〜442(追記分)。結果 JSON: `a64/fp/results/limit*-ytmem.json`。

## 方法

- 制限: ブラウザの全プロセスが入る計測用 cgroup の `memory.max` を設定(`memory.swap.max=0`)。コンテナ自体は 8 CPU / 8G(OS、Xvfb、計測スクリプトは制限の外)。`tools/fp/ytmem.py --limit`。
- 動画: YouTube aqz-KE-bpKQ(AV1 1080p60、S/W デコード)、warm プロファイル、再生 120 秒。
- 判定: 120 秒の間に再生が進み続けたら「再生できた」。cgroup の `memory.events` で OOM kill の回数を記録。
- 注意: `memory.max` が効くのは anon + shmem と、計測中に新しく読み込むファイルのページ。`libcef.so` などのページキャッシュは warm プロファイル作成時に cgroup の外で読み込まれ、外側に課金される。そのため PSS が上限を超えて見えることがある。上限と比べるべき値は「回収不可(anon + shmem)」。
- Chromium は cgroup の上限を知らない(物理メモリは 8G と認識)。上限に近づいても自分からはメモリを手放さず、カーネルがページキャッシュを追い出し、それでも足りなければ OOM killer がプロセスを落とす。

## 結果

### A. 起動引数なし / 低メモリ端末モードのみ(logs/430)

| 上限 | G0(ROM 削減なし) | G2-tv(ROM 最小、SwiftShader なし) | G2-dist(ROM 削減、SwiftShader あり) |
|---|---|---|---|
| 1GB | OFF・ON とも再生できた(回収不可 785 / 761MiB) | OFF・ON とも再生できた(回収不可 594 / 591MiB) | OFF で再生できた(回収不可 734MiB) |
| 600MB | OFF: **3 回とも OOM kill で落ちる**(再生前に落ちる) | 未計測(※) | 未計測(※) |

※ 300MB の前で止める切り替えスクリプトが、ログ冒頭の「実行予定一覧」の行に反応して、600MB の G0・ON の途中で logs/430 を止めてしまった(スクリプトの誤り)。方針変更後の B で 600MB 以下は確認している。

### B. `--single-process --no-zygote --enable-low-end-device-mode`(logs/435、437)

| 上限 | G0(ROM 削減なし) | G2-dist(ROM 削減後) |
|---|---|---|
| 300MB | OOM kill で落ちる(1 回) | — |
| 450MB | OOM kill で落ちる(2 / 2) | OOM kill で落ちる(2 / 2) |
| 600MB | OOM kill で落ちる(2 / 2) | OOM kill で落ちる(2 / 2) |
| 700MB | OOM kill で落ちる(2 / 2) | **再生できた(1 / 2)**: PSS 846.8、回収不可 667.7MiB |
| 800MB | **再生できた(1 / 2)**: PSS 943.3、回収不可 692.2MiB | **再生できた(1 / 2)**: PSS 815.0、回収不可 634.8MiB |

- 再生できた回でも、もう 1 回は再生途中に OOM kill で落ちている。700〜800MB は「ぎりぎり」の領域。
- **ROM 削減後(G2-dist)は、削減前(G0)より約 100MB 少ない上限で再生できる**(G0 は 800MB、G2-dist は 700MB で再生)。
- G2-tv(SwiftShader なし)は、`--single-process` を付けると起動できなかった(logs/436)。→ 原因と回避策は下の「追記」を参照。制限なし時の値(A の 1GB で回収不可 591MiB)からは、G2-tv が最も少ないメモリで再生できる可能性が高い(回避策つきでの上限別の計測は未実施)。

### 追記(2026-11-13 15:00): G2-tv + `--single-process` が起動しない原因と回避策(logs/439〜442)

- **原因は計測ツールの起動引数**。`measure.py` はどのビルドにも `--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader` を付けていた。G2-tv には SwiftShader(`libvk_swiftshader.so`)がないので、GL の初期化は必ず失敗する。
  - 通常(マルチプロセス)では、GPU プロセスが初期化失敗で終了 → ブラウザが次の GPU モード(`DISPLAY_COMPOSITOR` = ソフトウェア合成、`--use-gl=disabled`)で GPU プロセスを作り直す。G2-tv がこれまで動いていたのはこのフォールバックのおかげ。
  - `--single-process` では GPU はプロセスではなくスレッド(`Chrome_InProcGpuThread`)で、作り直せない(`GpuProcessHost::ValidateHost` は single-process なら常に有効扱い)。GPU モードは起動時に一度だけ決まり(`GpuDataManagerImplPrivate` のコンストラクタで `AppendGpuCommandLine`)、SwiftShader の指定があると `SOFTWARE_GL` になる。`GpuInit::InitializeInProcess` は GL の初期化に失敗しても `init_successful_ = true` のまま戻るので、失敗がブラウザに伝わらない。その後 `SharedImageStub::Initialize` → `GpuChannelManager::GetSharedContextState` → `gl::init::CreateGLContext` が未初期化の GL 実装で呼ばれ、**SIGTRAP でブラウザごと落ちる**(logs/441 の gdb のスタック)。
  - logs/436 の「ブラウザは起動するがページが作られない」は誤りで、実際は DevTools の待ち受けを出した直後にプロセスが落ちていた(logs/439: 失敗した条件はすべてプロセス数 0、終了コード 133)。
  - `--disable-gpu` や `--disable-software-rasterizer` を足すだけでは直らない(SwiftShader の指定が残っているとハードウェアのモードが飛ばされ `SOFTWARE_GL` が選ばれる。logs/439 の V1、V4)。
- **回避策: SwiftShader を指定する 3 引数を付けない**(+ `--disable-gpu` で最初からソフトウェア合成に固定)。logs/439 の V2、V3、V5、V6 はすべて起動し、機能確認ページが PASS(WebGL はなし、43 スレッド)。gdb の下で YouTube を開いて 150 秒間落ちないことも確認(logs/442)。ytmem でも再生を確認(logs/440、4 CPU / 8G、制限なし、有効 1 / 3 回。残り 2 回は YouTube 側の "Something went wrong"): **再生中 PSS 665.2MiB、回収不可 509.2MiB、cgroup のピーク 803.2MiB、コマ落ち 0%、1 プロセス**。並行して gdb の導入などを動かしていたので参考値。同じ 3 フラグの G2-dist(800MB 上限で PSS 815.0、回収不可 634.8MiB)より回収不可で約 125MiB 少ない。ビルドの作り直しは不要。
- `tools/fp/measure.py` を修正: `--single-process` 付きで、ビルドのディレクトリに `libvk_swiftshader.so` がなければ、3 引数を外して `--disable-gpu` を付ける。マルチプロセスの起動引数は変えていない(これまでの計測値と条件が変わらない)。
- 製品で G2-tv 相当(SwiftShader なし)を single-process で使う場合も同じで、`--use-angle=swiftshader` を付けない / `--disable-gpu` を付けることが条件になる。

## 分かったこと

1. **300MB / 600MB では、どの構成も YouTube(1080p、S/W デコード)を再生できない**。起動して YouTube を開いた時点で上限を超え、OOM kill で落ちる。
2. **再生に必要なのは約 700〜800MB**(3 フラグあり)。ROM 削減後は削減前より約 100MB 少なくて済む。
3. **Chromium は cgroup の上限に合わせない**。上限の手前でメモリを減らす振る舞いはなく、超えれば落ちる。上限の小さい環境で使うには、Chromium に実際のメモリ量を見せる(物理メモリ自体が少ない、あるいはそれを伝える)か、Cobalt のようなメモリ予算の仕組みが要る。
4. 今回は S/W デコードで、レンダラが dav1d のフレーム(約 140MiB)を持っている。H/W デコードの実機ではこの分がドライバ側に移るので、ブラウザの cgroup に必要な量はもっと小さくなるはず。解像度を下げる(720p 以下)ことでも減らせる。いずれも未計測。
