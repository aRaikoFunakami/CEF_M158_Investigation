#!/usr/bin/env python3
"""ytmem.py <name> <binary> [--runs N] [--play SEC] [--interval SEC] [--args "..."]

arm64 編の RAM 計測。YouTube(measure.YT_WATCH = https://www.youtube.com/watch?v=aqz-KE-bpKQ)を再生し、
再生中のメモリを時系列で記録する。measure.py mem との違い:
  - 再生開始から --play 秒(既定 120)まで --interval 秒(既定 10)ごとに標本を取る(時系列)。
  - 全プロセスの PSS(anon / file / shmem)とプロセス種別ごとの PSS に加え、cgroup v2(/sys/fs/cgroup/fpmeas)の
    anon / shmem / file と memory.peak を取る(startram.py と同じく、ブラウザを専用 cgroup に入れて起動する)。
  - YouTube プレーヤの「詳細統計情報」(getStatsForNerds)からコーデック、解像度、バッファ量を取る。
  - <video>.buffered から再生位置より先にバッファした秒数を取る(MSE のバッファ量の目安)。
  - 実行環境(nproc、MemTotal、起動引数)を結果に残す。
--args の起動引数は CEF / content_shell の起動引数に追加される(measure.launch の FP_EXTRA_ARGS)。
有効な回(再生点で実際に再生中だった回)が --runs 回(既定 3)集まるまで、最大 runs*3 回試す。
結果: <結果dir>/<name>-ytmem.json。単位は MiB(1024^2)。
"""
import sys, os, json, time, statistics, argparse, shlex, shutil, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure, memdump

CG = '/sys/fs/cgroup/fpmeas'
WARM = None   # --warm のとき、温めたプロファイルの保存先
CODEC_JS = None  # --codec h264 のとき、ページより先に評価させるスクリプト(M18)
LIMIT = None  # --limit のとき、計測 cgroup の memory.max(MiB)。ブラウザの全プロセス(anon + shmem + ページキャッシュ)が対象

def codec_js(codec, quality):
    """YouTube に H.264 を選ばせる: MSE の isTypeSupported、canPlayType、mediaCapabilities で AV1 / VP9 / VP8 / HEVC を非対応と答える。
    画質の希望(yt-player-quality)も localStorage に入れておく(setPlaybackQualityRange だけだと最初の数秒が別画質になることがある)。"""
    qn = {'hd2160': 2160, 'hd1440': 1440, 'hd1080': 1080, 'hd720': 720, 'large': 480, 'medium': 360}[quality]
    if codec == 'av1':
        # 4K で AV1 を選ばせる(M19、logs/450〜452)。YouTube は 1080p を超えると既定で VP9 を選ぶ。VP9 を非対応と答えると H.264 1080p まで落ちる。
        # mediaCapabilities.decodingInfo の av01 の問い合わせにだけ powerEfficient = true(H/W デコーダがあるふり)と答え、「常に AV1 を優先」(yt-player-av1-pref = 8192)を入れると AV1 になる。
        return '''(()=>{
  try{const mc=navigator.mediaCapabilities, d=mc.decodingInfo.bind(mc); mc.decodingInfo=cfg=>{const ct=(cfg&&cfg.video&&cfg.video.contentType)||''; return d(cfg).then(r=>/av01/i.test(ct)&&r.supported?{supported:true,smooth:true,powerEfficient:true,configuration:r.configuration}:r)};}catch(e){}
  try{if(location.hostname.endsWith('youtube.com')){const n=Date.now(); localStorage.setItem('yt-player-quality', JSON.stringify({data:JSON.stringify({quality:%s,previousQuality:%s}),expiration:n+864e5,creation:n})); localStorage.setItem('yt-player-av1-pref','8192');}}catch(e){}})()''' % (qn, qn)
    deny = {'h264': 'av01|vp09|vp9|vp8|hev1|hvc1|dvh1|dvhe'}[codec]
    return '''(()=>{const deny=/%s/i;
  try{const o=MediaSource.isTypeSupported.bind(MediaSource); MediaSource.isTypeSupported=t=>deny.test(t)?false:o(t);}catch(e){}
  try{if(window.ManagedMediaSource){const m=ManagedMediaSource.isTypeSupported.bind(ManagedMediaSource); ManagedMediaSource.isTypeSupported=t=>deny.test(t)?false:m(t);}}catch(e){}
  try{const c=HTMLMediaElement.prototype.canPlayType; HTMLMediaElement.prototype.canPlayType=function(t){return deny.test(t)?'':c.call(this,t)};}catch(e){}
  try{if(navigator.mediaCapabilities){const mc=navigator.mediaCapabilities, d=mc.decodingInfo.bind(mc);
    mc.decodingInfo=cfg=>{const ct=(cfg&&cfg.video&&cfg.video.contentType)||''; return deny.test(ct)?Promise.resolve({supported:false,smooth:false,powerEfficient:false}):d(cfg)};}}catch(e){}
  try{if(location.hostname.endsWith('youtube.com')){const n=Date.now(); localStorage.setItem('yt-player-quality', JSON.stringify({data:JSON.stringify({quality:%s,previousQuality:%s}),expiration:n+864e5,creation:n}));}}catch(e){}
})()''' % (deny, qn, qn)

def cg_events():
    d = {}
    if os.path.exists(CG + '/memory.events'):
        for l in open(CG + '/memory.events'): k, v = l.split(); d[k] = int(v)
    return d

def renderer_crashes():
    # CEF のログから、レンダラ / GPU の異常終了と OOM を数える(Chromium は子プロセスの終了理由をログに出す)
    try: t = open('/root/fp/browser-run.log', errors='replace').read()
    except OSError: return {}
    return {'renderer_gone': t.count('Renderer process') + t.count('render process gone') + t.count('RenderProcessGone'),
            'gpu_gone': t.count('GPU process exited') + t.count('GPU process isn\'t usable'), 'oom_word': t.lower().count('out of memory')}

def make_warm(binary, path):
    """YouTube を 1 回開いて 90 秒再生し、そのプロファイル(Cookie、訪問者情報、同意状態)を保存する。
    新しいプロファイルで毎回開くと、再生位置 40 秒前後で "Something went wrong" になる回が約半数あった(logs/423)。
    TV でも毎回まっさらなプロファイルで起動することはないので、こちらのほうが実態に近い。"""
    p, c = measure.launch(binary)
    try:
        measure.yt_play(c); time.sleep(90); v = measure.video_state(c); print('warm:', json.dumps(v), flush=True)
    finally:
        measure.kill(binary)
    time.sleep(3)
    for sub in ('Default/Cache', 'Default/Code Cache', 'Default/GPUCache', 'GrShaderCache', 'ShaderCache', 'Default/Service Worker/CacheStorage'):
        shutil.rmtree(f'/root/fp/profile/{sub}', ignore_errors=True)   # キャッシュは捨てる(Cookie / Local Storage は残す)
    shutil.rmtree(path, ignore_errors=True); shutil.copytree('/root/fp/profile', path, symlinks=True)
    for f in ('SingletonLock', 'SingletonSocket', 'SingletonCookie'):
        try: os.unlink(f'{path}/{f}')
        except OSError: pass
MIB = 1048576

def cg_stat():
    if not os.path.exists(CG + '/memory.stat'): return None
    d = {}
    for l in open(CG + '/memory.stat'):
        k, v = l.split()
        if k in ('anon', 'shmem', 'file', 'kernel', 'kernel_stack', 'pagetables', 'sock', 'slab'): d[k] = round(int(v) / MIB, 1)
    d['current'] = round(int(open(CG + '/memory.current').read()) / MIB, 1)
    if os.path.exists(CG + '/memory.peak'): d['peak'] = round(int(open(CG + '/memory.peak').read()) / MIB, 1)
    d['unreclaimable'] = round(d.get('anon', 0) + d.get('shmem', 0), 1)
    return d

NERDS_JS = r"""(()=>{const p=document.getElementById('movie_player'); const v=document.querySelector('video'); const r={};
  try{ const s=p&&p.getStatsForNerds?p.getStatsForNerds():null; if(s){ r.codecs=s.codecs; r.resolution=s.resolution; r.optimal_res=s.optimal_res;
       r.buffer_health_seconds=s.buffer_health_seconds; r.dims=s.dims_and_frames; r.mem=s.mem; } }catch(e){ r.err=String(e); }
  if(v){ r.currentTime=v.currentTime; r.paused=v.paused; r.size=v.videoWidth+'x'+v.videoHeight; r.readyState=v.readyState;
       let ahead=0; for(let i=0;i<v.buffered.length;i++){ if(v.buffered.start(i)<=v.currentTime+0.5&&v.buffered.end(i)>=v.currentTime) ahead=v.buffered.end(i)-v.currentTime; }
       r.buffered_ahead_s=Math.round(ahead*10)/10; r.buffered_ranges=v.buffered.length;
       let tot=0; for(let i=0;i<v.buffered.length;i++) tot+=v.buffered.end(i)-v.buffered.start(i); r.buffered_total_s=Math.round(tot*10)/10;
       r.n_video=document.querySelectorAll('video').length;
       const q=v.getVideoPlaybackQuality?v.getVideoPlaybackQuality():{}; r.total=q.totalVideoFrames; r.dropped=q.droppedVideoFrames; }
  try{ r.jsHeapUsedMiB=Math.round(performance.memory.usedJSHeapSize/1048576*10)/10; r.jsHeapLimitMiB=Math.round(performance.memory.jsHeapSizeLimit/1048576); }catch(e){}
  try{ r.deviceMemory=navigator.deviceMemory; r.hardwareConcurrency=navigator.hardwareConcurrency; }catch(e){}
  return r})()"""

def threads(binary):
    """プロセス種別ごとのスレッド数(CPU 数への依存を見るため。arm64 編で追加)"""
    out = {}
    for pid in measure.procs(binary):
        try:
            cmd = re.split(rb'[\0 ]', open(f'/proc/{pid}/cmdline', 'rb').read()); typ = 'browser'
            for a in cmd:
                if a.startswith(b'--type='): typ = a[7:].decode()
                if a.startswith(b'--utility-sub-type='): typ = 'utility:' + a[19:].decode().split('.')[-1]
            n = int([l for l in open(f'/proc/{pid}/status') if l.startswith('Threads:')][0].split()[1])
        except (OSError, IndexError): continue
        out[typ] = out.get(typ, 0) + n
    return out

def sample(binary, c):
    s = {'t': round(time.time(), 1), 'pss': measure.pss(binary), 'cg': cg_stat(), 'threads': threads(binary)}
    try: s['player'] = c.eval(NERDS_JS, await_promise=False)
    except Exception as e: s['player'] = {'error': repr(e)}
    return s

def one(name, binary, play, interval, shot):
    measure.kill(binary); time.sleep(2)
    use_cg = os.path.exists(CG + '/memory.stat')
    if use_cg:
        for _ in range(30):
            if not open(CG + '/cgroup.procs').read().strip(): break
            time.sleep(0.5)
        try: open(CG + '/memory.peak', 'w').write('0')   # 6.12 以降はリセットできる。できなければそのまま
        except OSError: pass
        open(CG + '/cgroup.procs', 'w').write(str(os.getpid()))
    if WARM:   # warm プロファイル方式: 保存しておいたプロファイルを毎回コピーして起動する
        shutil.rmtree('/root/fp/profile', ignore_errors=True); shutil.copytree(WARM, '/root/fp/profile', symlinks=True)
    if use_cg:
        open(CG + '/memory.max', 'w').write(str(LIMIT * MIB) if LIMIT else 'max')
        try: open(CG + '/memory.swap.max', 'w').write('0')
        except OSError: pass
    ev0 = cg_events()
    try: open('/root/fp/browser-run.log', 'w').close()
    except OSError: pass
    p, c = measure.launch(binary, keep_profile=bool(WARM))
    if CODEC_JS: c.call('Page.enable'); c.call('Page.addScriptToEvaluateOnNewDocument', source=CODEC_JS)   # Page.enable を先に呼ばないと注入されない(logs/446)
    if use_cg:
        dst = '/sys/fs/cgroup/main/cgroup.procs' if os.path.exists('/sys/fs/cgroup/main') else '/sys/fs/cgroup/cgroup.procs'
        open(dst, 'w').write(str(os.getpid()))
    r = {'timeline': []}
    try:
        time.sleep(15); r['blank'] = sample(binary, c)
        # YouTube は間欠的に "Something went wrong" で止まる(logs/157、418)。measure.py func と同じく、同じブラウザで開き直す(最大 4 回)。
        # 再生開始(currentTime > 1)を確認できた時点を t=0 とする。
        r['yt_attempts'] = 0
        for attempt in range(4):
            measure.yt_play(c); r['yt_attempts'] = attempt + 1; started = False
            for _ in range(20):
                time.sleep(2); v = measure.video_state(c)
                if v and v.get('currentTime', 0) > 1 and not v.get('paused'): started = True; break
            if started: break
            if shot: c.screenshot(f'{measure.SHOTS}/{name}-ytmem-fail{attempt + 1}.png')
        t0 = time.time()
        while time.time() - t0 < play:
            time.sleep(interval)
            s = sample(binary, c); s['t'] = round(time.time() - t0); r['timeline'].append(s)
        # 最後に memory-infra のダンプでアロケータ別の内訳を取る(logs/427)
        # 上限つき(--limit)のときは取らない: ダンプ自体がメモリを使い、再生は終わっているのに OOM kill される(logs/447)
        if not LIMIT:
            try: r['memdump'] = memdump.memdump(); r['memdump_summary'] = memdump.summarize(r['memdump'])
            except Exception as e: r['memdump_error'] = repr(e)
        last = r['timeline'][-1]['player'] if r['timeline'] else {}
        mid = r['timeline'][len(r['timeline']) // 2]['player'] if r['timeline'] else {}
        r['playing'] = bool(last.get('readyState', 0) >= 3 and not last.get('paused') and last.get('currentTime', 0) > mid.get('currentTime', 0) + 1)
        if shot: c.screenshot(f'{measure.SHOTS}/{name}-ytmem-play.png')
    except Exception as e:
        r['error'] = repr(e); r['playing'] = False
    measure.kill(binary)
    ev1 = cg_events(); r['cg_events'] = {k: ev1.get(k, 0) - ev0.get(k, 0) for k in ev1}; r['crashes'] = renderer_crashes()
    if use_cg: open(CG + '/memory.max', 'w').write('max')
    return r

def summarize(runs):
    ok = [r for r in runs if r.get('playing')]
    def med(f):
        v = [f(r) for r in ok]; v = [x for x in v if x is not None]
        return round(statistics.median(v), 1) if v else None
    def tl(r, key):
        return [key(s) for s in r['timeline'] if s.get('pss')]
    out = {'valid': len(ok), 'tried': len(runs)}
    out['blank_pss'] = med(lambda r: r['blank']['pss']['pss'])
    out['blank_unreclaimable_cg'] = med(lambda r: (r['blank'].get('cg') or {}).get('unreclaimable'))
    # 再生中: 後半(再生開始 60 秒以降)の標本の中央値と、全区間の最大値
    late = lambda r: [s for s in r['timeline'] if s['t'] >= 60] or r['timeline']
    out['play_pss_median'] = med(lambda r: statistics.median(s['pss']['pss'] for s in late(r)))
    out['play_pss_max'] = med(lambda r: max(s['pss']['pss'] for s in r['timeline']))
    out['play_anon_median'] = med(lambda r: statistics.median(s['pss']['pss_anon'] for s in late(r)))
    out['play_file_median'] = med(lambda r: statistics.median(s['pss']['pss_file'] for s in late(r)))
    out['play_shmem_median'] = med(lambda r: statistics.median(s['pss']['pss_shmem'] for s in late(r)))
    out['play_unreclaimable_cg_median'] = med(lambda r: statistics.median((s.get('cg') or {}).get('unreclaimable', 0) for s in late(r)) if late(r)[0].get('cg') else None)
    out['play_cg_peak'] = med(lambda r: (r['timeline'][-1].get('cg') or {}).get('peak'))
    out['procs'] = med(lambda r: late(r)[-1]['pss']['procs'])
    out['buffer_ahead_s'] = med(lambda r: statistics.median(s['player'].get('buffered_ahead_s', 0) or 0 for s in late(r)))
    out['dropped_ratio'] = med(lambda r: (late(r)[-1]['player'].get('dropped', 0) or 0) / max(1, late(r)[-1]['player'].get('total', 1) or 1))
    if ok:
        last = ok[0]['timeline'][-1]['player']
        out['codecs'] = last.get('codecs'); out['resolution'] = last.get('resolution') or last.get('size')
        out['jsHeapLimitMiB'] = last.get('jsHeapLimitMiB'); out['deviceMemory'] = last.get('deviceMemory'); out['hardwareConcurrency'] = last.get('hardwareConcurrency')
        types = {}
        for r in ok:
            for k, v in late(r)[-1]['pss']['by_type'].items(): types.setdefault(k, []).append(v['pss'])
        out['by_type_last'] = {k: round(statistics.median(v), 1) for k, v in types.items()}
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('name'); ap.add_argument('binary'); ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--play', type=int, default=120); ap.add_argument('--interval', type=int, default=10)
    ap.add_argument('--args', default='')
    ap.add_argument('--codec', default='', help='h264: YouTube に H.264 を選ばせる(M18)。av1: AV1 を選ばせる(M19)')
    ap.add_argument('--quality', default='hd1080', help='YouTube に要求する画質(hd2160 / hd1440 / hd1080 / hd720 / large / medium)')
    ap.add_argument('--limit', type=int, default=0, help='計測 cgroup の memory.max(MiB)。0 は制限なし')
    ap.add_argument('--max-tries', type=int, default=0, help='最大試行回数(既定 runs*3)')
    ap.add_argument('--warm', action='store_true', help='温めたプロファイルを使う(/root/fp/profile-warm-<binary のビルド名>。なければ作る)')
    a = ap.parse_args()
    if a.args: os.environ['FP_EXTRA_ARGS'] = (os.environ.get('FP_EXTRA_ARGS', '') + ' ' + a.args).strip()
    os.makedirs(measure.SHOTS, exist_ok=True)
    env = {'nproc': os.cpu_count(), 'memtotal_kib': int([l for l in open('/proc/meminfo') if l.startswith('MemTotal')][0].split()[1]),
           'arch': os.uname().machine, 'extra_args': os.environ.get('FP_EXTRA_ARGS', ''), 'url': measure.YT_WATCH}
    global WARM, LIMIT, CODEC_JS
    os.environ['FP_YT_QUALITY'] = a.quality
    if a.codec: CODEC_JS = codec_js(a.codec, a.quality)
    LIMIT = a.limit or None
    if a.warm:
        WARM = '/root/fp/profile-warm-' + os.path.basename(os.path.dirname(a.binary))
        if not os.path.isdir(WARM): make_warm(a.binary, WARM)
    env['warm_profile'] = WARM; env['limit_mib'] = LIMIT; env['codec'] = a.codec or 'auto'; env['quality'] = a.quality
    runs = []
    for i in range(a.max_tries or a.runs * 3):
        if sum(1 for r in runs if r.get('playing')) >= a.runs: break
        if runs: time.sleep(30 if runs[-1].get('playing') else 180)   # 新しいプロファイルで続けて開くと YouTube が一時的に再生を拒む(logs/418、423)。失敗後は長めに待つ
        r = one(a.name, a.binary, a.play, a.interval, shot=(i == 0)); runs.append(r)
        last = r['timeline'][-1] if r.get('timeline') else {}
        print(f"run {i+1}: playing={r.get('playing')} pss={last.get('pss', {}).get('pss')} cg={(last.get('cg') or {}).get('unreclaimable')} "
              f"events={r.get('cg_events')} crashes={r.get('crashes')} "
              f"player={json.dumps(last.get('player', {}), ensure_ascii=False)[:300]} {r.get('error', '')}", flush=True)
    s = summarize(runs)
    json.dump({'name': a.name, 'binary': a.binary, 'env': env, 'summary': s, 'runs': runs}, open(f'{measure.RES}/{a.name}-ytmem.json', 'w'), ensure_ascii=False, indent=1)
    print('ENV', json.dumps(env, ensure_ascii=False)); print('SUMMARY', json.dumps(s, ensure_ascii=False))

if __name__ == '__main__': main()
