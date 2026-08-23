# Phase E7：Phase E Closeout 与 Git Release

## 目标
完成整个 Experience Memory 后统一验证和发布。

## 必须生成
1. `docs/audits/experience_memory_phase_e_closeout.md`
2. Experience lifecycle architecture
3. privacy/scope matrix
4. promotion policy
5. evaluation report
6. KEEP / MERGE / FREEZE / REMOVE 更新

## 收口检查
必须确认没有：
- 第二 MemoryService
- 三套独立 Success/Failure/Strategy 数据库
- Experience-owned Runtime
- Experience-owned Task lifecycle
- 自动修改 prompt/Skill/code
- 自动 promotion
- 跨用户检索泄露
- synthetic 成功被标成 production strategy

## 本地完整验证
至少：

```text
git diff --check
ruff
mypy
experience targeted tests
planner/skill/reflection regression
privacy/isolation tests
checkpoint/resume tests
full pytest
repo drift
config validation
API/OpenAPI checks if schema changed
frontend typecheck/build if contract changed
```

## 大阶段统一提交

全部通过后：

```text
git add <Phase E related files only>
git commit -m "feat(agent): complete phase E experience memory"
git push origin agentic/phase-e-experience-memory
```

验证：
- local SHA
- remote SHA
- GitHub Actions

## CI 失败
如果是 Phase E regression：
- 最小修复
- 重验
- 可以追加一个 `fix(ci)` commit

如果是确认无关的历史失败：
- 记录具体 job/step/evidence
- 不得谎报 Overall PASS
- 是否允许 closeout 需明确写 condition

## 最终验收

```text
Phase E completed.

ExperienceRecord is the single governed experience contract.
Success/Failure/Strategy are projections, not separate memory systems.
Planner uses Experience only as a bounded prior.
Registry, SkillPolicy, ToolPolicy and verification remain authoritative.
Privacy, TTL, conflict and forget are enforced.
No automatic self-modification or automatic promotion exists.
Phase E release is pushed to GitHub and CI status is recorded.

Phase F has NOT started.
```
