# Agent Runtime 代码层完成审计（2026-08-10）

本审计以当前工作树、已提交的 Runtime 合同测试和受控本地证据为准。它回答
“代码是否已经具备真正 Agent Runtime 的必要机制”，不把结构测试、mock 或
自动化检查误写成模型质量或生产发布批准。

## 当前结论

代码层的 Agent Runtime 已具备目标、计划、受控节点执行、观察—决策—行动—
验证—重规划、耐久 checkpoint、人工控制、可观测事件与离线评测门禁。现有
业务路径可以增量接入该边界，且 Task 创建仍由后台 worker 异步执行。

这不等于“可设为默认”或“已通过生产发布”。当前状态是：**代码层已实现并
完成初步审计；发布保持 fail-closed**。

| 目标能力 | 当前状态 | 实现与可核验证据 | 尚未替代的证据 |
| --- | --- | --- | --- |
| 结构化目标与可执行计划 | 已实现 | `RuntimeGoal`、`RuntimeGoalPlanner`、`AgentRunPlan`；目标/准入/规划回归 23 项通过 | 真实业务语义是否满足 success criteria |
| 节点级工具和子 Agent | 已实现 | `RuntimeHandlerRegistry`、typed adapter、`RuntimeSubagentRegistry`；核心合同矩阵覆盖工具、子 Agent 与预算 | 外部工具在生产权限下的行为 |
| observe → decide → act → verify → replan | 已实现 | `RuntimeController`、`PlanExecutor`、版本化 replan 与 proposal；核心矩阵覆盖 fail-closed 分支 | Provider 输出质量与重规划效果 |
| durable checkpoint 与恢复 | 已实现 | `AgentRunRepository`、状态版本、sequence/event 关联、重放与并行恢复测试 | 生产 worker/数据库故障演练 |
| 暂停、恢复、审批、reconcile | 已实现并加固 | `TaskControlService` 与 Task API；审批与 handler scope 绑定且单次消费；47 项控制/恢复/任务回归通过 | 真实高风险工具的授权流程 |
| 可观测事件与调试投影 | 已实现 | checkpoint/SSE 事件桥、运行时耗时归因、计划顺序调试投影；UI/API 回归 9 项、通用目标 Task E2E 2 项通过 | 长时真实负载下的 SSE/浏览器行为 |
| 可复现评测与发布门禁 | 已实现，发布未满足 | collector、trace audit、semantic sidecar、preflight 均 fail-closed；受控开发目录已有授权配对和结构套件 | 独立语义评审与人工发布决定 |
| 业务路径增量迁移 | 已实现一批，持续扩展 | 通用问答、知识检索、Solver、教学、写作和外部检索均有 Runtime 适配/回归记录 | 每个待发布 Agent 的授权配对与语义证据 |
| 边界保护 | 已实现 | `SOLVER_CT v1.0` 未改；Task/Provider 分界不在路由同步调用 Provider；私有输入与原始 trace 不进入 Git | Docker、生产依赖与发布流程演练 |

## 已核对的受控运行证据

私有目录 `.local_outputs/runtime_authorized_dev_e2e_20260810/` 中存在四项
非星辰顶层 Agent 的 Legacy/Runtime 成对 Task、SSE 与 checkpoint 记录。离线
打包结果中，`GENERAL_QUESTION_V1`、`LEARN_01_LOCAL_RETRIEVAL_V1` 与
`RESEARCH_01_ACADEMIC_SEARCH_V1` 的结构门禁可通过；它们仍是
`needs_review`，没有 semantic sidecar 或发布决定。

`ACADEMIC_PROBLEM_SOLVER` 的初始配对及三轮重复样本显示明显时延波动；其中一
轮 Runtime 相对 Legacy 为 `+269.1%`。离线分析将其标记为
`requires_investigation=true`，因此该 Agent 继续保持 Legacy/fail-closed，不能
用中位数改善抵消单次回归。

上述原始输入、输出、checkpoint 与凭据均只留在 Git 忽略的受控目录。本审计
不复制这些材料，也不把它们作为公开仓库的发布证据。

## 本轮及关联验证

- 核心 Runtime 审计矩阵：142 项 provider-free 测试通过；不包括独立拥有的
  业务路径测试。
- 审批 scope、checkpoint/恢复、Generic Goal 与 Task 控制：47 项通过。
- 非 RESEARCH_03 的业务 Runtime 回归：教学/写作/外部检索 26 项、通用问答
  11 项、Solver 与知识问答 16 项通过。
- 调试投影/UI 9 项以及 Generic Goal Task API E2E 2 项通过。
- 对本轮修改均已执行 Ruff、目标 Mypy、配置检查、敏感文件检查和
  `git diff --check`。Docker 未运行；当前 shell 配置请求 mock Provider，未在
  本轮新增 Provider 调用。

Windows 上的若干聚合应用级测试因进程启动开销超过命令窗口被拆分执行；本文只
列出实际返回通过的子套件，不将超时算作通过。

## 发布前仍必须完成

1. 由独立评审人完成三个结构通过 Agent 的脱敏 semantic sidecar，并填写责任人、
   日期、风险和等价/可接受结论。
2. 由发布责任人作出可审计决定：继续 Legacy、有限 canary 或设为默认；代码和
   本审计不能代替该决定。
3. 定位并修复 Solver 的可复现性能回归后，用同一输入重新采集完整配对证据。
4. 在受控预发/生产等价环境执行数据库、Redis、MinIO、worker 重启和 Docker
   演练；保存回滚记录，且不得自动切换 default。

## 复核入口

- [初步审计与命令记录](runtime_initial_audit_2026-08-09.md)
- [授权配对采集与性能诊断记录](runtime_authorized_dev_e2e_2026-08-10.md)
- [证据 intake 合同](runtime_evidence_intake_contract.md)
- [授权采集与发布 runbook](runtime_authorized_paired_trace_release_runbook.md)
- [业务 Runtime 闭环证据](runtime_business_closure_evidence.md)
