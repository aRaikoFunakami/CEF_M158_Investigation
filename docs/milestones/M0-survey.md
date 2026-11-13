# M0: 調査と計画(2026-11-11 完了)

## 分かったこと

| 対象 | Chromium |
|---|---|
| Chromium 編のツリー | 159.0.8143.0 |
| CEF master | 158.0.8127.0 |
| CEF 8127(Beta、2026-11-10〜) | 158.0.8127.18 |
| CEF 8078(Stable) | 156.0.8078.88 |

- CEF は 159 に未対応。**CEF 8127 ブランチ + Chromium 158.0.8127.18** で進める。
- Chromium 編とメジャーが 1 つずれるので、CEF 編の中で基準(E1)を取り直し、可能なら 158 の `content_shell`(E0)も測る。

## 決めたこと

- ツリーは `/root/cef`(第 3 のツリー)。Chromium 編の 2 ツリーには触れない。
- 構成: E0(158 `content_shell`)、E1(CEF 既定)、E2(+ GN フラグ)、E3(+ パッチ)。
- テストアプリは `cefsimple --use-alloy-style`。
- マイルストーン M1〜M5 は `footprint-plan-cef.md` の 7 章。

## 計画への反映

- 計画書を新規作成(`footprint-plan-cef.md`)。
- 最大の論点は「Chrome ランタイムのみ = `//chrome` 層が必ず入る」こと。Chromium 編で最大だった `chrome` → `content_shell` の 98MB は CEF では取れない前提で E2 / E3 を組む。

ログ: `logs/119-cef-survey.{sh,log}`
