"""
Audit log index builder.

Builds volumes/audit_log/INDEX.jsonl — one line per job with summary
metadata for fast lookup. Used by self-diagnose to find similar past
failures without scanning every audit log file.

Can be run standalone (python -m src.runner.audit_index) or imported.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class IndexEntry:
    job_id: str
    skill: str
    model: str
    effort: str
    status: str
    user_rating: int | None
    review_outcome: str | None
    error_first_line: str | None
    keywords: list[str]


def _extract_keywords(summary: str, max_keywords: int = 10) -> list[str]:
    """Extract meaningful keywords from a summary string.

    Strips common words, lowercases, deduplicates. Pure function.
    """
    if not summary:
        return []

    # Simple word extraction — no NLP needed
    words = re.findall(r"[a-z][a-z0-9_-]{2,}", summary.lower())

    # Filter common words
    stop = {
        "the", "and", "for", "was", "that", "this", "with", "from",
        "has", "have", "had", "but", "not", "are", "were", "been",
        "all", "can", "will", "one", "its", "also", "into", "just",
        "than", "then", "when", "what", "which", "who", "how", "out",
        "did", "does", "done", "got", "let", "any", "now", "our",
        "use", "used", "using", "file", "files", "line", "none",
    }

    seen: set[str] = set()
    keywords: list[str] = []
    for w in words:
        if w not in stop and w not in seen:
            seen.add(w)
            keywords.append(w)
            if len(keywords) >= max_keywords:
                break
    return keywords


def build_index_entry(
    job_id: str,
    audit_lines: list[str],
    summary_text: str = "",
) -> IndexEntry | None:
    """Build one IndexEntry from a job's audit log lines + summary.

    Pure function. Returns None if no job_started event found.
    """
    skill = ""
    model = ""
    effort = ""
    status = ""
    user_rating: int | None = None
    review_outcome: str | None = None
    error_first_line: str | None = None

    for line in audit_lines:
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue

        kind = evt.get("kind", "")
        if kind == "job_started":
            skill = evt.get("skill", "")
            model = evt.get("model", "")
            effort = evt.get("effort", "")
        elif kind == "job_completed":
            status = "completed"
        elif kind == "job_failed":
            status = "failed"
            error = evt.get("error", "")
            if error:
                error_first_line = error.split("\n")[0][:200]
        elif kind == "job_cancelled":
            status = "cancelled"

    if not skill and not status:
        return None

    keywords = _extract_keywords(summary_text)

    return IndexEntry(
        job_id=job_id,
        skill=skill,
        model=model,
        effort=effort,
        status=status or "unknown",
        user_rating=user_rating,
        review_outcome=review_outcome,
        error_first_line=error_first_line,
        keywords=keywords,
    )


def rebuild_index(audit_log_dir: Path) -> int:
    """Rebuild INDEX.jsonl from all audit logs. Returns count of entries written."""
    index_path = audit_log_dir / "INDEX.jsonl"
    entries: list[dict[str, Any]] = []

    for log_file in sorted(audit_log_dir.glob("*.jsonl")):
        if log_file.name == "INDEX.jsonl":
            continue
        job_id = log_file.stem  # UUID without .jsonl

        with log_file.open() as f:
            lines = f.readlines()

        # Read summary if it exists
        summary_path = audit_log_dir / f"{job_id}.summary.md"
        summary = summary_path.read_text() if summary_path.exists() else ""

        entry = build_index_entry(job_id, lines, summary)
        if entry:
            entries.append(asdict(entry))

    # Write atomically-ish (overwrite)
    with index_path.open("w") as f:
        for entry in entries:
            f.write(json.dumps(entry, default=str) + "\n")

    return len(entries)


def search_index(
    index_path: Path,
    skill: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
) -> list[dict]:
    """Search the index. Returns matching entries. Pure function over file content."""
    if not index_path.exists():
        return []

    results: list[dict] = []
    with index_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if skill and entry.get("skill") != skill:
                continue
            if status and entry.get("status") != status:
                continue
            if keyword and keyword.lower() not in [k.lower() for k in entry.get("keywords", [])]:
                # Also check error_first_line
                if keyword.lower() not in (entry.get("error_first_line") or "").lower():
                    continue

            results.append(entry)

    return results


if __name__ == "__main__":
    from src.config import settings
    count = rebuild_index(settings.audit_log_dir)
    print(f"Indexed {count} jobs → {settings.audit_log_dir / 'INDEX.jsonl'}")
