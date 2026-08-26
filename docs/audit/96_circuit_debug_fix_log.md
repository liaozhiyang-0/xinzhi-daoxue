# 96 电路绘图调试修复记录

日期：2026-08-26

1. 将默认渲染路径改为确定性 SVG，保留旧路径仅供显式兼容测试。
2. 将布局从渲染器中拆成 `SchematicLayoutIR`，补充端口、边界、网络线、结点和标签合同。
3. 修复 invalid IR 仍可能进入绘图的问题：无效输入现在返回 failed 且无 SVG。
4. 修复运行时元数据丢失：artifact/observation 现在携带 renderer、layout version、template 和尺寸。
5. 修复浏览器静态资源构建覆盖电路开关与旧缓存查询的问题，并补上 dark/light token 样式。
6. 修复开发 Mock 测试路径与冻结生产执行面的边界：兼容逻辑只在 Mock development manifest 下启用。
