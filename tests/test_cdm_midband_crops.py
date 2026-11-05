"""CDM 中间带裁剪坐标单测：禁止把账号带错映射到 NOTES 表。"""
from __future__ import annotations

import numpy as np

from app.ocr_engine import OcrLine
from repayment_slip_ocr.main import _anchor_scale_y, _prepare_cdm_band_crops


def _lr(text: str, x0, y0, x1, y1) -> OcrLine:
    return OcrLine(
        text=text,
        confidence=0.9,
        box=[[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
    )


def test_anchor_scale_ignores_bottom_margin():
    """画布高于最底 OCR 行时不得放大坐标（否则账号带滑到面额表）。"""
    lines = [
        _lr("TRANSACTION", 58, 1376, 509, 1449),
        _lr("NARRATION:", 62, 1914, 463, 1991),
        _lr("STATUS", 325, 3006, 1453, 3079),
    ]
    assert _anchor_scale_y(4128.0, lines) == 1.0


def test_ekala_party_band_covers_account_rows():
    """EKALA：首个裁剪窗应覆盖 ACCOUNT/CUSTOMER（约 y=1500–1750）。"""
    lines = [
        _lr("TRANSACTION", 58, 1376, 509, 1449),
        _lr(": CARDLESS DEPOSIT", 566, 1368, 1324, 1446),
        _lr("NARRATION:", 62, 1914, 463, 1991),
        _lr("SUCCESSFUL", 325, 3006, 1453, 3079),
    ]
    img = np.zeros((4128, 1856, 3), dtype=np.uint8)
    crops = _prepare_cdm_band_crops(img, lines)
    assert crops
    # 至少一个窗口覆盖账号行中心 ~1600
    assert any(top <= 1600 <= top + crop.shape[0] for crop, top, _ in crops)
    # 首窗不应落到 NOTES 表（~2500+）
    first_top = crops[0][1]
    assert first_top < 2000
