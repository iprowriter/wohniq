"""Logging setup.

A thin wrapper now; it exists so the rest of the codebase imports `get_logger`
from one place. The observability requirement (SPEC §8) — logging every LLM call
with prompt id/version, token counts, latency, and validation result — will be
built on top of this in the LLM client (task T2.1).
"""

import logging

from core.config import settings


def configure_logging() -> None:
    level = logging.INFO if settings.is_production else logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
