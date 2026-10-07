import json
import logging

import pytest

from src.logging_config import JsonFormatter
from src.timing import StageTimer, measure_turn


def test_nested_stages_share_turn_and_record_failures(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="jsm_voice"):
        with measure_turn() as measurements:
            with measure_turn() as nested:
                assert nested is measurements
                with StageTimer("standardization"):
                    pass
            with pytest.raises(RuntimeError):
                with StageTimer("asr"):
                    raise RuntimeError("private transcript must not be logged")
    assert set(measurements.durations_ms) == {"standardization", "asr"}
    records = [json.loads(JsonFormatter().format(record)) for record in caplog.records]
    assert all(record["turn_id"] == measurements.turn_id for record in records)
    assert records[-1]["success"] is False and records[-1]["error_type"] == "RuntimeError"
    assert "private transcript" not in json.dumps(records)


def test_turn_scopes_do_not_leak() -> None:
    with measure_turn() as first:
        pass
    with measure_turn() as second:
        pass
    assert first.turn_id != second.turn_id
