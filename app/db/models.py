"""数据库 ORM 模型。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class HotAnalysis(Base):
    __tablename__ = "hot_analysis"
    __table_args__ = (
        UniqueConstraint("hot_id", "report_date", name="uq_hot_date"),
        Index("idx_ha_date_cat", "report_date", "category"),
        Index("idx_ha_importance", "report_date", "importance"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(128))
    heat: Mapped[int] = mapped_column(Integer, default=0)
    url: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(64))
    sub_category: Mapped[str | None] = mapped_column(String(64))
    summary: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[str | None] = mapped_column(Text)  # JSON 数组字符串
    importance: Mapped[int] = mapped_column(Integer, default=0)
    cluster_id: Mapped[str | None] = mapped_column(String(64))
    analyze_time: Mapped[datetime | None] = mapped_column(DateTime, default=func.now())


class DailyReport(Base):
    __tablename__ = "daily_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    summary: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)  # JSON
    hot_count: Mapped[int] = mapped_column(Integer, default=0)
    create_time: Mapped[datetime | None] = mapped_column(DateTime, default=func.now())


class AIConfigRow(Base):
    __tablename__ = "ai_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    api_url: Mapped[str | None] = mapped_column(Text)
    api_key: Mapped[str | None] = mapped_column(Text)  # Fernet 密文
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )


class AICallLog(Base):
    __tablename__ = "ai_call_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(128))
    purpose: Mapped[str | None] = mapped_column(String(32))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_msg: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=func.now())


class JobRun(Base):
    __tablename__ = "job_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(64), nullable=False)
    report_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="running")  # running|success|failed
    message: Mapped[str | None] = mapped_column(Text)
    # 进度：0-100；stage 如 fetch/cluster/analyze/report/done
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str | None] = mapped_column(String(32))
    current: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
