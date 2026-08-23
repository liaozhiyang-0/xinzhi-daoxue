# 前端收敛交付记录

## 结论

`/workspace` 是唯一正式学习工作台。旧入口 `/student`、`/workspace-legacy`、`/workspace-react` 只保留兼容跳转，不再作为新的产品入口。现有视觉风格、颜色 token 和页面壳层保持不变，本轮只收敛入口、布局、状态流和信息密度。

## 已完成

| 项目 | 结果 | 证据 |
|---|---|---|
| 路由收敛 | 完成 | `http_app.py` 将兼容入口 307 到 `/workspace`，React build 由 `/workspace` 正式承载 |
| AppShell / tokens | 完成 | `index.html` 引入 `design-tokens.css`、`app-shell.css`、`components.css`；React、Teacher、Admin、Debug 共用壳层 |
| 身份 | 完成 | React 通过 `/api/v1/auth/me`，未登录时使用后端 guest 会话，不再固定用户 ID |
| 会话 | 完成 | 新建、搜索、归档/恢复、消息历史、摘要和记忆设置接入统一 Session API |
| Task / SSE | 完成 | React 使用统一 `task-transport.ts` 和 `useTaskStream.ts`，提交仍然非阻塞 |
| 三栏布局 | 完成 | 左会话栏、中间回答区、右任务详情区独立滚动；桌面有两个可拖动分隔条，移动端使用抽屉 |
| 输入区 | 完成 | 仅保留回答深度；文本域可拖动/键盘调整高度，内部滚动；发送区 sticky |
| 六个示范案例 | 完成 | 只在中央欢迎内容中作为快捷入口，不进入左侧会话列表，也不与历史会话混排 |
| 结果交互 | 完成 | 结构化结果、证据、执行过程、反馈、复制回答和 Runtime 控制可用 |
| Markdown / KaTeX | 完成 | React 统一使用 `MarkdownRenderer`，没有再引入第二套渲染器 |

## 有意保留

Legacy 页面资产暂不删除。其文档页导航、图片查看器和部分研究字段仍作为迁移对照与回滚保险；由于正式入口已跳转，删除动作放到 parity 回归和 CI 通过之后单独执行。输入区的“学生答案/研究分析”字段按当前产品简化要求不在正式工作台展示，但后端协议仍保留兼容字段。

## 验收命令

```powershell
cd apps/web
npm run typecheck
npm run build
cd ../..
node --check apps/api/app/static/debug/admin.js
node --check apps/api/app/static/debug/teacher.js
git diff --check
```

浏览器验收重点：桌面默认 1280×720、移动端 390×844；确认三个滚动 owner、分隔条、输入区键盘调整、欢迎案例位置和页面无全局滚动条。

