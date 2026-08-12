"""Pydantic 响应模型。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    data: T | None = None
    message: str = "ok"


class HotItemOut(BaseModel):
    hot_id: int
    title: str
    category: str | None = None
    sub_category: str | None = None
    summary: str | None = None
    importance: int = 0
    tags: list[str] = Field(default_factory=list)
    source: str | None = None
    heat: int = 0
    url: str | None = None
    cluster_id: str | None = None


class ReportOut(BaseModel):
    date: date
    summary: str | None = None
    hot_count: int = 0
    content: dict[str, Any] | None = None
    items: list[HotItemOut] = Field(default_factory=list)


class CategoryStat(BaseModel):
    category: str
    count: int


class TodayStats(BaseModel):
    date: date
    hot_count: int = 0
    categories: list[CategoryStat] = Field(default_factory=list)
    has_report: bool = False
    report_summary: str | None = None
    job_status: str | None = None


class AIConfigOut(BaseModel):
    id: int
    name: str
    provider: str
    model: str
    api_url: str | None = None
    api_key: str = "****"
    enabled: bool = True
    priority: int = 100
    updated_at: datetime | None = None


class AIConfigUpdate(BaseModel):
    model: str | None = None
    api_url: str | None = None
    api_key: str | None = None
    enabled: bool | None = None
    priority: int | None = None


class JobOut(BaseModel):
    id: int
    job_name: str
    report_date: date | None = None
    status: str
    message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
