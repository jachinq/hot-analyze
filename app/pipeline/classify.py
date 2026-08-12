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


def allowed_categories() -> frozenset[str]:
    names = [str(c.get("name") or "").strip() for c in load_categories()]
    return frozenset(n for n in names if n) | frozenset({"其他"})


def category_options_text() -> str:
    """Prompt 用：与 rules 顺序一致的可选分类文案。"""
    names = [str(c.get("name") or "").strip() for c in load_categories()]
    ordered = [n for n in names if n]
    if "其他" not in ordered:
        ordered.append("其他")
    return "/".join(ordered)


def normalize_category(raw: Any, fallback: str = "其他") -> str:
    """将 AI/规则输出规范为白名单内的单个分类。

    常见非法值：整段「新闻/科技/...」、含斜杠、空白、未知词。
    """
    allowed = allowed_categories()
    fb = (fallback or "").strip()
    if fb not in allowed:
        fb = "其他"

    if raw is None:
        return fb
    name = str(raw).strip()
    if not name:
        return fb
    # 模型把「可选分类」整串抄回，或一次返回多个
    if "/" in name or "\\" in name or "|" in name or "、" in name:
        return fb
    if name in allowed:
        return name
    return fb


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
