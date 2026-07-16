# 本地知识库接入说明

## 数据边界

- 原始 `电路理论`、`模电`、`数电` 目录保持原位。
- Docker 以只读 bind mount 挂载到 `/knowledge/CT`、`/knowledge/AE`、`/knowledge/DE`。
- Git 和 Docker build context 不包含教材原文。
- API 只读取 UTF-8 `.md`，不解压 ZIP、不执行文件、不解析 PDF、不读取图片像素。

## 检索流程

```text
Markdown -> 标题分节 -> 定长重叠分块 -> 中英文词项索引
         -> BM25 风格排序 -> 相对路径命中 -> kb:// 引用
```

索引为进程内只读索引，首次查询时延迟构建；开发环境可调用 reload。未来可在保持
`KnowledgeHit` 合同不变的情况下替换为 PostgreSQL、向量数据库或独立检索服务。

## API

```http
GET  /api/v1/knowledge/sources
POST /api/v1/knowledge/search
POST /api/v1/knowledge/reload
```

示例：

```json
{
  "query": "戴维南等效电路",
  "course_ids": ["CT"],
  "top_k": 5
}
```

课程编号为 `CT`（电路理论）、`AE`（模拟电子技术）、`DE`（数字电子技术）。响应不暴露
宿主机绝对路径，只返回相对文档路径、片段、评分和 `kb://` 来源引用。

## 任务链路

TaskRunner 从 `canonical_input.text/question/problem/query/prompt` 提取检索词，在不占用数据库
连接的情况下执行检索，随后写入 `knowledge.retrieved` 事件。命中项进入
`structured_result.knowledge`、`citations` 与 Artifact `source_refs`。

Mock Provider 仍明确是 Mock；知识库命中只证明检索链路可用，不代表已完成智能解题。

## Docker 自动发现

`scripts/docker_dev.ps1` 和 `docker_dev.sh` 依次查找：

1. 当前仓库下的中文知识库目录；
2. 相邻 `xinzhi-daoxue` 工作目录下的中文知识库目录；
3. `local_knowledge/` 空目录回退。

可通过 `KNOWLEDGE_CT_HOST_PATH`、`KNOWLEDGE_AE_HOST_PATH`、
`KNOWLEDGE_DE_HOST_PATH` 显式覆盖宿主机路径。

## 当前限制

- 索引在 API 进程内，重启后需要重新构建，不适用于大规模多副本部署。
- 中文字符与双字词项检索能处理课程关键词，但不等同于 Embedding 语义检索。
- 未建立图片 OCR/视觉向量、PDF 页码引用和权限模型。
- 原始文档的 OCR 噪声会影响命中质量，应在下一阶段建立清洗清单和回归查询集。
