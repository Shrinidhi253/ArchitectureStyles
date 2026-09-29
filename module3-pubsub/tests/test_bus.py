"""Tests of the provided bus - these pass on the starter code and must keep passing.

Read tests/conftest.py first: no test in Module 3 uses time.sleep, and neither
should any test you add.
"""
import threading

from bus.topics import matches

from .conftest import wait_for


def test_topic_matching():
    assert matches("building/A101/temperature", "building/A101/temperature")
    assert matches("building/+/temperature", "building/A101/temperature")
    assert not matches("building/+/temperature", "building/A101/co2")
    assert matches("building/#", "building/A101/co2")
    assert matches("#", "anything/at/all")
    assert not matches("building/+", "building/A101/co2")
    assert not matches("building/A101", "building/A101/co2")


def test_publish_reaches_matching_subscribers_only(make_client, make_sink):
    temp = make_sink("s1", "building/+/temperature")
    everything = make_sink("s2", "building/#")
    co2 = make_sink("s3", "building/+/co2")
    pub = make_client("pub")

    pub.publish("building/A101/temperature", {"value": 21.5})

    temp.wait_for_messages(1)
    everything.wait_for_messages(1)
    # The co2 sink must NOT receive it. Flushing proves the message is not
    # merely late: the sentinel was published after it and has already arrived.
    co2.flush(pub)

    assert temp.messages == [("building/A101/temperature", {"value": 21.5})]
    assert everything.messages == [("building/A101/temperature", {"value": 21.5})]
    assert co2.messages == []


def test_publisher_does_not_wait_for_subscribers(make_client, make_sink, broker):
    """Implicit invocation: publishing returns without the subscriber running."""
    entered, release = threading.Event(), threading.Event()
    slow = make_sink("slow")
    slow._subscribe("building/A101/temperature",
                    lambda t, p: (entered.set(), release.wait(5)))
    pub = make_client("pub")

    pub.publish("building/A101/temperature", {"value": 21.5})
    wait_for(entered.is_set, "the slow subscriber to start handling")

    # The subscriber is still inside its callback; the publisher is free to
    # continue. If publishing were coupled to delivery, this would block.
    published_before = broker.stats["published"]
    pub.publish("building/A101/temperature", {"value": 22.0})
    wait_for(lambda: broker.stats["published"] == published_before + 1,
             "the second publish to be accepted while the subscriber is blocked")
    release.set()


def test_publish_to_nobody_is_counted_but_not_delivered(make_client, broker):
    pub = make_client("pub")
    pub.publish("building/A101/temperature", {"value": 21.5})    # nobody listening
    wait_for(lambda: broker.stats["published"] == 1, "the publish to be recorded")
    assert broker.stats["delivered"] == 0


def test_bad_callback_does_not_kill_receiver(make_client, make_sink):
    got = []
    sub = make_sink("sub")
    pub = make_client("pub")

    def cb(topic, payload):
        got.append(payload)
        if payload == 1:
            raise RuntimeError("boom")
    sub._subscribe("x", cb)

    pub.publish("x", 1)
    pub.publish("x", 2)
    wait_for(lambda: got == [1, 2], "both messages despite the raising callback")


def test_malformed_message_gets_error_not_disconnect(make_client, broker):
    c = make_client("raw")
    c._sock.sendall(b"this is not json\n")
    c._send({"op": "pub", "topic": "building/#", "payload": 1})   # wildcard in publish topic
    c.publish("still/alive", {"ok": True})
    wait_for(lambda: broker.stats["published"] == 1,
             "the connection to survive two bad messages and accept a good one")
