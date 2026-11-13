"""標準ライブラリだけの WebSocket エコーサーバー(テキストの短いフレームのみ)。 ws://localhost:8001"""
import socket, hashlib, base64, threading, struct
def handle(c):
    try:
        req = b''
        while b'\r\n\r\n' not in req: req += c.recv(4096)
        key = [l.split(b': ')[1] for l in req.split(b'\r\n') if l.lower().startswith(b'sec-websocket-key')][0]
        acc = base64.b64encode(hashlib.sha1(key + b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest())
        c.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ' + acc + b'\r\n\r\n')
        while True:
            h = c.recv(2)
            if len(h) < 2 or (h[0] & 0xf) == 8: break
            n = h[1] & 0x7f
            if n == 126: n = struct.unpack('>H', c.recv(2))[0]
            mask = c.recv(4); d = b''
            while len(d) < n: d += c.recv(n - len(d))
            d = bytes(b ^ mask[i % 4] for i, b in enumerate(d))
            c.sendall(bytes([0x81, len(d)]) + d if len(d) < 126 else bytes([0x81, 126]) + struct.pack('>H', len(d)) + d)
    except Exception: pass
    finally: c.close()
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(('127.0.0.1', 8001)); s.listen(8)
while True:
    c, _ = s.accept(); threading.Thread(target=handle, args=(c,), daemon=True).start()
