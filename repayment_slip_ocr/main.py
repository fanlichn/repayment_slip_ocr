"""还款/转账凭证信息提取 FastAPI 服务。

复用 sri_lanka_nic_ocr 的图像预处理、OCR 引擎与远程图片下载（含 SSRF 防护），
与身份证主服务相互独立，可单独部署。
"""
from __future__ import annotations

import base64
import binascii
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import get_settings
from app.logging_setup import setup_logging
from app.ocr_engine import OcrLine, create_engine
from app.preprocessing import build_variants, load_image
from app.url_fetch import UrlFetchError, fetch_image_bytes

from .extractor import dedup_lines, extract

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


def _anchor_y(lines: List[OcrLine], patterns: List[str]) -> Optional[float]:
    for ln in lines:
        low = ln.text.lower()
        if any(p in low for p in patterns):
            return _line_center_y(ln.box)
    return None


def _offset_ocr_lines(lines: List[OcrLine], dy: float, dx: float = 0.0) -> List[OcrLine]:
    out: List[OcrLine] = []
    for ln in lines:
        box = [[p[0] + dx, p[1] + dy] for p in ln.box]
        out.append(OcrLine(text=ln.text, confidence=ln.confidence, box=box))
    return out


def _ocr_cdm_party_band(engine, img, lines: List[OcrLine]) -> List[OcrLine]:
    """对 CDM 的 TRANSACTION~NARRATION/NOTES 中间带二次 OCR，补账号/户名。"""
    h, w = img.shape[:2]
    y0 = _anchor_y(lines, ["cardless", "transaction"])
    y1 = _anchor_y(lines, ["narration", "mobile", "source of funds", "notes", "value"])
    if y0 is None or y1 is None or y1 <= y0 + 60:
        y0 = h * 0.30
        y1 = h * 0.58
    pad = int(h * 0.02)
    top = max(0, int(y0) - pad)
    bottom = min(h, int(y1) + pad)
    if bottom - top < 50:
        return []
    # 左手拇指常挡左侧标签，右半+中间更易读出账号/户名
    left = int(w * 0.05)
    crop = img[top:bottom, left:w]
    if crop.size == 0:
        return []
    raw = engine.recognize(crop)
    return _offset_ocr_lines(raw, dy=float(top), dx=float(left))


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
    # CDM 中间段（ACCOUNT/CUSTOMER）易被拇指/倾角漏检：对中间带复检一次
    if _cdm_missing_party_fields(result):
        extra = _ocr_cdm_party_band(_engine, variants[0]["img"], unique)
        if extra:
            unique = dedup_lines(unique + extra)
            result = extract(unique, include_lines=include_lines)
        elif include_lines:
            result = extract(unique, include_lines=True)
    elif include_lines:
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
