"""Pending-enhancement approval store and maintainer workflow.

Every LLM result is saved as PendingEnhancement. A maintainer inspects the
diff between the original and enhanced description, then approves or rejects.
Only approved text is published; rejected entries are discarded.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class PendingEnhancement:
    bounty_id: str
    original_description: str
    enhanced_description: str
    provider: str
    confidence: float
    suggestions: list[str] = field(default_factory=list)
    status: str = "pending"  # pending | approved | rejected
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def review_diff(self) -> str:
        """Return a human-readable unified-ish diff for the maintainer UI."""
        lines: list[str] = []
        orig_lines = [l for l in self.original_description.splitlines() if l.strip()]
        enh_lines = [l for l in self.enhanced_description.splitlines() if l.strip()]
        seen: set[str] = set()
        for ln in enh_lines:
            if ln in orig_lines:
                lines.append(f"  {ln}")
                seen.add(ln)
            else:
                lines.append(f"+ {ln}")
        for ln in orig_lines:
            if ln not in seen:
                lines.append(f"- {ln}")
        return "\n".join(lines)


class ApprovalStore:
    """Disk-backed pending-approval queue.

    Stores one JSONL line per enhancement. Thread-safe via simple file locking
    semantics are not required in the (expected) single-process dev setup.
    """

    def __init__(self, *, store_dir: str = "data/enhancer") -> None:
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._file = self.store_dir / "pending.jsonl"

    # -- CRUD --

    def save(self, item: PendingEnhancement) -> PendingEnhancement:
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(json.dumps(_asdict(item)) + "\n")
        return item

    def list_pending(self) -> list[PendingEnhancement]:
        return [item for item in self._load_all() if item.status == "pending"]

    def get_by_bounty(self, bounty_id: str) -> Optional[PendingEnhancement]:
        latest: Optional[PendingEnhancement] = None
        for item in self._load_all():
            if item.bounty_id == bounty_id:
                latest = item
        return latest

    def approve(self, bounty_id: str, reviewed_by: str) -> PendingEnhancement:
        return self._update(bounty_id, "approved", reviewed_by)

    def reject(self, bounty_id: str, reviewed_by: str) -> PendingEnhancement:
        return self._update(bounty_id, "rejected", reviewed_by)

    def published(self, bounty_id: str) -> Optional[PendingEnhancement]:
        item = self.get_by_bounty(bounty_id)
        return item if (item and item.status == "approved") else None

    # -- internals --

    def _update(self, bounty_id: str, status: str, reviewed_by: str) -> PendingEnhancement:
        items = self._load_all()
        now = datetime.now(timezone.utc).isoformat()
        for item in items:
            if item.bounty_id == bounty_id:
                item.status = status
                item.reviewed_by = reviewed_by
                item.reviewed_at = now
                break
        self._rewrite(items)
        return self.get_by_bounty(bounty_id) or _blank(bounty_id)

    def _load_all(self) -> list[PendingEnhancement]:
        if not self._file.exists():
            return []
        out: list[PendingEnhancement] = []
        for line in self._file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(PendingEnhancement(**json.loads(line)))
            except Exception:
                continue
        return out

    def _rewrite(self, items: list[PendingEnhancement]) -> None:
        with open(self._file, "w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(_asdict(item)) + "\n")


def _blank(bounty_id: str) -> PendingEnhancement:
    return PendingEnhancement(
        bounty_id=bounty_id,
        original_description="",
        enhanced_description="",
        provider="local",
        confidence=0.0,
        status="approved",
        reviewed_by="",
        reviewed_at="",
    )


def _asdict(item: PendingEnhancement) -> dict:
    return {
        "bounty_id": item.bounty_id,
        "original_description": item.original_description,
        "enhanced_description": item.enhanced_description,
        "provider": item.provider,
        "confidence": item.confidence,
        "suggestions": item.suggestions,
        "status": item.status,
        "reviewed_by": item.reviewed_by,
        "reviewed_at": item.reviewed_at,
        "created_at": item.created_at,
    }
