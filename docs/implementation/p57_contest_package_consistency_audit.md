# P57：竞赛支撑材料一致性审计

## 目标

为 P60 最终统合提供可复核的竞赛材料状态。审计只读取 `submission/contest_package/package_manifest.yaml` 及其材料文件，检查 manifest、证据矩阵、文件存在性和边界声明是否一致。

## 新增输出

- `artifact_count`、`artifact_status_counts`
- `artifact_ids_missing_files`
- `pending_artifact_ids` 与 `pending_artifact_statuses`
- `evidence_matrix_nonempty`
- 官方规则、官方成绩、真实用户效果、真实 Provider 结果和三个案例的边界错误

当前仓库的 10 个材料文件均存在；材料包仍为 `draft_evidence_only`。官方规则、三个演示案例、授权用户试用、Docker/政策记录和 release inventory 继续保持待补状态。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_audit.py -q --no-cov
.venv\Scripts\python.exe scripts/audit_course_assets.py --course CT --course AE
```

该审计不生成竞赛内容、不核验官方规则原文、不调用 Provider/OCR。
