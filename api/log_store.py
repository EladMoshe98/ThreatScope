"""
Request log — a small SQLite table for the History dashboard.

Privacy: we store only **metadata** (timestamp, filename, latency, per-class entity
counts, status) — never the uploaded document text or the extracted entity strings.
The DB path is a mounted volume so history survives container restarts.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

LOG_DB_PATH = os.getenv("LOG_DB_PATH", "logs/requests.db")


def _connect() -> sqlite3.Connection:
    Path(LOG_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(LOG_DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS requests (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            ts           TEXT NOT NULL,
            filename     TEXT,
            latency_ms   REAL,
            num_entities INTEGER,
            status       TEXT,
            class_counts TEXT
        )"""
    )
    return conn


def log_request(filename: str, latency_ms: float, num_entities: int,
                status: str, class_counts: Optional[Dict[str, int]] = None) -> None:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            "INSERT INTO requests (ts, filename, latency_ms, num_entities, status, class_counts) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, filename, latency_ms, num_entities, status, json.dumps(class_counts or {})),
        )


def recent(limit: int = 20) -> List[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT ts, filename, latency_ms, num_entities, status, class_counts "
            "FROM requests ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "timestamp": r[0],
            "filename": r[1],
            "latency_ms": r[2],
            "num_entities": r[3],
            "status": r[4],
            "class_counts": json.loads(r[5] or "{}"),
        }
        for r in rows
    ]
