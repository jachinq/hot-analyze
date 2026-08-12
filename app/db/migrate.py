"""简易建表与配置种子同步。"""

from __future__ import annotations

import json
import logging

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.config import get_config
from app.db import models  # noqa: F401 — 注册表
from app.db.models import AIConfigRow, SystemSettingsRow
from app.db.session import get_engine, get_session_factory
from app.security.crypto import encrypt_secret

logger = logging.getLogger(__name__)


def init_db() -> None:
    engine = get_engine()
    models.Base.metadata.create_all(bind=engine)
    _ensure_job_run_progress_columns(engine)
    SessionLocal = get_session_factory()
    with SessionLocal() as db:
        seed_ai_config_from_yaml(db)
        seed_system_settings_from_yaml(db)
        db.commit()
        from app.settings.runtime import load_runtime_overlay

        load_runtime_overlay(db)
    logger.info("database initialized")


def _ensure_job_run_progress_columns(engine) -> None:
    """为已有 job_run 表补齐进度字段（create_all 不会 ALTER）。"""
    insp = inspect(engine)
    if "job_run" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("job_run")}
    alters = []
    if "progress" not in existing:
        alters.append("ALTER TABLE job_run ADD COLUMN progress INTEGER DEFAULT 0")
    if "stage" not in existing:
        alters.append("ALTER TABLE job_run ADD COLUMN stage VARCHAR(32)")
    if "current" not in existing:
        alters.append("ALTER TABLE job_run ADD COLUMN current INTEGER DEFAULT 0")
    if "total" not in existing:
        alters.append("ALTER TABLE job_run ADD COLUMN total INTEGER DEFAULT 0")
    if not alters:
        return
    with engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))
    logger.info("job_run progress columns ensured: %s", len(alters))


def seed_ai_config_from_yaml(db: Session) -> None:
    """将 config.yaml 中的 providers 同步到 ai_config（已存在行不覆盖）。"""
    cfg = get_config()
    encrypt = cfg.security.encrypt_api_key
    for p in cfg.ai.providers:
        existing = db.scalar(select(AIConfigRow).where(AIConfigRow.name == p.name))
        key = p.api_key or ""
        enc_key = encrypt_secret(key) if (encrypt and key) else (key or None)
        if existing is None:
            db.add(
                AIConfigRow(
                    name=p.name,
                    provider=p.provider,
                    model=p.model,
                    api_url=p.api_url,
                    api_key=enc_key,
                    enabled=p.enabled,
                    priority=p.priority,
                )
            )
        elif not existing.api_key and enc_key:
            # 仅补空密钥，不覆盖 model/api_url/enabled/priority
            existing.api_key = enc_key


def seed_system_settings_from_yaml(db: Session) -> None:
    """某 section 不存在时从 YAML 写入；已存在则跳过。"""
    cfg = get_config()
    section_payloads = {
        "collector": cfg.collector.model_dump(),
        "ai": {
            "prefer_local": cfg.ai.prefer_local,
            "max_calls_per_day": cfg.ai.max_calls_per_day,
            "max_tokens_per_day": cfg.ai.max_tokens_per_day,
            "timeout_sec": cfg.ai.timeout_sec,
            "default_provider": cfg.ai.default_provider,
        },
        "scheduler": cfg.scheduler.model_dump(),
        "pipeline": cfg.pipeline.model_dump(),
    }
    for section, payload in section_payloads.items():
        existing = db.get(SystemSettingsRow, section)
        if existing is None:
            db.add(
                SystemSettingsRow(
                    section=section,
                    payload=json.dumps(payload, ensure_ascii=False),
                )
            )
            logger.info("seeded system_settings section=%s", section)
