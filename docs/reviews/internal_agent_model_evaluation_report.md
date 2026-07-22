# 内部模型 Agent 首轮评测报告

评测日期：2026-07-21（Asia/Shanghai）

## 范围与边界

本轮在不改变七个既有顶层工作流和 `POST /api/v1/tasks` 的前提下，验证 9 个 `subordinate_only` 内部 Agent。文本案例按 Agent 分阶段执行，失败后先修改 Schema 或提示约束，再只复测受影响案例，以减少重复 Token。视觉案例使用仓库内 313×239、5102 字节的电路图，关闭高分辨率和自动重试。

评测只检查结构合同、路由和明确的业务边界，不把 Provider 成功、HTTP 200 或 Schema 通过描述为答案正确率。

## 最终通过结果

下表为每个文本 case 最后一次通过调用，不包含此前诊断调用：

| Case | 内部 Agent | 模型链 | Token |
|---|---|---|---:|
| `course_ct_capacitor` | 课程分类 | qwen3.5-flash | 308 |
| `course_ae_opamp` | 课程分类 | qwen3.5-flash | 263 |
| `course_de_flipflop` | 课程分类 | qwen3.5-flash | 207 |
| `intent_solver` | 意图分类 | qwen3.5-flash | 224 |
| `intent_lesson_prep` | 意图分类 | qwen3.5-flash | 225 |
| `rewrite_preserves_constraints` | 查询改写 | qwen3.5-flash | 255 |
| `circuit_plan_requires_tools` | 电路规划 | spark-x → qwen3.5-flash | 1184 |
| `lesson_prep_structure` | 备课草稿 | spark-x → qwen3.5-flash | 884 |
| `assignment_review_boundary` | 作业初审 | spark-x → qwen3.5-flash | 1062 |
| `academic_writing_no_fabrication` | 学术写作 | spark-x → qwen3.5-flash | 394 |
| `data_analysis_without_data` | 数据分析 | spark-x → qwen3.5-flash | 947 |

11 个文本案例最终均通过，最后一次通过调用合计 5953 Token。

视觉 Agent 在收紧元件 Schema 后通过：`qwen3.7-plus`，输入 462、输出 269、合计 731 Token，耗时 9638 ms；返回 `recognized_text`、`diagram_description`、`components`、`uncertain_info`、`confidence` 五个字段，结构中包含 3 个元件。首次 256 输出上限的视觉诊断调用在上限处截断并消耗 546 Token，随后将元件对象改为有限字段并以 384 上限复测。

因此，可复现的“每个 case 最后一次通过”文本加视觉调用合计 6684 Token。这不是本轮开发的账单总量：提示词调优、失败诊断和早期未完整记录 usage 的调用消耗未计入，不能据此推断账户实际费用。

## 工程验证

- `scripts/evaluate_model_agents.py --dry-run`：11 个文本案例、8 个文本 Agent，注册表无错误，不发送 API 请求。
- 内部 Agent 专项：17 passed；视觉 Schema 修改后相关测试 7 passed。
- 全仓 Pytest：295 passed、15 skipped；跳过项需要显式真实 API 或外部环境。
- Ruff：通过。
- Mypy：125 个源文件无问题。
- 敏感文件扫描：通过。
- Docker Compose 配置解析：通过。
- OpenAPI 导出与安全测试：2 passed。

本地脱敏运行报告位于 Git 忽略目录 `local_storage/evaluations/`。报告只保留 case、状态、模型、耗时、Token、请求 ID 和输出字段名，不保存完整输入、输出、图片 Base64 或 API Key。

## 已发现并修正的问题

1. Spark 直接生成严格 JSON 容易截断或缺字段。当前改为 Spark 生成业务草稿、Qwen3.5 负责结构归一，并合并两个阶段的 Token 与耗时。
2. CT/AE/DE 边界提示最初不足，已明确基础元件/KCL/KVL、模拟器件和数字逻辑的优先映射。
3. 结构校验错误原先可能触发无效回退。现在结构错误不重试、不回退；只有网络、限流和服务暂时不可用等 Provider 故障才回退。
4. 视觉元件最初使用无约束字典，256 Token 下输出截断。现在使用固定字段、短描述和长度约束。

## 集成进展与下一阶段

四个已通过专项评测的业务 Agent（备课、作业初审、学术写作、数据分析）已通过适配器接入既有 TaskRunner；没有新建顶层路由、任务队列或 SSE 协议。备课复用真实检索包作为生成上下文，作业初审保持 reference-only 边界，学术写作和数据分析默认不伪造 RAG 证据。学生 Workspace 已切换为能力卡片和自动路由，不再暴露星辰工作流实现细节。

下一步可把课程/意图分类和查询改写逐步放入 Supervisor 的可观测节点，并针对每次接入保留非阻塞创建、SSE 顺序、真实检索证据和 Token 上限测试。`SOLVER_CT_V1` 冻结基线仍不直接修改。
