# N8：Presentation 解耦与前端兼容验证

## 重要调整

Phase M 已完成：
- React 三栏展示；
- 六案例统一结果顺序；
- 中文 UI；
- MarkdownRenderer；
- 31 math fixtures。

因此 N8 不重新设计前端。

## 唯一目标

把 presentation 从固定 Agent ID 解耦。

## 建议

继续使用已有 structured result / presentation contract。

如需扩展，优先使用：

```text
section type
presentation profile
capability metadata
```

不要创建“Agent X 专属 React 页面”。

## 必须保持

- `MarkdownRenderer` 单一数学链；
- 31 条公式 fixture 全部通过；
- 主界面中文；
- waiting_review / waiting_user 视觉状态；
- 六案例三栏布局；
- unknown section generic fallback。

## 验收

新增 Capability 不需要：
- 新建固定 Agent 页面；
- 新建公式解析器；
- 新建固定 Runtime；
- 新建 raw JSON parser。

本阶段不 commit。
