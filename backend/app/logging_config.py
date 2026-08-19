"""
Logging configuration for AI Arena.

Call `setup_logging()` once at startup (done in app.main). Every module
should then just do `logger = logging.getLogger(__name__)`.
"""
import logging
import sys

from app.config import settings


def setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # Avoid duplicate handlers if setup_logging() is called more than once
    # (e.g. once by uvicorn's reloader, once by our own app import).
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Quiet down noisy third-party loggers a bit.
    logging.getLogger("httpx").setLevel(logging.WARNING)