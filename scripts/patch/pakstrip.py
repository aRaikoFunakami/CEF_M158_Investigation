#!/usr/bin/env python3
"""pakstrip.py <in.pak> <resources.pak.info> <out.pak> [--with-pdf] [--report]

resources.pak から TV 向けに不要なリソースを落とす(配布物を作る段階の後処理)。
生成元の grd(resources.pak.info の 3 列目)で「残すもの」を決める。残すのは Blink、content、net、
エラーページ類(components/resources)、CEF、拡張機能のレンダラ用 JS など、Web ページの表示に要るものだけ。
落とすのは chrome:// の WebUI(設定、履歴、新しいタブ、各種 internals)、DevTools フロントエンド、
WebUI の共有部品(Polymer / Lit / cr_elements)、起動演出の音声(IDR_INTRO_SOUND_*、FLAC 4.8MB)など。

--with-pdf: PDF ビューアと印刷プレビュー、それらが使う chrome://resources の共有部品を残す
            (PDF / 印刷を buildflag で外していない構成向け)。
"""
import sys, os, re, collections
SRC = os.environ.get('FP_SRC', '/root/cef/chromium/src')
sys.path.insert(0, SRC + '/tools/grit')
from grit.format import data_pack

KEEP = [
    r'^third_party/blink/', r'^gen/third_party/blink/', r'^resources/inspector_overlay/',
    r'^content/content_resources\.grd$', r'^net/', r'^chrome/common/', r'^chrome/app/theme/', r'^cef/',
    r'^mojo/public/js/mojo_bindings_resources\.grd$', r'^base/tracing/', r'^components/metrics/server_urls\.grd$',
    r'^components/resources/(?!dom_distiller)',
    r'^chrome/browser/browser_resources\.grd$',
    # 拡張機能(buildflag で外すまでは、レンダラのバインディング JS とコンポーネント拡張のマニフェストが要る)
    r'^extensions/', r'^gen/extensions/', r'^gen/chrome/renderer/resources/', r'^chrome/browser/resources/component_extension_resources\.grd$',
    r'^\(unknown\)$',
]
KEEP_PDF = [
    r'^gen/chrome/browser/resources/(pdf|print_preview)/', r'^gen/ui/webui/resources/', r'^gen/third_party/(polymer|lit|lottie)/',
    r'^gen/mojo/', r'^gen/bufbuild\.grdp$',
]
DROP_NAMES = [r'^IDR_INTRO_SOUND_']

def main():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    inp, info, out = a[0], a[1], a[2]
    keep = KEEP + (KEEP_PDF if '--with-pdf' in sys.argv else [])
    keep_re = [re.compile(k) for k in keep]; drop_re = [re.compile(k) for k in DROP_NAMES]
    names = {}
    for l in open(info):
        f = l.rstrip('\n').split(',')
        if len(f) >= 3 and f[1].isdigit(): names[int(f[1])] = (f[0], os.path.normpath(f[2]).replace('../../', ''))
    d = data_pack.ReadDataPack(inp)
    res = {}; kept = collections.Counter(); dropped = collections.Counter()
    for i, b in d.resources.items():
        n, g = names.get(i, ('', '(unknown)'))
        ok = any(r.search(g) for r in keep_re) and not any(r.search(n) for r in drop_re)
        if ok: res[i] = b; kept[g] += len(b)
        else: dropped[g if not any(r.search(n) for r in drop_re) else g + ' [' + DROP_NAMES[0] + ']'] += len(b)
    data_pack.WriteDataPack(res, out, d.encoding)
    print(f'in  {os.path.getsize(inp)/1e6:.2f} MB {len(d.resources)} resources')
    print(f'out {os.path.getsize(out)/1e6:.2f} MB {len(res)} resources (with_pdf={"--with-pdf" in sys.argv})')
    if '--report' in sys.argv:
        print('--- kept'); [print(f'{v/1e6:8.3f} MB {g}') for g, v in kept.most_common()]
        print('--- dropped (top 40)'); [print(f'{v/1e6:8.3f} MB {g}') for g, v in dropped.most_common(40)]
        print(f'--- dropped total {sum(dropped.values())/1e6:.2f} MB in {len(dropped)} groups')

if __name__ == '__main__': main()
