"""Subscriber: prints the latest value of every building topic and every alarm.

    python -m subscribers.dashboard
"""
from __future__ import annotations

import argparse
import threading
import time

from bus.client import BusClient


class Dashboard:
    def __init__(self) -> None:
        self.latest = {}
        self.alarms = []
        self._lock = threading.Lock()

    def on_reading(self, topic: str, payload) -> None:
        with self._lock:
            self.latest[topic] = payload

    def on_alarm(self, topic: str, payload) -> None:
        with self._lock:
            self.alarms.append((topic, payload))

    def render(self) -> str:
        with self._lock:
            lines = ["=== latest readings ==="]
            for topic in sorted(self.latest):
                lines.append(f"{topic:32s} {self.latest[topic]}")
            lines.append(f"=== alarms ({len(self.alarms)}) ===")
            for topic, payload in self.alarms[-5:]:
                lines.append(f"{topic:32s} {payload}")
        return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=7883)
    ap.add_argument("--refresh", type=float, default=2.0)
    args = ap.parse_args()
    dash = Dashboard()
    client = BusClient(port=args.port, name="dashboard").connect()
    client.subscribe("building/#", dash.on_reading)
    client.subscribe("alarm/#", dash.on_alarm)
    try:
        while True:
            print("\033[2J\033[H" + dash.render())
            time.sleep(args.refresh)
    except KeyboardInterrupt:
        client.close()


if __name__ == "__main__":
    main()
