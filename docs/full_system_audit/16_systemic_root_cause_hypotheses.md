# 系统性根因假设

以下是基于证据的定位假设，不是已确认根因；修复阶段应以 trace、contract test 和最小复现逐一证伪。

## H1：运行表面分裂

实际用户入口是 legacy workspace，而 React 源码/构建是另一套表面；`/api/v1/chat` 和 `/api/v1/tasks` 也出现不同执行结果。多份表面会让测试通过错误入口，造成状态、文案、任务契约长期漂移。

## H2：路由粒度和能力绑定不一致

同一任务的 route Agent、Planner capability、node target 和 output contract 不同粒度，简单 explain_concept 被放入 knowledge.govern 并在验证阶段失败。需要建立一次 canonical route/plan snapshot，并让执行和验证只消费它。

## H3：结果验证没有“最小可用降级”

执行节点已经完成，但 validator 以 insufficient 让整个任务失败；同时低相关检索没有拒答。验证器和 fallback 更偏向全有或全无，缺少“明确不确定、保留可靠部分、请求补充信息”的中间状态。

## H4：证据层没有可靠 abstention

不存在词仍能得到候选，RAG 和 research 接口都没有 warning/no_match。embedding/hybrid 召回结果被当作可用证据的风险高于模型本身的生成错误。

## H5：任务结果与 UI artifact ownership 不完整

旧电路图穿透到新文本任务，说明 state cleanup 不是唯一的任务 ID keyed store，或渲染层没有在新 task 开始/终态时替换全部节点。应为每个 message/task/artifact 建立显式 owner，并在渲染前断言 owner 一致。

## H6：取消是协作式而非用户可见的强语义

cancel 请求被保存，但 runtime/外部请求仍运行。应将 API/UI 状态区分 `cancel_requested` 与 `cancelled`，显示 deadline，并保证超时后的补偿收敛和资源回收。

## H7：失败路径埋点不完整

debug execution 的 waterfall 0 ms 与真实节点耗时不符，导致失败原因只能靠 task JSON 深挖。需要在每个 stage finally 记录 started/completed/error/duration，不能只在 happy path 更新指标。
