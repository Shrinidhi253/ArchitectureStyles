"""Tests of the three filters implemented by students (Module 1, Part 1).

They are expected to FAIL on the untouched starter code and PASS when the
filters are implemented correctly.
"""
import inspect
import json

import pytest

from pipeline.core import Filter, Pipeline
from pipeline.main import build_pipeline
from pipeline.student_filters import (CRITICAL_FACTOR, THRESHOLDS, ConvertUnits,
                                      MovingAverage, ThresholdAlarm)

from .test_core import Collect, ListSource


def reading(device="t-1", rtype="temperature", value=20.0, unit="C", ts="2026-09-01T08:00:00", room="A101"):
    return {"ts": ts, "device_id": device, "room": room, "type": rtype,
            "value": value, "unit": unit, "kind": "reading"}


def run_single(filter_obj: Filter, records):
    sink = Collect()
    Pipeline([ListSource(records), filter_obj, sink]).run()
    return sink.items


# ---------------------------------------------------------------- Filter 1
class TestConvertUnits:
    def test_fahrenheit_to_celsius(self):
        out = run_single(ConvertUnits(), [reading(value=71.6, unit="F")])
        assert len(out) == 1
        assert out[0]["unit"] == "C"
        assert out[0]["value"] == pytest.approx(22.0, abs=0.01)

    def test_freezing_point(self):
        out = run_single(ConvertUnits(), [reading(value=32, unit="F")])
        assert out[0]["value"] == pytest.approx(0.0, abs=0.01)

    def test_canonical_units_untouched(self):
        recs = [reading(value=21.5, unit="C"), reading(rtype="humidity", value=40, unit="%"),
                reading(rtype="co2", value=600, unit="ppm")]
        out = run_single(ConvertUnits(), recs)
        assert out == recs

    def test_unknown_unit_is_dropped_without_crash(self):
        f = ConvertUnits()
        out = run_single(f, [reading(value=295.0, unit="K"), reading(value=20, unit="C")])
        assert len(out) == 1 and out[0]["value"] == 20
        assert f.error_count == 1

    def test_input_record_not_mutated(self):
        rec = reading(value=50.0, unit="F")
        run_single(ConvertUnits(), [rec])
        assert rec["unit"] == "F" and rec["value"] == 50.0


# ---------------------------------------------------------------- Filter 2
class TestMovingAverage:
    def test_average_over_window(self):
        recs = [reading(value=v) for v in (10, 20, 30, 40)]
        out = run_single(MovingAverage(window=3), recs)
        assert [r["value"] for r in out] == [10.0, 15.0, 20.0, 30.0]
        assert [r["raw_value"] for r in out] == [10, 20, 30, 40]

    def test_windows_are_per_device(self):
        recs = [reading(device="a", value=10), reading(device="b", value=100),
                reading(device="a", value=20), reading(device="b", value=200)]
        out = run_single(MovingAverage(window=2), recs)
        assert [r["value"] for r in out] == [10.0, 100.0, 15.0, 150.0]

    def test_window_of_one_is_identity(self):
        recs = [reading(value=v) for v in (3, 5, 7)]
        out = run_single(MovingAverage(window=1), recs)
        assert [r["value"] for r in out] == [3.0, 5.0, 7.0]

    def test_rounding_two_decimals(self):
        out = run_single(MovingAverage(window=3), [reading(value=v) for v in (1, 2, 2)])
        assert out[-1]["value"] == 1.67

    def test_other_fields_preserved(self):
        out = run_single(MovingAverage(window=3), [reading(value=5, room="B7")])
        assert out[0]["room"] == "B7" and out[0]["unit"] == "C" and out[0]["kind"] == "reading"


# ---------------------------------------------------------------- Filter 3
class TestThresholdAlarm:
    def test_no_alarm_below_threshold(self):
        out = run_single(ThresholdAlarm(), [reading(value=THRESHOLDS["temperature"])])
        assert len(out) == 1 and out[0]["kind"] == "reading"

    def test_warning_alarm(self):
        out = run_single(ThresholdAlarm(), [reading(value=27.0)])
        assert [r["kind"] for r in out] == ["reading", "alarm"]
        alarm = out[1]
        assert alarm["severity"] == "warning"
        assert alarm["threshold"] == THRESHOLDS["temperature"]
        assert alarm["value"] == 27.0 and alarm["room"] == "A101" and alarm["device_id"] == "t-1"

    def test_critical_alarm(self):
        value = THRESHOLDS["co2"] * CRITICAL_FACTOR + 1
        out = run_single(ThresholdAlarm(), [reading(rtype="co2", value=value, unit="ppm")])
        assert out[1]["severity"] == "critical"

    def test_boundary_is_warning_not_critical(self):
        value = round(THRESHOLDS["humidity"] * CRITICAL_FACTOR, 2)
        out = run_single(ThresholdAlarm(), [reading(rtype="humidity", value=value, unit="%")])
        assert out[1]["severity"] == "warning"

    def test_reading_passes_through_unchanged(self):
        rec = reading(value=30.0)
        out = run_single(ThresholdAlarm(), [rec])
        assert out[0] == rec


# ---------------------------------------------------------------- Whole pipeline
def test_end_to_end_on_sample_data(tmp_path):
    p = build_pipeline("data/readings.jsonl", tmp_path, window=3)
    p.run()
    readings = [json.loads(l) for l in (tmp_path / "readings_clean.jsonl").read_text().splitlines()]
    alarms = [json.loads(l) for l in (tmp_path / "alarms.jsonl").read_text().splitlines()]
    assert len(readings) == 1080
    assert {r["unit"] for r in readings} == {"C", "%", "ppm"}
    assert len(alarms) == 41
    assert {a["room"] for a in alarms} == {"A101", "A102", "B201"}
    assert sum(1 for a in alarms if a["severity"] == "critical") == 11
    # the Kelvin reading must be dropped by ConvertUnits, not crash the stage
    assert p.filters[2].error_count == 1


# ---------------------------------------------------------------- Style checks
@pytest.mark.parametrize("cls", [ConvertUnits, MovingAverage, ThresholdAlarm])
def test_filters_do_not_reference_each_other(cls):
    """A filter must be independent: no other filter class may appear in its source."""
    src = inspect.getsource(cls)
    others = {ConvertUnits, MovingAverage, ThresholdAlarm} - {cls}
    for other in others:
        assert other.__name__ not in src, f"{cls.__name__} references {other.__name__}"


@pytest.mark.parametrize("cls", [ConvertUnits, MovingAverage, ThresholdAlarm])
def test_no_forbidden_libraries(cls):
    src = inspect.getsource(cls).lower()
    for lib in ("pandas", "numpy", "statistics"):
        assert lib not in src, f"{cls.__name__} must not use {lib}"
