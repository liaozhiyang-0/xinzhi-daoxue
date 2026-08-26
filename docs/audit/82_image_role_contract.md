# 82 图片角色契约

日期：2026-08-26

## 契约

`AttachmentRef` 增加以下兼容字段：

- `primary_role`：`TEXT_SCREENSHOT`、`PROBLEM_STATEMENT`、`CIRCUIT_DIAGRAM`、`STUDENT_SOLUTION`、`TABLE`、`CHART`、`WAVEFORM`、`FORMULA`、`DOCUMENT_PAGE`、`REFERENCE_IMAGE`、`GENERAL_IMAGE`、`UNKNOWN`。
- `secondary_roles`：最多 4 个，用于表达“题目截图”等复合语义。
- `role_source`：`explicit_user`、`user_prompt`、`conversation`、`multimodal_inference` 或 `unknown`。
- `role_confidence`：0 到 1。

`AttachmentRole` 是独立可复用契约；`MultimodalObservation` 以 attachment ID 关联一次视觉观察，避免下游再次上传或重复调用视觉模型。

## 优先级

角色解析按以下顺序覆盖：显式 attachment metadata > 用户当前提示 > 会话摘要 > 文件名/轻量推断 > `UNKNOWN`。显式角色一旦存在，不会被后续低优先级推断覆盖。

## 示例

“第一张是题目截图，第二张是我的答案”会得到：

```json
[
  {"primary_role": "PROBLEM_STATEMENT", "secondary_roles": ["TEXT_SCREENSHOT"]},
  {"primary_role": "STUDENT_SOLUTION", "secondary_roles": []}
]
```

“图片是表格”只增加 `TABLE` 角色和 `table_analysis` 能力，不自动请求 CircuitIR。无法判断时使用 `UNKNOWN`，并继续通用视觉路径。
