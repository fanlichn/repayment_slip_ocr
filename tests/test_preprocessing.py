from __future__ import annotations

import cv2
import numpy as np

from app.preprocessing import build_variants


def test_fast_denoise_keeps_variant_contract_without_nlm(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("NLM must not run in fast mode")

    monkeypatch.setattr(cv2, "fastNlMeansDenoising", forbidden)
    image = np.full((1200, 1200, 3), 255, dtype=np.uint8)

    variants = build_variants(image, fast_denoise=True)

    assert [variant["name"] for variant in variants] == [
        "color",
        "color_raw",
        "enhanced",
        "binarized",
    ]
    assert all(variant["img"].shape[:2] == (1200, 1200) for variant in variants)
