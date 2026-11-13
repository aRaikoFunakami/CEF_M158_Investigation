#!/usr/bin/env python3
"""停止検知つきビルドラッパー(コンテナ内で実行する)。

  fpbuild.py <src> <outdir> <target...> [--log FILE] [--stall SEC] [--retries N] [--nice N] [--keep-going]

autoninja(siso)を起動し、60 秒ごとに「進んでいるか」を判定する。
  進んでいる = ビルドログが伸びた、または siso とその子孫プロセスの CPU 時間が増えた
どちらも --stall 秒(既定 300)続けて動かなければ「停止」とみなし、siso を kill して再実行する
(siso は途中から再開する)。--retries 回(既定 5)まで。

背景: この環境(Apple Container + Rosetta)では siso spawn-helper の子プロセスがゾンビのまま
回収されず、siso 本体が何もせず待ち続ける停止が起きる(logs/113。logs/97 も同症状)。
ログの更新時刻だけで判定すると、出力なしで数分かかる LTO リンクを誤検知するため CPU 時間も見る。

状態は <log>.status に毎分 1 行で上書きする(STATE=RUNNING/STALLED/RETRY/OK/FAILED)。
停止を検知したら <log>.stalls に追記し、標準出力にも STALL_DETECTED を出す。
終了コード: 0=成功、1=ビルドエラー、3=停止が続いて諦めた。
"""
import sys, os, time, subprocess, signal, argparse, datetime

def now(): return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

def tree_cpu(root):
    """root とその子孫(ゾンビを除く)の CPU 時間合計(秒)と、生きているプロセス数。"""
    ppid, cpu, state, comm = {}, {}, {}, {}
    for d in os.listdir('/proc'):
        if not d.isdigit(): continue
        try:
            s = open(f'/proc/{d}/stat').read()
        except OSError:
            continue
        r = s.rsplit(')', 1)[1].split()          # r[0]=state r[1]=ppid r[11]=utime r[12]=stime
        pid = int(d); state[pid] = r[0]; ppid[pid] = int(r[1]); cpu[pid] = int(r[11]) + int(r[12])
        comm[pid] = s.split('(', 1)[1].rsplit(')', 1)[0]
    kids = {}
    for p, pp in ppid.items(): kids.setdefault(pp, []).append(p)
    live = 0; stack = [root]; zombies = 0; workers = {}
    while stack:
        p = stack.pop()
        if p in cpu:
            if state[p] == 'Z': zombies += 1
            else:
                live += 1
                # siso 本体は停止中も空回りで CPU を使う(logs/125 で 3 時間 45 分見逃した)。
                # 進捗の判定には、siso と起動ラッパー以外(clang、lld、python の各ステップ)だけを使う。
                if comm[p] not in WRAPPERS: workers[p] = cpu[p]
        stack.extend(kids.get(p, []))
    return workers, live, zombies

WRAPPERS = {'siso', 'ninja', 'autoninja', 'bash', 'nice'}
ROOT_PIDS = set()

def worker_progress(prev, cur):
    """作業プロセスが新しく現れたか、既存の作業プロセスの CPU 時間が増えたら True。"""
    hz = os.sysconf('SC_CLK_TCK')
    for p, c in cur.items():
        if p in ROOT_PIDS: continue
        if p not in prev or (c - prev[p]) / hz > 0.5: return True
    return False

def last_line(path):
    try:
        with open(path, 'rb') as f:
            f.seek(max(0, os.path.getsize(path) - 2000))
            t = f.read().decode('utf-8', 'replace').replace('\r', '\n').strip().split('\n')
        return t[-1][:160] if t else ''
    except OSError:
        return ''

def dump_diag(root, path, header):
    """停止した瞬間のプロセス木とスレッドの状態を残す(原因調査用)。"""
    try:
        out = subprocess.run(['ps', '-eLo', 'pid,ppid,lwp,stat,wchan:24,etime,time,comm'], capture_output=True, text=True).stdout
        with open(path, 'a') as f:
            f.write('##### ' + header + '\n' + out + '\n')
            for d in os.listdir('/proc'):
                if not d.isdigit(): continue
                try:
                    if open(f'/proc/{d}/comm').read().strip() != 'siso': continue
                    f.write(f'--- /proc/{d} cmdline: ' + open(f'/proc/{d}/cmdline').read().replace('\0', ' ') + '\n')
                    for t in os.listdir(f'/proc/{d}/task'):
                        try: f.write(f'  tid {t} syscall: ' + open(f'/proc/{d}/task/{t}/syscall').read())
                        except OSError as e: f.write(f'  tid {t} syscall: {e}\n')
                    f.write('  fds: ' + ' '.join(f'{x}->{os.readlink(f"/proc/{d}/fd/{x}")}' for x in os.listdir(f'/proc/{d}/fd')) + '\n')
                except OSError:
                    pass
    except Exception as e:
        print('fpbuild: diag failed', e, flush=True)

def kill_tree(p):
    try: os.killpg(p.pid, signal.SIGTERM)
    except OSError: pass
    for _ in range(20):
        if p.poll() is not None: break
        time.sleep(1)
    try: os.killpg(p.pid, signal.SIGKILL)
    except OSError: pass
    p.wait()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('outdir'); ap.add_argument('targets', nargs='+')
    ap.add_argument('--log'); ap.add_argument('--stall', type=int, default=300)
    ap.add_argument('--retries', type=int, default=5); ap.add_argument('--nice', type=int, default=0)
    ap.add_argument('--keep-going', action='store_true')
    a = ap.parse_args()
    log = a.log or f'/root/fp/build-{os.path.basename(a.outdir)}.txt'
    status, stalls = log + '.status', log + '.stalls'
    env = dict(os.environ, HOME='/root', DEPOT_TOOLS_UPDATE='0', GCLIENT_SUPPRESS_GIT_VERSION_WARNING='1')
    env['PATH'] = env.get('PATH', '') + ':/root/depot_tools'
    cmd = (['nice', '-n', str(a.nice)] if a.nice else []) + ['autoninja'] + (['-k', '0'] if a.keep_going else []) + ['-C', a.outdir] + a.targets
    open(log, 'w').close()
    if os.path.exists(stalls): os.remove(stalls)
    t_start = time.time(); nstall = 0

    def put_status(state, extra=''):
        line = f'STATE={state} time="{now()}" elapsed={int(time.time() - t_start)}s attempt={attempt} stalls={nstall} {extra}'
        with open(status + '.tmp', 'w') as f: f.write(line + '\n')
        os.replace(status + '.tmp', status)

    for attempt in range(1, a.retries + 2):
        with open(log, 'ab') as lf:
            lf.write(f'\n##### fpbuild attempt {attempt} {now()} : {" ".join(cmd)}\n'.encode()); lf.flush()
            p = subprocess.Popen(cmd, cwd=a.src, env=env, stdout=lf, stderr=subprocess.STDOUT, start_new_session=True)
        print(f'fpbuild: attempt {attempt} started {now()} pid={p.pid}', flush=True)
        last_size = os.path.getsize(log); t_progress = time.time(); stalled = False
        time.sleep(5)
        last_w, _, _ = tree_cpu(p.pid)
        ROOT_PIDS.clear(); ROOT_PIDS.update(last_w)   # autoninja.py の python など、常駐する起動ラッパー
        while p.poll() is None:
            time.sleep(60)
            size = os.path.getsize(log); w, live, zomb = tree_cpu(p.pid)
            if size != last_size or worker_progress(last_w, w):
                t_progress = time.time()
            idle = int(time.time() - t_progress)
            last_size, last_w = size, w
            put_status('RUNNING', f'idle={idle}s live_procs={live} zombies={zomb} last="{last_line(log)}"')
            if idle >= a.stall and p.poll() is None:
                nstall += 1; stalled = True
                msg = f'STALL_DETECTED {now()} attempt={attempt} idle={idle}s live_procs={live} zombies={zomb} last="{last_line(log)}"'
                print(msg, flush=True)
                with open(stalls, 'a') as f: f.write(msg + '\n')
                put_status('STALLED', f'idle={idle}s')
                dump_diag(p.pid, stalls + '.diag', msg)
                kill_tree(p)
                break
        if stalled:
            if attempt > a.retries:
                put_status('FAILED', 'reason=stall-retries-exhausted'); print('fpbuild: giving up (stalls)', flush=True); return 3
            put_status('RETRY'); continue
        rc = p.returncode
        dt = int(time.time() - t_start)
        if rc == 0:
            put_status('OK', f'rc=0'); print(f'fpbuild: OK rc=0 elapsed={dt}s stalls={nstall}', flush=True); return 0
        put_status('FAILED', f'rc={rc}'); print(f'fpbuild: build error rc={rc} elapsed={dt}s stalls={nstall}', flush=True); return 1

if __name__ == '__main__':
    sys.exit(main())
