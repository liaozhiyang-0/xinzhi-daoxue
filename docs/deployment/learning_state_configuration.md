# 学习状态配置

配置文件：`config/learning_mastery.yaml`，当前版本 `2.0`。

配置包含：

- `score_bounds` 和 `confidence_bounds`；
- `evidence_updates` 的 mastery 与 confidence delta；
- `retest_intervals` 的 1/7/28 天规则；
- `calibration_status: uncalibrated_heuristic`；
- 面向用户的辅助估计声明。

启动时 `LearningOutcomeService` 校验版本、全部证据类型、delta 范围、上下限
和未校准声明。配置错误会阻止应用启动，避免静默使用不完整策略。

验证命令：

```powershell
.\.venv\Scripts\python.exe scripts\validate_config.py
```

这些值是工程启发式默认值，不是从真实学生数据训练或统计校准得到的参数。生产
部署调整前应保留版本、评审依据和回归测试，不应将分数解释为考试成绩或真实
掌握概率。
