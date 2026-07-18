# 本地多模态知识库构建与接入指南

## 1. 原始知识库

三门课程正文资料保留现有层级；经审计确认的孤立图片单独进入待复核区：

| 课程 | 课程编号 | 仓库相对路径 | 当前文件 | 当前图片 |
|---|---|---|---:|---:|
| 电路理论 | CT | `电路理论/` | 1099 | 1053 |
| 模拟电子技术 | AE | `模电/` | 624 | 602 |
| 数字电子技术 | DE | `数电/` | 575 | 551 |

常规索引工具不会移动、删除、重命名或覆盖这些文件。2026-07-17 经人工授权，69 张未被任何 Markdown 引用的图片已迁移到 `知识库/待复核_孤立图片/`，按课程和原相对路径保存，并附带 checksum 迁移清单。`local_knowledge/CT|AE|DE` 为空占位目录时，本地运行会自动发现上述真实目录；Docker 和显式外部挂载路径仍优先使用配置值。

## 2. 生成目录

```text
knowledge_indexes/
├── knowledge_base_manifest.jsonl
├── knowledge_base_image_evidence.jsonl
├── knowledge_base_quality_issues.json
├── knowledge_base_index_state.json
└── cache/
    └── knowledge_base_chunks.jsonl
```

`cache/` 包含教材正文切块，已加入 `.gitignore`。Manifest、图片证据和问题清单只保存相对路径、稳定 ID、checksum、状态和元数据，不暴露操作系统绝对路径。

## 3. 执行审计

只读审计，不写任何文件：

```powershell
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py audit
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py audit --course CT
```

正式审计结果位于：

- `docs/reviews/knowledge_base_audit_report.md`
- `knowledge_indexes/knowledge_base_quality_issues.json`

## 4. 构建索引

首次完整构建：

```powershell
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py build --full
```

按课程构建：

```powershell
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py build --course CT
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py build --course AE
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py build --course DE
```

默认构建为增量模式。工具按 SHA-256 判断文件是否变化，未变化文档复用原 chunk；缺失文件在 Manifest 中标记为 inactive。预演和单文件重建：

```powershell
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py build --dry-run
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py build --course CT --file "课本/基础篇/3-重置md/第一章.md"
```

## 5. 查询与验证

```powershell
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py query --course CT --text "为什么电容电压不能突变" --top-k 3
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py query --course AE --text "负反馈为什么能稳定放大倍数" --top-k 3
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py query --course DE --text "D触发器的时序特性" --top-k 3
.\.venv\Scripts\python.exe scripts\knowledge_base_cli.py validate
```

运行时检索模式为 `hybrid_local_v1`：

- `course_id` 强过滤；
- 现有 BM25/关键词评分；
- BGE 神经网络 dense 向量与 Qdrant 检索；
- 标题、章节、文件名和精确短语加权；
- checksum 去重、单文档数量限制和来源多样性；
- 文本命中后的上下文图片补充。

生产哈希伪向量已移除。正式路径通过 `TextEmbeddingProvider` 加载真实 BGE 模型；BM25 仅作为独立 sparse 分支保留，模型不可用时明确降级，绝不生成哈希或随机向量。

## 6. 文本处理

首版安全解析 UTF-8 Markdown、TXT、JSON 和 CSV。PDF、DOCX 与压缩包仅登记元数据，优先使用仓库已有的 Markdown 提取文本。

分块按标题和段落组合，尽量保持公式与解释、例题题干与解法完整；超长段落才按句子边界拆分。每个 chunk 保存稳定 `chunk_id`、`document_id`、课程、章节、标题、内容类型、原文件 checksum、来源 URI 和相关图片。

## 7. 图片处理

首版图片链路为：

```text
图片相对路径和 checksum
  -> Markdown 图片链接
  -> alt、邻近段落和所属章节
  -> 父文档与 chunk 关联
  -> kb-image:// 安全资源标识
  -> 随相关文本检索结果返回
```

当前能力明确为：

```text
multimodal_level = neural_multimodal_rag
```

正式图片路径使用 `google/siglip2-base-patch16-224` 从原始图片像素生成真实视觉向量，并与 BGE caption 向量分别保存为 Qdrant 命名向量。图片说明仍优先使用 Markdown alt、邻近正文、章节和文件名；系统不会猜测孤立图片内容，模型生成说明必须标记 `description_source=model_generated`。

已迁移孤立图片位于：

```text
知识库/待复核_孤立图片/
├── CT/                         # 29 张
├── AE/                         # 39 张
├── DE/                         # 1 张
└── orphan_image_move_manifest.json
```

迁移清单记录原路径、新路径、稳定图片编号、文件大小和 SHA-256，可用于人工归类或回迁。

## 8. RetrievalContextPacket 与 LEARN_01

本地流程：

```text
用户问题
  -> 课程强过滤
  -> Top 3 混合检索
  -> RetrievalContextPacket
  -> to_retrieved_context()
  -> 注入现有 AGENT_USER_INPUT
  -> LEARN_01_KNOWLEDGE_QA_V1
```

证据编号按 `S1`、`S2`、`S3` 生成，并与 Packet 内 `evidence_id` 一致。每条证据包含稳定 `kb://` 来源和可选 `kb-image://` 图片。证据不足时仍生成 Packet，并传递 `evidence_status` 与 warnings；不会把整本教材或整章发送给云端。

当前云端 LEARN 工作流仍为 planned/disabled，因此任务会降级到 `LEARN_01_LOCAL_RETRIEVAL_V1`。云端发布后只需启用现有注册项，不需要修改云端节点结构或增加 Provider。

## 9. SOLVER_CT

`SOLVER_CT_V1` 云端工作流保持冻结：

- 纯文字解题最多检索 Top 2；
- 只保留 `method`、`formula`、`concept`、`common_error` 类型证据；
- 图片解题继续跳过知识库；
- 注入内容明确标记为方法参考，不得覆盖用户题目参数和连接事实。

## 10. 已知限制与人工整理优先级

1. 修复 AE 第七章发现的失效图片链接。
2. 审核 `知识库/待复核_孤立图片/` 中的 69 张图片，确认回迁关联或永久排除状态。
3. 审核 CT 的无编号图片、映射表和目录文件。
4. 复核 AE 第一章等 OCR 异常标题，并将批准修正规则写入 `knowledge_config/corrections/`。
5. 补充教材名称、版本、章节来源和版权边界等元数据。
6. PDF/DOCX 解析、真正语义 Embedding 和视觉向量检索均留作可替换增强项，不属于首版已完成功能。
