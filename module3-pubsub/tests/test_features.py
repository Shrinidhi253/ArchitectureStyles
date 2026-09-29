"""Feature tests for Module 3, Part 1. Expected to FAIL on the starter code.

These tests contain no time.sleep: see tests/conftest.py for wait_for() and
Sink.flush(), and use the same two tools in any test you write yourself.
"""
import csv

import pytest

from subscribers.alarm_monitor import ACKED, ALARM, NORMAL, AlarmMonitor, AlarmStateMachine
from subscribers.energy_logger import EnergyAccumulator, EnergyLogger

from .conftest import Sink, wait_for


# ---------------------------------------------------------------- Feature 1
class TestEnergyAccumulator:
    def test_first_report_contributes_nothing(self):
        acc = EnergyAccumulator()
        assert acc.add("A101", "2026-09-01T08:00:00", 1000.0) == 0.0

    def test_integration_over_time(self):
        acc = EnergyAccumulator()
        acc.add("A101", "2026-09-01T08:00:00", 1000.0)
        assert acc.add("A101", "2026-09-01T08:30:00", 1000.0) == pytest.approx(0.5)     # 1 kW for 30 min
        assert acc.add("A101", "2026-09-01T09:30:00", 500.0) == pytest.approx(1.0)      # + 0.5 kW for 1 h

    def test_rooms_are_independent(self):
        acc = EnergyAccumulator()
        acc.add("A101", "2026-09-01T08:00:00", 1000.0)
        acc.add("B201", "2026-09-01T08:00:00", 2000.0)
        acc.add("A101", "2026-09-01T09:00:00", 1000.0)
        acc.add("B201", "2026-09-01T09:00:00", 2000.0)
        assert dict(acc.rows()) == {"A101": pytest.approx(1.0), "B201": pytest.approx(2.0)}
        assert [r for r, _ in acc.rows()] == ["A101", "B201"]


def test_energy_logger_end_to_end(make_client, make_sink, broker, tmp_path):
    out = tmp_path / "energy.csv"
    sub, pub = make_client("energy"), make_client("pub")
    logger = EnergyLogger(sub, str(out))
    logger.start()
    wait_for(lambda: broker.subscription_count("building/+/power") == 1,
             "the logger to subscribe to building/+/power")
    # A sentinel on the logger's own connection: when it comes back, every
    # message published before it has already been handled by the logger.
    probe = Sink(sub, broker)

    pub.publish("building/A101/power", {"ts": "2026-09-01T08:00:00", "meter_id": "m", "watts": 1500})
    pub.publish("building/A101/power", {"ts": "garbage", "meter_id": "m", "watts": 1500})     # ignored
    pub.publish("building/A101/power", {"ts": "2026-09-01T08:20:00", "meter_id": "m"})        # ignored
    pub.publish("building/A101/temperature", {"ts": "2026-09-01T08:20:00", "value": 21})      # not subscribed
    pub.publish("building/A101/power", {"ts": "2026-09-01T09:00:00", "meter_id": "m", "watts": 1500})
    probe.flush(pub)

    assert out.exists(), "the logger must rewrite the CSV on every update"
    assert list(csv.DictReader(out.open())) == [{"room": "A101", "kwh": "1.5"}]


# ---------------------------------------------------------------- Feature 2
def test_retained_message_delivered_to_late_subscriber(make_client, make_sink, broker):
    pub = make_client("pub")
    pub.publish("building/A101/temperature", {"value": 21.0}, retain=True)
    pub.publish("building/A101/co2", {"value": 700}, retain=False)
    wait_for(lambda: broker.retained_snapshot() == {"building/A101/temperature": {"value": 21.0}},
             "exactly the retained topic to be stored (retain=False must not be stored)")

    late = make_sink("late", "building/A101/#")
    late.wait_for_messages(1)
    late.flush(pub)
    assert late.messages == [("building/A101/temperature", {"value": 21.0})]


def test_retained_keeps_only_last_value(make_client, make_sink, broker):
    pub = make_client("pub")
    pub.publish("building/B201/temperature", {"value": 20.0}, retain=True)
    pub.publish("building/B201/temperature", {"value": 25.0}, retain=True)
    # Wait for BOTH publishes, so that "only one value is retained" cannot pass
    # merely because the second message has not been processed yet.
    wait_for(lambda: broker.stats["published"] == 2, "both retained publishes")
    assert broker.retained_snapshot() == {"building/B201/temperature": {"value": 25.0}}

    late = make_sink("late", "building/+/temperature")
    late.wait_for_messages(1)
    late.flush(pub)
    assert late.payloads == [{"value": 25.0}], "only the last retained value, exactly once"


def test_retained_can_be_cleared(make_client, make_sink, broker):
    pub = make_client("pub")
    pub.publish("building/B201/temperature", {"value": 20.0}, retain=True)
    wait_for(lambda: "building/B201/temperature" in broker.retained_snapshot(),
             "the value to be retained before we clear it")

    pub.publish("building/B201/temperature", None, retain=True)      # empty payload clears
    wait_for(lambda: broker.retained_snapshot() == {}, "the retained value to be cleared")

    late = make_sink("late", "building/#")
    late.flush(pub)
    assert late.messages == [], "a cleared topic must not be replayed"


# ---------------------------------------------------------------- Feature 3
class TestAckStateMachine:
    def test_ack_moves_alarm_to_acked_and_silences(self):
        m = AlarmStateMachine()
        assert m.on_reading("B201", "temperature", 28.0, "t1")["severity"] == "warning"
        assert m.state[("B201", "temperature")] == ALARM
        assert m.on_ack("B201") == 1
        assert m.state[("B201", "temperature")] == ACKED
        assert m.on_reading("B201", "temperature", 29.0, "t2") is None       # silenced

    def test_ack_only_affects_that_room(self):
        m = AlarmStateMachine()
        m.on_reading("B201", "temperature", 28.0, "t")
        m.on_reading("A101", "co2", 1200.0, "t")
        assert m.on_ack("B201") == 1
        assert m.state[("A101", "co2")] == ALARM

    def test_ack_acknowledges_every_type_in_the_room(self):
        m = AlarmStateMachine()
        m.on_reading("B201", "temperature", 28.0, "t")
        m.on_reading("B201", "co2", 1200.0, "t")
        assert m.on_ack("B201") == 2
        assert m.state[("B201", "temperature")] == ACKED
        assert m.state[("B201", "co2")] == ACKED

    def test_ack_without_alarm_is_noop(self):
        m = AlarmStateMachine()
        assert m.on_ack("Z999") == 0
        m.on_reading("B201", "temperature", 20.0, "t")
        assert m.on_ack("B201") == 0

    def test_alarm_re_raised_after_recovery(self):
        m = AlarmStateMachine()
        m.on_reading("B201", "temperature", 28.0, "t")
        m.on_ack("B201")
        assert m.on_reading("B201", "temperature", 22.0, "t") is None
        assert m.state[("B201", "temperature")] == NORMAL
        assert m.on_reading("B201", "temperature", 28.0, "t") is not None


def test_ack_end_to_end(make_client, make_sink, broker):
    mon_client, pub = make_client("monitor"), make_client("pub")
    observer = make_sink("obs", "alarm/+")
    monitor = AlarmMonitor(mon_client)
    monitor.start()
    wait_for(lambda: broker.subscription_count("alarm/+/ack") == 1,
             "the monitor to subscribe to acknowledgements")
    monitor_probe = Sink(mon_client, broker)      # lets us flush the MONITOR's inbox

    pub.publish("building/B201/temperature", {"ts": "t1", "value": 28.0})
    observer.wait_for_messages(1)
    assert observer.topics == ["alarm/B201"]

    pub.publish("alarm/B201/ack", {"by": "kris", "ts": "t2"})
    monitor_probe.flush(pub)                      # the ack has been handled

    pub.publish("building/B201/temperature", {"ts": "t3", "value": 29.0})
    monitor_probe.flush(pub)                      # the reading has been handled
    observer.flush(pub)                           # any alarm it caused would be here by now
    assert len(observer.messages) == 1, "an acknowledged alarm must not be re-published"

    pub.publish("building/B201/temperature", {"ts": "t4", "value": 21.0})   # back to normal
    monitor_probe.flush(pub)
    pub.publish("building/B201/temperature", {"ts": "t5", "value": 28.0})   # rises again
    observer.wait_for_messages(2)
