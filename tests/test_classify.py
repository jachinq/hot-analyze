"""规则分类与聚类单测。"""

from app.pipeline.classify import rule_classify
from app.pipeline.cluster import cluster_hots
from app.clients.hot_collector import HotItem


def test_rule_classify_tech():
    r = rule_classify("OpenAI 发布新大模型 GPT", "微博")
    assert r.hit
    assert r.category == "科技"


def test_rule_classify_finance():
    r = rule_classify("A股三大指数收涨 财报季开启", "雪球")
    assert r.category == "财经"


def test_rule_classify_miss():
    r = rule_classify("今天天气不错", "")
    assert r.category == "其他"
    assert not r.hit


def test_cluster_similar_titles():
    items = [
        HotItem(id=1, title="华为发布新款手机", heat=100),
        HotItem(id=2, title="华为发布新手机", heat=80),
        HotItem(id=3, title="世界杯决赛精彩回顾", heat=50),
    ]
    clusters = cluster_hots(items)
    assert len(clusters) >= 2
    sizes = sorted(len(c.items) for c in clusters)
    assert sizes[-1] >= 1
