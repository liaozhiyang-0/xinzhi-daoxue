# P1 真实问题归因：Top 15 Failure Patterns

> 归因基于冻结的 Pilot 记录和已有回归，不把未量化的观察写成频率数字。`frequency` 使用观察范围，待 P7 统一统计。

| rank | issue_id | category | severity | frequency | user impact | reproducible | root cause confidence | disposition |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | P1-UPLOAD-01 | Product/upload | P0 | 复现于 Edge 文件选择器环境 | 图片任务无法开始 | high | high | P2 最小修复已完成；Edge 权限仍需复验 |
| 2 | P1-RUNTIME-01 | Product/runtime | P0 | 多个旧/新 Runtime 交界测试 | 可能出现错误终态或错误执行器 | high | high | P2/N 控制面收口；回归通过 |
| 3 | P1-EVIDENCE-01 | Agent/RAG | P0 | G2-05/G2-13 等真实记录 | 结果可生成但不可发布 | high | high | 保留 `completed_with_gaps/publishable=false` |
| 4 | P1-VISION-01 | Agent/vision | P0 | Q01–Q03 与 AC 类题图 | 读图不确定时可能误算 | medium | high | 视觉验收和拒答边界保留；继续扩充 fixture |
| 5 | P1-REVIEW-01 | Governance/review | P1 | TP/LP/KG/AC 业务边界 | 用户误以为结果已批准 | high | high | UI/结果契约显示人工复核边界 |
| 6 | P1-MATH-01 | Product/math_render | P1 | Q03/G2-07/G2-17 记录 | 公式不可读或不能发布 | medium | medium | 31 条 fixture 通过；真实结果仍需复验 |
| 7 | P1-ROUTE-01 | Agent/capability | P1 | 研究、课程和电路边界混合输入 | 任务进入不适合的能力 | high | high | Planner + preflight 接管；保留路由回归 |
| 8 | P1-CONTEXT-01 | Agent/experience | P1 | 跨课程/会话反馈 | 证据或历史状态串线 | medium | high | 已补课程边界回归；P6 做并发复验 |
| 9 | P1-PROVIDER-01 | Infrastructure/provider | P1 | 真实 Provider/本地环境切换 | Mock/真实状态可能误判 | high | high | 结果保留 provider/mock/fallback 字段 |
| 10 | P1-SSE-01 | Product/sse | P1 | 真实任务与 Runtime 回归 | 页面无法确认最终状态 | medium | high | 事件序列回归通过；重连仍列入 P6 |
| 11 | P1-RESEARCH-01 | Agent/evidence | P1 | G2-01/G2-06/G2-14/G2-15 | 无充分来源时出现空泛结论风险 | medium | high | 证据治理测试通过；真实检索未宣称 PASS |
| 12 | P1-CATALOG-01 | Governance/config | P1 | 场景数量和输入模式基线漂移 | 发布校验阻塞或错误告警 | high | high | 校验器增加标准输入模式兼容映射 |
| 13 | P1-QUALITY-01 | Agent/verification | P1 | G2-10/G2-11/G2-16/G2-17 | 内容可用但需要人工确认 | high | high | 质量门不降级，显示具体缺口 |
| 14 | P1-RECOVERY-01 | Product/retry_resume | P1 | 主要由确定性回归覆盖 | 故障后可能重复副作用 | medium | medium | Runtime checkpoint/retry 回归通过；P6 扩大压力 |
| 15 | P1-COST-01 | Infrastructure/cost | P2 | 尚无完整真实成本样本 | 无法审计模型成本 | low | high | P6 增加 max_cases/max_calls/max_tokens/cost 记录 |

## 第一轮只进入 P2 的问题

选择 P1-UPLOAD-01、P1-RUNTIME-01、P1-EVIDENCE-01、P1-VISION-01、P1-CATALOG-01。它们具有高用户影响、可复现证据和最小修复边界。其余问题保留为 P3/P5/P6 任务，不以答案润色掩盖产品阻断。
