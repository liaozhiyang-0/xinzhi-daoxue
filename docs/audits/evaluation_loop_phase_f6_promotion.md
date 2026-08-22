# Phase F6：Promotion Governance 与 Experience 对接

## Governance

`PromotionGovernance` 消费 `ImprovementProposal` 和 `ReplayResult`，输出 `PromotionDecision`：

```text
approve | reject | defer | needs_review
```

Decision 包含 eligible targets、evidence level、regression summary、risk、approval reason、reviewer/policy 和 rollback requirement。Replay gate 失败直接 reject；synthetic evidence 只能 needs_review，不能宣称生产质量。

## Experience boundary

只有通过治理的 proposal 才能由 `to_experience_candidate()` 生成 `ExperienceCandidateCreate`。生成的是 Phase E lifecycle 的 `candidate`、global-deidentified、redaction verified 记录草案；该函数不调用 repository、不写数据库、不 activate。

当前唯一 eligible target 是 `experience_candidate`。Prompt、Planner policy、Skill configuration、verification rule、reflection policy 和 Tool binding 不会自动进入生产配置。

## F6 结论

Phase E Experience Memory 收到的只能是 governed candidate；F6 完成。
