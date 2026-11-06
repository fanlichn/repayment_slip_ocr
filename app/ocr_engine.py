"""OCR engines.

A thin abstraction over PaddleOCR (default, production-recommended) with an
optional Tesseract fallback. Both expose ``recognize(image) -> list[OcrLine]``.
"""
from __future__ import annotations

import gc
import logging
import threading
from dataclasses import dataclass
from typing import List

import cv2
import numpy as np


logger = logging.getLogger(__name__)


@dataclass
class OcrLine:
    text: str
    confidence: float
    box: List[List[float]]


class PaddleOcrEngine:
    def __init__(self, settings):
        self._settings = settings
        self._ocr = None
        # Paddle Predictor 不是线程安全的。FastAPI 的同步 endpoint 会在线程池
        # 并发调用同一个 engine，必须把初始化和整次推理都串行化。
        self._lock = threading.RLock()

    def _new_ocr(self):
        from paddleocr import PaddleOCR

        return PaddleOCR(
            use_angle_cls=self._settings.paddle_use_angle_cls,
            lang=self._settings.ocr_lang,
            use_gpu=self._settings.paddle_use_gpu,
            show_log=False,
        )

    def _ensure(self):
        if self._ocr is None:
            with self._lock:
                if self._ocr is None:
                    self._ocr = self._new_ocr()
        return self._ocr

    def warmup(self):
        self._ensure()

    @staticmethod
    def _bounded_image(image, max_side: int = 5000, max_pixels: int = 16_000_000):
        """限制 Paddle 输入，返回 ``(连续数组, 坐标恢复倍率)``。

        保留常见 4096×3072 原图的原始清晰度；只限制超过 16MP 的异常输入。
        检测输出框再映射回原坐标。
        """
        arr = np.asarray(image)
        if arr.ndim not in (2, 3) or arr.size == 0:
            return np.ascontiguousarray(arr), 1.0
        h, w = arr.shape[:2]
        scale = min(
            1.0,
            max_side / max(h, w),
            (max_pixels / float(h * w)) ** 0.5,
        )
        if scale < 0.999:
            arr = cv2.resize(
                arr,
                # floor，避免两个维度各自 round 后略超 max_pixels。
                (max(1, int(w * scale)), max(1, int(h * scale))),
                interpolation=cv2.INTER_AREA,
            )
        return np.ascontiguousarray(arr), (1.0 / scale if scale else 1.0)

    def _run(self, ocr, image):
        return ocr.ocr(image, cls=self._settings.paddle_use_angle_cls)

    def _run_line(self, ocr, image):
        return ocr.ocr(
            image,
            det=False,
            rec=True,
            cls=self._settings.paddle_use_angle_cls,
        )

    def _with_primitive_retry(self, runner, image):
        ocr = self._ensure()
        try:
            return runner(ocr, image)
        except RuntimeError as exc:
            if "could not execute a primitive" not in str(exc).lower():
                raise
            logger.warning("Paddle primitive 执行失败，重建 predictor 后重试一次")
            self._ocr = None
            del ocr
            gc.collect()
            self._ocr = self._new_ocr()
            return runner(self._ocr, image)

    def recognize(self, image) -> List[OcrLine]:
        bounded, restore = self._bounded_image(image)
        with self._lock:
            result = self._with_primitive_retry(self._run, bounded)
        lines: List[OcrLine] = []
        for page in result or []:
            if not page:
                continue
            for item in page:
                box, (text, conf) = item[0], item[1]
                mapped_box = [
                    [float(point[0]) * restore, float(point[1]) * restore]
                    for point in box
                ]
                lines.append(
                    OcrLine(
                        text=text or "",
                        confidence=float(conf),
                        box=mapped_box,
                    )
                )
        return lines

    def recognize_line(self, image) -> List[OcrLine]:
        """跳过文本检测，直接识别一个已裁好的单行区域。

        折痕热敏票常出现“字清晰但检测器不给框”。CDM 已知行带可直接交给
        recognition model，避免检测阶段漏掉 ACCOUNT / 11,400。
        """
        bounded, _ = self._bounded_image(image, max_side=3200, max_pixels=4_000_000)
        with self._lock:
            result = self._with_primitive_retry(self._run_line, bounded)

        pairs = []

        def _visit(node):
            if isinstance(node, (list, tuple)):
                if (
                    len(node) == 2
                    and isinstance(node[0], str)
                    and isinstance(node[1], (int, float))
                ):
                    pairs.append((node[0], float(node[1])))
                    return
                for child in node:
                    _visit(child)

        _visit(result)
        h, w = np.asarray(image).shape[:2]
        box = [[0.0, 0.0], [float(w), 0.0], [float(w), float(h)], [0.0, float(h)]]
        return [
            OcrLine(text=text or "", confidence=conf, box=box)
            for text, conf in pairs
            if (text or "").strip()
        ]


class TesseractOcrEngine:
    def __init__(self, settings):
        self._settings = settings

    def warmup(self):
        return None

    def recognize(self, image) -> List[OcrLine]:
        import pytesseract

        data = pytesseract.image_to_data(
            image, lang=self._settings.ocr_lang, output_type=pytesseract.Output.DICT
        )
        lines: List[OcrLine] = []
        for i in range(len(data["text"])):
            text = (data["text"][i] or "").strip()
            if not text or int(data["conf"][i]) < 0:
                continue
            x, y, w, h = (
                int(data["left"][i]),
                int(data["top"][i]),
                int(data["width"][i]),
                int(data["height"][i]),
            )
            box = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
            lines.append(OcrLine(text=text, confidence=float(data["conf"][i]) / 100.0, box=box))
        return lines


class TesseractNameEngine:
    """多语言姓名第二引擎：Tesseract（sin/tam）识别僧伽罗语/泰米尔语文本。

    与主引擎相互独立（主引擎保持 PaddleOCR 不变），仅用于补充识别
    主引擎不支持的非拉丁文字，结果按 Unicode 脚本分类填充姓名字段。
    """

    def __init__(self, settings):
        self._lang = settings.name_ocr_lang or "sin+tam"
        self._psm = settings.name_tesseract_psm
        self._cmd = settings.tesseract_cmd or None

    def _pytesseract(self):
        import pytesseract

        if self._cmd:
            pytesseract.pytesseract.tesseract_cmd = self._cmd
        return pytesseract

    def warmup(self):
        """校验 tesseract 可执行文件与语言包是否可用，缺失时抛异常。"""
        pytesseract = self._pytesseract()
        pytesseract.get_tesseract_version()
        installed = set(pytesseract.get_languages(config=""))
        missing = [l for l in self._lang.split("+") if l and l not in installed]
        if missing:
            raise RuntimeError(
                "Tesseract 缺少语言包: "
                + ", ".join(missing)
                + "（安装: apt install "
                + " ".join(f"tesseract-ocr-{l}" for l in missing)
                + "）"
            )

    def recognize(self, image) -> List[OcrLine]:
        pytesseract = self._pytesseract()
        data = pytesseract.image_to_data(
            image,
            lang=self._lang,
            config=f"--psm {self._psm}",
            output_type=pytesseract.Output.DICT,
        )
        # 按 (block, paragraph, line) 把词聚合成行，取行级外接矩形
        groups: dict = {}
        for i in range(len(data["text"])):
            text = (data["text"][i] or "").strip()
            if not text or int(data["conf"][i]) < 0:
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            groups.setdefault(key, []).append(
                (
                    data["left"][i], data["top"][i],
                    data["width"][i], data["height"][i],
                    float(data["conf"][i]), text,
                )
            )
        lines: List[OcrLine] = []
        for words in groups.values():
            words.sort(key=lambda w: w[0])
            left = min(w[0] for w in words)
            top = min(w[1] for w in words)
            right = max(w[0] + w[2] for w in words)
            bottom = max(w[1] + w[3] for w in words)
            conf = sum(w[4] for w in words) / len(words) / 100.0
            lines.append(
                OcrLine(
                    text=" ".join(w[5] for w in words),
                    confidence=conf,
                    box=[[left, top], [right, top], [right, bottom], [left, bottom]],
                )
            )
        return lines


def create_engine(settings):
    if settings.ocr_engine == "tesseract":
        return TesseractOcrEngine(settings)
    return PaddleOcrEngine(settings)


def create_name_engine(settings):
    """创建多语言姓名第二引擎，返回 ``(engine | None, error | None)``。

    永不抛异常：tesseract 未安装 / 缺语言包时返回 ``(None, 原因)``，
    由调用方降级处理（记录日志，主流程不受影响）。
    """
    name = (settings.name_ocr_engine or "none").strip().lower()
    if name in ("", "none", "off", "false"):
        return None, None
    if name == "tesseract":
        try:
            engine = TesseractNameEngine(settings)
            engine.warmup()
            return engine, None
        except Exception as exc:  # tesseract 未安装 / 缺语言包
            return None, str(exc)
    return None, f"未知的多语言姓名引擎: {settings.name_ocr_engine}"
