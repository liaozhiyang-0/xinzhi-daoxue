# RESEARCH_03_DATA_ANALYSIS_V2 合成与边界评测

这份评测只使用测试运行时生成的合成 CSV，不代表真实用户数据、市场数据或科研效果。它验证的是“能否安全执行、能否阻断、能否复现和能否保留科学边界”。

| 类别 | 合成输入 | 预期门禁/结果 | 覆盖测试 |
|---|---|---|---|
| 两组实验 | 两个处理组、数值 outcome | 执行组间差异、区间、留一法和精确置换敏感性 | `test_executor_runs_two_group_mvp_and_writes_reproducible_artifacts` |
| 观察性回归 | 数值 exposure/outcome | 执行条件关联、残差诊断和未调整/调整敏感性 | `test_executor_runs_observational_regression_mvp` |
| 小样本实验 | 两组各少量观测 | 执行效应量，同时保留有限样本和人工复核边界 | `test_executor_runs_small_sample_mvp_with_exact_sensitivity` |
| 时间序列 | 按日期排序的 outcome | 执行一阶基线、两步基线和后半窗口敏感性 | `test_executor_runs_time_series_baseline_mvp` |
| 缺失值 | 声明变量含空值，计划未声明处理策略 | `quality_blocked`，不生成分析 Artifact | `test_executor_blocks_unplanned_missingness` |
| Manifest 形状不一致 | 实际行数与授权清单不一致 | `quality_blocked`，不执行统计计算 | `test_executor_blocks_manifest_shape_mismatch_before_analysis` |
| 计划篡改 | 修改冻结计划 hash | `failed`，不读取原始数据 | `test_executor_rejects_tampered_frozen_plan` |
| 方法/数据隔离 | 同时提供 `method_reference` 与 `user_dataset` | 只有方法证据 ID 进入分析结果 | `test_research_analysis_v2_uses_local_executor_without_model_calls` |
| 星辰配置边界 | 配置星辰 Provider，但请求显式启用 v2 | 仍走本地执行器，云端调用次数为 0 | `test_research_analysis_v2_stays_local_even_when_xingchen_is_configured` |
| 旧治理兼容 | v2 结果含样本量文本但无 `provided_results` | 不被旧 V1 校验器误判为伪造结果 | `test_data_analysis_v2_result_is_not_mistaken_for_unverified_model_output` |

验收重点：

1. 任何合成结果都不应被描述为真实研究效果。
2. `executed` 只表示本地计算完成，不表示结论已经通过科研人员签字。
3. `human_review_required` 必须保持为真，且复核清单未完成前不能视为可发表结论。
4. 真实项目接入时仍需补充数据字典、研究方案、样本抽样框、方法引用和隐私合规材料。
