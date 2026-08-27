# 多模态与电路可视化发现

## 当前能力

场景 readiness 将 `academic_visual_problem_solver_v1` 和 `academic_visual_spectrum_solver_v1` 标为支持 text/image/mixed；RAG image model 已加载，指标显示本实例有 multimodal task 和 circuit diagram image role 记录。浏览器 showcase 可自动附带运算放大器示例图，页面也有“显示教材图片”和 circuit visualization 开关。

## 已观察问题

- 浏览器普通纯文本问题仍展示旧电路图 artifact，说明多模态/可视化产物的 task ownership 不清晰；这比“图像理解不准”更基础，属于结果隔离问题。
- 现有页面把“电路图产物”“拓扑已校验”“需要人工复核”和“答案生成失败”放在同一回答区域，用户难以判断图是当前任务的正式结果、缓存结果还是部分产物。
- 页面出现 `Agent Runtime`、`Terminal Runtime runs cannot be controlled` 等内部执行术语；学习者关心的是“答案是否生成、图是否可信、哪些地方需复核”，不应先理解 Runtime 术语。
- readiness 允许 demo_ready，但所有场景 production_ready=false；多模态卡片可见会产生“可直接使用”的预期，需在入口上显示明确的实验/人工复核状态。

## 正面证据

电路渲染指标本次快照为 rendered=1、validated=1、professional SVG=1，未观察到重复 vision call；这证明部分电路渲染路径能形成结构化产物，但不证明每类图像题的语义解答正确。

## 未验证

本轮没有执行 20+ 张图、模糊图、旋转图、双图对照、频谱图和错误拓扑的系统矩阵；因此不能给出图像识别准确率，也不能宣称多模态功能达到发布质量。
