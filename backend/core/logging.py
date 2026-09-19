"""Structured logging configuration shared by backend processes."""

import logging


def configure_logging(level: str) -> None:
    """Configure conservative application logging without exposing secrets."""
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
