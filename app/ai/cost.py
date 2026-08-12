"""Token 统计与日限额。"""

from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_config
from app.db.models import AICallLog

logger = logging.getLogger(__name__)


class CostExceededError(RuntimeError):
    pass


def today_usage(db: Session, day: date | None = None) -> tuple[int, int]:
    day = day or date.today()
    start = datetime.combine(day, datetime.min.time())
    end = datetime.combine(day, datetime.max.time())
    row = db.execute(
        select(
            func.count(AICallLog.id),
            func.coalesce(func.sum(AICallLog.prompt_tokens + AICallLog.completion_tokens), 0),
        ).where(
            AICallLog.created_at >= start,
            AICallLog.created_at <= end,
            AICallLog.success.is_(True),
        )
    ).one()
    return int(row[0] or 0), int(row[1] or 0)


def check_quota(db: Session) -> None:
    cfg = get_config()
    calls, tokens = today_usage(db)
    if calls >= cfg.ai.max_calls_per_day:
        raise CostExceededError(f"daily AI calls exceeded: {calls}>={cfg.ai.max_calls_per_day}")
    if tokens >= cfg.ai.max_tokens_per_day:
        raise CostExceededError(f"daily AI tokens exceeded: {tokens}>={cfg.ai.max_tokens_per_day}")


def log_call(
    db: Session,
    *,
    provider: str,
    model: str,
    purpose: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    success: bool = True,
    error_msg: str | None = None,
) -> None:
    db.add(
        AICallLog(
            provider=provider,
            model=model,
            purpose=purpose,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            success=success,
            error_msg=(error_msg or "")[:2000] or None,
        )
    )
    db.flush()
