# 网络检索阶段 0：证据协议与安全边界

## 目标

本阶段只定义网络检索的稳定边界，不接入学生端任务执行链，不修改
不恢复已退役的 CT 专用 Solver，也不在 Agent 内部直接创建 HTTP Client。

外部资料与课程本地知识使用不同的契约：本地资料继续使用
`KnowledgeHit`、`kb://` 和现有 RAG 链；论文、网页和用户指定的外部来源使用
`ExternalEvidenceItem`。这样可以避免网络 URL 在尚未验证来源、时间和访问权限前，
被误当成课程知识库证据。

## 目标执行链

```text
AgentRequest
  -> AgentExecutionPlan
  -> RetrievalOrchestrator
     -> AcademicSearchProvider / WebSearchProvider / UserSourceProvider
     -> EvidenceNormalizer
     -> 去重、排序、时间和可信度策略
  -> ExternalRetrievalResult
  -> Evidence Packet（后续阶段）
  -> CitationValidator（后续阶段）
  -> Research Agent / 学习 Agent
```

网络检索必须在 `TaskRunner` 的受控阶段执行。Provider 只负责访问来源和返回
标准化候选，不负责生成最终答案。检索循环上限、抓取数量、超时和是否允许全文，
全部由 `ExternalRetrievalPolicy` 配置。

## 来源范围

| 范围 | 典型来源 | 默认用途 |
|---|---|---|
| `academic` | arXiv、Crossref、Semantic Scholar | 论文发现、DOI/作者/摘要元数据 |
| `web` | 配置的 Web Search Provider 与公开网页 | 新知识点、官方文档、最新资料 |
| `user` | 用户明确提供的 URL 或文件 | 用户指定来源核对 |

第一版只允许公开元数据、摘要和明确允许访问的局部内容。不能因为搜索结果
提供了 PDF 链接，就默认复制或解析整篇论文。

## 安全边界

### 网络请求

- Provider 必须复用统一 HTTP 客户端、超时、并发闸门、缓存和错误分类。
- 禁止在 Agent、YAML 或用户输入中直接拼接供应商密钥和请求头。
- URL 仅允许 `http`/`https`，禁止 URL 内嵌账号密码。
- Fetcher 必须阻断 localhost、私有网段、云元数据地址、非标准重定向和过大响应。
- 后续实现需要域名白名单、DNS 重绑定防护、最大响应体和最大重定向次数。
- 搜索、抓取、解析失败必须返回 `partial` 或 `failed`，不能伪造成空成功。

### 内容与 Prompt Injection

- 网页和论文内容一律视为不可信数据，不得改变系统指令、工具权限或路由。
- 网页正文不能直接作为工具调用参数或系统提示词。
- 外部内容进入模型前必须带来源边界、证据编号和“仅作资料”的标记。
- 外部来源不能覆盖用户题目中的数值、实验结果或电路连接事实。

### 证据与引用

- 检索命中不等于结论成立。
- 每条证据必须保留 `provider`、`canonical_url`、`retrieved_at` 和稳定 `source_ref`。
- 论文必须尽可能保留 DOI、arXiv ID、作者、venue 和发表时间。
- 后续 CitationValidator 需要区分“被检索”“支持结论”“冲突”和“无法判断”。
- 无法定位或无法访问原文时，回答必须明确标注限制。

## 阶段 1 的实施入口

阶段 1 先实现论文元数据检索，不修改通用 Web 页面抓取：

1. 定义 `AcademicSearchProvider` 接口和 Fake Provider。
2. 接入 arXiv、Crossref、Semantic Scholar 的只读搜索/详情适配器。
3. 增加 DOI、arXiv ID、规范 URL 和标题归一化去重。
4. 增加 Debug API、缓存和 Provider 状态，不自动注入学生端回答。
5. 通过检索、超时、限流、引用和敏感信息测试后，再接入研究 Agent。

## 非目标

- 本阶段不新增数据库表。
- 本阶段不恢复退役 Solver，也不改变本地 Runtime Provider。
- 本阶段不引入第二套 Agent Runtime。
- 本阶段不实现通用网页抓取、全文下载或自动知识库写入。
