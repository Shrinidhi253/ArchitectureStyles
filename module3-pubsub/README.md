# Module 3 – Publish-Subscribe: building event bus

A tiny MQTT-style broker (`bus/broker.py`) is the event bus. Publishers and
subscribers know **topics only**; nobody knows who else is connected.

```
sensor_simulator ──pub──►                    ──sub──► dashboard        (building/#, alarm/#)
                          broker (7883)      ──sub──► alarm_monitor    (building/+/temperature, building/+/co2)
operator_console ──pub──►  topic routing     ──sub──► energy_logger    (building/+/power)      <- YOU
alarm_monitor    ──pub──►  (+ and # wildcards)
```

Topics: `building/<room>/temperature|co2|power`, `alarm/<room>`, `alarm/<room>/ack`.

## Run

```bash
pip install -r requirements.txt
python run_demo.py --rounds 30 --interval 0.5      # broker + monitor + simulator
python -m subscribers.dashboard                     # in a 2nd terminal
python -m publishers.operator_console B201 --by you # in a 3rd terminal (Feature 3)
```

Or start the pieces yourself: `python -m bus.broker`, `python -m subscribers.alarm_monitor`,
`python -m publishers.sensor_simulator`.

## Your task

* **Feature 1** – `subscribers/energy_logger.py` (new subscriber, no publisher changes).
* **Feature 2** – retained messages in `bus/broker.py` (two `TODO` markers).
* **Feature 3** – alarm acknowledgement in `subscribers/alarm_monitor.py` (three `TODO` markers).

Do not change `bus/client.py`, `bus/topics.py`, the publishers, or anything under
`tests/` (including `conftest.py`). In `bus/broker.py` fill in the two `TODO`
markers and leave the rest alone — in particular the observation methods
`subscription_count()`, `retained_snapshot()` and `stats`, which the tests use to
watch the broker without touching its private attributes. Feature 2 must keep the
`_retained` dict up to date; `retained_snapshot()` returns a copy of it.

## Test

```bash
python -m pytest -q             # starts a private broker on a free port
```

On the untouched starter: 6 pass, 13 fail. A complete solution passes all 19.

**No test in this module sleeps, and neither should yours.** Fixed sleeps are not
synchronisation — they are too short on a loaded CI runner, too slow everywhere
else, and they prove nothing when you are asserting that something did *not*
happen. `tests/conftest.py` provides the two patterns you need:

* `wait_for(predicate, what)` — poll until observable state holds; raises a
  readable error on timeout. Use it to wait for something to happen.
* `Sink.flush(publisher)` — publish a sentinel on a private topic and wait for it
  to come back. Messages travel in order over one connection, so once the
  sentinel has arrived, everything published earlier has already been delivered
  and handled. Use it to prove something did *not* happen.

If you cannot test a behaviour without sleeping, the component usually lacks an
observable state to wait on — that is a design problem, not a test problem
(Lecture 3: limit nondeterminism).
