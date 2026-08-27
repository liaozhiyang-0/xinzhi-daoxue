# P2：Critical Product Fixes

## P0 Critical
优先修复：
- Task 无法完成
- Task 错误终态
- SSE 丢事件
- resume/retry 破坏状态
- 文件/图片上传失败
- waiting_review 无法继续
- 权限绕过
- 数据丢失
- 前端崩溃
- 公式导致整条消息崩溃

## P1 Major
随后处理：
- 中文状态不一致
- 错误提示不可操作
- 大公式溢出
- 关键按钮误导
- 主演示分辨率严重布局异常

## 规则
每个修复：
`reproduce → minimal fix → targeted regression → six-demo smoke`

P2 不做 Agent 算法优化。
