# figs_upx2.py <出力ディレクトリ>: 記事の UPX 節の図 11〜14 を SVG で書き出す(M22 追補、logs/510〜512)。
import sys, os
OUT = sys.argv[1]
FONT = 'Hiragino Sans, Hiragino Kaku Gothic ProN, sans-serif'
RED, YEL, BLUE, GRN, GRY, DARK, SUB = '#d93025', '#fbbc04', '#1a73e8', '#34a853', '#9aa0a6', '#202124', '#5f6368'

def svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">'
            f'<rect width="{w}" height="{h}" fill="#fff"/>' + ''.join(body) + '</svg>')

def t(x, y, s, size=14, anchor='start', fill=DARK, bold=False):
    b = ' font-weight="bold"' if bold else ''
    return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" fill="{fill}"{b}>{s}</text>'

def r(x, y, w, h, fill, stroke='none', rx=0, sw=1, dash=''):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>'

def line(x1, y1, x2, y2, col=SUB, sw=1.5):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="{sw}"/>'

def save(name, s):
    open(os.path.join(OUT, name), 'w').write(s); print(name)

# ---- 図 11: プロセスと展開コピー(起動フラグなし / 3 フラグ)
def proc(x, y, w, label, sub, copy):
    fill = '#fce8e6' if copy else '#f1f3f4'; st = RED if copy else GRY
    o = [r(x, y, w, 46, fill, st, 6, 2 if copy else 1), t(x + w / 2, y + 20, label, 14, 'middle', bold=bool(copy)), t(x + w / 2, y + 38, sub, 11.5, 'middle', SUB)]
    if copy:
        o += [r(x + w - 70, y - 13, 82, 22, RED, rx=11), t(x + w - 29, y + 3, copy, 12, 'middle', '#fff', True)]
    return o

b = [t(30, 36, 'UPX 版で libcef.so の展開コピーがいくつ作られるか(起動直後、arm64、削減版)', 19, bold=True)]
b += [t(30, 62, '赤枠 = 自分で起動し直す(execve)ので、自分専用の展開コピー(約 153MiB、カーネルが捨てられない)を作るプロセス。灰色 = fork で作られ、親のコピーを共有する', 12.5, fill=SUB)]
# 左: フラグなし
b += [t(265, 98, '起動フラグなし: 8 プロセス、コピー 4 個 → +613MiB', 16, 'middle', bold=True)]
b += proc(175, 116, 180, 'ブラウザ', 'execve(cefsimple)', 'コピー 1')
ys = 206
for i, (lab, sub, cp) in enumerate([('zygote 1', 'サンドボックスなし・execve', 'コピー 2'), ('zygote 2', 'サンドボックスあり・execve', 'コピー 3'), ('ネットワーク', 'サービス・execve', 'コピー 4')]):
    x = 20 + i * 170
    b += [line(265, 162, x + 80, ys)]
    b += proc(x, ys, 160, lab, sub, cp)
b += [line(100, 252, 100, 300)] + proc(20, 300, 160, 'GPU', 'fork(コピー 2 を共有)', None)
b += [line(205, 252, 205, 300 + 2 * 58 + 23)]
for j, lab in enumerate(['レンダラ', 'レンダラ', 'ストレージ']):
    y = 300 + j * 58
    b += [line(205, y + 23, 220, y + 23)] + proc(220, y, 160, lab, 'fork(コピー 3 を共有)', None)
# 右: 3 フラグ
X = 560
b += [line(530, 90, 530, 480, '#dadce0', 1)]
b += [t(X + 200, 98, '3 フラグ: 1 プロセス、コピー 1 個 → +153MiB', 16, 'middle', bold=True)]
b += [r(X + 40, 116, 330, 200, '#fce8e6', RED, 8, 2), r(X + 300, 103, 82, 22, RED, rx=11), t(X + 341, 119, 'コピー 1', 12, 'middle', '#fff', True)]
b += [t(X + 205, 142, 'ブラウザ(execve)', 15, 'middle', bold=True)]
for k, lab in enumerate(['ブラウザの処理', 'レンダラ(スレッド)', 'GPU(スレッド)', 'ネットワーク・ストレージ(スレッド)']):
    b += [r(X + 70, 158 + k * 37, 270, 30, '#fff', GRY, 5), t(X + 205, 178 + k * 37, lab, 13, 'middle')]
b += [t(X + 205, 345, '--single-process: 全部を 1 プロセスのスレッドにする', 12.5, 'middle', SUB),
      t(X + 205, 365, '--no-zygote: zygote を起動しない', 12.5, 'middle', SUB)]
b += [t(30, 490, 'logs/510: /proc/&lt;pid&gt;/maps の memfd:upx の inode を数えた。cgroup の shmem は、フラグなしで +613.4MiB(4 個)、3 フラグで +153.3MiB(1 個)増えた。', 12, fill=SUB)]
save('fig11-upx-copies.svg', svg(1000, 505, b))

# ---- 図 12: 参考記事との比較(コピーの大きさ × 個数)
b = [t(30, 36, 'UPX で増える回収できない RAM: 参考記事の Chromium と今回の CEF(arm64、単位 MiB)', 19, bold=True)]
rows = [('起動フラグなし(コピー 4 個)', 1124, 613), ('--single-process --no-zygote(コピー 1 個)', 283, 153)]
sc = 0.5; X0 = 360
b += [r(360, 52, 14, 14, GRY), t(380, 64, '参考記事: Chromium 156(実行ファイル 294MiB)', 13, fill=SUB),
      r(690, 52, 14, 14, RED), t(710, 64, '今回: 削減版 CEF(libcef.so 186.2MB)', 13, fill=SUB)]
for i, (lab, ref, me) in enumerate(rows):
    y = 100 + i * 110
    b += [t(X0 - 12, y + 34, lab, 14, 'end', bold=True)]
    b += [r(X0, y, ref * sc, 28, GRY), t(X0 + ref * sc + 8, y + 19, f'+{ref:,}', 13)]
    b += [r(X0, y + 34, me * sc, 28, RED), t(X0 + me * sc + 8, y + 53, f'+{me:,}', 13, bold=True)]
b += [t(30, 330, '1 コピーあたり: 参考記事 約 282MiB(コード 約 238MiB + 読み取り専用データの複製 約 45MiB)、今回 約 153MiB(コードと読み取り専用データ)。', 13),
      t(30, 352, '別起動のプロセスの数(4 個)はどちらも同じ。差はコピー 1 個の大きさで決まっている。', 13),
      t(30, 380, '参考記事の値は https://qiita.com/rairaii/items/d5a5c3da56dbc7063a19(arm64、1 タブ、cgroup の anon + shmem の増加)。今回は logs/483、510。', 11.5, fill=SUB)]
save('fig12-upx-vs-reference.svg', svg(1000, 395, b))

# ---- 図 13: ROM(配布物の内訳)
b = [t(30, 36, '配布物のサイズ(arm64、ロケールは ja と en-US、単位 MB)', 19, bold=True)]
b += [r(330, 52, 14, 14, BLUE), t(350, 64, 'libcef.so', 13, fill=SUB), r(450, 52, 14, 14, GRN), t(470, 64, 'cefsimple', 13, fill=SUB),
      r(570, 52, 14, 14, GRY), t(590, 64, 'そのほか(.pak、ICU、V8 の起動データ、ANGLE、ロケール)', 13, fill=SUB)]
data = [('CEF 既定', 275.1, 0, 91.2, '366.3'), ('削減版、SwiftShader なし', 186.2, 0.6, 9.2, '196.0'), ('削減版、SwiftShader なし + UPX', 86.0, 0.1, 9.2, '95.3(−51.4%)')]
sc = 1.75; X0 = 290
for i, (lab, a, c, o, tot) in enumerate(data):
    y = 95 + i * 62
    b += [t(X0 - 12, y + 22, lab, 14.5, 'end', bold=(i == 2))]
    b += [r(X0, y, a * sc, 34, BLUE), (r(X0 + a * sc, y, max(c * sc, 1.5), 34, GRN) if c else ''), r(X0 + (a + c) * sc, y, o * sc, 34, GRY)]
    b += [t(X0 + a * sc / 2, y + 22, f'{a}', 13, 'middle', '#fff', True), t(X0 + (a + c + o) * sc + 10, y + 22, tot, 14, bold=True)]
b += [t(30, 300, 'UPX が縮めるのは libcef.so(186.2 → 86.0MB)と cefsimple(0.6 → 0.1MB)だけ。そのほか 9.2MB は変わらない。', 13),
      t(30, 322, 'CEF 既定の青は libcef.so と cefsimple の合計(275.1MB)。UPX 版の配布物は CEF 既定の 26% になる。', 13)]
save('fig13-upx-rom.svg', svg(1000, 340, b))

# ---- 図 14: execve するプロセスの数と回収できない RAM(起動直後)。CEF 既定も並べる
b = [t(30, 36, 'execve するプロセスの数と、起動直後の回収できない RAM(arm64、単位 MiB)', 19, bold=True)]
b += [r(250, 52, 14, 14, BLUE), t(270, 64, 'CEF 既定', 13, fill=SUB), r(380, 52, 14, 14, GRY), t(400, 64, '削減版(圧縮前)', 13, fill=SUB), r(560, 52, 14, 14, RED), t(580, 64, '削減版 + UPX', 13, fill=SUB)]
rows = [('起動フラグなし', 'execve 4、8 プロセス', 160.5, 102.1, 715.4, 'サンドボックスあり / GPU は別プロセス(失敗時に切り替えられる)'),
        ('execve を 2 にするフラグ', 'execve 2、5 プロセス', 88.0, 76.0, 382.9, 'サンドボックスあり / GPU はブラウザ内(切り替えなし)'),
        ('3 フラグ', 'execve 1、1 プロセス', 65.7, 56.7, 210.0, 'サンドボックスなし / GPU はブラウザ内(切り替えなし)')]
sc = 0.85; X0 = 270
for i, (lab, sub, g, a, u, note) in enumerate(rows):
    y = 92 + i * 135
    b += [t(X0 - 12, y + 34, lab, 15, 'end', bold=True), t(X0 - 12, y + 54, sub, 12, 'end', SUB)]
    b += [r(X0, y, g * sc, 22, BLUE), t(X0 + g * sc + 8, y + 16, f'{g}', 12.5)]
    b += [r(X0, y + 26, a * sc, 22, GRY), t(X0 + a * sc + 8, y + 42, f'{a}', 12.5)]
    b += [r(X0, y + 52, u * sc, 22, RED), t(X0 + u * sc + 8, y + 68, f'{u}(圧縮前から +{u - a:.0f})', 12.5, bold=True)]
    b += [t(X0, y + 96, note, 12, fill=SUB)]
b += [t(30, 500, 'execve を 2 にするフラグ: --in-process-gpu --no-unsandboxed-zygote --enable-features=NetworkServiceInProcess2。', 11.5, fill=SUB),
      t(30, 520, 'GPU デバイスがないので 2 つ目と 3 つ目は --disable-gpu 付き。3 回の中央値。logs/428、483、512、514。CEF 既定は UPX で圧縮していない。', 11.5, fill=SUB)]
save('fig14-upx-execve.svg', svg(1000, 535, b))

# ---- 図 6 / 図 10 共通: PSS(A + B の積み上げ)と、回収できない RAM(cgroup)を別の棒で並べる
DRK = '#a50e0e'
def ab_fig(name, title, groups, sc, foot):
    b = [t(30, 38, title, 20, bold=True)]
    b += [r(160, 56, 14, 14, RED), t(180, 68, 'A: 回収できない分のうちプロセスが触ったページ', 13, fill=SUB),
          r(530, 56, 14, 14, YEL), t(550, 68, 'B: ファイル由来', 13, fill=SUB),
          r(690, 56, 14, 14, '#fff', DRK, 0, 2), t(710, 68, '回収できない RAM(cgroup)', 13, fill=SUB)]
    X0 = 250; y = 92
    for gl, items in groups:
        if gl: b += [t(30, y + 14, gl, 15, bold=True)]; y += 24
        for lab, A, B, C, P in items:
            b += [t(X0 - 12, y + 24, lab, 14, 'end', bold=('UPX' in lab))]
            b += [r(X0, y, A * sc, 22, RED), r(X0 + A * sc, y, B * sc, 22, YEL),
                  t(X0 + (A + B) * sc + 8, y + 16, f'PSS {P:,.1f}(A {A:,.1f} + B {B:,.1f})', 12, fill=DARK)]
            b += [r(X0, y + 26, C * sc, 14, '#fff', DRK, 0, 2), t(X0 + C * sc + 8, y + 38, f'cgroup {C:,.1f}', 12, fill=DRK, bold=True)]
            y += 54
        y += 10
    for k, f in enumerate(foot): b += [t(30, y + 10 + k * 20, f, 11.5, fill=SUB)]
    save(name, svg(1000, int(y + 20 + 20 * len(foot)), b))

ab_fig('fig6-startup-ram.svg', '起動直後の RAM(arm64、テストページを開いて 30 秒後、単位 MiB)',
       [('起動フラグなし', [('CEF 既定', 159.2, 228.7, 160.5, 387.6), ('削減版', 127.5, 159.4, 128.8, 286.7), ('削減版、SwiftShader なし', 93.8, 141.0, 101.8, 234.7), ('削減版、SwiftShader なし + UPX', 309.4, 27.1, 715.4, 336.5)]),
        ('3 フラグ(--disable-gpu 付き)', [('CEF 既定', 58.0, 208.2, 65.7, 266.1), ('削減版、SwiftShader なし', 48.8, 139.7, 56.7, 188.5), ('削減版、SwiftShader なし + UPX', 162.9, 25.6, 210.0, 188.5)])], 0.85,
       ['PSS = A + B(smaps_rollup。中央値を別々に取るので 0.3MiB ほどずれる)。cgroup は memory.stat の anon + shmem で、どのプロセスも触っていないページも含む。', '8 CPU / 8GB の arm64 コンテナ、3 回の中央値。logs/428、483、514。'])

ab_fig('fig10-upx-ram.svg', 'H.264 1080p 再生中の RAM(arm64、単位 MiB)',
       [('起動フラグなし', [('CEF 既定', 789.8, 255.8, 790.0, 1045.5), ('削減版', 590.3, 167.3, 598.3, 757.7), ('削減版 + UPX', 855.0, 32.5, 1366.2, 887.6)]),
        ('3 フラグ', [('CEF 既定', 660.7, 251.4, 661.9, 912.2), ('削減版', 528.9, 165.2, 537.7, 694.0), ('削減版 + UPX', 649.6, 31.9, 679.0, 681.5)])], 0.42,
       ['UPX では、展開したコードのうちプロセスが触っていない部分が cgroup にだけ入るので、cgroup が PSS を超える。', '最後まで再生できた 2 回の中央値。CEF 既定は SwiftShader で描画、削減版の 3 フラグは --disable-gpu。M18、logs/484。'])

# ---- 図 15: 描画の経路(GPU あり / GPU なし + SwiftShader / GPU なし・SwiftShader なし)
def box(x, y, w, h, s1, s2='', fill='#f1f3f4', st=GRY, bold=False, sw=1):
    o = [r(x, y, w, h, fill, st, 6, sw), t(x + w / 2, y + (h / 2 + 5 if not s2 else h / 2 - 3), s1, 14, 'middle', bold=bold)]
    if s2: o += [t(x + w / 2, y + h / 2 + 15, s2, 11.5, 'middle', SUB)]
    return o
def arrow(x, y1, y2):
    return [line(x, y1, x, y2 - 6, SUB, 1.5), f'<path d="M{x-5},{y2-8} L{x+5},{y2-8} L{x},{y2} z" fill="{SUB}"/>']
b = [t(30, 36, 'Chromium の描画の経路: GPU、SwiftShader、ソフトウェア合成', 20, bold=True),
     t(30, 60, 'ページの絵(タイル)を描く処理は、今回の 3 つの環境ではどれも CPU(Skia)。違いは、絵や動画を 1 枚の画面にまとめる「合成」と、WebGL の行き先。', 12.5, fill=SUB)]
cols = [('① GPU あり(実機)', '#e8f0fe', BLUE), ('② GPU なし、SwiftShader あり', '#fef7e0', '#f9ab00'), ('③ GPU なし、SwiftShader なし', '#fce8e6', RED)]
W = 300; G = 20; X = [30 + i * (W + G) for i in range(3)]
for i, (title, bg, col) in enumerate(cols):
    x = X[i]
    b += [r(x, 78, W, 560, bg, col, 10, 2), t(x + W / 2, 104, title, 15, 'middle', bold=True)]
    b += box(x + 20, 120, W - 40, 44, 'Blink(ページの内容)')
    b += arrow(x + W / 2, 164, 182)
    b += box(x + 20, 182, W - 40, 44, 'ページの絵を描く(ラスタ)', 'Skia が CPU で描く' if i else 'Skia。GPU でも描ける')
    b += arrow(x + W / 2, 226, 244)
    if i < 2:
        b += box(x + 20, 244, W - 40, 44, '合成(GPU 合成)', 'Skia が GLES を呼ぶ', '#fff', col, True, 2)
        b += arrow(x + W / 2, 288, 306)
        b += box(x + 20, 306, W - 40, 44, 'ANGLE', 'GLES を下の API に翻訳')
        b += arrow(x + W / 2, 350, 368)
        if i == 0:
            b += box(x + 20, 368, W - 40, 44, 'GPU ドライバ', '機器ベンダーの GLES / Vulkan')
            b += arrow(x + W / 2, 412, 430)
            b += box(x + 20, 430, W - 40, 44, 'GPU(ハードウェア)', '', '#fff', BLUE, True, 2)
        else:
            b += box(x + 20, 368, W - 40, 44, 'SwiftShader', 'GPU のふりをする CPU のプログラム', '#fff', '#f9ab00', True, 2)
            b += arrow(x + W / 2, 412, 430)
            b += box(x + 20, 430, W - 40, 44, 'CPU', '', '#fff', GRY, True, 2)
    else:
        b += box(x + 20, 244, W - 40, 44, '合成(ソフトウェア合成)', 'Skia が CPU で直接まとめる', '#fff', RED, True, 2)
        b += arrow(x + 60, 288, 430)
        b += [t(x + 80, 340, 'GLES、ANGLE、GPU ドライバ、', 12.5, 'start', SUB), t(x + 80, 360, 'SwiftShader を通らない', 12.5, 'start', SUB), t(x + 80, 380, '(GL を無効にする)', 12.5, 'start', SUB)]
        b += [line(x + 60, 474, x + 60, 474)]
        b += box(x + 20, 430, W - 40, 44, 'CPU', '', '#fff', GRY, True, 2)
    b += arrow(x + W / 2, 474, 492)
    b += box(x + 20, 492, W - 40, 36, '画面')
    res = [('WebGL ○', 'GPU 合成 ○', '今回は未計測'),
           ('WebGL ○(CPU で動くので遅い)', 'GPU 合成 ○(実体は CPU)', '削減版: 1080p60 でコマ落ち 約 3 割'),
           ('WebGL ×', 'GPU 合成 ×(ソフトウェア合成)', '削減版: 1080p60 でコマ落ち 0')][i]
    for k, s in enumerate(res): b += [t(x + W / 2, 556 + k * 22, s, 13, 'middle', bold=(k == 0))]
b += [t(30, 662, 'CEF 既定は②、今回の「削減版、SwiftShader なし」は③。②と③の WebGL、GPU 合成の状態は SystemInfo.getInfo の featureStatus(logs/515b)。', 11.5, fill=SUB),
      t(30, 682, 'コマ落ちは YouTube 1080p60、AV1、ソフトウェアデコード、マルチプロセス(logs/421、422)。①は実機で確かめていない。', 11.5, fill=SUB),
      t(30, 702, 'GPU がない、または初期化に失敗すると、マルチプロセスでは ②(SwiftShader があれば)か ③ に切り替わる。--single-process では切り替えられない。', 11.5, fill=SUB)]
save('fig15-render-paths.svg', svg(1000, 718, b))
