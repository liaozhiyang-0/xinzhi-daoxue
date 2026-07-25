# 本地知识库审计报告

生成时间：2026-07-24T15:46:51.806422+00:00

## 1. 总体概况

| 课程 | 实际相对路径 | 文件数 | 文字文件 | 图片 | 其他 |
|---|---|---:|---:|---:|---:|
| CT 电路理论 | `电路理论` | 1099 | 16 | 1053 | 30 |
| AE 模拟电子技术 | `模电` | 625 | 11 | 603 | 11 |
| DE 数字电子技术 | `数电` | 575 | 12 | 551 | 12 |
| SS 信号与系统 | `信号与系统版本一` | 459 | 2 | 457 | 0 |
| DSP 数字信号处理 | `数字信号处理` | 279 | 1 | 278 | 0 |
| COMM 通信原理 | `通信原理` | 381 | 14 | 367 | 0 |

总计 3418 个文件、56 个文字文件、3309 张图片、53 个其他文件，总大小约 342.54 MiB。

总体判断：Markdown 正文可直接进入只读索引；图片数量远高于文本，首版适合上下文图片检索；PDF、DOCX 和压缩包只登记元数据，暂不直接解析。

## 2. 分课程统计

| 课程 | 主要层级 | 类型分布 | 图片 | 直接索引 | 清洗/复核 | 暂不可用 |
|---|---|---|---:|---:|---:|---:|
| CT | 课本 | .jpg 1053、.md 16、.pdf 15、.zip 15 | 1053 | 15 (1.4%) | 1 (0.1%) | 30 (2.7%) |
| AE | 教材 / pdf | .jpg 603、.md 11、.pdf 11 | 603 | 11 (1.8%) | 0 (0.0%) | 11 (1.8%) |
| DE | 教材 / pdf | .jpg 551、.md 12、.pdf 12 | 551 | 12 (2.1%) | 0 (0.0%) | 12 (2.1%) |
| SS | images / 信号与线性系统-上.md / 信号与线性系统-下.md | .jpg 457、.md 2 | 457 | 2 (0.4%) | 0 (0.0%) | 0 (0.0%) |
| DSP | images / 数字信号处理.md | .jpg 278、.md 1 | 278 | 1 (0.4%) | 0 (0.0%) | 0 (0.0%) |
| COMM | images / 101_通信原理_通信原理（第7版）-Principles-of-Co_-Z-Library.md / 145_通信原理_通信原理（第7版）-Principles-of-Co_-Z-Library.md / 16_通信原理_通信原理（第7版）-Principles-of-Co_-Z-Library.md / 191_通信原理_通信原理（第7版）-Principles-of-Co_-Z-Library.md / 243_通信原理_通信原理（第7版）-Principles-of-Co_-Z-Library.md / 265_通信原理_通信原理（第7版）-Principles-of-Co_-Z-Library.md / 294_通信原理_通信原理（第7版）-Principles-of-Co_-Z-Library.md / 32_通信原理_通信原理（第7版）-Principles-of-Co_-Z-Library.md / 346_通信原理_通信原理（第7版）-Principles-of-Co_-Z-Library.md | .jpg 367、.md 14 | 367 | 14 (3.7%) | 0 (0.0%) | 0 (0.0%) |

章节文件覆盖需按各课程教材目录人工核对；部分课程按章拆分 Markdown，部分课程为上下册或整册 Markdown，不能仅凭文件名断言章节完整。

## 3. 结构质量

- 各课程均保留教材式 Markdown，可按标题和段落切块。
- 图片主要集中于课程 `images/` 目录，个别课程另有无编号图片和映射表。
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

共发现 150 个问题：blocker 0、high 0、medium 135、low 15。完整机器清单位于 `knowledge_indexes/knowledge_base_quality_issues.json`。

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
| medium | COMM | `images/30_564_1979_257_143_0.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | COMM | `images/30_569_1779_243_135_0.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | COMM | `images/30_586_1568_215_134_0.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | COMM | `images/30_969_1547_244_183_0.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | COMM | `images/30_972_1957_234_192_0.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | COMM | `images/30_974_1756_232_179_0.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | COMM | `images/31_537_724_259_144_0.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | COMM | `images/31_543_535_250_145_0.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | COMM | `images/31_550_345_235_142_0.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | COMM | `images/31_892_330_227_170_0.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | COMM | `images/31_942_713_231_171_0.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | COMM | `images/31_951_528_231_160_0.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
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
| medium | SS | `images/135_1167_253_236_371_-1.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | SS | `images/135_1170_1128_217_343_-1.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | SS | `images/135_168_278_181_341_-1.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | SS | `images/135_189_1181_182_230_-1.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | SS | `images/135_452_1177_220_290_-1.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | SS | `images/135_455_241_244_406_-1.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | SS | `images/135_787_210_302_422_-1.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | SS | `images/135_790_1116_282_338_-1.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | SS | `images/136_1259_1146_223_386_-1.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |
| medium | SS | `images/136_1275_219_219_506_-1.jpg` | orphan_image | 是 | 保留原图并进入人工关联队列 |

## 6. 接入建议

- 可直接索引：UTF-8 Markdown/TXT 且无严重警告的正文。
- 清洗后索引：缺少标题、过短、疑似 OCR 异常或草稿内容。
- 仅作为图片附件：可读取且能追溯相对路径的图片。
- 暂不索引：PDF、DOCX、ZIP 和无法 UTF-8 解码的文件。
- 人工复核：孤立图片、失效链接、乱码、同名冲突、重复文件和来源不明内容。

本审计只确认上下文图片关联输入已就绪；真实文本/视觉向量是否可用，以 RAG build 输出和运行时 health 为准。

## 7. 现有系统与接入现状

- 审计与基础检索能力：本地 Markdown 只读扫描、`local_lexical_v2` 词项检索、课程范围过滤与 `kb://` 引用。
- RAG 能力：在既有检索服务内使用可替换文本/图片向量适配器、Qdrant、混合排序、上下文图片关联，以及独立生成的 Manifest、图片证据索引和增量缓存；实际就绪状态以运行时 health 为准。
- LEARN：本地问答链路已经实际调用知识库并返回来源；云端 LEARN 通过既有 `RetrievalContextPacket` 转成 `retrieved_context` 文本，再进入原有 Provider 请求，未增加未经确认的云端节点或 HTTP 字段。
- SOLVER：仅复用既有任务路由和只读检索入口，限制为方法、公式、概念和常见错误；云端工作流与 Provider 参数保持冻结。
- 配置与存储：路径和权重由 `.env`/Settings 管理，课程元数据继续使用 YAML；业务状态仍使用 SQLAlchemy（SQLite/PostgreSQL），既有 Redis/MinIO 配置未改变。索引产物为本地 JSON/JSONL，不需要数据库迁移。

重点数据质量队列：失效图片链接 0 个，孤立图片 77 个，精确重复问题记录 0 条，近似重复问题记录 0 条。

## 8. 2026-07-25 运行时验收

- Qdrant 运行时 health 为 `ready`，服务端集合包含 27101 条文本向量和
  3309 条图片向量；SS、DSP、COMM 分别包含 6243、4134、3964 条文本向量，
  以及 457、278、367 条图片向量。
- 三门课的真实混合检索均只返回本课程证据：SS 命中卷积章节，DSP 命中基 2
  FFT 章节，COMM 命中正交振幅调制章节。
- RAG Debug 的真实星辰请求已验证 `retrieved_context` 与本地
  `RetrievalContextPacket` 生成的文本逐字一致，长度分别为 1519、1404、
  2061 字符，说明本地检索证据确实进入了既有 Provider 请求。
- 当前云端 `LEARN_01_KNOWLEDGE_QA_V1` 工作流仍声明只支持 CT、AE、DE；
  DSP 和 COMM 会返回 `status=failed`，SS 同样未得到可接受回答。任务链会按
  既有策略回退到本地证据回答，因此本地 RAG 接入验收通过，但三门新课的
  云端答案质量状态为 `BLOCKED_BY_CLOUD_FLOW`，不能把 Provider 调用完成视为
  云端答案验收通过。
- 正式 `POST /api/v1/tasks` 探针已确认 SS 任务非阻塞完成，路由先选择云端
  LEARN，检索策略为 `learn_knowledge_qa`、模式为 `grounded_generation`，
  三条最终证据和三条引用均来自 `kb://SS/`；云端失败后明确标记
  `cloud_failed_status` 并回退到本地结果。
