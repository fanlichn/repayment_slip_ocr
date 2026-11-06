"""Paddle OCR 包装层的并发、限幅和 primitive 容错。"""
from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import numpy as np

from app.ocr_engine import PaddleOcrEngine


def _settings():
    return SimpleNamespace(
        paddle_use_angle_cls=False,
        paddle_use_gpu=False,
        ocr_lang="en",
    )


def _result(box=None):
    box = box or [[10, 20], [30, 20], [30, 40], [10, 40]]
    return [[[box, ("TEXT", 0.99)]]]


def test_large_input_is_bounded_and_boxes_are_restored():
    class FakePredictor:
        def __init__(self):
            self.shape = None

        def ocr(self, image, cls=False):
            self.shape = image.shape
            return _result()

    engine = PaddleOcrEngine(_settings())
    fake = FakePredictor()
    engine._ocr = fake
    image = np.zeros((6000, 4000, 3), dtype=np.uint8)

    lines = engine.recognize(image)

    assert max(fake.shape[:2]) <= 5000
    assert fake.shape[0] * fake.shape[1] <= 16_000_000
    # 检测框须按缩放比例映射回原图坐标。
    assert lines[0].box[0][0] > 10
    assert lines[0].box[0][1] > 20


def test_primitive_error_rebuilds_predictor_and_retries_once():
    class BrokenPredictor:
        def ocr(self, image, cls=False):
            raise RuntimeError("could not execute a primitive")

    class HealthyPredictor:
        def ocr(self, image, cls=False):
            return _result()

    engine = PaddleOcrEngine(_settings())
    engine._ocr = BrokenPredictor()
    rebuilt = HealthyPredictor()
    engine._new_ocr = lambda: rebuilt

    lines = engine.recognize(np.zeros((100, 200, 3), dtype=np.uint8))

    assert engine._ocr is rebuilt
    assert lines[0].text == "TEXT"


def test_shared_predictor_inference_is_serialized():
    class ConcurrentProbe:
        def __init__(self):
            self.active = 0
            self.max_active = 0
            self.guard = threading.Lock()

        def ocr(self, image, cls=False):
            with self.guard:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            time.sleep(0.03)
            with self.guard:
                self.active -= 1
            return _result()

    engine = PaddleOcrEngine(_settings())
    probe = ConcurrentProbe()
    engine._ocr = probe
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    threads = [threading.Thread(target=engine.recognize, args=(image,)) for _ in range(3)]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert probe.max_active == 1


def test_recognize_line_skips_detector_and_parses_rec_result():
    class LinePredictor:
        def __init__(self):
            self.det = None

        def ocr(self, image, det=True, rec=True, cls=False):
            self.det = det
            return [[("ACCOUNT NUMBER: 1001096962", 0.98)]]

    engine = PaddleOcrEngine(_settings())
    predictor = LinePredictor()
    engine._ocr = predictor

    lines = engine.recognize_line(np.zeros((100, 800, 3), dtype=np.uint8))

    assert predictor.det is False
    assert lines[0].text == "ACCOUNT NUMBER: 1001096962"
    assert lines[0].confidence == 0.98
