"""LLM provider abstraction and provider pool.

Each provider is a callable that takes (description, language) -> (enhanced_text,
confidence). The pool tries providers in order, returning the first successful
response. A local rule-based fallback is always available so enhancement works
even when no API key is configured.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class ProviderConfig:
    name: str
    enabled: bool = True
    api_key: str = ""
    api_url: str = ""
    timeout_seconds: int = 30


class ProviderPool:
    """Manages an ordered list of LLM providers and calls the first that works."""

    def __init__(self, configs: Optional[list[ProviderConfig]] = None) -> None:
        self.configs: list[ProviderConfig] = [
            ProviderConfig(name="claude", enabled=True),
            ProviderConfig(name="gemini", enabled=True),
            ProviderConfig(name="codex", enabled=True),
        ]
        if configs:
            self.configs = configs
        self._callables: dict[str, Callable[[str, str], tuple[str, float]]] = {}

    def register(self, name: str, fn: Callable[[str, str], tuple[str, float]]) -> None:
        self._callables[name] = fn

    def enhance_sync(self, description: str, language: str = "english") -> tuple[str, float, int, str, list[str]]:
        """Synchronous enhancement: try configured providers, then fall back.

        Returns (enhanced_text, confidence, elapsed_ms, provider_name, errors).
        """
        errors: list[str] = []
        for cfg in self.configs:
            if not cfg.enabled:
                continue
            fn = self._callables.get(cfg.name)
            if not fn:
                errors.append(f"{cfg.name}: not configured")
                continue
            try:
                text, confidence = fn(description, language)
                if not text:
                    continue
                return text, confidence, 0, cfg.name, errors
            except Exception as exc:
                errors.append(f"{cfg.name}: {exc}")

        # Fallback: rule-based local enhancement, always succeeds.
        return _rule_based_enhance(description), 0.6, 0, "fallback", errors


def _rule_based_enhance(description: str) -> str:
    """Zero-dependency heuristic that structures a vague bounty description.

    Adds explicit requirement / acceptance / example sections when the original
    text is short or lacks structure. Never removes the original intent.
    """
    text = (description or "").strip()
    if not text:
        return _default_template()

    has_req = any(kw in text.lower() for kw in ("requirement", "acceptance", "criteria", "must"))
    has_ex = any(kw in text.lower() for kw in ("example", "e.g.", "for instance"))

    out = text
    if not has_req:
        out += (
            "\n\n## Requirements\n"
            "- Define the minimum functionality required to consider the bounty complete.\n"
            "- List concrete acceptance criteria the implementation must satisfy."
        )
    if not has_ex:
        out += (
            "\n\n## Example\n"
            "- Show a concrete before/after or input/output example that illustrates the expected behaviour."
        )
    return out


def _default_template() -> str:
    return (
        "## Description\n"
        "[Describe what the bounty asks the implementer to build, and why it matters.]\n\n"
        "## Requirements\n"
        "- State the core functionality that must be delivered.\n"
        "- List non-functional constraints (performance, compatibility, etc.).\n\n"
        "## Acceptance Criteria\n"
        "- [ ] Criterion 1 that can be verified objectively.\n"
        "- [ ] Criterion 2.\n\n"
        "## Example\n"
        "Provide a concrete input/output or before/after example."
    )
