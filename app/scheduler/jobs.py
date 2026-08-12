"""APScheduler 定时任务。"""

from __future__ import annotations

import logging
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_config
from app.db.session import get_session_factory
from app.pipeline.daily_job import run_daily_job

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _scheduled_daily_analyze() -> None:
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        result = await run_daily_job(db, date.today())
        logger.info("scheduled daily analyze done: %s", result)


def start_scheduler() -> None:
    cfg = get_config().scheduler
    if not cfg.enabled:
        logger.info("scheduler disabled")
        return
    if scheduler.running:
        return
    # cron: "0 8 * * *" -> minute hour day month day_of_week
    parts = cfg.daily_cron.split()
    if len(parts) != 5:
        logger.error("invalid daily_cron: %s", cfg.daily_cron)
        return
    minute, hour, day, month, day_of_week = parts
    trigger = CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        timezone=cfg.timezone,
    )
    scheduler.add_job(
        _scheduled_daily_analyze,
        trigger=trigger,
        id="daily_analyze",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("scheduler started cron=%s tz=%s", cfg.daily_cron, cfg.timezone)


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("scheduler stopped")
