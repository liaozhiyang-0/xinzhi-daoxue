# 统一多工作流前端指南

## 运行

```powershell
.\scripts\dev.ps1
```

打开 `http://127.0.0.1:8000/workspace`。正式工作台只有一个输入框；课程默认自动识别，附件和更多设置可选。前端始终提交 `intent=unknown`，不靠隐藏的功能按钮替用户选 Agent。

发送后界面从真实任务与 SSE 事件展示“需求识别、工作流选择、资料准备、专业处理、结果检查、完成”。识别完成后显示可读任务名与课程，例如“教案设计 · 模拟电子技术”，并显示资料数、降级状态；普通模式不暴露内部枚举。

业务结果按 Agent 渲染为分区：教案使用时间线，批改突出“建议分，不是正式成绩”，学术写作提供修改稿，数据分析 plan 显示“未实际运行计算”。高级执行详情位于 `/debug/execution?task_id=...`，可查看候选分数、材料、映射、RAG、Parser、Validator、重路由和 Trace。

附件支持图片及文本类文件。PDF 当前只保存并提示粘贴关键文字；不要在演示中宣称 PDF 全文解析。电路题统一路由到 `ACADEMIC_PROBLEM_SOLVER`，科研工作流不自动接收图片。

前端回归：

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_unified_web_ui.py apps/api/tests/test_debug_page.py apps/api/tests/test_execution_debug_api.py apps/api/tests/test_task_presentation.py -q
node scripts/run_web_ui_browser_acceptance.js
```

浏览器命令需要本地服务和 Playwright/Chromium；缺少任一项时应明确报告为未执行，而不是视作通过。

2026-07-20 本机执行结果：演示 preflight 19/19 通过；Node 环境缺少 `playwright` 模块，因此自动浏览器交互和新截图未执行。静态前端、路由和 API 回归已包含在全量 Pytest 的 255 个通过项中。
