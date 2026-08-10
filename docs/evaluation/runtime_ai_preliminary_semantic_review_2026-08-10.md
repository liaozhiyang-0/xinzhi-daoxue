# Runtime 语义初审记录（2026-08-10）

## 结论

本记录是基于已授权开发环境配对产物生成的模型初审，不能替代独立人工语义评审，也不是发布决定。三个案例均为 `needs_review`，因此不会解除任何 Runtime 发布门禁。

自 2026-08-10 起，Runtime 发布门禁不再允许仅凭结构性配对证据进入 `canary` 或 `default`：必须同时有覆盖全部案例、哈希绑定且结论为 `pass` 的语义 sidecar。模型初审中的 `needs_review` 会保持阻断；该规则已由 Task API 默认接管路径回归测试覆盖。

| Agent / case | 初审分数（完成度 / 事实 / 证据 / 安全） | 初审结论 | 原因 |
| --- | --- | --- | --- |
| `GENERAL_QUESTION_V1` / `general_stack_explanation` | 1.0 / 1.0 / N/A / 1.0 | `needs_review` | 两条路径均满足“两句话解释栈”的要求，定义正确；无外部证据要求。 |
| `LEARN_01_LOCAL_RETRIEVAL_V1` / `knowledge_capacitor_voltage` | 1.0 / 0.9 / 0.8 / 1.0 | `needs_review` | 两条路径都正确说明电压突变需要无界电流；引用为本地知识库定位，仍须人工抽查原文与表述边界。 |
| `RESEARCH_01_ACADEMIC_SEARCH_V1` / `research_reproducible_evals` | 0.7 / 0.5 / 0.4 / 1.0 | `needs_review` | Runtime 输出更贴近问题，但自身记录了论文审查超时和主题不匹配剔除；具体研究、日期和量化主张必须由人工逐条核验来源后才能采纳。 |

## 私有证据与边界

- 配对输出、输入哈希、Legacy/Runtime 输出哈希、checkpoint 路径在忽略目录 `.local_outputs/runtime_authorized_dev_e2e_20260810/semantic_review_packets/`。
- 初审 JSON 在同目录的 `semantic_review_ai_preliminary/`，字段遵循 `runtime_semantic_evidence.v1` 的输入格式，并显式标记 `judge_type: model`。
- 该目录不可提交；本文件不复述私有题目、输出、凭据、原始工作流或 checkpoint 内容。
- `ACADEMIC_PROBLEM_SOLVER` 未进入语义初审：其结构门禁因延迟回归未通过，且 `SOLVER_CT v1.0` 仍保持冻结。

## 仍待人工完成

1. 以私有评审包对照原始来源与 Runtime checkpoint，填写独立审核人的结论和时间。
2. 决定每个 Agent 继续灰度、设为默认或回滚；本次初审不作该决定。
3. 对学术检索案例重新执行有界的来源验证后，再考虑将其判为 `pass`。
