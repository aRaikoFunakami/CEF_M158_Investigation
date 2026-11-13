#!/usr/bin/env python3
"""mediaprobe.py <name> <binary> [page...] : 再生中のメディアプレーヤが実際に使ったデコーダを調べる(S/W か H/W か)。
CDP の Media ドメイン(Media.enable)で、WebMediaPlayer が報告するプロパティを集める。主なもの:
  kVideoDecoderName(Dav1dVideoDecoder / VpxVideoDecoder / FFmpegVideoDecoder なら S/W、VaapiVideoDecoder / V4L2VideoDecoder /
  VideoDecoderPipeline / MojoVideoDecoder なら H/W 経路)、kIsPlatformVideoDecoder(true なら H/W)、kAudioDecoderName、
  kVideoTracks(コーデック)、kIsVideoDecryptingDemuxerStream。
page: youtube(既定)、mp4、mse、eme(tools/fp/site のテストページ)。結果: <RES>/<name>-mediaprobe.json"""
import sys, os, json, time, socket
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure

KEYS = ('kVideoDecoderName', 'kIsPlatformVideoDecoder', 'kAudioDecoderName', 'kIsPlatformAudioDecoder', 'kVideoTracks', 'kAudioTracks',
        'kIsVideoDecryptingDemuxerStream', 'kFramerate', 'kVideoPlaybackRoughness', 'kRendererName', 'kHardwareContextReset')

def collect(c, sec):
    """sec 秒の間、Media ドメインのイベントを読む。"""
    props = {}; errs = []; msgs = []
    c.ws.s.settimeout(1.0); t0 = time.time()
    while time.time() - t0 < sec:
        try: m = json.loads(c.ws.recv())
        except (socket.timeout, TimeoutError): continue
        except Exception: break
        meth = m.get('method', '')
        if meth == 'Media.playerPropertiesChanged':
            pid = m['params']['playerId']
            for p in m['params']['properties']:
                props.setdefault(pid, {})[p['name']] = p['value']
        elif meth == 'Media.playerErrorsRaised': errs += m['params'].get('errors', [])
        elif meth == 'Media.playerMessagesLogged':
            for x in m['params'].get('messages', []):
                if any(w in x.get('message', '') for w in ('ecoder', 'VAAPI', 'Vaapi', 'V4L2', 'GpuVideo', 'platform')): msgs.append(x['message'][:200])
    c.ws.s.settimeout(120)
    return props, errs, msgs

def main():
    name, binary = sys.argv[1], sys.argv[2]; pages = sys.argv[3:] or ['youtube']
    os.makedirs(measure.SHOTS, exist_ok=True)
    p, c = measure.launch(binary); out = {'name': name, 'binary': binary, 'extra_args': os.environ.get('FP_EXTRA_ARGS', ''), 'pages': {}}
    try:
        c.call('Media.enable')
        for pg in pages:
            if pg == 'youtube': measure.yt_play(c); wait = 40
            else: c.navigate(f'http://localhost:8000/{pg}.html'); wait = 25
            props, errs, msgs = collect(c, wait)
            sel = {pid: {k: v for k, v in pr.items() if k in KEYS} for pid, pr in props.items()}
            out['pages'][pg] = {'players': sel, 'errors': errs[:5], 'decoder_msgs': msgs[:10], 'video': measure.video_state(c)}
            print(pg, json.dumps(out['pages'][pg], ensure_ascii=False)[:900], flush=True)
            c.screenshot(f'{measure.SHOTS}/{name}-mediaprobe-{pg}.png')
    except Exception as e: out['error'] = repr(e); print('ERROR', repr(e))
    measure.kill(binary)
    json.dump(out, open(f'{measure.RES}/{name}-mediaprobe.json', 'w'), ensure_ascii=False, indent=1)

if __name__ == '__main__': main()
