# HIGH_RISK 校验与局部补丁

## VerificationReport

HIGH_RISK 结果使用 `VerificationReport`，状态统一为 `pass`、`conflict`、
`uncertain`、`failed`。每个 `VerificationIssue` 有稳定 issue ID、类型、位置、
严重度、证据、修正指令和 `deterministic` 标记。问题类型覆盖方程、计算、单位、
方向、条件、逻辑、证据、引用和工具冲突。

确定性工具失败优先形成 `tool_conflict`；原始来源冲突和关键条件缺失不会被模型
意见自动覆盖。缺少确定性证据时，报告只能标为 `uncertain`。

## 次模型边界

只有 HIGH_RISK 已产生待处理问题、双模型校验开启且 verifier 可用时，才调用现有
ModelService verifier。输入限于问题摘要、关键方程、工具结果、待审核步骤和已有
issue；不得要求次模型重新完整解题。次模型返回只登记为非确定性 `evidence`，
不能单独把争议结论升级为事实。

## SolutionPatch

补丁操作限定为 `replace`、`append`、`remove`、`mark_uncertain`。当前自动路径只对
`final_answer` 应用 `mark_uncertain` 或追加提示，并保存 `patch_count`、
`patched_sections` 和 `remaining_issues`。对完整 `final_answer` 的 replace/remove 会
被拒绝，避免修正节点用整份新答案覆盖主答案。

## 回退条件

高严重度来源冲突、关键条件缺失或确定性工具失败会设置
`requires_fallback=true`。CT CoursePack 仍只通过原有 TaskRunner/AgentRegistry
配置决定是否调用 `SOLVER_CT_V1`；未配置或调用失败时保留本地条件化结果和问题
报告，不伪造云端校验成功。
