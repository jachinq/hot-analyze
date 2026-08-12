"""热点标题聚类。"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass

from app.clients.hot_collector import HotItem
from app.settings.runtime import get_runtime_config

logger = logging.getLogger(__name__)


@dataclass
class Cluster:
    cluster_id: str
    items: list[HotItem]
    representative: HotItem


def _normalize_title(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"[\s\[\]【】（）()《》<>\"'：:，,。.!！?？、·|#]+", "", t)
    return t


def _title_sim_clusters(items: list[HotItem], threshold: float) -> list[Cluster]:
    """简单字符 bigram Jaccard 相似度聚类。"""
    clusters: list[Cluster] = []
    for item in items:
        placed = False
        norm = _normalize_title(item.title)
        grams = set(norm[i : i + 2] for i in range(max(len(norm) - 1, 1)))
        for c in clusters:
            ref = _normalize_title(c.representative.title)
            ref_g = set(ref[i : i + 2] for i in range(max(len(ref) - 1, 1)))
            if not grams or not ref_g:
                continue
            inter = len(grams & ref_g)
            union = len(grams | ref_g)
            sim = inter / union if union else 0.0
            if sim >= threshold:
                c.items.append(item)
                if item.heat > c.representative.heat:
                    c.representative = item
                placed = True
                break
        if not placed:
            cid = hashlib.md5(item.title.encode("utf-8")).hexdigest()[:12]
            clusters.append(Cluster(cluster_id=cid, items=[item], representative=item))
    return clusters


def _tfidf_clusters(items: list[HotItem], threshold: float) -> list[Cluster]:
    if len(items) <= 1:
        return _title_sim_clusters(items, threshold)
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        logger.warning("sklearn not available, fallback to title_sim")
        return _title_sim_clusters(items, threshold)

    texts = [it.title for it in items]
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
    try:
        matrix = vectorizer.fit_transform(texts)
    except ValueError:
        return _title_sim_clusters(items, threshold)

    sim = cosine_similarity(matrix)
    n = len(items)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if sim[i, j] >= threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    clusters: list[Cluster] = []
    for idxs in groups.values():
        members = [items[i] for i in idxs]
        rep = max(members, key=lambda x: x.heat)
        cid = hashlib.md5(rep.title.encode("utf-8")).hexdigest()[:12]
        clusters.append(Cluster(cluster_id=cid, items=members, representative=rep))
    return clusters


def cluster_hots(items: list[HotItem]) -> list[Cluster]:
    cfg = get_runtime_config().pipeline.cluster
    if not cfg.enabled or not items:
        return [
            Cluster(
                cluster_id=hashlib.md5(it.title.encode("utf-8")).hexdigest()[:12],
                items=[it],
                representative=it,
            )
            for it in items
        ]
    method = (cfg.method or "tfidf").lower()
    if method == "title_sim":
        return _title_sim_clusters(items, cfg.similarity_threshold)
    return _tfidf_clusters(items, cfg.similarity_threshold)
