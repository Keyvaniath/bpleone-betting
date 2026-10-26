# Sandbox: no network, no sleeping (fetchers fail fast, backoffs cost nothing).
import socket, time
_orig = socket.socket.connect
def _deny(self, addr, *a, **k):
    raise ConnectionRefusedError("sandbox: network disabled")
socket.socket.connect = _deny
socket.socket.connect_ex = lambda self, addr: 111
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(ConnectionRefusedError("sandbox: network disabled"))
time.sleep = lambda s=0: None
