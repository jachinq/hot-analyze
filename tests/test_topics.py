"""话题聚合单测。"""

from datetime import date

from app.db.models import HotAnalysis
from app.pipeline.topics import build_topic, rows_to_topics


def _row(**kwargs) -> HotAnalysis:
    defaults = {
        "hot_id": 1,
        "report_date": date(2026, 8, 12),
        "title": "测试标题",
        "source": "weibo",
        "heat": 100,
        "rank": 10,
        "url": "https://example.com",
        "category": "社会",
        "sub_category": None,
        "summary": "摘要",
        "tags": "[]",
        "importance": 7,
        "cluster_id": "abc",
    }
    defaults.update(kwargs)
    return HotAnalysis(**defaults)


def test_build_topic_heat_is_max_rank_is_min():
    rows = [
        _row(hot_id=1, title="A", heat=100, rank=5, cluster_id="c1"),
        _row(hot_id=2, title="B", heat=500, rank=2, cluster_id="c1", url="https://b.example"),
        _row(hot_id=3, title="C", heat=200, rank=8, cluster_id="c1"),
    ]
    topic = build_topic(rows, "c1")
    assert topic.heat == 500
    assert topic.rank == 2
    assert topic.hot_id == 2
    assert topic.title == "B"
    assert topic.member_count == 3
    assert [m.hot_id for m in topic.members] == [2, 3, 1]
    assert [m.rank for m in topic.members] == [2, 8, 5]


def test_rows_to_topics_partition_then_heat_raw_rank(monkeypatch):
    monkeypatch.setattr(
        "app.pipeline.topics.group_rows",
        lambda rows: {f"solo-{r.hot_id}": [r] for r in rows},
    )
    monkeypatch.setattr(
        "app.pipeline.topics.is_ignored_category",
        lambda category, pref=None: (category or "") == "娱乐",
    )
    rows = [
        # 不关心：热度更高，但仍应排在关心/其他之后
        _row(hot_id=1, title="忽略高热", heat=900, rank=1, importance=9, category="娱乐"),
        _row(hot_id=2, title="忽略低热", heat=50, rank=2, importance=9, category="娱乐"),
        # 关心/其他
        _row(hot_id=3, title="关注低热高原始", heat=100, rank=9, importance=9, category="科技"),
        _row(hot_id=4, title="关注高热", heat=200, rank=5, importance=5, category="社会"),
        _row(hot_id=5, title="关注低热低名次", heat=100, rank=2, importance=8, category="社会"),
    ]
    # 前半：关心/其他 → 4(热200) → 3(热100,原始9) → 5(热100,原始8,rank2)
    # 后半：不关心 → 1(热900) → 2(热50)
    topics = rows_to_topics(rows)
    assert [t.hot_id for t in topics] == [4, 3, 5, 1, 2]


def test_rows_to_topics_live_clusters_similar_titles(monkeypatch):
    from app.config import ClusterConfig

    monkeypatch.setattr(
        "app.pipeline.cluster.get_runtime_config",
        lambda: type(
            "C",
            (),
            {
                "pipeline": type(
                    "P",
                    (),
                    {
                        "cluster": ClusterConfig(
                            enabled=True, method="tfidf", similarity_threshold=0.35
                        )
                    },
                )()
            },
        )(),
    )
    monkeypatch.setattr(
        "app.pipeline.topics.is_ignored_category",
        lambda category, pref=None: False,
    )
    rows = [
        _row(hot_id=1, title="朱镕基同志逝世", heat=300, rank=3, cluster_id="solo1"),
        _row(hot_id=2, title="朱镕基同志永垂不朽", heat=100, rank=8, cluster_id="solo2"),
        _row(hot_id=3, title="完全无关的体育比赛结果", heat=999, rank=1, cluster_id="solo3"),
    ]
    topics = rows_to_topics(rows, by="heat")
    multi = [t for t in topics if t.member_count > 1]
    assert len(multi) >= 1
    assert multi[0].heat == 300
    assert multi[0].rank == 3
    assert multi[0].member_count >= 2
    assert any(t.hot_id == 3 and t.member_count == 1 for t in topics)
    assert topics[0].hot_id == 3
