# P9：知识库课程边界与解析证据审计

## 目标

把已有知识库质量报告中的课程归属检查提升为可重复的审计信号，防止不同课程的资料、相对路径或引用元数据混入同一课程索引。该检查只读取已生成的 Manifest 和质量问题报告，不修改原始教材、索引或 Solver。

## 检查内容

- Manifest 中缺失或未知的 `course_id`。
- `source_relative_path` 与 `relative_path` 不一致。
- 同一课程出现多个来源根目录，提示可能的跨课程放置。
- 现有 `possible_cross_course_placement` 质量问题数量。
- 课程边界汇总状态：`clean` 或 `review`。
- Manifest 是否携带 OCR 状态、置信度和人工复核字段；缺失时报告为 `unavailable`，不等同于 OCR 通过。

当前报告中 CT/AE 的边界状态为 `clean`；这只说明当前 Manifest 没有触发上述结构化边界规则，不代表教材内容已经完成语义级人工复核。

## 复现

```powershell
.\.venv\Scripts\python.exe scripts\audit_course_assets.py --course CT --course AE
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_audit.py -q --no-cov
```

OCR 置信度仍遵循 P5 边界：没有 OCR 引擎或人工确认时，置信度保持为空，PDF/DOCX 不得因元数据登记而被描述为已完成正文解析。
