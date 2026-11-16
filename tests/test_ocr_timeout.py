from concurrent.futures import ThreadPoolExecutor
import asyncio
import json
import time

import pytest

from repayment_slip_ocr import main
from repayment_slip_ocr.worker import OcrTimeout, OcrWorker


def simulated_worker(requests, responses):
    while True:
        kind, payload, include_lines = requests.get()
        if payload == "hang":
            time.sleep(30)
        responses.put(("ok", {"success": True, "value": payload}))


def test_timeout_terminates_worker_and_next_request_recovers():
    worker = OcrWorker(target=simulated_worker)
    try:
        with pytest.raises(OcrTimeout):
            worker.run("ocr_url", "hang", False, time.monotonic() + 1.5)
        status, result = worker.run("ocr_url", "next", False, time.monotonic() + 10)
        assert status == "ok"
        assert result == {"success": True, "value": "next"}
    finally:
        worker.close()


def test_waiting_request_times_out_without_killing_active_request():
    worker = OcrWorker(target=simulated_worker)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            active = pool.submit(worker.run, "ocr_url", "hang", False, time.monotonic() + 3)
            time.sleep(0.5)
            with pytest.raises(OcrTimeout):
                worker.run("ocr_url", "waiting", False, time.monotonic() + 0.2)
            with pytest.raises(OcrTimeout):
                active.result(timeout=8)
        assert worker.run("ocr_url", "next", False, time.monotonic() + 10)[0] == "ok"
    finally:
        worker.close()


def test_http_timeout_is_json_failure_and_recovers(monkeypatch):
    async def exercise():
        monkeypatch.setattr(main, "_REQUEST_TIMEOUT_SECONDS", 1.5)
        async with main.lifespan(main.app):
            main._ocr_worker.close()
            main._ocr_worker = OcrWorker(target=simulated_worker)
            timed_out = await main.ocr_url(main.UrlRequest(image_url="hang"))
            assert timed_out.status_code == 504
            assert json.loads(timed_out.body)["success"] is False
            monkeypatch.setattr(main, "_REQUEST_TIMEOUT_SECONDS", 10)
            result = await main.ocr_url(main.UrlRequest(image_url="next"))
            assert result == {"success": True, "value": "next"}

    asyncio.run(exercise())
