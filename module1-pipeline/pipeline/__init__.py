"""Sensor telemetry processing pipeline (Pipe-and-Filter style).

A pipeline is a chain of *filters* connected by *pipes*. Each filter runs in
its own thread, reads records from its input pipe, transforms them, and writes
the results to its output pipe. Filters know nothing about their neighbours.
"""
