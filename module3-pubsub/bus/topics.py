"""MQTT-style topic matching used by the broker.

A topic is a slash-separated path such as ``building/A101/temperature``.
A *filter* (subscription pattern) may contain the wildcards
    ``+``  matches exactly one level      (building/+/temperature)
    ``#``  matches all remaining levels   (building/#) - only as the last level
"""
from __future__ import annotations


def matches(pattern: str, topic: str) -> bool:
    p_levels = pattern.split("/")
    t_levels = topic.split("/")
    for i, p in enumerate(p_levels):
        if p == "#":
            return i == len(p_levels) - 1
        if i >= len(t_levels):
            return False
        if p != "+" and p != t_levels[i]:
            return False
    return len(p_levels) == len(t_levels)


def validate_publish_topic(topic: str) -> None:
    if not topic or "+" in topic or "#" in topic:
        raise ValueError(f"invalid publish topic {topic!r}")
