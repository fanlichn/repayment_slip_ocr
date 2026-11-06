"""还款/转账凭证信息提取 FastAPI 服务。

复用 sri_lanka_nic_ocr 的图像预处理、OCR 引擎与远程图片下载（含 SSRF 防护），
与身份证主服务相互独立，可单独部署。
"""
from __future__ import annotations

import base64
import binascii
import re
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import get_settings
from app.logging_setup import setup_logging
from app.ocr_engine import OcrLine, create_engine
from app.preprocessing import build_variants, load_image
from app.url_fetch import UrlFetchError, fetch_image_bytes

from .extractor import (
    _is_ntb_description_code,
    _is_ntb_ocr_junk_token,
    _is_ntb_watermark_text,
    _ntb_description_contaminated,
    _parse_money,
    _scrub_ntb_watermark_glue,
    dedup_lines,
    extract,
)

setup_logging("repayment_ocr")

_engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine
    settings = get_settings()
    _engine = create_engine(settings)
    _engine.warmup()
    yield


app = FastAPI(
    title="Repayment Slip OCR",
    description="识别斯里兰卡银行的还款/转账凭证并抽取付款方、收款方、金额、日期、参考号等字段。",
    version="1.0.0",
    lifespan=lifespan,
)


class Base64Request(BaseModel):
    image_base64: str


class UrlRequest(BaseModel):
    image_url: str


def _structured_fallback(result) -> Dict[str, Any]:
    """无明确 label 的图片：用统一的结构化字段名作为 key 返回。"""
    refs = result.references
    transaction_reference = (
        refs.txn_ref or refs.transaction_id or refs.bank_reference_number
        or refs.retrieval_ref or refs.e_receipt_reference or refs.my_ref
        or refs.receiver_ref
    )
    return {
        "status": result.status,
        "bank": result.bank,
        "amount": result.amount,
        "fee": result.fee,
        "total_debit": result.total_debit,
        "currency": result.currency,
        "datetime": result.datetime,
        "payer_name": result.payer.name,
        "payer_account": result.payer.account,
        "payer_bank": result.payer.bank,
        "payee_name": result.payee.name,
        "payee_account": result.payee.account,
        "payee_bank": result.payee.bank,
        "transaction_reference": transaction_reference,
        "remarks": refs.remarks,
    }


def _line_center_y(box) -> float:
    return sum(p[1] for p in box) / len(box)


def _line_center_x(box) -> float:
    return sum(p[0] for p in box) / len(box)


def _is_cdm_result(result) -> bool:
    fields = result.fields or {}
    return (
        result.doc_type == "cash_deposit_slip"
        or str(fields.get("TRANSACTION", "")).upper().find("CARDLESS") >= 0
        or bool(fields.get("TERMINAL ID") and fields.get("DEPOSIT AMOUNT"))
        or bool(fields.get("SOURCE OF FUNDS"))
    )


def _cdm_account_digits_weak(acct: Optional[str]) -> bool:
    """截断账号（如 00109696←1001096962）视为弱，需中间带复检。"""
    digits = re.sub(r"\D", "", str(acct or ""))
    if not digits:
        return True
    if len(digits) < 10:
        return True
    if digits.startswith("00"):
        return True
    return False


def _cdm_missing_party_fields(result) -> bool:
    """CDM 缺少户名，或账号缺失/截断时，需要对中间带复检。"""
    if not _is_cdm_result(result):
        return False
    fields = result.fields or {}
    if not fields.get("CUSTOMER NAME"):
        return True
    return _cdm_account_digits_weak(fields.get("ACCOUNT NUMBER"))


def _cdm_missing_deposit_amount(result) -> bool:
    """CDM 缺存款总额时，对金额带（DEPOSIT AMOUNT / 面额表）复检。"""
    if not _is_cdm_result(result):
        return False
    fields = result.fields or {}
    amt = result.amount
    dep = fields.get("DEPOSIT AMOUNT")
    # 行小计（如 400=4×100）被当成总额时仍须复检
    if amt is not None and _looks_like_row_subtotal_deposit(amt, fields):
        return True
    if dep:
        parsed = _parse_money(str(dep))
        if parsed is not None and _looks_like_row_subtotal_deposit(parsed, fields):
            return True
    if dep and amt is not None:
        return False
    if amt is not None and amt >= 100:
        return False
    return True


def _cdm_missing_header_fields(result) -> bool:
    """缺 TERMINAL ID / BRANCH 时复检日期行右侧与银行名下方。"""
    if not _is_cdm_result(result):
        return False
    fields = result.fields or {}
    return not fields.get("TERMINAL ID") or not fields.get("BRANCH")


def _looks_like_row_subtotal_deposit(amount: float, fields: dict) -> bool:
    """无可靠大额时，偏小的「存款额」更像面额表行 AMOUNT。"""
    if amount < 100:
        return False
    # 常见面额面值（含 10,000 行小计）不得充当 DEPOSIT 总额而停止复检
    if amount in {100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0}:
        return True
    if amount >= 5000:
        return False
    for denom in (100.0, 500.0, 1000.0, 2000.0, 5000.0):
        if denom > amount:
            continue
        qty = amount / denom
        if abs(qty - round(qty)) < 0.01 and 2 <= round(qty) <= 50:
            return True
    return False


def _anchor_ys(lines: List[OcrLine], patterns: List[str]) -> List[float]:
    hits: List[float] = []
    for ln in lines:
        low = ln.text.lower()
        if any(p in low for p in patterns):
            hits.append(_line_center_y(ln.box))
    return hits


def _anchor_boxes(lines: List[OcrLine], patterns: List[str]) -> List[list]:
    boxes: List[list] = []
    for ln in lines:
        low = ln.text.lower()
        if any(p in low for p in patterns):
            boxes.append(ln.box)
    return boxes


def _offset_ocr_lines(lines: List[OcrLine], dy: float, dx: float = 0.0, scale: float = 1.0) -> List[OcrLine]:
    out: List[OcrLine] = []
    inv = 1.0 / scale if scale else 1.0
    for ln in lines:
        box = [[p[0] * inv + dx, p[1] * inv + dy] for p in ln.box]
        out.append(OcrLine(text=ln.text, confidence=ln.confidence, box=box))
    return out


def _line_max_y(lines: List[OcrLine]) -> float:
    ys = [max(p[1] for p in ln.box) for ln in lines if ln.box]
    return max(ys) if ys else 1.0


def _has_strong_cdm_account(lines: List[OcrLine]) -> bool:
    """是否已读到完整账号（拒 8 位/00 开头截断，拒把 CARDLESS 当 party）。"""
    for ln in lines:
        for m in re.finditer(r"(?<!\d)(\d{9,14})(?!\d)", ln.text):
            digits = m.group(1)
            if not digits.startswith("00"):
                return True
    return False


def _has_cdm_party_text(lines: List[OcrLine]) -> bool:
    """中间带早停：须有完整账号，或同时有账号标签+≥8 位数字。"""
    if _has_strong_cdm_account(lines):
        return True
    blob = " ".join(ln.text.lower() for ln in lines)
    if ("account" in blob or "customer" in blob or "acc0unt" in blob) and re.search(
        r"(?<!\d)\d{8,14}(?!\d)", blob
    ):
        # 仍可能是截断号；有强账号才真正早停
        return _has_strong_cdm_account(lines)
    return False


def _has_cdm_deposit_amount_text(lines: List[OcrLine]) -> bool:
    """金额带早停：须看到 DEPOSIT 标签，或明显大于面额面值的总额（如 11,400）。"""
    blob = " ".join(ln.text.lower() for ln in lines)
    if "deposit" in blob and "amount" in blob:
        return True
    vals = []
    for ln in lines:
        low = ln.text.lower()
        if "fee" in low or "charge" in low:
            continue
        if re.search(r"(?i)\bnotes\b|\bvalue\b", low) and "deposit" not in low:
            if not re.search(r"\d", ln.text):
                continue
        val = _parse_money(ln.text)
        if val is None or val < 100 or val >= 50_000_000:
            continue
        vals.append(val)
    if not vals:
        return False
    max_v = max(vals)
    # 面额面值（含 10,000 行 AMOUNT）不算读到总额，继续扫 LKR 旁 11,400
    if max_v in {100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0}:
        return False
    if max_v <= 5000 and any(
        abs(max_v / d - round(max_v / d)) < 0.01 and 2 <= round(max_v / d) <= 50
        for d in (100.0, 500.0, 1000.0, 2000.0, 5000.0)
        if d <= max_v
    ):
        return False
    return max_v >= 1000


def _anchor_scale_y(img_h: float, lines: List[OcrLine]) -> float:
    """仅当行框明显超出当前图高（来自更大 variant）时才缩小；禁止把空白底边当成缩放。

    旧逻辑用 h/max_line_y：收据未铺满画布时 max_line_y < h，会把 TRANSACTION~NARRATION
    错映射到下方 NOTES 表，账号行永远裁不到。
    """
    ref = _line_max_y(lines)
    if ref > img_h * 1.05:
        return img_h / ref
    return 1.0


def _roi_from_boxes(
    img: np.ndarray, boxes: List[list], pad_x: float = 0.04, pad_y: float = 0.04
) -> Optional[tuple]:
    """锚点框并集裁剪：(crop, top, left)。用于竖排/合成图（Truecaller+收据）。"""
    if not boxes:
        return None
    h, w = img.shape[:2]
    xs = [float(p[0]) for b in boxes for p in b]
    ys = [float(p[1]) for b in boxes for p in b]
    x0 = max(0, int(min(xs) - w * pad_x))
    x1 = min(w, int(max(xs) + w * pad_x))
    y0 = max(0, int(min(ys) - h * pad_y))
    y1 = min(h, int(max(ys) + h * pad_y))
    if x1 - x0 < 40 or y1 - y0 < 40:
        return None
    crop = img[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    return crop, float(y0), float(x0)


def _cdm_receipt_x_bounds(lines: List[OcrLine], img_w: int) -> tuple:
    """按已识别文字框估计收据左右边界，裁掉手/地面背景以免干扰 OCR。"""
    xs = [float(p[0]) for ln in lines if ln.box for p in ln.box]
    if not xs:
        return 0, img_w
    x0 = max(0, int(min(xs) - img_w * 0.02))
    x1 = min(img_w, int(max(xs) + img_w * 0.04))
    if x1 - x0 < img_w * 0.35:
        return 0, img_w
    return x0, x1


def _prepare_cdm_band_crops(img: np.ndarray, lines: List[OcrLine]) -> List[tuple]:
    """生成若干中间带裁剪：(crop, top, left)。

    NAWALAPI 类折痕凭条：全幅裁易被背景干扰；用 TRACE/TRANSACTION→NOTES
    锚定，限制在收据 x 范围内切细条，专打 ACCOUNT/CUSTOMER。
    """
    h, w = img.shape[:2]
    scale_y = _anchor_scale_y(float(h), lines)
    rx0, rx1 = _cdm_receipt_x_bounds(lines, w)

    out: List[tuple] = []
    seen = set()

    def _add_crop(crop, top: float, left: float) -> None:
        if crop is None or crop.size == 0:
            return
        key = (int(top) // 12, int(left) // 12, crop.shape[0] // 12, crop.shape[1] // 20)
        if key in seen:
            return
        seen.add(key)
        out.append((crop, float(top), float(left)))

    # 竖排/合成图：ACCOUNT/CUSTOMER/TRANSACTION 等锚点并集（含邻近纯数字行）
    party_boxes = _anchor_boxes(
        lines,
        [
            "account",
            "customer",
            "cardless",
            "transaction",
            "ransaction",
            "narration",
            "mobile",
        ],
    )
    if party_boxes:
        xs0 = min(p[0] for b in party_boxes for p in b)
        xs1 = max(p[0] for b in party_boxes for p in b)
        ys0 = min(p[1] for b in party_boxes for p in b)
        ys1 = max(p[1] for b in party_boxes for p in b)
        for ln in lines:
            if not re.search(r"\d{6,}", ln.text):
                continue
            cx = sum(p[0] for p in ln.box) / 4.0
            cy = sum(p[1] for p in ln.box) / 4.0
            if xs0 - 80 <= cx <= xs1 + 80 and ys0 - 80 <= cy <= ys1 + 120:
                party_boxes.append(ln.box)
        roi = _roi_from_boxes(img, party_boxes, pad_x=0.06, pad_y=0.05)
        if roi:
            _add_crop(*roi)

    y0_hits = _anchor_ys(lines, ["cardless", "transaction", "trace"])
    y1_hits = _anchor_ys(lines, ["narration", "mobile", "source of funds", "notes", "hotes", "value"])
    # TRACE 下方即 TRANSACTION/ACCOUNT；NOTES 上方结束中间段
    y_trace = min(_anchor_ys(lines, ["trace"]), default=None)
    y_txn = min(_anchor_ys(lines, ["transaction", "cardless"]), default=None)
    y_notes = min(_anchor_ys(lines, ["notes", "hotes", "value"]), default=None)
    y0 = None
    if y_txn is not None:
        y0 = y_txn * scale_y
    elif y_trace is not None:
        y0 = y_trace * scale_y + 40
    elif y0_hits:
        y0 = min(y0_hits) * scale_y
    y1 = None
    if y_notes is not None:
        y1 = y_notes * scale_y
    elif y1_hits:
        below = [y * scale_y for y in y1_hits if y0 is None or y * scale_y > y0 + 40]
        y1 = min(below) if below else min(y1_hits) * scale_y

    # 细条带优先：限制在收据宽度内，避免右手/地面进框
    strip_windows: List[tuple] = []
    if y0 is not None and y1 is not None and y1 > y0 + 80:
        gap0 = y0 + 20
        gap1 = y1 - 10
        strip_h = max(110.0, min(200.0, (gap1 - gap0) / 4.5))
        step = strip_h * 0.50
        y = gap0
        while y < gap1 - 60:
            strip_windows.append((y, min(gap1, y + strip_h)))
            y += step
        # 半段 / 整段放后：细条先跑，避免宽幅热敏区整段漏读
        strip_windows.append((gap0 + (gap1 - gap0) * 0.05, gap0 + (gap1 - gap0) * 0.55))
        strip_windows.append((gap0 + (gap1 - gap0) * 0.35, gap0 + (gap1 - gap0) * 0.95))
        strip_windows.append((gap0, gap1))
    else:
        for ya, yb in (
            (h * 0.36, h * 0.40),
            (h * 0.38, h * 0.42),
            (h * 0.40, h * 0.44),
            (h * 0.42, h * 0.55),
            (h * 0.35, h * 0.55),
            (h * 0.45, h * 0.65),
        ):
            strip_windows.append((ya, yb))

    # 中间字段在收据左~75%：裁掉右侧手/地面，对齐诊断 party_mid
    party_x1 = min(rx1, max(rx0 + int((rx1 - rx0) * 0.78), int(w * 0.62)))
    strip_out: List[tuple] = []
    strip_seen = set()
    for y_a, y_b in strip_windows:
        top = max(0, int(y_a))
        bottom = min(h, int(y_b))
        if bottom - top < 50:
            continue
        key = (top // 10, bottom // 10, rx0 // 20)
        if key in strip_seen:
            continue
        strip_seen.add(key)
        crop = img[top:bottom, rx0:party_x1]
        if crop.size:
            strip_out.append((crop, float(top), float(rx0)))
    out = strip_out + out

    windows: List[tuple] = []
    windows.extend(
        [
            (h * 0.34, h * 0.47),
            (h * 0.32, h * 0.50),
            (h * 0.30, h * 0.55),
            (h * 0.40, h * 0.68),
            (h * 0.55, h * 0.85),
        ]
    )
    if y0 is not None and y1 is not None and y1 > y0 + 60:
        span = y1 - y0
        windows.append((y0 + span * 0.10, y1 - span * 0.05))
        windows.append((y0 + 15, y1 - 5))

    for y_a, y_b in windows:
        top = max(0, int(y_a))
        bottom = min(h, int(y_b))
        if bottom - top < 40:
            continue
        _add_crop(img[top:bottom, rx0:party_x1], float(top), float(rx0))
    return out


def _prepare_cdm_amount_band_crops(img: np.ndarray, lines: List[OcrLine]) -> List[tuple]:
    """DEPOSIT AMOUNT / NOTES 面额表区域裁剪。

    诊断：右侧 AMOUNT 列 + 底部 LKR 旁 11,400 在紧裁下清晰；宽幅全图易漏。
    """
    h, w = img.shape[:2]
    out: List[tuple] = []
    seen = set()
    rx0, rx1 = _cdm_receipt_x_bounds(lines, w)

    def _add(crop, top: float, left: float) -> None:
        if crop is None or crop.size == 0:
            return
        key = (int(top) // 12, int(left) // 12, crop.shape[0] // 12)
        if key in seen:
            return
        seen.add(key)
        out.append((crop, float(top), float(left)))

    amt_boxes = _anchor_boxes(
        lines,
        [
            "deposit",
            "depusi",
            "amount",
            "mount",
            "notes",
            "hotes",
            "value",
            "lkr",
            "successful",
            "status",
        ],
    )
    # AMOUNT 列表头左缘：专裁右列（400 / 1,000 / 10,000 / 11,400）
    amount_xs = []
    notes_ys = []
    lkr_ys = []
    for ln in lines:
        low = ln.text.strip().lower()
        cy = _line_center_y(ln.box)
        if low.rstrip(":.") == "amount" or low.startswith("amount"):
            amount_xs.append(min(p[0] for p in ln.box))
        if _looks_like_notes_header_text(low) or low.startswith("value"):
            notes_ys.append(cy)
        if re.fullmatch(r"lkr", low) and cy > h * 0.55:
            lkr_ys.append(cy)
            amount_xs.append(min(p[0] for p in ln.box))

    # 总额数字比 AMOUNT 表头更靠左，少裁会只剩 ".00"
    col_x0 = int(min(amount_xs) - 220) if amount_xs else int(w * 0.42)
    col_x0 = max(rx0, min(col_x0, int(w * 0.55)))
    y_notes = min(notes_ys) if notes_ys else h * 0.65
    y_lkr = max(lkr_ys) if lkr_ys else h * 0.82

    # 右列：NOTES 表到页脚（诊断裁 notes_right / amt_lkr）
    for y_a, y_b, x_a in (
        (y_notes - 40, min(h, y_lkr + 180), col_x0),
        (y_notes - 20, min(h, y_notes + (h - y_notes) * 0.85), col_x0 - 40),
        (y_lkr - 80, min(h, y_lkr + 160), max(rx0, int(w * 0.35))),
        (y_lkr - 40, min(h, y_lkr + 120), col_x0 - 100),
        (max(0, y_lkr - 30), min(h, y_lkr + 100), max(rx0, int(w * 0.40))),
    ):
        top = max(0, int(y_a))
        bottom = min(h, int(y_b))
        x0 = max(0, int(x_a))
        if bottom - top < 36:
            continue
        _add(img[top:bottom, x0:rx1], float(top), float(x0))

    if amt_boxes:
        roi = _roi_from_boxes(img, amt_boxes, pad_x=0.10, pad_y=0.12)
        if roi:
            _add(*roi)

    for y_a, y_b, x_a in (
        (h * 0.65, h * 0.98, 0.45),
        (h * 0.70, h * 0.99, 0.50),
        (h * 0.75, h * 1.00, 0.40),
        (h * 0.58, h * 0.92, 0.48),
    ):
        top = max(0, int(y_a))
        bottom = min(h, int(y_b))
        x0 = max(rx0, int(w * x_a))
        if bottom - top < 40:
            continue
        _add(img[top:bottom, x0:rx1], float(top), float(x0))
    return out


def _looks_like_notes_header_text(text: str) -> bool:
    t = " ".join((text or "").lower().split()).strip(":.")
    return t in {"notes", "hotes", "hote"} or t.startswith(("notes", "hotes"))


def _prepare_cdm_header_band_crops(img: np.ndarray, lines: List[OcrLine]) -> List[tuple]:
    """TERMINAL ID / BRANCH：DATE-TIME 行右侧与银行名下方。"""
    h, w = img.shape[:2]
    rx0, rx1 = _cdm_receipt_x_bounds(lines, w)
    out: List[tuple] = []
    seen = set()

    def _add(crop, top: float, left: float) -> None:
        if crop is None or crop.size == 0:
            return
        key = (int(top) // 12, int(left) // 12, crop.shape[0] // 12)
        if key in seen:
            return
        seen.add(key)
        out.append((crop, float(top), float(left)))

    y_date = min(_anchor_ys(lines, ["date"]), default=None)
    y_time = min(_anchor_ys(lines, ["time", "tiwe"]), default=None)
    y_trace = min(_anchor_ys(lines, ["trace"]), default=None)
    y0 = min(v for v in (y_date, y_time) if v is not None) if (y_date or y_time) else h * 0.22
    y1 = y_trace if y_trace is not None else y0 + h * 0.12
    # TERMINAL 在 TIME 右侧（诊断裁 term）；上扩避免切掉 TERMINAL 标签
    x_term = int(w * 0.42)
    for ya, yb, xa in (
        (y0 - 100, y1 + 40, x_term),
        (y0 - 140, y1 + 80, int(w * 0.38)),
        (max(0, y0 - h * 0.10), min(h, y1 + 20), int(w * 0.40)),
        (max(0, y0 - h * 0.08), y0 + 40, rx0),  # BRANCH 在 DATE 上方
        (h * 0.12, h * 0.32, rx0),
        (h * 0.15, h * 0.36, int(w * 0.40)),
    ):
        top = max(0, int(ya))
        bottom = min(h, int(yb))
        left = max(rx0, int(xa))
        if bottom - top < 40:
            continue
        _add(img[top:bottom, left:rx1], float(top), float(left))
    return out


def _cdm_band_prep_variants(crop_img: np.ndarray, heavy: bool = False) -> List[np.ndarray]:
    """复检预处理。默认轻量（原图+CLAHE+锐化）；heavy 才上二值，避免上百次空跑。"""
    out = [crop_img]
    if len(crop_img.shape) == 3:
        gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = crop_img
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    out.append(enhanced)
    blur = cv2.GaussianBlur(enhanced, (0, 0), 1.0)
    sharp = cv2.addWeighted(enhanced, 1.6, blur, -0.6, 0)
    out.append(sharp)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 1))
    out.append(cv2.morphologyEx(sharp, cv2.MORPH_CLOSE, h_kernel, iterations=1))
    if not heavy:
        return out
    binary = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    out.append(binary)
    out.append(cv2.morphologyEx(binary, cv2.MORPH_CLOSE, h_kernel, iterations=1))
    _, otsu = cv2.threshold(sharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    out.append(otsu)
    kernel = np.ones((2, 2), np.uint8)
    out.append(cv2.dilate(binary, kernel, iterations=1))
    out.append(cv2.bitwise_not(binary))
    return out


def _pad_crop_for_ocr(
    crop_img: np.ndarray, top: float, left: float, pad: int = 24
) -> tuple:
    """Paddle 检测器对无边距细条常漏字；白边 padding 后偏移回推。"""
    if crop_img is None or crop_img.size == 0:
        return crop_img, top, left
    if len(crop_img.shape) == 3:
        value = (255, 255, 255)
    else:
        value = 255
    padded = cv2.copyMakeBorder(
        crop_img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=value
    )
    return padded, float(top) - pad, float(left) - pad


def _run_cdm_band_ocr(
    engine,
    crop_img: np.ndarray,
    top: float,
    left: float,
    scales: tuple,
    heavy: bool = False,
) -> List[OcrLine]:
    found: List[OcrLine] = []
    crop_img, top, left = _pad_crop_for_ocr(crop_img, top, left)
    for prep in _cdm_band_prep_variants(crop_img, heavy=heavy):
        for scale in scales:
            work = prep
            if scale != 1.0:
                work = cv2.resize(
                    prep, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
                )
            raw = engine.recognize(work)
            found = dedup_lines(
                found + _offset_ocr_lines(raw, dy=top, dx=left, scale=scale)
            )
    return found


def _run_cdm_direct_line_windows(
    engine, img: np.ndarray, windows: List[tuple]
) -> List[OcrLine]:
    """对已知单行窗口跳过 detector，直接调用 Paddle recognition model。"""
    recognize_line = getattr(engine, "recognize_line", None)
    if not callable(recognize_line):
        return []
    h, w = img.shape[:2]
    found: List[OcrLine] = []
    for x0, y0, x1, y1 in windows:
        left, right = max(0, int(x0)), min(w, int(x1))
        top, bottom = max(0, int(y0)), min(h, int(y1))
        if right - left < 40 or bottom - top < 24:
            continue
        crop = img[top:bottom, left:right]
        if crop.size == 0:
            continue
        padded, ptop, pleft = _pad_crop_for_ocr(crop, top, left, pad=16)
        # 原图与 CLAHE 各直读一次；检测器路径再负责其它增强，避免过多调用。
        preps = _cdm_band_prep_variants(padded, heavy=False)[:2]
        for prep in preps:
            raw = recognize_line(prep)
            found = dedup_lines(
                found + _offset_ocr_lines(raw, dy=ptop, dx=pleft, scale=1.0)
            )
    return found


def _cdm_party_direct_windows(img: np.ndarray, lines: List[OcrLine]) -> List[tuple]:
    """TRANSACTION→NOTES 内固定字段行：ACCOUNT/CUSTOMER/NARRATION/MOBILE/SOURCE。"""
    h, w = img.shape[:2]
    rx0, rx1 = _cdm_receipt_x_bounds(lines, w)
    party_x1 = min(rx1, max(rx0 + int((rx1 - rx0) * 0.84), int(w * 0.66)))
    y_txn = min(
        _anchor_ys(lines, ["transaction", "cardless"]),
        default=min(_anchor_ys(lines, ["trace"]), default=h * 0.38) + h * 0.06,
    )
    y_notes = min(
        _anchor_ys(lines, ["notes", "hotes", "value"]),
        default=h * 0.71,
    )
    span = y_notes - y_txn
    if span < 300:
        span = h * 0.28
        y_notes = min(h, y_txn + span)
    # 单行直读不得夹入下一行；热敏字高约 70–90px。
    half = max(52.0, min(68.0, span * 0.05))
    centers = (0.15, 0.28, 0.49, 0.69, 0.84)
    return [
        (rx0, y_txn + span * frac - half, party_x1, y_txn + span * frac + half)
        for frac in centers
    ]


def _cdm_amount_direct_windows(img: np.ndarray, lines: List[OcrLine]) -> List[tuple]:
    """NOTES 后右侧金额行：各面额小计、DEPOSIT AMOUNT、STATUS。"""
    h, w = img.shape[:2]
    rx0, rx1 = _cdm_receipt_x_bounds(lines, w)
    y_notes = min(
        _anchor_ys(lines, ["notes", "hotes", "value", "amount"]),
        default=h * 0.68,
    )
    left = max(rx0, int(w * 0.34))
    # 以票高归一化，覆盖 400/1000/10000、11,400 和状态行。
    offsets = (0.040, 0.065, 0.090, 0.132, 0.170)
    half = max(50.0, min(62.0, h * 0.0135))
    return [
        (left, y_notes + h * frac - half, rx1, y_notes + h * frac + half)
        for frac in offsets
    ]


def _cdm_header_direct_windows(img: np.ndarray, lines: List[OcrLine]) -> List[tuple]:
    """DATE/TIME/TERMINAL 的值行分三列直读，避免 17:00 噪声抢占 08:03。"""
    h, w = img.shape[:2]
    rx0, rx1 = _cdm_receipt_x_bounds(lines, w)
    labels = [
        ln
        for ln in lines
        if _norm_main_label(ln.text) in {"date", "time", "terminalid", "terminal"}
    ]
    label_bottoms = [max(p[1] for p in ln.box) for ln in labels]
    y_trace = min(_anchor_ys(lines, ["trace"]), default=h * 0.37)
    # 各列标签有倾斜，取最早底边并上扩，避免切掉 08:03 / TERMINAL 首行。
    y0 = min(label_bottoms, default=y_trace - h * 0.075) - 15
    # TRACE 数值在标签上方，至少留约 2% 票高间隔，避免和 TIME 合成一行。
    y1 = y_trace - max(35.0, h * 0.02)
    if y1 - y0 < 50:
        y0, y1 = y_trace - h * 0.07, y_trace - 10
    date_lines = [ln for ln in labels if _norm_main_label(ln.text) == "date"]
    time_lines = [ln for ln in labels if _norm_main_label(ln.text) == "time"]
    if date_lines and time_lines:
        date_cx = _line_center_x(date_lines[0].box)
        time_cx = _line_center_x(time_lines[0].box)
        gap = max(180.0, time_cx - date_cx)
        boundary = (date_cx + time_cx) / 2
        # TERMINAL 列约在 TIME 右一列；允许与 TIME 少量重叠，避免 ID 首字被切。
        return [
            (max(rx0, date_cx - gap * 0.55), y0, boundary, y1),
            (boundary, y0, min(rx1, time_cx + gap * 0.65), y1),
            (max(rx0, time_cx + gap * 0.50), y0, rx1, y1),
        ]
    span_x = rx1 - rx0
    cuts = (0.0, 0.27, 0.50, 1.0)
    return [
        (rx0 + span_x * cuts[i], y0, rx0 + span_x * cuts[i + 1], y1)
        for i in range(3)
    ]


def _cdm_branch_direct_windows(img: np.ndarray, lines: List[OcrLine]) -> List[tuple]:
    """银行名下、DATE 上方的网点行（如 NAWALAPI-CRM1 BR）。"""
    h, w = img.shape[:2]
    rx0, rx1 = _cdm_receipt_x_bounds(lines, w)
    y_date = min(_anchor_ys(lines, ["date"]), default=h * 0.31)
    center = y_date - h * 0.09
    half = max(55.0, min(80.0, h * 0.017))
    return [(rx0, center - half, rx1, center + half)]


def _norm_main_label(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _priority_cdm_party_crops(img: np.ndarray, lines: List[OcrLine]) -> List[tuple]:
    """优先中高裁：TRANSACTION→NOTES 整段（诊断 party_mid），Paddle 需要上下文。"""
    h, w = img.shape[:2]
    rx0, rx1 = _cdm_receipt_x_bounds(lines, w)
    party_x1 = min(rx1, max(rx0 + int((rx1 - rx0) * 0.82), int(w * 0.65)))
    y_txn = min(_anchor_ys(lines, ["transaction", "cardless", "trace"]), default=h * 0.35)
    y_notes = min(_anchor_ys(lines, ["notes", "hotes", "value"]), default=h * 0.70)
    y0 = max(0, int(y_txn - 20))
    y1 = min(h, int(y_notes + 10))
    out: List[tuple] = []
    if y1 - y0 >= 80:
        # 整段 + 上半（ACCOUNT/CUSTOMER 常在 TRANSACTION 下 0–55%）
        for ya, yb in (
            (y0, y1),
            (y0, y0 + int((y1 - y0) * 0.55)),
            (y0 + int((y1 - y0) * 0.15), y0 + int((y1 - y0) * 0.70)),
        ):
            crop = img[ya:yb, rx0:party_x1]
            if crop.size:
                out.append((crop, float(ya), float(rx0)))
    return out


def _priority_cdm_amount_crops(img: np.ndarray, lines: List[OcrLine]) -> List[tuple]:
    """优先右列 AMOUNT + 底部 LKR 总额（诊断 notes_right / amt_lkr）。

    注意：11,400 / 10,000 左缘常比 AMOUNT 表头更靠左，col 起点须再左移。
    """
    h, w = img.shape[:2]
    rx0, rx1 = _cdm_receipt_x_bounds(lines, w)
    y_notes = min(_anchor_ys(lines, ["notes", "hotes", "value", "amount"]), default=h * 0.65)
    amount_lefts = [
        min(p[0] for p in ln.box)
        for ln in lines
        if ln.text.strip().lower().rstrip(":.").startswith("amount")
    ]
    # 表头左缘再左偏，避免裁掉 10,000 / 11,400 千位
    col_x0 = int(min(amount_lefts) - 220) if amount_lefts else int(w * 0.42)
    col_x0 = max(rx0, min(col_x0, int(w * 0.55)))
    y0 = max(0, int(y_notes - 30))
    out: List[tuple] = []
    for ya, yb, xa in (
        (y0, h, col_x0),
        (y0, min(h, y0 + int(h * 0.28)), col_x0),
        (int(h * 0.70), h, max(rx0, int(w * 0.32))),
        (int(h * 0.78), h, max(rx0, col_x0 - 120)),
        (int(h * 0.78), h, max(rx0, int(w * 0.38))),
    ):
        top, bottom = max(0, ya), min(h, yb)
        left = max(0, xa)
        if bottom - top < 40:
            continue
        crop = img[top:bottom, left:rx1]
        if crop.size:
            out.append((crop, float(top), float(left)))
    return out


def _ocr_cdm_party_band(engine, img, lines: List[OcrLine]) -> List[OcrLine]:
    """对 CDM 的 TRANSACTION~NARRATION 中间带二次 OCR，补账号/户名。"""
    found = _run_cdm_direct_line_windows(
        engine, img, _cdm_party_direct_windows(img, lines)
    )
    if _has_strong_cdm_account(found):
        return found
    # 1) 中高优先裁 + 轻量预处理（原先细条×重预处理把账号跑丢且极慢）
    for crop, top, left in _priority_cdm_party_crops(img, lines):
        found = dedup_lines(
            found + _run_cdm_band_ocr(engine, crop, top, left, (1.5, 2.0, 2.5))
        )
        if _has_strong_cdm_account(found):
            return found
    # 2) 细条/宽窗兜底，仍限轻量
    for crop, top, left in _prepare_cdm_band_crops(img, lines)[:10]:
        scales = (2.0, 2.5) if crop.shape[0] < 220 else (1.5, 2.0)
        found = dedup_lines(
            found + _run_cdm_band_ocr(engine, crop, top, left, scales)
        )
        if _has_strong_cdm_account(found):
            return found
    # 3) 仍无账号时对优先裁加重预处理一次
    if not _has_strong_cdm_account(found):
        for crop, top, left in _priority_cdm_party_crops(img, lines)[:2]:
            found = dedup_lines(
                found
                + _run_cdm_band_ocr(engine, crop, top, left, (2.0, 2.5), heavy=True)
            )
            if _has_strong_cdm_account(found):
                return found
    return found


def _ocr_cdm_amount_band(engine, img, lines: List[OcrLine]) -> List[OcrLine]:
    """复检 CDM DEPOSIT AMOUNT / 面额表区域。"""
    found = _run_cdm_direct_line_windows(
        engine, img, _cdm_amount_direct_windows(img, lines)
    )
    if _has_cdm_deposit_amount_text(found):
        return found
    for crop, top, left in _priority_cdm_amount_crops(img, lines):
        found = dedup_lines(
            found + _run_cdm_band_ocr(engine, crop, top, left, (1.5, 2.0, 2.5))
        )
        if _has_cdm_deposit_amount_text(found):
            return found
    for crop, top, left in _prepare_cdm_amount_band_crops(img, lines)[:8]:
        found = dedup_lines(
            found + _run_cdm_band_ocr(engine, crop, top, left, (2.0, 2.5))
        )
        if _has_cdm_deposit_amount_text(found):
            return found
    if not _has_cdm_deposit_amount_text(found):
        for crop, top, left in _priority_cdm_amount_crops(img, lines)[:2]:
            found = dedup_lines(
                found
                + _run_cdm_band_ocr(engine, crop, top, left, (2.0, 2.5), heavy=True)
            )
            if _has_cdm_deposit_amount_text(found):
                return found
    return found


def _has_cdm_terminal_text(lines: List[OcrLine]) -> bool:
    blob = " ".join(ln.text for ln in lines)
    if re.search(r"(?i)terminal", blob):
        return True
    return any(
        re.fullmatch(r"[A-Z]{1,3}[A-Z0-9]{5,12}", ln.text.strip().upper())
        for ln in lines
    )


def _ocr_cdm_header_band(engine, img, lines: List[OcrLine]) -> List[OcrLine]:
    """复检 TERMINAL ID / BRANCH。"""
    found = _run_cdm_direct_line_windows(
        engine,
        img,
        _cdm_header_direct_windows(img, lines)
        + _cdm_branch_direct_windows(img, lines),
    )
    if _has_cdm_terminal_text(found):
        return found
    for crop, top, left in _prepare_cdm_header_band_crops(img, lines)[:6]:
        found = dedup_lines(
            found + _run_cdm_band_ocr(engine, crop, top, left, (1.5, 2.0, 2.5))
        )
        if _has_cdm_terminal_text(found):
            return found
    return found


def _variant_img(variants: List[dict], name: str):
    for v in variants:
        if v.get("name") == name:
            return v["img"]
    return variants[0]["img"]


def _boc_missing_hero_amount(result) -> bool:
    """BOC Transaction Details 已识别但漏了顶部大额 Transfer Amount。"""
    fields = result.fields or {}
    if not fields.get("Receiver's Account No") and not fields.get("Sender's Account No"):
        return False
    if fields.get("Transfer Amount"):
        return False
    if result.amount is None:
        return True
    fee = _parse_money(fields["Fees & Charges"]) if fields.get("Fees & Charges") else None
    if fee is not None and abs(result.amount - fee) < 0.01:
        return True
    return False


def _has_boc_hero_amount_text(lines: List[OcrLine], fee_hint: Optional[float] = None) -> bool:
    for ln in lines:
        low = ln.text.lower()
        if "fee" in low or "charge" in low:
            continue
        if not re.search(r"(?i)\blkr\b", ln.text) and not re.search(
            r"\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2}", ln.text
        ):
            continue
        m = _parse_money(ln.text)
        if m is None or m < 100:
            continue
        if fee_hint is not None and abs(m - fee_hint) < 0.01:
            continue
        return True
    return False


def _boc_amount_band_windows(img: np.ndarray, lines: List[OcrLine]) -> List[tuple]:
    """标题到 Receiver 之间的多个裁剪窗；(crop, top, left)。"""
    h, w = img.shape[:2]
    scale_y = _anchor_scale_y(float(h), lines)
    y0 = h * 0.06
    y1 = h * 0.30
    for ln in lines:
        low = ln.text.lower()
        if "transaction detail" in low:
            y0 = max(p[1] for p in ln.box) * scale_y
        if "receiver" in low and "account" in low:
            y1 = min(y1, min(p[1] for p in ln.box) * scale_y)
    if y1 <= y0 + 30:
        y0, y1 = h * 0.08, h * 0.28
    windows = [
        # 全宽标题~Receiver
        (y0, y1, w * 0.05, w * 0.95),
        # 居中大额（避开右上反光）
        (y0, y1, w * 0.15, w * 0.85),
        (y0 + (y1 - y0) * 0.1, y0 + (y1 - y0) * 0.85, w * 0.20, w * 0.80),
        # 固定比例兜底
        (h * 0.08, h * 0.28, w * 0.12, w * 0.88),
        (h * 0.10, h * 0.26, w * 0.18, w * 0.82),
    ]
    out = []
    seen = set()
    for ya, yb, xa, xb in windows:
        top = max(0, int(ya))
        bottom = min(h, int(yb))
        left = max(0, int(xa))
        right = min(w, int(xb))
        if bottom - top < 30 or right - left < 40:
            continue
        key = (top // 10, bottom // 10, left // 20)
        if key in seen:
            continue
        seen.add(key)
        crop = img[top:bottom, left:right]
        if crop.size:
            out.append((crop, float(top), float(left)))
    return out


def _boc_amount_prep_variants(crop_img: np.ndarray) -> List[np.ndarray]:
    """抗反光预处理：CLAHE、压高光、提蓝字、二值。"""
    out = [crop_img]
    if len(crop_img.shape) == 3:
        bgr = crop_img
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        # BOC 金额多为蓝色大字：强化 B 通道
        b, g, r = cv2.split(bgr)
        blue_emph = cv2.addWeighted(b, 1.4, gray, -0.2, 0)
        out.append(blue_emph)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        # 压掉过曝反光后再 OCR
        v = hsv[:, :, 2]
        v = np.clip(v, 0, 220).astype(np.uint8)
        hsv2 = hsv.copy()
        hsv2[:, :, 2] = v
        out.append(cv2.cvtColor(hsv2, cv2.COLOR_HSV2BGR))
    else:
        gray = crop_img
    clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    out.append(enhanced)
    binary = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 9
    )
    out.append(binary)
    out.append(cv2.bitwise_not(binary))
    return out


def _ocr_boc_amount_band(engine, img, lines: List[OcrLine]) -> List[OcrLine]:
    """复检 BOC Transaction Details 顶部大额（标题 ~ Receiver's Account 之间）。"""
    found: List[OcrLine] = []

    def _run(crop_img: np.ndarray, top: float, left: float, scale: float) -> List[OcrLine]:
        work = crop_img
        if scale != 1.0:
            work = cv2.resize(
                crop_img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
            )
        raw = engine.recognize(work)
        return _offset_ocr_lines(raw, dy=top, dx=left, scale=scale)

    for crop, top, left in _boc_amount_band_windows(img, lines):
        for prep in _boc_amount_prep_variants(crop):
            for scale in (1.0, 2.0, 2.5):
                found = dedup_lines(found + _run(prep, top, left, scale))
                if _has_boc_hero_amount_text(found):
                    return found
    return found


def _ntb_needs_description_band(result, lines: List[OcrLine]) -> bool:
    """NTB Description 仍粘 Nations 水印（NatiPU8QAW / 3 Nat PU8QAW）时复检。"""
    if (result.bank or "").lower() != "ntb":
        return False
    desc = (result.fields or {}).get("Description") or ""
    # 已是干净短码（PU8QAW）或无水印正文则跳过
    if desc and not _ntb_description_contaminated(desc):
        return False
    if _ntb_description_contaminated(desc):
        return True
    for ln in lines:
        t = ln.text.strip()
        if re.match(r"(?i)^(?:\d+\s*)?(?:nati|nat|nations?).+\d", t):
            return True
    return False


def _has_clean_ntb_description(lines: List[OcrLine]) -> bool:
    for ln in lines:
        if _is_ntb_watermark_text(ln.text):
            continue
        scrubbed = _scrub_ntb_watermark_glue(ln.text)
        if not scrubbed or _ntb_description_contaminated(scrubbed):
            continue
        if _is_ntb_description_code(scrubbed):
            return True
        if re.fullmatch(r"[A-Za-z][A-Za-z\s.'-]{1,40}", scrubbed) and len(scrubbed) >= 4:
            if scrubbed.lower() not in {"description", "success", "status", "bank"}:
                return True
    return False


def _prepare_ntb_description_crops(img: np.ndarray, lines: List[OcrLine]) -> List[tuple]:
    h, w = img.shape[:2]
    y0, y1 = h * 0.62, h * 0.78
    for ln in lines:
        if "description" in ln.text.lower():
            cy = sum(p[1] for p in ln.box) / 4.0
            y0 = max(0.0, cy - h * 0.03)
            y1 = min(float(h), cy + h * 0.04)
            break
    windows = [
        (y0, y1, w * 0.45, w * 0.98),
        (y0, y1, w * 0.55, w * 0.99),
        (y0 - h * 0.01, y1 + h * 0.01, w * 0.40, w * 0.99),
    ]
    out = []
    seen = set()
    for ya, yb, xa, xb in windows:
        top = max(0, int(ya))
        bottom = min(h, int(yb))
        left = max(0, int(xa))
        right = min(w, int(xb))
        if bottom - top < 20 or right - left < 40:
            continue
        key = (top // 8, bottom // 8, left // 20)
        if key in seen:
            continue
        seen.add(key)
        crop = img[top:bottom, left:right]
        if crop.size:
            out.append((crop, float(top), float(left)))
    return out


def _ntb_desc_prep_variants(crop_img: np.ndarray) -> List[np.ndarray]:
    """压浅色水印、强化深色正文。"""
    out = [crop_img]
    if len(crop_img.shape) == 3:
        gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = crop_img
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    out.append(enhanced)
    # 浅灰水印抬亮后二值，保留深字
    blur = cv2.GaussianBlur(enhanced, (3, 3), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    out.append(binary)
    out.append(cv2.bitwise_not(binary))
    adaptive = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 7
    )
    out.append(adaptive)
    return out


def _ocr_ntb_description_band(engine, img, lines: List[OcrLine]) -> List[OcrLine]:
    found: List[OcrLine] = []

    def _run(crop_img: np.ndarray, top: float, left: float, scale: float) -> List[OcrLine]:
        work = crop_img
        if scale != 1.0:
            work = cv2.resize(
                crop_img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
            )
        raw = engine.recognize(work)
        return _offset_ocr_lines(raw, dy=top, dx=left, scale=scale)

    for crop, top, left in _prepare_ntb_description_crops(img, lines):
        for prep in _ntb_desc_prep_variants(crop):
            for scale in (1.5, 2.0, 2.5):
                found = dedup_lines(found + _run(prep, top, left, scale))
                if _has_clean_ntb_description(found):
                    return found
    return found


def _recognize(buf: bytes, include_lines: bool = False) -> Dict[str, Any]:
    settings = get_settings()
    if len(buf) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="文件过大")
    t0 = time.perf_counter()
    img = load_image(buf)
    variants = build_variants(img)
    lines: List[OcrLine] = []
    for variant in variants:
        lines.extend(_engine.recognize(variant["img"]))

    unique = dedup_lines(lines)

    result = extract(unique, include_lines=False)
    # CDM 复检只用未纠偏原图：框坐标来自多 variant 混合，套到 rotate 后的 color 会裁空
    _cdm_band_variants = ("color_raw", "enhanced")
    # CDM 中间段（ACCOUNT/CUSTOMER）易被拇指/倾角/合成截图漏检或截断：对中间带复检
    if _cdm_missing_party_fields(result):
        extras: List[OcrLine] = []
        for name in _cdm_band_variants:
            extras.extend(_ocr_cdm_party_band(_engine, _variant_img(variants, name), unique))
            probe = dedup_lines(unique + extras)
            probe_result = extract(probe, include_lines=False)
            if not _cdm_missing_party_fields(probe_result):
                unique = probe
                result = extract(unique, include_lines=include_lines)
                break
        else:
            if extras:
                unique = dedup_lines(unique + extras)
                result = extract(unique, include_lines=include_lines)
            elif include_lines:
                result = extract(unique, include_lines=True)
    # CDM DEPOSIT AMOUNT：远距/竖排常漏总额，对金额带复检
    if _cdm_missing_deposit_amount(result):
        extras = []
        for name in _cdm_band_variants:
            extras.extend(_ocr_cdm_amount_band(_engine, _variant_img(variants, name), unique))
            probe = dedup_lines(unique + extras)
            probe_result = extract(probe, include_lines=False)
            if not _cdm_missing_deposit_amount(probe_result):
                unique = probe
                result = extract(unique, include_lines=include_lines)
                break
        else:
            if extras:
                unique = dedup_lines(unique + extras)
                result = extract(unique, include_lines=include_lines)
    # CDM TERMINAL ID / BRANCH：并排表头右侧与网点行常漏
    if _cdm_missing_header_fields(result):
        extras = []
        for name in _cdm_band_variants:
            extras.extend(_ocr_cdm_header_band(_engine, _variant_img(variants, name), unique))
            probe = dedup_lines(unique + extras)
            probe_result = extract(probe, include_lines=False)
            if not _cdm_missing_header_fields(probe_result):
                unique = probe
                result = extract(unique, include_lines=include_lines)
                break
        else:
            if extras:
                unique = dedup_lines(unique + extras)
                result = extract(unique, include_lines=include_lines)
    # BOC Transaction Details：顶部 LKR 大额常被反光漏读
    if _boc_missing_hero_amount(result):
        extras = []
        for name in ("color_raw", "enhanced", "color"):
            extras.extend(_ocr_boc_amount_band(_engine, _variant_img(variants, name), unique))
            probe = dedup_lines(unique + extras)
            probe_result = extract(probe, include_lines=False)
            if not _boc_missing_hero_amount(probe_result):
                unique = probe
                result = extract(unique, include_lines=include_lines)
                break
        else:
            if extras:
                unique = dedup_lines(unique + extras)
                result = extract(unique, include_lines=False)
    # NTB：斜向水印粘进 Description（NatiPU8QAW），对描述行复检
    if _ntb_needs_description_band(result, unique):
        extras = []
        for name in ("color_raw", "enhanced", "color"):
            extras.extend(
                _ocr_ntb_description_band(_engine, _variant_img(variants, name), unique)
            )
            probe = dedup_lines(unique + extras)
            probe_result = extract(probe, include_lines=False)
            desc = (probe_result.fields or {}).get("Description")
            if desc and not _ntb_description_contaminated(desc) and len(str(desc)) >= 4:
                # 复检得到更完整描述时采用
                cur = (result.fields or {}).get("Description") or ""
                if len(str(desc)) >= len(str(cur)):
                    unique = probe
                    result = extract(unique, include_lines=include_lines)
                    break
        else:
            if extras:
                unique = dedup_lines(unique + extras)
                result = extract(unique, include_lines=include_lines)
    if include_lines and not result.lines:
        result = extract(unique, include_lines=True)

    result.elapsed_ms = (time.perf_counter() - t0) * 1000
    out: Dict[str, Any] = {"success": result.success}
    out.update(result.fields if result.fields else _structured_fallback(result))
    out["bank"] = result.bank.upper() if result.bank else ""
    if include_lines:
        out["lines"] = [l.dict() for l in result.lines]
    return out


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ocr", response_model=Dict[str, Any], response_model_exclude_none=True)
async def ocr(file: UploadFile = File(...), include_lines: bool = False):
    buf = await file.read()
    return _recognize(buf, include_lines=include_lines)


@app.post("/ocr_base64", response_model=Dict[str, Any], response_model_exclude_none=True)
async def ocr_base64(req: Base64Request, include_lines: bool = False):
    try:
        buf = base64.b64decode(req.image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="无效的 base64 图片数据")
    return _recognize(buf, include_lines=include_lines)


@app.post("/ocr_url", response_model=Dict[str, Any], response_model_exclude_none=True)
def ocr_url(req: UrlRequest, include_lines: bool = False):
    try:
        buf = fetch_image_bytes(req.image_url, get_settings())
    except UrlFetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _recognize(buf, include_lines=include_lines)
