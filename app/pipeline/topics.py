"""将热点明细聚合为话题（展示层）。"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from app.clients.hot_collector import HotItem
from app.db.models import HotAnalysis
from app.pipeline.cluster import cluster_hots
from app.pipeline.preference import (
    category_delta,
    effective_importance,
    is_ignored_category,
)
from app.schemas import TopicItemOut, TopicMemberOut

# 缺失榜内名次时靠后；与 reverse=True 搭配用 -rank
_MISSING_RANK = 10**9


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        tags = json.loads(raw)
        return tags if isinstance(tags, list) else []
    except json.JSONDecodeError:
        return []


def _rank_value(rank: Any) -> int:
    try:
        n = int(rank)
    except (TypeError, ValueError):
        return _MISSING_RANK
    return n if n > 0 else _MISSING_RANK


def _raw_importance(raw: Any) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 5


def _row_fields(row: HotAnalysis) -> dict[str, Any]:
    raw = _raw_importance(row.importance)
    boost = category_delta(row.category)
    return {
        "hot_id": row.hot_id,
        "title": row.title,
        "source": row.source,
        "heat": row.heat,
        "rank": row.rank,
        "url": row.url,
        "category": row.category,
        "sub_category": row.sub_category,
        "summary": row.summary,
        "tags": _parse_tags(row.tags),
        "raw_importance": raw,
        "category_boost": boost,
        "importance": effective_importance(row.importance, row.category),
        "cluster_id": row.cluster_id,
    }


def _member_sort_key(row: HotAnalysis) -> tuple:
    """热度 ↓ → 原始分数 ↓ → rank ↑。"""
    return (
        int(row.heat or 0),
        _raw_importance(row.importance),
        -_rank_value(row.rank),
    )


def _pick_representative(rows: list[HotAnalysis]) -> HotAnalysis:
    return max(rows, key=_member_sort_key)


def _stable_cluster_id(rows: list[HotAnalysis]) -> str:
    ids = sorted(int(r.hot_id) for r in rows)
    raw = ",".join(str(i) for i in ids)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def _live_cluster_groups(rows: list[HotAnalysis]) -> dict[str, list[HotAnalysis]]:
    """按当前阈值对标题做展示侧聚类。"""
    items = [
        HotItem(
            id=int(r.hot_id),
            title=r.title or "",
            source=r.source or "",
            heat=int(r.heat or 0),
            rank=r.rank,
            url=r.url,
        )
        for r in rows
    ]
    by_id = {int(r.hot_id): r for r in rows}
    groups: dict[str, list[HotAnalysis]] = {}
    for cluster in cluster_hots(items):
        members = [by_id[it.id] for it in cluster.items if it.id in by_id]
        if not members:
            continue
        cid = _stable_cluster_id(members)
        groups[cid] = members
    return groups


def group_rows(rows: Iterable[HotAnalysis]) -> dict[str, list[HotAnalysis]]:
    """展示层始终按当前聚类配置实时聚合，不依赖库内可能过时的 cluster_id。

    分析任务写入的 cluster_id 主要用于降 AI 成本；展示合并以现行阈值/算法为准。
    """
    row_list = list(rows)
    if not row_list:
        return {}
    return _live_cluster_groups(row_list)


def build_topic(rows: list[HotAnalysis], cluster_id: str | None = None) -> TopicItemOut:
    rep = _pick_representative(rows)
    base = _row_fields(rep)
    members_sorted = sorted(rows, key=_member_sort_key, reverse=True)
    sources: list[str] = []
    seen_src: set[str] = set()
    for m in members_sorted:
        src = (m.source or "").strip()
        if src and src not in seen_src:
            seen_src.add(src)
            sources.append(src)

    cid = cluster_id or rep.cluster_id or _stable_cluster_id(rows)
    heat = max(int(m.heat or 0) for m in rows)
    best_rank = min((_rank_value(m.rank) for m in rows), default=_MISSING_RANK)
    topic_rank = None if best_rank >= _MISSING_RANK else best_rank
    members = [
        TopicMemberOut(
            hot_id=int(m.hot_id),
            title=m.title or "",
            source=m.source,
            heat=int(m.heat or 0),
            rank=m.rank if _rank_value(m.rank) < _MISSING_RANK else None,
            url=m.url,
        )
        for m in members_sorted
    ]
    return TopicItemOut(
        hot_id=base["hot_id"],
        title=base["title"],
        category=base.get("category"),
        sub_category=base.get("sub_category"),
        summary=base.get("summary"),
        importance=base.get("importance") or 0,
        raw_importance=int(base.get("raw_importance") or 0),
        category_boost=int(base.get("category_boost") or 0),
        tags=base.get("tags") or [],
        source=base.get("source"),
        heat=heat,
        rank=topic_rank,
        url=base.get("url"),
        cluster_id=cid,
        member_count=len(members),
        sources=sources,
        members=members,
    )


def _topic_sort_key(t: TopicItemOut) -> tuple:
    """组内：热度 ↓ → 原始分数 ↓ → rank ↑。"""
    return (
        int(t.heat or 0),
        int(t.raw_importance or 0),
        -_rank_value(t.rank),
    )


def rows_to_topics(
    rows: Iterable[HotAnalysis],
    *,
    by: str = "heat",
    limit: int | None = None,
) -> list[TopicItemOut]:
    """聚合话题并分区排序。

    先按分类偏好拆成两组：
    - 关心 + 其他（非 ignore）
    - 不关心（ignore）
    各组内按：热度 → 原始分数 → rank；再拼接（关心/其他在前）。
    ``by`` 仅兼容旧调用。
    """
    del by
    groups = group_rows(rows)
    topics = [build_topic(members, cid) for cid, members in groups.items()]
    focus = [t for t in topics if not is_ignored_category(t.category)]
    ignored = [t for t in topics if is_ignored_category(t.category)]
    focus.sort(key=_topic_sort_key, reverse=True)
    ignored.sort(key=_topic_sort_key, reverse=True)
    topics = focus + ignored
    if limit is not None:
        topics = topics[:limit]
    return topics


def topic_count(rows: Iterable[HotAnalysis]) -> int:
    return len(group_rows(rows))


def flatten_topics_for_linkify(topics: list[TopicItemOut]) -> list[dict[str, Any]]:
    """供日报标题挂链接：代表条 + 全部成员。"""
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for t in topics:
        for m in t.members:
            if m.hot_id in seen:
                continue
            seen.add(m.hot_id)
            out.append(
                {
                    "hot_id": m.hot_id,
                    "title": m.title,
                    "url": m.url,
                }
            )
    return out
