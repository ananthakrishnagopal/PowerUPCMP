"""Small local logging setup with deterministic handler management."""

from __future__ import annotations

import logging
from pathlib import Path


LOGGER_NAME = "semifab_poc"


def configure_logging(level: str = "INFO", log_path: str | Path | None = None) -> logging.Logger:
    """Configure the package logger for a CLI or library run.

    Existing package handlers are replaced so repeated CLI/test setup does not duplicate
    messages. No root logger or external logging service is modified.
    """

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_path is not None:
        destination = Path(log_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(destination, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
