"""CDM 中间带裁剪坐标单测：禁止把账号带错映射到 NOTES 表。"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from app.ocr_engine import OcrLine
from repayment_slip_ocr.main import (
    _anchor_scale_y,
    _add_cdm_explicit_nulls,
    _cdm_amount_direct_windows,
    _cdm_account_digits_weak,
    _cdm_branch_direct_windows,
    _cdm_header_direct_windows,
    _cdm_party_direct_windows,
    _cdm_table_direct_windows,
    _has_cdm_deposit_amount_text,
    _pad_crop_for_ocr,
    _prepare_cdm_amount_band_crops,
    _prepare_cdm_band_crops,
    _prepare_cdm_header_band_crops,
    _priority_cdm_amount_crops,
    _priority_cdm_party_crops,
    _run_cdm_direct_line_windows,
)


def _lr(text: str, x0, y0, x1, y1) -> OcrLine:
    return OcrLine(
        text=text,
        confidence=0.9,
        box=[[x0, y0], [x1, y0], [x1, y1], [x0, y1]],
    )


def test_direct_line_windows_can_run_one_prep_then_fallback():
    class Engine:
        def __init__(self):
            self.calls = 0

        def recognize_line(self, image):
            self.calls += 1
            return []

    image = np.zeros((100, 200, 3), dtype=np.uint8)
    window = [(10, 20, 190, 80)]

    raw_engine = Engine()
    _run_cdm_direct_line_windows(
        raw_engine, image, window, prep_indices=(0,)
    )
    assert raw_engine.calls == 1

    fallback_engine = Engine()
    _run_cdm_direct_line_windows(
        fallback_engine, image, window, prep_indices=(0, 1)
    )
    assert fallback_engine.calls == 2


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
    # 细条带须优先且覆盖 ACCOUNT(~1560)/CUSTOMER(~1680)，高<220
    thin = [(crop, top) for crop, top, _ in crops if crop.shape[0] < 220]
    assert thin, "TRANSACTION~NARRATION 细条带缺失"
    assert any(top <= 1560 <= top + crop.shape[0] for crop, top in thin)
    assert any(top <= 1680 <= top + crop.shape[0] for crop, top in thin)
    # 队首应为细条，避免宽幅热敏区先跑导致整段漏读
    assert crops[0][0].shape[0] < 220
    # 固定比例窗仍应在 NOTES 之上
    ratio_tops = [top for crop, top, left in crops if left <= 30 and crop.shape[0] >= 220]
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


def test_nawalapi_sparse_crops_cover_party_amount_terminal():
    """NAWALAPI 折痕稀疏 OCR：裁窗须覆盖 ACCOUNT(~2000)/11400(~3350)/TERMINAL(~1300)。"""
    lines = [
        _lr("DATE", 500, 1238, 682, 1320),
        _lr("TIME", 981, 1211, 1157, 1305),
        _lr("08:03", 983, 1287, 1193, 1381),
        _lr("TRACE", 513, 1461, 734, 1554),
        _lr("3528", 999, 1429, 1183, 1523),
        _lr("TRANSACTION", 533, 1697, 997, 1787),
        _lr("CARDL", 1148, 1682, 1356, 1732),
        _lr("NOTES", 608, 2880, 830, 2966),
        _lr("VALUE", 979, 2843, 1198, 2937),
        _lr("AMOUNT", 1873, 2770, 2131, 2864),
        _lr("4", 836, 3032, 881, 3097),
        _lr("100.00", 1238, 2988, 1493, 3069),
        _lr("400.00", 1888, 2933, 2156, 3022),
        _lr("1", 839, 3118, 889, 3181),
        _lr("1.000.00", 1813, 3023, 2160, 3112),
        _lr("2", 847, 3200, 890, 3264),
        _lr("LKR", 1412, 3303, 1566, 3394),
    ]
    img = np.zeros((4096, 3072, 3), dtype=np.uint8)
    party = _prepare_cdm_band_crops(img, lines)
    assert party
    assert any(top <= 2000 <= top + crop.shape[0] for crop, top, _ in party)
    assert any(top <= 2200 <= top + crop.shape[0] for crop, top, _ in party)
    # 中间带不得过宽带进右手背景
    assert all(left + crop.shape[1] < 2800 for crop, top, left in party[:8])

    amt = _prepare_cdm_amount_band_crops(img, lines)
    assert amt
    assert any(
        top <= 3350 <= top + crop.shape[0] and left <= 1900 <= left + crop.shape[1]
        for crop, top, left in amt
    )
    assert any(
        top <= 3100 <= top + crop.shape[0] and left >= 1500
        for crop, top, left in amt
    )

    hdr = _prepare_cdm_header_band_crops(img, lines)
    assert hdr
    assert any(
        top <= 1300 <= top + crop.shape[0] and left <= 1600 <= left + crop.shape[1]
        for crop, top, left in hdr
    )

    # 仅有面额 10000 不得早停；须见到非面额总额
    assert not _has_cdm_deposit_amount_text(
        [_lr("10,000.00", 1813, 3023, 2160, 3112), _lr("400.00", 1888, 2933, 2156, 3022)]
    )
    assert _has_cdm_deposit_amount_text(
        [_lr("11,400.00", 1700, 3344, 2100, 3376), _lr("10,000.00", 1813, 3023, 2160, 3112)]
    )

    # 优先中高裁须覆盖账号带与右列总额（Paddle 细条无边距易漏）
    pri_party = _priority_cdm_party_crops(img, lines)
    assert pri_party
    assert any(top <= 2000 <= top + crop.shape[0] for crop, top, _ in pri_party)
    assert pri_party[0][0].shape[0] >= 400
    pri_amt = _priority_cdm_amount_crops(img, lines)
    assert pri_amt
    assert any(
        top <= 3350 <= top + crop.shape[0] and left <= 1900 <= left + crop.shape[1]
        for crop, top, left in pri_amt
    )
    padded, top2, left2 = _pad_crop_for_ocr(pri_party[0][0], pri_party[0][1], pri_party[0][2], pad=24)
    assert padded.shape[0] == pri_party[0][0].shape[0] + 48
    assert top2 == pri_party[0][1] - 24

    direct_party = _cdm_party_direct_windows(img, lines)
    assert any(y0 <= 1950 <= y1 for _, y0, _, y1 in direct_party)
    assert any(y0 <= 2100 <= y1 for _, y0, _, y1 in direct_party)

    direct_amount = _cdm_amount_direct_windows(img, lines)
    assert any(y0 <= 2980 <= y1 for _, y0, _, y1 in direct_amount)
    assert any(y0 <= 3350 <= y1 for _, y0, _, y1 in direct_amount)

    direct_header = _cdm_header_direct_windows(img, lines)
    assert len(direct_header) == 3
    # 中列覆盖 TIME 值，右列覆盖 TERMINAL ID。
    assert direct_header[1][0] <= 1080 <= direct_header[1][2]
    assert direct_header[2][0] <= 1700 <= direct_header[2][2]
    direct_branch = _cdm_branch_direct_windows(img, lines)
    assert any(y0 <= 1030 <= y1 for _, y0, _, y1 in direct_branch)


def test_cdm_visible_blank_labels_are_returned_as_null():
    result = SimpleNamespace(
        doc_type="cash_deposit_slip",
        fields={"TRANSACTION": "CARDLESS DEPOSIT"},
    )
    out = {"TRANSACTION": "CARDLESS DEPOSIT"}
    lines = [
        _lr("ARRATION", 100, 2100, 800, 2180),
        _lr("MOBILENO.", 100, 2400, 800, 2480),
    ]

    _add_cdm_explicit_nulls(out, result, lines)

    assert "NARRATION" in out and out["NARRATION"] is None
    assert "MOBILE NO." in out and out["MOBILE NO."] is None


def test_madawala_small_image_direct_windows_follow_table_cells():
    """1024px 远拍图不能套用 4096px 绝对高度；三列窗口应各自覆盖同一纸币行。"""
    img = np.zeros((1024, 768, 3), dtype=np.uint8)
    lines = [
        _lr("TRANSACTION", 270, 552, 355, 568),
        _lr("NOTES", 260, 747, 310, 763),
        _lr("VALUE", 325, 747, 370, 763),
        _lr("AMOUNT", 485, 747, 540, 763),
        _lr("1", 295, 778, 305, 794),
    ]

    party = _cdm_party_direct_windows(img, lines)
    # 第一/二行分别覆盖 ACCOUNT(~587) 与 CUSTOMER(~615)，不整体下移。
    assert party[0][1] <= 587 <= party[0][3]
    assert party[1][1] <= 615 <= party[1][3]

    table = _cdm_table_direct_windows(img, lines)
    assert len(table) == 3
    qty, value, amount = table
    assert qty[0] <= 300 <= qty[2] and qty[1] <= 786 <= qty[3]
    assert value[0] <= 350 <= value[2] and value[1] <= 786 <= value[3]
    assert amount[0] <= 500 <= amount[2] and amount[1] <= 795 <= amount[3]


def test_table_direct_windows_stop_before_deposit_amount_row():
    img = np.zeros((2000, 1200, 3), dtype=np.uint8)
    lines = [
        _lr("NOTES", 150, 900, 300, 940),
        _lr("VALUE", 380, 900, 530, 940),
        _lr("AMOUNT", 720, 900, 920, 940),
        _lr("4", 210, 980, 250, 1020),
        _lr("DEPOSIT AMOUNT", 100, 1080, 430, 1120),
        # 总额带的噪声数字不能触发第二组三列 OCR。
        _lr("1", 210, 1082, 250, 1118),
    ]

    windows = _cdm_table_direct_windows(img, lines)

    assert len(windows) == 3
    assert all((top + bottom) / 2 < 1080 for _, top, _, bottom in windows)
