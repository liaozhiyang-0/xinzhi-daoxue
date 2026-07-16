# SOLVER_CT 导出解析结果

BLOCKED：本轮附件未包含 `SOLVER_CT_电路理论专业解题_v1.0.yml`。

原始 YAML 应放入：

```text
.local_inputs/SOLVER_CT_电路理论专业解题_v1.0.yml
```

然后运行：

```powershell
.\.venv\Scripts\python.exe scripts\inspect_xingchen_workflow.py `
  --input ".local_inputs\SOLVER_CT_电路理论专业解题_v1.0.yml" `
  --output-dir "docs\baseline\generated"
```

原始 YAML 被 `.gitignore` 和 `.dockerignore` 排除，不得提交。未获得源文件前，不生成或猜测节点数、连线数、SHA-256 与内部资源配置。
