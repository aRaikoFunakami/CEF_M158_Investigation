# M14b: これまでの動画デコードは S/W か H/W か

作成: 2026-11-13 09:55 JST(ユーザー指示)。ログ: logs/431、431b、432、433。結果: `a64/fp/results/{a64,x64}-*-mediaprobe.json`、スクリーンショット `a64/fp/results/shots/*-mediaprobe-*.png`。

## 結論

**これまでの計測は、x64 編・arm64 編のすべてで、動画デコードはソフトウェア(S/W)だった。** ハードウェア(H/W)デコードは一度も使われていない。

| 動画 | 使われたデコーダ | 種類 |
|---|---|---|
| YouTube(AV1 1080p60) | `Dav1dVideoDecoder`(dav1d) | S/W |
| テストページ mp4 / mse / eme(H.264) | `FFmpegVideoDecoder`(FFmpeg) | S/W |
| 音声(Opus / AAC) | `OpusAudioDecoder` / `FFmpegAudioDecoder` | S/W |

`kIsPlatformVideoDecoder` はすべて `false`(H/W なら `true` になる)。

## 調べ方

1. **実際に選ばれたデコーダ(logs/432、433)**: 新しく書いた `tools/fp/mediaprobe.py` で、CDP の Media ドメイン(`Media.enable`)を有効にして再生し、メディアプレーヤが報告するプロパティ(`kVideoDecoderName`、`kIsPlatformVideoDecoder`)と、デコーダ選択のログを集めた。`chrome://media-internals` と同じ情報だが、WebUI を削った構成でも取れる。
   - x64(ビルドコンテナ、Rosetta): E1(CEF 既定)と F4b(第 2 期の最終)
   - arm64(ネイティブのコンテナ、4 CPU): G0(CEF 既定)と G2(最終)
2. **ビルド設定(logs/431、431b)**: `gn args --list` で H/W デコード関連の引数を確認。
3. **実行環境**: `/dev` の中身と、VA-API のライブラリの有無。

## 詳細

### ビルド設定

| 構成 | `use_vaapi` | `use_v4l2_codec` | H/W デコードのコード |
|---|---|---|---|
| x64 E1、arm64 G0(CEF 既定) | **true**(既定値) | false | VA-API のデコーダが入っている |
| x64 E3a〜F4b、arm64 G1 / G2 | **false**(第 1 期の E3a で明示的に外した) | false | 入っていない |

- `use_vaapi` の既定値は `is_linux && (X11 または Wayland) && (x86 / x64 / arm64)` で true(`media/gpu/args.gni`)。Linux 版では `AcceleratedVideoDecoder` 機能も `USE_VAAPI` のとき既定で有効(`media/base/media_switches.cc:1508`)。
- `use_v4l2_codec`(ARM の SoC でよく使う Video4Linux2 のデコーダ)は Linux デスクトップでは既定で false。

### 実際のデコーダ選択(デコーダ選択ログより)

- **E1 / G0(VA-API あり)**: 最初に `VaapiVideoDecoder` を試し、`kUnsupportedConfig` で選べず、S/W の `Dav1dVideoDecoder` / `FFmpegVideoDecoder` に落ちている。ブラウザのログにも `vaapi_wrapper.cc: drmGetDevices2() has not found any devices` が出ている(過去の x64 の実行分にも同じ警告が残っていた)。
- **F4b / G2(VA-API なし)**: H/W の候補自体がなく、最初から S/W を選ぶ。

### 実行環境

- どちらのコンテナにも `/dev/dri`(GPU / 動画エンジンのデバイス)がない。Apple の仮想化(Virtualization.framework)上の Linux VM には、GPU も動画デコーダも渡されていない。arm64 の実行コンテナの `/dev` にあるのは virtio のディスク / コンソール / vsock などだけ。
- 描画も GPU を使わず、SwiftShader(CPU で動く Vulkan)を ANGLE 経由で使っている(G2-tv はソフトウェア合成)。

## これまでの結果への影響

- **RAM**: レンダラの `media`(約 140MiB、memory-infra)には、dav1d のデコード済みフレームと作業領域が含まれる。H/W デコードでは、デコード済みフレームはドライバ / GPU 側のメモリ(多くは別勘定の DMA バッファ)に置かれるので、レンダラの `media` は小さくなり、代わりに GPU プロセスやカーネル側のメモリが増える。**TV の実機の値は、今回の S/W の値とは配分が変わる**。
- **CPU**: AV1 1080p60 を dav1d で CPU デコードしているので、CPU 数の影響(2 CPU でコマ落ち 15%)は S/W デコードの負荷を含む。H/W デコードならこの依存はほぼ消える。
- **Cobalt のフラグ**: Cobalt の既定フラグの `--disable-accelerated-video-decode` は、今回の環境では元々 H/W を使っていないので効果がない(logs/424 の cobalt 条件)。
- **ROM**: E3a 以降で `use_vaapi=false` にしたことで VA-API のコードは外れている。TV の SoC は VA-API ではなく V4L2(stateful / stateless)や SoC ベンダー独自のデコーダを使うことが多く、実機向けには `use_v4l2_codec` か独自の `media::VideoDecoder` 実装を入れることになる。その分の ROM と RAM は今回の数値に含まれていない。
