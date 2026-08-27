# 前端与用户体验发现

## 入口与产品一致性

`/workspace` 实际服务 `apps/api/app/static/debug/workspace.html`；React 源码在 `apps/web/src`，构建产物在 `apps/api/app/static/debug/react`，但 `/workspace-react` 最终重定向回 legacy `/workspace`。这造成至少两套 UI/状态实现，前端类型检查通过也不能证明用户实际看到的页面已覆盖这些修改。

## 已观察的摩擦

- 三栏工作台信息密度高：回答、证据、执行过程、上下文、回答信息和 Runtime 控制同时出现；失败、部分产物和未验证状态的层级不清。
- 用户可见 `Agent Runtime`、`Terminal Runtime runs cannot be controlled`、`planner_active`、`accepted_with_warnings` 等内部词汇；这些词不帮助学习者完成任务。
- 普通问题被呈现为“学院知识库治理 · 电路理论”，与用户真实意图不匹配；侧栏历史会话很多，且多个标题重复或显示“新会话 · 0 条消息”，降低定位能力。
- 后端 readiness 有 9 个场景，但首页 showcase 只有 6 张卡片；评分量规、纯文本诊断、频谱和部分研究/数据能力没有同等发现路径。
- 当前回答允许出现“有直接课程资料支持”但同时“尚无独立答案质量判定”，用户需要自己理解两者差异。

## 正面观察

页面具备键盘可见的按钮/文本框标签、深浅主题、侧栏和上下文面板开关、文件预览、停止按钮、证据卡片和刷新恢复；控制台本轮未观察到 error/warn。

## 移动端边界

legacy CSS 明确为 `max-width:1180` 隐藏会话侧栏、转为右侧抽屉；`max-width:620` 将上下文转为底部抽屉并隐藏部分高级设置。由于本轮未改变浏览器真实 viewport，移动交互/触摸可用性仍未验证，不能报告通过。
