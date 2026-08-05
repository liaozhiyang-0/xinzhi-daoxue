# P17 教师 OCR 复核可观测性

## 目标

在只读教师工作台中补充 OCR 复核快照的新鲜度和决策证据摘要，帮助教师判断当前列表是否来自缓存、是否需要重新检查，同时保留“人工复核后才能继续”的边界。三个演示案例不属于本阶段范围。

## 本阶段变更

- OCR 复核摘要展示 `Snapshot miss`、`Snapshot hit` 等缓存状态，并显示缓存后端和快照年龄。
- 复核候选行继续展示课程、文件、候选页、页数和优先级；若决策 YAML 提供 `evidence_refs`、`decision_note`、复核人或复核时间，则在只读证据区域展示。
- 证据引用和备注在浏览器端以文本节点渲染，并做长度截断，避免长文本撑破布局或被当作 HTML 执行。
- 不自动运行 OCR、不自动批准、不自动发布，也不改变 Provider 调用链。

## 数据边界

缓存快照只保存队列响应和源文件指纹，不替代原始材料或教师决策文件。源文件或决策 YAML 的元数据变化会使指纹失效；快照过期后下一次读取会重新审计。没有决策文件时，页面会显示 `Decision files 0`，候选仍保持 `pending`。

## 验证

```powershell
node --check apps/api/app/static/debug/teacher.js
pytest apps/api/tests/test_teacher_web.py -q --no-cov
```

浏览器验收使用测试环境和 Mock Provider 启动本地服务后访问 `/teacher`：

1. 首次加载应看到 `Snapshot miss`，并能渲染候选列表。
2. 点击“刷新数据”后应看到 `Snapshot hit`。
3. 浏览器控制台不应出现 error 或 warn。

本阶段未执行真实 OCR、真实 Provider 或 Docker。缓存命中耗时和完整接口质量门禁记录在对应会话报告中，不将本地 Mock/测试环境结果描述为生产性能。

## 后续

下一阶段可继续完善教师筛选和决策证据统计，并为 CT/AE 课程材料质量报告提供可追溯的复核汇总；仍需保持演示案例由用户单独设计。
