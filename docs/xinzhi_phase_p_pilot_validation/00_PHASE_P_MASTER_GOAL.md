# 芯智导学 Phase P：Pilot Validation & Product Hardening

## 阶段定位
Phase N 完成后，不再新增 Planner、Runtime、Agent、Memory 等架构层。

先进行一次组员真实使用测试（Pilot 0），再进入 Phase P。

Phase P 的目标：
> 用真实用户行为、真实任务与真实失败证据，把“架构完成的系统”收敛成“可演示、可测试、可交付的完成品”。

## 总流程
```text
Phase N 完成
→ Release Candidate Snapshot
→ Pilot 0：组员真实测试
→ 冻结 Task / Trace / Feedback / Failure
→ P0 证据冻结
→ P1 失败归因
→ P2 Critical Bug 修复
→ P3 Agent Quality 定向优化
→ P4 六案例产品化
→ P5 UX / 中文 / LaTeX 收口
→ P6 稳定性 / 性能 / 成本
→ P7 Final Pilot / Acceptance
→ P8 Release / Team Handoff
```

## 三类问题
### 产品阻断
Task 卡死、SSE 断流、附件失败、公式崩溃、review/resume 失效等。

### Agent 质量
Planner、Capability、Skill、RAG、Tool、Vision、Verification、Reflection、Experience 等。

### 体验与演示
输出太长、重点不突出、中文混杂、操作不清楚、六案例视觉不统一。

## 最终完成标准
- Architecture stable
- Real-user validated
- Critical bugs closed
- Six Demo stable
- Chinese UI stable
- LaTeX stable
- Real image flow stable
- Runtime recoverable
- Benchmark reproducible
- Known limitations documented
- Team handoff ready
