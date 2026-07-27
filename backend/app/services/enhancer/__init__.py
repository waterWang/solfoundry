"""Bounty description enhancement module.

Analyses a bounty description through a configurable pool of LLM providers
(Claude, Codex, Gemini), produces an improved version with clearer requirements,
explicit acceptance criteria, and concrete examples. Each result is stored in a
pending-approval queue; a maintainer must approve before the enhanced text is
written back.
"""
from __future__ import annotations

from .approval_store import ApprovalStore, PendingEnhancement
from .models import EnhanceRequest, EnhanceResult
from .enhancer_service import Enhancer
from .providers import ProviderPool, ProviderConfig

__all__ = [
    "Enhancer",
    "EnhanceRequest",
    "EnhanceResult",
    "ApprovalStore",
    "PendingEnhancement",
    "ProviderPool",
    "ProviderConfig",
]
