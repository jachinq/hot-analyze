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


def test_build_topic_heat_is_max():
    rows = [
        _row(hot_id=1, title="A", heat=100, cluster_id="c1"),
        _row(hot_id=2, title="B", heat=500, cluster_id="c1", url="https://b.example"),
        _row(hot_id=3, title="C", heat=200, cluster_id="c1"),
    ]
    topic = build_topic(rows, "c1")
    assert topic.heat == 500
    assert topic.hot_id == 2
    assert topic.title == "B"
    assert topic.member_count == 3
    assert [m.hot_id for m in topic.members] == [2, 3, 1]


def test_rows_to_topics_groups_by_cluster_id():
    rows = [
        _row(hot_id=1, title="事件甲侧面1", heat=300, cluster_id="g1"),
        _row(hot_id=2, title="事件甲侧面2", heat=100, cluster_id="g1"),
        _row(hot_id=3, title="无关事件", heat=999, cluster_id="g2"),
    ]
    topics = rows_to_topics(rows, by="heat")
    assert len(topics) == 2
    assert topics[0].hot_id == 3
    assert topics[1].member_count == 2
    assert topics[1].heat == 300
