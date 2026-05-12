"""Structured logging setup.

The production rule of thumb is: logs are a product, not a print stream. We:

* Read verbosity and format from ``Settings`` (single source of truth).
* Support JSON output behind a flag so the same binary can ship logs to Loki,
  CloudWatch, or stdout for local dev without code changes.
* Expose ``get_logger(name)`` so each module keeps its own named logger
  (easier filtering than a global ``agent_logger``).

``agent_logger`` is kept as a module-level alias for backward compatibility
with existing callers.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from core.config import get_settings


class _JsonFormatter(logging.Formatter):
    """Minimal JSON formatter suitable for shipping to log aggregators."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "line": record.lineno,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Attach any structured ``extra`` keys while skipping the standard LogRecord ones.
        reserved = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message"}
        for key, value in record.__dict__.items():
            if key not in reserved and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


_CONFIGURED = False


def _configure_root() -> None:
    """Attach handlers to the root application logger exactly once."""

    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", f"agent_trace_{datetime.now():%Y-%m-%d}.log")

    root = logging.getLogger("copilot")
    root.setLevel(settings.log_level.upper())
    # Bypass the global root to keep library noise (httpx, docker) out of our file.
    root.propagate = False

    if settings.log_json:
        formatter: logging.Formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s"
        )

    # Rotating file handler — 5 MB per file, keep 5 backups (~25 MB ceiling).
    file_handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setLevel(settings.log_level.upper())
    console_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``copilot`` namespace."""

    _configure_root()
    return logging.getLogger(f"copilot.{name}")


# Backward-compatible alias used by existing modules.
agent_logger = get_logger("agent")
