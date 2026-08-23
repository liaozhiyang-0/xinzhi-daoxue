# 芯智导学统一 Web UI 架构

## 审计结论

改造前存在 `/debug`、`/student`、`/debug/rag`、`/debug/agents` 四个独立静态页面。当前 `/workspace` 已收敛到 React/Vite 实现；旧 `student.html`、`workspace.html`、`student.js`、`workspace.js` 及其静态 Workspace 适配器已删除。`/student` 与 `/workspace-legacy` 只保留兼容重定向。

可复用部分是既有 API、任务事件流、图片资源接口、调试 Trace 和浏览器端原生技术栈。主要重复是各页面各自实现请求、转义、状态颜色、布局、错误提示和响应式 CSS。视觉上的主要问题是导航缺失、主题不统一、状态文案混用，以及调试内容在单个长页面堆叠。

稳定边界保持不变：`POST /api/v1/tasks`、SSE、文件上传、知识图片、RAG Debug、Agent Debug、健康接口、LEARN、SOLVER_CT、RAG 和索引均未改动。

## 最终结构

```text
FastAPI 页面路由
  /                 home.html
  /workspace        react/index.html（唯一学生工作区）
  /student          307 → /workspace
  /workspace-legacy 307 → /workspace
  /debug/rag        rag.html
  /debug/agents     agents.html
  /system           system.html
  /demo             demo.html
  /debug            demo.html（旧书签兼容）

共享静态管理/调试前端
  design-tokens.css  颜色、排版、间距、深浅主题
  app-shell.css      Sidebar、Topbar、抽屉、演示模式
  components.css     Button、Badge、Card、Table、Toast 等
  pages.css          页面专属布局
  ui-core.js         非 Workspace 页面 Shell、主题、API缓存、安全渲染、状态映射

React Workspace
  apps/web/src/      会话、消息、Composer、任务流、证据、Runtime 控制
  react/index.html   唯一 Workspace HTML 壳与 Vite 构建产物
```

页面加载只读取静态资源和轻量状态接口。业务调用仍由现有 API 完成；前端不包含 RAG、Provider 或 TaskRunner 逻辑。`ui-core.js` 使用 DOM `textContent`/`createTextNode` 构造动态内容，Markdown 首版支持标题、列表、引用和代码块，不直接插入未过滤 HTML。

## 兼容与安全

- `/debug` 保留并进入新的演示中心；其余旧 URL 不变。
- 学生端不展示完整 Trace、point ID、Prompt 或向量。
- Agent 与系统页面只显示 configured 布尔值和脱敏摘要。
- 真实云端动作需要用户确认；页面载入不会触发云端调用。
- Mock 使用紫色“开发模拟”状态，不作为开放能力展示。
