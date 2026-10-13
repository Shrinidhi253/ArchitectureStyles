"""A minimal publish-subscribe broker (the *event bus* of the style).

Clients connect over TCP and exchange newline-delimited JSON messages:

    client -> broker   {"op": "sub",   "topic": "building/+/temperature"}
                       {"op": "unsub", "topic": "..."}
                       {"op": "pub",   "topic": "building/A101/temperature",
                                       "payload": {...}, "retain": false}
    broker -> client   {"op": "msg",   "topic": "building/A101/temperature", "payload": {...}}

Publishers never learn who the subscribers are, and subscribers never learn
who published: all coupling is to *topics*. This is implicit invocation.

Run stand-alone:   python -m bus.broker --port 7883
"""
from __future__ import annotations

import argparse
import json
import socket
import threading
from typing import Dict, List, Set, Tuple

from .topics import matches, validate_publish_topic


class Broker:
    def __init__(self, host: str = "127.0.0.1", port: int = 7883) -> None:
        self.host, self.port = host, port
        self._server: socket.socket | None = None
        self._lock = threading.Lock()
        self._subscriptions: Dict[socket.socket, Set[str]] = {}   # client -> patterns
        self._retained: Dict[str, object] = {}                      # topic -> last retained payload
        self._send_lock = threading.Lock()   # keeps concurrent sends from interleaving
        self.stats = {"published": 0, "delivered": 0, "dropped": 0}
        self._stopping = threading.Event()

    # ------------------------------------------------------------ lifecycle
    def start(self) -> "Broker":
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self.host, self.port))
        self._server.listen()
        self.port = self._server.getsockname()[1]
        threading.Thread(target=self._accept_loop, name="broker-accept", daemon=True).start()
        return self

    def stop(self) -> None:
        self._stopping.set()
        if self._server:
            try:
                self._server.close()
            except OSError:
                pass
        with self._lock:
            for conn in list(self._subscriptions):
                try:
                    conn.close()
                except OSError:
                    pass
            self._subscriptions.clear()

    def serve_forever(self) -> None:
        try:
            self._stopping.wait()
        except KeyboardInterrupt:
            self.stop()

    # ------------------------------------------------------------ networking
    def _accept_loop(self) -> None:
        assert self._server is not None
        while not self._stopping.is_set():
            try:
                conn, _ = self._server.accept()
            except OSError:
                return
            with self._lock:
                self._subscriptions[conn] = set()
            threading.Thread(target=self._client_loop, args=(conn,), daemon=True).start()

    def _client_loop(self, conn: socket.socket) -> None:
        buffer = b""
        try:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line.strip():
                        self._handle(conn, line)
        except (ConnectionError, OSError):
            pass
        finally:
            with self._lock:
                self._subscriptions.pop(conn, None)
            try:
                conn.close()
            except OSError:
                pass

    def _handle(self, conn: socket.socket, raw: bytes) -> None:
        try:
            msg = json.loads(raw.decode("utf-8"))
            op = msg["op"]
        except (ValueError, KeyError, UnicodeDecodeError):
            self._send(conn, {"op": "error", "detail": "malformed message"})
            return
        if op == "sub":
            self._subscribe(conn, str(msg.get("topic", "")))
        elif op == "unsub":
            with self._lock:
                self._subscriptions.get(conn, set()).discard(str(msg.get("topic", "")))
        elif op == "pub":
            try:
                topic = str(msg["topic"])
                validate_publish_topic(topic)
            except (KeyError, ValueError) as exc:
                self._send(conn, {"op": "error", "detail": str(exc)})
                return
            self.publish(topic, msg.get("payload"), retain=bool(msg.get("retain", False)))
        else:
            self._send(conn, {"op": "error", "detail": f"unknown op {op!r}"})

    # ------------------------------------------------------------ pub / sub
    def _subscribe(self, conn: socket.socket, pattern: str) -> None:
        with self._lock:
            if conn in self._subscriptions:
                self._subscriptions[conn].add(pattern)
                # We make a copy of the retained items while under the lock to safely iterate over them on a list
            retained_items = list(self._retained.items())

        # (Feature 2 - retained messages): a subscriber that connects AFTER
        # a retained message was published must receive the last retained
        # payload of every topic that matches its new subscription.

        for topic, payload in retained_items:
            # To handle new subscriptions properly we use the provided 'matches' function
            if matches(pattern, topic):
                self._send(conn, {"op": "msg", "topic": topic, "payload": payload})

    def publish(self, topic: str, payload, retain: bool = False) -> int:
        """Deliver payload to every subscriber whose pattern matches. Returns #delivered."""
        with self._lock:
            self.stats["published"] += 1
        # (Feature 2 - retained messages): remember the last payload of
        # topics published with retain=True (an empty payload clears it).

            if retain:
                    if payload is None:
                        # If payload = None, remove the retained message if it exists
                        self._retained.pop(topic, None)
                    else:
                        # Otherwise, store or overwrite the retained payload for this topic with retain=True logic
                        self._retained[topic] = payload

        with self._lock:
            targets: List[Tuple[socket.socket, str]] = [
                (conn, pattern)
                for conn, patterns in self._subscriptions.items()
                for pattern in patterns if matches(pattern, topic)]
        delivered = dropped = 0
        seen: Set[socket.socket] = set()
        for conn, _ in targets:
            if conn in seen:
                continue                      # one delivery per client even if several patterns match
            seen.add(conn)
            if self._send(conn, {"op": "msg", "topic": topic, "payload": payload}):
                delivered += 1
            else:
                dropped += 1
        with self._lock:
            self.stats["delivered"] += delivered
            self.stats["dropped"] += dropped
        return delivered

    def _send(self, conn: socket.socket, msg: dict) -> bool:
        line = (json.dumps(msg) + "\n").encode("utf-8")
        with self._send_lock:        # two threads must never interleave one line
            try:
                conn.sendall(line)
                return True
            except OSError:
                return False

    # ------------------------------------------------------- observability
    # Provided so that tests (and you, while debugging) can observe the broker
    # without reaching into its private attributes. Tactic: specialized
    # interfaces / observability, Ch. 12.
    def subscription_count(self, pattern: str | None = None) -> int:
        """How many client subscriptions exist, in total or for one pattern."""
        with self._lock:
            if pattern is None:
                return sum(len(patterns) for patterns in self._subscriptions.values())
            return sum(1 for patterns in self._subscriptions.values() if pattern in patterns)

    def client_count(self) -> int:
        with self._lock:
            return len(self._subscriptions)

    def retained_snapshot(self) -> Dict[str, object]:
        """A copy of the retained store: topic -> last retained payload.

        Feature 2 must keep ``self._retained`` up to date; this method is what
        the tests read, so do not rename the attribute.
        """
        with self._lock:
            return dict(self._retained)


def main() -> None:
    ap = argparse.ArgumentParser(description="Tiny pub-sub broker")
    ap.add_argument("--port", type=int, default=7883)
    args = ap.parse_args()
    broker = Broker(port=args.port).start()
    print(f"broker listening on {broker.host}:{broker.port} (Ctrl-C to stop)")
    broker.serve_forever()


if __name__ == "__main__":
    main()
