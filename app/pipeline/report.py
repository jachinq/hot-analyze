"""日报生成。"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.ai import prompts
from app.ai.cost import CostExceededError, check_quota, log_call
from app.ai.errors import InvalidAIJsonError
from app.ai.factory import with_provider_fallback
from app.pipeline.preference import effective_importance, sort_key_importance_heat

logger = logging.getLogger(__name__)


def _rule_report(report_date: date, analyses: list[dict[str, Any]]) -> dict[str, Any]:
    top = sorted(analyses, key=sort_key_importance_heat, reverse=True)[:8]
    highlights = [
        {
            "title": a.get("title"),
            "impact": effective_importance(a.get("importance", 5), a.get("category")),
            "summary": a.get("summary") or "",
            "url": a.get("url") or "",
        }
        for a in top
    ]
    cats = {}
    for a in analyses:
        c = a.get("category") or "其他"
        cats[c] = cats.get(c, 0) + 1
    trends = [k for k, _ in sorted(cats.items(), key=lambda x: -x[1])[:5]]
    summary = f"{report_date.isoformat()} 共 {len(analyses)} 条热点，集中在：{'、'.join(trends) or '综合'}"
    lines = [f"# {report_date.isoformat()} 热点日报", "", summary, "", "## 重点事件"]
    for h in highlights:
        title = h["title"] or ""
        url = (h.get("url") or "").strip()
        title_md = f"[{title}]({url})" if url else title
        lines.append(f"- **{title_md}**（影响 {h['impact']}）：{h['summary']}")
    if trends:
        lines.extend(["", "## 趋势", ", ".join(trends)])
    return {
        "summary": summary,
        "highlights": highlights,
        "trends": trends,
        "markdown": "\n".join(lines),
    }


async def generate_daily_report(
    db: Session,
    report_date: date,
    analyses: list[dict[str, Any]],
    top_n: int = 30,
) -> dict[str, Any]:
    if not analyses:
        empty = {
            "summary": f"{report_date.isoformat()} 暂无热点数据",
            "highlights": [],
            "trends": [],
            "markdown": f"# {report_date.isoformat()} 热点日报\n\n暂无数据。",
        }
        return empty

    # 按话题去重：同 cluster 只保留热度最高的一条进入日报 Top
    best_by_cluster: dict[str, dict[str, Any]] = {}
    solo: list[dict[str, Any]] = []
    for a in analyses:
        cid = (a.get("cluster_id") or "").strip()
        if not cid:
            solo.append(a)
            continue
        prev = best_by_cluster.get(cid)
        if prev is None or int(a.get("heat") or 0) > int(prev.get("heat") or 0):
            best_by_cluster[cid] = a
    deduped = list(best_by_cluster.values()) + solo

    ranked = sorted(
        deduped,
        key=lambda x: (
            effective_importance(x.get("importance", 0), x.get("category"))
            * max(x.get("heat", 0), 1)
        ),
        reverse=True,
    )[:top_n]
    payload = [
        {
            "title": a.get("title"),
            "category": a.get("category"),
            "summary": a.get("summary"),
            "importance": effective_importance(a.get("importance"), a.get("category")),
            "heat": a.get("heat"),
            "tags": a.get("tags"),
            "url": a.get("url") or "",
        }
        for a in ranked
    ]

    try:
        check_quota(db)
    except CostExceededError:
        logger.warning("quota exceeded, rule report")
        return _rule_report(report_date, analyses)

    user = prompts.build_report_user(report_date.isoformat(), json.dumps(payload, ensure_ascii=False))

    async def _call(provider):
        return await provider.chat_json(prompts.REPORT_SYSTEM, user, max_tokens=2048)

    try:
        data, provider = await with_provider_fallback(db, _call)
        usage = getattr(provider, "last_usage", {}) or {}
        log_call(
            db,
            provider=provider.provider,
            model=provider.model,
            purpose="report",
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            success=True,
        )
        return {
            "summary": str(data.get("summary") or ""),
            "highlights": data.get("highlights") or [],
            "trends": data.get("trends") or [],
            "markdown": str(data.get("markdown") or ""),
        }
    except InvalidAIJsonError as e:
        logger.error(
            "AI report invalid JSON after retry, fallback to rule report; raw=%s",
            (e.raw or "")[:800],
        )
        try:
            log_call(
                db,
                provider="unknown",
                model="",
                purpose="report",
                success=False,
                error_msg=f"invalid_json: {e}",
            )
        except Exception:
            pass
        return _rule_report(report_date, analyses)
    except Exception as e:
        logger.exception("AI report failed: %s", e)
        try:
            log_call(
                db,
                provider="unknown",
                model="",
                purpose="report",
                success=False,
                error_msg=str(e),
            )
        except Exception:
            pass
        return _rule_report(report_date, analyses)
