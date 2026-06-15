"""
Centralized logging — file + console with rotation.
Falls back to stdlib logging (no external dependency).
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import date


def get_logger(name: str = "jobhuntbot") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger   # already configured

    logger.setLevel(logging.INFO)

    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"jobhunt_{date.today().isoformat()}.log")

    # File handler (rotates at 5 MB)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)-12s | %(message)s",
        datefmt="%H:%M:%S",
    ))
    file_handler.setLevel(logging.INFO)

    # Console handler (cleaner format)
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)-7s  %(message)s"))
    console.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console)
    return logger
