# Phase P Final Report

## Release decision

**CONDITIONAL GO：可进入受控演示和团队交接；不宣称生产发布。**

Phase N 已将 active 控制权收敛到 Unified Ingress → GoalContract → Planner → CanonicalPlan → Runtime。Phase P 关闭了已确认的产品阻断问题，并完成六案例演示包；真实科研检索、教师发布审批、准生产并发和 Final Pilot 仍需要外部参与或专用环境。

## Completed

1. P0：冻结 Pilot 证据、任务索引和隐私口径。
2. P1：建立 Top 15 Failure Patterns，选择 5 项进入第一轮修复。
3. P2：修复 AC-01 图片导入边界、Runtime 业务适配误接管和场景输入模式校验。
4. P3：不新增 Agent；保留 Planner/Capability/Skill 作为唯一 active 计划面，质量门不降级。
5. P4：为 TP/FE/LP/RB/KG/AC 固定黄金、备用、边界和失败/降级演示输入。
6. P5：保留 React 单一工作台、单一 Markdown/KaTeX 渲染链和 31 条数学夹具。
7. P6：完成 provider-free Runtime/SSE/retry/resume/cancel 回归；准生产长时/并发/双 Worker 仍列为条件项。

## Six-case summary

| ID | 产品价值 | 关键能力 | 必须保留的边界 |
| --- | --- | --- | --- |
| TP-01 | 把课程目标组织成可执行教案 | Planner、课程证据、Teaching Skill | 教师确认，不自动发布 |
| FE-01 | 找到学生最早实质错误并给验证任务 | 首错定位、Verification、反馈 | 不自动总分 |
| LP-01 | 把学习状态变成阶段路径 | Learning State、Skill、Planner | 不宣称能力已掌握 |
| RB-01 | 在时间/主题范围内整理科研证据 | External Retrieval、Evidence Governance | 不虚构 DOI/定量结论 |
| KG-01 | 审查版本、来源、权限和发布 | Knowledge Governance、审批 | 不自动发布 |
| AC-01 | 对题图进行结构化诊断和求解 | Vision、Solver、Tool、Verification | 不编造图像事实，必要时拒答 |

## Known limitations

- Pilot 0 历史记录并不等同于 5–10 人、50–100 次的 Final Pilot；P7 仍需真实测试者参与。
- 真实模型生成成功不等于证据充分或可发布；多个记录保持 `completed_with_gaps/publishable=false`。
- Edge 文件选择器权限、真实外部科研检索、双 Worker、长时并发、成本和完整重连仍需准生产验收。
- 课程资料覆盖不足时，系统会保留待复核状态；不得通过增加模型费用绕过证据门。

## Required final gate

在 commit/push 前必须重新执行：frontend checks、Ruff、Mypy、backend full suite、`git diff --check`、sensitive/config checks；push 后必须取得 GitHub Actions PASS 和 remote SHA 一致性。未满足时保持本报告的 CONDITIONAL GO，不升级为 production GO。
