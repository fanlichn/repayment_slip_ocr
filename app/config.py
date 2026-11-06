"""Application configuration.

All values can be overridden via environment variables prefixed with ``NIC_OCR_``
or via a ``.env`` file placed next to the application.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NIC_OCR_", extra="ignore")

    # ---- OCR engine ----
    # "paddle" (PP-OCR, recommended) or "tesseract"
    ocr_engine: str = "paddle"
    # PaddleOCR: "en"; Tesseract: "eng" (add "sin" for Sinhala if needed)
    ocr_lang: str = "en"
    paddle_use_gpu: bool = False
    paddle_use_angle_cls: bool = True
    # 0 表示保留 Paddle 默认值；生产环境应通过同机基准选择 1/2/4。
    paddle_cpu_threads: int = 0
    # None 表示保留 PaddleOCR 默认值。
    paddle_enable_mkldnn: Optional[bool] = None
    # 0 表示保留 OpenCV 默认线程设置。
    opencv_threads: int = 0
    # repayment 服务的二值 variant 使用轻量高斯降噪；false 可回滚到 NLM。
    fast_preprocessing: bool = True

    # ---- NIC decoding ----
    # "literal": read day-of-year code literally (Jan 1 == day 001)
    # "nic366":  compensate the fixed 366-day calendar used by SL NICs
    #            (recovers real DOB for non-leap-year births on/after 1 Mar).
    #            Default nic366 matches the printed DOB on real cards.
    nic_day_mode: str = "nic366"
    old_nic_century: int = 1900

    # ---- HTTP server ----
    host: str = "0.0.0.0"
    port: int = 8000
    max_upload_bytes: int = 15 * 1024 * 1024  # 15 MB
    workers: int = 2
    # 单 worker 共享一个非线程安全 Paddle predictor；默认整请求串行，避免请求间
    # 交错数十次推理并造成内存/尾延迟放大。多进程并发由 Uvicorn workers 提供。
    ocr_max_concurrent_requests_per_worker: int = 1

    # ---- Remote image fetching (POST /ocr_url) ----
    url_fetch_timeout_seconds: float = 10.0
    # False: reject URLs resolving to private/loopback addresses (SSRF guard)
    url_fetch_allow_private_hosts: bool = False
    # 仅向服务器日志写入分阶段耗时；不会改变 API JSON。
    stage_timing_log: bool = False
    # false 保留优化前 CDM 调用顺序，便于同版本 A/B 和紧急回滚。
    cdm_adaptive_early_stop: bool = True

    # ---- 多语言姓名第二引擎（僧伽罗语/泰米尔语） ----
    # "none": 关闭；"tesseract": 用 Tesseract sin+tam 补充识别（需安装系统语言包）
    name_ocr_engine: str = "tesseract"
    # Tesseract 语言串："sin+tam"；只需其中一种时可改为 "sin" 或 "tam"
    name_ocr_lang: str = "sin+tam"
    # Tesseract 页面分割模式（psm），整卡识别常用 6；漏检时可试 3 / 11
    name_tesseract_psm: int = 6
    # Tesseract 可执行文件路径；Linux 已在 PATH 时留空即可
    tesseract_cmd: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
