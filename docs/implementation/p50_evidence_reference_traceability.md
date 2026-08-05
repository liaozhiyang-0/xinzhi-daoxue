# P50：教师证据引用可追踪性

## 目标

P49 已在发布预览中显示证据引用数量，但“非空”不等于“可定位”。本阶段为 CT/AE 错误模板复核增加兼容的引用分类：路径、URI、带类型前缀的引用视为可追踪；单一无定位信息的字符串视为不可追踪。

## 规则

- `path`：包含相对/绝对路径分隔符的引用，例如 `teacher-notes/AE-review.md#1`。
- `uri`：带协议的引用，例如 `kb://AE/materials/chunk-1`。
- `typed`：带类型前缀的引用，例如 `course_material:AE/chapter-1`。
- `opaque`：无法定位来源的单一字符串，例如 `teacher-review`。

复核决定为 `pending` 时可以暂存空或不完整引用；决定为 `approved` 或 `rejected` 时，服务层和复核文档校验都要求至少存在一个可追踪引用。Promotion Gate 也独立检查该条件。

## 输出与边界

- 教师队列新增 `review_evidence_quality` 和 `review_evidence_reference_kinds`，工作台会显示质量状态。
- Promotion dry-run 会在 `review_evidence_summary` 中显示 `evidence_quality` 和引用类型。
- 分类只判断引用格式，不声称目标文件、URI 或材料真实存在；教师仍需提供可核验的材料/案例证据。
- 不改变冻结基线，不调用 Provider，不自动批准或发布候选模板；三个演示案例仍由用户设计。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest apps/api/tests/test_evidence_references.py apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_error_pool_promotion.py -q --no-cov
.venv\Scripts\python.exe scripts/promote_error_pool.py --course AE
```

当前仓库的 AE 复核记录仍为 pending，因此 Promotion dry-run 应保持 blocked。
