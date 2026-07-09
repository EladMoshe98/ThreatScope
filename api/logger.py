"""
Application logging setup.

`get_logger()` returns a ready-to-use logger that the rest of the API shares to
record what it's doing — the model loading at startup, every prediction (file name,
entity count, latency), and any rejected upload or error.


Each line looks like:
    2026-07-09 12:00:01 INFO    nerf | predicted 'report.txt': 7 entities in 88.8 ms
    └── timestamp ──┘  └level┘ └name┘  └───────────── message ─────────────┘
"""
import logging
import os
import sys

# Log line layout: when · level · logger-name · message
_FMT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"


def get_logger(name: str = "nerf") -> logging.Logger:
    """Return the shared app logger, configuring it on first call."""
    logger = logging.getLogger(name)
    if logger.handlers:                     # already set up on a previous call — reuse it
        return logger
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

    # 1) console handler — always on (captured by `docker logs`)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(_FMT))
    logger.addHandler(console)

    # 2) file handler — only if LOG_FILE is set (e.g. /app/logs/nerf.log)
    log_file = os.getenv("LOG_FILE")
    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(_FMT))
        logger.addHandler(file_handler)

    logger.propagate = False                # don't also bubble up to the root logger (avoids doubled lines)
    return logger
