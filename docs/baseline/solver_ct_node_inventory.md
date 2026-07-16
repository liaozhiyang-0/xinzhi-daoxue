# SOLVER_CT v1.0 节点清单

BLOCKED：本轮未收到原始星辰 YAML，因此不报告或猜测节点数、连线数与节点类型统计。

解析工具已提供：

```powershell
.\.venv\Scripts\python.exe scripts\inspect_xingchen_workflow.py `
  --input ".local_inputs\SOLVER_CT_电路理论专业解题_v1.0.yml" `
  --output-dir "docs\baseline\generated"
```

生成文件默认只包含节点名称、类型、职责摘要、输入输出变量、显示名称、非敏感参数、连接关系、内容摘要和完整性检查。原始提示词、代码与内部资源 ID 不会完整复制。
