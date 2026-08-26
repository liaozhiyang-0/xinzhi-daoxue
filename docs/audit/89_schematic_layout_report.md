# 89 原理图布局报告

日期：2026-08-26

`SchematicLayoutIR` 版本为 `schematic_layout.v1`，当前模板覆盖 series、parallel、divider、ladder、bridge、RC/RLC、运放、晶体管、source-load、logic-flow 及通用正交布局。

布局输出具有稳定顺序和固定尺寸；器件边界、端口坐标、网络线、结点和标签分离保存。线段只使用水平/垂直 Manhattan 路由，标签通过避让位置生成。布局由语义 IR 驱动，不从 SVG 反向推断拓扑。
