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


def _cdm_missing_party_fields(result) -> bool:
    """CDM 已识别但缺少账号/户名时，需要对中间带复检。"""
    fields = result.fields or {}
    is_cdm = (
        result.doc_type == "cash_deposit_slip"
        or str(fields.get("TRANSACTION", "")).upper().find("CARDLESS") >= 0
        or bool(fields.get("TERMINAL ID") and fields.get("DEPOSIT AMOUNT"))
    )
    if not is_cdm:
        return False
    return not fields.get("ACCOUNT NUMBER") or not fields.get("CUSTOMER NAME")


def _anchor_ys(lines: List[OcrLine], patterns: List[str]) -> List[float]:
    hits: List[float] = []
    for ln in lines:
        low = ln.text.lower()
        if any(p in low for p in patterns):
            hits.append(_line_center_y(ln.box))
    return hits


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


def _has_cdm_party_text(lines: List[OcrLine]) -> bool:
    """是否已读到账号/户名（不能把 CARDLESS DEPOSIT 误判为已有 party）。"""
    blob = " ".join(ln.text.lower() for ln in lines)
    if "account" in blob or "customer" in blob or "acc0unt" in blob:
        return True
    return re.search(r"(?<!\d)\d{8,14}(?!\d)", blob) is not None


def _prepare_cdm_band_crops(img: np.ndarray, lines: List[OcrLine]) -> List[tuple]:
    """生成若干中间带裁剪：(crop, top, left)。

    行框可能来自纠偏后的其它 variant，需按当前图高做比例映射；
    并收紧到 TRANSACTION 与 NARRATION 之间，避免只读到 CARDLESS 就停。
    """
    h, w = img.shape[:2]
    ref_h = max(_line_max_y(lines), float(h))
    scale_y = h / ref_h

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
    if y0 is not None and y1 is not None and y1 > y0 + 60:
        # 略缩进：跳过 TRANSACTION 行本身，聚焦 ACCOUNT/CUSTOMER
        span = y1 - y0
        windows.append((y0 + span * 0.12, y1 - span * 0.08))
        windows.append((y0 - h * 0.01, y1 + h * 0.01))
    # 固定比例兜底（手持 CDM 账号常在中上部）
    windows.extend(
        [
            (h * 0.32, h * 0.50),
            (h * 0.28, h * 0.55),
            (h * 0.35, h * 0.48),
        ]
    )

    left = max(0, int(w * 0.01))
    out: List[tuple] = []
    seen = set()
    for y_a, y_b in windows:
        top = max(0, int(y_a))
        bottom = min(h, int(y_b))
        if bottom - top < 40:
            continue
        key = (top // 20, bottom // 20)
        if key in seen:
            continue
        seen.add(key)
        crop = img[top:bottom, left:w]
        if crop.size == 0:
            continue
        out.append((crop, float(top), float(left)))
    return out


def _ocr_cdm_party_band(engine, img, lines: List[OcrLine]) -> List[OcrLine]:
    """对 CDM 的 TRANSACTION~NARRATION 中间带二次 OCR，补账号/户名。

    多窗口 + CLAHE/放大：首轮常只能读到 CARDLESS，必须在未见账号数字时继续加强。
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

    def _variants(crop_img: np.ndarray) -> List[np.ndarray]:
        out = [crop_img]
        if len(crop_img.shape) == 3:
            gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop_img
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        out.append(enhanced)
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
        )
        out.append(binary)
        return out

    for crop, top, left in _prepare_cdm_band_crops(img, lines):
        for prep in _variants(crop):
            found = dedup_lines(found + _run(prep, top, left, 1.0))
            if _has_cdm_party_text(found):
                return found
            found = dedup_lines(found + _run(prep, top, left, 2.0))
            if _has_cdm_party_text(found):
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
            r"\d{1,3}(?:,\d{3})+\.\d{2}", ln.text
        ):
            continue
        m = _parse_money(ln.text)
        if m is None or m < 100:
            continue
        if fee_hint is not None and abs(m - fee_hint) < 0.01:
            continue
        return True
    return False


def _ocr_boc_amount_band(engine, img, lines: List[OcrLine]) -> List[OcrLine]:
    """复检 BOC Transaction Details 顶部大额（标题 ~ Receiver's Account 之间）。"""
    h, w = img.shape[:2]
    ref_h = max(_line_max_y(lines), float(h))
    scale_y = h / ref_h
    y0 = h * 0.04
    y1 = h * 0.32
    for ln in lines:
        low = ln.text.lower()
        if "transaction detail" in low:
            y0 = max(p[1] for p in ln.box) * scale_y
        if "receiver" in low and "account" in low:
            y1 = min(y1, min(p[1] for p in ln.box) * scale_y)
    if y1 <= y0 + 30:
        y0, y1 = h * 0.05, h * 0.30
    top = max(0, int(y0) - int(h * 0.01))
    bottom = min(h, int(y1) + int(h * 0.01))
    left = max(0, int(w * 0.05))
    right = min(w, int(w * 0.95))
    crop = img[top:bottom, left:right]
    if crop.size == 0:
        return []

    def _run(crop_img: np.ndarray, scale: float) -> List[OcrLine]:
        work = crop_img
        if scale != 1.0:
            work = cv2.resize(
                crop_img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
            )
        raw = engine.recognize(work)
        return _offset_ocr_lines(raw, dy=float(top), dx=float(left), scale=scale)

    found = _run(crop, 1.0)
    if not _has_boc_hero_amount_text(found):
        if len(crop.shape) == 3:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        found = dedup_lines(found + _run(enhanced, 1.0) + _run(enhanced, 2.0))
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
    # CDM 中间段（ACCOUNT/CUSTOMER）易被拇指/倾角漏检：对中间带复检
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
