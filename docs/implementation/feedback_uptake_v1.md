# FeedbackUptakeV1

`FeedbackUptakeService` 比较同一用户、Session 和来源题的前后 Attempt。
判断顺序为：所有权检查、提交间隔、规范化文本、结构化步骤 ID、目标步骤、
前后 VerificationReport。

可确定判断包括是否有新版本、文本/最终答案/目标步骤是否变化，以及有限的数值、
单位、符号和布尔验证是否从错误变为正确。复杂推导、合法替代方法、纯文字改写、
复制答案或主观理解不能可靠判断，统一返回 `indeterminate`。

服务不调用模型，`FEEDBACK_UPTAKE_MODEL_ENABLED` 的实际行为固定为 false。
结果保存在当前 Attempt 的 `feedback_uptake_json`，不新增独立表。

学生界面只显示“你已经修正了目标步骤”“当前修改仍需检查”“未发现目标步骤
发生变化”或“该过程较复杂，暂时无法自动判断”，不展示枚举、内部置信度或
算法评分。FeedbackUptake 不等于真实理解。
