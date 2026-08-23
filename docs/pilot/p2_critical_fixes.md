# P2 Critical Product Fixes

## 已关闭

| issue_id | reproduce | minimal fix | targeted regression | status |
| --- | --- | --- | --- | --- |
| P1-UPLOAD-01 | AC-01 图片展示路径、二进制 MIME、任务附件链 | 演示图改走公共 `/demo-assets/case6-opamp.png`；保留管理员题库权限边界；图片扩展名/MIME 兜底 | Case6/auth/upload/showcase `18 passed`；demo contract PASS | CLOSED |
| P1-RUNTIME-01 | active Planner 任务与业务 Runtime 交界 | `ACADEMIC_PROBLEM_SOLVER` 保留已注册业务 Runtime；CanonicalPlan 只投影 Goal 来源，不误接管冻结求解器 | Planner/Runtime/控制面集合 `154 passed, 1 skipped` | CLOSED |
| P1-EVIDENCE-01 | 真实任务证据不足却可能被看作普通成功 | 保留 `completed_with_gaps`、`publishable=false`、`manual_review_required` 与证据缺口 | knowledge/quality/场景回归；真实台账记录 | CLOSED |
| P1-VISION-01 | 图像字段不完整时继续推导的风险 | 保留视觉结构验收、关键字段拒答和人工复核；不放宽电路拓扑安全门 | 视觉/题图定向回归与 AC-01 图片矩阵 | CLOSED / continuing evidence |
| P1-CATALOG-01 | 场景 `text/image/mixed` 与 Agent 细粒度模式校验不一致 | 校验器把标准场景输入映射到 `single_image`/`text_and_single_image` 等执行模式；禁用场景不参与可执行能力门 | `scripts/validate_scenarios.py` PASS | CLOSED |

## 没有做的事

- 没有删除测试、调低 CI 标准或关闭 workflow；
- 没有恢复旧 Router/legacy Runtime 作为 active owner；
- 没有把真实模型生成成功改写成“证据充分”或“可发布”；
- 没有修改数据库 migration 或公共 Task/RAG/Tool 接口。

## 未关闭但有明确 workaround

科研真实检索质量、课程资料不足、教师复核、Edge 文件选择器权限、双 Worker/长时并发和真实成本仍是 P6/P7 门禁。系统在这些条件不满足时必须显示待复核/不可发布，而不是假成功。
