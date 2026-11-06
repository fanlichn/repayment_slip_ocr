from __future__ import annotations

import logging

from app.ocr_engine import _TimedPredictorProxy
from app.stage_timing import operation, request_timing, stage


def test_stage_timing_is_log_only_and_request_scoped(caplog):
    caplog.set_level(logging.INFO, logger="repayment_ocr.timing")

    with request_timing(True, service="repayment", route="ocr_url", request_id="abc"):
        with operation("primary:color"):
            with stage("image_decode", image_bytes=123):
                pass

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "req=abc" in message
        and "phase=image_decode" in message
        and "operation=primary:color" in message
        and "image_bytes=123" in message
        for message in messages
    )
    assert any("phase=request_total" in message and "route=ocr_url" in message for message in messages)


def test_disabled_stage_timing_emits_nothing(caplog):
    caplog.set_level(logging.INFO, logger="repayment_ocr.timing")

    with request_timing(False, request_id="off"):
        with stage("image_decode"):
            pass

    assert not any("req=off" in record.getMessage() for record in caplog.records)


def test_predictor_proxy_preserves_result_and_logs_phase(caplog):
    caplog.set_level(logging.INFO, logger="repayment_ocr.timing")
    calls = []

    def detector(value):
        calls.append(value)
        return f"result:{value}"

    proxy = _TimedPredictorProxy(detector, "ocr_detection")
    with request_timing(True, request_id="predict"):
        result = proxy("image")

    assert result == "result:image"
    assert calls == ["image"]
    assert any(
        "req=predict" in record.getMessage() and "phase=ocr_detection" in record.getMessage()
        for record in caplog.records
    )
