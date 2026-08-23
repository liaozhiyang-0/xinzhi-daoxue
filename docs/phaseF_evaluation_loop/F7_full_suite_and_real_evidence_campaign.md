# Phase F7：Full Suite 与真实 Evidence Campaign

## 目标
用代表性评测证明整个优化闭环可用，而不是只靠 contract tests。

## 第一优先级：336-case suite
至少输出：
- overall pass/score
- course breakdown
- task/problem type breakdown
- failure-stage breakdown
- route/planner failure
- skill/tool failure
- generation failure
- verification/reflection failure
- latency/cost
- top failure patterns

## 第二优先级：真实历史失败
至少选择：
- Phase B/C/D/E 中发现的真实问题
- 336-case 中高频失败
- 图片/复杂公式/专业求解失败
- Knowledge evidence failure
- Research evidence failure

## Evidence Levels
synthetic_provider_free / offline_real_case / real_provider_test / controlled_canary / production

## 至少验证一个完整闭环
```text
336-case failure
→ Failure Attribution
→ Pattern
→ Improvement Proposal
→ Offline Replay
→ score improvement
→ no critical regression
→ PromotionDecision
→ Experience candidate
```

不要求自动实施 Proposal。

若无法跑真实 Provider，只能给 `STRUCTURAL_GO / CONDITIONAL_GO`，不能宣称真实自我优化能力已完成。

Phase E 前已有的 6 个 full-suite failures 必须继续单独记录，除非 Phase F 明确修复并有证据。

## 本阶段不 commit
完成后继续 F8。
