# 外部学术源登记与审查边界

## 已核对的官方入口

| Source | 用途 | 默认证据等级 | 运行边界 |
| --- | --- | --- | --- |
| arXiv API | 学术预印本元数据与检索 | 补充证据 | 商业使用前复核 API 条款；默认只保存标识、标题、作者、日期和短摘录 |
| Crossref REST API | DOI、出版物和工作元数据 | 补充证据 | 优先使用 DOI、标题、作者、期刊和日期；不把元数据等同于论文全文结论 |
| OpenAlex API | 学术作品、作者、机构和主题索引 | 补充证据 | 使用 API key、配额和来源时间戳；结果需要 DOI/作品标识回溯 |

官方文档：

- [arXiv API Access](https://info.arxiv.org/help/api/index.html)
- [Crossref REST API](https://api.crossref.org/swagger-ui/index.html)
- [OpenAlex Developers](https://developers.openalex.org/)

## 接入流程

外部结果进入产品前按以下顺序处理：

1. 记录 provider、source_ref、canonical_url、retrieved_at 和内容哈希。
2. 将来源归类为 `academic_paper`、`web_page` 或 `user_source`，不允许未知类型直接进入引用结果。
3. 根据场景 `evidence_policy` 检查权威/补充来源、发布时间窗口和合成材料许可。
4. 检查回答是否引用实际返回的 evidence_id；无引用时拒绝自动通过。
5. 场景要求人工复核时保留 `needs_manual_review`，不能仅因自动规则通过而标记为最终证据。

## 当前状态

本文件是来源治理和接入边界，不是已下载的数据集，也不代表真实检索效果。后续可以在授权和配额确认后接入少量元数据样本，再通过 `/api/v1/scenarios/{scenario_id}/evidence-review` 做自动审查；未经人工确认的网络或 AI 合成内容只能作为补充证据。
