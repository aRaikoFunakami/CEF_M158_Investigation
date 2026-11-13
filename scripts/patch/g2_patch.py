#!/usr/bin/env python3
"""g2_patch.py <src> : arm64 編 G2(Cobalt 由来の追加削減)のパッチ(冪等)。
enable_media_remoting=false(Cobalt の common.gn と同じ)を通すため、chrome 層で無条件に残っていた
CastRemotingConnector の参照 2 箇所を BUILDFLAG(ENABLE_MEDIA_REMOTING) で囲む(第 2 期 logs/191 でリンクに失敗した箇所)。
タブのミラーリング(Cast)自体は残るが、ミラーリング中のメディアリモーティング(動画だけを受信側で再生する最適化)がなくなる。"""
import sys
src = sys.argv[1]
def edit(path, fn):
    p = f'{src}/{path}'; s = open(p).read(); t = fn(s)
    if t != s: open(p, 'w').write(t); print('patched', path)
    else: print('unchanged', path)
def inc(s):
    if '#include "media/media_buildflags.h"' in s: return s
    a = '#include "chrome/browser/media/cast_remoting_connector.h"\n'
    assert s.count(a) == 1
    return s.replace(a, '#include "media/media_buildflags.h"\n#if BUILDFLAG(ENABLE_MEDIA_REMOTING)\n' + a + '#endif\n')

def mrd(s):
    s = inc(s)
    old = ('    // Ensure the CastRemotingConnector is created before mirroring starts.\n'
           '    CastRemotingConnector* const connector =\n'
           '        CastRemotingConnector::Get(web_contents);\n'
           '    connector->ResetRemotingPermission();\n')
    if 'FP: media remoting' in s: return s
    assert s.count(old) == 1
    return s.replace(old, '#if BUILDFLAG(ENABLE_MEDIA_REMOTING)  // FP: media remoting\n' + old + '#endif\n')
edit('chrome/browser/media/router/mojo/media_router_desktop.cc', mrd)

def cms(s):
    s = inc(s)
    old = ('      CastRemotingConnector::Get(source_contents)\n'
           '          ->ConnectWithMediaRemoter(std::move(remoter), std::move(receiver));\n')
    if 'FP: media remoting' in s: return s
    assert s.count(old) == 1
    return s.replace(old, '#if BUILDFLAG(ENABLE_MEDIA_REMOTING)  // FP: media remoting\n' + old + '#endif\n')
edit('chrome/browser/media/cast_mirroring_service_host.cc', cms)
