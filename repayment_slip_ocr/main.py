"""还款/转账凭证信息提取 FastAPI 服务。

复用 sri_lanka_nic_ocr 的图像预处理、OCR 引擎与远程图片下载（含 SSRF 防护），
与身份证主服务相互独立，可单独部署。
"""
from __future__ import annotations

import base64
import binascii
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import get_settings
from app.ocr_engine import create_engine
from app.preprocessing import build_variants, load_image
from app.url_fetch import UrlFetchError, fetch_image_bytes

from .extractor import extract
from .schemas import RepaymentResult

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


def _recognize(buf: bytes) -> RepaymentResult:
    settings = get_settings()
    if len(buf) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="文件过大")
    t0 = time.perf_counter()
    img = load_image(buf)
    lines = []
    for variant in build_variants(img):
        lines.extend(_engine.recognize(variant["img"]))

    dedup = {}
    for ln in lines:
        key = ln.text.strip().lower()
        if not key:
            continue
        if key not in dedup or ln.confidence > dedup[key].confidence:
            dedup[key] = ln
    unique = sorted(dedup.values(), key=lambda l: l.confidence, reverse=True)

    result = extract(unique)
    result.elapsed_ms = (time.perf_counter() - t0) * 1000
    return result


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ocr", response_model=RepaymentResult, response_model_exclude_none=True)
async def ocr(file: UploadFile = File(...)):
    buf = await file.read()
    return _recognize(buf)


@app.post("/ocr_base64", response_model=RepaymentResult, response_model_exclude_none=True)
async def ocr_base64(req: Base64Request):
    try:
        buf = base64.b64decode(req.image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="无效的 base64 图片数据")
    return _recognize(buf)


@app.post("/ocr_url", response_model=RepaymentResult, response_model_exclude_none=True)
def ocr_url(req: UrlRequest):
    try:
        buf = fetch_image_bytes(req.image_url, get_settings())
    except UrlFetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _recognize(buf)