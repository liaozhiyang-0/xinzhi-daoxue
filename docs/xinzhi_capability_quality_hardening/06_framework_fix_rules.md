# 06 框架级修复规则

## 最高原则

任何失败先判断：

单场景问题，还是共享框架问题。

如果同类问题可能影响多个 Agent，必须修共享层。

## 禁止

禁止针对具体 Agent 写特殊分支，如果真实问题来自 capability contract。

禁止针对图片数量写分支，如果真实问题来自多图编排。

禁止针对 benchmark 题目 hardcode。

禁止通过在 prompt 里塞完整历史掩盖 Context/Memory 问题。

禁止把 data_analysis 的 409 简单改成固定 200 文本。

## 修改前影响分析

必须列：

- Affected agents
- Affected scenarios
- Affected APIs
- Affected runtime
- Affected provider
- Affected state
- Regression risk

## 推荐修复层

Multimodal：
manifest / provider capability / orchestrator / coverage validation

Memory：
ContextAssembly / WorkingState / Correction priority / Compaction

Router：
follow-up continuity / task-switch detection

General：
fallback policy / legacy intent alias

Validation：
shared semantic checks

## 修改后回归

Target tests
+ Contract tests
+ Six-scenario smoke
+ Affected capability E2E

## 输出

`docs/audit/34_capability_quality_fix_report.md`
