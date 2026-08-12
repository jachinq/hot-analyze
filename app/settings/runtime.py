"""运行时配置 overlay：YAML 兜底 + DB 覆盖。"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import (
    AIConfig,
    AppConfig,
    CollectorConfig,
    PipelineConfig,
    SchedulerConfig,
    get_config,
)
from app.db.models import SystemSettingsRow

logger = logging.getLogger(__name__)

SETTINGS_SECTIONS = ("collector", "ai", "scheduler", "pipeline")

# section -> payload dict
_overlay: dict[str, dict[str, Any]] = {}


def load_runtime_overlay(db: Session) -> None:
    """从 DB 加载全部 section 到内存 overlay。"""
    global _overlay
    rows = db.scalars(select(SystemSettingsRow)).all()
    next_overlay: dict[str, dict[str, Any]] = {}
    for row in rows:
        try:
            data = json.loads(row.payload or "{}")
            if isinstance(data, dict):
                next_overlay[row.section] = data
        except json.JSONDecodeError:
            logger.warning("invalid system_settings payload section=%s", row.section)
    _overlay = next_overlay
    logger.info("runtime overlay loaded sections=%s", list(_overlay.keys()))


def get_overlay() -> dict[str, dict[str, Any]]:
    return _overlay


def get_runtime_config() -> AppConfig:
    """YAML 基线深拷贝后应用 DB overlay。ai.providers 仍来自 YAML（实际选用走 ai_config 表）。"""
    base = get_config()
    cfg = base.model_copy(deep=True)

    if "collector" in _overlay:
        cfg.collector = CollectorConfig.model_validate(
            {**cfg.collector.model_dump(), **_overlay["collector"]}
        )
    if "scheduler" in _overlay:
        cfg.scheduler = SchedulerConfig.model_validate(
            {**cfg.scheduler.model_dump(), **_overlay["scheduler"]}
        )
    if "pipeline" in _overlay:
        cfg.pipeline = PipelineConfig.model_validate(
            {**cfg.pipeline.model_dump(), **_overlay["pipeline"]}
        )
    if "ai" in _overlay:
        ai_data = cfg.ai.model_dump()
        # overlay 不含 providers，保留 YAML providers 作兜底
        for key in (
            "prefer_local",
            "max_calls_per_day",
            "max_tokens_per_day",
            "timeout_sec",
            "default_provider",
        ):
            if key in _overlay["ai"]:
                ai_data[key] = _overlay["ai"][key]
        cfg.ai = AIConfig.model_validate(ai_data)
    return cfg


def ai_globals_dict(cfg: AppConfig | None = None) -> dict[str, Any]:
    c = cfg or get_runtime_config()
    return {
        "prefer_local": c.ai.prefer_local,
        "max_calls_per_day": c.ai.max_calls_per_day,
        "max_tokens_per_day": c.ai.max_tokens_per_day,
        "timeout_sec": c.ai.timeout_sec,
        "default_provider": c.ai.default_provider,
    }


def update_section(db: Session, section: str, payload: dict[str, Any]) -> dict[str, Any]:
    """校验并写入某 section，刷新 overlay，返回规范化后的 payload。"""
    if section not in SETTINGS_SECTIONS:
        raise ValueError(f"unknown section: {section}")

    if section == "collector":
        validated = CollectorConfig.model_validate(payload).model_dump()
    elif section == "scheduler":
        validated = SchedulerConfig.model_validate(payload).model_dump()
    elif section == "pipeline":
        validated = PipelineConfig.model_validate(payload).model_dump()
    else:  # ai globals
        allowed = {
            "prefer_local",
            "max_calls_per_day",
            "max_tokens_per_day",
            "timeout_sec",
            "default_provider",
        }
        merged = {**ai_globals_dict(), **{k: v for k, v in payload.items() if k in allowed}}
        # 用临时 AIConfig 校验全局字段（providers 置空）
        tmp = AIConfig.model_validate({**merged, "providers": []})
        validated = {
            "prefer_local": tmp.prefer_local,
            "max_calls_per_day": tmp.max_calls_per_day,
            "max_tokens_per_day": tmp.max_tokens_per_day,
            "timeout_sec": tmp.timeout_sec,
            "default_provider": tmp.default_provider,
        }

    row = db.get(SystemSettingsRow, section)
    raw = json.dumps(validated, ensure_ascii=False)
    if row is None:
        db.add(SystemSettingsRow(section=section, payload=raw))
    else:
        row.payload = raw
        row.updated_at = datetime.now()
    db.commit()

    _overlay[section] = validated
    return validated
