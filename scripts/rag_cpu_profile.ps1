# Dot-source this file before running the API or knowledge CLI:
#   . .\scripts\rag_cpu_profile.ps1
# It intentionally contains no credentials and does not modify .env.

$env:TEXT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
$env:TEXT_EMBEDDING_DEVICE = "cpu"
$env:TEXT_EMBEDDING_BATCH_SIZE = "8"
$env:TEXT_EMBEDDING_MAX_LENGTH = "512"
$env:TEXT_EMBEDDING_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："
$env:IMAGE_EMBEDDING_MODEL = "google/siglip2-base-patch16-224"
$env:IMAGE_EMBEDDING_DEVICE = "cpu"
$env:IMAGE_EMBEDDING_BATCH_SIZE = "2"
$env:RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
$env:RERANKER_DEVICE = "cpu"
$env:RERANKER_ENABLED = "true"
$env:QDRANT_MODE = "local"
$env:KNOWLEDGE_CHUNK_SIZE_CHARS = "300"
$env:KNOWLEDGE_CHUNK_OVERLAP_CHARS = "50"

Write-Host "Loaded xinzhi multimodal RAG CPU profile (BGE-small/SigLIP2/Qdrant local)."
