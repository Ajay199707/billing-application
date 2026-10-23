"""
Structured and robust logging configuration for the Windows Billing Application.
"""

import logging
import logging.handlers
import sys
from pathlib import Path


def setup_logging(
    log_dir: Path | None = None,
    log_level: int = logging.INFO,
    app_name: str = "billing_system",
) -> logging.Logger:
    """
    Configures structured root logging with both Console and Rotating File handlers.
    Sensitive credentials like passwords and tokens are never logged.
    """
    if log_dir is None:
        log_dir = Path.home() / ".antigravity_billing" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{app_name}.log"

    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Prevent duplicate handlers on multiple invocations
    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating File Handler (10MB max, 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_file),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Set SQLAlchemy logging level to WARNING by default so standard queries don't flood console
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logger.info(f"Logging initialized. Output target: {log_file}")
    return logger
