"""外部服务连通性探测。"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.ai.factory import LOCAL_PROVIDERS, resolve_api_key
from app.db.models import AIConfigRow
from app.settings.runtime import get_runtime_config

logger = logging.getLogger(__name__)


def _ms_since(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)


async def test_collector(
    *,
    base_url: str,
    list_path: str,
    timeout_sec: float = 30,
) -> dict[str, Any]:
    """探测 collector：优先 /health，再试 list_path。"""
    base = (base_url or "").rstrip("/")
    path = list_path or "/api/hot/list"
    if not path.startswith("/"):
        path = "/" + path
    timeout = max(3.0, float(timeout_sec or 30))
    start = time.perf_counter()
    detail: dict[str, Any] = {"base_url": base, "list_path": path}

    if not base:
        return {
            "ok": False,
            "message": "base_url 为空",
            "latency_ms": _ms_since(start),
            "detail": detail,
        }

    async with httpx.AsyncClient(timeout=timeout) as client:
        health_url = f"{base}/health"
        try:
            hr = await client.get(health_url)
            detail["health_status"] = hr.status_code
            if hr.status_code >= 500:
                return {
                    "ok": False,
                    "message": f"health 返回 {hr.status_code}",
                    "latency_ms": _ms_since(start),
                    "detail": detail,
                }
        except Exception as e:
            detail["health_error"] = str(e)
            # health 失败仍尝试 list，兼容无 health 的上游
            logger.info("collector health failed: %s", e)

        list_url = f"{base}{path}"
        params = {
            "date": date.today().isoformat(),
            "sort": "hot",
            "order": "desc",
            "pageSize": 1,
        }
        try:
            lr = await client.get(list_url, params=params)
            detail["list_status"] = lr.status_code
            if lr.status_code >= 400:
                return {
                    "ok": False,
                    "message": f"列表接口返回 HTTP {lr.status_code}",
                    "latency_ms": _ms_since(start),
                    "detail": detail,
                }
            data = lr.json()
            if isinstance(data, list):
                count = len(data)
            elif isinstance(data, dict):
                items = data.get("items") or data.get("data") or data.get("list") or []
                if isinstance(items, dict):
                    items = items.get("items") or []
                count = len(items) if isinstance(items, list) else 0
            else:
                count = 0
            detail["sample_count"] = count
            health_ok = detail.get("health_status") is not None and detail["health_status"] < 500
            msg = f"连接成功（列表可访问，样例 {count} 条"
            if health_ok:
                msg += "，health 正常"
            msg += "）"
            return {
                "ok": True,
                "message": msg,
                "latency_ms": _ms_since(start),
                "detail": detail,
            }
        except Exception as e:
            detail["list_error"] = str(e)
            if detail.get("health_status") is not None and detail["health_status"] < 500:
                return {
                    "ok": False,
                    "message": f"health 正常，但列表接口失败：{e}",
                    "latency_ms": _ms_since(start),
                    "detail": detail,
                }
            return {
                "ok": False,
                "message": f"连接失败：{e}",
                "latency_ms": _ms_since(start),
                "detail": detail,
            }


async def test_ai_provider(
    db: Session,
    *,
    config_id: int | None,
    name: str | None,
    provider: str,
    api_url: str,
    model: str,
    api_key: str | None,
    timeout_sec: float | None = None,
) -> dict[str, Any]:
    """探测 AI Provider：请求 OpenAI 兼容 /models（Ollama 原生则试 /api/tags）。"""
    start = time.perf_counter()
    base = (api_url or "").rstrip("/")
    provider_l = (provider or "").lower().strip()
    model_name = (model or "").strip()
    stored_key = api_key
    row_name = (name or "").strip()
    detail: dict[str, Any] = {
        "provider": provider_l,
        "api_url": base,
        "model": model_name,
    }

    if config_id is not None:
        row = db.get(AIConfigRow, config_id)
        if row is None:
            return {
                "ok": False,
                "message": f"找不到 Provider id={config_id}",
                "latency_ms": _ms_since(start),
                "detail": detail,
            }
        row_name = row_name or row.name
        provider_l = provider_l or (row.provider or "").lower()
        if not base:
            base = (row.api_url or "").rstrip("/")
        if not model_name:
            model_name = row.model or ""
        if stored_key in (None, "", "****"):
            stored_key = row.api_key
        detail.update({"provider": provider_l, "api_url": base, "model": model_name})

    if not base:
        return {
            "ok": False,
            "message": "api_url 为空",
            "latency_ms": _ms_since(start),
            "detail": detail,
        }

    key = resolve_api_key(name=row_name or provider_l, provider=provider_l, stored_key=stored_key)
    if provider_l not in LOCAL_PROVIDERS and not key:
        return {
            "ok": False,
            "message": "缺少 API Key（请填写或配置环境变量）",
            "latency_ms": _ms_since(start),
            "detail": detail,
        }

    cfg_timeout = float(timeout_sec or get_runtime_config().ai.timeout_sec or 30)
    timeout = max(5.0, min(cfg_timeout, 60.0))
    headers = {"Authorization": f"Bearer {key or 'lm-studio'}"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        # Ollama 原生 API（非 /v1）
        if provider_l == "ollama" and not base.endswith("/v1"):
            tags_url = f"{base}/api/tags"
            try:
                r = await client.get(tags_url)
                detail["status"] = r.status_code
                if r.status_code >= 400:
                    return {
                        "ok": False,
                        "message": f"Ollama /api/tags 返回 HTTP {r.status_code}",
                        "latency_ms": _ms_since(start),
                        "detail": detail,
                    }
                data = r.json()
                models = [m.get("name") for m in (data.get("models") or []) if isinstance(m, dict)]
                detail["models_sample"] = models[:8]
                model_ok = not model_name or any(
                    model_name == m or (m and str(m).startswith(model_name)) for m in models
                )
                if model_name and models and not model_ok:
                    return {
                        "ok": True,
                        "message": f"服务可达，但未找到模型 {model_name!r}（已加载 {len(models)} 个）",
                        "latency_ms": _ms_since(start),
                        "detail": detail,
                    }
                return {
                    "ok": True,
                    "message": f"连接成功（Ollama，模型数 {len(models)}）",
                    "latency_ms": _ms_since(start),
                    "detail": detail,
                }
            except Exception as e:
                return {
                    "ok": False,
                    "message": f"连接失败：{e}",
                    "latency_ms": _ms_since(start),
                    "detail": detail,
                }

        models_url = f"{base}/models"
        try:
            r = await client.get(models_url, headers=headers)
            detail["status"] = r.status_code
            if r.status_code in (401, 403):
                return {
                    "ok": False,
                    "message": f"鉴权失败（HTTP {r.status_code}），请检查 API Key",
                    "latency_ms": _ms_since(start),
                    "detail": detail,
                }
            if r.status_code >= 400:
                return {
                    "ok": False,
                    "message": f"/models 返回 HTTP {r.status_code}",
                    "latency_ms": _ms_since(start),
                    "detail": detail,
                }
            data = r.json()
            items = data.get("data") if isinstance(data, dict) else None
            ids: list[str] = []
            if isinstance(items, list):
                ids = [str(m.get("id")) for m in items if isinstance(m, dict) and m.get("id")]
            detail["models_sample"] = ids[:8]
            if model_name and ids:
                matched = any(
                    model_name == mid or model_name in mid or mid in model_name for mid in ids
                )
                if not matched:
                    return {
                        "ok": True,
                        "message": f"服务可达且鉴权通过，但模型列表中未见 {model_name!r}",
                        "latency_ms": _ms_since(start),
                        "detail": detail,
                    }
            return {
                "ok": True,
                "message": f"连接成功（/models 可访问，共 {len(ids)} 个模型）",
                "latency_ms": _ms_since(start),
                "detail": detail,
            }
        except Exception as e:
            return {
                "ok": False,
                "message": f"连接失败：{e}",
                "latency_ms": _ms_since(start),
                "detail": detail,
            }
