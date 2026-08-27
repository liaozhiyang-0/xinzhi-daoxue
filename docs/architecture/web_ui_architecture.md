# 芯智导学统一 Web UI 架构

## 审计结论

改造前存在 `/debug`、`/student`、`/debug/rag`、`/debug/agents` 四个独立静态页面。当前 `/student`、`/workspace` 与 `/workspace-legacy` 共用 FastAPI 托管的 `workspace.html` 和原生 JavaScript；`/workspace-legacy` 保留为兼容入口，不做重定向。

可复用部分是既有 API、任务事件流、图片资源接口、调试 Trace 和浏览器端原生技术栈。主要重复是各页面各自实现请求、转义、状态颜色、布局、错误提示和响应式 CSS。视觉上的主要问题是导航缺失、主题不统一、状态文案混用，以及调试内容在单个长页面堆叠。

稳定边界保持不变：`POST /api/v1/tasks`、SSE、文件上传、知识图片、RAG Debug、Agent Debug、健康接口、`ACADEMIC_PROBLEM_SOLVER`、RAG 和索引均由现有后端服务提供。

## 最终结构

```text
FastAPI 页面路由
  /                 home.html
  /workspace        debug/workspace.html
  /student          debug/workspace.html
  /workspace-legacy debug/workspace.html（兼容入口）
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

Student Workspace
  debug/workspace.html  页面结构与案例按钮
  debug/workspace.js    会话、消息、任务流、证据和 Runtime 控制
  debug/ts/*.js         Legacy 工作区复用的模块化传输/材料合同
```

页面加载只读取静态资源和轻量状态接口。业务调用仍由现有 API 完成；前端不包含 RAG、Provider 或 TaskRunner 逻辑。`ui-core.js` 使用 DOM `textContent`/`createTextNode` 构造动态内容，Markdown 首版支持标题、列表、引用和代码块，不直接插入未过滤 HTML。

## 兼容与安全

- `/debug` 保留并进入演示中心；`/student`、`/workspace` 和 `/workspace-legacy` 共用同一页面。
- 学生端不展示完整 Trace、point ID、Prompt 或向量。
- Agent 与系统页面只显示 configured 布尔值和脱敏摘要。
- 真实云端动作需要用户确认；页面载入不会触发云端调用。
- Mock 使用紫色“开发模拟”状态，不作为开放能力展示。
