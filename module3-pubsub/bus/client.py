"""Client library used by every publisher and subscriber.

    client = BusClient(port=7883).connect()
    client.subscribe("building/+/temperature", lambda topic, payload: print(topic, payload))
    client.publish("building/A101/temperature", {"value": 21.5, "unit": "C"})
    client.close()

Callbacks run on the client's receiver thread; keep them short.
"""
from __future__ import annotations

import json
import socket
import threading
from typing import Callable, Dict, List

from .topics import matches

Callback = Callable[[str, object], None]


class BusClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 7883, name: str = "client") -> None:
        self.host, self.port, self.name = host, port, name
        self._sock: socket.socket | None = None
        self._callbacks: Dict[str, List[Callback]] = {}
        self._lock = threading.Lock()
        self._closed = threading.Event()
        self.received = 0

    def connect(self) -> "BusClient":
        self._sock = socket.create_connection((self.host, self.port), timeout=5)
        self._sock.settimeout(None)
        threading.Thread(target=self._receive_loop, name=f"{self.name}-rx", daemon=True).start()
        return self

    def close(self) -> None:
        self._closed.set()
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._sock.close()

    def _send(self, msg: dict) -> None:
        assert self._sock is not None, "call connect() first"
        self._sock.sendall((json.dumps(msg) + "\n").encode("utf-8"))

    def publish(self, topic: str, payload, retain: bool = False) -> None:
        self._send({"op": "pub", "topic": topic, "payload": payload, "retain": retain})

    def subscribe(self, pattern: str, callback: Callback) -> None:
        with self._lock:
            self._callbacks.setdefault(pattern, []).append(callback)
        self._send({"op": "sub", "topic": pattern})

    def unsubscribe(self, pattern: str) -> None:
        with self._lock:
            self._callbacks.pop(pattern, None)
        self._send({"op": "unsub", "topic": pattern})

    def _receive_loop(self) -> None:
        assert self._sock is not None
        buffer = b""
        while not self._closed.is_set():
            try:
                chunk = self._sock.recv(4096)
            except OSError:
                break
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                self._dispatch(line)

    def _dispatch(self, line: bytes) -> None:
        try:
            msg = json.loads(line.decode("utf-8"))
        except ValueError:
            return
        if msg.get("op") == "error":
            print(f"[{self.name}] broker error: {msg.get('detail')}")
            return
        if msg.get("op") != "msg":
            return
        self.received += 1
        topic, payload = msg.get("topic", ""), msg.get("payload")
        with self._lock:
            handlers = [cb for pattern, cbs in self._callbacks.items() if matches(pattern, topic) for cb in cbs]
        for cb in handlers:
            try:
                cb(topic, payload)
            except Exception as exc:   # a faulty callback must not kill the receiver
                print(f"[{self.name}] callback error on {topic}: {type(exc).__name__}: {exc}")
