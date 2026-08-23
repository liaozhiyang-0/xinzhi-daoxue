# Phase D4：Bounded Revision 集成

## 目标
Critic shadow 证明有价值后，引入最多一次受控 Revision。

## 前置条件
若 D3 显示 Critic 噪声过高或错误指控明显，先修正 Critic/Policy，不得直接开启 revision。

## 流程
```text
Draft
 ↓
Critic
 ↓
pass → Verification
revise → RevisionHandler(max 1) → Verification
fail / needs_review → Fail-closed / Approval / Existing Review Path
```

## 限制
1. 默认最多 1 次。
2. 只修改 Critic 明确指出的问题。
3. 不扩大任务范围。
4. 不新增无 evidence 支持的事实。
5. Tool 结果、引用 ID、deterministic observation 不得被模型擅改。
6. side-effect Tool 不因 revision 自动重跑。
7. 需要重跑 Tool/RAG 时必须走已有 Runtime action/policy。
8. Revision 后必须重新走 deterministic/domain verification。
9. Revision 失败不得覆盖已有 fail-closed 行为。

## Trace
记录 original result、critic、revision summary/diff、revision count、verification before/after、cost/latency。

## 提交
本阶段不 commit，完成后继续 D5。
