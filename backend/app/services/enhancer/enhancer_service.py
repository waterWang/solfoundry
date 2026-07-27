"""High-level orchestrator that runs the enhancement pipeline and records the result."""
from __future__ import annotations

from typing import Optional

from .approval_store import ApprovalStore, PendingEnhancement
from .models import EnhanceRequest, EnhanceResult
from .providers import ProviderPool


class Enhancer:
    def __init__(self, pool: Optional[ProviderPool] = None, store: Optional[ApprovalStore] = None) -> None:
        self.pool = pool or ProviderPool()
        self.store = store or ApprovalStore()

    def enhance(self, request: EnhanceRequest) -> EnhanceResult:
        """Run the enhancement via the provider pool and store the result pending approval."""
        enhanced_text, confidence, elapsed, provider, errors = self.pool.enhance_sync(
            request.description, request.language
        )
        suggestions = self._derive_suggestions(request.description)
        result = EnhanceResult(
            bounty_id=request.bounty_id,
            provider=provider,
            enhanced_description=enhanced_text,
            suggestions=suggestions,
            confidence=confidence,
            elapsed_ms=elapsed,
        )
        if errors:
            result.error = "; ".join(errors)
        self._store_pending(request, result)
        return result

    def approve(self, bounty_id: str, reviewed_by: str = "maintainer") -> PendingEnhancement:
        return self.store.approve(bounty_id, reviewed_by)

    def reject(self, bounty_id: str, reviewed_by: str = "maintainer") -> PendingEnhancement:
        return self.store.reject(bounty_id, reviewed_by)

    def get_pending(self, bounty_id: str) -> Optional[PendingEnhancement]:
        return self.store.get_by_bounty(bounty_id)

    def list_pending(self) -> list[PendingEnhancement]:
        return self.store.list_pending()

    def _store_pending(self, request: EnhanceRequest, result: EnhanceResult) -> None:
        self.store.save(PendingEnhancement(
            bounty_id=result.bounty_id,
            original_description=request.description,
            enhanced_description=result.enhanced_description,
            provider=result.provider,
            confidence=result.confidence,
            suggestions=result.suggestions,
        ))

    @staticmethod
    def _derive_suggestions(description: str) -> list[str]:
        suggestions: list[str] = []
        lower = (description or "").lower()
        if "acceptance" not in lower and "criteria" not in lower:
            suggestions.append("Add explicit acceptance criteria.")
        if "example" not in lower and "e.g." not in lower:
            suggestions.append("Include a concrete example or input/output.")
        if "must" not in lower and "required" not in lower:
            suggestions.append("State the minimum required behaviour clearly.")
        if len(description) < 100:
            suggestions.append("Expand the description with context and motivation.")
        return suggestions
