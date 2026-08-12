"""AI Provider 选择逻辑测试。"""

from __future__ import annotations

import os

from app.ai.factory import _build_provider, _resolve_api_key, list_candidate_providers


def test_resolve_skips_placeholder_for_online(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert _resolve_api_key(name="deepseek", provider="openai", stored_key="") == ""
    assert _resolve_api_key(name="deepseek", provider="openai", stored_key="sk-placeholder") == ""


def test_resolve_env_fallback(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-real-test-key")
    assert (
        _resolve_api_key(name="deepseek", provider="openai", stored_key=None)
        == "sk-real-test-key"
    )


def test_build_skips_online_without_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert (
        _build_provider(
            name="deepseek",
            provider="openai",
            api_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
            api_key=None,
        )
        is None
    )


def test_build_allows_lmstudio_placeholder():
    p = _build_provider(
        name="lmstudio",
        provider="lmstudio",
        api_url="http://127.0.0.1:1234/v1",
        model="qwen",
        api_key="lm-studio",
    )
    assert p is not None
    assert p.provider == "lmstudio"


def test_list_candidates_skips_unkeyed_online(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from app.ai.factory import clear_provider_cache

    clear_provider_cache()
    providers = list_candidate_providers(None)
    names = {p.name for p in providers}
    from app import config as config_mod

    cfg = config_mod.get_config()
    deepseek = next((p for p in cfg.ai.providers if p.name == "deepseek"), None)
    if deepseek and deepseek.enabled and not (deepseek.api_key or os.getenv("DEEPSEEK_API_KEY")):
        assert "deepseek" not in names
