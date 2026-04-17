"""Audit log retention: compress and archive JSONL files older than 30 days."""

from __future__ import annotations

import gzip
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def rotate_audit_logs(audit_dir: Path, archive_after_days: int = 30) -> int:
    """Compress and move old JSONL files to archive/YYYY-MM.jsonl.gz.
    Returns number of files processed."""
    if not audit_dir.exists():
        return 0
    archive_dir = audit_dir / "archive"
    archive_dir.mkdir(exist_ok=True)

    cutoff = datetime.now().timestamp() - archive_after_days * 86400
    processed = 0
    month_bundles: dict[str, list[Path]] = {}

    for jsonl in audit_dir.glob("*.jsonl"):
        if jsonl.stat().st_mtime >= cutoff:
            continue
        mtime = datetime.fromtimestamp(jsonl.stat().st_mtime)
        key = mtime.strftime("%Y-%m")
        month_bundles.setdefault(key, []).append(jsonl)

    for month, files in month_bundles.items():
        bundle = archive_dir / f"{month}.jsonl.gz"
        with gzip.open(bundle, "at") as out:
            for f in files:
                out.write(f.read_text())
                f.unlink()
                processed += 1

    logger.info("audit log rotation", processed=processed)
    return processed
