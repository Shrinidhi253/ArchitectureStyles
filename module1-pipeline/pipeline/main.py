"""Command-line entry point.

    python -m pipeline.main data/readings.jsonl out/

Assembles the pipeline

    read_jsonl -> validate -> convert_units -> moving_average -> threshold_alarm -> write_jsonl

and prints a short run summary.
"""
from __future__ import annotations

import argparse
import time

from .core import Pipeline
from .filters import ReadJsonl, ValidateRecord, WriteJsonl
from .student_filters import ConvertUnits, MovingAverage, ThresholdAlarm


def build_pipeline(input_path: str, out_dir: str, window: int = 3) -> Pipeline:
    return Pipeline([
        ReadJsonl(input_path),
        ValidateRecord(),
        ConvertUnits(),
        MovingAverage(window=window),
        ThresholdAlarm(),
        WriteJsonl(out_dir),
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Sensor telemetry pipeline")
    parser.add_argument("input", help="JSON-lines file with raw readings")
    parser.add_argument("out_dir", help="directory for readings_clean.jsonl and alarms.jsonl")
    parser.add_argument("--window", type=int, default=3, help="moving-average window size")
    args = parser.parse_args()

    pipeline = build_pipeline(args.input, args.out_dir, args.window)
    print("Pipeline:", pipeline.describe())
    start = time.perf_counter()
    pipeline.run()
    elapsed = time.perf_counter() - start

    source, validator, *_, sink = pipeline.filters
    print(f"lines read     : {source.lines_read}")
    print(f"invalid dropped: {validator.dropped}")
    print(f"errors per stage: " + ", ".join(f"{f.name}={f.error_count}" for f in pipeline.filters))
    print(f"readings written: {sink.written['reading']}, alarms written: {sink.written['alarm']}")
    print(f"elapsed: {elapsed:.3f}s")


if __name__ == "__main__":
    main()
