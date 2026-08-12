"""按配置 / 数据库创建 AI Provider，支持本地优先降级。"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.ollama import OllamaProvider
from app.ai.openai_compat import OpenAICompatProvider
from app.config import get_config
from app.db.models import AIConfigRow
from app.security.crypto import decrypt_secret

logger = logging.getLogger(__name__)

LOCAL_PROVIDERS = {"lmstudio", "ollama"}
PLACEHOLDER_KEYS = {"", "lm-studio", "sk-placeholder", "ollama", "****"}

ENV_KEY_MAP = {
    "lmstudio": "LMSTUDIO_API_KEY",
    "ollama": "OLLAMA_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "openai": "OPENAI_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
}

# 短时缓存，避免逐条分析时反复重建 / 刷屏
_PROVIDERS_CACHE: list[AIProvider] | None = None
_PROVIDERS_CACHE_AT: float = 0.0
_PROVIDERS_CACHE_TTL = 60.0
_SKIPPED_KEY_LOGGED = False


def clear_provider_cache() -> None:
    global _PROVIDERS_CACHE, _PROVIDERS_CACHE_AT, _SKIPPED_KEY_LOGGED
    _PROVIDERS_CACHE = None
    _PROVIDERS_CACHE_AT = 0.0
    _SKIPPED_KEY_LOGGED = False


def _env_api_key(name: str, provider: str) -> str | None:
    for key in (name, provider):
        env_name = ENV_KEY_MAP.get(key.lower())
        if env_name:
            val = (os.getenv(env_name) or "").strip()
            if val:
                return val
    return None


def _resolve_api_key(
    *,
    name: str,
    provider: str,
    stored_key: str | None,
) -> str:
    """优先用库内密钥；为空时回退环境变量；本地模型允许占位。"""
    plain = decrypt_secret(stored_key or "") if stored_key else ""
    plain = (plain or "").strip()
    if plain and plain not in PLACEHOLDER_KEYS:
        return plain

    env_key = _env_api_key(name, provider)
    if env_key:
        return env_key

    if provider in LOCAL_PROVIDERS:
        return plain or ("lm-studio" if provider == "lmstudio" else "ollama")

    return ""


def _build_provider(
    *,
    name: str,
    provider: str,
    api_url: str,
    model: str,
    api_key: str | None,
) -> AIProvider | None:
    key = _resolve_api_key(name=name, provider=provider, stored_key=api_key)
    if provider not in LOCAL_PROVIDERS and not key:
        # 缺 key 属常见配置（本地优先时），不在此刷 warning
        logger.debug("skip provider %s: online model missing API key", name)
        return None

    timeout = float(get_config().ai.timeout_sec or 120.0)
    if provider == "ollama":
        return OllamaProvider(
            name=name,
            api_url=api_url,
            model=model,
            api_key=key or "ollama",
            timeout=timeout,
        )
    return OpenAICompatProvider(
        name=name,
        provider=provider,
        api_url=api_url,
        model=model,
        api_key=key or "lm-studio",
        timeout=timeout,
    )


def _rows_from_db(db: Session) -> list[AIConfigRow]:
    return list(
        db.scalars(
            select(AIConfigRow).where(AIConfigRow.enabled.is_(True)).order_by(AIConfigRow.priority)
        ).all()
    )


def _fallback_from_yaml() -> list[dict[str, Any]]:
    cfg = get_config()
    items = [p.model_dump() for p in cfg.ai.providers if p.enabled]
    items.sort(key=lambda x: x.get("priority", 100))
    return items


def list_candidate_providers(db: Session | None = None) -> list[AIProvider]:
    global _PROVIDERS_CACHE, _PROVIDERS_CACHE_AT, _SKIPPED_KEY_LOGGED

    now = time.monotonic()
    if _PROVIDERS_CACHE is not None and (now - _PROVIDERS_CACHE_AT) < _PROVIDERS_CACHE_TTL:
        return list(_PROVIDERS_CACHE)

    cfg = get_config()
    providers: list[AIProvider] = []
    seen: set[str] = set()
    skipped_no_key: list[str] = []

    rows: list[Any] = []
    if db is not None:
        rows = _rows_from_db(db)
    if not rows:
        rows = _fallback_from_yaml()

    for r in rows:
        if hasattr(r, "name"):
            name, provider, api_url, model, api_key = (
                r.name,
                r.provider,
                r.api_url or "",
                r.model,
                r.api_key,
            )
        else:
            name = r["name"]
            provider = r["provider"]
            api_url = r.get("api_url") or ""
            model = r["model"]
            api_key = r.get("api_key")
        if name in seen:
            continue
        seen.add(name)
        try:
            key = _resolve_api_key(name=name, provider=provider, stored_key=api_key)
            if provider not in LOCAL_PROVIDERS and not key:
                skipped_no_key.append(name)
                continue
            built = _build_provider(
                name=name,
                provider=provider,
                api_url=api_url,
                model=model,
                api_key=api_key,
            )
            if built is not None:
                providers.append(built)
        except Exception as e:
            logger.warning("skip provider %s: %s", name, e)

    if cfg.ai.prefer_local:
        providers.sort(key=lambda p: (0 if p.provider in LOCAL_PROVIDERS else 1, p.name))

    has_local = any(p.provider in LOCAL_PROVIDERS for p in providers)
    # 本地已可用：不提示在线模型缺 key；仅在没有本地、且最终无候选时给一次提示
    if skipped_no_key and not has_local and not providers and not _SKIPPED_KEY_LOGGED:
        logger.warning(
            "无可用 AI Provider，已跳过缺少 API Key 的在线模型: %s。"
            "请启动 LM Studio，或配置 DEEPSEEK_API_KEY / OPENAI_API_KEY",
            ", ".join(skipped_no_key),
        )
        _SKIPPED_KEY_LOGGED = True

    _PROVIDERS_CACHE = list(providers)
    _PROVIDERS_CACHE_AT = now
    return providers


def get_active_provider(db: Session | None = None) -> AIProvider:
    candidates = list_candidate_providers(db)
    if not candidates:
        raise RuntimeError("no AI provider configured")
    return candidates[0]


async def with_provider_fallback(
    db: Session | None,
    coro_factory,
):
    """依次尝试候选 Provider，成功即返回。coro_factory(provider) -> awaitable。"""
    candidates = list_candidate_providers(db)
    if not candidates:
        raise RuntimeError(
            "没有可用的 AI Provider：请启动本地 LM Studio，"
            "或在 .env 配置 DEEPSEEK_API_KEY / OPENAI_API_KEY 等在线密钥"
        )
    last_err: Exception | None = None
    errors: list[str] = []
    for p in candidates:
        try:
            return await coro_factory(p), p
        except Exception as e:
            msg = f"{p.name}: {e}"
            logger.warning("provider %s failed: %s", p.name, e)
            # 失败后清缓存，便于下次重建（例如临时掉线）
            clear_provider_cache()
            errors.append(msg)
            last_err = e
    detail = " | ".join(errors)
    if last_err:
        raise RuntimeError(f"全部 AI Provider 调用失败: {detail}") from last_err
    raise RuntimeError("no AI provider available")
