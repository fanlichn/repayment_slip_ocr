"""Request-scoped OCR stage timing.

Timing is opt-in and log-only.  It never changes an API response.
"""
from __future__ import annotations

import contextlib
import contextvars
import logging
import os
import secrets
import time
from typing import Iterator, Optional


logger = logging.getLogger("repayment_ocr.timing")
logger.setLevel(logging.INFO)
# Uvicorn configures logging before importing the app and may mark pre-existing
# application loggers disabled. Keep this dedicated metrics logger active.
logger.disabled = False

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "ocr_request_id", default="-"
)
_service: contextvars.ContextVar[str] = contextvars.ContextVar(
    "ocr_service", default="repayment"
)
_operation: contextvars.ContextVar[str] = contextvars.ContextVar(
    "ocr_operation", default="-"
)
_enabled: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "ocr_timing_enabled", default=False
)


def timing_enabled() -> bool:
    return _enabled.get()


def current_operation() -> str:
    return _operation.get()


def log_duration(phase: str, elapsed_ms: float, **values) -> None:
    if not timing_enabled():
        return
    parts = [
        "ocr_timing",
        f"service={_service.get()}",
        f"req={_request_id.get()}",
        f"pid={os.getpid()}",
        f"phase={phase}",
        f"ms={elapsed_ms:.3f}",
    ]
    operation = current_operation()
    if operation != "-":
        parts.append(f"operation={operation}")
    for key, value in values.items():
        if value is None:
            continue
        safe = str(value).replace(" ", "_").replace("\n", "_")
        parts.append(f"{key}={safe}")
    logger.info(" ".join(parts))


@contextlib.contextmanager
def request_timing(
    enabled: bool,
    *,
    service: str = "repayment",
    route: str = "-",
    request_id: Optional[str] = None,
) -> Iterator[str]:
    req = request_id or secrets.token_hex(4)
    token_req = _request_id.set(req)
    token_service = _service.set(service)
    token_enabled = _enabled.set(bool(enabled))
    started = time.perf_counter()
    try:
        yield req
    finally:
        log_duration(
            "request_total",
            (time.perf_counter() - started) * 1000,
            route=route,
        )
        _enabled.reset(token_enabled)
        _service.reset(token_service)
        _request_id.reset(token_req)


@contextlib.contextmanager
def operation(name: str) -> Iterator[None]:
    token = _operation.set(name)
    try:
        yield
    finally:
        _operation.reset(token)


@contextlib.contextmanager
def stage(phase: str, **values) -> Iterator[None]:
    if not timing_enabled():
        yield
        return
    started = time.perf_counter()
    try:
        yield
    finally:
        log_duration(phase, (time.perf_counter() - started) * 1000, **values)
