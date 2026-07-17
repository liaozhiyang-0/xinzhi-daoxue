from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "xinzhi-daoxue-api"
    app_env: Literal["development", "test", "production"] = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "sqlite+aiosqlite:///./xzd-dev.db"
    test_database_url: str = "sqlite+aiosqlite:///./test.db"
    redis_url: str = "redis://localhost:6379/0"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "xzd_minio"
    minio_secret_key: str = "change_me"
    minio_bucket: str = "xzd-files"
    minio_secure: bool = False

    default_agent_provider: Literal["mock", "xingchen"] = "mock"
    allow_mock_fallback: bool = True
    xingchen_enabled: bool = False
    xingchen_publication_status: Literal["not_published"] = "not_published"
    xingchen_base_url: str = ""
    xingchen_api_key: str = ""
    xingchen_solver_ct_workflow_id: str = ""
    xingchen_timeout_seconds: float = Field(default=120, gt=0)

    max_upload_size_mb: int = Field(default=20, gt=0)
    local_storage_fallback: bool = True
    local_storage_path: Path = PROJECT_ROOT / "local_storage"
    sse_heartbeat_seconds: float = Field(default=10.0, gt=0)

    knowledge_enabled: bool = True
    knowledge_ct_path: Path = PROJECT_ROOT / "电路理论"
    knowledge_ae_path: Path = PROJECT_ROOT / "模电"
    knowledge_de_path: Path = PROJECT_ROOT / "数电"
    knowledge_chunk_size_chars: int = Field(default=1200, ge=300, le=4000)
    knowledge_chunk_overlap_chars: int = Field(default=150, ge=0, le=500)
    knowledge_default_top_k: int = Field(default=5, ge=1, le=20)
    knowledge_max_files_per_course: int = Field(default=1000, ge=1, le=10000)
    knowledge_max_file_size_mb: int = Field(default=5, ge=1, le=100)
    knowledge_config_path: Path = PROJECT_ROOT / "knowledge_config"
    knowledge_min_score_v2: float = Field(default=0.35, ge=0)
    knowledge_low_confidence_threshold: float = Field(default=0.45, ge=0, le=1)
    knowledge_max_hits_per_document: int = Field(default=2, ge=1, le=10)
    knowledge_max_context_chars: int = Field(default=6000, ge=500, le=50000)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL 必须是标准 Python 日志级别")
        return normalized

    @property
    def active_database_url(self) -> str:
        return self.test_database_url if self.app_env == "test" else self.database_url

    @property
    def xingchen_runtime_available(self) -> bool:
        return False

    @property
    def knowledge_paths(self) -> dict[str, Path]:
        return {
            "CT": self.knowledge_ct_path,
            "AE": self.knowledge_ae_path,
            "DE": self.knowledge_de_path,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
