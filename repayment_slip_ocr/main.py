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

from .extractor import _parse_money, dedup_lines, extract

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
    if fields.get("DEPOSIT AMOUNT") and result.amount is not None:
        return False
    if result.amount is not None and result.amount >= 100:
        return False
    return True


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
    for ln in lines:
        low = ln.text.lower()
        if "fee" in low or "charge" in low:
            continue
        if re.search(r"(?i)\bnotes\b|\bvalue\b", low) and "deposit" not in low:
            # 面额表头本身不算
            if not re.search(r"\d", ln.text):
                continue
        val = _parse_money(ln.text)
        if val is None or val < 100:
            continue
        if val in {20, 50, 100, 200, 500, 1000, 2000, 5000} and not re.search(
            r"(?i)lkr|rs\.?|[.,]\d{2}", ln.text
        ):
            continue
        if re.search(r"(?i)lkr|rs\.?|[.,]\d{2}", ln.text) or val >= 100:
            return True
    return False


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


def _prepare_cdm_band_crops(img: np.ndarray, lines: List[OcrLine]) -> List[tuple]:
    """生成若干中间带裁剪：(crop, top, left)。

    优先锚点并集（兼容竖排旋转收据）；再 TRANSACTION~NARRATION 水平带；
    最后固定比例窗口（正拍整页 CDM）。
    """
    h, w = img.shape[:2]
    scale_y = _anchor_scale_y(float(h), lines)

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
        # 并入账号附近的数字碎片框
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
            # 再扩一圈，照顾竖排值列在标签外侧
            crop, top, left = roi
            y0 = max(0, int(top - h * 0.03))
            x0 = max(0, int(left - w * 0.05))
            y1 = min(h, int(top + crop.shape[0] + h * 0.05))
            x1 = min(w, int(left + crop.shape[1] + w * 0.08))
            _add_crop(img[y0:y1, x0:x1], float(y0), float(x0))

    y0_hits = _anchor_ys(lines, ["cardless", "transaction"])
    y1_hits = _anchor_ys(lines, ["narration", "mobile", "source of funds", "notes", "value"])
    y0 = min(y0_hits) * scale_y if y0_hits else None
    y1 = None
    if y0 is not None and y1_hits:
        below = [y * scale_y for y in y1_hits if y * scale_y > y0 + 40]
        y1 = min(below) if below else min(y1_hits) * scale_y
    elif y1_hits:
        y1 = min(y1_hits) * scale_y

    windows: List[tuple] = []
    # 固定比例：正拍整页 CDM，EKALA 账号约在 0.34–0.45
    windows.extend(
        [
            (h * 0.34, h * 0.47),
            (h * 0.32, h * 0.50),
            (h * 0.30, h * 0.52),
            (h * 0.28, h * 0.55),
            # 合成截图里收据常在下半幅
            (h * 0.55, h * 0.85),
            (h * 0.60, h * 0.92),
            (h * 0.70, h * 0.98),
        ]
    )
    if y0 is not None and y1 is not None and y1 > y0 + 60:
        span = y1 - y0
        windows.append((y0 + span * 0.15, y1 - span * 0.10))
        windows.append((y0 + 20, y1 - 10))

    left = max(0, int(w * 0.01))
    for y_a, y_b in windows:
        top = max(0, int(y_a))
        bottom = min(h, int(y_b))
        if bottom - top < 40:
            continue
        _add_crop(img[top:bottom, left:w], float(top), float(left))
    return out


def _prepare_cdm_amount_band_crops(img: np.ndarray, lines: List[OcrLine]) -> List[tuple]:
    """DEPOSIT AMOUNT / NOTES 面额表区域裁剪。"""
    h, w = img.shape[:2]
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

    amt_boxes = _anchor_boxes(
        lines,
        [
            "deposit",
            "depusi",
            "amount",
            "mount",
            "notes",
            "value",
            "lkr",
            "successful",
            "status",
        ],
    )
    if amt_boxes:
        roi = _roi_from_boxes(img, amt_boxes, pad_x=0.08, pad_y=0.06)
        if roi:
            _add(*roi)
    # 正拍：下部金额带；合成图：右下/底部收据区
    left = max(0, int(w * 0.01))
    for y_a, y_b, x_a in (
        (h * 0.55, h * 0.92, 0.01),
        (h * 0.65, h * 0.98, 0.01),
        (h * 0.70, h * 0.99, 0.20),
        (h * 0.45, h * 0.85, 0.25),
    ):
        top = max(0, int(y_a))
        bottom = min(h, int(y_b))
        x0 = max(0, int(w * x_a))
        if bottom - top < 40:
            continue
        _add(img[top:bottom, x0:w], float(top), float(x0))
    return out


def _cdm_band_prep_variants(crop_img: np.ndarray) -> List[np.ndarray]:
    out = [crop_img]
    if len(crop_img.shape) == 3:
        gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = crop_img
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    out.append(enhanced)
    binary = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    out.append(binary)
    kernel = np.ones((2, 2), np.uint8)
    out.append(cv2.dilate(binary, kernel, iterations=1))
    out.append(cv2.bitwise_not(binary))
    return out


def _ocr_cdm_party_band(engine, img, lines: List[OcrLine]) -> List[OcrLine]:
    """对 CDM 的 TRANSACTION~NARRATION 中间带二次 OCR，补账号/户名。

    多窗口 + CLAHE/二值/加粗 + 放大：热敏字细、首轮常漏 ACCOUNT 行。
    """
    found: List[OcrLine] = []

    def _run(crop_img: np.ndarray, top: float, left: float, scale: float) -> List[OcrLine]:
        work = crop_img
        if scale != 1.0:
            work = cv2.resize(
                crop_img,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC,
            )
        raw = engine.recognize(work)
        return _offset_ocr_lines(raw, dy=top, dx=left, scale=scale)

    for crop, top, left in _prepare_cdm_band_crops(img, lines):
        for prep in _cdm_band_prep_variants(crop):
            for scale in (1.0, 2.0, 2.5):
                found = dedup_lines(found + _run(prep, top, left, scale))
                if _has_strong_cdm_account(found):
                    return found
    return found


def _ocr_cdm_amount_band(engine, img, lines: List[OcrLine]) -> List[OcrLine]:
    """复检 CDM DEPOSIT AMOUNT / 面额表区域。"""
    found: List[OcrLine] = []

    def _run(crop_img: np.ndarray, top: float, left: float, scale: float) -> List[OcrLine]:
        work = crop_img
        if scale != 1.0:
            work = cv2.resize(
                crop_img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
            )
        raw = engine.recognize(work)
        return _offset_ocr_lines(raw, dy=top, dx=left, scale=scale)

    for crop, top, left in _prepare_cdm_amount_band_crops(img, lines):
        for prep in _cdm_band_prep_variants(crop):
            for scale in (1.0, 2.0, 2.5):
                found = dedup_lines(found + _run(prep, top, left, scale))
                if _has_cdm_deposit_amount_text(found):
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
    # CDM 中间段（ACCOUNT/CUSTOMER）易被拇指/倾角/合成截图漏检或截断：对中间带复检
    if _cdm_missing_party_fields(result):
        # 先未纠偏原图，再 enhanced；纠偏色图常把中间行读丢
        extras: List[OcrLine] = []
        for name in ("color_raw", "enhanced", "color"):
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
        for name in ("color_raw", "enhanced", "color"):
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
