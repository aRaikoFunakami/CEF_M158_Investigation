# M1: ソース取得(2026-11-11 10:32 完了)

## 結果

| 項目 | 値 |
|---|---|
| ツリー | `/root/cef/chromium/src`(CEF は `src/cef`) |
| Chromium | 158.0.8127.18(タグを `--depth=1` で取得) |
| CEF | 8127 ブランチ `6ee3fb965`(Update to Chromium version 158.0.8127.18) |
| CEF が Chromium に当てるパッチ | 474 ファイル、+4835 / −790 行 |
| ツリーのサイズ | 46GB(ビルド出力を除く) |
| `gn gen` | `out/Release_GN_x64`、37,102 ターゲット |

## 所要時間と失敗

| 手順 | 所要 | 結果 |
|---|---|---|
| logs/120: 既存ツリーを複製 → `automate-git.py` | 1 時間 54 分で打ち切り | **失敗**。浅いツリーに対して全履歴(約 2,550 万オブジェクト)を fetch。48GB 受信して破棄 |
| logs/123: タグだけ `--depth=1` で fetch、checkout | 1 分半 | 成功(175MB) |
| logs/123: `gclient sync --no-history --nohooks` | 11 分 | **失敗**。`quiche.googlesource.com` が HTTP 429 |
| logs/124: 同 `-j 4` で再試行 | 14 分 | 成功 |
| logs/124: `gclient runhooks`(PGO プロファイル取得を含む) | 1 分 | 成功 |
| logs/124: `cef_create_projects.sh` | 30 秒 | **失敗**。`use_sysroot=false`(CEF の Linux 既定)でシステムの `libpipewire-0.3` を要求 |
| logs/125: `use_sysroot=true` を追加して再実行 | 30 秒 | 成功 |

## 分かったこと(記事向け)

- `automate-git.py` を浅いチェックアウトに対してそのまま流すと全履歴を取りにいく。`--no-chromium-history` があるが、既存ツリーのバージョンが違うと削除して取り直す。
  今回は「タグの浅い fetch → `gclient sync --no-history` → runhooks → `cef_create_projects.sh`」に分解して解決した。
- CEF が既定で入れる GN 引数(`tools/gn_args.py`)のうち、フットプリントに関係しそうなもの:
  - `enable_backup_ref_ptr_support=false`、`use_partition_alloc_as_malloc=false`(Chromium 編では D で初めて BRP を切った。CEF は最初から切っている。メモリ比較で注意)
  - `enable_background_mode=false`(Chromium 編の `chrome` では `gn gen` で落ちたフラグ)
  - `blink_heap_inside_shared_library=true`、`disable_fieldtrial_testing_config=true`
- 必須(assert で強制): `enable_widevine=true`、`optimize_webui=true`、`clang_use_chrome_plugins=false`、`enable_linux_installer=false`。
- リリース設定は Chromium 編と同じに揃った: `is_cfi=true`、`chrome_pgo_phase=2`、`use_thin_lto=true`(`gn args --list` で確認)。

## 計画への反映

- E1 の引数を確定: CEF 既定 + Chromium 編 A と同じリリース設定 + `use_sysroot=true`。
- E0(158 の `content_shell`)は E1 のビルド出力ディレクトリとは別になり 2 時間級。E1〜E3 を優先し、時間が余れば実施する。
- メモリ比較の注意点を追加: CEF は BRP と PartitionAlloc-as-malloc を既定で切っている。

ログ: `logs/120`、`logs/122`〜`logs/125`
