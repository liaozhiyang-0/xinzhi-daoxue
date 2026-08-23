# Phase E6：Experience Evaluation、Privacy、Conflict 与 Forget

## 目标
证明 Experience Memory 不会污染 Planner、泄露数据或放大错误策略。

## Evaluation

### Retrieval
- valid match rate
- irrelevant match rate
- stale/expired filtering
- wrong-scope filtering
- version mismatch filtering
- top-k latency

### Planner impact
- plan improvement
- plan degradation
- failure avoidance
- invalid target
- unsupported skill/tool
- cost/latency overhead

### Experience quality
- false success promotion
- false failure generalization
- conflicting strategy detection
- stale strategy usage
- provenance completeness

### Privacy
- cross-user isolation
- raw sensitive text leakage
- user-scoped/global boundary
- deleted/forgotten records not retrievable

### Lifecycle
- expiry
- deprecation
- conflict resolution
- supersede
- forget

## Conflict 规则
如果两个 active Strategy 冲突：
- 不静默任选；
- 根据 evidence level / version / applicability / recency / validation quality 排序；
- 无法决策时 Planner 不使用该经验，并写 conflict trace。

## Forget
必须支持：
- user-scoped forget
- expiry
- admin/system deprecation
- superseded strategy retirement

Forget 后：
- Retriever 不再返回；
- audit tombstone 是否保留按隐私政策决定；
- 不影响 Runtime checkpoint 历史恢复语义。

## Evidence
继续区分 synthetic / offline real / real provider / canary / production。

如果没有真实 Provider：
Phase E 可给 `STRUCTURAL_GO` 或 `CONDITIONAL_GO`，
不得宣称 Experience 已提升真实答案质量。

## 本阶段不 commit
完成后继续 E7。
