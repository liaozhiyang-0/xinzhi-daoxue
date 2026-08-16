# P0：CT/AE 旗舰教学闭环实施计划

## 目标

在不修改冻结的 `SOLVER_CT v1.0`/`SOLVER_CT_V1` 的前提下，复用现有 `POST /api/v1/files`、`DocumentIngestionService`、`DocumentChunkModel`、`KnowledgeBaseService`、`RAGRetrievalService`、`TaskRunner` 和学习闭环，先实现一个可审计的课程资料资产生命周期：

```text
教师上传资料
  -> 文件解析与 chunk 落库
  -> 课程/资料身份与版本记录
  -> 草稿状态
  -> 人工发布
  -> 作为课程证据来源参与后续索引/检索
```

## 边界

- “已发布”只表示教师确认该版本可用于课程知识空间，不表示模型答案正确，也不表示向量索引已完成。
- “Mock”只用于离线联调，所有 Mock 结果都必须显式标识。
- 任务创建仍然非阻塞；资料解析属于上传后的资料处理，不在任务路由中直接执行 Provider。
- 历史基线原始输入、真实 API Key 和未脱敏学生数据不进入公共目录。

## 任务分解

| 编号 | 状态 | 工作 |
|---|---|---|
| P0-1 | 已完成 | 在文件资产上增加课程、资料逻辑标识、版本和发布状态；保留 checksum 与解析版本 |
| P0-2 | 已完成 | 增加教师资产列表、发布和撤回 API；发布动作保留人工操作记录 |
| P0-3 | 已完成（仓库证据） | 把已发布资产映射到 RAG manifest/index 输入，区分 `not_indexed`、`indexed`、`stale`；真实索引环境验收仍需单独执行 |
| P0-4 | 已有基础 | 学生文本/单图任务、证据包、引用、工具验证、人工复核和学习状态复用现有链路 |
| P0-5 | 按用户范围延期 | 三个 Demo 案例由负责人自行设计；本长期任务不生成、不改写、不自动评测案例正文 |

## 验收命令

```powershell
$env:APP_ENV = "test"
$env:DEFAULT_AGENT_PROVIDER = "mock"
$env:ALLOW_MOCK_FALLBACK = "true"
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe scripts\check_sensitive_files.py
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy apps/api/app
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_document_ingestion.py apps/api/tests/test_knowledge_api.py -q
.\.venv\Scripts\python.exe scripts\validate_evaluation_cases.py
git diff --check
```

真实模型和 Docker 验收必须另行显式执行并单独报告，不能由上述离线命令替代。
## P0-1/P0-2 接口用法

课程资料必须带课程、逻辑资料标识和版本号，并通过现有文件上传链路解析为 chunks：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/files `
  -F "purpose=course_material" `
  -F "course_id=CT" `
  -F "material_key=kcl-intro" `
  -F "material_version=1.0.0" `
  -F "upload=@lesson.pdf"
```

教师或管理员可查看、发布和撤回课程资料：

```text
GET  /api/v1/knowledge/materials?course_id=CT
POST /api/v1/knowledge/materials/{file_id}/publish
POST /api/v1/knowledge/materials/{file_id}/withdraw
```

`knowledge_index_status=not_indexed` 表示文件已完成文本解析和 chunk 落库，但尚未进入向量索引；`indexed` 由 RAG 状态文件中的文件 checksum 证明，`stale` 表示资料已撤回、被替代或索引需要重建。

发布资料后，教师或管理员可生成 RAG 输入 manifest：

```text
POST /api/v1/knowledge/materials/manifest?course_id=CT
```

该接口只生成 `knowledge_indexes/course_material_manifest.jsonl` 和
`knowledge_indexes/cache/course_material_chunks.jsonl`，不调用 Embedding Provider。随后使用现有 CLI 构建向量索引：

```powershell
python scripts/knowledge_base_cli.py build --course CT --rag --delete-stale-points
```

## 当前状态

- P0-1 已完成：课程、资料标识、版本、发布状态和解析索引状态已落到文件资产。
- P0-2 已完成：教师/管理员材料列表、发布、撤回和审计记录已实现。
- P0-3 已完成第一版：发布资料可生成 RAG manifest/chunks，RAG 构建器读取上传资料并依据 checksum 暴露 `indexed/stale`；仍需真实环境验收索引构建。
- P0-5 按用户范围延期：CT/AE 演示案例留给负责人设计，不作为本长期任务的自动优化完成条件。
