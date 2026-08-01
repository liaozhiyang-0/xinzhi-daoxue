# 多模态材料输入

当前工作台支持在同一次任务中选择图片和文本材料。文件上传后先进入统一文件存储，再由服务端提取文本、生成分块并写入任务附件引用；任务创建仍然是非阻塞的，Agent/Provider 调用链不变。

## 支持格式

- 图片：`jpg`、`jpeg`、`png`、`webp`；继续沿用原有图片处理链路。
- 文本：`txt`、`md`、`csv`、`json`。
- 文档：`pdf`、`docx`、`doc`。

`txt`、`md`、`docx` 和可提取文本的 PDF 会生成 `ready` 状态和 `file_chunks`。扫描型 PDF 会标记为 `partial` 或 `failed`，并在元数据中标记 `ocr_required=true`，当前版本不会伪造 OCR 结果。`.doc` 解析依赖服务器上的 LibreOffice/`soffice`，未安装时会保留文件并显示明确失败原因。

## 配置

复制 `.env.example` 中的 `DOCUMENT_*` 配置，按服务器资源调整：

- `DOCUMENT_MAX_FILES_PER_TASK`：单任务最多材料数，默认 8。
- `DOCUMENT_MAX_PAGES`：PDF 最大页数，默认 200。
- `DOCUMENT_MAX_EXTRACTED_CHARS`：单文件提取文本上限，默认 80,000 字符。
- `DOCUMENT_CHUNK_SIZE_CHARS` / `DOCUMENT_CHUNK_OVERLAP_CHARS`：分块大小和重叠字符数。
- `DOCUMENT_CONVERTER_COMMAND`：`.doc` 转换器命令，默认 `soffice`。

数据库升级：

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

新增 `files` 摄取字段和 `file_chunks` 表，不修改已有 migration。

## 管理与排错

管理员登录 `/admin` 后打开“文件中心”，可以按文件名、类型和解析状态查询文件，查看解析统计、页数、关联任务和提取错误。文件分块接口为：

```text
GET /api/v1/files/{file_id}/chunks
```

当任务引用的文档仍处于 `pending`/`processing` 时，任务创建会返回可识别的冲突信息；`failed` 文件不会进入 Agent 上下文。提取文本会同时写入 `canonical_input.uploaded_text` 和附件元数据，后续可直接扩展 OCR、表格解析或向量索引，而无需改变前端附件协议。
