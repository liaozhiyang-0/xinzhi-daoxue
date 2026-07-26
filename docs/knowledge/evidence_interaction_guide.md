# 证据交互指南

## 学生视图

每条 `evidence_view` 包含 S 编号、标题、课程、章节、内容类型、摘要、图片、是否进入工作流、是否被最终回答使用及角色。

- `cited`：证据进入 grounded 工作流，且 S 编号通过 CitationValidator。
- `supplementary`：候选可供补充阅读，但不得称为回答依据。
- `method_reference`：SOLVER_CT 的公式、方法或易错点参考；与题目解答分开。

正文 S 编号只定位当前任务已有数据，不调用检索接口。损坏或非 `kb-image://` URI 不渲染。相关图片标题沿用证据标题或原 caption。

## 证据覆盖度

界面仅展示“充分 / 部分 / 不足”和“实际引用 x / y 条”，不称为正确率或可信度评分。状态由 `evidence_status`、`source_references` 和 CitationValidator 共同决定。

## 调试视图

统一调试页同时展示最终证据、进入工作流的编号、实际引用编号与候选 Trace。开发者可以核对“检索到”不等于“进入云端”，“进入云端”也不等于“最终引用”。
