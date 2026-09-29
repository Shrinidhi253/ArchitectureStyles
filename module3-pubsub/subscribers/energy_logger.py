"""Subscriber (Feature 1 - YOU implement this): logs energy use per room.

Subscribes to   building/+/power      payload {"ts": iso-8601, "meter_id", "watts": float}
Writes          out/energy.csv        columns: room, kwh   (one row per room, rewritten on every update)

Energy is integrated over time: when a room reports P watts at time t2 and its
previous report was at time t1, add   P * (t2 - t1 in hours) / 1000   kWh.
The first report of a room contributes nothing (no interval yet).
Malformed payloads (missing fields, non-numeric watts, unparsable timestamp)
must be ignored - the logger must never crash.

No publisher needs to change for this feature: the power topic already exists.

    python -m subscribers.energy_logger
"""
from __future__ import annotations

import argparse
import threading
from datetime import datetime
from typing import Dict, Optional

from bus.client import BusClient


class EnergyAccumulator:
    """Pure logic, no networking."""

    def __init__(self) -> None:
        self.kwh: Dict[str, float] = {}
        self._last_ts: Dict[str, datetime] = {}

    def add(self, room: str, ts: str, watts: float) -> float:
        """Register one power report; return the room's total kWh (rounded to 4 decimals)."""
        raise NotImplementedError("TODO: implement EnergyAccumulator.add")

    def rows(self):
        """Yield (room, kwh) sorted by room."""
        raise NotImplementedError("TODO: implement EnergyAccumulator.rows")


class EnergyLogger:
    def __init__(self, client: BusClient, out_path: str = "out/energy.csv") -> None:
        self.client = client
        self.out_path = out_path
        self.acc = EnergyAccumulator()
        self._lock = threading.Lock()

    def start(self) -> None:
        raise NotImplementedError("TODO: subscribe to building/+/power")

    def on_power(self, topic: str, payload) -> None:
        raise NotImplementedError("TODO: parse room/ts/watts, update the accumulator, rewrite the CSV")

    def write_csv(self) -> None:
        raise NotImplementedError("TODO: write room,kwh rows to self.out_path")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=7883)
    ap.add_argument("--out", default="out/energy.csv")
    args = ap.parse_args()
    client = BusClient(port=args.port, name="energy_logger").connect()
    EnergyLogger(client, args.out).start()
    print("energy logger running (Ctrl-C to stop)")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        client.close()


if __name__ == "__main__":
    main()
