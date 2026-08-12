"""规则分类。"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import yaml

from app.config import ROOT_DIR


@dataclass
class RuleResult:
    category: str
    score: int
    matched: list[str]
    hit: bool


@lru_cache
def load_categories() -> list[dict[str, Any]]:
    path = ROOT_DIR / "app" / "rules" / "categories.yaml"
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return list(data.get("categories") or [])


def reload_categories() -> list[dict[str, Any]]:
    load_categories.cache_clear()
    return load_categories()


def rule_classify(title: str, source: str = "") -> RuleResult:
    """标题命中权重 > 来源权重；同分取列表顺序；均未命中 → 其他。"""
    categories = load_categories()
    best: RuleResult | None = None
    text = title or ""
    src = source or ""

    for cat in categories:
        name = cat.get("name") or "其他"
        keywords = cat.get("keywords") or []
        matched: list[str] = []
        score = 0
        for kw in keywords:
            if not kw:
                continue
            if kw in text:
                score += 3
                matched.append(kw)
            elif kw.lower() in text.lower():
                score += 2
                matched.append(kw)
            elif kw in src:
                score += 1
                matched.append(f"src:{kw}")
        if score <= 0:
            continue
        candidate = RuleResult(category=name, score=score, matched=matched, hit=True)
        if best is None or candidate.score > best.score:
            best = candidate

    if best is None:
        return RuleResult(category="其他", score=0, matched=[], hit=False)
    return best
