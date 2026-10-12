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
import os
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
        current_ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        
        # Initializes the room if it's the first time we see it
        if room not in self.kwh:
            self.kwh[room] = 0.0
            
        # Calculates the time difference in hours, if we have a previous timestamp
        if room in self._last_ts:
            delta = current_ts - self._last_ts[room]
            hours = delta.total_seconds() / 3600.0
            
            # It only accumulates watts if time actually moved forward
            if hours > 0:
                self.kwh[room] += (watts * hours) / 1000.0
                
        # Updates the last seen timestamp for this room
        self._last_ts[room] = current_ts
        return round(self.kwh[room], 4)

    def rows(self):
        """Yield (room, kwh) sorted by room."""
        # Yield the items alphabetically by room name to satisfy the sorting requirement
        for room in sorted(self.kwh.keys()):
            yield room, round(self.kwh[room], 4)


class EnergyLogger:
    def __init__(self, client: BusClient, out_path: str = "out/energy.csv") -> None:
        self.client = client
        self.out_path = out_path
        self.acc = EnergyAccumulator()
        self._lock = threading.Lock()

    def start(self) -> None:
        # Subscribes using the topic building/+/power specified in the instructions
        self.client.subscribe("building/+/power", self.on_power)

    def on_power(self, topic: str, payload) -> None:
        # Ignores it if the payload is not a dictionary
        if not isinstance(payload, dict):
            return
        
        try:
            # Extracts the room from the topic
            room = topic.split("/")[1] # example: "building/D303/power" -> "D303"
            
            # Extract fields. KeyError is raised if anything is missing
            ts = payload["ts"]
            
            # Convert watts. ValueError is raised if it is a text instead of a number
            watts = float(payload["watts"])
            
            # Use the thread lock to prevent concurrent write issues 
            with self._lock:
                self.acc.add(room, ts, watts)
                self.write_csv()
                
        except (KeyError, ValueError, TypeError):
            # In case the payload is malformed, we pass, so we guarantee the logger never crashes as required
            pass

    def write_csv(self) -> None:
    # Ensures that the output directory exists before trying to write on it
        os.makedirs(os.path.dirname(self.out_path), exist_ok=True)
        
        with open(self.out_path, "w", encoding="utf-8") as f:
            f.write("room,kwh\n")
            # round() function implemented, since it automatically formats, for example, 1.5 instead of 1.5000 
            for room, kwh in self.acc.rows():
                f.write(f"{room},{kwh}\n")


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
