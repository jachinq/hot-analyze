"""将热点明细聚合为话题（展示层）。"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any, Iterable

from app.clients.hot_collector import HotItem
from app.db.models import HotAnalysis
from app.pipeline.cluster import cluster_hots
from app.pipeline.preference import effective_importance
from app.schemas import TopicItemOut, TopicMemberOut


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        tags = json.loads(raw)
        return tags if isinstance(tags, list) else []
    except json.JSONDecodeError:
        return []


def _row_fields(row: HotAnalysis) -> dict[str, Any]:
    return {
        "hot_id": row.hot_id,
        "title": row.title,
        "source": row.source,
        "heat": row.heat,
        "url": row.url,
        "category": row.category,
        "sub_category": row.sub_category,
        "summary": row.summary,
        "tags": _parse_tags(row.tags),
        "importance": effective_importance(row.importance, row.category),
        "cluster_id": row.cluster_id,
    }


def _member_sort_key(row: HotAnalysis) -> tuple:
    return (
        int(row.heat or 0),
        effective_importance(row.importance, row.category),
        -int(row.hot_id or 0),
    )


def _pick_representative(rows: list[HotAnalysis]) -> HotAnalysis:
    return max(rows, key=_member_sort_key)


def _stable_cluster_id(rows: list[HotAnalysis]) -> str:
    ids = sorted(int(r.hot_id) for r in rows)
    raw = ",".join(str(i) for i in ids)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def _rows_by_stored_cluster(rows: list[HotAnalysis]) -> dict[str, list[HotAnalysis]]:
    groups: dict[str, list[HotAnalysis]] = defaultdict(list)
    for r in rows:
        cid = (r.cluster_id or "").strip() or f"solo-{r.hot_id}"
        groups[cid].append(r)
    return groups


def _live_cluster_groups(rows: list[HotAnalysis]) -> dict[str, list[HotAnalysis]]:
    """库内全是单簇时，按当前阈值对标题做展示侧聚类。"""
    items = [
        HotItem(
            id=int(r.hot_id),
            title=r.title or "",
            source=r.source or "",
            heat=int(r.heat or 0),
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


def _should_live_recluster(stored: dict[str, list[HotAnalysis]]) -> bool:
    if not stored:
        return False
    return max(len(v) for v in stored.values()) <= 1


def group_rows(rows: Iterable[HotAnalysis]) -> dict[str, list[HotAnalysis]]:
    row_list = list(rows)
    if not row_list:
        return {}
    stored = _rows_by_stored_cluster(row_list)
    if _should_live_recluster(stored):
        return _live_cluster_groups(row_list)
    return stored


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
    members = [
        TopicMemberOut(
            hot_id=int(m.hot_id),
            title=m.title or "",
            source=m.source,
            heat=int(m.heat or 0),
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
        tags=base.get("tags") or [],
        source=base.get("source"),
        heat=heat,
        url=base.get("url"),
        cluster_id=cid,
        member_count=len(members),
        sources=sources,
        members=members,
    )


def rows_to_topics(
    rows: Iterable[HotAnalysis],
    *,
    by: str = "importance",
    limit: int | None = None,
) -> list[TopicItemOut]:
    groups = group_rows(rows)
    topics = [build_topic(members, cid) for cid, members in groups.items()]
    if by == "heat":
        topics.sort(
            key=lambda t: (int(t.heat or 0), int(t.importance or 0), -int(t.hot_id)),
            reverse=True,
        )
    else:
        topics.sort(
            key=lambda t: (int(t.importance or 0), int(t.heat or 0), -int(t.hot_id)),
            reverse=True,
        )
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
