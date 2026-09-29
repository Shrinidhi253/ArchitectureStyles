"""Core abstractions of the Pipe-and-Filter style.

Elements
--------
Pipe     : a bounded, thread-safe, unidirectional channel carrying records
           (plain ``dict`` objects) from exactly one producer to one consumer.
Filter   : an independent processing step. A filter never references another
           filter; it only reads from its input pipe and writes to its output
           pipe. Sub-classes implement ``process(record)`` (transformers),
           ``produce()`` (sources) or ``consume(record)`` (sinks).
Pipeline : wires filters together with pipes and runs them concurrently.

End-of-stream is signalled by the sentinel object ``END``.
"""
from __future__ import annotations

import queue
import threading
from abc import ABC
from typing import Any, Dict, Iterable, Iterator, List, Optional

Record = Dict[str, Any]

END = object()  # sentinel placed on a pipe when the producer is finished


class Pipe:
    """Unidirectional, point-to-point, bounded channel between two filters."""

    def __init__(self, capacity: int = 256) -> None:
        self._queue: "queue.Queue[Any]" = queue.Queue(maxsize=capacity)

    def put(self, record: Any) -> None:
        self._queue.put(record)

    def get(self) -> Any:
        return self._queue.get()

    def close(self) -> None:
        self._queue.put(END)

    def __iter__(self) -> Iterator[Record]:
        while True:
            item = self._queue.get()
            if item is END:
                return
            yield item


class Filter(ABC):
    """Base class for every processing step.

    A filter has at most one input pipe and one output pipe, both assigned by
    the Pipeline. It never calls another filter directly.
    """

    name: str = "filter"

    def __init__(self) -> None:
        self.inbox: Optional[Pipe] = None
        self.outbox: Optional[Pipe] = None
        self.error_count = 0

    # --- hooks -----------------------------------------------------------
    def produce(self) -> Iterable[Record]:
        """Source hook: yield records into the pipeline. Default: nothing."""
        return []

    def process(self, record: Record) -> Iterable[Record]:
        """Transformer hook: return zero or more records for one input."""
        return [record]

    def consume(self, record: Record) -> None:
        """Sink hook: handle a record that leaves the pipeline."""

    def finish(self) -> Iterable[Record]:
        """Called once after the input pipe is exhausted (flush state)."""
        return []

    # --- execution -------------------------------------------------------
    def emit(self, record: Record) -> None:
        if self.outbox is not None:
            self.outbox.put(record)

    def run(self) -> None:
        try:
            if self.inbox is None:                      # source
                for rec in self.produce():
                    self.emit(rec)
            else:                                       # transformer / sink
                for rec in self.inbox:
                    try:
                        if self.outbox is None:
                            self.consume(rec)
                        else:
                            for out in self.process(rec):
                                self.emit(out)
                    except Exception as exc:            # never let one bad record kill the stage
                        self.error_count += 1
                        self.on_error(rec, exc)
                for out in self.finish():
                    self.emit(out)
        finally:
            if self.outbox is not None:
                self.outbox.close()

    def on_error(self, record: Record, exc: Exception) -> None:
        print(f"[{self.name}] dropped record due to {type(exc).__name__}: {exc}")


class Pipeline:
    """Connects a linear sequence of filters with pipes and executes them."""

    def __init__(self, filters: List[Filter], capacity: int = 256) -> None:
        if len(filters) < 2:
            raise ValueError("A pipeline needs at least a source and a sink")
        self.filters = filters
        self.pipes: List[Pipe] = []
        for upstream, downstream in zip(filters, filters[1:]):
            pipe = Pipe(capacity)
            upstream.outbox = pipe
            downstream.inbox = pipe
            self.pipes.append(pipe)

    def run(self) -> None:
        threads = [threading.Thread(target=f.run, name=f.name, daemon=True)
                   for f in self.filters]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def describe(self) -> str:
        return " -> ".join(f.name for f in self.filters)
