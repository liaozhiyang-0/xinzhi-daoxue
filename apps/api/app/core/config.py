from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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
    app_debug: bool = True
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"

    # Authentication is opt-in for local development and mandatory in production.
    auth_required: bool = False
    auth_allow_registration: bool = True
    auth_allow_guest: bool = True
    auth_guest_ttl_seconds: int = Field(default=86_400, ge=300, le=31_536_000)
    auth_guest_cookie_name: str = "xzd_guest_token"
    auth_guest_signing_key: SecretStr = SecretStr("")
    auth_access_ttl_seconds: int = Field(default=900, ge=60, le=86_400)
    auth_refresh_ttl_seconds: int = Field(default=2_592_000, ge=3_600, le=31_536_000)
    auth_access_cookie_name: str = "xzd_access_token"
    auth_refresh_cookie_name: str = "xzd_refresh_token"
    auth_cookie_secure: bool = False
    auth_cookie_same_site: Literal["lax", "strict", "none"] = "lax"
    auth_login_max_attempts: int = Field(default=5, ge=1, le=20)
    auth_login_window_seconds: int = Field(default=300, ge=30, le=3_600)
    auth_login_lockout_seconds: int = Field(default=900, ge=60, le=86_400)
    auth_scrypt_n_log2: int = Field(default=15, ge=14, le=20)
    auth_scrypt_r: int = Field(default=8, ge=1, le=32)
    auth_scrypt_p: int = Field(default=1, ge=1, le=8)

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "sqlite+aiosqlite:///./xzd-dev.db"
    test_database_url: str = "sqlite+aiosqlite:///./test.db"
    redis_url: str = "redis://localhost:6379/0"
    vector_store_path: Path = PROJECT_ROOT / "knowledge_indexes"
    upload_dir: Path = PROJECT_ROOT / "local_storage" / "uploads"
    cache_dir: Path = PROJECT_ROOT / "local_storage" / "cache"
    scenario_catalog_path: Path = PROJECT_ROOT / "config" / "scenarios.yaml"

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

    # A single fast model call may refine the deterministic route before execution.
    # Overall Router is an explicit legacy compatibility switch after Phase B.
    # Planner/TaskRouter own the default control path; opt-in is retained for
    # rollback and older deployments that still need the second-pass route.
    overall_routing_enabled: bool = False
    overall_routing_timeout_seconds: float = Field(default=10, gt=0, le=30)
    overall_routing_max_tokens: int = Field(default=160, ge=64, le=512)
    overall_routing_skip_confidence_threshold: float = Field(
        default=0.95, ge=0.5, le=1.0
    )

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
    academic_solver_retrieval_timeout_seconds: float = Field(default=30, gt=0, le=120)
    academic_solver_vision_timeout_seconds: float = Field(default=60, gt=0, le=180)
    academic_solver_min_generation_seconds: float = Field(default=90, gt=0, le=180)

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

    default_agent_provider: Literal["local", "mock"] = "local"
    allow_mock_fallback: bool = True
    workflow_default_timeout_seconds: int = Field(default=120, ge=1, le=600)
    workflow_max_retries: int = Field(default=1, ge=0, le=3)

    max_upload_size_mb: int = Field(default=20, gt=0)
    document_max_files_per_task: int = Field(default=8, ge=1, le=32)
    evaluation_attachment_cleanup_grace_seconds: int = Field(
        default=86_400, ge=60, le=2_592_000
    )
    document_max_pages: int = Field(default=200, ge=1, le=2000)
    document_max_extracted_chars: int = Field(default=80_000, ge=4_000, le=500_000)
    document_chunk_size_chars: int = Field(default=1_200, ge=200, le=10_000)
    document_chunk_overlap_chars: int = Field(default=160, ge=0, le=2_000)
    document_extraction_timeout_seconds: float = Field(default=30, gt=0, le=300)
    document_converter_command: str = "soffice"
    local_storage_fallback: bool = True
    local_storage_path: Path = PROJECT_ROOT / "local_storage"
    research_analysis_artifact_root: Path = (
        PROJECT_ROOT / ".local_outputs" / "research_analysis"
    )
    research_analysis_temp_root: Path = (
        PROJECT_ROOT / ".local_outputs" / "research_analysis_tmp"
    )
    research_analysis_model_assist_enabled: bool = True
    research_analysis_model_assist_max_tokens: int = Field(
        default=900, ge=256, le=4000
    )
    research_analysis_model_direct_enabled: bool = True
    research_analysis_model_direct_max_tokens: int = Field(
        default=2400, ge=512, le=8000
    )
    research_analysis_model_input_max_chars: int = Field(
        default=80_000, ge=10_000, le=500_000
    )
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
    knowledge_ocr_decisions_path: Path = (
        PROJECT_ROOT / ".local_outputs" / "ocr_decisions"
    )
    knowledge_ocr_review_cache_enabled: bool = True
    knowledge_ocr_review_cache_path: Path = (
        PROJECT_ROOT / ".local_outputs" / "ocr_review_snapshots"
    )
    knowledge_ocr_review_cache_ttl_seconds: int = Field(
        default=300, ge=1, le=86_400
    )
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
    # Hash vectors are a compatibility fixture, not a semantic RAG fallback.
    # Enable explicitly for isolated legacy tests; normal development must fail
    # closed when the configured real embedding model is unavailable.
    legacy_hash_embedding_enabled: bool = False
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
    qdrant_research_collection: str = "xinzhi_research_evidence_v1"

    research_knowledge_enabled: bool = True
    research_knowledge_maintenance_enabled: bool = True
    research_knowledge_maintenance_interval_seconds: int = Field(
        default=86_400, ge=3_600, le=2_592_000
    )
    research_knowledge_retention_days: int = Field(default=1095, ge=30, le=3650)
    research_knowledge_search_top_k: int = Field(default=8, ge=1, le=30)

    # LangGraph checkpoints are process-local until a durable saver is wired.
    # Keep the backend explicit so production cannot mistake memory for a
    # restart-safe persistence layer.
    langgraph_checkpoint_enabled: bool = True
    langgraph_checkpoint_backend: Literal["disabled", "memory"] = "memory"

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

    # External retrieval is available by default, but intent recognition must
    # still approve the request before any provider is contacted.
    external_retrieval_enabled: bool = True
    external_retrieval_intent_gate_enabled: bool = True
    external_retrieval_timeout_seconds: float = Field(default=120, gt=0, le=180)
    external_retrieval_review_enabled: bool = True
    external_retrieval_planning_timeout_seconds: float = Field(
        default=6, gt=0, le=60
    )
    external_retrieval_planning_max_tokens: int = Field(
        default=700, ge=256, le=4000
    )
    external_retrieval_review_timeout_seconds: float = Field(default=10, gt=0, le=60)
    external_retrieval_review_max_tokens: int = Field(default=2400, ge=512, le=8000)
    external_retrieval_provider_retries: int = Field(default=1, ge=0, le=3)
    external_retrieval_max_provider_concurrency: int = Field(
        default=4, ge=1, le=16
    )
    external_retrieval_max_query_variants: int = Field(default=2, ge=1, le=6)
    external_retrieval_rate_limit_cooldown_seconds: float = Field(
        default=60, ge=0, le=3600
    )
    external_retrieval_cache_size: int = Field(default=128, ge=0, le=10_000)
    external_retrieval_cache_ttl_seconds: float = Field(
        default=120, ge=0, le=86_400
    )
    external_retrieval_max_results: int = Field(default=8, ge=1, le=50)
    external_retrieval_max_fetches: int = Field(default=4, ge=0, le=20)
    external_retrieval_allow_full_text: bool = False
    external_retrieval_max_content_chars: int = Field(
        default=12_000, ge=500, le=100_000
    )
    external_arxiv_base_url: str = "https://export.arxiv.org/api"
    external_arxiv_min_delay_seconds: float = Field(default=3, ge=0, le=30)
    external_arxiv_timeout_seconds: float = Field(default=30, gt=0, le=120)
    external_arxiv_max_concurrency: int = Field(default=1, ge=1, le=4)
    external_crossref_base_url: str = "https://api.crossref.org"
    external_crossref_mailto: str = ""
    external_crossref_min_delay_seconds: float = Field(
        default=0.5, ge=0, le=10
    )
    external_crossref_timeout_seconds: float = Field(default=30, gt=0, le=120)
    external_crossref_max_concurrency: int = Field(default=1, ge=1, le=4)
    external_openalex_base_url: str = "https://api.openalex.org"
    external_openalex_api_key: SecretStr = SecretStr("")
    external_openalex_mailto: str = ""
    external_openalex_min_delay_seconds: float = Field(
        default=0.5, ge=0, le=10
    )
    external_openalex_timeout_seconds: float = Field(default=45, gt=0, le=120)
    external_openalex_max_concurrency: int = Field(default=2, ge=1, le=4)
    external_semantic_scholar_base_url: str = "https://api.semanticscholar.org/graph/v1"
    external_semantic_scholar_api_key: SecretStr = SecretStr("")
    external_semantic_scholar_allow_unauthenticated: bool = False
    external_semantic_scholar_min_delay_seconds: float = Field(
        default=1, ge=0, le=30
    )
    external_semantic_scholar_timeout_seconds: float = Field(
        default=30, gt=0, le=120
    )
    external_semantic_scholar_max_concurrency: int = Field(default=1, ge=1, le=4)
    external_cnki_base_url: str = ""
    external_cnki_api_key: SecretStr = SecretStr("")
    external_cnki_auth_header: str = "x-api-key"
    external_cnki_timeout_seconds: float = Field(default=8, gt=0, le=60)
    external_web_search_base_url: str = ""
    external_web_search_api_key: SecretStr = SecretStr("")
    external_web_search_auth_header: str = "x-api-key"
    external_web_search_timeout_seconds: float = Field(default=15, gt=0, le=120)
    external_tavily_base_url: str = "https://api.tavily.com/search"
    external_tavily_api_key: SecretStr = SecretStr("")
    external_tavily_auth_header: str = "Authorization"
    external_tavily_auth_scheme: str = "Bearer"
    external_tavily_search_depth: str = "basic"
    external_tavily_topic: str = "general"
    external_tavily_include_answer: bool = False
    external_tavily_include_raw_content: bool = False
    external_tavily_min_delay_seconds: float = Field(default=1, ge=0, le=30)
    external_tavily_timeout_seconds: float = Field(default=30, gt=0, le=120)
    external_tavily_max_results: int = Field(default=5, ge=1, le=20)
    external_tavily_max_concurrency: int = Field(default=1, ge=1, le=4)
    external_brave_base_url: str = (
        "https://api.search.brave.com/res/v1/web/search"
    )
    external_brave_api_key: SecretStr = SecretStr("")
    external_brave_auth_header: str = "X-Subscription-Token"
    external_brave_country: str = "CN"
    external_brave_search_lang: str = "zh"
    external_brave_min_delay_seconds: float = Field(default=1, ge=0, le=30)
    external_brave_timeout_seconds: float = Field(default=30, gt=0, le=120)
    external_brave_max_results: int = Field(default=5, ge=1, le=20)
    external_brave_max_concurrency: int = Field(default=1, ge=1, le=4)
    external_serpapi_base_url: str = "https://serpapi.com/search.json"
    external_serpapi_api_key: SecretStr = SecretStr("")
    external_serpapi_engine: str = "google"
    external_serpapi_min_delay_seconds: float = Field(default=1, ge=0, le=30)
    external_serpapi_timeout_seconds: float = Field(default=30, gt=0, le=120)
    external_serpapi_max_results: int = Field(default=5, ge=1, le=20)
    external_serpapi_max_concurrency: int = Field(default=1, ge=1, le=4)
    external_searxng_base_url: str = ""
    external_searxng_api_key: SecretStr = SecretStr("")
    external_searxng_format: str = "json"
    external_searxng_categories: str = "general"
    external_searxng_language: str = "zh-CN"
    external_searxng_min_delay_seconds: float = Field(default=1, ge=0, le=30)
    external_searxng_timeout_seconds: float = Field(default=30, gt=0, le=120)
    external_searxng_max_results: int = Field(default=5, ge=1, le=20)
    external_searxng_max_concurrency: int = Field(default=1, ge=1, le=4)
    # Optional domestic web-search fallbacks.  They remain inactive until an
    # API key is supplied and their provider adapter is explicitly enabled.
    external_aliyun_iqs_base_url: str = "https://cloud-iqs.aliyuncs.com/search/unified"
    external_aliyun_iqs_api_key: SecretStr = SecretStr("")
    external_aliyun_iqs_engine_type: str = "Generic"
    external_aliyun_iqs_time_range: str = "NoLimit"
    external_aliyun_iqs_min_delay_seconds: float = Field(default=1, ge=0, le=30)
    external_aliyun_iqs_timeout_seconds: float = Field(default=30, gt=0, le=120)
    external_aliyun_iqs_max_results: int = Field(default=5, ge=1, le=20)
    external_aliyun_iqs_max_concurrency: int = Field(default=1, ge=1, le=4)
    external_bocha_base_url: str = "https://api.bochaai.com/v1/web-search"
    external_bocha_api_key: SecretStr = SecretStr("")
    external_bocha_auth_header: str = "Authorization"
    external_bocha_auth_scheme: str = "Bearer"
    external_bocha_freshness: str = "noLimit"
    external_bocha_summary: bool = True
    external_bocha_min_delay_seconds: float = Field(default=1, ge=0, le=30)
    external_bocha_timeout_seconds: float = Field(default=30, gt=0, le=120)
    external_bocha_max_results: int = Field(default=5, ge=1, le=20)
    external_bocha_max_concurrency: int = Field(default=1, ge=1, le=4)
    external_news_rss_base_url: str = "https://news.google.com/rss/search"
    external_news_rss_timeout_seconds: float = Field(default=15, gt=0, le=120)
    external_news_rss_min_delay_seconds: float = Field(default=1, ge=0, le=30)
    external_news_rss_max_concurrency: int = Field(default=1, ge=1, le=4)

    rag_debug_enabled: bool = True
    rag_debug_max_input_chars: int = Field(default=2000, ge=100, le=20000)
    rag_debug_trace_max_records: int = Field(default=100, ge=1, le=10000)
    rag_debug_trace_ttl_seconds: float = Field(default=3600, ge=60, le=86400)

    enable_debug_api: bool = True
    enable_evaluation_api: bool = False
    enable_local_knowledge_qa: bool = True
    # Product freeze: keep the data-analysis path reversible but unavailable.
    data_analysis_enabled: bool = False
    enable_local_solver_ct: bool = False

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
    task_executor_mode: Literal["local", "redis"] = "local"
    task_queue_name: str = "xzd:tasks"
    task_queue_block_timeout_seconds: int = Field(default=5, ge=1, le=60)
    task_worker_recovery_interval_seconds: int = Field(default=15, ge=5, le=300)
    task_worker_lock_ttl_seconds: int = Field(default=120, ge=30, le=3600)
    task_queue_dead_letter_enabled: bool = True
    task_queue_dead_letter_max_attempts: int = Field(default=3, ge=1, le=20)
    task_lease_seconds: int = Field(default=120, ge=30, le=3600)
    task_recovery_enabled: bool = True
    task_max_concurrency: int = Field(default=4, ge=1, le=64)
    agent_runtime_plan_proposals_enabled: bool = False
    # Kept as a compatibility switch for local Runtime integration callers;
    # explicit task options still decide which goal/runtime is executable.
    agent_runtime_shadow_enabled: bool = False
    agent_runtime_goal_capabilities: str = ""
    agent_runtime_canary_artifacts: str = ""
    agent_runtime_semantic_evidence: str = ""
    agent_runtime_release_authorizations: str = ""
    agent_runtime_release_gate_required: bool = True
    # Phase N Planner control plane. One mode is authoritative; the two older
    # booleans remain read-compatible for historical tests and adapters only.
    planner_mode: Literal["shadow", "controlled", "active"] = "active"
    circuit_visualization_mode: Literal["off", "shadow", "controlled"] = "off"
    # Deprecated Phase B compatibility switches; production code must use
    # planner_mode instead.
    planner_shadow_enabled: bool = False
    planner_takeover_enabled: bool = False
    planner_canary_agent_ids: str = ""
    planner_canary_scenario_ids: str = ""
    # Phase D Reflection controls. Both paths remain disabled unless explicitly enabled.
    reflection_shadow_enabled: bool = False
    reflection_revision_enabled: bool = False
    reflection_canary_agent_ids: str = ""
    reflection_critic_budget_tokens: int = Field(default=512, ge=128, le=4096)
    reflection_critic_budget_ms: int = Field(default=3000, ge=250, le=120000)
    # Phase E Experience prior.  Retrieval remains shadow-only unless all
    # gates are explicitly enabled by an operator.
    experience_planner_prior_enabled: bool = False
    experience_planner_capability_allowlist: str = ""
    experience_planner_minimum_evidence: Literal[
        "synthetic_provider_free",
        "offline_real_case",
        "real_provider_test",
        "controlled_canary",
        "production",
    ] = "offline_real_case"
    experience_planner_max_influence_weight: float = Field(
        default=0.15, ge=0, le=1
    )

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

    @model_validator(mode="after")
    def validate_authentication(self) -> Settings:
        if self.app_env == "production" and not self.auth_required:
            raise ValueError("AUTH_REQUIRED must be true in production")
        if self.app_env == "production" and self.qdrant_mode != "server":
            raise ValueError("QDRANT_MODE must be server in production")
        if (
            self.app_env == "production"
            and self.langgraph_checkpoint_enabled
            and self.langgraph_checkpoint_backend == "memory"
        ):
            raise ValueError(
                "LANGGRAPH_CHECKPOINT_BACKEND=memory is not restart-safe in production"
            )
        if (
            self.app_env == "production"
            and self.auth_allow_guest
            and not self.auth_guest_signing_key.get_secret_value()
        ):
            raise ValueError(
                "AUTH_GUEST_SIGNING_KEY must be set when guest mode is enabled "
                "in production"
            )
        # Debug surfaces and mock fallbacks must be disabled explicitly in
        # production; runtime guards alone are not enough because they can be
        # bypassed by a misconfigured deploy.
        if self.app_env == "production" and self.allow_mock_fallback:
            raise ValueError("ALLOW_MOCK_FALLBACK must be false in production")
        if self.app_env == "production" and self.default_agent_provider == "mock":
            raise ValueError("DEFAULT_AGENT_PROVIDER=mock is forbidden in production")
        if self.app_env == "production" and self.allow_agent_mocks:
            raise ValueError("ALLOW_AGENT_MOCKS must be false in production")
        if self.app_env == "production" and self.enable_debug_api:
            raise ValueError("ENABLE_DEBUG_API must be false in production")
        if self.app_env == "production" and self.rag_debug_enabled:
            raise ValueError("RAG_DEBUG_ENABLED must be false in production")
        if self.auth_cookie_same_site == "none" and not self.auth_cookie_secure:
            raise ValueError("AUTH_COOKIE_SECURE must be true when SameSite=None")
        return self

    @property
    def active_database_url(self) -> str:
        return self.test_database_url if self.app_env == "test" else self.database_url

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
