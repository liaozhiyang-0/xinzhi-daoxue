# 统一 Web UI 重构报告

## 范围与结果

本次把原本分散的学生端、旧演示页、RAG Debug 和 Agent Debug 统一到同一 AppShell，并新增首页、系统状态和会议演示中心。业务后端、LEARN、SOLVER_CT、RAG、知识库与索引均未修改。

统一路由为 `/`、`/student`、`/debug/rag`、`/debug/agents`、`/system`、`/demo`；`/debug` 继续兼容。共享设计系统由 `design-tokens.css`、`app-shell.css`、`components.css`、`pages.css` 和 `ui-core.js` 组成。旧的 `index.html`、`app.js`、`style.css`、`student.css` 已删除，因为它们只服务旧壳层并重复请求、状态与样式逻辑。

## 页面改进

- 学生端：文档式回答、固定输入区、示例预填、图片预览、来源折叠、可读路由、Mock/降级提示。
- RAG Debug：首屏请求与概要，过程/上下文/云端/引用/评测标签分层，统一时间线和证据卡。
- Agent 管理：状态表格、过滤、可读概览、协议与策略标签页、分级调试动作。
- 系统状态：组合既有轻量状态接口，失败时局部降级，不触发云端或大型模型。
- 演示中心：七个固定场景、说明/载入/开始/重置、真实云端确认和 presentation 模式。

## 浏览器验收

Edge/Chromium 无头浏览器在 test + mock Provider 下完成 14 张截图，浏览器脚本异常为 0。学生完成态和 RAG 结果态均通过实际本地接口产生；截图位于 `docs/reviews/web_ui_screenshots/`。覆盖首页浅/深色、学生空/完成/图片、RAG 总览/结果、Agent 列表/详情、系统、演示、presentation、1366×768 和 390×844。

页面首屏只请求静态资源与轻量状态；系统页脚本不包含任务创建或 RAG 运行端点。浏览器批处理总耗时不是首屏性能数据，其中包含实际本地任务、检索和14张全页截图。

## 最终回归（2026-07-18）

- Ruff：通过。
- Mypy：73 个源文件通过。
- Pytest：165 passed、13 skipped，覆盖率 83%。
- RAG fixture：60/60，Top3 代理召回 96.7%，跨课程证据率 0；本轮平均耗时 839ms 包含 BGE 与图片模型冷启动，不能与历史热路径 p95 直接比较。
- Demo Preflight：19/19；测试环境 FastAPI 总状态为 `degraded`（MinIO 被刻意设为不可达），但 API、六个页面路由、Qdrant、索引、LEARN Flow 与 SOLVER_CT Flow 均通过。
- 浏览器：14/14 截图，0 个脚本异常，覆盖浅色、深色、1366×768 和 390×844。
- 真实 Xingchen：LEARN 与 SOLVER 测试文件共 11 项通过，包含 CT/AE/DE、边界、文字与单图片路径；未修改云端工作流。
- 敏感文件扫描与 `git diff --check`：通过。

## 风险

原生安全 Markdown 渲染器当前只覆盖常用标题、列表、引用与代码块，复杂表格和公式仍依赖纯文本可读降级。真实云端回归与本地 UI 浏览器回归分开执行，避免截图过程消耗额度。移动端以基本可用为目标，复杂 RAG 表格仍优先桌面端。
