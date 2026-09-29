"""Subscriber + publisher: watches readings and raises alarms.

Subscribes to   building/+/temperature  and  building/+/co2
Publishes       alarm/<room>            {"type", "value", "threshold", "severity", "ts"}

Feature 3 (acknowledgement) is implemented in ``AlarmStateMachine``:
    NORMAL --(value > threshold)--> ALARM --(ack received)--> ACKED
    ALARM/ACKED --(value <= threshold)--> NORMAL
While ACKED no further alarm is published for that room+type, until the
value drops to normal and rises again.

    python -m subscribers.alarm_monitor
"""
from __future__ import annotations

import argparse
import threading
from typing import Dict, Optional, Tuple

from bus.client import BusClient

THRESHOLDS = {"temperature": 26.0, "co2": 1000.0}
CRITICAL_FACTOR = 1.10

NORMAL, ALARM, ACKED = "NORMAL", "ALARM", "ACKED"


class AlarmStateMachine:
    """Pure logic, no networking, so it can be unit-tested."""

    def __init__(self) -> None:
        self.state: Dict[Tuple[str, str], str] = {}    # (room, type) -> NORMAL | ALARM | ACKED

    def on_reading(self, room: str, rtype: str, value: float, ts: str) -> Optional[dict]:
        """Return an alarm payload to publish, or None."""
        threshold = THRESHOLDS.get(rtype)
        if threshold is None:
            return None
        key = (room, rtype)
        current = self.state.get(key, NORMAL)
        if value <= threshold:
            self.state[key] = NORMAL
            return None
        if current == ACKED:
            return None                                  # operator already knows
        self.state[key] = ALARM
        severity = "critical" if value > threshold * CRITICAL_FACTOR else "warning"
        return {"type": rtype, "value": value, "threshold": threshold, "severity": severity, "ts": ts}

    def on_ack(self, room: str) -> int:
        """Feature 3: acknowledge every active alarm of the room. Returns #acknowledged."""
        # TODO (Feature 3): move every (room, *) entry that is in state ALARM to ACKED
        # and return how many were acknowledged.
        raise NotImplementedError("TODO: implement AlarmStateMachine.on_ack")


class AlarmMonitor:
    def __init__(self, client: BusClient) -> None:
        self.client = client
        self.machine = AlarmStateMachine()
        self._lock = threading.Lock()
        self.published = 0

    def start(self) -> None:
        self.client.subscribe("building/+/temperature", self.on_reading)
        self.client.subscribe("building/+/co2", self.on_reading)
        # TODO (Feature 3): subscribe to acknowledgements  alarm/+/ack  -> self.on_ack

    def on_reading(self, topic: str, payload) -> None:
        try:
            _, room, rtype = topic.split("/")
            value = float(payload["value"])
            ts = str(payload.get("ts", ""))
        except (ValueError, KeyError, TypeError):
            print(f"[alarm_monitor] ignoring malformed message on {topic}: {payload!r}")
            return
        with self._lock:
            alarm = self.machine.on_reading(room, rtype, value, ts)
        if alarm:
            self.client.publish(f"alarm/{room}", alarm)
            self.published += 1
            print(f"[alarm_monitor] ALARM {room} {alarm}")

    def on_ack(self, topic: str, payload) -> None:
        # TODO (Feature 3): parse the room from the topic, call machine.on_ack(room)
        # under the lock and print a confirmation.
        raise NotImplementedError("TODO: implement AlarmMonitor.on_ack")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=7883)
    args = ap.parse_args()
    client = BusClient(port=args.port, name="alarm_monitor").connect()
    AlarmMonitor(client).start()
    print("alarm monitor running (Ctrl-C to stop)")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        client.close()


if __name__ == "__main__":
    main()
