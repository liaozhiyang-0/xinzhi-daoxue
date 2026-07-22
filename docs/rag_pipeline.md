# RAG Pipeline

当前主链复用已有实现：查询规范化与改写、课程过滤、BM25/词项召回、BGE dense 召回、RRF 融合、去重、阈值与可选 BGE reranker，最后生成 `RetrievalContextPacket` 和可追踪的 `kb://` 引用。

知识块保存 document/chunk ID、课程、章节、标题、相对路径、内容类型、校验和、相关图片、Embedding 模型/版本和索引版本。不存在的页码不会被补造；Markdown 无页码时引用 chunk/章节。

```powershell
python scripts/knowledge_base_cli.py build --rag --text --course CT --batch-size 8
python scripts/rebuild_index.py --course CT --text --dry-run
python scripts/migrate_legacy_index.py --course CT --dry-run
```

生产环境不会自动降级为哈希向量。开发环境只有在 `LEGACY_HASH_EMBEDDING_ENABLED=true` 且真实模型加载失败时才启用兼容 Provider，并记录 `legacy_embedding_fallback=true`。迁移脚本不删除旧索引。
