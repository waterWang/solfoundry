"""FastAPI endpoints for the AI Bounty Description Enhancer.

Exposes:
  POST /api/v1/ai/enhance      - enhance a bounty description (async LLM pool)
  GET  /api/v1/ai/pending      - list pending / approved / rejected enhancements
  GET  /api/v1/ai/pending/{bounty_id} - get pending enhancement for a bounty
  POST /api/v1/ai/approve/{bounty_id} - maintainer approval
  POST /api/v1/ai/reject/{bounty_id}  - maintainer rejection
  POST /api/v1/ai/providers/register - register an LLM provider
  GET  /api/v1/ai/providers/configured - list configured providers
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.enhancer import (
    EnhanceRequest,
    EnhanceResult,
    PendingEnhancement,
    ProviderConfig,
)
from app.services.enhancer.enhancer_service import Enhancer
from app.services.enhancer.providers import ProviderPool, ProviderConfig

router = APIRouter()


def _service() -> Enhancer:
    pool = ProviderPool()
    return Enhancer(pool=pool)


@router.post("/ai/enhance", response_model=dict)
async def enhance_bounty_description(request: EnhanceRequest):
    """Run a bounty description through the AI enhancement pipeline.

    Multi-LLM analysis (Claude, Codex, Gemini) produces an improved version with
    clearer requirements, acceptance criteria, and examples. The result is stored
    in the pending-approval queue and returned to the caller.
    """
    service = _service()
    result = service.enhance(request)
    return {
        "bounty_id": result.bounty_id,
        "provider": result.provider,
        "enhanced_description": result.enhanced_description,
        "suggestions": result.suggestions,
        "confidence": result.confidence,
        "elapsed_ms": result.elapsed_ms,
        "error": result.error,
    }


@router.get("/ai/pending")
async def list_pending(status: str | None = None) -> list[dict]:
    """List pending enhancements, optionally filtered by status."""
    service = _service()
    items = service.list_pending()
    if status:
        items = [i for i in items if i.status == status]
    return [
        {
            "bounty_id": i.bounty_id,
            "provider": i.provider,
            "confidence": i.confidence,
            "suggestions": i.suggestions,
            "status": i.status,
            "reviewed_by": i.reviewed_by,
            "reviewed_at": i.reviewed_at,
            "diff": i.review_diff(),
            "created_at": i.created_at,
        }
        for i in items
    ]


@router.get("/ai/pending/{bounty_id}")
async def get_pending(bounty_id: str) -> dict:
    service = _service()
    item = service.get_pending(bounty_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"No enhancement for bounty {bounty_id}")
    return {
        "bounty_id": item.bounty_id,
        "provider": item.provider,
        "confidence": item.confidence,
        "suggestions": item.suggestions,
        "status": item.status,
        "reviewed_by": item.reviewed_by,
        "reviewed_at": item.reviewed_at,
        "diff": item.review_diff(),
        "original_description": item.original_description,
        "enhanced_description": item.enhanced_description,
        "created_at": item.created_at,
    }


@router.post("/ai/approve/{bounty_id}")
async def approve_enhancement(bounty_id: str, *, reviewed_by: str = "maintainer") -> dict:
    service = _service()
    item = service.approve(bounty_id, reviewed_by)
    return {
        "bounty_id": item.bounty_id,
        "status": item.status,
        "reviewed_by": item.reviewed_by,
        "enhanced_description": item.enhanced_description,
    }


@router.post("/ai/reject/{bounty_id}")
async def reject_enhancement(bounty_id: str, *, reviewed_by: str = "maintainer") -> dict:
    service = _service()
    item = service.reject(bounty_id, reviewed_by)
    return {
        "bounty_id": item.bounty_id,
        "status": item.status,
        "reviewed_by": item.reviewed_by,
    }
