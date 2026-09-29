"""Regenerates data/readings.jsonl (deterministic). Run once; file is committed."""
import json
import random
from datetime import datetime, timedelta

random.seed(349)
rooms = {"A101": ("t-101", "h-101", "c-101"), "A102": ("t-102", "h-102", "c-102"),
         "B201": ("t-201", "h-201", "c-201")}
start = datetime(2026, 9, 1, 8, 0, 0)
lines = []
for i in range(120):
    ts = (start + timedelta(minutes=5 * i)).isoformat()
    for room, (t, h, c) in rooms.items():
        base_t = 21 + (6.5 if room == "B201" and 40 < i < 70 else 0) + (2.5 if room == "B201" and 55 < i < 60 else 0)  # B201 overheats
        temp_c = round(base_t + random.gauss(0, 0.6), 2)
        if t == "t-102":                                                       # legacy sensor in Fahrenheit
            lines.append({"ts": ts, "device_id": t, "room": room, "type": "temperature",
                          "value": round(temp_c * 9 / 5 + 32, 2), "unit": "F"})
        else:
            lines.append({"ts": ts, "device_id": t, "room": room, "type": "temperature",
                          "value": temp_c, "unit": "C"})
        hum = round(45 + (30 if room == "A101" and 90 < i < 100 else 0) + random.gauss(0, 2), 1)
        lines.append({"ts": ts, "device_id": h, "room": room, "type": "humidity",
                      "value": hum, "unit": "%"})
        co2 = int(550 + (600 if room == "A102" and 20 < i < 30 else 0) + random.gauss(0, 40))
        lines.append({"ts": ts, "device_id": c, "room": room, "type": "co2",
                      "value": co2, "unit": "ppm"})
    if i in (7, 33, 88):      # inject malformed rows the validator must drop
        lines.append({"ts": ts, "device_id": "x-999", "room": "Z", "type": "noise", "value": 1, "unit": "?"})
        lines.append({"ts": ts, "device_id": "t-101", "room": room, "type": "temperature", "value": "n/a", "unit": "C"})
    if i == 50:                # a reading in an unknown unit -> ConvertUnits must reject it
        lines.append({"ts": ts, "device_id": "t-301", "room": "C301", "type": "temperature", "value": 295.2, "unit": "K"})

with open("readings.jsonl", "w", encoding="utf-8") as fh:
    for k, rec in enumerate(lines):
        fh.write(json.dumps(rec) + "\n")
        if k == 200:
            fh.write("this line is not json\n")
print(len(lines), "records")
