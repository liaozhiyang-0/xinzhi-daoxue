# 外部网络检索阶段 2–5 设计与运行说明

## 目标

在不扩大本地专业求解边界的前提下，为已发布 Agent 增加可控的外部检索能力，覆盖学术论文、网页知识和后续可扩展的检索 Provider。

## 阶段 2：配置与 Agent 能力声明

- 全局开关：`EXTERNAL_RETRIEVAL_ENABLED`，默认 `true`；请求仍必须通过用户意图门控。
- 意图门控：`EXTERNAL_RETRIEVAL_INTENT_GATE_ENABLED`，默认 `true`。
- Agent 级策略位于 `agent_configs/registry.yaml` 的 `retrieval_policy.external`。
- Provider 名称与来源范围由策略声明，避免在任务路由中硬编码。
- 当前内置学术 Provider：`arxiv`、`crossref`、`openalex`、`semantic_scholar`；中国知网使用可配置的授权 JSON 网关 `cnki`；网页 Provider 使用可配置的 JSON 搜索网关。
- 创建任务仍只负责入队，Provider 调用发生在后台 `TaskRunner`。

只有同时满足全局开关、Agent 策略、有效查询条件和外部检索意图时，才会执行外部检索。

意图识别优先匹配显式联网/搜索请求、论文/文献/引用、最新/近期信息、新闻/政策/版本/价格等时效性事实。普通概念解释、常规课程问答和纯解题没有这些信号时会跳过外部 Provider。学术写作 Agent 可通过 `intent_allowlist` 声明在没有关键词时也允许检索。

## 阶段 3：检索编排与证据边界

`AcademicSearchService` 对多个 Provider 并发检索，进行结果去重、数量限制和单 Provider 故障隔离。TaskRunner 会发送：

1. `external_retrieval.started`
2. `external_retrieval.completed` 或 `external_retrieval.failed`

检索候选不会直接展示。TaskRunner 会将候选论文批量交给
`ACADEMIC_PAPER_REVIEW_LOCAL_V1`，审核标题、摘要、领域相关性和日期；只有模型覆盖并批准的记录才会进入前端卡片。审核模型不可用、候选未被覆盖或日期明显异常时，系统按 fail-closed 处理，不展示未经审核的论文。

检索结果以结构化证据保存到任务结果，并以 `[UNTRUSTED_EXTERNAL_EVIDENCE]` 标记注入生成上下文。外部网页内容不被视为系统指令，默认只传递摘要和元数据。

## 阶段 4：安全与引用校验

- 网页抓取默认关闭，必须同时启用 Agent 策略和全局 `EXTERNAL_RETRIEVAL_ALLOW_FULL_TEXT`。
- 抓取器手动处理有限次数重定向，并拒绝本地、回环、链路本地、保留和私有地址。
- 仅允许 HTTP(S)，拒绝 URL 用户凭据；限制响应类型、大小和文本长度。
- HTML 会移除脚本、样式和标记内容；抓取结果保存内容哈希及 `untrusted_external` 信任标记。
- 模型输出中的外部引用必须使用 `[evidence_id]`，系统会检查缺失引用、未知证据 ID 和非 HTTP(S) URL，并将问题写入 warnings。

## 阶段 5：事件流与重连

外部检索事件沿用现有事件存储和 SSE 通道，包含单调递增的 `seq`。客户端可通过 `Last-Event-ID` 从指定事件之后继续读取；测试覆盖事件顺序、失败事件和重连行为。

## 配置示例

PowerShell：

```powershell
$env:EXTERNAL_RETRIEVAL_ENABLED = "true"
$env:EXTERNAL_RETRIEVAL_INTENT_GATE_ENABLED = "true"
$env:EXTERNAL_RETRIEVAL_MAX_RESULTS = "6"
# 可选：配置兼容 results=[{title,url,content/snippet,...}] 的 JSON 网关
$env:EXTERNAL_WEB_SEARCH_BASE_URL = "https://search-gateway.example/v1/search"
$env:EXTERNAL_WEB_SEARCH_API_KEY = "<secret-from-secret-store>"
```

`arXiv`、`Crossref` 和 `OpenAlex` 默认使用公开 API；Semantic Scholar API Key 为可选配置。中国知网没有稳定的公开匿名元数据 API，不能直接把检索网页当作稳定接口；接入 CNKI 必须配置机构授权的 JSON 网关：

```powershell
$env:EXTERNAL_CNKI_BASE_URL = "https://your-institution.example/cnki/search"
$env:EXTERNAL_CNKI_API_KEY = "<secret-from-secret-store>"
$env:EXTERNAL_CNKI_AUTH_HEADER = "x-api-key"
```

网关返回格式为 `results=[{id,title,url,abstract,authors,venue,published_date,doi}]`。如果 CNKI 网关未配置，系统不会伪造 CNKI 论文或摘要；如果请求失败，结果 warnings 会保留 `cnki: timeout`、`cnki: http_429` 等具体原因。生产环境应通过密钥管理系统注入凭据，不应写入 YAML、源码或测试数据。

## 验证命令

从仓库根目录执行：

```powershell
$env:PYTHONPATH = ((Get-Location).Path + ";" + (Join-Path (Get-Location) "apps/api"))
& ".venv\Scripts\python.exe" -m pytest -q apps/api/tests
& ".venv\Scripts\python.exe" scripts/validate_config.py
& ".venv\Scripts\python.exe" scripts/check_sensitive_files.py
```

当前测试使用 Fake Provider 或本地响应，不代表真实外部网络服务已完成联调。上线前应使用隔离的测试凭据执行一次受限的 Provider smoke test，并检查限流、超时、引用完整性和 SSE 重连。
