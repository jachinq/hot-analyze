"""加载 YAML 业务配置与环境变量。"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


class CollectorConfig(BaseModel):
    base_url: str = "http://127.0.0.1:8080"
    list_path: str = "/api/hot/list"
    timeout_sec: int = 30
    max_retries: int = 3


class SchedulerConfig(BaseModel):
    daily_cron: str = "0 8 * * *"
    timezone: str = "Asia/Shanghai"
    enabled: bool = True


class ProviderItem(BaseModel):
    name: str
    provider: str
    api_url: str
    model: str
    enabled: bool = True
    priority: int = 100
    api_key: str | None = None


class AIConfig(BaseModel):
    prefer_local: bool = True
    max_calls_per_day: int = 2000
    max_tokens_per_day: int = 500000
    # 单条分析通常较快；本地模型可按需在 config.yaml 调大
    timeout_sec: float = 120.0
    default_provider: str = "lmstudio"
    providers: list[ProviderItem] = Field(default_factory=list)


class ClusterConfig(BaseModel):
    enabled: bool = True
    method: str = "tfidf"
    similarity_threshold: float = 0.72


class ClassifyConfig(BaseModel):
    rule_first: bool = True
    ai_fallback: bool = True


class CategoryPreferenceConfig(BaseModel):
    """关心/不关心分类：列表顺序越前加减分越大；仅影响排序与展示，不改库内原始分。"""

    care: list[str] = Field(default_factory=list)
    ignore: list[str] = Field(default_factory=list)
    boost_max: int = 3
    suppress_max: int = 3


class PipelineConfig(BaseModel):
    cluster: ClusterConfig = Field(default_factory=ClusterConfig)
    classify: ClassifyConfig = Field(default_factory=ClassifyConfig)
    category_preference: CategoryPreferenceConfig = Field(
        default_factory=CategoryPreferenceConfig
    )
    batch_size: int = 20
    report_top_n: int = 30


class DatabaseConfig(BaseModel):
    url: str = "sqlite:///./data/analyzer.db"


class SecurityConfig(BaseModel):
    encrypt_api_key: bool = True


class CorsConfig(BaseModel):
    allow_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"]
    )


class AppConfig(BaseModel):
    collector: CollectorConfig = Field(default_factory=CollectorConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    cors: CorsConfig = Field(default_factory=CorsConfig)


def _resolve_provider_keys(cfg: AppConfig) -> AppConfig:
    """从环境变量补全 provider api_key。"""
    env_map = {
        "lmstudio": "LMSTUDIO_API_KEY",
        "ollama": "OLLAMA_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "openai": "OPENAI_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
    }
    providers: list[ProviderItem] = []
    for p in cfg.ai.providers:
        data = p.model_dump()
        if not data.get("api_key"):
            # 按 name / provider 尝试环境变量
            for key in (p.name, p.provider):
                env_name = env_map.get(key.lower())
                if env_name and os.getenv(env_name):
                    data["api_key"] = os.getenv(env_name)
                    break
            if not data.get("api_key") and p.provider == "lmstudio":
                data["api_key"] = os.getenv("LMSTUDIO_API_KEY", "lm-studio")
        providers.append(ProviderItem(**data))
    cfg.ai.providers = providers
    return cfg


@lru_cache
def get_config(config_path: str | None = None) -> AppConfig:
    path = Path(config_path) if config_path else ROOT_DIR / "config.yaml"
    raw: dict[str, Any] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    cfg = AppConfig.model_validate(raw)
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        cfg.database.url = db_url
    return _resolve_provider_keys(cfg)


def reload_config(config_path: str | None = None) -> AppConfig:
    get_config.cache_clear()
    return get_config(config_path)
