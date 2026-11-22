"""Bounded, structured application log storage for the authenticated admin UI."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

SERVICES = ("auth", "backend", "rag")
MAX_LOG_BYTES = 5 * 1024 * 1024
LOG_BACKUPS = 2
READ_BYTES_PER_FILE = 512 * 1024


def read_recent_logs(directory, *, service=None, level="DEBUG", search="", limit=200):
    """Read only fixed service filenames and a bounded tail of each rotated file.

    No Docker socket, subprocesses, user-supplied filenames or full-file reads.
    Rotations can happen during a read; a disappeared file is safe to skip.
    """
    if service is not None and service not in SERVICES:
        raise ValueError("Unknown log service")
    minimum = getattr(logging, level, None)
    if not isinstance(minimum, int) or not 1 <= limit <= 1000:
        raise ValueError("Invalid log filters")
    entries = []
    truncated = False
    if directory:
        for name in (SERVICES if service is None else (service,)):
            for suffix in ("", ".1", ".2"):
                path = Path(directory) / f"{name}.jsonl{suffix}"
                try:
                    with path.open("rb") as source:
                        size = source.seek(0, 2)
                        offset = max(0, size - READ_BYTES_PER_FILE)
                        source.seek(offset)
                        if offset:
                            source.readline(READ_BYTES_PER_FILE)  # Discard an incomplete line.
                            truncated = True
                        raw = source.read(READ_BYTES_PER_FILE)
                except FileNotFoundError:
                    continue
                for line in raw.splitlines():
                    try:
                        record = json.loads(line)
                    except (ValueError, UnicodeError):
                        continue
                    if not isinstance(record, dict) or record.get("service") != name:
                        continue
                    severity = getattr(logging, str(record.get("level", "")), 0)
                    if not isinstance(severity, int) or severity < minimum:
                        continue
                    if not isinstance(record.get("timestamp"), str):
                        continue
                    if search.casefold() not in json.dumps(record, ensure_ascii=False).casefold():
                        continue
                    entries.append(record)
    entries.sort(key=lambda item: item["timestamp"], reverse=True)
    return {
        "entries": entries[:limit],
        "truncated": truncated or len(entries) > limit,
        "configured": bool(directory),
        "services": list(SERVICES),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    }
