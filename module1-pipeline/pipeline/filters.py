"""Provided filters: the source, the validator and the sink.

You do NOT need to change this file. Study it to see how a filter is written,
then implement your own filters in ``student_filters.py``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .core import Filter, Record

READING_TYPES = {"temperature", "humidity", "co2"}
REQUIRED_FIELDS = ("ts", "device_id", "room", "type", "value", "unit")


class ReadJsonl(Filter):
    """Source: reads one JSON object per line from a file."""

    name = "read_jsonl"

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.path = Path(path)
        self.lines_read = 0

    def produce(self) -> Iterable[Record]:
        with self.path.open(encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                self.lines_read += 1
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    self.error_count += 1
                    print(f"[{self.name}] line {line_no} is not valid JSON: {exc}")


class ValidateRecord(Filter):
    """Transformer: drops records that do not match the reading schema."""

    name = "validate"

    def __init__(self) -> None:
        super().__init__()
        self.dropped = 0

    def process(self, record: Record) -> Iterable[Record]:
        for field in REQUIRED_FIELDS:
            if field not in record:
                self.dropped += 1
                return []
        if record["type"] not in READING_TYPES:
            self.dropped += 1
            return []
        if not isinstance(record["value"], (int, float)) or isinstance(record["value"], bool):
            self.dropped += 1
            return []
        clean = dict(record)
        clean["kind"] = "reading"
        return [clean]


class WriteJsonl(Filter):
    """Sink: routes readings and alarms to two output files."""

    name = "write_jsonl"

    def __init__(self, out_dir: str | Path) -> None:
        super().__init__()
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.readings_path = self.out_dir / "readings_clean.jsonl"
        self.alarms_path = self.out_dir / "alarms.jsonl"
        self._readings = self.readings_path.open("w", encoding="utf-8")
        self._alarms = self.alarms_path.open("w", encoding="utf-8")
        self.written = {"reading": 0, "alarm": 0}

    def consume(self, record: Record) -> None:
        target = self._alarms if record.get("kind") == "alarm" else self._readings
        target.write(json.dumps(record, sort_keys=True) + "\n")
        self.written["alarm" if target is self._alarms else "reading"] += 1

    def run(self) -> None:
        try:
            super().run()
        finally:
            self._readings.close()
            self._alarms.close()
