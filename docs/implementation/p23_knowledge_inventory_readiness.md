# P23：知识库质量摘要接入课程 readiness

## 目标

将现有知识库 manifest、质量问题清单和 OCR 元数据覆盖情况接入课程资产 readiness。该阶段只读审计，不执行 OCR、不重建索引、不修改冻结基线，也不把 Mock 或缺失证据描述为真实结果。

## 实现

- `build_course_asset_readiness` 增加 `knowledge_inventory` 摘要。
- 摘要读取 `knowledge_indexes/knowledge_base_manifest.jsonl` 和 `knowledge_indexes/knowledge_base_quality_issues.json`，按 CT/AE 过滤。
- 返回文档数量、解析状态分布、质量状态分布、质量问题类型、manifest 异常行数、OCR 元数据和置信度覆盖、人工复核标记数量。
- OCR 状态只表达 manifest 中的元数据覆盖：`available`、`partial` 或 `unavailable`；它不等同于 OCR 已执行或 OCR 质量合格。
- 教师工作台 readiness 卡片显示文档量、质量问题数和 OCR 元数据覆盖率。

## 阻塞规则

- manifest 缺失或存在不可解析行：高优先级阻塞。
- 质量问题清单不可用：中优先级阻塞；清单存在问题时提示复核，不自动修复。
- OCR 元数据完全缺失或覆盖不完整：中优先级阻塞，并要求先明确 OCR 适用范围和元数据契约。
- `manual_review_required=true` 的记录会形成待人工复核阻塞。

这些规则不假设每个文件都必须 OCR；“OCR metadata unavailable”表示当前 manifest 没有可供审计的 OCR 元数据，不是对文件 OCR 必要性的结论。

## 当前审计观察

审计时 CT manifest 有 1,099 条记录、31 条质量问题，AE manifest 有 625 条记录、30 条质量问题；两门课程记录中均未发现 OCR 元数据字段。因此工作台应显示质量待复核和 OCR 元数据不可用，不能显示 OCR 已完成或质量合格。

## 验证

```powershell
.\.venv\Scripts\ruff.exe check apps/api/app/services/course_asset_review.py apps/api/app/contracts/knowledge.py apps/api/app/contracts/__init__.py apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py
.\.venv\Scripts\mypy.exe apps/api/app
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py -q
node --check apps/api/app/static/debug/teacher.js
```

浏览器验收应确认 CT/AE readiness 卡片显示知识库摘要；DE 仍保持课程边界提示；不执行 OCR、不调用真实 Provider。

## 后续

下一阶段可在明确 OCR 适用范围后，补充按文档/页的质量明细和教师复核入口；在此之前不自动运行 OCR，也不把质量问题清单直接转成运行时资料。
