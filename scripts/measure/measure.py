#!/usr/bin/env python3
"""フットプリント計測と動作確認。コンテナ内で実行する。
  measure.py size  <name> <outdir> <binary>            ディスクサイズ
  measure.py mem   <name> <outdir> <binary> [runs]     メモリ(PSS) 3 時点
  measure.py func  <name> <outdir> <binary>            動作確認 + スクリーンショット
結果は <結果dir>/<name>-{size,mem,func}.json、スクリーンショットは <結果dir>/shots/。
"""
import sys, os, json, time, subprocess, shutil, glob, statistics, signal, re, shlex
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import CDP

RES = '/root/fp/results'; SHOTS = RES + '/shots'
YT_HOME = 'https://www.youtube.com/'
YT_WATCH = 'https://www.youtube.com/watch?v=aqz-KE-bpKQ'   # Big Buck Bunny (Blender Foundation 公式)
STRIP = '/root/chromium/src/third_party/llvm-build/Release+Asserts/bin/llvm-strip'
# arm64 の ELF は GNU size(x86 用)では読めないので、ELF の e_machine を見て aarch64-linux-gnu-size に切り替える(arm64 編で追加)
def size_tool(path):
    with open(path, 'rb') as f: h = f.read(20)
    return 'aarch64-linux-gnu-size' if h[18:20] == b'\xb7\x00' else 'size'

CEF_APPS = ('cefsimple', 'cefclient')

def sh(cmd): return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout

def wait_port_free(port=9222, sec=15):
    import socket
    for _ in range(sec * 2):
        with socket.socket() as k:
            if k.connect_ex(('127.0.0.1', port)) != 0: return True
        time.sleep(0.5)
    return False

def launch(binary, url='about:blank', keep_profile=False):
    kill(binary)
    if not wait_port_free(): print('WARNING: port 9222 still in use:', sh('ss -ltnp | grep 9222'))
    prof = '/root/fp/profile'
    if not keep_profile: shutil.rmtree(prof, ignore_errors=True)
    is_shell = os.path.basename(binary) == 'content_shell'
    if os.path.basename(binary) in CEF_APPS:
        # CEF: Alloy スタイルで起動する。URL は --url= で渡す。ウィンドウは最大化(Xvfb 1920x1080)。
        args = [binary, '--use-alloy-style', '--no-sandbox', '--remote-debugging-port=9222', '--remote-allow-origins=*',
                '--autoplay-policy=no-user-gesture-required', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
                '--lang=ja', f'--user-data-dir={prof}', '--password-store=basic', '--initial-show-state=maximized', f'--url={url}']
        extra = shlex.split(os.environ.get('FP_EXTRA_ARGS', ''))   # 切り分け用の追加引数(logs/158)。空白入りの --js-flags="..." のために shlex で分割(arm64 編)
        # SwiftShader のないビルド(G2-tv)を --single-process で動かすときは、SwiftShader を指定する 3 引数を外して --disable-gpu を付ける(logs/439〜441)。
        # single-process では GPU がスレッドなので作り直しによるフォールバックができず、GL 初期化に失敗したまま CreateGLContext で落ちるため。
        # FP_NO_GL_ARGS=1 で、条件によらず 3 引数だけを外せる(切り分け用)。
        no_ss = '--single-process' in extra and not os.path.exists(os.path.join(os.path.dirname(binary), 'libvk_swiftshader.so'))
        if no_ss or os.environ.get('FP_NO_GL_ARGS'):
            args = [a for a in args if a not in ('--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader')]
        if no_ss and '--disable-gpu' not in extra: extra.append('--disable-gpu')
        args[1:1] = extra
        env = dict(os.environ, DISPLAY=':1')
        log = open('/root/fp/browser-run.log', 'ab')
        p = subprocess.Popen(args, env=env, stdout=log, stderr=log, start_new_session=True, cwd=os.path.dirname(binary))
        return p, CDP(9222, wait=90)
    args = [binary, '--no-sandbox', '--remote-debugging-port=9222', '--autoplay-policy=no-user-gesture-required',
            '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--lang=ja',
            f'--user-data-dir={prof}', '--no-first-run', '--no-default-browser-check', '--password-store=basic']
    args += ['--content-shell-host-window-size=1920x1080'] if is_shell else ['--window-size=1920,1080', '--window-position=0,0']
    args.append(url)
    env = dict(os.environ, DISPLAY=':1')
    log = open('/root/fp/browser-run.log', 'ab')
    p = subprocess.Popen(args, env=env, stdout=log, stderr=log, start_new_session=True)
    return p, CDP(9222, wait=90)

def procs(binary):
    real = os.path.realpath(binary); out = []
    for d in glob.glob('/proc/[0-9]*'):
        try:
            if os.path.realpath(d + '/exe') == real: out.append(int(d[6:])); continue
            # Rosetta 上では exe が /run/rosetta/rosetta を指す場合がある(CEF で発生、logs/138)。argv[0] でも照合する。
            a0 = open(d + '/cmdline', 'rb').read().split(b'\0')[0].decode('utf-8', 'replace')
            if a0 and os.path.realpath(a0) == real and open(d + '/stat').read().rsplit(')', 1)[1].split()[0] != 'Z': out.append(int(d[6:]))
        except OSError: pass
    return out

def kill(binary):
    for _ in range(3):
        ps = procs(binary)
        if not ps: return
        for p in ps:
            try: os.kill(p, signal.SIGKILL)
            except OSError: pass
        time.sleep(1)

def pss(binary):
    """全プロセスの smaps_rollup を合算。種別(--type=)ごとの内訳つき。単位 MB。"""
    tot = {'pss': 0, 'pss_anon': 0, 'pss_file': 0, 'pss_shmem': 0, 'rss': 0, 'procs': 0}; by = {}
    for pid in procs(binary):
        try:
            # arm64 ネイティブでは子プロセスが setproctitle で cmdline を空白区切りの 1 文字列に書き換える(logs/416)。NUL と空白の両方で区切る
            cmd = re.split(rb'[\0 ]', open(f'/proc/{pid}/cmdline', 'rb').read())
            typ = 'browser'
            for a in cmd:
                if a.startswith(b'--type='): typ = a[7:].decode()
                if a.startswith(b'--utility-sub-type='): typ = 'utility:' + a[19:].decode().split('.')[-1]
            d = {}
            for l in open(f'/proc/{pid}/smaps_rollup'):
                f = l.split()
                if len(f) >= 3 and f[-1] == 'kB': d[f[0].rstrip(':')] = int(f[1])
        except OSError: continue
        # zygote も数える。CEF では zygote から fork したレンダラ / GPU の cmdline が --type=zygote のまま残り、
        # 除外するとレンダラと GPU が丸ごと漏れる(logs/143 で procs=2〜3 しかなかった)。
        vals = {'pss': d.get('Pss', 0), 'pss_anon': d.get('Pss_Anon', 0), 'pss_file': d.get('Pss_File', 0), 'pss_shmem': d.get('Pss_Shmem', 0), 'rss': d.get('Rss', 0)}
        for k, v in vals.items(): tot[k] += v
        tot['procs'] += 1
        b = by.setdefault(typ, {'pss': 0, 'n': 0}); b['pss'] += vals['pss']; b['n'] += 1
    r = {k: (round(v / 1024, 1) if k != 'procs' else v) for k, v in tot.items()}
    r['by_type'] = {k: {'pss': round(v['pss'] / 1024, 1), 'n': v['n']} for k, v in sorted(by.items())}
    return r

def video_state(c):
    return c.eval("""(()=>{const v=document.querySelector('video'); if(!v) return null;
      const q=v.getVideoPlaybackQuality?v.getVideoPlaybackQuality():{};
      return {currentTime:v.currentTime, paused:v.paused, size:v.videoWidth+'x'+v.videoHeight, readyState:v.readyState,
              total:q.totalVideoFrames, dropped:q.droppedVideoFrames}})()""")

def yt_play(c):
    """再生を開始させ、画質を要求する(既定 1080p。環境変数 FP_YT_QUALITY で hd720 などに変えられる。M18 で追加)。"""
    q = os.environ.get('FP_YT_QUALITY', 'hd1080')
    c.navigate(YT_WATCH); time.sleep(12)
    c.eval("""(()=>{const p=document.getElementById('movie_player'); if(p){ try{p.setPlaybackQualityRange&&p.setPlaybackQualityRange('QQ','QQ');}catch(e){}""".replace('QQ', q) + """
       try{p.playVideo&&p.playVideo();}catch(e){} } const v=document.querySelector('video'); if(v&&v.paused) v.play().catch(()=>{}); return 1})()""")

def playing(v):
    return bool(v and v.get('readyState', 0) >= 3 and not v.get('paused') and v.get('currentTime', 0) > 5)

def cmd_mem(name, binary, runs):
    """runs 回ぶん「再生点で実際に再生中だった」計測が集まるまで繰り返す(最大 runs*4 回)。
    YouTube は "Something went wrong" で間欠的に止まる(Chromium 編の content_shell でも同じ。logs/159)。
    止まった回の yt_play は約 100MB 低く出るので中央値から除く(blank / yt_home は全回を使う)。"""
    os.makedirs(SHOTS, exist_ok=True); allruns = []; valid = 0; shot = False
    for i in range(runs * 4):
        if valid >= runs: break
        p, c = launch(binary); r = {}
        try:
            time.sleep(20); r['blank'] = pss(binary)
            c.navigate(YT_HOME); time.sleep(30); r['yt_home'] = pss(binary)
            if i == 0: c.screenshot(f'{SHOTS}/{name}-mem-yt-home.png')
            yt_play(c); time.sleep(60); r['yt_play'] = pss(binary); r['video'] = video_state(c)
            r['playing'] = playing(r['video'])
            if r['playing']:
                valid += 1
                if not shot: c.screenshot(f'{SHOTS}/{name}-mem-yt-play.png'); shot = True
            else:
                r['yt_play_stopped'] = r.pop('yt_play')
        except Exception as e: r['error'] = repr(e)
        kill(binary); allruns.append(r); print(json.dumps(r, ensure_ascii=False)); sys.stdout.flush()
    print(f'VALID_PLAY_RUNS {valid}/{len(allruns)}')
    med = {}
    for pt in ('blank', 'yt_home', 'yt_play'):
        vals = [x[pt] for x in allruns if pt in x]
        if vals: med[pt] = {k: statistics.median(v[k] for v in vals) for k in ('pss', 'pss_anon', 'pss_file', 'pss_shmem', 'rss', 'procs')}
    out = {'name': name, 'binary': binary, 'runs': allruns, 'median': med}
    json.dump(out, open(f'{RES}/{name}-mem.json', 'w'), ensure_ascii=False, indent=1)
    print('MEDIAN', json.dumps(med))

def cmd_func(name, binary):
    os.makedirs(SHOTS, exist_ok=True); res = {}
    p, c = launch(binary)
    try:
        for page, wait in (('caps', 20), ('sw', 30), ('ws', 20), ('mp4', 80), ('mse', 90), ('eme', 90)):
            c.navigate(f'http://localhost:8000/{page}.html'); t0 = time.time(); r = None
            while time.time() - t0 < wait:
                time.sleep(2); r = c.eval('window.__result || null', await_promise=False)
                if r: break
            time.sleep(1); c.screenshot(f'{SHOTS}/{name}-func-{page}.png'); res[page] = r or {'pass': False, 'error': 'timeout'}
            print(page, json.dumps(res[page], ensure_ascii=False)[:600]); sys.stdout.flush()
        # YouTube は間欠的に "Something went wrong" で止まる(構成に依存しない。logs/157、159)。最大 4 回まで開き直す。
        tries = []
        for attempt in range(4):
            yt_play(c); time.sleep(25); v1 = video_state(c); time.sleep(10); v2 = video_state(c)
            ok = bool(v1 and v2 and v2['currentTime'] > v1['currentTime'] and not v2['paused'] and v2['readyState'] >= 3)
            tries.append({'ok': ok, 't1': v1, 't2': v2})
            if ok: break
            c.screenshot(f'{SHOTS}/{name}-func-youtube-fail{attempt + 1}.png')
        c.screenshot(f'{SHOTS}/{name}-func-youtube.png')
        res['youtube'] = {'pass': ok, 'attempts': len(tries), 't1': v1, 't2': v2, 'tries': tries, 'title': c.eval('document.title', await_promise=False)}
        print('youtube', json.dumps(res['youtube'], ensure_ascii=False))
        sh(f'DISPLAY=:1 scrot -o {SHOTS}/{name}-func-youtube-desktop.png')
    except Exception as e: res['error'] = repr(e); print('ERROR', repr(e))
    kill(binary)
    json.dump({'name': name, 'binary': binary, 'results': res}, open(f'{RES}/{name}-func.json', 'w'), ensure_ascii=False, indent=1)
    print('SUMMARY', {k: (v.get('pass') if isinstance(v, dict) else v) for k, v in res.items()})

def cmd_size(name, binary):
    d = os.path.dirname(binary); base = os.path.basename(binary); r = {'name': name, 'binary': binary, 'files': {}}
    st = f'/root/fp/stripped/{name}-{base}'; os.makedirs(os.path.dirname(st), exist_ok=True)
    sh(f'{STRIP} -o {st} {binary}')
    r['unstripped'] = os.path.getsize(binary); r['stripped'] = os.path.getsize(st)
    f = sh(f'{size_tool(st)} {st}').splitlines()[1].split(); r['text'], r['data'], r['bss'] = int(f[0]), int(f[1]), int(f[2])
    is_cef = base in CEF_APPS
    if is_cef:
        # CEF: 本体は libcef.so。実行ファイルと合算する。
        lib = f'{d}/libcef.so'; stl = f'/root/fp/stripped/{name}-libcef.so'
        sh(f'{STRIP} -o {stl} {lib}')
        r['exe_stripped'] = r['stripped']; r['libcef_unstripped'] = os.path.getsize(lib); r['libcef_stripped'] = os.path.getsize(stl)
        f = sh(f'{size_tool(stl)} {stl}').splitlines()[1].split()
        r['text'] += int(f[0]); r['data'] += int(f[1]); r['bss'] += int(f[2])
        r['unstripped'] += r['libcef_unstripped']; r['stripped'] += r['libcef_stripped']
    if base == 'chrome' or is_cef:
        files = ['resources.pak', 'chrome_100_percent.pak', 'chrome_200_percent.pak', 'icudtl.dat', 'v8_context_snapshot.bin', 'snapshot_blob.bin',
                 'libEGL.so', 'libGLESv2.so', 'libvk_swiftshader.so', 'libvulkan.so.1', 'libVkLayer_khronos_validation.so', 'chrome_crashpad_handler',
                 'libqt5_shim.so', 'libqt6_shim.so', 'vk_swiftshader_icd.json', 'chrome_sandbox', 'chrome-sandbox']
    else:
        files = ['content_shell.pak', 'icudtl.dat', 'v8_context_snapshot.bin', 'snapshot_blob.bin', 'libEGL.so', 'libGLESv2.so',
                 'libvk_swiftshader.so', 'libvulkan.so.1', 'libVkLayer_khronos_validation.so', 'vk_swiftshader_icd.json', 'shell_resources.pak', 'ui_resources_100_percent.pak']
    for fn in files:
        p = f'{d}/{fn}'
        if os.path.exists(p): r['files'][fn] = os.path.getsize(p)
    loc = glob.glob(f'{d}/locales/*.pak')
    r['locales_all'] = sum(os.path.getsize(p) for p in loc); r['locales_n'] = len(loc)
    r['locales_ja_en'] = sum(os.path.getsize(p) for p in loc if os.path.basename(p) in ('ja.pak', 'en-US.pak'))
    r['total_ja_en'] = r['stripped'] + sum(r['files'].values()) + (r['locales_ja_en'] if base == 'chrome' or is_cef else 0)
    r['total_all_locales'] = r['stripped'] + sum(r['files'].values()) + (r['locales_all'] if base == 'chrome' or is_cef else 0)
    os.makedirs(RES, exist_ok=True)
    json.dump(r, open(f'{RES}/{name}-size.json', 'w'), indent=1)
    mb = lambda x: f'{x/1e6:.1f}MB'
    print(name, 'stripped', mb(r['stripped']), 'text', mb(r['text']), 'data', mb(r['data']), 'total(ja+en)', mb(r['total_ja_en']), 'total(all locales)', mb(r['total_all_locales']))
    for k, v in r['files'].items(): print('  ', k, mb(v))

if __name__ == '__main__':
    mode, name, binary = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(RES, exist_ok=True)
    if mode == 'size': cmd_size(name, binary)
    elif mode == 'mem': cmd_mem(name, binary, int(sys.argv[4]) if len(sys.argv) > 4 else 3)
    elif mode == 'func': cmd_func(name, binary)
