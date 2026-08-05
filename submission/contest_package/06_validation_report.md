# 06 效果验证报告（待运行记录）

本文件是报告模板，不包含虚构指标。每次填报必须同时记录：

- 命令、输入数据集、运行模式和随机种子（如适用）
- 报告路径、运行 ID、案例集合 SHA-256 和实现指纹
- 通过/失败/错误/超时数量及其边界说明
- 是否离线、Mock、本地确定性或真实 Provider
- 人工复核范围、数据授权和未解决风险

建议的本地校验命令：

```powershell
.\.venv\Scripts\python.exe scripts\run_evaluation.py --validate-only
.\.venv\Scripts\python.exe scripts\audit_course_assets.py --course CT --course AE
.\.venv\Scripts\python.exe scripts\validate_config.py
```

这些命令不等于官方竞赛成绩，也不替代真实用户试用记录。
