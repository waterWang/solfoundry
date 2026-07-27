"""Tests for the AI Bounty Description Enhancer service.

Covers the provider pool, fallback behaviour, enhancement model, and the
approval workflow. These tests are intentionally dependency-free (stdlib only).
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.services.enhancer import (
    EnhanceRequest,
    Enhancer,
)
from app.services.enhancer.approval_store import ApprovalStore, PendingEnhancement
from app.services.enhancer.enhancer_service import Enhancer
from app.services.enhancer.providers import ProviderPool, ProviderConfig


def test_provider_pool_fallback():
    pool = ProviderPool()
    text, conf, elapsed, provider, errors = pool.enhance_sync("vague")
    assert provider == "fallback"
    assert conf > 0
    assert "Requirements" in text or "## Requirements" in text


def test_provider_pool_registered_provider():
    pool = ProviderPool(configs=[ProviderConfig(name="mock", enabled=True)])
    pool.register(
        "mock",
        lambda d, lang: ("[MOCK] " + d, 0.95),
    )
    text, conf, elapsed, provider, errors = pool.enhance_sync("do the thing")
    assert provider == "mock"
    assert conf == 0.95
    assert text == "[MOCK] do the thing"


def test_provider_pool_disabled_provider():
    pool = ProviderPool(
        configs=[ProviderConfig(name="disabled", enabled=False), ProviderConfig(name="fallback", enabled=True)],
    )
    pool.register("disabled", lambda d, lang: ("NO", 1.0))
    text, conf, elapsed, provider, errors = pool.enhance_sync("x")
    assert provider == "fallback"


def test_provider_pool_failing_provider_falls_back():
    pool = ProviderPool(
        configs=[ProviderConfig(name="bad", enabled=True), ProviderConfig(name="fb", enabled=True)],
    )
    pool.register("bad", lambda d, lang: (_raise(), 0.0))
    text, conf, elapsed, provider, errors = pool.enhance_sync("y")
    assert provider == "fallback"
    assert "bad:" in errors[0]


def test_enhancer_end_to_end():
    store_dir = tempfile.mkdtemp()
    store = ApprovalStore(store_dir=store_dir)
    enhancer = Enhancer(store=store)
    req = EnhanceRequest(
        bounty_id="b1",
        description="build login",
        requested_providers=["claude"],
        language="english",
    )
    result = enhancer.enhance(req)
    assert result.bounty_id == "b1"
    assert result.provider == "fallback"
    assert result.enhanced_description
    assert "Acceptance" in result.enhanced_description or "criteria" in result.enhanced_description


def test_enhancer_suggestions():
    req = EnhanceRequest(bounty_id="b2", description="do x")
    enhancer = Enhancer()
    result = enhancer.enhance(req)
    assert len(result.suggestions) >= 2
    assert any("acceptance" in s.lower() for s in result.suggestions)


def test_approval_store_save_and_load():
    store_dir = tempfile.mkdtemp()
    store = ApprovalStore(store_dir=store_dir)
    item = PendingEnhancement(
        bounty_id="b3",
        original_description="old",
        enhanced_description="new",
        provider="mock",
        confidence=0.8,
    )
    saved = store.save(item)
    assert saved.bounty_id == "b3"
    pending = store.list_pending()
    assert len(pending) == 1
    assert pending[0].status == "pending"


def test_approval_store_approve_and_reject():
    store_dir = tempfile.mkdtemp()
    store = ApprovalStore(store_dir=store_dir)
    store.save(PendingEnhancement(
        bounty_id="b4", original_description="o",
        enhanced_description="e", provider="x", confidence=1.0,
    ))
    approved = store.approve("b4", "alice")
    assert approved.status == "approved"
    assert approved.reviewed_by == "alice"
    rejected = store.reject("b4", "bob")
    assert rejected.status == "rejected"
    assert rejected.reviewed_by == "bob"


def test_enhancer_approve_reject_workflow():
    store_dir = tempfile.mkdtemp()
    store = ApprovalStore(store_dir=store_dir)
    enhancer = Enhancer(store=store)
    enhancer.enhance(EnhanceRequest(bounty_id="b5", description="x"))
    assert enhancer.get_pending("b5").status == "pending"
    enhancer.approve("b5", "maintainer")
    assert enhancer.get_pending("b5").status == "approved"
    enhancer.reject("b5", "maintainer")
    assert enhancer.get_pending("b5").status == "rejected"


def test_review_diff():
    item = PendingEnhancement(
        bounty_id="b6",
        original_description="hello world",
        enhanced_description="hello world\nextra line",
        provider="x",
        confidence=1.0,
    )
    diff = item.review_diff()
    assert "+ extra line" in diff
    assert "  hello world" in diff


def test_rule_based_no_template_for_empty_description():
    pool = ProviderPool()
    text, *_ = pool.enhance_sync("")
    assert "## Description" in text
    assert "## Requirements" in text


def test_enhance_request_defaults():
    req = EnhanceRequest(bounty_id="b7", description="desc")
    assert req.requested_providers == []
    assert req.language == "english"
    assert req.title == ""


def _raise():
    raise RuntimeError("provider down")
