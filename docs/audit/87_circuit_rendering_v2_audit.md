# 87 电路绘图 v2 审计

日期：2026-08-26

## 结论

电路绘图已切换为 `CircuitIR -> SchematicLayoutIR -> deterministic SVG` 的确定性链路。`SOLVER_CT v1.0` 未修改；绘图失败只形成嵌套观察结果，不阻断 Solver 主结果。

## 已核对

- `CircuitIR` 继续只表达器件、端口、网络、注释和不确定性。
- `SchematicLayoutIR` 单独表达模板、放置、端口、正交线、结点和标签。
- 默认生产渲染器为 `professional_svg`；旧 Schemdraw/fallback 仅保留显式兼容路径。
- 无效拓扑不输出 SVG；自由文本或图片没有可信 `CircuitIR` 时不猜测拓扑。
- 结果元数据包含渲染器、布局版本、模板、尺寸和延迟。

## 验证

定向电路回归、渲染基准和多模态路由回归已通过；完整检查以最终 CI/本地命令输出为准。
