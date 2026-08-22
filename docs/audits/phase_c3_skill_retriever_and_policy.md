# Phase C3 SkillRetriever and SkillPolicy

## 目标与边界

`SkillRetriever` 和 `SkillPolicy` 是独立、无 Provider、无 Runtime side effect
的 metadata services。它们只从 Phase C2 的唯一 `SkillRegistry` 读取 manifest，
不创建 Skill、不执行 Skill、不保存 SkillMemory，也不进入真实 Planner 路径。

```text
SkillRetrievalRequest
        |
        v
SkillRetriever -- deterministic bounded top-k --> SkillMatch[*]
        |
        v
SkillPolicy -- fail closed --> approved / rejected(reason_codes)
```

## 输入

请求结构表达 `CanonicalGoal`、course、intent、problem_type、capabilities、context
summary、evidence state、learner state、available workers/tools、available skill
IDs、Planner budget、risk ceiling、role 和显式 requested IDs。所有字段都是只读
metadata；worker/tool 字符串不是可调用对象。

## Deterministic retrieval

当前只使用：

1. problem type exact match；
2. capability intersection；
3. keywords/title text match；
4. task-family/chapter metadata；
5. prerequisite availability 作为 match eligibility；
6. stable `(-score, skill_id)` 排序和 `1 <= top_k <= 20` 上限。

course 只作为候选过滤条件，不单独产生匹配分。因此只有“课程=CT”的普通请求
不会自动得到 CT Skill，避免 general fallback 污染。semantic/vector rerank 尚未
启用；如未来启用必须置于独立 flag 后并保留上述确定性 fallback。

## Policy checks

`SkillPolicy` 对每个 candidate 检查：

- 注册 identity 和精确 version；
- course/domain 和 capability；
- `active`/`experimental` 状态，拒绝 `frozen`/`deprecated`；
- 先修关系；
- eligible worker/tool 是否在当前可用集合；
- required evidence 是否已提供；
- risk ceiling、budget hint 和 allowed role；
- 显式 requested ID 是否已注册，避免模型/输入注入新 ID。

任何检查失败都进入 `rejected`，带稳定 `reason_codes`；不会降级为模糊匹配或
隐式补造。没有 course 或没有匹配 metadata 时返回空候选，供上层保留旧路径。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q --no-cov `
  apps/api/tests/test_skill_retriever_policy.py `
  apps/api/tests/test_skill_registry.py
```

覆盖 CT top-k、general 空候选、Research 先修/worker/evidence、合法依赖和
unregistered/version injection。结果：5 个新策略测试和既有 Registry 测试通过。
