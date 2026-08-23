# 芯智导学 Phase C 总目标：Skill Framework

## 阶段定位
Phase B 已完成 Planner / Canonical Plan 的控制面建设。Phase C 的唯一主目标是：将分散在课程配置、内部 Worker、Tool、RAG 和业务 Runtime 中的“专业做事方法”收敛为可注册、可检索、可选择、可绑定 Runtime、可评测、可追踪的 Skill Framework。

目标架构：
```text
User Goal
↓
PlannerService
↓
SkillRetriever
↓
SkillPolicy / Registry Validation
↓
Canonical Plan
↓
Runtime Skill Binding
↓
Existing Tool / Worker / RAG / Capability
↓
Runtime Kernel
```


## Phase B 进入 Phase C 前必须保留的观察项
- B4 只有 5 个 `synthetic_provider_free` 用例，1.0 parity 只能证明结构兼容，不能证明 Planner/Skill 的真实智能质量。
- Planner takeover 仍是 default OFF / allowlist gated，因此 Phase C 不得把“Planner 已全量成为生产控制中心”当作既成事实。
- Phase B parity 中 Academic Solver、Knowledge、Teaching 多数 `selected_skills` 仍为空，Phase C 应把“为什么为空、何时必须有 Skill、何时允许无 Skill”做成明确 policy。
- Teaching parity 样例中候选列表的 `available=false` 与最终 RouteDecision availability 为可用存在表面不一致，应在 C1 审计候选可用性语义，避免 Skill policy 继承错误状态。
- General fallback 样例在“跨课程且信息不足”时落到 `course_id=CT`，需要在 C1/C4 检查这是有意的默认上下文还是潜在课程污染，防止错误约束 SkillRetriever。

## 非协商原则
1. 不创建第二套 SkillRegistry，优先扩展仓库已有 Skill registry/config。
2. 不新增 public Agent。
3. Classifier、Rewriter、Extractor、Planner Worker、Reviewer 保持 Internal Worker。
4. Skill 不是 Agent，不拥有独立 Task lifecycle，不创建第二 Runtime。
5. Skill 只能绑定已有 Runtime Handler / Tool / Worker / RAG / Capability。
6. Planner 只能选择 Registry 中已注册且通过 SkillPolicy 的 Skill。
7. 未注册、版本不兼容、前置条件不满足、风险超限必须 fail-closed。
8. selected skill 必须进入 Canonical Plan、trace、event/evaluation。
9. Phase C 不实现 SkillMemory，不实现 Reflection。
10. Planner takeover 仍保持 feature flag / allowlist / rollback，不因 Phase C 自动扩大。
11. 每个子阶段完成后必须 commit + push 到 GitHub。
12. 每个子阶段完成后立即停止，不自动进入下一阶段。

## GitHub 固定门禁
每个子阶段完成前执行：
```text
git status
git diff --check
targeted tests
pytest / contract tests as required
git add <仅本阶段相关文件>
git commit -m "<phase commit message>"
git push origin <current-branch>
git rev-parse HEAD
git ls-remote origin <current-branch>
```
要求本地 HEAD 可在远端解析到。禁止 force push、git reset --hard、git clean -fd，不得混入 unrelated user changes。

建议分支：
```text
agentic/phase-c-skill-framework
```

## 执行顺序
1. C0_repository_sync_and_phase_b_checkpoint.md
2. C1_existing_skill_audit_and_contract.md
3. C2_skill_registry_consolidation.md
4. C3_skill_retriever_and_policy.md
5. C4_planner_skill_shadow_integration.md
6. C5_runtime_skill_binding.md
7. C6_skill_evaluation_and_controlled_canary.md
8. C7_phase_c_closeout.md

## Phase C 总退出条件
- Phase B 已 push 到 GitHub；
- authoritative SkillRegistry 唯一；
- Skill contract 版本化；
- SkillRetriever 可输出 bounded top-k；
- SkillPolicy 可拒绝非法 skill；
- Planner 不能生成不存在的 Skill；
- selected skill 写入 Canonical Plan 与 trace；
- Runtime 通过 adapter 绑定已有 Handler/Tool/Worker；
- 没有第二套 Runtime；
- 至少一个 Skill 被两个合法入口复用；
- CT 至少一组 skill 形成可审计链；
- evaluation 覆盖 selection、binding、failure、fallback；
- provider-free 与真实 Provider 证据等级分离；
- C0-C7 每个阶段都有独立 commit 且已 push；
- Phase D 尚未启动。
