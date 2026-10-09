"""命令行单图测试。

用法:
    python -m repayment_slip_ocr.cli path/to/slip.jpg
"""
from __future__ import annotations

import json
import sys

from app.config import get_settings
from app.ocr_engine import create_engine
from app.preprocessing import build_variants, load_image

from .extractor import dedup_lines, extract


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python -m repayment_slip_ocr.cli <图片路径>")
        return 1

    settings = get_settings()
    engine = create_engine(settings)
    engine.warmup()

    with open(sys.argv[1], "rb") as f:
        img = load_image(f.read())

    lines = []
    for variant in build_variants(img):
        lines.extend(engine.recognize(variant["img"]))

    unique = dedup_lines(lines)

    result = extract(unique)
    print(json.dumps(result.model_dump(exclude_none=True), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())