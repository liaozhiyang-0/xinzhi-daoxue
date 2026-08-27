# 端到端链路发现

## 浏览器主链路

实际 `/workspace` 能完成游客身份、创建会话、输入问题、提交任务、显示进度、渲染答案、查看证据、刷新恢复。普通串联电阻问题在本轮浏览器路径完成，答案中的核心物理结论基本正确。

但同一链路暴露两个高风险现象：

1. 新任务执行期间和完成后仍有上一任务的 5V/R1/R2 分压电路图产物；当前文本问题没有请求电路图。该 UI 状态污染会让用户把旧图当成新答案的一部分。
2. 右侧“学院知识库治理 · 电路理论”与普通学生问答不匹配；证据列表混入三相电路和正弦量等不适用片段，虽然正文部分做了有限免责声明，但用户仍需自行判断。

## `POST /api/v1/chat` 链路

简单串联电阻问题通过 `POST /api/v1/chat` 返回 202，得到 request/task/stream/result URL；随后任务很快变为 `failed`，`failure_category=runtime_node_error`，`result_content=null`，`started_at=null`，且调用记录显示没有模型调用和工具调用。该入口对 API 消费方并不可靠。

## `POST /api/v1/tasks` 链路

同类简单问题通过 tasks 入口可以进入 route/plan/runtime，但本次任务的 route 是 `LEARN_01_KNOWLEDGE_QA_V1`，Planner selected capability 是 `knowledge.govern`，knowledge.execute 实际完成约 3254 ms，verify 完成后，最终在结果契约校验阶段以 `insufficient` 失败。执行过但不能形成用户可用结果，说明“运行完成”和“任务成功”之间的契约存在断层。

## 状态和事件

SSE 对已产生的任务事件表现良好：从 Last-Event-ID 0、10、16 分别能够从对应位置继续，事件序号保持顺序，终止事件可到达。取消语义则相反：请求立即被接受，但实际 runtime 仍运行约 50 秒才收敛。

## 端到端结论

系统不是“全链路不可用”，而是存在路径分叉：基础设施、队列、部分 RAG 和页面渲染可以正常工作，但 route/plan/result/UI 的一致性不足。应优先建立单一的实际用户入口和同一任务契约，再修复单个 Agent 的内容质量。
