# P58：静态资产与 readiness 一致性审计

P58 为课程资产静态审计和 API readiness 摘要增加只读交叉校验，避免两个入口在长期维护中分别读取后出现状态漂移。审计只比较现有仓库证据，不执行 Provider、OCR、教师审批或 release 写入。

## 校验范围

- CT/AE 的运行时加载标志和 registry 来源；
- 教师复核队列数量、未覆盖签名和候选模板数量；
- 确定性校验证据就绪数量与教师证据缺失数量；
- 候选模板的 `runtime_eligible` 必须继续为 `false`；
- 竞赛材料包状态，以及官方规则、官方成绩、三个演示案例、真实用户结果和真实 Provider 结果五项边界。

新增脚本输出 `course_asset_readiness_consistency.v1`。`status=consistent` 只表示静态审计和 readiness 对当前仓库状态的读取结果一致，不代表官方竞赛验收、真实用户试用或线上发布已完成。

## 可复现验证

```powershell
.venv\Scripts\python.exe -m pytest apps/api/tests/test_readiness_consistency_audit.py -q --no-cov
.venv\Scripts\python.exe scripts/audit_readiness_consistency.py --course CT --course AE
```

当前预期：一致性审计为 `consistent`，候选模板的运行时可用数量为 0；三个演示案例仍由负责人设计，未被脚本生成或纳入结果声明。
