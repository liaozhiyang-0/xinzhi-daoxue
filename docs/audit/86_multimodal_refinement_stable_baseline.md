# 86 多模态细化稳定基线

日期：2026-08-26

## 本次基线内容

- 新增轻量 `AttachmentRole`、`MultimodalCapabilityHint`、`MultimodalObservation` 契约。
- 在统一请求准备阶段写入角色和能力提示，不写固定 Agent 路由。
- 将通用视觉摘要与 CircuitIR 资格解耦；普通图片可继续进入 Solver。
- CircuitIR 仅由显式渲染、拓扑级分析、Planner topology hint 或固定计划模式触发。
- 复用已存在的多模态观察，避免同一任务的重复视觉调用。
- 保留原有上传校验、Planner 节点模型、Runtime 执行、非致命 Circuit 渲染和默认严格拓扑边界。

## 代码回归

新增多模态矩阵及受影响的 Solver/Circuit 回归：`101 passed`。

全量后端回归：`2007 passed, 15 skipped, 6 failed`。6 个失败均为现有 debug 页面编码断言、Runtime handler registry 冻结测试，以及既有取消/重试/Provider 错误基线；traceback 未落入本轮改动文件，不能把全量结果记为 PASS。

全仓 Mypy（按项目配置）：`Success: no issues found in 362 source files`；核心新增/修改文件的定向检查也通过。无缓存全量检查运行超过约 6 分钟后主动停止，未产生错误输出。

前端 `npm run typecheck` 与 `npm run build` 通过；构建生成的既有静态镜像已恢复，未作为本轮变更保留。配置校验、敏感文件扫描、全仓 Ruff 和 `git diff --check` 通过。

## 后续门槛

在发布前继续执行完整 Pytest、Ruff、Mypy、配置/敏感文件检查，以及 workspace 浏览器矩阵；不得把 mock 结果描述为真实 Provider 结果。
