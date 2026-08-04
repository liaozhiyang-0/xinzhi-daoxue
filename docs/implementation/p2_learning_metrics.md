# P2 学习反馈与教师统计

## 目标

本阶段把已有的学习闭环数据变成教师/管理员可读取的汇总指标，暂不新增反馈事件表，也不改变 `PracticeAttemptModel`、`RetestPlanModel` 的数据库结构。这样可以先验证指标语义和使用方式，再决定是否需要增量 migration 或物化汇总表。

## 接口

```text
GET /api/v1/learning/metrics
```

可选参数：

- `course_id`：按课程筛选；不传时统计全部课程。
- `window_start`、`window_end`：ISO 8601 时间窗口，左闭右开；缺省为最近 30 天。
- `row_limit`：单类记录的读取上限，默认 5000，最大 20000。

返回 `LearningMetricsRead` v1，包含：

- 学习尝试的总数、状态分布、验证状态分布；
- 人工审核计数；
- `feedback_uptake` 状态分布、可判定事件数、可判定率和“采纳后被确定为正确”的计数；
- 复测计划总数和状态分布；
- `truncated` 与 `data_quality_warnings`。

接口只返回聚合结果，不返回学生 ID、答案文本或题目内容。启用认证后，仅教师和管理员可访问；开发/测试配置 `auth_required=false` 时保持本地调试可用。

## 指标边界

这些指标是本地数据库中的确定性运行遥测，不是学习效果、学生接受度、因果收益或模型准确率。`feedback_uptake_correct_rate` 的分母只包含四种可判定状态：`applied_correctly`、`applied_incorrectly`、`partially_applied`、`not_applied`；`indeterminate` 和 `not_applicable` 不进入该分母。

当前统计会在应用层读取 JSON 字段并按 `row_limit` 截断。出现截断时响应会标记 `truncated=true`，不能把截断结果当作全量报表。若后续规模需要全量统计，应新增事件列或汇总表 migration，并保留本接口契约。

## 验证

在项目根目录执行：

```powershell
pytest apps/api/tests/test_learning_metrics.py -q
```

## Teacher workspace

The read-only teacher workspace is available at `/teacher`. It reuses the
same metrics endpoint, provides course and time-window filters, and renders
feedback/verification distributions plus explicit truncation and data-quality
warnings. It does not expose student identifiers or answer content.

该测试验证课程筛选、反馈状态聚合、人工审核识别、复测聚合和非法时间窗口处理。
