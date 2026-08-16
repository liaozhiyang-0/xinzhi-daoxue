# 开发态 Mock Agent 指南

开发态Mock只验证输入映射、输出结构、`business_data`、Parser边界和页面容器，不评价智能质量。配置位于唯一Agent注册表的`development`字段，确定性profile位于`agent_configs/mock_profiles.yaml`。

## 启用条件

必须同时满足：`APP_ENV`为`development`或`test`、`ALLOW_AGENT_MOCKS=true`、Agent的`development.mock_enabled=true`、profile存在、请求显式设置`allow_mock=true`。`production`会由代码强制关闭执行动作，即使环境变量误设为true也不会生成Mock答案。

Mock结果固定包含：`provider=mock`、`mock_used=true`、`mock_profile`、`cloud_status=not_called`和“当前结果来自开发态 Mock，仅用于协议联调”警告。被禁止时返回 planned 状态、`provider=none`，不会伪装成本地 Runtime 成功。

运行方式：

```powershell
$env:ALLOW_AGENT_MOCKS="true"
python scripts/agent_cli.py dry-run TEACH_01_LESSON_PREP_V1
# 页面：http://127.0.0.1:8000/debug/agents
```

新增profile时只填写确定性协议示例。文献跟踪不得伪造论文，数据分析不得伪造数值，教师分析不得放入真实学生隐私。每个计划Agent必须有正常、缺失必填和边界三类fixture。
