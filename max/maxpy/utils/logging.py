from __future__ import annotations

import logging
import sys
import json
from typing import Optional
from logging import LogRecord


class PrettyFormatter(logging.Formatter):
    """Pretty colored formatter."""

    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors and sys.stderr.isatty()

    def format(self, record: LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "") if self.use_colors else ""
        reset = self.RESET if self.use_colors else ""

        # Format: [timestamp] [level] [logger] message
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        level = f"{color}{record.levelname:<8}{reset}"
        logger = record.name
        message = record.getMessage()

        # Add extra fields if present
        extra = ""
        if hasattr(record, "extra") and record.extra:
            extra = f" {record.extra}"

        return f"[{timestamp}] {level} [{logger}] {message}{extra}"


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "lineno", "funcName", "created",
                "msecs", "relativeCreated", "thread", "threadName",
                "processName", "process", "message", "exc_info", "exc_text",
                "stack_info", "extra",
            }:
                log_obj[key] = value

        return json.dumps(log_obj, ensure_ascii=False)


def configure_logging(
    level: str = "INFO",
    stream=None,
    use_colors: bool = True,
    format: str = "pretty",
    force: bool = False,
) -> None:
    """Configure library logging."""
    stream = stream or sys.stderr

    if format == "json":
        formatter = JSONFormatter()
    else:
        formatter = PrettyFormatter(use_colors=use_colors)

    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger("maxpy")
    root_logger.setLevel(getattr(logging, level.upper()))
    root_logger.handlers = [handler] if force else []
    if force or not root_logger.handlers:
        root_logger.addHandler(handler)

    # Prevent propagation to root logger
    root_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Get logger for module."""
    return logging.getLogger(f"maxpy.{name}")