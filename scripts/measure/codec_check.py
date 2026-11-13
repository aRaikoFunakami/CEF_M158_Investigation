#!/usr/bin/env python3
"""コーデックと DRM の対応を実機で確認する。codec_check.py <name> <binary>"""
import sys, json, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure as m
name, binary = sys.argv[1], sys.argv[2]
p, c = m.launch(binary, 'http://localhost:8000/caps.html')
JS = '''(async()=>{const T=(t)=>MediaSource.isTypeSupported(t); const v=document.createElement('video');
const types={h264_main:'video/mp4; codecs="avc1.4d401f"',h264_high_1080p:'video/mp4; codecs="avc1.640028"',aac_lc:'audio/mp4; codecs="mp4a.40.2"',he_aac:'audio/mp4; codecs="mp4a.40.5"',
 vp9:'video/webm; codecs="vp09.00.40.08"',vp8:'video/webm; codecs="vp8"',av1:'video/mp4; codecs="av01.0.08M.08"',opus:'audio/webm; codecs="opus"',vorbis:'audio/webm; codecs="vorbis"',
 mp3:'audio/mpeg',flac:'audio/mp4; codecs="flac"',hevc:'video/mp4; codecs="hvc1.1.6.L120.90"',ac3:'audio/mp4; codecs="ac-3"',eac3:'audio/mp4; codecs="ec-3"',mpeg2ts:'video/mp2t; codecs="avc1.4d401f"'};
const r={mse:{},canPlay:{},eme:{}}; for(const k in types){r.mse[k]=T(types[k]); r.canPlay[k]=v.canPlayType(types[k]);}
const cfg=[{initDataTypes:['cenc'],videoCapabilities:[{contentType:'video/mp4; codecs="avc1.4d401f"'}],audioCapabilities:[{contentType:'audio/mp4; codecs="mp4a.40.2"'}]}];
for(const ks of ['org.w3.clearkey','com.widevine.alpha','com.microsoft.playready']){try{await navigator.requestMediaKeySystemAccess(ks,cfg); r.eme[ks]=true}catch(e){r.eme[ks]=e.name}}
return r})()'''
try:
    time.sleep(5); r = {'t5s': c.eval(JS)}
    time.sleep(90); r['widevine_after_95s'] = c.eval(JS)['eme']       # Widevine CDM はコンポーネント更新で後から入る場合がある
    m.yt_play(c); time.sleep(25)
    r['youtube'] = c.eval('''(()=>{const p=document.getElementById('movie_player'); const s=p&&p.getStatsForNerds?p.getStatsForNerds():null;
      return s?{codecs:s.codecs,resolution:s.resolution}:null})()''', await_promise=False)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    json.dump(r, open(f'{m.RES}/{name}-codecs.json', 'w'), ensure_ascii=False, indent=1)
finally:
    m.kill(binary)
os.system("ls -la /root/fp/profile/WidevineCdm 2>&1 | head -5")
