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
    importance: int = 0  # 有效重要性 = 原始 + 分类加减分
    raw_importance: int = 0  # AI/规则原始分数
    category_boost: int = 0  # 分类偏好加减分
    tags: list[str] = Field(default_factory=list)
    source: str | None = None
    heat: int = 0
    rank: int | None = None  # 采集榜内名次，越小越热
    url: str | None = None
    cluster_id: str | None = None


class TopicMemberOut(BaseModel):
    hot_id: int
    title: str
    source: str | None = None
    heat: int = 0
    rank: int | None = None
    url: str | None = None


class TopicItemOut(HotItemOut):
    """话题卡：代表条字段 + 可展开成员。heat=max(heat)，rank=min(rank)。"""

    member_count: int = 1
    sources: list[str] = Field(default_factory=list)
    members: list[TopicMemberOut] = Field(default_factory=list)


class ReportOut(BaseModel):
    date: date
    summary: str | None = None
    hot_count: int = 0
    topic_count: int = 0
    content: dict[str, Any] | None = None
    items: list[TopicItemOut] = Field(default_factory=list)


class CategoryStat(BaseModel):
    category: str
    count: int


class TodayStats(BaseModel):
    date: date
    hot_count: int = 0
    topic_count: int = 0
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


class AIGlobalsOut(BaseModel):
    prefer_local: bool = True
    max_calls_per_day: int = 2000
    max_tokens_per_day: int = 500000
    timeout_sec: float = 120.0
    default_provider: str = "lmstudio"


class CollectorSettingsOut(BaseModel):
    base_url: str
    list_path: str
    timeout_sec: int = 30
    max_retries: int = 3


class SchedulerSettingsOut(BaseModel):
    daily_cron: str
    timezone: str
    enabled: bool = True


class ClusterSettingsOut(BaseModel):
    enabled: bool = True
    method: str = "tfidf"
    similarity_threshold: float = 0.40


class ClassifySettingsOut(BaseModel):
    rule_first: bool = True
    ai_fallback: bool = True


class CategoryPreferenceOut(BaseModel):
    care: list[str] = Field(default_factory=list)
    ignore: list[str] = Field(default_factory=list)
    boost_max: int = 3
    suppress_max: int = 3


class PipelineSettingsOut(BaseModel):
    cluster: ClusterSettingsOut = Field(default_factory=ClusterSettingsOut)
    classify: ClassifySettingsOut = Field(default_factory=ClassifySettingsOut)
    category_preference: CategoryPreferenceOut = Field(default_factory=CategoryPreferenceOut)
    batch_size: int = 20
    report_top_n: int = 30


class SystemSettingsOut(BaseModel):
    collector: CollectorSettingsOut
    ai: AIGlobalsOut
    scheduler: SchedulerSettingsOut
    pipeline: PipelineSettingsOut


class SystemSettingsUpdate(BaseModel):
    collector: CollectorSettingsOut | None = None
    ai: AIGlobalsOut | None = None
    scheduler: SchedulerSettingsOut | None = None
    pipeline: PipelineSettingsOut | None = None


class ConnectionTestResult(BaseModel):
    ok: bool
    message: str
    latency_ms: float | None = None
    detail: dict[str, Any] | None = None


class CollectorTestRequest(BaseModel):
    base_url: str
    list_path: str = "/api/hot/list"
    timeout_sec: int = 30


class AIProviderTestRequest(BaseModel):
    id: int | None = None
    name: str | None = None
    provider: str = ""
    api_url: str = ""
    model: str = ""
    api_key: str | None = None
    timeout_sec: float | None = None


class JobOut(BaseModel):
    id: int
    job_name: str
    report_date: date | None = None
    status: str
    message: str | None = None
    progress: int = 0
    stage: str | None = None
    current: int = 0
    total: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
