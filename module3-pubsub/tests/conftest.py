"""Fixtures and synchronisation helpers for the Module 3 tests.

Why there is not a single ``time.sleep`` in this test suite
-----------------------------------------------------------
The bus is concurrent: publishers, the broker and every subscriber run on
different threads, so a message takes an unknown amount of time to travel.
The tempting fix is ``time.sleep(0.1)`` after each publish. Do not do it:

* too short on a loaded CI runner  -> the test fails although the code is fine
  (a flaky test, which teaches everyone to ignore red pipelines);
* too long                         -> the suite crawls;
* it proves nothing at all when you are asserting that something did *not*
  happen, because "it has not arrived yet" and "it will never arrive" look
  exactly the same after any finite sleep.

This file gives you two tools instead, both of which wait for *observed state*:

``wait_for(predicate, what)``
    Polls until the predicate holds and raises with a readable message on
    timeout. Use it when you are waiting for something to happen.

``Sink.flush(publisher)``
    Publishes a sentinel message to the sink's own private topic and waits for
    it to come back. Messages travel in order over one connection, so once the
    sentinel has been delivered to that client, every message published to it
    earlier has already been delivered and its callback has already run.
    Use it when you are asserting that something did *not* happen.

The same reasoning applies to your own code: a subscriber that "works if you
wait a moment" is a subscriber whose behaviour you cannot test.
"""
from __future__ import annotations

import itertools
import time

import pytest

from bus.broker import Broker
from bus.client import BusClient

TIMEOUT = 5.0          # generous: only reached when the test is genuinely failing
POLL = 0.002


def wait_for(predicate, what="condition", timeout=TIMEOUT):
    """Wait until predicate() is true. Raise AssertionError on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(POLL)
    raise AssertionError(f"timed out after {timeout:g}s waiting for {what}")


@pytest.fixture
def broker():
    b = Broker(port=0).start()      # port 0 = pick a free port
    yield b
    b.stop()


@pytest.fixture
def make_client(broker):
    clients = []

    def _make(name="c"):
        c = BusClient(port=broker.port, name=name).connect()
        clients.append(c)
        return c
    yield _make
    for c in clients:
        c.close()


class Sink:
    """A test subscriber that records what it receives and can be flushed.

    ``Sink(client, broker)`` also subscribes the client to a private sentinel
    topic, which is what :meth:`flush` uses.
    """

    _ids = itertools.count()

    def __init__(self, client, broker):
        self.client, self.broker = client, broker
        self.messages = []                       # list of (topic, payload)
        self._sentinel_topic = f"test-sentinel/{next(Sink._ids)}"
        self._sentinels = []
        self._subscribe(self._sentinel_topic, lambda t, p: self._sentinels.append(p))

    def _subscribe(self, pattern, callback):
        before = self.broker.subscription_count(pattern)
        self.client.subscribe(pattern, callback)
        # subscribe() is asynchronous: wait until the BROKER has registered it,
        # otherwise a publish that follows can legitimately miss this subscriber.
        wait_for(lambda: self.broker.subscription_count(pattern) > before,
                 f"broker to register subscription {pattern!r}")

    def subscribe(self, pattern):
        self._subscribe(pattern, lambda t, p: self.messages.append((t, p)))
        return self

    def flush(self, publisher):
        """Round-trip a sentinel through the broker to this client."""
        seen = len(self._sentinels)
        publisher.publish(self._sentinel_topic, "ping")
        wait_for(lambda: len(self._sentinels) > seen,
                 f"sentinel on {self._sentinel_topic} to come back")

    def wait_for_messages(self, count):
        wait_for(lambda: len(self.messages) >= count,
                 f"{count} message(s) on client {self.client.name!r} "
                 f"(have {len(self.messages)})")

    @property
    def topics(self):
        return [t for t, _ in self.messages]

    @property
    def payloads(self):
        return [p for _, p in self.messages]


@pytest.fixture
def make_sink(make_client, broker):
    """make_sink("dashboard", "building/#") -> a connected, subscribed Sink."""
    def _make(name="sink", *patterns):
        sink = Sink(make_client(name), broker)
        for pattern in patterns:
            sink.subscribe(pattern)
        return sink
    return _make
