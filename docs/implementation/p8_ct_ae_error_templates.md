# P8：CT/AE 错误模板候选与竞赛证据边界

## 目标

补齐 CT/AE 当前技能清单中缺失的错误签名候选，同时保证没有教师复核时不会扩大运行时自动诊断范围。三个演示案例继续由项目负责人设计，本阶段不生成、不改写案例正文。

## 当前实现

- 运行时模板仍只从 `config/error_pool/CT.yaml`、`AE.yaml`、`DE.yaml` 加载。
- 候选模板位于 `config/error_pool/proposals/CT.yaml` 和 `AE.yaml`，明确标记 `runtime_loaded: false`、`review_status: pending_teacher_review`、`enabled: false`。
- 审核记录位于 `config/error_pool/reviews/CT.yaml` 和 `AE.yaml`，每个候选必须有唯一 decision；`approved` 必须带审核人、日期和证据引用，记录本身仍不会加载到运行时。
- CT 候选覆盖：等效电阻、KCL 符号、相量相位和功率因数。
- AE 候选覆盖：二极管工作区、BJT 工作区、MOS 工作区、Q 点区域一致性、反馈极性和增益符号。
- `scripts/audit_course_assets.py` 同时报告运行时覆盖率与候选缺口覆盖率；候选覆盖率不计入运行时覆盖率。

## 教师复核后置流程

教师需要针对每个候选补充教材/题库证据、适用题型、边界条件和复核意见。只有完成复核后，才可以把经过确认的内容转换到正式错误池，并同时设置 `teacher_reviewed: true` 与 `enabled: true`。未完成复核的候选不得用于正式评分、正式成绩或竞赛结论。

## 复现与检查

```powershell
.\.venv\Scripts\python.exe scripts\audit_course_assets.py --course CT --course AE
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_audit.py -q --no-cov
```

应看到 CT 与 AE 的 `proposals_runtime_loaded` 为 `false`、`proposal_schema_errors` 为空；`error_signature_coverage_ratio` 仍只反映已启用且已复核模板。
同时应看到 `teacher_review_record_schema_errors` 为空，当前 `approved_error_proposal_count` 为 0。

## 竞赛材料边界

`submission/contest_package/package_manifest.yaml` 和 `09_evidence_matrix.md` 将仓库证据、待官方核验事项、待负责人提供的三个案例和待授权用户试用事项分开。当前状态仍是草案证据包，不代表官方规则已核验、官方成绩已取得或真实用户效果已证明。

CT/AE 的课程资产兼容边界另见 `config/course_assets/CT.yaml` 和 `config/course_assets/AE.yaml`；这两个清单只供审计使用，运行时仍以 `CourseRegistry` 为唯一事实源。
