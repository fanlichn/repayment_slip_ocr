"""CDM 中间带裁剪坐标单测：禁止把账号带错映射到 NOTES 表。"""
from __future__ import annotations

import numpy as np

from app.ocr_engine import OcrLine
from repayment_slip_ocr.main import (
    _anchor_scale_y,
    _cdm_account_digits_weak,
    _prepare_cdm_amount_band_crops,
    _prepare_cdm_band_crops,
)


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
    # 锚点并集窗可能先于固定比例；固定比例首窗仍应在 NOTES 之上
    ratio_tops = [top for crop, top, left in crops if left <= 30]
    assert ratio_tops
    assert min(ratio_tops) < 2000


def test_kalutara_rotated_roi_covers_account_digits():
    """竖排合成图：锚点并集裁剪须覆盖 ACCOUNT 数字列（约 x=730,y=1340）。"""
    lines = [
        _lr("ACCOUNT NUMBER:", 721, 1170, 753, 1295),
        _lr("00109696", 730, 1306, 753, 1370),
        _lr("CUSTOMER NAME LAK ARTHA SERVICES", 686, 1167, 730, 1436),
        _lr("CARDLESS DEPOSIT", 744, 1276, 791, 1432),
        _lr("NARRATION:", 646, 1175, 675, 1261),
        _lr("DEPUSIT", 415, 1183, 438, 1236),
        _lr("MOUNT", 537, 1425, 557, 1464),
    ]
    img = np.zeros((1500, 1200, 3), dtype=np.uint8)
    crops = _prepare_cdm_band_crops(img, lines)
    assert crops
    assert any(
        top <= 1340 <= top + crop.shape[0] and left <= 740 <= left + crop.shape[1]
        for crop, top, left in crops
    )
    amt_crops = _prepare_cdm_amount_band_crops(img, lines)
    assert amt_crops
    assert any(
        top <= 1440 <= top + crop.shape[0] for crop, top, _ in amt_crops
    )
    assert _cdm_account_digits_weak("00109696")
    assert not _cdm_account_digits_weak("1001096962")
