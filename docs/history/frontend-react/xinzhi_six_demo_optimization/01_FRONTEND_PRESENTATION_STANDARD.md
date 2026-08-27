# 六大演示案例前端呈现统一规范

## 首页
增加“六大典型演示场景”卡片，每张卡片包含：
- 场景标题
- 一句话说明
- 核心能力标签
- 示例输入
- 开始演示

## 桌面布局
左：场景导航
中：主工作区
右：智能体执行轨迹
底部：来源 / 证据 / 限制 / 人工复核

## 执行轨迹
统一显示：
- 理解任务
- 制定计划
- 读取资料
- 调用能力
- 验证结果
- 人工复核
- 完成

状态：完成 / 进行中 / 跳过 / 警告 / 失败。

主界面不得直接显示 Agent ID、Skill ID、raw JSON、Provider 原始错误。
这些只进入“高级详情”。

## 结果结构
所有案例统一：
结果摘要 → 核心结论 → 分析/方案 → 证据/依据 → 需要复核 → 下一步建议。

## 公共组件
建议：
DemoScenarioCard、AgentProgress、EvidenceCard、ReviewPointCard、AssumptionCard、WarningCard、ConfidenceBadge、SourceList、StructuredResultSection、MathBlock、ComparisonTable、DemoExamplePicker。

## Demo Mode
可支持 `?demo=1`：
- 显示六个场景；
- 一键填入示例；
- 自动展开关键证据；
- 隐藏开发噪声；
- 仍运行真实 Agent，不得注入静态伪结果。
