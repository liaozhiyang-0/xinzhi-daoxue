# Agent 接入控制台指南

地址：`http://127.0.0.1:8000/debug/agents`。

页面显示Agent版本、发布状态、configured布尔值、Parser、RetrievalPolicy、fallback、输入/输出映射、mock profile、最近一次进程内契约结果和ExecutionPlan。页面永不返回完整Flow ID、Key、Secret、Authorization、本地绝对资料路径或向量。

支持Validate、Dry-run、Mock、fixture契约测试以及Mock/Cloud结构比较。计划Agent在发布前只能用脱敏`cloud_sample`比较；依据仓库安全规则，只有已发布、已启用且配置完整的Agent才能在显式确认后真实调用Cloud。结构比较只比较字段、类型、缺失和额外字段，不判断答案语义优劣。

`RAG_DEBUG_ENABLED=false`时接口不可用；production默认禁止所有执行动作，页面仅可读取脱敏注册状态。页面不能修改`.env`或读取任意本地文件。
