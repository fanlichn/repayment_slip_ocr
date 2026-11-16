"""Isolated, reusable OCR process with a deadline for each request."""
from __future__ import annotations

import logging
import multiprocessing
import queue
import threading
import time

logger = logging.getLogger(__name__)


def _worker_main(requests, responses):
    # Import inside the spawned process so the predictor belongs to this process.
    from fastapi import HTTPException
    from app.config import get_settings
    from app.ocr_engine import create_engine
    from app.stage_timing import request_timing, stage
    from app.url_fetch import UrlFetchError, fetch_image_bytes
    from repayment_slip_ocr import main

    settings = get_settings()
    main._engine = create_engine(settings)
    main._engine.warmup()
    while True:
        job = requests.get()
        if job is None:
            return
        kind, payload, include_lines = job
        try:
            with request_timing(settings.stage_timing_log, service="repayment", route=kind):
                if kind == "ocr_url":
                    with stage("image_download"):
                        payload = fetch_image_bytes(payload, settings)
                result = main._recognize_impl(payload, include_lines=include_lines)
            responses.put(("ok", result))
        except UrlFetchError as exc:
            responses.put(("error", (400, str(exc))))
        except HTTPException as exc:
            responses.put(("error", (exc.status_code, str(exc.detail))))
        except Exception:
            logger.exception("OCR worker failed")
            responses.put(("error", (500, "OCR 识别失败")))


class OcrTimeout(Exception):
    pass


class OcrWorker:
    def __init__(self, target=_worker_main):
        self._context = multiprocessing.get_context("spawn")
        self._target = target
        self._lock = threading.Lock()
        self._process = None
        self._requests = None
        self._responses = None

    def _start(self):
        self._requests = self._context.Queue()
        self._responses = self._context.Queue()
        self._process = self._context.Process(
            target=self._target, args=(self._requests, self._responses), daemon=True
        )
        self._process.start()

    def _stop(self):
        process = self._process
        self._process = None
        if process is not None:
            if process.is_alive():
                process.terminate()
                process.join(timeout=1)
                if process.is_alive():
                    process.kill()
            process.join(timeout=1)
        for channel in (self._requests, self._responses):
            if channel is not None:
                channel.cancel_join_thread()
                channel.close()
        self._requests = self._responses = None

    def close(self):
        with self._lock:
            self._stop()

    def run(self, kind, payload, include_lines, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not self._lock.acquire(timeout=remaining):
            raise OcrTimeout()
        try:
            if time.monotonic() >= deadline:
                raise OcrTimeout()
            if self._process is None or not self._process.is_alive():
                self._stop()
                self._start()
            try:
                self._requests.put((kind, payload, include_lines))
            except (OSError, ValueError):
                self._stop()
                return "error", (500, "OCR 识别进程异常退出")
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._stop()
                    raise OcrTimeout()
                try:
                    return self._responses.get(timeout=min(remaining, 0.2))
                except queue.Empty:
                    if not self._process.is_alive():
                        self._stop()
                        return "error", (500, "OCR 识别进程异常退出")
                except (EOFError, OSError, ValueError):
                    self._stop()
                    return "error", (500, "OCR 识别进程通信失败")
        finally:
            self._lock.release()
