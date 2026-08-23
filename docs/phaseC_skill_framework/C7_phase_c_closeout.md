# Phase C7：Phase C Closeout

## 前置条件
C0-C6 均完成且所有 commit 已 push。

## 必须完成
1. 生成最终 Skill Framework 架构图。
2. 更新 KEEP/MERGE/FREEZE/REMOVE。
3. 检查是否出现第二 SkillRegistry、第二 Runtime、新 public Agent、Worker 升级为 Agent。
4. 旧 skill mapping 能适配则 adapter；只有无调用证据充分时才删除。
5. 保留 Planner rollback 和 Overall Router compatibility。
6. 生成 `docs/audits/skill_framework_phase_c_closeout.md`。
7. 更新项目架构文档。
8. 完整 regression。

## GitHub 结束要求
最终 commit：
`feat(agent): complete phase C skill framework`

push 到 Phase C 分支，验证远端 SHA。

如 gh CLI 可用且已认证：
- 创建或更新 Phase C PR 到 main；
- 不自动 merge，除非用户明确授权。

记录 branch、final SHA、remote SHA、PR URL（如有）、test summary。

## 最终验收
- authoritative SkillRegistry 唯一；
- SkillRetriever + SkillPolicy 可用；
- Planner 只能选 registered skill；
- Skill 写入 CanonicalPlan/trace；
- Runtime 使用现有 Handler/Tool/Worker；
- 有合理的跨入口复用；
- CT pilot skill 可审计；
- rollback/resume 可用；
- 每个子阶段已 push GitHub；
- Phase D 尚未开始。

## 结束
Phase C completed. Skill Framework integrated. No new public Agent. Runtime Kernel unchanged. All Phase C commits pushed. Phase D not started.
