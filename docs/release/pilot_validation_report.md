# Phase P Pilot Validation Report

## Scope and evidence posture

本报告汇总 Phase P Pilot 0 冻结证据、N 阶段控制面回归、六案例产品化和已有真实任务记录。它区分：

- `PASS`：有可重复的确定性或真实链路证据；
- `CONDITIONAL`：链路可运行，但证据、人工复核或环境条件未满足发布门；
- `NOT RUN`：本轮没有真实执行，不能用单测替代。

## Six-case validation

| case | control-plane | input/output contract | real-provider evidence | release posture |
| --- | --- | --- | --- | --- |
| TP-01 | PASS, controlled Planner | PASS, review boundary present | CONDITIONAL; related real teaching records exist | teacher review required |
| FE-01 | PASS, controlled Planner | PASS, no automatic score | PASS for related G2-10/G2-11 task records; semantic review remains | not auto-publishable |
| LP-01 | PASS, controlled Planner | PASS, evidence/prediction separated | PASS for related G2-05/G2-12/G2-13 records; course evidence gaps remain | not a formal mastery decision |
| RB-01 | PASS, controlled Planner | PASS, source/time-window boundary | NOT RUN as a complete real external-evidence acceptance | no unsupported conclusion |
| KG-01 | PASS, controlled Planner | PASS, permission/release boundary | CONDITIONAL; no final publish approval | manual approval required |
| AC-01 | PASS, controlled Planner | PASS, image import and uncertainty boundary | PASS for backend/image-chain evidence; Edge picker environment remains conditional | human review required |

## Reproducible checks

| check | result |
| --- | --- |
| Controlled six-case validator | PASS: 6/6, 0 network calls, 0 provider calls |
| Planner/Runtime/Web/attachment targeted regression | PASS: 154 passed, 1 skipped |
| Knowledge and retrieval regression | PASS: 85 passed |
| Case6/auth/upload/showcase regression | PASS: 18 passed |
| Web typecheck | PASS |
| Math fixtures | PASS: 31 |
| Demo contract | PASS: six real scenario entries |
| Web smoke | PASS |
| Web production build | PASS; chunk-size warning only |
| Scenario catalog validator | PASS: 10 total, 9 enabled |
| Sensitive-file scan | PASS |
| Full backend suite | PASS: 1956 passed, 15 skipped, 1 warning |

## User feedback boundary

历史组员反馈已冻结在 [Pilot 0 摘要](../pilot/pilot0_summary.md) 和 [匿名 manifest](../pilot/pilot0_case_manifest.md)。历史资料没有统一的 1–5 评分、匿名用户 ID、延迟 p50/p95 和完整事件字段，因此本报告不编造平均满意度、准确率或成本数字。P7 必须使用相同模板重新收集 Final Pilot。

## Acceptance conclusion

产品阻断问题（案例 6 图片导入、active Runtime 误接管冻结求解器、场景输入模式校验）已有最小修复和定向回归。六案例可以进入受控演示；“真实模型质量”“科研证据充分”“教师批准发布”“双 Worker 准生产稳定性”仍是条件项，不得写成已完成。
