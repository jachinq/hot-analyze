"""单条 / 按簇 AI 分析（分类+摘要合并）。"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.ai import prompts
from app.ai.cost import CostExceededError, check_quota, log_call
from app.ai.errors import InvalidAIJsonError
from app.ai.factory import with_provider_fallback
from app.clients.hot_collector import HotItem
from app.config import get_config
from app.pipeline.classify import rule_classify

logger = logging.getLogger(__name__)


def _clamp_importance(v: Any) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = 5
    return max(1, min(10, n))


def _fallback_result(item: HotItem, category: str | None = None) -> dict[str, Any]:
    rule = rule_classify(item.title, item.source)
    cat = category or rule.category
    summary = item.title[:80]
    return {
        "title": item.title,
        "category": cat,
        "sub_category": None,
        "summary": summary,
        "importance": 5,
        "tags": rule.matched[:5],
        "from_ai": False,
    }


async def analyze_item(db: Session, item: HotItem) -> dict[str, Any]:
    """规则优先；未命中或需补充时走合并 Prompt AI。"""
    cfg = get_config().pipeline
    rule = rule_classify(item.title, item.source)

    need_ai = True
    if cfg.classify.rule_first and rule.hit and not cfg.classify.ai_fallback:
        # 规则命中且不启用 AI 补充分类：仍可用 AI 做摘要；这里简化为规则结果 + 标题摘要
        result = _fallback_result(item, rule.category)
        result["importance"] = min(10, 4 + rule.score)
        return result

    if cfg.classify.rule_first and rule.hit:
        # 规则命中：仍调用 AI 生成摘要/标签，但可把分类作为提示（合并一次调用）
        need_ai = True

    if not need_ai:
        return _fallback_result(item, rule.category)

    try:
        check_quota(db)
    except CostExceededError:
        logger.warning("AI quota exceeded, rule fallback for hot_id=%s", item.id)
        return _fallback_result(item, rule.category if rule.hit else None)

    user = prompts.build_analyze_user(item.title, item.source, item.heat)
    if rule.hit:
        user += f"\n规则建议分类: {rule.category}（可参考）"

    async def _call(provider):
        return await provider.chat_json(prompts.ANALYZE_SYSTEM, user)

    try:
        data, provider = await with_provider_fallback(db, _call)
        usage = getattr(provider, "last_usage", {}) or {}
        log_call(
            db,
            provider=provider.provider,
            model=provider.model,
            purpose="analyze",
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            success=True,
        )
        category = data.get("category") or (rule.category if rule.hit else "其他")
        tags = data.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]
        return {
            "title": data.get("title") or item.title,
            "category": str(category),
            "sub_category": data.get("sub_category"),
            "summary": str(data.get("summary") or item.title)[:200],
            "importance": _clamp_importance(data.get("importance")),
            "tags": [str(t) for t in tags][:10],
            "from_ai": True,
        }
    except InvalidAIJsonError as e:
        # 已重试仍无法解析：向上抛出，由 daily_job 跳过本条继续后续任务
        logger.error(
            "AI analyze invalid JSON, will skip hot_id=%s title=%s raw=%s",
            item.id,
            (item.title or "")[:80],
            (e.raw or "")[:800],
        )
        try:
            log_call(
                db,
                provider="unknown",
                model="",
                purpose="analyze",
                success=False,
                error_msg=f"invalid_json: {e}",
            )
        except Exception:
            pass
        raise
    except Exception as e:
        logger.exception("AI analyze failed hot_id=%s: %s", item.id, e)
        try:
            log_call(
                db,
                provider="unknown",
                model="",
                purpose="analyze",
                success=False,
                error_msg=str(e),
            )
        except Exception:
            pass
        return _fallback_result(item, rule.category if rule.hit else None)
