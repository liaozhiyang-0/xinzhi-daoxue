# 本地知识库审计报告

生成时间：2026-07-17T13:41:28.428976+00:00

## 1. 总体概况

| 课程 | 实际相对路径 | 文件数 | 文字文件 | 图片 | 其他 |
|---|---|---:|---:|---:|---:|
| CT 电路理论 | `电路理论` | 1099 | 16 | 1053 | 30 |
| AE 模拟电子技术 | `模电` | 625 | 11 | 603 | 11 |
| DE 数字电子技术 | `数电` | 575 | 12 | 551 | 12 |

总计 2299 个文件、39 个文字文件、2207 张图片、53 个其他文件，总大小约 307.72 MiB。

总体判断：Markdown 正文可直接进入只读索引；图片数量远高于文本，首版适合上下文图片检索；PDF、DOCX 和压缩包只登记元数据，暂不直接解析。

## 2. 分课程统计

| 课程 | 主要层级 | 类型分布 | 图片 | 直接索引 | 清洗/复核 | 暂不可用 |
|---|---|---|---:|---:|---:|---:|
| CT | 课本 | .jpg 1053、.md 16、.pdf 15、.zip 15 | 1053 | 15 (1.4%) | 1 (0.1%) | 30 (2.7%) |
| AE | 教材 / pdf | .jpg 603、.md 11、.pdf 11 | 603 | 11 (1.8%) | 0 (0.0%) | 11 (1.8%) |
| DE | 教材 / pdf | .jpg 551、.md 12、.pdf 12 | 551 | 12 (2.1%) | 0 (0.0%) | 12 (2.1%) |

章节文件覆盖：CT 发现第一至第十三章及附录；AE 发现第一至第十一章；DE 发现第一至第十一章和目录。未发现按章文件的明显编号缺口，但章节内容完整性仍需按教材目录人工核对。

## 3. 结构质量

- 三门课程均保留教材式章节 Markdown，适合按标题和段落切块。
- AE、DE 图片集中于教材 `images/`；CT 另有无编号图片和映射表。
- Markdown 中存在大量相对图片链接，可建立父文档和章节关系。
- 未被 Markdown 引用的图片保留为孤立证据并进入人工关联队列。
- PDF 与 ZIP 和已有 Markdown 并存，存在重复来源和索引重复风险。

## 4. 内容质量

| 维度 | 评价 | 理由 | 代表性文件 |
|---|---|---|---|
| 完整性 | medium | 章节较完整，二进制原件未解析 | `CT/课本/基础篇/3-重置md/第一章.md` |
| 准确性风险 | medium | OCR 标题异常，内容待复核 | `AE/教材/1-第一章.md` |
| 章节覆盖度 | high | 发现连续章节文件 | `DE/教材/数电_第一章.md` |
| 来源可追溯性 | medium | 缺少教材版次等统一元数据 | `knowledge_config/courses/*.yaml` |
| 公式可读性 | medium | 保留 LaTeX，转换质量需复核 | `CT/课本/基础篇/3-重置md/第三章.md` |
| 图片可理解性 | medium | 多数可由相邻文本关联，孤立图待处理 | `AE/教材/images/` |
| 检索友好度 | medium | 标题段落可检索，长章需切块 | `DE/教材/数电_第四章.md` |
| 重复度 | medium | PDF、ZIP、Markdown 与图片并存 | `CT/课本/基础篇/` |
| 噪声程度 | medium | 目录、无编号图片和异常标题带来噪声 | `CT/课本/基础篇/3-重置md/目录.md` |
| 知识问答适用度 | medium | 正文充足，引用和清洗需加强 | `AE/教材/模电_第八章.md` |
| 解题方法检索适用度 | medium | 方法较多，须防止样题参数污染 | `CT/课本/基础篇/3-重置md/第五章.md` |

## 5. 问题清单

共发现 73 个问题：blocker 0、high 0、medium 58、low 15。完整机器清单位于 `knowledge_indexes/knowledge_base_quality_issues.json`。

| 严重级别 | 课程 | 文件 | 类型 | 是否影响索引 | 建议 |
|---|---|---|---|---|---|
| medium | AE | `pdf/1-第一章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | AE | `pdf/2-第二章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | AE | `pdf/3-第三章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | AE | `pdf/4-第四章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | AE | `pdf/5-第五章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | AE | `pdf/6-第六章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | AE | `pdf/模电_第七章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | AE | `pdf/模电_第九章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | AE | `pdf/模电_第八章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | AE | `pdf/模电_第十一章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | AE | `pdf/模电_第十章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | AE | `教材/images/模电_第十一章_图11.1.1_变压器二次侧有中心抽头的全波整流电路_副本35.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十一章_图11.2.1_串联反馈式稳压电路一般结构图_副本11.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十一章_图11.2.6_具有跟踪特性的正负电压输出的稳压电路_副本42.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十一章_图11.2.8_可调恒流源电路_副本44.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十一章_图11.3.1_串联型DCDC变换电路主回路原理图_副本20.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十一章_图11.3.1_开关式稳压电路_副本46.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十一章_图11.3.5_串联型开关稳压电路DCDC变换电路原理图_副本24.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十章_图10.1.3_相同样阶数的三类低通滤波器幅频响应比较图_副本1.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十章_图10.2.1_一阶低通滤波电路_副本7.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十章_图10.2.3_一阶高通滤波器电路_副本8.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十章_图10.3.10_压控电压源型二阶带通滤波电路_副本2.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十章_图10.3.5_滤波电路_副本10.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十章_图10.7.4_RC文氏电桥振荡电路_副本11.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十章_图10.7.8_石英晶体的电路模型与电抗特性_副本3.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十章_图10.8.10_电路_副本14.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十章_图10.8.13_锯齿波电压产生电路_副本6.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十章_图10.8.1_同相输入单门限电压比较器_副本4.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十章_图10.8.3_比较电路_副本12.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | AE | `教材/images/模电_第十章_图10.8.5_电压器比较器电路_副本13.jpg` | possible_temporary_or_draft | 是 | 进入人工复核队列 |
| medium | CT | `课本/基础篇/1-原始pdf/目录.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | CT | `课本/基础篇/1-原始pdf/第一章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | CT | `课本/基础篇/1-原始pdf/第七章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | CT | `课本/基础篇/1-原始pdf/第三章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | CT | `课本/基础篇/1-原始pdf/第九章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | CT | `课本/基础篇/1-原始pdf/第二章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | CT | `课本/基础篇/1-原始pdf/第五章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | CT | `课本/基础篇/1-原始pdf/第八章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | CT | `课本/基础篇/1-原始pdf/第六章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | CT | `课本/基础篇/1-原始pdf/第十一章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | CT | `课本/基础篇/1-原始pdf/第十三章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | CT | `课本/基础篇/1-原始pdf/第十二章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | CT | `课本/基础篇/1-原始pdf/第十章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | CT | `课本/基础篇/1-原始pdf/第四章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | CT | `课本/基础篇/1-原始pdf/附录.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | CT | `课本/基础篇/3-重置md/无编号图片/映射表.md` | missing_markdown_heading | 否 | 在索引元数据覆盖层补充标题 |
| medium | DE | `pdf/数电_目录.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | DE | `pdf/数电_第一章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | DE | `pdf/数电_第七章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | DE | `pdf/数电_第三章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | DE | `pdf/数电_第九章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | DE | `pdf/数电_第二章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | DE | `pdf/数电_第五章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | DE | `pdf/数电_第八章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | DE | `pdf/数电_第六章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | DE | `pdf/数电_第十一章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | DE | `pdf/数电_第十章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| medium | DE | `pdf/数电_第四章.pdf` | binary_document_not_parsed | 是 | 优先使用已有提取文本，后续增加可替换解析器 |
| low | CT | `课本/基础篇/2-原始md压缩包/11_电路理论_电路理论-基础篇_14320476-20260713234546.zip` | archive_not_parsed | 否 | 确认内容已存在于当前只读目录后排除压缩包 |
| low | CT | `课本/基础篇/2-原始md压缩包/134_电路理论_电路理论-基础篇_14320476-20260713235122.zip` | archive_not_parsed | 否 | 确认内容已存在于当前只读目录后排除压缩包 |
| low | CT | `课本/基础篇/2-原始md压缩包/183_电路理论_电路理论-基础篇_14320476-20260713234610.zip` | archive_not_parsed | 否 | 确认内容已存在于当前只读目录后排除压缩包 |
| low | CT | `课本/基础篇/2-原始md压缩包/1_电路理论_电路理论-基础篇_14320476-20260713233854.zip` | archive_not_parsed | 否 | 确认内容已存在于当前只读目录后排除压缩包 |
| low | CT | `课本/基础篇/2-原始md压缩包/210_电路理论_电路理论-基础篇_14320476-20260713235130.zip` | archive_not_parsed | 否 | 确认内容已存在于当前只读目录后排除压缩包 |
| low | CT | `课本/基础篇/2-原始md压缩包/231_电路理论_电路理论-基础篇_14320476-20260713235144.zip` | archive_not_parsed | 否 | 确认内容已存在于当前只读目录后排除压缩包 |
| low | CT | `课本/基础篇/2-原始md压缩包/289_电路理论_电路理论-基础篇_14320476-20260713235151.zip` | archive_not_parsed | 否 | 确认内容已存在于当前只读目录后排除压缩包 |
| low | CT | `课本/基础篇/2-原始md压缩包/355_电路理论_电路理论-基础篇_14320476-20260713234104.zip` | archive_not_parsed | 否 | 确认内容已存在于当前只读目录后排除压缩包 |
| low | CT | `课本/基础篇/2-原始md压缩包/393_电路理论_电路理论-基础篇_14320476-20260713235827.zip` | archive_not_parsed | 否 | 确认内容已存在于当前只读目录后排除压缩包 |
| low | CT | `课本/基础篇/2-原始md压缩包/457_电路理论_电路理论-基础篇_14320476-20260713235643.zip` | archive_not_parsed | 否 | 确认内容已存在于当前只读目录后排除压缩包 |
| low | CT | `课本/基础篇/2-原始md压缩包/486_电路理论_电路理论-基础篇_14320476-20260714000301.zip` | archive_not_parsed | 否 | 确认内容已存在于当前只读目录后排除压缩包 |
| low | CT | `课本/基础篇/2-原始md压缩包/525_电路理论_电路理论-基础篇_14320476-20260713235756.zip` | archive_not_parsed | 否 | 确认内容已存在于当前只读目录后排除压缩包 |
| low | CT | `课本/基础篇/2-原始md压缩包/56_电路理论_电路理论-基础篇_14320476-20260713234557.zip` | archive_not_parsed | 否 | 确认内容已存在于当前只读目录后排除压缩包 |
| low | CT | `课本/基础篇/2-原始md压缩包/571_电路理论_电路理论-基础篇_14320476-20260713235515.zip` | archive_not_parsed | 否 | 确认内容已存在于当前只读目录后排除压缩包 |
| low | CT | `课本/基础篇/2-原始md压缩包/96_电路理论_电路理论-基础篇_14320476-20260713234618.zip` | archive_not_parsed | 否 | 确认内容已存在于当前只读目录后排除压缩包 |

## 6. 接入建议

- 可直接索引：UTF-8 Markdown/TXT 且无严重警告的正文。
- 清洗后索引：缺少标题、过短、疑似 OCR 异常或草稿内容。
- 仅作为图片附件：可读取且能追溯相对路径的图片。
- 暂不索引：PDF、DOCX、ZIP 和无法 UTF-8 解码的文件。
- 人工复核：孤立图片、失效链接、乱码、同名冲突、重复文件和来源不明内容。

当前 `multimodal_level = contextual_image_retrieval`，没有实现真正的视觉向量检索。

## 7. 现有系统与接入现状

- 实施前已有能力：本地 Markdown 只读扫描、`local_lexical_v2` BM25-like 词项检索、课程范围过滤与 `kb://` 引用；没有向量数据库、神经网络 Embedding、图像向量或独立 RAG 框架。
- 当前首版能力：在既有检索服务内增加可替换文本向量适配器、关键词与本地哈希向量混合排序、上下文图片关联，以及独立生成的 Manifest、图片证据索引和增量缓存。
- LEARN：本地问答链路已经实际调用知识库并返回来源；云端 LEARN 通过既有 `RetrievalContextPacket` 转成 `retrieved_context` 文本，再进入原有 Provider 请求，未增加未经确认的云端节点或 HTTP 字段。
- SOLVER：仅复用既有任务路由和只读检索入口，限制为方法、公式、概念和常见错误；云端工作流与 Provider 参数保持冻结。
- 配置与存储：路径和权重由 `.env`/Settings 管理，课程元数据继续使用 YAML；业务状态仍使用 SQLAlchemy（SQLite/PostgreSQL），既有 Redis/MinIO 配置未改变。索引产物为本地 JSON/JSONL，不需要数据库迁移。

重点数据质量队列：失效图片链接 0 个，孤立图片 0 个，精确重复问题记录 0 条，近似重复问题记录 0 条。
