# P19：CT/AE 错误模板教师复核清单

## 目标

在不修改运行时错误模板、不批准候选模板、不补写官方竞赛规则和不生成三个演示案例的前提下，为 CT/AE 课程资产审计增加可追溯的教师复核清单。

## 实现

`scripts/audit_course_assets.py` 在每门课程报告中增加 `teacher_review_queue.v1`：

- `items`：列出候选 proposal、错误签名、关联技能、题型和当前运行时覆盖状态；
- `review_decision` 与 `review_evidence_refs`：读取现有教师复核记录，缺失时明确标记；
- `priority`：被多个技能引用的签名标为 `P1`，单个技能引用的签名标为 `P2`，排序规则固定且可复现；
- `runtime_eligible` 始终为 `false`，候选项只有在教师完成审核并提供证据后，才允许进入后续人工 promotion 流程；
- `unresolved_signatures_without_proposal`：提示仍没有候选方案覆盖的运行时缺口。

该清单是只读审计结果，不会写回 YAML，不会触发 Provider/OCR 调用，也不会把 `config/error_pool/proposals/` 加入运行时加载链路。

## 运行

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe scripts\audit_course_assets.py --course CT --course AE --output .local_outputs\p19_teacher_review_queue_audit.json
```

查看 JSON 中的：

```text
courses.CT.teacher_review_queue
courses.AE.teacher_review_queue
```

## 验证

```powershell
.\.venv\Scripts\python.exe -m ruff check scripts\audit_course_assets.py apps\api\tests\test_course_asset_audit.py
.\.venv\Scripts\python.exe -m pytest apps\api\tests\test_course_asset_audit.py -q --no-cov
```

教师实际审核仍需补充真实课程依据、审核人、审核时间和证据引用；在此之前，候选模板必须继续保持 disabled、pending、runtime_loaded=false。
