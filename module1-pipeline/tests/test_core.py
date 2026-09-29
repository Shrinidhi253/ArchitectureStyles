"""Tests of the provided framework - these must pass on the starter code."""
from pipeline.core import Filter, Pipeline
from pipeline.filters import ReadJsonl, ValidateRecord


class ListSource(Filter):
    name = "list_source"

    def __init__(self, records):
        super().__init__()
        self.records = records

    def produce(self):
        return list(self.records)


class Collect(Filter):
    name = "collect"

    def __init__(self):
        super().__init__()
        self.items = []

    def consume(self, record):
        self.items.append(record)


class Double(Filter):
    name = "double"

    def process(self, record):
        return [{**record, "value": record["value"] * 2}]


class Explode(Filter):
    name = "explode"

    def process(self, record):
        if record["value"] == 2:
            raise RuntimeError("boom")
        return [record]


def test_pipeline_passes_records_in_order():
    sink = Collect()
    Pipeline([ListSource([{"value": v} for v in (1, 2, 3)]), Double(), sink]).run()
    assert [r["value"] for r in sink.items] == [2, 4, 6]


def test_bad_record_is_dropped_not_fatal():
    sink = Collect()
    bad = Explode()
    Pipeline([ListSource([{"value": v} for v in (1, 2, 3)]), bad, sink]).run()
    assert [r["value"] for r in sink.items] == [1, 3]
    assert bad.error_count == 1


def test_validate_drops_malformed(tmp_path):
    src = tmp_path / "in.jsonl"
    src.write_text('{"ts":"t","device_id":"d","room":"r","type":"co2","value":5,"unit":"ppm"}\n'
                   '{"ts":"t","device_id":"d","room":"r","type":"co2","value":"x","unit":"ppm"}\n'
                   '{"ts":"t","device_id":"d","room":"r","type":"noise","value":5,"unit":"ppm"}\n'
                   '{"ts":"t"}\n'
                   'not json\n')
    sink = Collect()
    reader, validator = ReadJsonl(src), ValidateRecord()
    Pipeline([reader, validator, sink]).run()
    assert len(sink.items) == 1 and sink.items[0]["kind"] == "reading"
    assert validator.dropped == 3
    assert reader.error_count == 1
