"""標準ライブラリだけで書いた最小の Chrome DevTools Protocol クライアント。"""
import socket, os, base64, json, struct, urllib.request, time

class WS:
    def __init__(self, url):
        hp, path = url[5:].split('/', 1); host, port = hp.split(':')
        self.s = socket.create_connection((host, int(port)), timeout=120)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET /{path} HTTP/1.1\r\nHost: {hp}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b''
        while b'\r\n\r\n' not in buf: buf += self.s.recv(4096)
        self.buf = buf.split(b'\r\n\r\n', 1)[1]
    def send(self, text):
        d = text.encode(); n = len(d); mask = os.urandom(4); h = b'\x81'
        if n < 126: h += bytes([0x80 | n])
        elif n < 65536: h += bytes([0x80 | 126]) + struct.pack('>H', n)
        else: h += bytes([0x80 | 127]) + struct.pack('>Q', n)
        self.s.sendall(h + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(d)))
    def _read(self, n):
        while len(self.buf) < n:
            c = self.s.recv(1 << 16)
            if not c: raise EOFError
            self.buf += c
        r = self.buf[:n]; self.buf = self.buf[n:]; return r
    def recv(self):
        data = b''
        while True:
            b0, b1 = self._read(2); op = b0 & 0xf; n = b1 & 0x7f
            if n == 126: n = struct.unpack('>H', self._read(2))[0]
            elif n == 127: n = struct.unpack('>Q', self._read(8))[0]
            p = self._read(n)
            if op == 8: raise EOFError
            if op in (9, 10): continue
            data += p
            if b0 & 0x80: return data.decode('utf8', 'replace')

class CDP:
    def __init__(self, port=9222, wait=60):
        t0 = time.time(); last = None
        while time.time() - t0 < wait:
            try:
                tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json', timeout=5))
                pages = [t for t in tabs if t.get('type') == 'page']
                if pages:
                    self.ws = WS(pages[0]['webSocketDebuggerUrl']); self.id = 0; return
            except Exception as e: last = e
            time.sleep(1)
        raise RuntimeError(f'CDP に接続できない: {last}')
    def call(self, method, **params):
        self.id += 1; i = self.id
        self.ws.send(json.dumps({'id': i, 'method': method, 'params': params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get('id') == i:
                if 'error' in m: raise RuntimeError(f"{method}: {m['error']}")
                return m.get('result', {})
    def navigate(self, url): return self.call('Page.navigate', url=url)
    def eval(self, expr, await_promise=True):
        r = self.call('Runtime.evaluate', expression=expr, awaitPromise=await_promise, returnByValue=True)
        if 'exceptionDetails' in r: return {'__exception': r['exceptionDetails'].get('exception', {}).get('description', str(r['exceptionDetails']))[:300]}
        return r.get('result', {}).get('value')
    def screenshot(self, path):
        r = self.call('Page.captureScreenshot', format='png')
        open(path, 'wb').write(base64.b64decode(r['data']))
