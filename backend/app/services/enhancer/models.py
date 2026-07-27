"""Bounty description enhancement request/response models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class EnhanceRequest:
    """Input for a single description enhancement job."""

    bounty_id: str
    description: str
    title: str = ""
    requested_providers: list[str] = field(default_factory=list)
    language: str = "english"


@dataclass
class EnhanceResult:
    """Output of an enhancement pass from one provider."""

    bounty_id: str
    provider: str
    enhanced_description: str
    suggestions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    elapsed_ms: int = 0
    error: Optional[str] = None
