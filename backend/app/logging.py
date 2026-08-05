"""Structured logging configuration and utilities for NextGen backend modules."""

from __future__ import annotations

import logging
import sys

# Configure root logger format and standard stdout handler
LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)],
)


def get_logger(name: str) -> logging.Logger:
    """Returns a logger instance for the given module name."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    return logger
