"""Publisher: simulates the building's sensors.

Publishes, every ``--interval`` seconds and for ``--rounds`` rounds:
    building/<room>/temperature   {"ts", "device_id", "value", "unit": "C"}
    building/<room>/co2           {"ts", "device_id", "value", "unit": "ppm"}
    building/<room>/power         {"ts", "meter_id", "watts"}
Room B201 overheats in the middle of the run so alarms can be observed.

    python -m publishers.sensor_simulator --rounds 30 --interval 0.5
"""
from __future__ import annotations

import argparse
import random
import time
from datetime import datetime, timedelta, timezone

from bus.client import BusClient

ROOMS = ["A101", "A102", "B201"]


def make_readings(round_no: int, now: datetime, rng: random.Random):
    for room in ROOMS:
        hot = room == "B201" and 8 <= round_no <= 16
        temp = round((28.5 if hot else 21.0) + rng.gauss(0, 0.4), 2)
        co2 = int(600 + (500 if room == "A102" and round_no in (5, 6) else 0) + rng.gauss(0, 30))
        watts = round(400 + (900 if hot else 0) + rng.gauss(0, 25), 1)
        ts = now.isoformat(timespec="seconds")
        yield f"building/{room}/temperature", {"ts": ts, "device_id": f"t-{room}", "value": temp, "unit": "C"}
        yield f"building/{room}/co2", {"ts": ts, "device_id": f"c-{room}", "value": co2, "unit": "ppm"}
        yield f"building/{room}/power", {"ts": ts, "meter_id": f"m-{room}", "watts": watts}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=7883)
    ap.add_argument("--rounds", type=int, default=30)
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=349)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    client = BusClient(port=args.port, name="simulator").connect()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    try:
        for r in range(args.rounds):
            for topic, payload in make_readings(r, now, rng):
                client.publish(topic, payload)
            print(f"round {r + 1}/{args.rounds} published")
            now += timedelta(minutes=5)      # simulated clock: one round == 5 minutes
            time.sleep(args.interval)
    finally:
        client.close()


if __name__ == "__main__":
    main()
