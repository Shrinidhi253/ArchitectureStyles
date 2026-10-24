# Module 1 – Pipe-and-Filter: sensor telemetry pipeline

Raw sensor readings from a building (JSON-lines) flow through a chain of
independent filters connected by pipes:

```
read_jsonl -> validate -> convert_units -> moving_average -> threshold_alarm -> write_jsonl
  (given)     (given)      (YOU)            (YOU)            (YOU)             (given)
```

Every filter runs in its own thread and communicates **only** through its
input and output pipe (`pipeline/core.py`). Filters never call each other.

## UML component diagram of the pipeline
![Pipe-and-filter UML diagram](/diagrams/pipe-and-filter-diagram.jpg)

## Run

```bash
pip install -r requirements.txt
python -m pipeline.main data/readings.jsonl out/
```

Outputs: `out/readings_clean.jsonl` (normalised, smoothed readings) and
`out/alarms.jsonl` (threshold violations).

## Your task

Implement the three classes in `pipeline/student_filters.py`. The docstring of
each class is the specification. Do not modify `core.py`, `filters.py`,
`main.py`, the data or the tests.

## Test

```bash
python -m pytest -q            # all tests
python -m pytest -q tests/test_core.py   # framework only (passes on the starter)
```
