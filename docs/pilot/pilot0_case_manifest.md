# Pilot 0 Case Manifest

> 这是匿名审计索引，不是完整原始用户数据集。`pilot_user_id` 未从历史记录复制；缺失字段保持 `null`，不补造时间、延迟、评分或模型调用次数。

| record_id | pilot_user_id | scenario | task_id | evidence_level | status / gate | source |
| --- | --- | --- | --- | --- | --- | --- |
| PILOT-REC-G2-05 | null | G2-05 BJT 两周学习路径 | `task_114f6e78ff6c49f0a8c8ed86b5f2b891` | L3 | API/Edge 完成；证据不足、待复核 | 31 场景台账 |
| PILOT-REC-G2-08 | null | G2-08 Mealy/Moore 翻转课堂 | `task_de41531d7f8a4ea2a51888642d8d721d` | L3 | 真实生成完成；课时/证据需教师确认 | 31 场景台账 |
| PILOT-REC-G2-10 | null | G2-10 旁路电容首错 | `task_5ec21ab6e3584aada03059841c01687b` | L3 | 真实链路完成；语义门禁需复核 | 31 场景台账 |
| PILOT-REC-G2-11 | null | G2-11 CMOS 功耗诊断 | `task_9884cc13cf704ff88061cb9543d28907` | L3 | 真实链路完成；教师复核未完成 | 31 场景台账 |
| PILOT-REC-G2-12 | null | G2-12 四周电源训练 | `task_90d0b0810bc340529de6822cd77f4ce4` | L3 | 真实链路完成；安全边界需教师确认 | 31 场景台账 |
| PILOT-REC-G2-13 | null | G2-13 拉普拉斯补救路径 | `task_60dbbc1f5d0a4342923d342badf2d991` | L3 | 真实生成完成；课程证据不足 | 31 场景台账 |
| PILOT-REC-G2-16 | null | G2-16 BJT 纯文本诊断 | `task_2c0be8b54551426ea89970a7cee10127` | L3 | 真实生成完成；人工复核门保留 | 31 场景台账 |
| PILOT-REC-G2-17 | null | G2-17 积分器漂移诊断 | `task_55ae950ed6164f978d3c2f92daa2bf5d` | L3 | 真实生成完成；人工复核/数学风险保留 | 31 场景台账 |
| PILOT-REC-Q01 | null | G1-Q01 卷积图像题 | `task_1bf25313a69340149f54bc26726e9d02` | L3 | 真实后端完成；Edge T2 未冻结为 PASS | 31 场景台账 |
| PILOT-REC-Q02 | null | G1-Q02 傅里叶频谱图 | `task_7ba07093d3e147f7b092b913ebfb7035` | L3 | 真实视觉/求解完成；发布门需复核 | 31 场景台账 |
| PILOT-REC-AC01 | null | AC-01 运放题图演示 | null | L1/L2 | 控制面与图片导入回归 PASS | 六案例报告/控制面脚本 |

## 字段完整性

历史记录没有统一保存所有 Pilot 字段（例如匿名用户、统一评分、延迟 p50/p95），因此这些字段不在本 manifest 中伪造。P7 必须按同一模板补齐真实 Final Pilot 记录。
