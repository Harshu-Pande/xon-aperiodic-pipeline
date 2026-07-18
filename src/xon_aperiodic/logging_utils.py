"""Run logging: a single logger that prints to the console AND writes a per-run
log file, so every step (and every channel/epoch decision) is recoverable after
the fact. Replaces the scattered ``print(...)`` calls in the original monolith.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

_LOGGER_NAME = "xon_aperiodic"


def get_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)


def setup_logging(output_dir: Optional[Path] = None, level: int = logging.INFO,
                  logfile: str = "pipeline_run.log") -> logging.Logger:
    """Configure the package logger. Console always; file if output_dir is given."""
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    # Drop old handlers, but PRESERVE any tagged with _keep (e.g. a GUI progress handler),
    # closing the rest so file handles don't leak.
    kept = [h for h in logger.handlers if getattr(h, "_keep", False)]
    for h in list(logger.handlers):
        if h in kept:
            continue
        try:
            h.close()
        except Exception:
            pass
    logger.handlers = list(kept)
    logger.propagate = False

    fmt = logging.Formatter("%(message)s")
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(output_dir / logfile, mode="w")
        fh.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
        logger.addHandler(fh)
    return logger


def step(title: str) -> None:
    """Print a boxed step header (keeps the original's readable console output)."""
    log = get_logger()
    log.info("\n" + "=" * 72)
    log.info(title)
    log.info("=" * 72)


def info(msg: str) -> None:
    get_logger().info(msg)


def banner(title: str, char: str = "#", width: int = 80) -> None:
    log = get_logger()
    log.info("\n" + char * width)
    log.info(title)
    log.info(char * width)
