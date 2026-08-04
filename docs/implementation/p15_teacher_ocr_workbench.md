# P15 教师 OCR 复核工作台

## 目标

在教师工作台增加原始 PDF/OCR 复核队列的只读视图，让教师能按课程查看待确认材料、候选页码、解析边界和已有决策状态。此阶段不执行 OCR、不批准材料、不发布索引，也不调用任何真实 Provider。

## 实现

- `GET /api/v1/knowledge/ocr-review-queue` 复用课程材料审计和 OCR 决策校验链路。
- 仅材料管理员（教师/管理员）可读取，游客或学生不能读取该队列。
- `course_id` 支持 `CT`、`AE`、`DE`；未指定时返回全部课程。
- 教师工作台新增 OCR 复核区域，展示候选数量、高优先级数量、决策文件数量、候选页码、建议动作和决策状态。
- 课程选择变化时只刷新 OCR 队列；“查询指标”仍负责刷新学习指标、材料质量和完整工作台数据。
- 决策文件仍从 `.local_outputs/ocr_decisions/` 读取，任何过期校验或非法状态只作为报告返回，不会修改源文件。

## 验证

后端测试：

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_teacher_web.py -q
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_knowledge_api.py apps/api/tests/test_knowledge_ocr_review.py -q
```

浏览器验收：

1. 打开 `/teacher`，确认 OCR 区域显示为只读说明。
2. 确认全部课程显示 38 条候选（数量随本地材料变化，不作为模型指标）。
3. 将课程切换为 `CT`，确认队列刷新为 CT 课程候选；当前本地材料为 15 条。
4. 检查浏览器控制台无 error/warn。

## 已知边界

首次加载或文件指纹变化时仍会对本地课程材料执行审计，可能需要十几秒；未命中时的审计结果会写入 P16 快照缓存。后续仍需保留生成时间、输入摘要和重建方式。
