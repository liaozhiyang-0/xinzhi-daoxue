from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
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
    app_env: str = "development"
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

    default_agent_provider: str = "mock"
    xingchen_enabled: bool = False
    xingchen_base_url: str = "https://xingchen-api.xf-yun.com"
    xingchen_workflow_path: str = "/workflow/v1/chat/completions"
    xingchen_upload_path: str = "/workflow/v1/upload_file"
    xingchen_api_key: SecretStr = SecretStr("")
    xingchen_api_secret: SecretStr = SecretStr("")
    xingchen_solver_ct_flow_id: str = ""
    xingchen_solver_ct_workflow_id: str = ""
    xingchen_timeout_seconds: float = 120
    xingchen_uid: str = "local-demo-user"
    xingchen_bot_id: str = ""

    local_route_confidence_threshold: float = Field(default=0.75, ge=0, le=1)
    xingchen_knowledge_qa_flow_id: str = ""
    xingchen_fallback_router_flow_id: str = ""
    xingchen_solver_timeout_seconds: float = Field(default=180, gt=0)
    xingchen_knowledge_timeout_seconds: float = Field(default=90, gt=0)
    xingchen_router_timeout_seconds: float = Field(default=30, gt=0)
    xingchen_max_retries: int = Field(default=0, ge=0, le=1)

    solver_use_local_kb_context: bool = True
    solver_kb_top_k: int = Field(default=2, ge=1, le=5)
    solver_kb_max_chars: int = Field(default=2000, ge=200, le=10000)
    knowledge_use_local_kb_context: bool = True
    knowledge_kb_top_k: int = Field(default=3, ge=1, le=10)
    knowledge_kb_max_chars: int = Field(default=3500, ge=200, le=20000)
    knowledge_ct_path: Path = PROJECT_ROOT / "电路理论"
    knowledge_ae_path: Path = PROJECT_ROOT / "模电"
    knowledge_de_path: Path = PROJECT_ROOT / "数电"
    knowledge_max_files_per_course: int = Field(default=1000, ge=1, le=10000)
    knowledge_max_file_size_mb: int = Field(default=5, ge=1, le=100)

    xingchen_cache_enabled: bool = True
    xingchen_solver_cache_ttl_seconds: int = Field(default=1800, ge=0)
    xingchen_knowledge_cache_ttl_seconds: int = Field(default=3600, ge=0)
    xingchen_router_cache_ttl_seconds: int = Field(default=600, ge=0)

    max_upload_size_mb: int = Field(default=20, gt=0)
    local_storage_fallback: bool = True
    local_storage_path: Path = PROJECT_ROOT / "local_storage"

    @property
    def active_database_url(self) -> str:
        return self.test_database_url if self.app_env == "test" else self.database_url

    @property
    def xingchen_credentials_available(self) -> bool:
        return self.xingchen_enabled and bool(
            self.xingchen_base_url
            and self.xingchen_api_key.get_secret_value()
            and self.xingchen_api_secret.get_secret_value()
        )

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
