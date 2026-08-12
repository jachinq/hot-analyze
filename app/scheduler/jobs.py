"""APScheduler 定时任务。"""

from __future__ import annotations

import logging
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db.session import get_session_factory
from app.pipeline.daily_job import run_daily_job
from app.settings.runtime import get_runtime_config

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
JOB_ID = "daily_analyze"


async def _scheduled_daily_analyze() -> None:
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        result = await run_daily_job(db, date.today())
        logger.info("scheduled daily analyze done: %s", result)


def _parse_cron(daily_cron: str) -> CronTrigger | None:
    parts = daily_cron.split()
    if len(parts) != 5:
        logger.error("invalid daily_cron: %s", daily_cron)
        return None
    minute, hour, day, month, day_of_week = parts
    cfg = get_runtime_config().scheduler
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        timezone=cfg.timezone,
    )


def start_scheduler() -> None:
    cfg = get_runtime_config().scheduler
    if not cfg.enabled:
        logger.info("scheduler disabled")
        return
    if scheduler.running:
        return
    trigger = _parse_cron(cfg.daily_cron)
    if trigger is None:
        return
    scheduler.add_job(
        _scheduled_daily_analyze,
        trigger=trigger,
        id=JOB_ID,
        replace_existing=True,
    )
    scheduler.start()
    logger.info("scheduler started cron=%s tz=%s", cfg.daily_cron, cfg.timezone)


def reload_scheduler() -> None:
    """按当前 runtime 配置重挂/停止 daily_analyze。"""
    cfg = get_runtime_config().scheduler
    if not cfg.enabled:
        if scheduler.running and scheduler.get_job(JOB_ID):
            scheduler.remove_job(JOB_ID)
            logger.info("scheduler job removed (disabled)")
        return

    trigger = _parse_cron(cfg.daily_cron)
    if trigger is None:
        return

    if not scheduler.running:
        scheduler.add_job(
            _scheduled_daily_analyze,
            trigger=trigger,
            id=JOB_ID,
            replace_existing=True,
        )
        scheduler.start()
        logger.info("scheduler started cron=%s tz=%s", cfg.daily_cron, cfg.timezone)
        return

    scheduler.add_job(
        _scheduled_daily_analyze,
        trigger=trigger,
        id=JOB_ID,
        replace_existing=True,
    )
    logger.info("scheduler reloaded cron=%s tz=%s", cfg.daily_cron, cfg.timezone)


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("scheduler stopped")
