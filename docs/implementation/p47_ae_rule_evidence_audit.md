# P47：AE 课程规则证据覆盖审计

## 目标

现有课程资产审计可以统计技能引用的错误签名和教师复核模板覆盖率，但不能回答运行时 CoursePack 的每条 `verification_rule` 是否有确定性验证器和测试证据。本阶段增加只读的规则证据审计，不改变运行时规则、不加载候选错误模板。

## 实现

- 在 `config/course_assets/AE.yaml` 增加 `verification_rule_evidence.v1` 映射：记录验证器 ID/路径、每条规则对应的冲突类型和测试文件。
- `scripts/audit_course_assets.py` 从运行时 `CourseRegistry` 读取真实规则，再检查清单映射、验证器文件、冲突类型字符串和测试文件是否存在。
- 审计输出新增 `courses.AE.verification_rule_coverage`，包括运行时规则数量、证据覆盖率、逐规则状态和 schema 错误。
- 证据缺失或文件/冲突类型不一致时标记 `review`；审计只读，不会把模板写入 `config/error_pool/AE.yaml`，也不会创建 release 文件。

## 当前证据

当前 AE 的 4 条运行时规则均有验证器与测试证据：

- `operating_region`
- `small_signal_prerequisite`
- `feedback_polarity`
- `unit_consistency`

因此当前审计证据覆盖率为 4/4。该指标只表示代码证据链完整，不代表 AE CoursePack 已达到 `complete`、不代表模型准确率，也不替代教师复核和官方规则核验。错误池模板覆盖率仍由独立字段统计，当前仍是部分覆盖。

## 风险与边界

规则证据覆盖不等于所有输入都能被验证，也不等于候选错误模板已经发布；审计继续保持只读并排除三个负责人设计的演示案例。

## 验证命令

```powershell
.venv\Scripts\python.exe scripts/audit_course_assets.py --course AE
.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_audit.py -q --no-cov
```

三个演示案例仍由用户设计，未纳入自动生成或本审计的完成条件。
