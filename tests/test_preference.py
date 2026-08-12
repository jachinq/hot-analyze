"""分类重要性偏好单测。"""

from app.config import CategoryPreferenceConfig, get_config, reload_config
from app.pipeline import preference
from app.pipeline.preference import category_delta, effective_importance, is_ignored_category


def setup_function():
    preference._warned_conflicts.clear()
    reload_config()


def teardown_function():
    preference._warned_conflicts.clear()
    reload_config()


def test_delta_order_decreasing():
    pref = CategoryPreferenceConfig(
        care=["科技", "财经", "新闻"],
        ignore=["娱乐", "体育", "社会"],
        boost_max=3,
        suppress_max=3,
    )
    assert category_delta("科技", pref) == 3
    assert category_delta("财经", pref) == 2
    assert category_delta("新闻", pref) == 1
    assert category_delta("娱乐", pref) == -3
    assert category_delta("体育", pref) == -2
    assert category_delta("社会", pref) == -1


def test_is_ignored_category():
    pref = CategoryPreferenceConfig(care=["科技"], ignore=["娱乐", "体育"])
    assert is_ignored_category("娱乐", pref) is True
    assert is_ignored_category("体育", pref) is True
    assert is_ignored_category("科技", pref) is False
    assert is_ignored_category("军事", pref) is False
    assert is_ignored_category(None, pref) is False
    # care 优先
    both = CategoryPreferenceConfig(care=["娱乐"], ignore=["娱乐"])
    assert is_ignored_category("娱乐", both) is False


def test_delta_unlisted_is_zero():
    pref = CategoryPreferenceConfig(care=["科技"], ignore=["娱乐"])
    assert category_delta("军事", pref) == 0
    assert category_delta(None, pref) == 0
    assert category_delta("", pref) == 0


def test_delta_empty_lists():
    pref = CategoryPreferenceConfig()
    assert category_delta("科技", pref) == 0


def test_effective_clamp():
    pref = CategoryPreferenceConfig(care=["科技"], ignore=["娱乐"], boost_max=3, suppress_max=3)
    assert effective_importance(9, "科技", pref) == 10
    assert effective_importance(10, "科技", pref) == 10
    assert effective_importance(2, "娱乐", pref) == 1
    assert effective_importance(1, "娱乐", pref) == 1


def test_care_wins_on_conflict(caplog):
    pref = CategoryPreferenceConfig(
        care=["科技"],
        ignore=["科技"],
        boost_max=3,
        suppress_max=3,
    )
    with caplog.at_level("WARNING"):
        assert category_delta("科技", pref) == 3
    assert any("care wins" in r.message for r in caplog.records)


def test_effective_with_pref_changes_order():
    pref = CategoryPreferenceConfig(care=["科技"], ignore=["娱乐"], boost_max=3, suppress_max=3)
    assert effective_importance(5, "科技", pref) == 8
    assert effective_importance(7, "娱乐", pref) == 4


def test_live_config_loads_preference():
    cfg = get_config()
    pref = cfg.pipeline.category_preference
    assert isinstance(pref.care, list)
    assert isinstance(pref.ignore, list)
    assert pref.boost_max >= 0
    assert pref.suppress_max >= 0
