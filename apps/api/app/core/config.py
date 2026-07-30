from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]
XINGCHEN_TIMEOUT_DEFAULT_SECONDS = 300
XINGCHEN_TIMEOUT_MIN_SECONDS = 30
XINGCHEN_TIMEOUT_MAX_SECONDS = 600


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
    app_debug: bool = True
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "sqlite+aiosqlite:///./xzd-dev.db"
    test_database_url: str = "sqlite+aiosqlite:///./test.db"
    redis_url: str = "redis://localhost:6379/0"
    vector_store_path: Path = PROJECT_ROOT / "knowledge_indexes"
    upload_dir: Path = PROJECT_ROOT / "local_storage" / "uploads"
    cache_dir: Path = PROJECT_ROOT / "local_storage" / "cache"

    spark_enabled: bool = False
    spark_base_url: str = "https://spark-api-open.xf-yun.com/v1/chat/completions"
    spark_app_id: str = ""
    spark_api_key: SecretStr = SecretStr("")
    spark_api_secret: SecretStr = SecretStr("")
    spark_api_password: SecretStr = SecretStr("")
    spark_model: str = "4.0Ultra"
    spark_timeout_seconds: float = Field(default=90, gt=0, le=600)

    # Unified domestic model APIs. Legacy SPARK_* remains readable during migration.
    iflytek_spark_enabled: bool = True
    iflytek_spark_api_key: SecretStr = SecretStr("")
    iflytek_spark_base_url: str = "https://spark-api-open.xf-yun.com/x2"
    iflytek_spark_model: str = "spark-x"
    iflytek_spark_timeout_seconds: float = Field(default=120, gt=0, le=600)
    iflytek_spark_max_tokens: int = Field(default=8192, ge=1, le=65536)
    iflytek_spark_thinking_mode: Literal["enabled", "disabled", "auto"] = "auto"

    dashscope_enabled: bool = True
    dashscope_api_key: SecretStr = SecretStr("")
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_workspace_id: str = ""
    dashscope_region: Literal[
        "cn-beijing",
        "ap-southeast-1",
        "ap-northeast-1",
        "eu-central-1",
        "us-east-1",
    ] = "cn-beijing"
    qwen_vision_primary_model: str = "qwen3.7-plus"
    qwen_vision_fast_model: str = "qwen3.6-flash"
    qwen_text_fast_model: str = "qwen3.5-flash"
    qwen_timeout_seconds: float = Field(default=90, gt=0, le=600)
    qwen_vision_high_resolution: bool = True

    model_connect_timeout_seconds: float = Field(default=10, gt=0, le=120)
    model_read_timeout_seconds: float = Field(default=120, gt=0, le=600)
    model_max_retries: int = Field(default=1, ge=0, le=1)
    model_global_max_concurrency: int = Field(default=6, ge=1, le=32)
    model_circuit_failure_threshold: int = Field(default=1, ge=1, le=20)
    model_circuit_reset_seconds: float = Field(default=300, gt=0, le=3600)
    spark_max_concurrency: int = Field(default=4, ge=1, le=16)
    qwen_max_concurrency: int = Field(default=2, ge=1, le=32)
    enable_model_cost_tracking: bool = True
    academic_solver_max_tokens: int = Field(default=4096, ge=1024, le=65536)
    academic_solver_max_continuations: int = Field(default=2, ge=0, le=4)
    academic_solver_timeout_seconds: float = Field(default=240, gt=0, le=600)
    academic_solver_soft_deadline_seconds: float = Field(default=140, gt=0, le=175)
    academic_solver_finalization_deadline_seconds: float = Field(
        default=165, gt=0, le=175
    )
    academic_solver_hard_deadline_seconds: float = Field(default=175, gt=0, le=175)
    academic_solver_complex_soft_deadline_seconds: float = Field(
        default=200, gt=0, le=235
    )
    academic_solver_complex_finalization_deadline_seconds: float = Field(
        default=225, gt=0, le=235
    )
    academic_solver_complex_hard_deadline_seconds: float = Field(
        default=235, gt=0, le=240
    )
    academic_solver_retrieval_timeout_seconds: float = Field(
        default=30, gt=0, le=120
    )
    academic_solver_vision_timeout_seconds: float = Field(
        default=60, gt=0, le=180
    )
    academic_solver_min_generation_seconds: float = Field(
        default=90, gt=0, le=180
    )

    upload_max_image_size_mb: int = Field(default=6, ge=1, le=50)
    upload_max_images: int = Field(default=8, ge=1, le=32)
    image_max_long_edge: int = Field(default=4096, ge=256, le=16384)
    image_auto_rotate: bool = True
    image_remove_exif: bool = True
    multi_image_stitch_max_images: int = Field(default=4, ge=2, le=8)
    multi_image_stitch_max_total_pixels: int = Field(
        default=16_000_000, ge=1_000_000, le=100_000_000
    )
    multi_image_stitch_max_canvas_edge: int = Field(default=4096, ge=1024, le=8192)
    multi_image_stitch_max_aspect_ratio: float = Field(default=4.0, ge=1.5, le=20)
    multi_image_preserve_originals: bool = True
    multi_image_fallback_concurrency: int = Field(default=2, ge=1, le=4)
    multi_image_summary_max_chars: int = Field(default=24_000, ge=2000, le=100_000)

    enable_spark_reasoner: bool = True
    enable_qwen_text_fast: bool = True
    enable_qwen_vision_fast: bool = True
    enable_qwen_vision_primary: bool = True
    enable_dual_model_verification: bool = True
    dual_model_min_risk_level: Literal["low", "medium", "high", "critical"] = "high"
    student_verification_model_enabled: bool = False

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "xzd_minio"
    minio_secret_key: str = "change_me"
    minio_bucket: str = "xzd-files"
    minio_secure: bool = False

    default_agent_provider: Literal["mock", "xingchen"] = "mock"
    allow_mock_fallback: bool = True
    xingchen_enabled: bool = False
    xingchen_workflows_default_enabled: bool = False
    xingchen_publication_status: str = "published"
    xingchen_base_url: str = "https://xingchen-api.xf-yun.com"
    xingchen_workflow_path: str = "/workflow/v1/chat/completions"
    xingchen_upload_path: str = "/workflow/v1/upload_file"
    xingchen_api_key: SecretStr = SecretStr("")
    xingchen_api_secret: SecretStr = SecretStr("")
    xingchen_solver_ct_flow_id: str = ""
    xingchen_fallback_flow_id: str = ""
    xingchen_fallback_router_flow_id: str = ""
    xingchen_knowledge_qa_flow_id: str = ""
    xingchen_lesson_prep_flow_id: str = ""
    xingchen_assignment_review_flow_id: str = ""
    xingchen_academic_writing_flow_id: str = ""
    xingchen_data_analysis_flow_id: str = ""
    xingchen_uid: str = "local-demo-user"
    xingchen_timeout_seconds: float = Field(
        default=XINGCHEN_TIMEOUT_DEFAULT_SECONDS,
        ge=XINGCHEN_TIMEOUT_MIN_SECONDS,
        le=XINGCHEN_TIMEOUT_MAX_SECONDS,
    )
    xingchen_connect_timeout_seconds: float = Field(default=10, gt=0, le=120)
    xingchen_read_timeout_seconds: float = Field(default=300, gt=0, le=600)
    xingchen_write_timeout_seconds: float = Field(default=30, gt=0, le=120)
    xingchen_pool_timeout_seconds: float = Field(default=10, gt=0, le=120)
    xingchen_max_connections: int = Field(default=20, ge=1, le=100)
    xingchen_max_keepalive_connections: int = Field(default=10, ge=1, le=100)
    cloud_concurrency_limit: int = Field(default=4, ge=1, le=32)
    cloud_circuit_failure_threshold: int = Field(default=3, ge=1, le=20)
    cloud_circuit_reset_seconds: float = Field(default=30, gt=0, le=600)
    xingchen_use_local_kb_context: bool = True
    xingchen_bot_id: str = ""
    workflow_default_timeout_seconds: int = Field(default=120, ge=1, le=600)
    workflow_max_retries: int = Field(default=1, ge=0, le=3)

    max_upload_size_mb: int = Field(default=20, gt=0)
    local_storage_fallback: bool = True
    local_storage_path: Path = PROJECT_ROOT / "local_storage"
    sse_heartbeat_seconds: float = Field(default=10.0, gt=0)

    knowledge_enabled: bool = True
    knowledge_ct_path: Path = PROJECT_ROOT / "电路理论"
    knowledge_ae_path: Path = PROJECT_ROOT / "模电"
    knowledge_de_path: Path = PROJECT_ROOT / "数电"
    knowledge_ss_path: Path = PROJECT_ROOT / "信号与系统版本一"
    knowledge_dsp_path: Path = PROJECT_ROOT / "数字信号处理"
    knowledge_comm_path: Path = PROJECT_ROOT / "通信原理"
    knowledge_chunk_size_chars: int = Field(default=400, ge=300, le=4000)
    knowledge_chunk_overlap_chars: int = Field(default=150, ge=0, le=500)
    knowledge_default_top_k: int = Field(default=5, ge=1, le=20)
    knowledge_max_files_per_course: int = Field(default=1000, ge=1, le=10000)
    knowledge_max_file_size_mb: int = Field(default=5, ge=1, le=100)
    knowledge_config_path: Path = PROJECT_ROOT / "knowledge_config"
    knowledge_index_path: Path = PROJECT_ROOT / "knowledge_indexes"
    knowledge_min_score_v2: float = Field(default=0.35, ge=0)
    knowledge_low_confidence_threshold: float = Field(default=0.45, ge=0, le=1)
    knowledge_max_hits_per_document: int = Field(default=2, ge=1, le=10)
    knowledge_max_context_chars: int = Field(default=6000, ge=500, le=50000)
    knowledge_keyword_weight: float = Field(default=1.0, ge=0, le=10)
    knowledge_image_context_weight: float = Field(default=0.4, ge=0, le=10)

    rag_enabled: bool = True
    rag_warmup_on_startup: bool = True
    rag_warmup_image_model: bool = True
    rag_warmup_reranker: bool = False
    rag_warmup_strict: bool = False
    text_embedding_provider: Literal["local", "local_bge", "hash_legacy"] = "local_bge"
    text_embedding_model: str = "BAAI/bge-small-zh-v1.5"
    text_embedding_revision: str = "7999e1d3359715c523056ef9478215996d62a620"
    text_embedding_device: Literal["auto", "cpu", "cuda", "mps"] = "auto"
    text_embedding_batch_size: int = Field(default=8, ge=1, le=128)
    text_embedding_normalize: bool = True
    text_embedding_max_length: int = Field(default=1024, ge=64, le=8192)
    text_embedding_cache_dir: Path | None = None
    text_embedding_trust_remote_code: bool = False
    text_embedding_query_instruction: str = ""
    rag_model_local_files_only: bool = True
    text_colbert_enabled: bool = False
    legacy_hash_embedding_enabled: bool = True
    legacy_hash_embedding_dimension: int = Field(default=384, ge=8, le=4096)

    image_embedding_enabled: bool = True
    image_embedding_provider: Literal["local_siglip2"] = "local_siglip2"
    image_embedding_model: str = "google/siglip2-base-patch16-224"
    image_embedding_revision: str = "main"
    image_embedding_device: Literal["auto", "cpu", "cuda", "mps"] = "auto"
    image_embedding_batch_size: int = Field(default=4, ge=1, le=64)
    image_embedding_normalize: bool = True
    image_embedding_cache_dir: Path | None = None
    image_caption_embedding_enabled: bool = True

    reranker_enabled: bool = True
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_revision: str = "main"
    reranker_device: Literal["auto", "cpu", "cuda", "mps"] = "auto"
    reranker_top_n: int = Field(default=20, ge=1, le=100)
    reranker_output_k: int = Field(default=5, ge=1, le=20)

    vector_store_provider: Literal["qdrant"] = "qdrant"
    qdrant_mode: Literal["local", "server"] = "local"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr = SecretStr("")
    qdrant_trust_env: bool = False
    qdrant_local_path: Path = PROJECT_ROOT / "knowledge_indexes" / "qdrant"
    qdrant_text_collection: str = "xinzhi_kb_text_v2"
    qdrant_image_collection: str = "xinzhi_kb_image_v2"

    rag_dense_candidate_k: int = Field(default=20, ge=1, le=100)
    rag_sparse_candidate_k: int = Field(default=20, ge=1, le=100)
    rag_image_candidate_k: int = Field(default=12, ge=1, le=100)
    rag_final_text_k: int = Field(default=5, ge=1, le=20)
    rag_final_image_k: int = Field(default=3, ge=0, le=20)
    rag_rrf_k: int = Field(default=60, ge=1, le=1000)
    rag_query_cache_size: int = Field(default=256, ge=0, le=10000)
    rag_result_cache_size: int = Field(default=128, ge=0, le=10000)
    rag_result_cache_ttl_seconds: float = Field(default=300, ge=0, le=86400)
    text_embedding_concurrency_limit: int = Field(default=2, ge=1, le=16)
    image_embedding_concurrency_limit: int = Field(default=1, ge=1, le=8)
    reranker_concurrency_limit: int = Field(default=1, ge=1, le=8)
    reranker_conditional_score_gap: float = Field(default=0.01, ge=0, le=1)
    rag_retrieval_worker_count: int = Field(default=2, ge=1, le=8)
    rag_default_use_reranker: bool = False
    rag_chunker_version: str = "semantic_v2"
    rag_cleaning_version: str = "clean_v1"
    rag_schema_version: str = "2"
    rag_sufficient_min_sources: int = Field(default=2, ge=1, le=10)
    rag_sufficient_min_score: float = Field(default=0.45, ge=0, le=1)
    rag_partial_min_score: float = Field(default=0.01, ge=0, le=1)

    rag_debug_enabled: bool = True
    rag_debug_max_input_chars: int = Field(default=2000, ge=100, le=20000)
    rag_debug_trace_max_records: int = Field(default=100, ge=1, le=10000)
    rag_debug_trace_ttl_seconds: float = Field(default=3600, ge=60, le=86400)

    enable_debug_api: bool = True
    enable_evaluation_api: bool = False
    enable_local_knowledge_qa: bool = True
    enable_local_solver_ct: bool = False
    enable_xingchen_fallback: bool = False

    vision_enabled: bool = False
    vision_endpoint: str = ""
    vision_max_concurrency: int = Field(default=2, ge=1, le=8)
    vision_max_images_per_request: int = Field(default=8, ge=1, le=32)
    pdf_max_size_mb: int = Field(default=20, ge=1, le=200)
    pdf_max_pages: int = Field(default=40, ge=1, le=500)
    pdf_render_dpi: int = Field(default=144, ge=72, le=300)
    pdf_max_concurrency: int = Field(default=2, ge=1, le=8)
    temporary_file_ttl_seconds: int = Field(default=3600, ge=60, le=86400)

    allow_agent_mocks: bool = False
    agent_mock_profiles_path: Path = (
        PROJECT_ROOT / "agent_configs" / "mock_profiles.yaml"
    )
    agent_mock_max_latency_ms: int = Field(default=100, ge=0, le=2000)

    student_image_max_size_mb: int = Field(default=8, ge=1, le=20)
    student_upload_ttl_seconds: int = Field(default=3600, ge=300, le=86400)
    student_conversation_summary_chars: int = Field(default=800, ge=100, le=2000)
    student_previous_answer_chars: int = Field(default=600, ge=100, le=2000)

    context_max_input_tokens: int = Field(default=16_000, ge=1_000, le=1_000_000)
    context_reserved_output_tokens: int = Field(default=4_096, ge=256, le=262_144)
    context_compaction_trigger_ratio: float = Field(default=0.70, ge=0.1, le=0.95)
    context_recent_message_limit: int = Field(default=12, ge=2, le=100)
    context_relevant_older_limit: int = Field(default=6, ge=0, le=50)
    context_memory_limit: int = Field(default=8, ge=0, le=50)
    context_summary_target_tokens: int = Field(default=1_200, ge=100, le=8_000)
    context_summary_message_trigger: int = Field(default=24, ge=4, le=1_000)
    conversation_memory_summary_enabled: bool = True
    conversation_memory_summary_max_turn_chars: int = Field(
        default=12_000, ge=1_000, le=50_000
    )
    conversation_memory_summary_max_items: int = Field(default=8, ge=1, le=20)
    context_cache_ttl_seconds: int = Field(default=300, ge=1, le=86_400)
    context_cache_max_entries: int = Field(default=256, ge=1, le=10_000)
    context_config_version: str = "conversation-v2"

    route_budget_ms: int = Field(default=50, ge=1, le=5000)
    normalization_budget_ms: int = Field(default=20, ge=1, le=5000)
    retrieval_p95_target_ms: int = Field(default=600, ge=1, le=30000)
    context_format_budget_ms: int = Field(default=50, ge=1, le=5000)
    local_total_p95_target_ms: int = Field(default=1000, ge=1, le=30000)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL 必须是标准 Python 日志级别")
        return normalized

    @model_validator(mode="after")
    def validate_academic_solver_deadlines(self) -> Settings:
        deadline_groups = (
            (
                self.academic_solver_soft_deadline_seconds,
                self.academic_solver_finalization_deadline_seconds,
                self.academic_solver_hard_deadline_seconds,
                "standard",
            ),
            (
                self.academic_solver_complex_soft_deadline_seconds,
                self.academic_solver_complex_finalization_deadline_seconds,
                self.academic_solver_complex_hard_deadline_seconds,
                "complex",
            ),
        )
        for soft, finalization, hard, label in deadline_groups:
            if not 0 < soft <= finalization <= hard:
                raise ValueError(
                    f"{label} solver deadlines must satisfy soft <= "
                    "finalization <= hard"
                )
        return self

    @property
    def active_database_url(self) -> str:
        return self.test_database_url if self.app_env == "test" else self.database_url

    @property
    def xingchen_runtime_available(self) -> bool:
        return self.xingchen_enabled and all(
            (
                self.xingchen_api_key.get_secret_value(),
                self.xingchen_api_secret.get_secret_value(),
                self.xingchen_solver_ct_flow_id,
            )
        )

    def resolve_flow_env(self, env_name: str | None) -> str | None:
        """Resolve an allow-listed Flow setting without reading process env directly."""

        if (
            not env_name
            or not env_name.startswith("XINGCHEN_")
            or not env_name.endswith("_FLOW_ID")
        ):
            return None
        if env_name == "XINGCHEN_FALLBACK_FLOW_ID":
            value = (
                self.xingchen_fallback_flow_id or self.xingchen_fallback_router_flow_id
            )
        else:
            value = getattr(self, env_name.lower(), "")
        if not isinstance(value, str):
            return None
        return value.strip() or None

    @property
    def knowledge_paths(self) -> dict[str, Path]:
        return {
            "CT": self._resolve_local_placeholder(self.knowledge_ct_path, "电路理论"),
            "AE": self._resolve_local_placeholder(self.knowledge_ae_path, "模电"),
            "DE": self._resolve_local_placeholder(self.knowledge_de_path, "数电"),
            "SS": self._resolve_local_placeholder(
                self.knowledge_ss_path, "信号与系统版本一"
            ),
            "DSP": self._resolve_local_placeholder(
                self.knowledge_dsp_path, "数字信号处理"
            ),
            "COMM": self._resolve_local_placeholder(
                self.knowledge_comm_path, "通信原理"
            ),
        }

    @staticmethod
    def _resolve_local_placeholder(configured: Path, source_name: str) -> Path:
        """Resolve an empty repo-local placeholder to the actual source folder."""

        placeholder_root = (PROJECT_ROOT / "local_knowledge").resolve()
        configured_resolved = configured.resolve()
        try:
            configured_resolved.relative_to(placeholder_root)
        except ValueError:
            return configured
        has_material = configured_resolved.is_dir() and any(
            path.is_file() and path.name != ".gitkeep"
            for path in configured_resolved.rglob("*")
        )
        discovered = PROJECT_ROOT / source_name
        if not has_material and discovered.is_dir():
            return discovered
        return configured


@lru_cache
def get_settings() -> Settings:
    return Settings()
