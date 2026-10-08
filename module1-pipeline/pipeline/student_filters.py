"""Filters YOU implement for Module 1.

Rules (see the assignment description):
* Each filter is a self-contained class that extends ``Filter`` and only
  overrides the hooks ``process`` / ``finish``. It must not import or call any
  other filter, and must not touch files, sockets or global state.
* Do not use pandas/numpy or a one-line ``return [ ... ]`` trick; write the
  algorithm out explicitly so that your reasoning is visible.
* A filter must never crash the pipeline on a malformed record. Raise an
  exception for a record you cannot handle - the framework will drop it and
  count it in ``error_count`` - or return an empty list.

Reading record (after validation):
    {"ts": "...", "device_id": "t-101", "room": "A101",
     "type": "temperature" | "humidity" | "co2",
     "value": 71.6, "unit": "F" | "C" | "%" | "ppm", "kind": "reading"}
"""
from __future__ import annotations

from typing import Dict, Iterable, List

from .core import Filter, Record

# Alarm thresholds in the *canonical* units produced by ConvertUnits.
THRESHOLDS = {"temperature": 26.0,   # degrees C
              "humidity": 70.0,      # percent
              "co2": 1000.0}         # ppm
CRITICAL_FACTOR = 1.10               # > threshold * 1.10  => "critical", else "warning"


class ConvertUnits(Filter):
    """Filter 1 - normalise every reading to canonical units.

    * temperature given in Fahrenheit ("F") must be converted to Celsius
      ("C") with  C = (F - 32) * 5 / 9, rounded to 2 decimals.
    * Readings already in "C", "%" or "ppm" pass through unchanged.
    * Any other unit is an error: raise ``ValueError`` so the record is dropped.
    """

    name = "convert_units"

    def process(self, record: Record) -> Iterable[Record]:
      unit = record.get("unit")
      
      if unit in ("C", "%", "ppm"):
        return[record]
      
      if unit == "F":
        new_record = record.copy()
        celsius = (new_record["value"]- 32.0) * (5.0/9.0)
        new_record["value"] = round (celsius, 2)
        new_record["unit"] = "C"
        return [new_record]
      
      raise ValueError(f"Unknown unit: {unit}")
        
      
        
        #raise NotImplementedError("TODO: implement ConvertUnits.process")


class MovingAverage(Filter):
    """Filter 2 - smooth noisy readings with a per-device moving average.

    * Keep, for every ``device_id``, the last ``window`` values seen.
    * Emit a copy of the record where ``value`` is the arithmetic mean of the
      values currently in that device's window (rounded to 2 decimals), and
      the original value is preserved under ``raw_value``.
    * The first records of a device are averaged over the values available
      so far (window not yet full).
    """

    name = "moving_average"

    def __init__(self, window: int = 3) -> None:
        super().__init__()
        if window < 1:
            raise ValueError("window must be >= 1")
        self.window = window
        self._history: Dict[str, List[float]] = {}

    def process(self, record: Record) -> Iterable[Record]:
      new_record = record.copy()
      device_id = new_record["device_id"]
      current_value = float(new_record["value"])
      
      new_record["raw_value"]= new_record["value"]
      
      if device_id not in self._history:
        self._history[device_id] = []
        
      self._history[device_id].append(current_value)
      
      if len(self._history[device_id]) > self.window:
        self._history[device_id].pop(0)
        
      window_values = self._history[device_id]
      total_sum = 0.0
      for val in window_values:
        total_sum += val
      moving_average = total_sum / len(window_values)
      
      new_record["value"] = round(moving_average, 2)
      return [new_record]
    
    #raise NotImplementedError("TODO: implement MovingAverage.process")


class ThresholdAlarm(Filter):
    """Filter 3 - raise alarms for readings above their threshold.

    * Every reading passes through unchanged.
    * If ``value`` > THRESHOLDS[type], additionally emit an alarm record:
        {"kind": "alarm", "ts", "device_id", "room", "type", "value",
         "threshold": <float>, "severity": "warning" | "critical"}
      where severity is "critical" when value > threshold * CRITICAL_FACTOR.
    * Emit the reading first, then the alarm.
    """

    name = "threshold_alarm"

    def process(self, record: Record) -> Iterable[Record]:
        raise NotImplementedError("TODO: implement ThresholdAlarm.process")
