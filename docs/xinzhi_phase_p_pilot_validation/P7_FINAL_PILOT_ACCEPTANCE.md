# P7：Final Pilot + Acceptance

## 建议规模
5–10 名测试者，每人 5–10 个任务，总计约 50–100 次真实交互。

## 每人至少覆盖
- 自由问题
- 六案例之一
- 图片/附件
- 一次追问
- 一次信息不足输入
- 一次 retry/cancel/resume（如可用）

## 评分
1–5 分：
- 结果有用性
- 结果清晰度
- 操作易用性
- 可信度
- 整体满意度

## Product Gate
- critical crash = 0
- upload/review/SSE 基本稳定
- unrecoverable failure 可接受

## Agent Gate
- goal understood
- capability appropriate
- answer useful
- evidence boundary correct
- no critical hallucination

只有 critical issue = 0、major issue 有明确 workaround/limitation、六 Demo stable，才进入 P8。
