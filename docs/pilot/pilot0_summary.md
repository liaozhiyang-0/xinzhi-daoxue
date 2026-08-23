# Phase P Pilot 0 证据冻结摘要

> 冻结日期：2026-08-23
> 证据口径：只引用仓库已有的组员反馈台账、真实任务记录、确定性回归和六案例控制面验证；没有把 Mock 或 provider-free 结果写成真实模型准确率。

## 结论

Pilot 0 已形成可审计的混合证据集：

- 31 个组员反馈场景已进入长期台账，见 `docs/optimization/team_feedback_31_scenario_ledger.md`；
- 六个产品案例已完成统一 Planner/Capability/Skill/Runtime 控制面验证；
- 多个组员场景已有真实 Provider/API/Edge 任务记录，但部分结果仍为 `completed_with_gaps`、`publishable=false` 或需要教师复核；
- 案例 6 图片导入问题已有仓库演示资产、真实上传接口和回归测试证据；Edge 文件选择器权限仍不等同于后端上传通过。

## 证据等级

| 等级 | 含义 | 本次使用 |
| --- | --- | --- |
| L1 | 静态检查、单元测试 | 用于回归和契约，不宣称真实用户体验 |
| L2 | 原始文本/图片的 provider-free 回放 | 用于路由、输入、输出契约和安全边界 |
| L3 | 配置完整的真实 Provider/API/Edge 任务 | 只对有明确 task ID 的记录使用 |
| L4 | 并发、重连、恢复和发布环境验收 | 当前仍是后续准生产门禁 |

## 已冻结的 Pilot 事实

| 范围 | 已有证据 | 当前结论 |
| --- | --- | --- |
| 六案例 Planner 接管 | `scripts/validate_planner_controlled_takeover.py`：6/6，0 网络调用，0 Provider 调用 | 控制面 PASS；不是模型质量验收 |
| AC-01 图片链路 | `/demo-assets/case6-opamp.png`、上传/附件/展示定向回归、已有真实后端链路记录 | 后端与安全边界 PASS；Edge 选择器仍需环境复验 |
| G2-05/G2-08/G2-10/G2-11/G2-12/G2-13/G2-16/G2-17 | 组员台账中的 task ID、Provider/模型、事件序号和质量门记录 | 真实链路部分通过；内容发布仍按人工复核门处理 |
| 科研证据类 G2-01/G2-06/G2-14/G2-15 | 失败归因和确定性证据治理测试 | 真实检索验收未冻结为 PASS |
| 准生产稳定性 | Runtime/SSE/retry/resume/cancel 回归集合 | L1/L2 PASS；双 Worker 与长时并发仍待 P6 |

## 隐私与复现

- 原始组员身份、学号、联系方式和私人账号不进入本目录；记录使用 `PILOT-REC-*` 匿名记录号。
- task ID 仅保留用于仓库内审计关联；真实用户身份字段不在本报告中复制。
- 详细任务证据仍以现有台账和受控本地环境为准，不将结果上传到公共仓库之外。

## P0 冻结判定

P0 证据冻结完成。后续修复必须引用本冻结集中的 `record_id`、场景 ID 或确定性回归，不得边修边重写 Pilot 原始结论。
