# 教学基础配置与验证

第一阶段没有新增密钥、环境变量、数据库表或 migration。运行时自动读取：

- `config/skills/CT.yaml`、`AE.yaml`、`DE.yaml`
- `config/error_pool/CT.yaml`、`AE.yaml`、`DE.yaml`

错因池仅允许 `teacher_reviewed: true`、`enabled: true` 且
`match_mode: exact_rule` 的模板参与匹配。未精确命中时返回 `not_matched`，不得用
相似文本猜测错因。

Windows 验证命令：

```powershell
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe scripts\validate_evaluation_cases.py
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_teaching_foundation_contracts.py apps/api/tests/test_skill_registry.py apps/api/tests/test_solution_packet_adapter.py apps/api/tests/test_evidence_packet_adapter.py apps/api/tests/test_error_pool.py apps/api/tests/test_teaching_foundation_integration.py apps/api/tests/test_teaching_foundation_evaluation.py
```

`validate_config.py` 输出 CT/AE/DE 的技能数和受审核错因模板数；任一 YAML 格式、
引用、前置关系或注册标识异常都会以非零状态退出。公开的
`evaluation/cases/teaching_foundation/` 全部标记为 synthetic 且
`official_scoring: false`，不能作为真实教学效果或学科准确率结论。
