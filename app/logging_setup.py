"""日志配置：同时输出到控制台和 log/ 目录下的文件（按天轮转）。"""
from __future__ import annotations

import logging
import os
from logging.handlers import TimedRotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "log")


def setup_logging(name: str = "app") -> None:
    """配置日志，输出到控制台和 log/{name}.log（按天轮转，保留 30 天）。"""
    os.makedirs(LOG_DIR, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # 避免重复添加 handler
    if root.handlers:
        return

    # 控制台
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)

    # 文件（按天轮转，保留 30 天）
    fh = TimedRotatingFileHandler(
        os.path.join(LOG_DIR, f"{name}.log"),
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)
