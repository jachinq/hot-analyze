"""上游 hot-collector HTTP 客户端。"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from app.settings.runtime import get_runtime_config

logger = logging.getLogger(__name__)


@dataclass
class HotItem:
    id: int
    title: str
    source: str = ""
    heat: int = 0
    url: str | None = None
    collected_at: str | None = None
    raw: dict[str, Any] | None = None


def _adapt_item(raw: dict[str, Any]) -> HotItem | None:
    """Adapter：兼容字段别名。"""
    hid = raw.get("id") or raw.get("hot_id")
    title = raw.get("title") or raw.get("name") or ""
    if hid is None or not title:
        return None
    heat = raw.get("heat") or raw.get("hot") or raw.get("score") or 0
    try:
        heat_i = int(heat)
    except (TypeError, ValueError):
        heat_i = 0
    return HotItem(
        id=int(hid),
        title=str(title).strip(),
        source=str(raw.get("source") or raw.get("platform") or ""),
        heat=heat_i,
        url=raw.get("url") or raw.get("link"),
        collected_at=raw.get("collected_at") or raw.get("time"),
        raw=raw,
    )


class HotCollectorClient:
    def __init__(
        self,
        base_url: str | None = None,
        list_path: str | None = None,
        timeout_sec: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        cfg = get_runtime_config().collector
        self.base_url = (base_url or cfg.base_url).rstrip("/")
        self.list_path = list_path or cfg.list_path
        self.timeout = timeout_sec if timeout_sec is not None else cfg.timeout_sec
        self.max_retries = max_retries if max_retries is not None else cfg.max_retries

    async def fetch_hots(self, report_date: date) -> list[HotItem]:
        url = f"{self.base_url}{self.list_path}"
        # 默认按热度倒序，与上游 /api/hot/list?sort=hot&order=desc 约定一致
        params = {
            "date": report_date.isoformat(),
            "sort": "hot",
            "order": "desc",
            "pageSize": 1000,
        }
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                return self._parse_response(data)
            except Exception as e:
                last_err = e
                wait = 2**attempt
                logger.warning(
                    "fetch hots failed attempt=%s wait=%ss err=%s", attempt + 1, wait, e
                )
                await asyncio.sleep(wait)
        raise RuntimeError(f"fetch hots failed after retries: {last_err}")

    def _parse_response(self, data: Any) -> list[HotItem]:
        if isinstance(data, list):
            items_raw = data
        elif isinstance(data, dict):
            items_raw = data.get("items") or data.get("data") or data.get("list") or []
            if isinstance(items_raw, dict):
                items_raw = items_raw.get("items") or []
        else:
            items_raw = []
        out: list[HotItem] = []
        for raw in items_raw:
            if not isinstance(raw, dict):
                continue
            item = _adapt_item(raw)
            if item:
                out.append(item)
        return out
