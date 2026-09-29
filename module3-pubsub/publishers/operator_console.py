"""Publisher: an operator acknowledges an alarm for a room (Feature 3).

    python -m publishers.operator_console B201 --by kris

Publishes   alarm/<room>/ack   {"by": "<operator>", "ts": "<iso>"}
The console does not know which component handles the acknowledgement.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from bus.client import BusClient


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("room")
    ap.add_argument("--by", default="operator")
    ap.add_argument("--port", type=int, default=7883)
    args = ap.parse_args()
    client = BusClient(port=args.port, name="console").connect()
    client.publish(f"alarm/{args.room}/ack", {"by": args.by, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    print(f"acknowledged alarms for {args.room}")
    client.close()


if __name__ == "__main__":
    main()
