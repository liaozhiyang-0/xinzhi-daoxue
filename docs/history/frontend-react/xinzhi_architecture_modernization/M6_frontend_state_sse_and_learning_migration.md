# M6：Frontend State / SSE / Learning Migration

## 目标
迁移最关键的 Agent 工作台状态逻辑。

## 状态
以现有后端真实状态/事件为准，React 建立明确映射，不自行发明不兼容状态。

## SSE
建议封装 `useTaskStream(taskId)`：
- EventSource lifecycle
- sequence handling
- reconnect（仅按既有语义）
- event parsing
- cleanup
- error surface

不得改变后端 SSE 顺序/含义。

## Task
建议 `useTask()` 统一：
submit / status / result / cancel / retry / resume。

## Attachments
独立 feature。

## Learning
迁移 hint / check / disclose / progress / retest / runtime approval/resume。
必须继续走既有 Learning API，不建立第二业务链。

## Debug
正式 Workspace 与调试面板分模块，但保留必要调试能力。

本阶段不 commit。
