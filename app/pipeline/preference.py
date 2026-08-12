"""分类重要性偏好：关心强化 / 不关心弱化，仅影响排序与展示。"""

from __future__ import annotations

import logging
from typing import Any

from app.config import CategoryPreferenceConfig
from app.settings.runtime import get_runtime_config

logger = logging.getLogger(__name__)
_warned_conflicts: set[str] = set()


def _pref() -> CategoryPreferenceConfig:
    return get_runtime_config().pipeline.category_preference


def category_delta(category: str | None, pref: CategoryPreferenceConfig | None = None) -> int:
    """按配置顺序递减：care 第 i 项 +max(0, boost_max-i)；ignore 同理取负。冲突时 care 优先。"""
    cfg = pref or _pref()
    name = (category or "").strip()
    if not name:
        return 0

    care = list(cfg.care or [])
    ignore = list(cfg.ignore or [])
    if name in care and name in ignore:
        key = name
        if key not in _warned_conflicts:
            logger.warning(
                "category %r in both care and ignore; care wins",
                name,
            )
            _warned_conflicts.add(key)

    if name in care:
        i = care.index(name)
        return max(0, int(cfg.boost_max) - i)
    if name in ignore:
        i = ignore.index(name)
        return -max(0, int(cfg.suppress_max) - i)
    return 0


def is_ignored_category(
    category: str | None,
    pref: CategoryPreferenceConfig | None = None,
) -> bool:
    """是否属于「不关心」分类；与 care 冲突时 care 优先（不算不关心）。"""
    cfg = pref or _pref()
    name = (category or "").strip()
    if not name:
        return False
    care = list(cfg.care or [])
    ignore = list(cfg.ignore or [])
    if name in care:
        return False
    return name in ignore


def effective_importance(
    raw: Any,
    category: str | None,
    pref: CategoryPreferenceConfig | None = None,
) -> int:
    """原始 importance + 分类加减分，clamp 到 1–10。"""
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = 5
    return max(1, min(10, n + category_delta(category, pref)))


def sort_key_importance_heat(item: dict[str, Any]) -> tuple[int, int]:
    """(effective_importance, heat)，用于降序排序。"""
    return (
        effective_importance(item.get("importance", 0), item.get("category")),
        int(item.get("heat") or 0),
    )


def apply_effective_importance(item: dict[str, Any]) -> dict[str, Any]:
    """返回副本，importance 替换为 effective（不改入参）。"""
    out = dict(item)
    out["importance"] = effective_importance(item.get("importance", 0), item.get("category"))
    return out
