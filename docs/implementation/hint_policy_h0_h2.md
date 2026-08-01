# H0—H2 提示策略

`HintPolicyService` 不调用模型，按以下顺序选择提示：

1. `teacher_reviewed=true` 的错因池模板；
2. `SkillRegistry` 的通用知识点提示；
3. `SolutionPacketV1` 的下一步骤标题；
4. 不含公式拼接的受控通用模板。

H0 只提出诊断问题，H1 给出知识点或检查方向，H2 给出下一步方法。首次提示为
H0 或 H1；用户请求更多提示后最多到 H2。再次请求不会产生 H3—H5，而是提示可
主动切换到直接解答。

每个 `HintDecisionV1` 记录等级、目标 skill/step、来源、披露检查状态和下一动作。
提示来源不可用时使用受控 H0，不能拼造未经验证的公式。
